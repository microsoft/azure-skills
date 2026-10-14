"""Read-only, resource-specific prerequisites for Prompt connection planning/apply."""
from __future__ import annotations

import copy
import json
import re
from importlib.metadata import PackageNotFoundError, version
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit

try:
    from ._bootstrap_io import run_cli
    from ._common import MANAGEMENT_AUDIENCE, SEARCH_AUDIENCE, HelperFailure, digest, require_allowed_fields
except ImportError:
    from _bootstrap_io import run_cli
    from _common import MANAGEMENT_AUDIENCE, SEARCH_AUDIENCE, HelperFailure, digest, require_allowed_fields


PROJECT_API = "2025-10-01-preview"
SEARCH_API = "2025-05-01"
ROLE_API = "2022-04-01"
READER_ROLE = "1407120a-92aa-4202-b7e9-c0e197c71c8f"
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
GUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
SEARCH_ID = re.compile(
    r"/subscriptions/[^/?#\s]+/resourceGroups/[^/?#\s]+/"
    r"providers/Microsoft\.Search/searchServices/(?P<name>[a-z0-9-]{2,60})",
    re.IGNORECASE,
)


def fail(code: str, message: str, response=None, *, status=None, request_id=None) -> HelperFailure:
    return HelperFailure(
        code, message, blocked_at="reconciliation",
        status=response.status if response is not None else status,
        request_id=response.request_id if response is not None else request_id,
    )


def binding(plan: dict[str, Any]) -> tuple[str, str, str]:
    scope = plan["rbac_verified"].get("scope")
    match = SEARCH_ID.fullmatch(scope) if isinstance(scope, str) else None
    target = urlsplit(plan["connection"]["target"])
    parts = target.path.split("/")
    if (
        match is None or target.hostname != match["name"].lower() + ".search.windows.net"
        or len(parts) != 4 or parts[1] != "knowledgebases" or parts[3] != "mcp"
        or parse_qs(target.query) != {"api-version": ["2026-08-01-preview"]}
        or not NAME.fullmatch(unquote(parts[2]))
    ):
        raise fail("kb-binding-invalid", "Bind an exact Search service ID and preview KB MCP name, not a generated index.")
    assignment = plan["rbac_verified"].get("assignment_id")
    prefix = scope + "/providers/Microsoft.Authorization/roleAssignments/"
    if (
        not isinstance(assignment, str) or not assignment.casefold().startswith(prefix.casefold())
        or not GUID.fullmatch(assignment[len(prefix):])
    ):
        raise fail("rbac-scope-invalid", "Select one exact Search-service-scoped role assignment resource ID.")
    return scope, "https://" + target.hostname, unquote(parts[2])


def get_object(url, token, transport, *, absent=False, label="resource"):
    try:
        result = transport(
            "GET", url, token, follow_redirects=False, max_response_bytes=1024 * 1024,
        )
    except HelperFailure as error:
        if absent and error.http_status == 404 and not error.partial:
            return None, [error.request_id] if error.request_id else []
        raise
    if result.status == 404 and absent:
        return None, [result.request_id] if result.request_id else []
    if result.status != 200:
        raise fail(label + "-unavailable", "Exact " + label + " read failed; no fallback or inferred absence.", result)
    if not isinstance(result.body, dict) or not result.body:
        raise fail(label + "-readback-invalid", "Exact " + label + " readback must be a nonempty object.", result)
    return result.body, [result.request_id] if result.request_id else []


def cli_context(project_id, *, cli=run_cli):
    rc, out, _ = cli(["account", "show"], 60)
    if rc:
        raise fail("cli-context-unavailable", "The selected signed-in Azure CLI context could not be read.")
    try:
        value = json.loads(out)
    except (UnicodeError, ValueError) as error:
        raise fail("cli-context-invalid", "Azure CLI context is malformed.") from error
    user = value.get("user") if isinstance(value, dict) else None
    if (
        not isinstance(user, dict) or user.get("type") not in {"user", "servicePrincipal"}
        or not isinstance(user.get("name"), str) or not 1 <= len(user["name"]) <= 256
        or value.get("environmentName") != "AzureCloud"
        or str(value.get("state", "")).casefold() != "enabled"
        or str(value.get("id", "")).casefold() != project_id.split("/")[2].casefold()
        or not isinstance(value.get("tenantId"), str) or not GUID.fullmatch(value["tenantId"])
    ):
        raise fail("cli-context-conflict", "Select the project's enabled subscription and tenant without changing identity.")
    return {"subscription_id": value["id"].lower(), "tenant_id": value["tenantId"].lower(),
            "principal": user["name"], "principal_type": user["type"]}


def kb_state(value, name):
    if value.get("name") != name:
        raise fail("kb-identity-mismatch", "The exact knowledgebases API returned another KB identity.")
    sources, models = value.get("knowledgeSources"), value.get("models", [])
    if models is None:
        models = []
    effort = value.get("retrievalReasoningEffort")
    mode = value.get("outputMode")
    if (
        not isinstance(sources, list) or not 1 <= len(sources) <= 200
        or any(not isinstance(item, dict) or not isinstance(item.get("name"), str)
               or not NAME.fullmatch(item["name"]) for item in sources)
        or len({item["name"] for item in sources}) != len(sources)
        or not isinstance(models, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("@odata.type"), str)
            or not item["@odata.type"].strip()
            for item in models
        )
        or not isinstance(effort, dict) or effort.get("kind") not in {"minimal", "low", "medium"}
        or mode not in {"extractiveData", "answerSynthesis"}
    ):
        raise fail("kb-configuration-unresolved", "Read complete KB sources, model configuration, reasoning and output; never infer them from generated indexes.")
    if not models and (effort["kind"] != "minimal" or mode != "extractiveData"):
        raise fail("kb-model-required", "This existing KB configuration requires a KB chat model; connection planning never changes its mode or models.")
    material = copy.deepcopy(value)
    for field in ("@odata.etag", "description", "tags"):
        material.pop(field, None)
    return {"name": name, "definition_digest": digest(material)}, {
        "source_count": len(sources), "model_configured": bool(models),
        "reasoning": effort["kind"], "output": mode,
    }


def read_dependencies(plan, *, token_provider, transport, cli=run_cli, capture_context=False):
    scope, endpoint, kb_name = binding(plan)
    project_id = plan["project_resource_id"]
    context = cli_context(project_id, cli=cli) if capture_context else None
    token = token_provider(MANAGEMENT_AUDIENCE)
    request_ids = []
    project, ids = get_object(MANAGEMENT_AUDIENCE + project_id + "?api-version=" + PROJECT_API,
                              token, transport, label="project")
    request_ids.extend(ids)
    identity, props = project.get("identity"), project.get("properties")
    endpoints = props.get("endpoints") if isinstance(props, dict) else None
    identity_types = identity.get("type") if isinstance(identity, dict) else None
    identity_types = {item.strip() for item in identity_types.split(",")} if isinstance(identity_types, str) else set()
    if (
        str(project.get("id", "")).casefold() != project_id.casefold()
        or not isinstance(identity, dict) or identity_types not in ({"SystemAssigned"}, {"SystemAssigned", "UserAssigned"})
        or not isinstance(identity.get("principalId"), str) or not GUID.fullmatch(identity["principalId"])
        or not isinstance(identity.get("tenantId"), str) or not GUID.fullmatch(identity["tenantId"])
        or not isinstance(props, dict) or str(props.get("provisioningState", "")).casefold() != "succeeded"
        or not isinstance(endpoints, dict) or plan["project_endpoint"].rstrip("/") not in {
            value.rstrip("/") for value in endpoints.values() if isinstance(value, str)
        }
    ):
        raise fail("project-identity-unverified", "Require the selected ready Foundry PROJECT endpoint and its system-assigned principalId/tenantId.",
                   request_id=ids[-1] if ids else None)
    if context is not None and context["tenant_id"] != identity["tenantId"].lower():
        raise fail("cli-context-conflict", "CLI tenant differs from the observed project identity tenant.")
    project_state = {"id": project_id, "endpoint": plan["project_endpoint"].rstrip("/"),
                     "principal_id": identity["principalId"].lower(), "tenant_id": identity["tenantId"].lower()}

    search, ids = get_object(MANAGEMENT_AUDIENCE + scope + "?api-version=" + SEARCH_API,
                             token, transport, label="search")
    request_ids.extend(ids)
    props = search.get("properties")
    if str(search.get("id", "")).casefold() != scope.casefold() or not isinstance(props, dict):
        raise fail("search-identity-unverified", "The selected Search resource identity is unresolved.", request_id=ids[-1] if ids else None)
    status, provisioning = str(props.get("status", "")).lower(), str(props.get("provisioningState", "")).lower()
    if status not in {"running", "provisioning", "degraded"} or provisioning not in {"succeeded", "provisioning"}:
        raise fail("search-operation-blocked", "Search is failed, disabled, deleting or unresolved; no connection write is allowed.",
                   request_id=ids[-1] if ids else None)
    warnings = [] if status == "running" and provisioning == "succeeded" else [
        "Search is provisioning/degraded; healthy KB GET permits connection configuration only, not readiness or retrieval proof."
    ]
    search_state = {"id": scope, "endpoint": endpoint, "access_digest": digest({
        key: props.get(key) for key in ("disableLocalAuth", "authOptions", "publicNetworkAccess", "networkRuleSet", "privateEndpointConnections")
    })}

    assignment_id = plan["rbac_verified"]["assignment_id"]
    assignment, ids = get_object(MANAGEMENT_AUDIENCE + assignment_id + "?api-version=" + ROLE_API,
                                 token, transport, label="role-assignment")
    request_ids.extend(ids)
    role = assignment.get("properties")
    if (
        str(assignment.get("id", "")).casefold() != assignment_id.casefold()
        or not isinstance(role, dict)
        or str(role.get("principalId", "")).casefold() != project_state["principal_id"]
        or str(role.get("scope", "")).casefold() != scope.casefold()
        or str(role.get("roleDefinitionId", "")).casefold() not in {
            "/providers/microsoft.authorization/roledefinitions/" + READER_ROLE,
            "/subscriptions/" + scope.split("/")[2].lower() + "/providers/microsoft.authorization/roledefinitions/" + READER_ROLE,
        }
        or role.get("principalType", "ServicePrincipal") != "ServicePrincipal"
        or role.get("condition") not in (None, "")
    ):
        raise fail("project-reader-role-unverified", "Search Index Data Reader must be an unconditional exact-scope grant to the observed PROJECT principal, not the agent identity.",
                   request_id=ids[-1] if ids else None)
    rbac = {"assignment_id": assignment_id, "principal_id": project_state["principal_id"],
            "scope": scope, "role_definition_id": READER_ROLE}
    url = endpoint + "/knowledgebases('" + quote(kb_name.replace("'", "''"), safe="") + "')?api-version=2026-08-01-preview"
    kb, ids = get_object(url, token_provider(SEARCH_AUDIENCE), transport, absent=True, label="knowledge-base")
    request_ids.extend(ids)
    if kb is None:
        raise fail("knowledge-base-absent", "The exact KB is absent; a generated index is not a knowledge base.",
                   status=404, request_id=ids[-1] if ids else None)
    try:
        knowledge_base, profile = kb_state(kb, kb_name)
    except HelperFailure as error:
        error.request_id = ids[-1] if ids else None
        raise
    state = {"project": project_state, "search": search_state, "rbac": rbac, "knowledge_base": knowledge_base}
    if context is not None:
        state["cli_context"] = context
    expected = plan.get("verified_dependencies")
    if expected is not None:
        require_allowed_fields(expected, set(state), label="Verified Prompt dependencies")
        if expected != state:
            raise fail("connection-prerequisite-drift", "Project principal, CLI context, KB binding or exact role changed since planning; refresh before approval.")
    elif plan["rbac_verified"].get("verified") is True and (
        str(plan["rbac_verified"]["principal_id"]).lower() != project_state["principal_id"]
    ):
        raise fail("project-reader-role-unverified", "The approved principal is not the observed Foundry PROJECT identity.")
    return state, profile, warnings, request_ids


ARM_API_VERSION = "2025-10-01-preview"


SDK_MAJOR = "2"


PROJECT_ID = re.compile(
    r"^/subscriptions/[^/]+/resourceGroups/[^/]+/providers/"
    r"Microsoft\.CognitiveServices/accounts/(?P<account>[^/]+)/projects/"
    r"(?P<project>[^/]+)$",
    re.IGNORECASE,
)


PROJECT_PATH = re.compile(r"^/api/projects/(?P<project>[^/]+)/?$")


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


def _load_connection_sdk() -> tuple[Any, Any, Any, Any, Any]:
    sdk = _load_sdk()
    installed = re.match(r"^2\.(\d+)\.", version("azure-ai-projects"))
    if installed is None or int(installed[1]) < 4:
        raise fail("sdk-version-invalid", "Complete Prompt version reads require azure-ai-projects>=2.4.0,<3, including drafts.")
    return sdk
