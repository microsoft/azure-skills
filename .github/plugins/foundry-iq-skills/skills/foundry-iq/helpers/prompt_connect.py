from __future__ import annotations

import argparse
import copy
try:
    from . import _cleanup_receipts as cleanup_receipts
except ImportError:
    import _cleanup_receipts as cleanup_receipts
import json
import re
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit

try:
    from . import _prompt_read
    from ._bootstrap_io import MAX_BYTES, read_json, run_cli
    from ._common import (
        MANAGEMENT_AUDIENCE,
        HelperFailure,
        TokenProvider,
        Transport,
        azure_cli_token,
        blocked_result,
        canonical_bytes,
        digest,
        emit_result,
        http_request,
        is_ambiguous_mutation_failure,
        is_ambiguous_sdk_error,
        load_approved_input,
        reject_secrets,
        require_allowed_fields,
        sdk_error_metadata,
    )
except ImportError:
    import _prompt_read
    from _bootstrap_io import MAX_BYTES, read_json, run_cli
    from _common import (  # type: ignore[no-redef]
        MANAGEMENT_AUDIENCE,
        HelperFailure,
        TokenProvider,
        Transport,
        azure_cli_token,
        blocked_result,
        canonical_bytes,
        digest,
        emit_result,
        http_request,
        is_ambiguous_mutation_failure,
        is_ambiguous_sdk_error,
        load_approved_input,
        reject_secrets,
        require_allowed_fields,
        sdk_error_metadata,
    )


ARM_API_VERSION = "2025-10-01-preview"
SDK_MAJOR = "2"
GROUNDING = (
    "For every user question, call knowledge_base_retrieve before answering, "
    "including questions that seem unrelated to the knowledge base. "
    "Answer only from evidence returned for that question and cite the original "
    "sources. Do not answer from general knowledge or assume an answer without "
    "retrieval. If the retrieved evidence does not support an answer, reply "
    "exactly: I don't know. Do not add citations to an unsupported answer. "
    "If retrieval fails, report the failure instead of treating it as no evidence "
    "or answering from general knowledge."
)
PROJECT_ID = re.compile(
    r"^/subscriptions/[^/]+/resourceGroups/[^/]+/providers/"
    r"Microsoft\.CognitiveServices/accounts/(?P<account>[^/]+)/projects/"
    r"(?P<project>[^/]+)$",
    re.IGNORECASE,
)
PROJECT_PATH = re.compile(r"^/api/projects/(?P<project>[^/]+)/?$")
SEARCH_HOST = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,58}[a-z0-9])?\.search\.windows\.net$"
)
KB_MCP_PATH = re.compile(r"^/knowledgebases/[^/]+/mcp$")
SHA256 = re.compile(r"^sha256:[a-f0-9]{64}$")
PLAN_FIELDS = {
    "operation",
    "outcome",
    "sdk_major",
    "project_resource_id",
    "project_endpoint",
    "connection",
    "agent",
    "rbac_verified",
    "allowed_tools",
    "require_approval",
    "permission_forwarding",
    "grounding_instructions",
    "network",
    "owner",
    "cleanup_approved",
    "connection_plan_version",
    "verified_dependencies",
    "agent_versions",
}


def _project_endpoint(value: Any) -> str:
    if not isinstance(value, str):
        raise HelperFailure(
            "project-endpoint-invalid",
            "Project endpoint must be a string.",
            blocked_at="input-resolution",
        )
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise HelperFailure(
            "project-endpoint-invalid", "Project endpoint is malformed.",
            blocked_at="input-resolution",
        ) from error
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".services.ai.azure.com")
        or PROJECT_PATH.fullmatch(parsed.path) is None
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
        or port not in {None, 443}
    ):
        raise HelperFailure(
            "project-endpoint-invalid",
            "Project endpoint must be an HTTPS services.ai.azure.com project URL.",
            blocked_at="input-resolution",
        )
    return value.rstrip("/")


def _project_identity(plan: dict[str, Any]) -> tuple[str, str]:
    project_id = plan.get("project_resource_id")
    match = PROJECT_ID.fullmatch(project_id) if isinstance(project_id, str) else None
    if match is None:
        raise HelperFailure(
            "project-resource-id-invalid",
            "project_resource_id must identify one Microsoft Foundry project.",
            blocked_at="input-resolution",
        )
    endpoint = _project_endpoint(plan.get("project_endpoint"))
    parsed = urlsplit(endpoint)
    endpoint_account = parsed.hostname.removesuffix(".services.ai.azure.com")
    endpoint_match = PROJECT_PATH.fullmatch(parsed.path)
    if (
        endpoint_match is None
        or endpoint_account.casefold() != match.group("account").casefold()
        or unquote(endpoint_match.group("project")).casefold()
        != match.group("project").casefold()
    ):
        raise HelperFailure(
            "project-identity-mismatch",
            "project_endpoint and project_resource_id must identify the same Foundry project.",
            blocked_at="reconciliation",
        )
    return project_id, endpoint


def _connection_url(plan: dict[str, Any]) -> str:
    project_id = plan.get("project_resource_id")
    if not isinstance(project_id, str) or PROJECT_ID.fullmatch(project_id) is None:
        raise HelperFailure(
            "project-resource-id-invalid",
            "project_resource_id must identify one Microsoft Foundry project.",
            blocked_at="input-resolution",
        )
    connection = plan.get("connection")
    if not isinstance(connection, dict):
        raise HelperFailure(
            "connection-invalid",
            "connection must be an object.",
            blocked_at="input-resolution",
        )
    name = connection.get("name")
    if not isinstance(name, str) or not name:
        raise HelperFailure(
            "connection-invalid",
            "connection.name is required.",
            blocked_at="input-resolution",
        )
    return (
        "https://management.azure.com"
        f"{project_id}/connections/{quote(name, safe='')}?"
        + urlencode({"api-version": ARM_API_VERSION})
    )


def connection_definition(plan: dict[str, Any]) -> dict[str, Any]:
    connection = plan["connection"]
    return {
        "name": connection["name"],
        "type": "Microsoft.CognitiveServices/accounts/projects/connections",
        "properties": {
            "authType": "ProjectManagedIdentity",
            "category": "RemoteTool",
            "target": connection["target"],
            "isSharedToAll": connection.get("is_shared_to_all", True),
            "audience": "https://search.azure.com/",
            "metadata": {"ApiType": "Azure"},
        },
    }


def _subset(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _subset(value, actual[key])
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(expected) == len(actual)
            and all(_subset(left, right) for left, right in zip(expected, actual))
        )
    return expected == actual


def _connection_readback(
    plan: dict[str, Any], actual: dict[str, Any]
) -> tuple[bool, list[str]]:
    expected = connection_definition(plan)
    properties = actual.get("properties")
    expected_id = (
        f"{plan['project_resource_id']}/connections/{plan['connection']['name']}"
    )
    actual_id = actual.get("id")
    if (
        actual.get("name") != expected["name"]
        or (
            "id" in actual
            and (
                not isinstance(actual_id, str)
                or actual_id.casefold() != expected_id.casefold()
            )
        )
        or not isinstance(properties, dict)
    ):
        return False, []
    required = {
        key: value
        for key, value in expected["properties"].items()
        if key != "isSharedToAll"
    }
    if not _subset(required, properties):
        return False, []

    expected_sharing = expected["properties"]["isSharedToAll"]
    actual_sharing = properties.get("isSharedToAll")
    if not isinstance(actual_sharing, bool) or (
        actual_sharing and not expected_sharing
    ):
        return False, []
    if not expected_sharing and properties.get("sharedUserList", []) != []:
        return False, []
    warnings = []
    if actual.get("type") != expected["type"]:
        warnings.append(
            "connection-type-metadata-differs: ARM type metadata differs from the "
            "Foundry project type; the exact resource path and binding were checked."
        )
    if expected_sharing and not actual_sharing:
        warnings.append(
            "connection-sharing-restricted: requested isSharedToAll=true but Azure "
            "returned false; retained without widening access. Agent invocation "
            "is required to verify usability."
        )
    return True, warnings


def connection_leaf(value: Any) -> str:
    return str(value or "").rstrip("/").rsplit("/", 1)[-1]


def normalized_tool(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("authorization") is not None or value.get("connector_id") is not None:
        raise _prompt_read.fail(
            "agent-tool-auth-unverified",
            "Selected MCP inline authorization or connector configuration requires a supported explicit auth-migration contract; preserve it unchanged.",
        )
    names = value.get("allowed_tools") or []
    if isinstance(names, dict):
        names = names.get("tool_names") or []
    return {
        "type": str(value.get("type") or "").lower(),
        "server_label": value.get("server_label"),
        "server_url": value.get("server_url"),
        "project_connection_id": connection_leaf(
            value.get("project_connection_id")
        ),
        "allowed_tools": sorted(names),
        "require_approval": str(value.get("require_approval") or "").lower(),
        "headers": dict(sorted((value.get("headers") or {}).items())),
    }


def normalized_agent_definition(
    value: dict[str, Any], server_label: str
) -> dict[str, Any]:
    normalized = json.loads(json.dumps(value))
    for tool in normalized.get("tools") or []:
        if (
            not isinstance(tool, dict)
            or tool.get("type") != "mcp"
            or tool.get("server_label") != server_label
        ):
            continue
        allowed = tool.get("allowed_tools")
        if isinstance(allowed, list):
            tool["allowed_tools"] = {"tool_names": allowed}
        elif isinstance(allowed, dict) and allowed.get("read_only") is None:
            allowed.pop("read_only", None)
    return normalized


def desired_agent_definition(
    current: dict[str, Any],
    expected_tool: dict[str, Any],
    expected_structured_input: tuple[str, dict[str, Any]] | None = None,
    *,
    replace_binding: bool = False,
) -> tuple[dict[str, Any], bool]:
    desired = json.loads(json.dumps(current))
    tools = list(desired.get("tools") or [])
    same_label = [
        tool
        for tool in tools
        if tool.get("server_label") == expected_tool.get("server_label")
    ]
    if len(same_label) > 1:
        raise HelperFailure(
            "duplicate-tool-label",
            "More than one knowledge-base MCP tool uses the approved label.",
            blocked_at="reconciliation",
        )
    if same_label and same_label[0].get("headers") and same_label[0]["headers"] != expected_tool.get("headers"):
        raise _prompt_read.fail(
            "agent-tool-auth-unverified",
            "Selected MCP headers conflict with the approved authentication recipe; no implicit credential migration is allowed.",
        )
    replace = bool(same_label and normalized_tool(same_label[0]) != normalized_tool(expected_tool))
    if replace and (not replace_binding or same_label[0].get("type") != "mcp"):
        raise HelperFailure(
            "agent-definition-drift",
            "The existing same-label MCP tool conflicts with the approved binding.",
            blocked_at="reconciliation",
        )
    instructions = str(desired.get("instructions") or "").rstrip()
    structured_exact = True
    if expected_structured_input is not None:
        input_name, input_definition = expected_structured_input
        structured_inputs = desired.get("structured_inputs") or {}
        if not isinstance(structured_inputs, dict):
            raise HelperFailure(
                "agent-definition-drift",
                "Existing structured inputs are not an object.",
                blocked_at="reconciliation",
            )
        current_input = structured_inputs.get(input_name)
        if current_input is not None and current_input != input_definition:
            raise HelperFailure(
                "agent-definition-drift",
                "The permission-forwarding structured input conflicts with the approved binding.",
                blocked_at="reconciliation",
            )
        structured_exact = current_input == input_definition
    tool_exact = bool(same_label) and not replace
    grounding_exact = GROUNDING in instructions
    if tool_exact and grounding_exact and structured_exact:
        return desired, False
    if replace:
        replacement = {**same_label[0], **expected_tool}
        if "headers" not in expected_tool:
            replacement.pop("headers", None)
        desired["tools"] = [replacement if tool is same_label[0] else tool for tool in tools]
    elif not tool_exact:
        tools.append(expected_tool)
        desired["tools"] = tools
    if not grounding_exact:
        desired["instructions"] = f"{instructions}\n\n{GROUNDING}".strip()
    if expected_structured_input is not None and not structured_exact:
        input_name, input_definition = expected_structured_input
        structured_inputs = dict(desired.get("structured_inputs") or {})
        structured_inputs[input_name] = input_definition
        desired["structured_inputs"] = structured_inputs
    return desired, True


def _validate_plan(plan: dict[str, Any], *, resolved: bool = True) -> None:
    reject_secrets(plan)
    require_allowed_fields(plan, PLAN_FIELDS, label="Prompt connection plan")
    if plan.get("grounding_instructions") != GROUNDING:
        raise HelperFailure(
            "grounding-instructions-mismatch",
            "The plan must bind the current exact grounding_instructions; obtain new approval.",
            blocked_at="confirmation",
        )
    network = plan.get("network")
    if network is not None:
        if not isinstance(network, dict):
            raise HelperFailure(
                "input-schema-invalid",
                "network must be an object.",
                blocked_at="input-resolution",
            )
        require_allowed_fields(
            network,
            {"posture", "evidence"},
            label="network",
        )
    if plan.get("operation") != "connect":
        raise HelperFailure(
            "operation-invalid",
            "Prompt helper supports only operation connect.",
            blocked_at="input-resolution",
        )
    if plan.get("cleanup_approved") is not False:
        raise HelperFailure(
            "cleanup-boundary-invalid",
            "Connection approval must not include cleanup.",
            blocked_at="confirmation",
        )
    if plan.get("sdk_major") != 2:
        raise HelperFailure(
            "sdk-version-invalid",
            "The approved plan must bind azure-ai-projects major version 2.",
            blocked_at="input-resolution",
        )
    _project_identity(plan)
    connection = plan.get("connection")
    agent = plan.get("agent")
    rbac = plan.get("rbac_verified")
    if not isinstance(connection, dict) or not isinstance(agent, dict):
        raise HelperFailure(
            "input-schema-invalid",
            "connection and agent objects are required.",
            blocked_at="input-resolution",
        )
    require_allowed_fields(
        connection,
        {"name", "target", "action", "expected_etag", "is_shared_to_all"},
        label="Prompt connection target",
    )
    if not isinstance(connection.get("is_shared_to_all", True), bool):
        raise HelperFailure(
            "connection-invalid",
            "connection.is_shared_to_all must be a boolean.",
            blocked_at="input-resolution",
        )
    require_allowed_fields(
        agent,
        {"name", "version", "model", "expected_definition_digest", "binding_action"},
        label="Prompt agent target",
    )
    target = connection.get("target")
    parsed_target = urlsplit(target) if isinstance(target, str) else None
    if (
        parsed_target is None
        or parsed_target.scheme != "https"
        or parsed_target.hostname is None
        or SEARCH_HOST.fullmatch(parsed_target.hostname) is None
        or KB_MCP_PATH.fullmatch(parsed_target.path) is None
        or parse_qs(parsed_target.query) != {"api-version": ["2026-08-01-preview"]}
        or parsed_target.fragment
        or parsed_target.username
        or parsed_target.password
        or parsed_target.port not in {None, 443}
    ):
        raise HelperFailure(
            "connection-invalid",
            "Connection target must be the exact preview knowledge-base MCP endpoint.",
            blocked_at="input-resolution",
        )
    if connection.get("action") not in {"create", "update", "reuse"}:
        raise HelperFailure(
            "connection-invalid",
            "connection.action must be create, update, or reuse.",
            blocked_at="input-resolution",
        )
    if plan.get("allowed_tools") != ["knowledge_base_retrieve"]:
        raise HelperFailure(
            "tool-policy-invalid",
            "allowed_tools must contain only knowledge_base_retrieve.",
            blocked_at="input-resolution",
        )
    if plan.get("require_approval") != "never":
        raise HelperFailure(
            "tool-policy-invalid",
            "The approved base-only MCP tool policy requires require_approval never.",
            blocked_at="input-resolution",
        )
    forwarding = plan.get("permission_forwarding")
    if not isinstance(forwarding, dict) or forwarding.get("mode") not in {
        "not-applicable",
        "structured-input",
    }:
        raise HelperFailure(
            "permission-forwarding-invalid",
            "permission_forwarding.mode must be not-applicable or structured-input.",
            blocked_at="input-resolution",
        )
    require_allowed_fields(
        forwarding,
        {"mode", "name"},
        label="Permission forwarding",
    )
    if forwarding["mode"] == "structured-input" and forwarding.get("name") != (
        "search_auth_token"
    ):
        raise HelperFailure(
            "permission-forwarding-invalid",
            "Permission forwarding requires the search_auth_token structured input.",
            blocked_at="input-resolution",
        )
    required_agent = {"name", "version"}
    if resolved:
        required_agent |= {"model", "expected_definition_digest"}
    if not required_agent.issubset(agent) or not all(
        isinstance(agent[field], str) and agent[field]
        for field in required_agent
    ):
        raise HelperFailure(
            "agent-invalid",
            "Agent name, version, model, and expected definition digest are required.",
            blocked_at="input-resolution",
        )
    if not isinstance(rbac, dict):
        raise HelperFailure("rbac-unverified", "An exact role-assignment binding is required.", blocked_at="input-resolution")
    if resolved and (
        not isinstance(rbac, dict)
        or rbac.get("verified") is not True
        or not rbac.get("assignment_id")
        or not rbac.get("principal_id")
        or not rbac.get("scope")
        or rbac.get("role") != "Search Index Data Reader"
    ):
        raise HelperFailure(
            "rbac-unverified",
            "Exact Search Index Data Reader assignment readback is required.",
            blocked_at="reconciliation",
        )
    require_allowed_fields(
        rbac,
        {"verified", "assignment_id", "principal_id", "role", "scope"},
        label="RBAC verification",
    )
    if resolved and SHA256.fullmatch(agent["expected_definition_digest"]) is None:
        raise HelperFailure(
            "agent-invalid",
            "expected_definition_digest must be a canonical SHA-256 digest.",
            blocked_at="input-resolution",
        )
    for label, value in (("connection", connection.get("name")), ("agent", agent.get("name")), ("version", agent.get("version"))):
        if not isinstance(value, str) or not _prompt_read.NAME.fullmatch(value):
            raise _prompt_read.fail("input-schema-invalid", label + " requires an exact bounded name.")
    if agent["version"].casefold() in {"latest", "default"}:
        raise _prompt_read.fail("agent-version-unresolved", "Select an exact agent version after portal activity, never implicit latest.")
    if agent.get("binding_action", "ensure") not in {"ensure", "replace-selected"}:
        raise _prompt_read.fail("agent-binding-invalid", "Choose ensure or an explicit replace-selected binding delta.")
    _prompt_read.binding(plan)
    if any(key in plan for key in ("connection_plan_version", "verified_dependencies", "agent_versions")):
        if (plan.get("connection_plan_version") != "1.0" or not isinstance(plan.get("verified_dependencies"), dict)
                or not isinstance(plan.get("agent_versions"), dict) or not plan["agent_versions"]
                or len(plan["agent_versions"]) > 200):
            raise _prompt_read.fail("connection-plan-invalid", "Retain complete supported planner dependency and version evidence.")
        if any(not isinstance(key, str) or not _prompt_read.NAME.fullmatch(key)
               or not isinstance(value, str) or not SHA256.fullmatch(value)
               for key, value in plan["agent_versions"].items()):
            raise _prompt_read.fail("connection-plan-invalid", "Agent version evidence must retain exact version/digest pairs.")
        shapes = {
            "project": {"id", "endpoint", "principal_id", "tenant_id"},
            "search": {"id", "endpoint", "access_digest"}, "knowledge_base": {"name", "definition_digest"},
            "rbac": {"assignment_id", "principal_id", "scope", "role_definition_id"},
            "cli_context": {"subscription_id", "tenant_id", "principal", "principal_type"},
        }
        if set(plan["verified_dependencies"]) != set(shapes):
            raise _prompt_read.fail("connection-plan-invalid", "Retain complete planner dependency sections.")
        for key, fields in shapes.items():
            section = plan["verified_dependencies"][key]
            if (not isinstance(section, dict) or set(section) != fields
                    or any(not isinstance(value, str) or not 1 <= len(value) <= 2048 for value in section.values())):
                raise _prompt_read.fail("connection-plan-invalid", "Dependency evidence has missing or undeclared fields.")


def _unique_resources(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for resource in resources:
        if resource not in result:
            result.append(resource)
    return result


def _unverified_mutation(failure: HelperFailure, identity: dict[str, Any]) -> HelperFailure:
    failure.partial = True
    failure.resources_remaining = _unique_resources(failure.resources_remaining)
    failure.resources_reused = _unique_resources(failure.resources_reused)
    failure.resources_unverified = _unique_resources([*failure.resources_unverified, identity])
    return failure


def _reconcile_connection(
    plan: dict[str, Any],
    token: str,
    *,
    transport: Transport,
    cleanup_capture=None,
) -> tuple[str, dict[str, Any], list[str]]:
    url = _connection_url(plan)
    desired = connection_definition(plan)
    request_ids: list[str] = []
    current, ids = _prompt_read.get_object(url, token, transport, absent=True, label="connection")
    request_ids.extend(ids)
    if current is not None and not isinstance(current, dict):
        raise HelperFailure(
            "connection-readback-invalid",
            "Project connection readback was not a JSON object.",
            blocked_at="reconciliation",
        )
    if current is not None and _connection_readback(plan, current)[0]:
        return "reused", current, request_ids

    action = plan["connection"]["action"]
    headers = {"Content-Type": "application/json"}
    if current is None:
        if action != "create":
            raise HelperFailure(
                "connection-absent",
                "The approved non-create connection target is absent.",
                blocked_at="reconciliation",
            )
        headers["If-None-Match"] = "*"
        completed_action = "created"
    else:
        raise HelperFailure(
            "connection-conflict",
            "The same chosen connection name has a conflicting configuration; preserve it and plan a new explicit name.",
            blocked_at="reconciliation",
        )

    try:
        result = transport(
            "PUT",
            url,
            token,
            body=canonical_bytes(desired),
            headers=headers,
        )
    except HelperFailure as failure:
        if not is_ambiguous_mutation_failure(failure):
            raise
        if cleanup_capture is not None:
            _unverified_mutation(failure, {
                "type": "project-connection",
                "name": plan["connection"]["name"],
                "resource_id": plan["project_resource_id"] + "/connections/" + plan["connection"]["name"],
            })
            failure.warnings.append("Connection create acknowledgement is unproven; GET recovery cannot produce ownership or cleanup evidence.")
            raise
        return _recover_ambiguous_connection(
            plan,
            url,
            token,
            desired,
            completed_action,
            request_ids,
            failure,
            transport=transport,
        )
    if result.status not in {200, 201}:
        if result.status in {408, 429} or result.status >= 500:
            if cleanup_capture is not None:
                raise _unverified_mutation(
                    HelperFailure("connection-outcome-ambiguous", "Connection acknowledgement is unproven; no recovery ownership.",
                                  blocked_at="execution", status=result.status, request_id=result.request_id),
                    {"type": "project-connection", "name": plan["connection"]["name"],
                     "resource_id": plan["project_resource_id"] + "/connections/" + plan["connection"]["name"]},
                )
            return _recover_ambiguous_connection(
                plan,
                url,
                token,
                desired,
                completed_action,
                request_ids,
                HelperFailure(
                    "connection-outcome-ambiguous",
                    f"Connection mutation returned ambiguous HTTP {result.status}.",
                    blocked_at="execution",
                    request_id=result.request_id,
                    status=result.status,
                    partial=True,
                ),
                transport=transport,
            )
        raise HelperFailure(
            "connection-mutation-failed",
            f"Connection create or update returned HTTP {result.status}.",
            blocked_at="execution",
            request_id=result.request_id,
            status=result.status,
        )
    if result.request_id:
        request_ids.append(result.request_id)
    write = {"action": completed_action, "connection": desired["name"]}
    try:
        if completed_action == "created" and cleanup_capture is not None:
            cleanup_receipts.connection_ack(cleanup_capture, plan, result)
        readback = transport("GET", url, token)
        if (completed_action == "created" and cleanup_capture is not None and readback.status == 200
                and isinstance(readback.body, dict) and _connection_readback(plan, readback.body)[0]):
            cleanup_receipts.connection_finish(cleanup_capture, plan, readback.body)
    except HelperFailure as failure:
        raise HelperFailure(
            failure.code,
            failure.message,
            blocked_at=failure.blocked_at,
            writes=[write, *failure.writes],
            resources_remaining=[
                {
                    "type": "project-connection",
                    "name": plan["connection"]["name"],
                }
            ],
            request_id=failure.request_id,
            status=failure.http_status,
            partial=True,
        ) from failure
    if readback.request_id:
        request_ids.append(readback.request_id)
    if readback.status != 200 or not isinstance(readback.body, dict):
        raise HelperFailure(
            "connection-readback-invalid",
            "Connection readback did not return one JSON object.",
            blocked_at="verification",
            writes=[write],
            resources_remaining=[
                {
                    "type": "project-connection",
                    "name": plan["connection"]["name"],
                }
            ],
            request_id=readback.request_id,
            partial=True,
        )
    if not _connection_readback(plan, readback.body)[0]:
        raise HelperFailure(
            "connection-readback-mismatch",
            "Connection readback does not match the approved definition.",
            blocked_at="verification",
            writes=[write],
            resources_remaining=[
                {
                    "type": "project-connection",
                    "name": plan["connection"]["name"],
                }
            ],
            request_id=readback.request_id,
            partial=True,
        )
    return completed_action, readback.body, request_ids


def _recover_ambiguous_connection(
    plan: dict[str, Any],
    url: str,
    token: str,
    desired: dict[str, Any],
    completed_action: str,
    request_ids: list[str],
    failure: HelperFailure,
    *,
    transport: Transport,
) -> tuple[str, dict[str, Any], list[str]]:
    identity = {
        "type": "project-connection",
        "name": plan["connection"]["name"],
    }
    if failure.request_id:
        request_ids.append(failure.request_id)
    try:
        readback = transport("GET", url, token)
    except HelperFailure as readback_failure:
        raise HelperFailure(
            "connection-outcome-ambiguous",
            "Connection mutation and same-identity readback are ambiguous.",
            blocked_at="verification",
            resources_remaining=[identity],
            request_id=readback_failure.request_id or failure.request_id,
            status=failure.http_status,
            partial=True,
        ) from readback_failure
    if readback.request_id:
        request_ids.append(readback.request_id)
    if (
        readback.status != 200
        or not isinstance(readback.body, dict)
        or not _connection_readback(plan, readback.body)[0]
    ):
        raise HelperFailure(
            "connection-outcome-ambiguous",
            "Same-identity readback did not prove the approved connection mutation.",
            blocked_at="verification",
            resources_remaining=[identity],
            request_id=readback.request_id or failure.request_id,
            status=failure.http_status,
            partial=True,
        )
    return completed_action, readback.body, request_ids


def _load_sdk() -> tuple[Any, Any, Any, Any, Any]:
    try:
        if version("azure-ai-projects").split(".", 1)[0] != SDK_MAJOR:
            raise HelperFailure(
                "sdk-version-invalid",
                "azure-ai-projects 2.x is required.",
                blocked_at="execution",
            )
        from azure.ai.projects import AIProjectClient
        from azure.ai.projects.models import (
            MCPTool,
            PromptAgentDefinition,
            StructuredInputDefinition,
        )
        from azure.core.exceptions import AzureError
        from azure.identity import AzureCliCredential
    except PackageNotFoundError as exc:
        raise HelperFailure(
            "sdk-unavailable",
            "azure-ai-projects 2.x is not installed.",
            blocked_at="execution",
        ) from exc
    except ImportError as exc:
        raise HelperFailure(
            "sdk-unavailable",
            "azure-ai-projects, azure-identity, and azure-core are required.",
            blocked_at="execution",
        ) from exc
    return (
        AIProjectClient,
        MCPTool,
        PromptAgentDefinition,
        StructuredInputDefinition,
        (AzureCliCredential, AzureError),
    )


def _version_ids(agents, name: str) -> list[str]:
    result = agents.list_versions(agent_name=name, include_drafts=True)
    pages = result.by_page() if hasattr(result, "by_page") else [result]
    versions = []
    for page_number, page in enumerate(pages, 1):
        if page_number > 200:
            raise _prompt_read.fail("agent-version-limit", "Selected-agent version pages exceed 200; do not truncate.")
        for item in page:
            value = getattr(item, "version", None)
            if isinstance(value, bool) or not isinstance(value, (str, int)) or not _prompt_read.NAME.fullmatch(str(value)):
                raise _prompt_read.fail("agent-version-invalid", "Selected-agent version inventory is malformed.")
            if str(value) in versions:
                raise _prompt_read.fail("agent-version-ambiguous", "Duplicate version identities in scoped inventory.")
            versions.append(str(value))
            if len(versions) > 200:
                raise _prompt_read.fail("agent-version-limit", "Selected agent has more than 200 versions; do not truncate.")
    return sorted(versions)


def _load_connection_sdk() -> tuple[Any, Any, Any, Any, Any]:
    sdk = _load_sdk()
    installed = re.match(r"^2\.(\d+)\.", version("azure-ai-projects"))
    if installed is None or int(installed[1]) < 4:
        raise _prompt_read.fail("sdk-version-invalid", "Complete Prompt version reads require azure-ai-projects>=2.4.0,<3, including drafts.")
    return sdk


def _version_state(agents, name: str, version_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    item = agents.get_version(agent_name=name, agent_version=version_id)
    return _checked_version_state(item, name, version_id)


def _checked_version_state(item, name: str, version_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    definition = getattr(item, "definition", None)
    if (
        getattr(item, "name", None) != name or str(getattr(item, "version", "")) != version_id
        or definition is None or not hasattr(definition, "as_dict")
    ):
        raise _prompt_read.fail("agent-version-invalid", "SDK readback does not bind the exact selected agent/version.")
    value = definition.as_dict()
    if not isinstance(value, dict) or len(canonical_bytes(value)) > MAX_BYTES:
        raise _prompt_read.fail("agent-definition-invalid", "Agent definition must be a bounded object.")
    tools = value.get("tools")
    if tools is not None and (not isinstance(tools, list) or any(not isinstance(tool, dict) for tool in tools)):
        raise _prompt_read.fail("agent-definition-invalid", "Agent tool inventory is malformed.")
    options = {}
    for key in ("metadata", "description", "draft", "blueprint_reference"):
        option = getattr(item, key, None)
        if option is not None:
            options[key] = option.as_dict() if hasattr(option, "as_dict") else copy.deepcopy(option)
    metadata = options.get("metadata", {})
    if (
        not isinstance(metadata, dict) or len(metadata) > 16
        or any(not isinstance(key, str) or not 1 <= len(key) <= 64
               or not isinstance(item, str) or len(item) > 512 for key, item in metadata.items())
        or ("description" in options and not isinstance(options["description"], str))
        or ("draft" in options and not isinstance(options["draft"], bool))
        or ("blueprint_reference" in options and not isinstance(options["blueprint_reference"], dict))
        or len(canonical_bytes({"definition": value, "version_options": options})) > MAX_BYTES
    ):
        raise _prompt_read.fail("agent-version-invalid", "Writable version settings are malformed or exceed the readback bound.")
    return value, options


def _connect_agent(
    plan: dict[str, Any],
    *,
    sdk_loader: Callable[[], tuple[Any, Any, Any, Any, Any]] = _load_connection_sdk,
    read_only: bool = False,
    resolve: bool = False,
    before_write: Callable[[], None] | None = None,
    cleanup_capture=None,
) -> tuple[str, dict[str, Any]]:
    (
        AIProjectClient,
        MCPTool,
        PromptAgentDefinition,
        StructuredInputDefinition,
        extras,
    ) = sdk_loader()
    AzureCliCredential, AzureError = extras
    agent = plan["agent"]
    connection = plan["connection"]
    created_write: dict[str, Any] | None = None
    client = AIProjectClient(
        endpoint=_project_endpoint(plan["project_endpoint"]),
        credential=AzureCliCredential(),
    )
    try:
        versions = _version_ids(client.agents, agent["name"])
        if agent["version"] not in versions:
            raise HelperFailure(
                "agent-version-absent",
                "The exact existing Prompt Agent version was not found.",
                blocked_at="reconciliation",
            )
        current_definition, version_options = _version_state(client.agents, agent["name"], agent["version"])
        if (
            current_definition.get("kind") != "prompt"
            or not isinstance(current_definition.get("model"), str) or not current_definition["model"]
            or (not resolve and current_definition.get("model") != agent["model"])
        ):
            raise HelperFailure(
                "agent-definition-drift",
                "Agent type or model differs from the approved plan.",
                blocked_at="reconciliation",
            )
        if not resolve and digest(current_definition) != agent["expected_definition_digest"]:
            raise HelperFailure(
                "agent-definition-drift",
                "Agent definition digest changed after approval.",
                blocked_at="reconciliation",
            )
        for tool in current_definition.get("tools") or []:
            if tool.get("server_label") != "knowledge-base":
                continue
            reference = tool.get("project_connection_id")
            leaf = connection_leaf(reference)
            resource_id = plan["project_resource_id"] + "/connections/" + leaf
            if (not isinstance(reference, str) or not _prompt_read.NAME.fullmatch(leaf)
                    or (reference != leaf and reference.casefold() not in {
                        resource_id.casefold(), (MANAGEMENT_AUDIENCE + resource_id).casefold(),
                    })):
                raise _prompt_read.fail("agent-binding-invalid", "The selected tool connection must bind this exact project, not another project's same-name connection.")
        tool_arguments = {
            "server_label": "knowledge-base",
            "server_url": connection["target"],
            "project_connection_id": connection["name"],
            "allowed_tools": plan["allowed_tools"],
            "require_approval": plan["require_approval"],
        }
        expected_structured_input = None
        if plan["permission_forwarding"]["mode"] == "structured-input":
            input_name = plan["permission_forwarding"]["name"]
            tool_arguments["headers"] = {
                "x-ms-query-source-authorization": f"{{{{{input_name}}}}}"
            }
            input_definition = StructuredInputDefinition(
                description="Per-user Azure AI Search bearer token",
                required=True,
                schema={"type": "string"},
            ).as_dict()
            expected_structured_input = (input_name, input_definition)
        expected_tool = MCPTool(
            **tool_arguments,
        ).as_dict()
        desired, changed = desired_agent_definition(
            current_definition,
            expected_tool,
            expected_structured_input,
            replace_binding=agent.get("binding_action") == "replace-selected",
        )
        normalized_desired = normalized_agent_definition(
            desired, tool_arguments["server_label"]
        )
        manifest = {agent["version"]: digest({"definition": current_definition, "version_options": version_options})}
        exact_versions = []
        for version_id in versions:
            if version_id == agent["version"]:
                continue
            candidate_definition, candidate_options = _version_state(client.agents, agent["name"], version_id)
            manifest[version_id] = digest({"definition": candidate_definition, "version_options": candidate_options})
            if candidate_options == version_options and normalized_agent_definition(
                candidate_definition, tool_arguments["server_label"]
            ) == normalized_desired:
                exact_versions.append(
                    {
                        "name": agent["name"],
                        "version": version_id,
                        "definition_digest": digest(candidate_definition),
                    }
                )
        if _version_ids(client.agents, agent["name"]) != versions:
            raise _prompt_read.fail("agent-version-drift", "Version inventory changed during readback; refresh after portal activity.")
        if plan.get("agent_versions") is not None and plan["agent_versions"] != manifest:
            raise _prompt_read.fail("agent-version-drift", "Agent versions changed since planning; refresh the exact scoped inventory.")
        if changed and len(exact_versions) > 1:
            raise HelperFailure(
                "duplicate-desired-agent-version",
                "More than one existing Prompt Agent version matches the approved result.",
                blocked_at="reconciliation",
            )
        reuse = (
            {"name": agent["name"], "version": agent["version"], "definition_digest": digest(current_definition)}
            if not changed else exact_versions[0] if exact_versions else None
        )
        typed_definition = None
        if reuse is None:
            if len(versions) >= 200:
                raise _prompt_read.fail(
                    "agent-version-limit",
                    "Creating another version would exceed the 200-version inventory bound; exact reuse remains available.",
                )
            try:
                typed_definition = PromptAgentDefinition(desired)
                serialized = typed_definition.as_dict()
            except (TypeError, ValueError) as error:
                raise _prompt_read.fail("agent-definition-unsupported", "Installed SDK cannot preserve the complete agent definition; no configuration write is allowed.") from error
            if not isinstance(serialized, dict) or normalized_agent_definition(
                serialized, tool_arguments["server_label"]
            ) != normalized_desired:
                raise _prompt_read.fail("agent-definition-unsupported", "SDK serialization would change unrelated agent state; no configuration write is allowed.")
        if read_only:
            selected_tools = [tool for tool in current_definition.get("tools") or []
                              if tool.get("server_label") == "knowledge-base"]
            old_connection = connection_leaf(selected_tools[0].get("project_connection_id")) if selected_tools else ""
            if old_connection and not _prompt_read.NAME.fullmatch(old_connection):
                raise _prompt_read.fail("agent-binding-invalid", "Observed selected connection identity is malformed; do not guess its replacement.")
            return ("reused" if reuse else "create"), {
                "agent": {**agent, "model": current_definition["model"],
                          "expected_definition_digest": digest(current_definition)},
                "versions": manifest, "desired_digest": digest(desired), "reused": reuse,
                "binding_action": agent.get("binding_action", "ensure"),
                "grounding_appended": GROUNDING not in str(current_definition.get("instructions") or ""),
                "previous_connection": old_connection or None,
            }
        if before_write is not None:
            before_write()
        if reuse is not None:
            return "reused", reuse
        native_response = {}
        try:
            updated = client.agents.create_version(
                agent_name=agent["name"],
                definition=typed_definition,
                **version_options,
                **({"raw_response_hook": cleanup_receipts.sdk_response_hook(native_response)} if cleanup_capture else {}),
            )
        except AzureError as exc:
            if not is_ambiguous_sdk_error(exc):
                raise HelperFailure(
                    message="The Prompt Agent SDK create operation failed.",
                    blocked_at="execution",
                    **sdk_error_metadata(exc, "agent-sdk-failed"),
                ) from exc
            if cleanup_capture is not None:
                raise HelperFailure(message="Version create acknowledgement is ambiguous; GET recovery cannot establish cleanup ownership.",
                                    blocked_at="execution", partial=True,
                                    resources_unverified=[{
                                        "type": "prompt-agent-version", "name": agent["name"],
                                        "project_resource_id": plan["project_resource_id"],
                                        "definition_digest": digest(desired),
                                    }],
                                    **sdk_error_metadata(exc, "agent-create-outcome-ambiguous")) from exc
            identity = {
                "type": "prompt-agent-version",
                "name": agent["name"],
                "definition_digest": digest(desired),
                "run_owned": False,
            }
            try:
                matches = []
                for version_id in _version_ids(client.agents, agent["name"]):
                    candidate_definition, candidate_options = _version_state(client.agents, agent["name"], version_id)
                    if candidate_options == version_options and normalized_agent_definition(
                        candidate_definition, tool_arguments["server_label"]
                    ) == normalized_desired:
                        matches.append(
                            {
                                "name": agent["name"],
                                "version": version_id,
                                "definition_digest": digest(candidate_definition),
                            }
                        )
            except (AzureError, HelperFailure) as readback_exc:
                raise HelperFailure(
                    "agent-create-outcome-ambiguous",
                    "Agent version creation and same-identity readback are ambiguous.",
                    blocked_at="verification",
                    resources_remaining=[identity],
                    partial=True,
                    **sdk_error_metadata(exc),
                ) from readback_exc
            if len(matches) == 1:
                raise HelperFailure(
                    "agent-create-outcome-ambiguous",
                    "An exact version was observed after an ambiguous create, but its creation ownership is unverified.",
                    blocked_at="verification",
                    resources_remaining=[{**identity, **matches[0]}],
                    partial=True,
                    **sdk_error_metadata(exc),
                ) from exc
            raise HelperFailure(
                "agent-create-outcome-ambiguous",
                "Same-agent readback did not identify exactly one approved version.",
                blocked_at="verification",
                resources_remaining=[identity],
                partial=True,
                **sdk_error_metadata(exc),
            ) from exc
        created_write = {
            "action": "created",
            "agent": agent["name"],
        }
        created_identity = {
            "type": "prompt-agent-version",
            "name": agent["name"],
        }
        try:
            receipt_target = cleanup_receipts.agent_ack(cleanup_capture, plan, updated, native_response) if cleanup_capture else None
            created_version = str(getattr(updated, "version", ""))
            if getattr(updated, "name", None) != agent["name"] or not _prompt_read.NAME.fullmatch(created_version):
                raise _prompt_read.fail("agent-version-invalid", "Creation returned an unverified version identity; do not follow another agent name.")
            created_write["version"] = created_version
            created_identity["version"] = created_version
            readback = client.agents.get_version(agent_name=agent["name"], agent_version=created_version)
            readback_definition, readback_options = _checked_version_state(readback, agent["name"], created_version)
            expected_definition, changed_after = desired_agent_definition(
                readback_definition,
                expected_tool,
                expected_structured_input,
            )
            if (
                changed_after
                or readback_options != version_options
                or expected_definition != readback_definition
                or normalized_agent_definition(
                    readback_definition, tool_arguments["server_label"]
                ) != normalized_desired
            ):
                raise HelperFailure(
                    "agent-readback-mismatch",
                    "Created version differs from the approved definition or tool and grounding delta.",
                    blocked_at="verification",
                )
            if cleanup_capture is not None:
                cleanup_capture.finish(receipt_target, {"definition_digest": digest(readback_definition), "etag": None, "generated": [],
                                                       "version_identity": cleanup_receipts.version_identity(readback)})
        except HelperFailure as failure:
            raise HelperFailure(
                failure.code,
                failure.message,
                blocked_at=failure.blocked_at,
                writes=[created_write, *failure.writes],
                resources_remaining=[
                    created_identity,
                    *[
                        item
                        for item in failure.resources_remaining
                        if item != created_identity
                    ],
                ],
                request_id=failure.request_id,
                status=failure.http_status,
                partial=True,
                resources_reused=failure.resources_reused,
                resources_unverified=failure.resources_unverified,
                warnings=failure.warnings,
            ) from failure
        return "created", {
            "name": updated.name,
            "version": str(updated.version),
            "definition_digest": digest(readback_definition),
        }
    except AzureError as exc:
        remaining = (
            [
                {
                    "type": "prompt-agent-version",
                    "name": created_write["agent"],
                    "version": created_write["version"],
                }
            ]
            if created_write is not None
            else []
        )
        raise HelperFailure(
            message="The Prompt Agent SDK operation failed.",
            blocked_at="execution",
            writes=[created_write] if created_write is not None else [],
            resources_remaining=remaining,
            partial=created_write is not None,
            **sdk_error_metadata(exc, "agent-sdk-failed"),
        ) from exc
    finally:
        client.close()


def execute(
    document: dict[str, Any],
    *,
    token_provider: TokenProvider = azure_cli_token,
    transport: Transport = http_request,
    sdk_loader: Callable[[], tuple[Any, Any, Any, Any, Any]] = _load_connection_sdk,
    cli=run_cli,
    cleanup_capture=None,
) -> dict[str, Any]:
    plan = document["plan"]
    fingerprint = document["_computed_fingerprint"]
    if plan.get("operation") == "create-initial-prompt-agent":
        try:
            from . import _initial_prompt, prompt_cleanup
        except ImportError:
            import _initial_prompt, prompt_cleanup
        if sdk_loader in (_load_sdk, _load_connection_sdk):
            sdk_loader = prompt_cleanup.load_cleanup_sdk
        return _initial_prompt.execute(document, capture=cleanup_capture, token_provider=token_provider,
                                       transport=transport, sdk_loader=sdk_loader)
    _validate_plan(plan)
    if cleanup_capture is not None and (
        not isinstance(cleanup_capture, cleanup_receipts.Capture) or cleanup_capture.plan_digest != fingerprint
        or cleanup_capture.owner != plan.get("owner")
    ):
        raise HelperFailure("cleanup-receipt-input-invalid", "Capture must bind this exact approved connection plan.", blocked_at="confirmation")
    if cleanup_capture is not None and sdk_loader in (_load_sdk, _load_connection_sdk):
        try:
            from .prompt_cleanup import load_cleanup_sdk
        except ImportError:
            from prompt_cleanup import load_cleanup_sdk
        loaded = load_cleanup_sdk()
        sdk_loader = lambda: loaded
    connection_action, connection = "", {}
    request_ids, connection_warnings, connection_write = [], [], []
    def preflight_connection():
        nonlocal connection_action, connection, request_ids, connection_write
        _, _, warnings, ids = _prompt_read.read_dependencies(
            plan, token_provider=token_provider, transport=transport, cli=cli,
            capture_context=plan.get("connection_plan_version") is not None,
        )
        connection_warnings.extend(warnings)
        request_ids.extend(ids)
        connection_action, connection, ids = _reconcile_connection(
            plan, token_provider(MANAGEMENT_AUDIENCE), transport=transport,
            **({"cleanup_capture": cleanup_capture} if cleanup_capture else {}),
        )
        request_ids.extend(ids)
        connection_warnings.extend(_connection_readback(plan, connection)[1])
        if connection_action != "reused":
            connection_write = [{"action": connection_action, "connection": plan["connection"]["name"]}]
    try:
        agent_action, agent = _connect_agent(
            plan, sdk_loader=sdk_loader, before_write=preflight_connection,
            **({"cleanup_capture": cleanup_capture} if cleanup_capture else {}),
        )
    except HelperFailure as failure:
        raise HelperFailure(
            failure.code,
            failure.message,
            blocked_at=failure.blocked_at,
            writes=connection_write + failure.writes,
            resources_remaining=_unique_resources(
                (
                    [
                        {
                            "type": "project-connection",
                            "name": plan["connection"]["name"],
                        }
                    ]
                    if connection_write
                    else []
                )
                + failure.resources_remaining
            ),
            resources_unverified=_unique_resources(failure.resources_unverified),
            request_id=failure.request_id,
            status=failure.http_status,
            partial=bool(connection_write or failure.writes or failure.partial),
            warnings=connection_warnings + failure.warnings,
            resources_reused=_unique_resources((
                [{"type": "project-connection", "name": plan["connection"]["name"]}]
                if connection_action == "reused" else []
            ) + failure.resources_reused),
        ) from failure

    resources = {"created": [], "reused": [], "updated": [], "skipped": []}
    resources[connection_action].append(
        {"type": "project-connection", "name": plan["connection"]["name"]}
    )
    resources[agent_action].append({"type": "prompt-agent-version", **agent})
    return {
        "status": "completed",
        "outcome": str(plan.get("outcome") or "connect-existing-prompt-agent"),
        "approved_plan": {"fingerprint": fingerprint, "confirmed": True},
        "resources": resources,
        "api_contracts": [
            {
                "operation": "project-connection",
                "version": ARM_API_VERSION,
                "preview": True,
            },
            {
                "operation": "prompt-agent-version",
                "version": "azure-ai-projects-2.x",
                "preview": True,
            },
        ],
        "data_movement": {"boundary": "knowledge-base MCP retrieval", "result": "bound"},
        "auth": {"mode": "managed-identity", "principals": [plan["rbac_verified"]["principal_id"]]},
        "rbac": {"assignments": [plan["rbac_verified"]["assignment_id"]]},
        "network": plan.get("network", {"posture": "preserved", "evidence": None}),
        "verification": {
            "connection_readback": {
                "name": connection.get("name"),
                "definition_digest": digest(connection),
                "request_ids": request_ids,
                "actual_is_shared_to_all": connection["properties"]["isSharedToAll"],
            },
            "agent_readback": agent,
            "permission_forwarding": plan["permission_forwarding"],
            "idempotency": "compatible connection and exact tool/grounding state is zero-write",
            "agent_invocation": "not-run; required for end-to-end verification",
        },
        "warnings": connection_warnings,
        "ownership": {
            "run_owned": connection_write
            + ([{"type": "prompt-agent-version", **agent}] if agent_action == "created" else []),
            "reused_not_owned": (
                [{"type": "project-connection", "name": plan["connection"]["name"]}]
                if connection_action == "reused"
                else []
            )
            + ([{"type": "prompt-agent-version", **agent}] if agent_action == "reused" else []),
            "owner": plan.get("owner"),
        },
        "cleanup": {
            "status": "not-requested",
            "separate_confirmation_required": True,
        },
    }


def plan_source(request: dict[str, Any], *, token_provider=azure_cli_token,
                transport=http_request, sdk_loader=_load_connection_sdk, cli=run_cli) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise _prompt_read.fail("input-schema-invalid", "Prompt planning requires a resolved intent object.")
    reject_secrets(request)
    fields = {
        "schema_version", "project_resource_id", "project_endpoint", "search_resource_id",
        "knowledge_base_name", "agent_name", "agent_version", "connection_name",
        "is_shared_to_all", "binding_action", "role_assignment_id", "permission_forwarding",
        "network", "owner",
    }
    require_allowed_fields(request, fields, label="Prompt planning intent")
    if set(request) != fields or request["schema_version"] != "1.0":
        raise _prompt_read.fail("input-schema-invalid", "Supply all documented Prompt intent decisions; no inferred future approval.")
    for field in ("knowledge_base_name", "agent_name", "agent_version", "connection_name"):
        if not isinstance(request[field], str) or not _prompt_read.NAME.fullmatch(request[field]):
            raise _prompt_read.fail("input-schema-invalid", "Select exact bounded KB, agent/version and connection names.")
    scope = request["search_resource_id"]
    match = _prompt_read.SEARCH_ID.fullmatch(scope) if isinstance(scope, str) else None
    if match is None or not isinstance(request["owner"], str) or not 1 <= len(request["owner"]) <= 256:
        raise _prompt_read.fail("input-schema-invalid", "Select the exact Search resource ID and owner.")
    network = request["network"]
    if (not isinstance(network, dict) or set(network) != {"posture", "evidence"}
            or any(not isinstance(value, str) or not 1 <= len(value) <= 4096 for value in network.values())):
        raise _prompt_read.fail("input-schema-invalid", "Supply resolved network posture and owner-verified reachability evidence.")
    endpoint = "https://" + match["name"].lower() + ".search.windows.net"
    plan = {
        "operation": "connect", "outcome": "connect-existing-prompt-agent", "sdk_major": 2,
        "project_resource_id": request["project_resource_id"], "project_endpoint": request["project_endpoint"],
        "connection": {
            "name": request["connection_name"],
            "target": endpoint + "/knowledgebases/" + quote(request["knowledge_base_name"], safe="") + "/mcp?api-version=2026-08-01-preview",
            "action": "create", "is_shared_to_all": request["is_shared_to_all"],
        },
        "agent": {"name": request["agent_name"], "version": request["agent_version"], "binding_action": request["binding_action"]},
        "rbac_verified": {"verified": False, "assignment_id": request["role_assignment_id"],
                          "scope": scope, "role": "Search Index Data Reader"},
        "allowed_tools": ["knowledge_base_retrieve"], "require_approval": "never",
        "permission_forwarding": copy.deepcopy(request["permission_forwarding"]),
        "grounding_instructions": GROUNDING, "network": copy.deepcopy(request["network"]),
        "owner": request["owner"], "cleanup_approved": False,
    }
    _validate_plan(plan, resolved=False)
    sdk = sdk_loader()
    state, profile, warnings, request_ids = _prompt_read.read_dependencies(
        plan, token_provider=token_provider, transport=transport, cli=cli, capture_context=True,
    )
    plan["rbac_verified"].update(verified=True, principal_id=state["project"]["principal_id"])
    current, ids = _prompt_read.get_object(
        _connection_url(plan), token_provider(MANAGEMENT_AUDIENCE), transport, absent=True, label="connection",
    )
    request_ids.extend(ids)
    if current is not None:
        matches, connection_warnings = _connection_readback(plan, current)
        if not matches:
            raise _prompt_read.fail("connection-conflict", "The exact chosen connection name has another configuration; preserve it and explicitly select a new deterministic name.")
        warnings.extend(connection_warnings)
        plan["connection"]["action"] = "reuse"
    agent_action, agent = _connect_agent(plan, sdk_loader=lambda: sdk, resolve=True, read_only=True)
    plan.update(connection_plan_version="1.0", verified_dependencies=state, agent_versions=agent["versions"])
    plan["agent"] = agent["agent"]
    _validate_plan(plan)
    _, _, refreshed_warnings, ids = _prompt_read.read_dependencies(
        plan, token_provider=token_provider, transport=transport, cli=cli, capture_context=True,
    )
    warnings = list(dict.fromkeys(warnings + refreshed_warnings))
    request_ids.extend(ids)
    refreshed, ids = _prompt_read.get_object(
        _connection_url(plan), token_provider(MANAGEMENT_AUDIENCE), transport, absent=True, label="connection",
    )
    request_ids.extend(ids)
    if ((current is None) != (refreshed is None)
            or (refreshed is not None and not _connection_readback(plan, refreshed)[0])):
        raise _prompt_read.fail("connection-drift", "Selected connection changed during planning; refresh before approval.")
    mutation = plan["connection"]["action"] != "reuse" or agent_action != "reused"
    return {
        "status": "planned", "outcome": plan["outcome"], "writes_performed": [],
        "execution_input": {"schema_version": "1.0", "plan": plan,
                            "approval": {"confirmed": False, "fingerprint": digest(plan)}},
        "approval_summary": {
            "project_resource_id": plan["project_resource_id"], "connection_name": request["connection_name"],
            "connection_action": plan["connection"]["action"], "kb_endpoint": plan["connection"]["target"],
            "agent_name": request["agent_name"], "selected_version": request["agent_version"],
            "agent_action": agent_action, "binding_action": request["binding_action"],
            "previous_connection": agent["previous_connection"],
            "reused_version": agent["reused"]["version"] if agent["reused"] else None,
            "grounding_appended": agent["grounding_appended"], "project_principal_id": state["project"]["principal_id"],
            "role": "Search Index Data Reader", "role_scope": scope, "kb_profile": profile,
            "sharing": request["is_shared_to_all"], "network": request["network"]["posture"],
            "execution_required": mutation, "mutation_approval_required": mutation,
            "preservation": "All unrelated agent fields/tools, prior versions and other connection names remain.",
            "version_settings": "Preserve description, metadata, draft state and blueprint reference.",
            "cleanup": "Separate plan and approval; no cleanup planner.",
            "cost": "Configuration only; no inference. Later agent/KB invocations incur separate usage.",
        },
        "request_ids": request_ids, "warnings": warnings,
        "verification": {
            "configuration": "prerequisites observed; configuration not applied" if mutation else "exact existing configuration read back",
            "agent_invocation": "not-run", "retrieval": "unverified",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--input", type=Path)
    modes.add_argument("--plan-initial", type=Path, help="Plan the existing local v1 initial-agent creation with protected provenance.")
    modes.add_argument("--plan", type=Path)
    cleanup_receipts.add_argument(parser)
    args = parser.parse_args(argv)
    fingerprint: str | None = None
    owner: Any = None
    outcome = "connect-existing-prompt-agent"
    capture = None
    try:
        if args.plan_initial or args.plan:
            if args.cleanup_receipt_dir:
                raise HelperFailure("input-schema-invalid", "Creation capture requires approved --input.", blocked_at="confirmation")
            try:
                from . import _initial_prompt, prompt_cleanup
                from ._bootstrap_io import read_json
            except ImportError:
                import _initial_prompt, prompt_cleanup
                from _bootstrap_io import read_json
            result = (
                _initial_prompt.plan(read_json(args.plan_initial), prompt_cleanup.load_cleanup_sdk)
                if args.plan_initial else plan_source(read_json(args.plan))
            )
            emit_result(result, preserve_unapproved_input=True)
            return 0
        document, plan, fingerprint = load_approved_input(args.input)
        document["_computed_fingerprint"] = fingerprint
        owner = plan.get("owner")
        outcome = str(plan.get("outcome") or outcome)
        capture = cleanup_receipts.Capture(args.cleanup_receipt_dir, document) if args.cleanup_receipt_dir else None
        result = execute(document, **({"cleanup_capture": capture} if capture else {}))
    except HelperFailure as failure:
        result = blocked_result(
            failure,
            outcome=outcome,
            fingerprint=fingerprint,
            owner=owner,
        )
        if capture is not None:
            result["cleanup_receipts"] = capture.summaries
        if result["status"] == "partial":
            remaining = result["resources_remaining"]
            remaining["unverified"] = _unique_resources(remaining.get("unverified", []) + [
                item for item in remaining["run_owned"] if item.get("run_owned") is False
            ])
            remaining["run_owned"] = [
                item for item in remaining["run_owned"] if item.get("run_owned") is not False
            ]
        emit_result(result)
        return 3 if result["status"] == "partial" else 2
    if capture is not None:
        result["cleanup_receipts"] = capture.summaries
    emit_result(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
