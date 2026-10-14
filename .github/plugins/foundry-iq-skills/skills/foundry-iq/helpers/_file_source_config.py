"""File source plan and Content Understanding validation/readback."""
from __future__ import annotations

import copy
import re
from typing import Any

try:
    from . import (
        search_reconcile, file_cu_mi, cu_ingestion_auth as file_cu_auth, _bootstrap_io, _embedding,
        _file_inventory, _search_read,
    )
    from ._common import (
        MANAGEMENT_AUDIENCE, HelperFailure, TokenProvider, Transport, digest, normalize_azure_location,
        reject_secrets, require_allowed_fields,
    )
except ImportError:
    import search_reconcile
    import file_cu_mi
    import cu_ingestion_auth as file_cu_auth
    import _bootstrap_io
    import _embedding
    import _file_inventory
    import _search_read
    from _common import (
        MANAGEMENT_AUDIENCE, HelperFailure, TokenProvider, Transport, digest, normalize_azure_location,
        reject_secrets, require_allowed_fields,
    )


def _cu_failure(code: str, message: str, *, request_id: str | None = None) -> HelperFailure:
    return HelperFailure(code, message, blocked_at="cu-prerequisites", request_id=request_id)


def validate_content_understanding(value: Any, *, enabled: bool) -> dict[str, Any] | None:
    if not enabled:
        if value is not None:
            raise _cu_failure("cu-choice-conflict", "Minimal extraction must omit CU choices.")
        return None
    if not isinstance(value, dict):
        raise _cu_failure("cu-prerequisite-missing", "Standard planning requires a resolved CU account, disclosed auth channel and owner-verified prerequisites.")
    value = copy.deepcopy(value)
    value.setdefault("auth", "system-assigned")
    reject_secrets(value)
    require_allowed_fields(value, {
        "endpoint", "resource_id", "auth", "api_key_environment", "prerequisites", "managed_identity",
    }, label="File CU choice")
    if (
        not isinstance(value.get("endpoint"), str)
        or re.fullmatch(r"https://[a-z0-9][a-z0-9-]{0,62}\.services\.ai\.azure\.com/?", value["endpoint"]) is None
        or not isinstance(value.get("resource_id"), str)
        or re.fullmatch(
            r"/subscriptions/[0-9a-fA-F-]{36}/resourceGroups/[A-Za-z0-9_.()-]{1,90}"
            r"/providers/Microsoft\.CognitiveServices/accounts/[A-Za-z0-9][A-Za-z0-9_.-]{1,63}",
            value["resource_id"], re.IGNORECASE,
        ) is None
        or value.get("auth") not in ("api-key-environment", "api-key-arm", "system-assigned")
        or (value.get("auth") == "api-key-environment" and (
            not isinstance(value.get("api_key_environment"), str)
            or search_reconcile.ENVIRONMENT_NAME.fullmatch(value["api_key_environment"]) is None
        ))
        or (value.get("auth") != "api-key-environment" and "api_key_environment" in value)
        or (value.get("auth") != "system-assigned" and "managed_identity" in value)
    ):
        raise _cu_failure("cu-choice-invalid", "Select exact AIServices and system-assigned MI, or explicitly retain approved ARM/ENV key auth. No automatic auth fallback or setup changes.")
    if value["auth"] == "system-assigned":
        file_cu_mi.validate_choice(value.get("managed_identity"), value["resource_id"])
    prerequisites = value.get("prerequisites")
    if not isinstance(prerequisites, dict):
        raise _cu_failure("cu-prerequisite-missing", "Supply CU region/capability, selected processing/required deployments, identity/local-auth and network evidence references.")
    fields = {"resource", "configuration", "identity", "network"}
    require_allowed_fields(prerequisites, fields, label="File CU prerequisites")
    if any(not _embedding._text(prerequisites.get(key)) for key in fields):
        raise _cu_failure("cu-prerequisite-missing", "Owner-verified CU capability/region, selected processing/required deployments, auth/access and reachability evidence is required.")
    _embedding._json_valid(value)
    return copy.deepcopy(value)


def _cu_account_state(choice: dict[str, Any], account: Any) -> dict[str, Any]:
    properties = account.get("properties") if isinstance(account, dict) else None
    if not isinstance(properties, dict):
        raise _cu_failure("cu-prerequisite-invalid", "CU account readback is incomplete.")
    endpoints = properties.get("endpoints", {})
    candidates = [properties.get("endpoint")]
    if isinstance(endpoints, dict):
        candidates.extend(endpoints.values())
    if (
        str(account.get("id", "")).casefold() != choice["resource_id"].casefold()
        or account.get("kind") != "AIServices"
        or normalize_azure_location(account.get("location")) is None
        or properties.get("provisioningState") != "Succeeded"
        or (choice["auth"] != "system-assigned" and properties.get("disableLocalAuth") is not False)
        or properties.get("publicNetworkAccess") not in ("Enabled", "Disabled")
        or choice["endpoint"].rstrip("/") not in [v.rstrip("/") for v in candidates if isinstance(v, str)]
    ):
        raise _cu_failure("cu-prerequisite-invalid", "Readback must bind the selected ready AIServices account/endpoint/location/network. Key modes also need enabled local auth; MI does not. Any required setup change needs separate approval.")
    state = {
        "id": choice["resource_id"], "kind": "AIServices", "location": account["location"],
        "identity": copy.deepcopy(account.get("identity")),
        "properties": {
            "endpoint": choice["endpoint"].rstrip("/"), "provisioningState": "Succeeded",
            "disableLocalAuth": properties.get("disableLocalAuth"), "publicNetworkAccess": properties["publicNetworkAccess"],
            "networkAcls": copy.deepcopy(properties.get("networkAcls")),
        },
    }
    if choice["auth"] == "system-assigned":
        acl = properties.get("networkAcls")
        if properties["publicNetworkAccess"] != "Enabled" or (
            acl is not None and (not isinstance(acl, dict) or acl.get("defaultAction") != "Allow")
        ):
            raise _cu_failure("cu-mi-network-unverified", "This MI path requires existing public CU reachability without default-deny ACLs. Restricted/private network compatibility needs separate verified setup and approval; no network changes or key fallback.")
    reject_secrets(state)
    _embedding._json_valid(state)
    return state


def _cu_states_match(current: dict[str, Any], retained: dict[str, Any]) -> bool:
    location = normalize_azure_location(retained.get("location"))
    return location is not None and (
        {**current, "location": normalize_azure_location(current.get("location"))}
        == {**retained, "location": location}
    )


def read_content_understanding(
    choice: dict[str, Any], *, token_provider: TokenProvider, transport: Transport,
) -> tuple[dict[str, Any], list[str]]:
    url = f"{MANAGEMENT_AUDIENCE}{choice['resource_id']}?api-version=2024-10-01"
    response = transport("GET", url, token_provider(MANAGEMENT_AUDIENCE))
    try:
        if response.status != 200:
            raise _cu_failure("cu-prerequisite-unavailable", "Selected CU account metadata could not be read; no provisioning or auth changes are allowed.")
        state = _cu_account_state(choice, response.body)
    except HelperFailure as failure:
        failure.request_id = response.request_id
        if response.status != 200:
            failure.http_status = response.status
        raise
    return state, [response.request_id] if response.request_id else []


def verify_content_understanding_readback(choice: dict[str, Any], current: Any) -> None:
    parameters = current.get("fileParameters") if isinstance(current, dict) else None
    ingestion = parameters.get("ingestionParameters") if isinstance(parameters, dict) else None
    ai = ingestion.get("aiServices") if isinstance(ingestion, dict) else None
    if (
        not isinstance(ai, dict) or ingestion.get("contentExtractionMode") != "standard"
        or not isinstance(ai.get("uri"), str)
        or ai["uri"].rstrip("/") != choice["endpoint"].rstrip("/")
        or ingestion.get("identity") is not None
        or (choice["auth"] == "system-assigned" and ai.get("apiKey") not in file_cu_mi.REDACTED)
    ):
        raise _cu_failure("cu-readback-mismatch", "Observed File CU endpoint/extraction/auth conflicts with the selected configuration; credential details withheld.")


def _validate_plan(
    plan: dict[str, Any],
    *,
    require_cu_readback: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    reject_secrets(plan)
    require_allowed_fields(
        plan,
        {
            "operation",
            "outcome",
            "cleanup_approved",
            "owner",
            "source",
            "ingestion",
            "embedding",
            "content_understanding",
            "file_cu_plan_version",
            "cu_resource_state",
            "cu_identity_state",
        },
        label="File source plan",
    )
    if (
        plan.get("operation") != "reconcile-and-ingest"
        or plan.get("cleanup_approved") is not False
    ):
        raise HelperFailure(
            "operation-invalid",
            "File source application requires reconcile-and-ingest with cleanup excluded.",
            blocked_at="input-resolution",
        )
    source = plan.get("source")
    ingestion = plan.get("ingestion")
    if not isinstance(source, dict) or not isinstance(ingestion, dict):
        raise HelperFailure(
            "input-schema-invalid",
            "File source application requires source and ingestion objects.",
            blocked_at="input-resolution",
        )
    desired = source.get("desired")
    if (
        source.get("operation") != "reconcile"
        or source.get("resource_type") != "knowledge-source"
        or source.get("action") not in {"create", "reuse"}
        or not isinstance(desired, dict)
        or desired.get("kind") != "file"
        or ingestion.get("operation") != "ingest"
        or plan.get("owner") != source.get("owner")
        or any(
            source.get(field) != ingestion.get(field)
            for field in ("endpoint", "name", "api_version", "owner")
        )
    ):
        raise HelperFailure(
            "step-contract-mismatch",
            "Source reconciliation and ingestion must target the same approved File source.",
            blocked_at="input-resolution",
        )
    source_mode = desired.get("fileParameters", {}).get(
        "ingestionParameters", {}
    ).get("contentExtractionMode")
    if source_mode != ingestion.get("extraction_mode"):
        raise HelperFailure(
            "step-contract-mismatch",
            "Source and ingestion extraction modes must match exactly.",
            blocked_at="input-resolution",
        )
    search_reconcile._validate_plan(source)
    _file_inventory._validate_plan(ingestion)
    _embedding.validate_plan_choice(plan)
    if any(field in plan for field in ("file_cu_plan_version", "content_understanding", "cu_resource_state")):
        if plan.get("file_cu_plan_version") not in ("1.0", "1.1", "1.2") or source_mode != "standard":
            raise _cu_failure("cu-plan-mismatch", "New File CU plans require their supported CU-specific version and standard extraction.")
        cu = validate_content_understanding(plan.get("content_understanding"), enabled=True)
        automatic = cu["auth"] == "api-key-arm"
        mi = cu["auth"] == "system-assigned"
        acquisition = source.get("ai_services_key_acquisition")
        if automatic:
            file_cu_auth.validate_acquisition(acquisition, cu["endpoint"])
        if (
            plan["file_cu_plan_version"] != ("1.2" if mi else "1.1" if automatic else "1.0")
            or (automatic and acquisition["resource_id"] != cu["resource_id"])
            or (not automatic and acquisition is not None)
            or source.get("ai_services_managed_identity") is not (True if mi else None)
            or (not mi and "cu_identity_state" in plan)
        ):
            raise _cu_failure("cu-plan-mismatch", "CU auth mode, version and exact acquisition scope must match the approved plan.")
        settings = desired["fileParameters"]["ingestionParameters"]
        if (
            settings.get("aiServices") != {"uri": cu["endpoint"].rstrip("/")}
            or settings.get("identity") is not None
            or settings.get("disableImageVerbalization") is not True
            or settings.get("chatCompletionModel") is not None
            or source.get("ai_services_api_key_environment") != cu.get("api_key_environment")
            or ("embedding" in plan) != (settings.get("embeddingModel") is not None)
        ):
            raise _cu_failure("cu-plan-mismatch", "CU/embedding choices, credential channel and source processing must match the approved definition.")
        if require_cu_readback:
            state = plan.get("cu_resource_state")
            if not isinstance(state, dict) or state != _cu_account_state(cu, state):
                raise _cu_failure("cu-prerequisite-missing", "Retain the planner's selected CU account readback.")
            if mi:
                file_cu_mi.validate_state(plan.get("cu_identity_state"), cu, source["endpoint"])
    elif source.get("ai_services_key_acquisition") is not None or source.get("ai_services_managed_identity") is not None or "cu_identity_state" in plan:
        raise _cu_failure("cu-plan-mismatch", "Automatic acquisition requires the complete versioned File CU workflow.")
    return source, ingestion


def verify_reuse(request, plan, current):
    paths = (request.get("reuse_input_file"), request.get("reuse_result_file"))
    if not all(isinstance(p, str) and p for p in paths):
        raise file_cu_mi.fail("cu-mi-provenance-required", "A redacted source GET cannot establish key versus MI auth. Retain the original approved version 1.2 File input and completed creation result for exact reuse.")
    prior, result = (_bootstrap_io.read_json(path) for path in paths)
    if (
        not isinstance(prior, dict) or not isinstance(result, dict)
        or not isinstance(prior.get("plan"), dict) or not isinstance(prior.get("approval"), dict)
        or not isinstance(result.get("resources"), dict)
        or not isinstance(result["resources"].get("created"), list)
    ):
        raise file_cu_mi.fail("cu-mi-provenance-mismatch", "Retain complete approved input and completed File result objects.")
    require_allowed_fields(prior, {"schema_version", "plan", "approval"}, label="MI creation input")

    approved = prior.get("approval", {})
    pp = prior.get("plan", {})
    _validate_plan(pp)
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
        or not _search_read.definitions_match(source.get("desired"), current)
        or not any(isinstance(item, dict) and item.get("type") == "knowledge-source"
                   and item.get("name") == source["name"] and item.get("etag") == current.get("@odata.etag")
                   and item.get("definition_digest") == digest(_search_read._definition(current))
                   for item in created)
    ):
        raise file_cu_mi.fail("cu-mi-provenance-mismatch", "Retained MI creation evidence does not bind the fresh source/ETag/account/identity. No auth inference, reingestion or ownership claim.")
