"""File Standard system-MI binding; implementation evidence is not rollout proof."""
from __future__ import annotations

import copy
import re

try:
    from . import _bootstrap_io, cu_ingestion_auth, search_reconcile
    from ._common import MANAGEMENT_AUDIENCE, HelperFailure, digest, require_allowed_fields
except ImportError:
    import _bootstrap_io, cu_ingestion_auth, search_reconcile
    from _common import MANAGEMENT_AUDIENCE, HelperFailure, digest, require_allowed_fields

SEARCH_API = "2025-05-01"
ROLE_API = "2022-04-01"
CU_ROLE = "a97b65f3-24c7-4388-baec-2e87135dc908"
SEARCH_ID = re.compile(
    r"/subscriptions/[0-9a-fA-F-]{36}/resourceGroups/[A-Za-z0-9_.()-]{1,90}"
    r"/providers/Microsoft\.Search/searchServices/(?=.{2,60}$)((?a:[a-z0-9][a-z0-9]+(?:-[a-z0-9]+)*))", re.I,
)
REDACTED = (None, "", "<redacted>", "***")


def fail(code, message, *, request_id=None, status=None):
    return HelperFailure(code, message, blocked_at="cu-managed-identity", request_id=request_id, status=status)


def validate_choice(value, resource_id):
    if not isinstance(value, dict):
        raise fail("cu-mi-prerequisite-missing", "Resolve existing Search resource ID and exact CU-scoped Cognitive Services User assignment. Missing identity/role changes need packaged bootstrap plans and explicit approval.")
    require_allowed_fields(value, {"search_resource_id", "role_assignment_id"}, label="File CU managed identity")
    search = value.get("search_resource_id")
    role = value.get("role_assignment_id")
    prefix = resource_id + "/providers/Microsoft.Authorization/roleAssignments/"
    if (
        not isinstance(search, str) or SEARCH_ID.fullmatch(search) is None
        or not isinstance(role, str) or not role.casefold().startswith(prefix.casefold())
        or cu_ingestion_auth.UUID.fullmatch(role[len(prefix):]) is None
    ):
        raise fail("cu-mi-binding-invalid", "Select exact Search and CU-account-scoped role assignment IDs; no inferred account, inherited/custom role or user-assigned identity.")
    return copy.deepcopy(value)


def read_binding(choice, endpoint, *, token_provider, transport):
    selected = validate_choice(choice.get("managed_identity"), choice["resource_id"])
    match = SEARCH_ID.fullmatch(selected["search_resource_id"])
    if endpoint.rstrip("/").casefold() != f"https://{match.group(1)}.search.windows.net".casefold():
        raise fail("cu-mi-search-mismatch", "Search resource ID must match the exact approved Search endpoint.")
    ids = []

    def get(resource, version):
        response = transport(
            "GET", f"{MANAGEMENT_AUDIENCE}{resource}?api-version={version}",
            token_provider(MANAGEMENT_AUDIENCE), follow_redirects=False, max_response_bytes=65536,
        )
        if response.status != 200 or not isinstance(response.body, dict):
            raise fail("cu-mi-prerequisite-unavailable", "Cannot GET the exact Search identity or scoped CU role. Have its owner resolve read access or plan missing setup; no key fallback or permission changes.",
                       request_id=response.request_id, status=response.status)
        if str(response.body.get("id", "")).casefold() != resource.casefold():
            raise fail("cu-mi-resource-mismatch", "ARM returned another resource or scope; refresh the selected bindings.", request_id=response.request_id)
        if response.request_id:
            ids.append(response.request_id)
        return response.body

    search = get(selected["search_resource_id"], SEARCH_API)
    identity, props = search.get("identity"), search.get("properties")
    if (
        not isinstance(identity, dict) or not isinstance(props, dict)
        or "SystemAssigned" not in str(identity.get("type", "")).replace(" ", "").split(",")
        or any(not isinstance(identity.get(k), str) or cu_ingestion_auth.UUID.fullmatch(identity[k]) is None
               for k in ("principalId", "tenantId"))
        or str(props.get("provisioningState", "")).casefold() != "succeeded"
        or str(props.get("status", "")).casefold() != "running"
        or str(props.get("endpoint", "")).rstrip("/").casefold() not in (
            endpoint.rstrip("/").casefold(), endpoint.rstrip("/").casefold().removeprefix("https://"),
        )
    ):
        raise fail("cu-mi-identity-unverified", "Require ready Search system-assigned principal/tenant and endpoint readback; resolve missing identity with a separately approved bootstrap plan.")
    role = get(selected["role_assignment_id"], ROLE_API)
    rp = role.get("properties")
    expected_role = re.compile(r"/subscriptions/[0-9a-fA-F-]{36}/providers/Microsoft.Authorization/roleDefinitions/" + CU_ROLE, re.I)
    if (
        not isinstance(rp, dict)
        or str(rp.get("principalId", "")).casefold() != identity["principalId"].casefold()
        or rp.get("principalType") != "ServicePrincipal"
        or str(rp.get("scope", "")).casefold() != choice["resource_id"].casefold()
        or expected_role.fullmatch(str(rp.get("roleDefinitionId", ""))) is None
        or rp.get("condition") not in (None, "")
    ):
        raise fail("cu-mi-role-unverified", "Require the selected Search principal's unconditional Cognitive Services User assignment on this CU account. Plan a missing scoped role explicitly; no self-grant or key fallback.")
    return {
        **selected, "search_endpoint": endpoint.rstrip("/"),
        "principal_id": identity["principalId"], "tenant_id": identity["tenantId"],
        "identity_type": identity["type"], "search_api_version": SEARCH_API, "role_api_version": ROLE_API,
        "role_definition_id": rp["roleDefinitionId"], "cu_resource_id": choice["resource_id"],
        "search_network": {k: copy.deepcopy(props.get(k)) for k in ("publicNetworkAccess", "networkRuleSet")},
    }, ids


def validate_state(state, choice, endpoint):
    if not isinstance(state, dict):
        raise fail("cu-mi-prerequisite-missing", "Retain the planner's verified Search identity/role binding.")
    fields = {"search_resource_id", "role_assignment_id", "search_endpoint", "principal_id", "tenant_id",
              "identity_type", "search_api_version", "role_api_version", "role_definition_id",
              "cu_resource_id", "search_network"}
    require_allowed_fields(state, fields, label="File CU identity state")
    selected = validate_choice(choice["managed_identity"], choice["resource_id"])
    if (
        set(state) != fields or any(state.get(k) != v for k, v in selected.items())
        or state["search_endpoint"] != endpoint.rstrip("/")
        or state["cu_resource_id"] != choice["resource_id"]
        or state["search_api_version"] != SEARCH_API or state["role_api_version"] != ROLE_API
        or not isinstance(state["search_network"], dict)
        or any(not isinstance(state[k], str) or cu_ingestion_auth.UUID.fullmatch(state[k]) is None
               for k in ("principal_id", "tenant_id"))
        or "SystemAssigned" not in str(state["identity_type"]).replace(" ", "").split(",")
        or not str(state["role_definition_id"]).casefold().endswith("/roledefinitions/" + CU_ROLE)
    ):
        raise fail("cu-mi-binding-invalid", "Retain complete, unchanged identity, role, API and account bindings.")


def verify_reuse(request, plan, current):
    paths = (request.get("reuse_input_file"), request.get("reuse_result_file"))
    if not all(isinstance(p, str) and p for p in paths):
        raise fail("cu-mi-provenance-required", "A redacted source GET cannot establish key versus MI auth. Retain the original approved version 1.2 File input and completed creation result for exact reuse.")
    prior, result = (_bootstrap_io.read_json(path) for path in paths)
    if (
        not isinstance(prior, dict) or not isinstance(result, dict)
        or not isinstance(prior.get("plan"), dict) or not isinstance(prior.get("approval"), dict)
        or not isinstance(result.get("resources"), dict)
        or not isinstance(result["resources"].get("created"), list)
    ):
        raise fail("cu-mi-provenance-mismatch", "Retain complete approved input and completed File result objects.")
    require_allowed_fields(prior, {"schema_version", "plan", "approval"}, label="MI creation input")
    try:
        from . import file_source
    except ImportError:
        import file_source
    approved = prior.get("approval", {})
    pp = prior.get("plan", {})
    file_source._validate_plan(pp)
    fingerprint = digest(pp)
    created = result.get("resources", {}).get("created", [])
    source = pp.get("source", {})
    if (
        prior.get("schema_version") != "1.0" or pp.get("file_cu_plan_version") != "1.2"
        or approved != {"confirmed": True, "fingerprint": fingerprint}
        or source.get("action") != "create" or source.get("endpoint") != plan["source"]["endpoint"]
        or source.get("name") != plan["source"]["name"] or pp.get("owner") != plan["owner"]
        or pp.get("cu_identity_state") != plan["cu_identity_state"]
        or pp.get("cu_resource_state") != plan["cu_resource_state"]
        or result.get("status") != "completed"
        or result.get("approved_plan") != {"confirmed": True, "fingerprint": fingerprint}
        or not search_reconcile.definitions_match(source.get("desired"), current)
        or not any(isinstance(item, dict) and item.get("type") == "knowledge-source"
                   and item.get("name") == source["name"] and item.get("etag") == current.get("@odata.etag")
                   and item.get("definition_digest") == digest(search_reconcile._definition(current))
                   for item in created)
    ):
        raise fail("cu-mi-provenance-mismatch", "Retained MI creation evidence does not bind the fresh source/ETag/account/identity. No auth inference, reingestion or ownership claim.")


def guard_create(plan, transport, recheck, checkpoint=None):
    """An expected-absent MI plan must not adopt another actor's redacted source."""
    url = search_reconcile.resource_url(plan["source"])
    acknowledged = False
    created_etag = None

    def on_created(**evidence):
        nonlocal created_etag
        # The reconciler calls this after ACK, outside ambiguous transport recovery.
        if checkpoint is not None:
            try:
                checkpoint(**evidence)
            except HelperFailure:
                raise
            except Exception:
                raise fail("cu-mi-checkpoint-failed", "Acknowledged MI creation checkpoint failed; private details withheld.") from None
        try:
            response = evidence["response"]
            created_etag = search_reconcile.resolve_etag(search_reconcile.response_etags(response), response.request_id)
        except HelperFailure:
            raise fail("cu-mi-ack-version-unverified", "MI creation was acknowledged, but its version evidence is invalid. Retain ownership; do not replay.") from None
        if created_etag is None:
            raise fail("cu-mi-ack-version-unverified", "MI creation was acknowledged without an ETag; redacted auth cannot be bound to a created version. Retain ownership; do not replay.")

    def guarded(method, target, token, **kwargs):
        nonlocal acknowledged, created_etag
        if method == "PUT" and target == url:
            recheck()
        result = transport(method, target, token, **kwargs)
        if target == url:
            if method == "PUT" and result.status in (200, 201):
                acknowledged = True
            if method == "GET" and result.status == 200 and plan["source"]["action"] == "create" and not acknowledged:
                raise fail("cu-mi-source-drift", "Expected source absence changed before creation; do not infer MI from redacted readback. Refresh discovery and provenance.")
            if method == "GET" and result.status == 200 and acknowledged:
                try:
                    observed_etag = search_reconcile.resolve_etag(search_reconcile.response_etags(result), result.request_id)
                except HelperFailure:
                    raise fail("cu-mi-readback-version-unverified", "Created MI source readback has invalid version evidence.") from None
                if observed_etag != created_etag:
                    raise fail("cu-mi-source-drift", "Source version changed after acknowledged MI creation; redacted auth is unproven. Inspect ownership before cleanup.")
        return result

    return guarded, on_created
