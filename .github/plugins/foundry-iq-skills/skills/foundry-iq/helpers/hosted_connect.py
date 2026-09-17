"""GET-only assessment of an existing Hosted agent's toolbox connection.

Promotion is deliberately unavailable until a conditional shared-default update
contract is verified. No intermediate resources are created while that gate blocks.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

try:
    from . import _prompt_read as read
    from ._bootstrap_io import read_json, run_cli
    from ._common import (
        MANAGEMENT_AUDIENCE, SEARCH_AUDIENCE, HelperFailure, azure_cli_token,
        blocked_result, digest, emit_result, http_request, reject_secrets,
    )
    from .prompt_connect import _project_identity, _project_endpoint, PROJECT_ID
except ImportError:
    import _prompt_read as read
    from _bootstrap_io import read_json, run_cli
    from _common import (
        MANAGEMENT_AUDIENCE, SEARCH_AUDIENCE, HelperFailure, azure_cli_token,
        blocked_result, digest, emit_result, http_request, reject_secrets,
    )
    from prompt_connect import _project_identity, _project_endpoint, PROJECT_ID

AI_AUDIENCE = "https://ai.azure.com"
FOUNDRY_USER = "53ca6127-db72-4b80-b1b0-d745d6d5456d"
OUTCOME = "assess-existing-hosted-toolbox"
FIELDS = {
    "schema_version", "scope", "project", "search_service", "knowledge_base",
    "agent_name", "agent_version", "toolbox_name", "tool_label", "connection_name",
    "reader_assignment_id", "project_assignment_id", "retention_owner",
}
OPTIONAL = {"known_agents", "supported_question", "unrelated_question"}


class ProjectSelectionFailure(HelperFailure):
    def __init__(self, candidates):
        super().__init__(
            "project-ambiguous" if candidates else "project-absent",
            "Scoped project name did not resolve uniquely; select an exact account/project without widening scope.",
            blocked_at="input-resolution",
        )
        self.candidates = candidates


def fail(code, message, **metadata):
    return read.fail(code, message, **metadata)


def name(value):
    return isinstance(value, str) and read.NAME.fullmatch(value) is not None


def url(value):
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.port not in (None, 443) or parsed.fragment):
            raise ValueError()
        return parsed
    except ValueError as error:
        raise fail("selection-invalid", "Use an exact public-cloud HTTPS endpoint without credentials or fragments.") from error


def validate(request):
    if not isinstance(request, dict):
        raise fail("input-schema-invalid", "Hosted assessment requires a resolved intent object.")
    reject_secrets(request)
    if set(request) - FIELDS - OPTIONAL or not FIELDS <= set(request) or request["schema_version"] != "1.0":
        raise fail("input-schema-invalid", "Use only the documented Hosted assessment decisions.")
    scope = request["scope"]
    if (not isinstance(scope, dict) or not {"subscription_id", "resource_group"} <= set(scope)
            or set(scope) - {"subscription_id", "resource_group", "account_name"}
            or any(not name(value) for value in scope.values())):
        raise fail("scope-invalid", "Select one subscription/resource group and optionally one account; no automatic widening.")
    for key in ("agent_name", "agent_version", "toolbox_name", "tool_label", "connection_name"):
        if not name(request[key]):
            raise fail("input-schema-invalid", "Select bounded exact agent/version, toolbox and connection names.")
    if request["agent_version"].casefold() in {"latest", "default"}:
        raise fail("agent-version-unresolved", "Pin the observed agent version, never latest.")
    for key in ("project", "search_service", "knowledge_base"):
        value = request[key]
        if not isinstance(value, str) or not 1 <= len(value) <= 2048:
            raise fail("selection-invalid", "Supply a name, exact resource ID or documented endpoint.")
        if value.startswith("https:"):
            parsed = url(value)
            if key == "project":
                _project_endpoint(value)
                if (not name(parsed.hostname.removesuffix(".services.ai.azure.com"))
                        or not name(unquote(parsed.path.rstrip("/").rsplit("/", 1)[-1]))):
                    raise fail("selection-invalid", "The project endpoint must identify a valid account/project name.")
            elif key == "search_service":
                if (not parsed.hostname.endswith(".search.windows.net") or parsed.path not in ("", "/")
                        or parsed.query):
                    raise fail("selection-invalid", "Select one Search service endpoint, not an index.")
            elif (not parsed.hostname.endswith(".search.windows.net")
                  or re.fullmatch(r"/knowledgebases/[A-Za-z0-9_.-]+/mcp", parsed.path) is None
                  or parse_qs(parsed.query) != {"api-version": ["2026-08-01-preview"]}):
                raise fail("selection-invalid", "Select an exact preview KB MCP endpoint.")
        elif value.startswith("/"):
            pattern = PROJECT_ID if key == "project" else read.SEARCH_ID if key == "search_service" else None
            if pattern is None or pattern.fullmatch(value) is None:
                raise fail("selection-invalid", "The supplied resource ID does not identify the selected resource kind.")
        elif not name(value):
            raise fail("selection-invalid", "The selected name is malformed.")
        if key == "search_service" and not value.startswith("/"):
            service = url(value).hostname.removesuffix(".search.windows.net") if value.startswith("https:") else value
            resource_id = (f"/subscriptions/{scope['subscription_id']}/resourceGroups/{scope['resource_group']}"
                           "/providers/Microsoft.Search/searchServices/" + service)
            if read.SEARCH_ID.fullmatch(resource_id) is None:
                raise fail("selection-invalid", "Use a valid Search service name, not a display label or index.")
    for key in ("reader_assignment_id", "project_assignment_id"):
        value = request[key]
        if (not isinstance(value, str) or len(value) > 2048
                or re.fullmatch(r"/subscriptions/[^/?#\s]+/resourceGroups/[^?#\s]+/providers/"
                                r"Microsoft.Authorization/roleAssignments/[0-9a-fA-F-]+", value, re.I) is None
                or not read.GUID.fullmatch(value.rsplit("/", 1)[-1])):
            raise fail("role-selection-invalid", "Select exact resource-scoped role-assignment IDs, not principals to invent.")
    if (not isinstance(request["retention_owner"], str) or not request["retention_owner"].strip()
            or len(request["retention_owner"]) > 256):
        raise fail("owner-unresolved", "Name the retained connection/toolbox-version owner; cleanup is unsupported.")
    agents = request.get("known_agents", [])
    if (not isinstance(agents, list) or len(agents) > 20
            or any(not isinstance(item, dict) or set(item) != {"name", "version"}
                   or not name(item["name"]) or not name(item["version"])
                   or item["version"].casefold() in {"latest", "default"} for item in agents)):
        raise fail("known-bindings-invalid", "Supply at most 20 known exact agent/version bindings; no exclusive-consumer inference.")
    for key in ("supported_question", "unrelated_question"):
        if key in request and (not isinstance(request[key], str) or not request[key].strip() or len(request[key]) > 4096):
            raise fail("acceptance-invalid", "Questions are optional resolved candidates, never implicit invocation approval.")


class Reads:
    def __init__(self, token_provider, transport):
        self.token_provider, self.transport = token_provider, transport
        self.tokens, self.request_ids = {}, []
        self.last_request_id = None

    def get(self, endpoint, audience, *, absent=False, label="resource"):
        if audience not in self.tokens:
            self.tokens[audience] = self.token_provider(audience)
        value, ids = read.get_object(endpoint, self.tokens[audience], self.transport, absent=absent, label=label)
        self.request_ids.extend(ids)
        self.last_request_id = ids[-1] if ids else None
        return value

    def collection(self, endpoint):
        initial = urlsplit(endpoint)
        result, seen = [], set()
        while endpoint:
            current = url(endpoint)
            if (endpoint in seen or len(seen) >= 20 or current.netloc != initial.netloc
                    or current.path != initial.path
                    or parse_qs(current.query).get("api-version") != parse_qs(initial.query).get("api-version")):
                raise fail("inventory-unverified", "Scoped inventory continuation is unsafe or exceeds 20 pages.")
            seen.add(endpoint)
            page = self.get(endpoint, MANAGEMENT_AUDIENCE, label="scoped-inventory")
            items = page.get("value")
            if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
                raise fail("inventory-unverified", "Scoped inventory is malformed; no inferred absence.")
            result.extend(items)
            if len(result) > 100:
                raise fail("inventory-limit", "Scoped inventory exceeds 100 resources; select an exact parent instead.")
            endpoint = page.get("nextLink")
            if endpoint is not None and not isinstance(endpoint, str):
                raise fail("inventory-unverified", "Scoped continuation must be a URL.")
        return result


def resolve(request, reads):
    scope = request["scope"]
    prefix = f"/subscriptions/{scope['subscription_id']}/resourceGroups/{scope['resource_group']}"
    account_prefix = prefix + "/providers/Microsoft.CognitiveServices/accounts/"
    selection = request["project"]
    if selection.startswith("/"):
        project_id = selection
    elif selection.startswith("https:"):
        parsed = url(selection)
        project_id = account_prefix + parsed.hostname.removesuffix(".services.ai.azure.com") + "/projects/" + unquote(parsed.path.rstrip("/").rsplit("/", 1)[-1])
    elif scope.get("account_name"):
        project_id = account_prefix + scope["account_name"] + "/projects/" + selection
    else:
        accounts = reads.collection(MANAGEMENT_AUDIENCE + account_prefix.rstrip("/") + "?api-version=2025-06-01")
        if len(accounts) > 20:
            raise fail("account-selection-required", "Select one account; do not enumerate more than 20 accounts for a project name.")
        matches, seen = [], set()
        for account in accounts:
            account_id = account.get("id", "")
            if (not isinstance(account_id, str) or not account_id.casefold().startswith(account_prefix.casefold())
                    or not name(account_id[len(account_prefix):]) or account_id.casefold() in seen):
                raise fail("inventory-unverified", "Account inventory contains a duplicate or out-of-scope resource.")
            seen.add(account_id.casefold())
            projects_seen = set()
            for project in reads.collection(MANAGEMENT_AUDIENCE + account_id + "/projects?api-version=" + read.PROJECT_API):
                candidate = project.get("id", "")
                if (not isinstance(candidate, str) or PROJECT_ID.fullmatch(candidate) is None
                        or not candidate.casefold().startswith((account_id + "/projects/").casefold())
                        or candidate.casefold() in projects_seen):
                    raise fail("inventory-unverified", "Project inventory contains an unverified identity.")
                projects_seen.add(candidate.casefold())
                if candidate.rsplit("/", 1)[-1].casefold() == selection.casefold():
                    matches.append(candidate)
        if len(matches) != 1:
            raise ProjectSelectionFailure(matches)
        project_id = matches[0]
    match = PROJECT_ID.fullmatch(project_id)
    if match is None:
        raise fail("selection-invalid", "The resolved project resource identity is malformed.")
    endpoint = f"https://{match['account']}.services.ai.azure.com/api/projects/{quote(match['project'], safe='')}"
    _project_identity({"project_resource_id": project_id, "project_endpoint": endpoint})
    selection = request["search_service"]
    if selection.startswith("/"):
        search_id = selection
    else:
        service = url(selection).hostname.removesuffix(".search.windows.net") if selection.startswith("https:") else selection
        search_id = prefix + "/providers/Microsoft.Search/searchServices/" + service
    match = read.SEARCH_ID.fullmatch(search_id)
    if match is None:
        raise fail("selection-invalid", "The selected Search service identity is invalid.")
    search_endpoint = "https://" + match["name"].lower() + ".search.windows.net"
    selection = request["knowledge_base"]
    if selection.startswith("https:"):
        parsed = url(selection)
        if parsed.hostname != urlsplit(search_endpoint).hostname:
            raise fail("kb-binding-invalid", "The KB endpoint belongs to another selected Search service.")
        kb_name = parsed.path.split("/")[2]
    else:
        kb_name = selection
    return project_id, endpoint, search_id, search_endpoint, kb_name


def role(reads, assignment_id, scope, principal, role_id):
    prefix = scope + "/providers/Microsoft.Authorization/roleAssignments/"
    if (not assignment_id.casefold().startswith(prefix.casefold())
            or not read.GUID.fullmatch(assignment_id[len(prefix):])):
        raise fail("role-scope-invalid", "Role assignment must use the exact selected resource scope.")
    value = reads.get(MANAGEMENT_AUDIENCE + assignment_id + "?api-version=" + read.ROLE_API,
                      MANAGEMENT_AUDIENCE, label="role-assignment")
    properties = value.get("properties")
    definitions = {
        "/providers/microsoft.authorization/roledefinitions/" + role_id,
        "/subscriptions/" + scope.split("/")[2].lower() + "/providers/microsoft.authorization/roledefinitions/" + role_id,
    }
    if (str(value.get("id", "")).casefold() != assignment_id.casefold() or not isinstance(properties, dict)
            or str(properties.get("principalId", "")).lower() != principal
            or str(properties.get("scope", "")).casefold() != scope.casefold()
            or str(properties.get("roleDefinitionId", "")).casefold() not in definitions
            or properties.get("principalType", "ServicePrincipal") != "ServicePrincipal"
            or properties.get("condition") not in (None, "")):
        raise fail("hosted-runtime-role-unverified", "Require exact-scope grants to the published Hosted principal, not the project or blueprint.")
    return value


def agent(reads, endpoint, agent_name, version):
    value = reads.get(endpoint + f"/agents/{quote(agent_name, safe='')}/versions/{quote(version, safe='')}?api-version=v1",
                      AI_AUDIENCE, label="hosted-agent")
    if value.get("name") != agent_name or str(value.get("version")) != version or not isinstance(value.get("definition"), dict):
        raise fail("agent-identity-unverified", "Read the exact observed agent/version; never select latest.")
    return value


def toolbox_binding(environment, endpoint, toolbox_name):
    """Match the first-party FoundryToolbox environment resolver, not arbitrary code."""
    if not isinstance(environment, dict):
        return None
    consumer = endpoint + "/toolboxes/" + toolbox_name + "/mcp?api-version=v1"
    if "TOOLBOX_ENDPOINT" in environment:
        return "endpoint" if environment["TOOLBOX_ENDPOINT"] == consumer else None
    project = environment.get("FOUNDRY_PROJECT_ENDPOINT")
    if (isinstance(project, str) and project.rstrip("/") == endpoint
            and environment.get("TOOLBOX_NAME") == toolbox_name):
        return "name"
    return None


def assess(request, *, token_provider=azure_cli_token, transport=http_request, cli=run_cli):
    validate(request)
    scope = request["scope"]
    selected_project = request["project"]
    context_id = selected_project if selected_project.startswith("/") else "/subscriptions/" + scope["subscription_id"]
    context = read.cli_context(context_id, cli=cli)
    reads = Reads(token_provider, transport)
    project_id, endpoint, search_id, search_endpoint, kb_name = resolve(request, reads)
    project = reads.get(MANAGEMENT_AUDIENCE + project_id + "?api-version=" + read.PROJECT_API, MANAGEMENT_AUDIENCE, label="project")
    properties = project.get("properties", {})
    endpoints = properties.get("endpoints") if isinstance(properties, dict) else None
    if (str(project.get("id", "")).casefold() != project_id.casefold() or not isinstance(properties, dict)
            or str(properties.get("provisioningState", "")).lower() != "succeeded"
            or not isinstance(endpoints, dict) or endpoint not in endpoints.values()):
        raise fail("project-unverified", "The exact ready project endpoint must be confirmed remotely.")
    selected = agent(reads, endpoint, request["agent_name"], request["agent_version"])
    definition, identity = selected["definition"], selected.get("instance_identity")
    other_principals = [
        value.get("principalId") or value.get("principal_id")
        for value in (project.get("identity"), selected.get("blueprint"))
        if isinstance(value, dict)
    ]
    if (definition.get("kind") != "hosted" or selected.get("status") != "active"
            or not isinstance(identity, dict) or identity.get("status") != "active"
            or not isinstance(identity.get("principal_id"), str) or not read.GUID.fullmatch(identity["principal_id"])
            or not isinstance(identity.get("client_id"), str) or not read.GUID.fullmatch(identity["client_id"])
            or identity["principal_id"].casefold() in {
                value.casefold() for value in other_principals if isinstance(value, str)
            }):
        raise fail("hosted-principal-unverified", "Require an active published Hosted agent and observed instance principal.")
    principal = identity["principal_id"].lower()
    consumer = endpoint + "/toolboxes/" + request["toolbox_name"] + "/mcp?api-version=v1"
    environment = definition.get("environment_variables")
    binding_mode = toolbox_binding(environment, endpoint, request["toolbox_name"])
    if binding_mode is None:
        raise fail("hosted-runtime-change-required", "Observed settings do not establish this unversioned FoundryToolbox binding. The runtime owner must verify custom/overridden behavior or the actual configuration change before requesting source; a version-pinned developer endpoint is not equivalent.")
    search = reads.get(MANAGEMENT_AUDIENCE + search_id + "?api-version=" + read.SEARCH_API, MANAGEMENT_AUDIENCE, label="search")
    properties = search.get("properties")
    if (str(search.get("id", "")).casefold() != search_id.casefold() or not isinstance(properties, dict)
            or str(properties.get("status", "")).lower() not in {"running", "provisioning", "degraded"}
            or str(properties.get("provisioningState", "")).lower() not in {"succeeded", "provisioning"}):
        raise fail("search-operation-blocked", "Search failed/deleting/disabled/unresolved state blocks this assessment.")
    kb = reads.get(search_endpoint + "/knowledgebases('" + quote(kb_name, safe="") + "')?api-version=2026-08-01-preview",
                   SEARCH_AUDIENCE, absent=True, label="knowledge-base")
    if kb is None:
        raise fail("knowledge-base-absent", "The exact KB is absent; Search indexes are not KB evidence.",
                   status=404, request_id=reads.last_request_id)
    _, profile = read.kb_state(kb, kb_name)
    reader = role(reads, request["reader_assignment_id"], search_id, principal, read.READER_ROLE)
    project_role = role(reads, request["project_assignment_id"], project_id, principal, FOUNDRY_USER)
    toolbox_url = endpoint + "/toolboxes/" + request["toolbox_name"]
    toolbox = reads.get(toolbox_url + "?api-version=v1", AI_AUDIENCE, label="toolbox")
    default = toolbox.get("default_version")
    if (toolbox.get("name") != request["toolbox_name"] or not name(default)
            or default.casefold() in {"latest", "default"}):
        raise fail("toolbox-default-unverified", "Read the exact toolbox and its current default version.")
    version = reads.get(toolbox_url + "/versions/" + default + "?api-version=v1", AI_AUDIENCE, label="toolbox-version")
    tools = version.get("tools")
    if (version.get("name") != request["toolbox_name"] or str(version.get("version")) != default
            or not isinstance(tools, list) or len(tools) > 200 or any(not isinstance(tool, dict) for tool in tools)):
        raise fail("toolbox-version-unverified", "The default immutable version and its complete tool list must be verified.")
    matching = [tool for tool in tools if tool.get("server_label") == request["tool_label"]]
    if len(matching) > 1:
        raise fail("toolbox-binding-ambiguous", "Multiple selected KB tool labels require explicit reconciliation.")
    if matching:
        tool = matching[0]
        allowed = tool.get("allowed_tools") or []
        allowed = allowed.get("tool_names", []) if isinstance(allowed, dict) else allowed
        if (tool.get("type") != "mcp" or not isinstance(allowed, list)
                or any(not isinstance(item, str) for item in allowed)
                or not isinstance(tool.get("headers") or {}, dict)
                or not isinstance(tool.get("server_url"), str) or len(tool["server_url"]) > 2048
                or not isinstance(tool.get("project_connection_id"), str)):
            raise fail("toolbox-binding-unverified", "The selected MCP tool definition is malformed or has another type.")
        if tool.get("authorization") is not None or tool.get("connector_id") is not None or tool.get("headers"):
            raise fail("toolbox-auth-unverified", "Inline authorization, connectors or custom headers are outside this agentic-identity recipe; preserve them rather than silently replacing their auth.")
        if "allowed_tools" in tool and tool["allowed_tools"] is not None and "knowledge_base_retrieve" not in allowed:
            raise fail("toolbox-policy-unverified", "The explicit tool filter does not establish access to knowledge_base_retrieve; review the policy delta separately, never silently widen it.")
        old_endpoint = url(tool["server_url"])
        api = parse_qs(old_endpoint.query)
        reference = tool["project_connection_id"]
        prefix = project_id + "/connections/"
        if (not old_endpoint.hostname.endswith(".search.windows.net")
                or re.fullmatch(r"/knowledgebases/[A-Za-z0-9_.-]+/mcp", old_endpoint.path) is None
                or set(api) != {"api-version"} or len(api["api-version"]) != 1
                or re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:-preview)?", api["api-version"][0]) is None
                or not (name(reference) or (reference.casefold().startswith(prefix.casefold())
                                           and name(reference[len(prefix):])))):
            raise fail("toolbox-binding-unverified", "The selected label is not a verified Search KB MCP binding.")
    target = search_endpoint + "/knowledgebases/" + kb_name + "/mcp?api-version=2026-08-01-preview"
    connection_url = MANAGEMENT_AUDIENCE + project_id + "/connections/" + request["connection_name"] + "?api-version=" + read.PROJECT_API
    connection = reads.get(connection_url, MANAGEMENT_AUDIENCE, absent=True, label="connection")
    if connection is not None:
        props = connection.get("properties")
        expected_id = project_id + "/connections/" + request["connection_name"]
        if (connection.get("name") != request["connection_name"] or not isinstance(props, dict)
                or str(connection.get("id", expected_id)).casefold() != expected_id.casefold()
                or any(props.get(key) != value for key, value in {
                    "category": "RemoteTool", "authType": "AgenticIdentityToken",
                    "target": target, "audience": "https://search.azure.com/",
                }.items())):
            raise fail("connection-conflict", "This exact connection NAME has incompatible Hosted recipe auth/binding. Preserve it; explicitly choose a new name, even for the same KB endpoint.")
    old_connection, old_connection_url = None, None
    if matching:
        old_name = matching[0]["project_connection_id"].rsplit("/", 1)[-1]
        old_connection_url = MANAGEMENT_AUDIENCE + project_id + "/connections/" + old_name + "?api-version=" + read.PROJECT_API
        old_connection = connection if old_name == request["connection_name"] else reads.get(
            old_connection_url, MANAGEMENT_AUDIENCE, label="previous-connection",
        )
        old_id = project_id + "/connections/" + old_name
        if (old_connection is None or old_connection.get("name") != old_name
                or str(old_connection.get("id", old_id)).casefold() != old_id.casefold()
                or not isinstance(old_connection.get("properties"), dict)
                or old_connection["properties"].get("target") != matching[0]["server_url"]):
            raise fail("toolbox-existing-binding-unverified", "The previous connection and selected toolbox tool do not establish one consistent KB binding.")
    exact = bool(connection and matching
                 and matching[0].get("project_connection_id") in {
                     request["connection_name"], project_id + "/connections/" + request["connection_name"],
                 }
                 and matching[0]["server_url"] == target)
    known = [{"name": request["agent_name"], "version": request["agent_version"]}]
    known_states = []
    for item in request.get("known_agents", []):
        observed = agent(reads, endpoint, item["name"], item["version"])
        known_states.append(observed)
        env = observed["definition"].get("environment_variables", {})
        configured_tools = observed["definition"].get("tools") or []
        tool_binding = isinstance(configured_tools, list) and any(
            isinstance(tool, dict) and tool.get("type") == "mcp" and tool.get("server_url") == consumer
            for tool in configured_tools
        )
        if (toolbox_binding(env, endpoint, request["toolbox_name"]) or tool_binding) and item not in known:
            known.append(item)
    refreshed = reads.get(toolbox_url + "?api-version=v1", AI_AUDIENCE, label="toolbox")
    refreshed_agent = agent(reads, endpoint, request["agent_name"], request["agent_version"])
    refreshed_connection = reads.get(connection_url, MANAGEMENT_AUDIENCE, absent=True, label="connection")
    refreshed_old = old_connection
    if old_connection_url and old_connection_url != connection_url:
        refreshed_old = reads.get(old_connection_url, MANAGEMENT_AUDIENCE, label="previous-connection")
    refreshed_version = reads.get(toolbox_url + "/versions/" + default + "?api-version=v1", AI_AUDIENCE, label="toolbox-version")
    if (refreshed != toolbox or refreshed_agent != selected or refreshed_connection != connection
            or refreshed_old != old_connection or refreshed_version != version
            or read.cli_context(project_id, cli=cli) != context):
        raise fail("hosted-protected-state-drift", "Agent, toolbox default/metadata or CLI context changed during assessment.")
    summary = {
        "branch": "toolbox-only", "agent": request["agent_name"], "agent_version": request["agent_version"],
        "project_resource_id": project_id, "project_endpoint": endpoint, "search_resource_id": search_id,
        "toolbox_name": request["toolbox_name"], "consumer_endpoint": consumer,
        "runtime_binding": {"resolver": "FoundryToolbox environment", "mode": binding_mode,
                            "runtime_usage_verified": False},
        "agent_change": "none", "runtime_principal_id": principal, "kb_profile": profile,
        "before": {"kb_endpoint": matching[0].get("server_url") if matching else None, "default_version": default,
                   "connection": matching[0].get("project_connection_id") if matching else None},
        "after": {"kb_endpoint": target, "default_version": default if exact else "new immutable version (not created)",
                  "connection": request["connection_name"]},
        "connection_action": "reuse" if connection else "create (blocked)",
        "known_consumers": known, "unknown_consumers": True,
        "shared_default_approval_required": not exact, "mutation_approval_required": not exact,
        "retention_owner": request["retention_owner"], "cleanup": "unsupported; retain previous versions and legacy connections",
        "rollback": "separate explicit plan; never automatic",
        "tool_policy": "Preserve existing tool approval/filter/configuration; runtime enforcement is not proven by this assessment.",
        "acceptance": {
            "supported_candidate_needed": "supported_question" not in request,
            "unrelated_question_needed": "unrelated_question" not in request,
            "invocation_approval": "not granted by assessment", "agent_tool_retrieval": "not-run",
        },
    }
    result = {
        "status": "planned" if exact else "blocked", "outcome": OUTCOME, "approval_summary": summary,
        "writes_performed": [], "execution_input": None, "execution_available": False,
        "private_evidence": {"fingerprint": digest({
            "project": project, "agent": selected, "search": search, "kb": kb,
            "reader": reader, "project_role": project_role, "toolbox": toolbox,
            "version": version, "connection": connection, "previous_connection": old_connection,
            "known_agents": known_states, "cli": context,
        })},
        "request_ids": reads.request_ids,
        "warnings": ["Configured runtime binding is not actual agent tool-use proof; acceptance invocations remain separate.",
                     "Known bindings are not a complete consumer inventory; external consumers may follow this default."],
    }
    if (str(search["properties"].get("status")).lower() != "running"
            or str(search["properties"].get("provisioningState")).lower() != "succeeded"):
        result["warnings"].append("Search is provisioning/degraded; healthy KB GET is configuration evidence, not retrieval readiness.")
    if not exact:
        result["first_blocker"] = {
            "code": "toolbox-promotion-concurrency-unverified",
            "message": "SDK/REST version creation and default promotion exist, but their conditional ETag/default update contract is unverified. Obtain service-owner confirmation before any connection/version creation; arbitrary If-Match headers are not proof.",
        }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = assess(read_json(args.plan))
    except HelperFailure as error:
        result = blocked_result(error, outcome=OUTCOME, fingerprint=None, owner=None)
        if isinstance(error, ProjectSelectionFailure):
            result["selection_candidates"] = error.candidates
    emit_result(result)
    return 3 if result["status"] == "partial" else 2 if result["status"] == "blocked" else 0


if __name__ == "__main__":
    sys.exit(main())
