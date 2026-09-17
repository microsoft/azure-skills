from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

try:
    from ._progress import Progress, add_progress_argument, reporting
    from . import blob_inventory, search_reconcile, source_vector, cu_ingestion_auth
    from ._common import (
        SEARCH_AUDIENCE, HelperFailure, TokenProvider, Transport, azure_cli_token,
        blocked_result, canonical_bytes, digest, emit_result, http_request, load_approved_input, HttpResult,
        reject_secrets, require_allowed_fields,
    )
except ImportError:
    from _progress import Progress, add_progress_argument, reporting
    import blob_inventory  # type: ignore[no-redef]
    import search_reconcile  # type: ignore[no-redef]
    import source_vector  # type: ignore[no-redef]
    import cu_ingestion_auth
    from _common import (  # type: ignore[no-redef]
        SEARCH_AUDIENCE, HelperFailure, TokenProvider, Transport, azure_cli_token,
        blocked_result, canonical_bytes, digest, emit_result, http_request, load_approved_input, HttpResult,
        reject_secrets, require_allowed_fields,
    )


SNAPSHOT_WARNING = (
    "Before/after inventories detect observed drift, not an atomic Storage snapshot "
    "or a source lock. Scheduled sources can change after this run."
)
RETRY_STATUS = {408, 429, 500, 502, 503, 504}


def validate_content_understanding(value: Any, *, enabled: bool) -> dict[str, Any] | None:
    if not enabled:
        if value is not None:
            raise _failure("cu-choice-conflict", "Minimal extraction must omit Content Understanding choices.")
        return None
    if not isinstance(value, dict):
        raise _failure("cu-prerequisite-missing", "Standard extraction requires an existing CU-capable AIServices account.")
    require_allowed_fields(value, {"endpoint", "auth", "prerequisites"}, label="Content Understanding choices")
    endpoint = value.get("endpoint")
    if (
        not isinstance(endpoint, str)
        or re.fullmatch(r"https://[a-z0-9][a-z0-9-]{0,62}\.services\.ai\.azure\.com/?", endpoint) is None
        or value.get("auth") != "system-assigned"
    ):
        raise _failure("cu-auth-unsupported", "Select an exact AIServices services.ai.azure.com endpoint and existing Search system-assigned identity; no keys.")
    prerequisites = value.get("prerequisites")
    if not isinstance(prerequisites, dict):
        raise _failure("cu-prerequisite-missing", "Supply current CU resource, configuration, identity and network evidence references.")
    fields = {"resource", "configuration", "identity", "network"}
    require_allowed_fields(prerequisites, fields, label="Content Understanding prerequisites")
    if any(not isinstance(prerequisites.get(key), str) or not prerequisites[key].strip()
           or len(prerequisites[key]) > 4096 for key in fields):
        raise _failure("cu-prerequisite-missing", "Owner-verified CU capability/region, configuration, Search role and reachability evidence is required.")
    return copy.deepcopy(value)


def verify_content_understanding_readback(choice: dict[str, Any] | None, current: Any) -> None:
    if choice is None or current is None:
        return
    parameters = current.get("azureBlobParameters") if isinstance(current, dict) else None
    ingestion = parameters.get("ingestionParameters") if isinstance(parameters, dict) else None
    ai = ingestion.get("aiServices") if isinstance(ingestion, dict) else None
    if (
        not isinstance(ai, dict) or ingestion.get("contentExtractionMode") != "standard"
        or not isinstance(ai.get("uri"), str)
        or ai["uri"].rstrip("/") != choice["endpoint"].rstrip("/")
    ):
        raise _failure("cu-readback-mismatch", "Observed standard extraction and CU endpoint must match the selected configuration.")
    key = ai.get("apiKey")
    if (key is not None and not (isinstance(key, str) and key == "")
            or ingestion.get("identity") is not None):
        raise _failure("cu-auth-conflict", "Observed CU authentication does not prove system-assigned mode; credential details withheld.")


def generated_resources(current: dict[str, Any], *, strict: bool = False) -> list[dict[str, Any]]:
    parameters = current.get("azureBlobParameters")
    created = parameters.get("createdResources") if isinstance(parameters, dict) else None
    generated = []
    if isinstance(created, dict):
        for kind, name in created.items():
            if (
                kind in {"datasource", "dataSourceConnection", "indexer", "skillset", "index"}
                and isinstance(name, str) and re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}", name)
            ):
                generated.append({
                    "type": "datasource" if kind == "dataSourceConnection" else kind,
                    "name": name, "service_managed": True,
                })
    generated.sort(key=lambda item: (item["type"], item["name"]))
    if strict and (
        not isinstance(created, dict) or len(created) != 4 or len(generated) != 4
        or {item["type"] for item in generated} != {"datasource", "indexer", "skillset", "index"}
    ):
        raise _failure("generated-resources-unverified", "Exact service-generated identities are required for reuse.")
    return generated


def _read_intent(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _failure("input-unreadable", "Input must be readable UTF-8 JSON.") from exc
    if not isinstance(document, dict):
        raise _failure("input-schema-invalid", "Input must be an object.")
    return document


def _receipt_paths(request: dict[str, Any]) -> tuple[str, str] | None:
    paths = [request.get(field) for field in ("reuse_input_file", "reuse_result_file")]
    if paths == [None, None]:
        return None
    if not all(isinstance(path, str) and path.strip() for path in paths):
        raise _failure("reuse-evidence-invalid", "Select both retained approved input and creation result files.")
    return paths[0], paths[1]


def _reuse_receipts(paths: tuple[str, str] | None) -> tuple[dict[str, Any], dict[str, Any]] | None:
    if paths is None:
        return None
    try:
        _, prior, fingerprint = load_approved_input(Path(paths[0]))
    except UnicodeError as exc:
        raise _failure("input-unreadable", "Retained input must be readable UTF-8 JSON.") from exc
    _validate_plan(prior)
    result = _read_intent(Path(paths[1]))
    _validate_reuse_receipts(prior, fingerprint, result)
    return prior, result


def _validate_reuse_receipts(prior, fingerprint, result):
    reject_secrets(result)
    if not all(isinstance(result.get(field), dict) for field in (
        "approved_plan", "source_evidence", "resources", "verification", "source"
    )):
        raise _failure("reuse-evidence-invalid", "Retained creation result sections must be objects.")
    if (
        prior["source"]["action"] != "create" or result.get("status") != "completed"
        or result["approved_plan"].get("confirmed") is not True
        or result.get("approved_plan") != {"confirmed": True, "fingerprint": fingerprint}
        or result.get("source_evidence", {}).get("boundary") != prior["boundary"]
        or result.get("source_evidence", {}).get("inventory_digest") != prior["inventory_digest"]
    ):
        raise _failure("reuse-evidence-invalid", "Retained records must prove the exact approved source creation.")


def _connection_binding(connection, boundary):
    if connection is None or isinstance(connection, str) and connection.lower() in ("", "<redacted>"):
        return "concealed"
    if isinstance(connection, str) and connection.startswith("ResourceId="):
        if connection.removesuffix(";") != f"ResourceId={boundary['storage_id']}":
            raise _failure("boundary-mismatch", "Observed connection targets a different Storage account.")
        return "visible"
    raise _failure("source-binding-conflict", "Observed credentials are not the selected keyless binding or a recognized concealed value; details withheld.")


def _verify_storage_binding(
    source: dict[str, Any], boundary: dict[str, Any], current: dict[str, Any],
    generated: list[dict[str, Any]],
    load_receipts: Callable[[], tuple[dict[str, Any], dict[str, Any]] | None],
) -> None:
    connection = current["azureBlobParameters"].get("connectionString")
    if _connection_binding(connection, boundary) == "visible":
        return
    receipts = load_receipts()
    if receipts is None:
        raise _failure(
            "source-binding-unverified",
            "Source account binding is unknown: GET the exact source definition or select its retained approved input/successful creation result pair. Redaction is not a mismatch; snippets are not binding proof.",
        )
    _verify_creation_binding(source, boundary, current, generated, receipts)


def _verify_creation_binding(
    source: dict[str, Any], boundary: dict[str, Any], current: dict[str, Any],
    generated: list[dict[str, Any]], receipts: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    prior, result = receipts
    observed = {
        "type": "knowledge-source", "name": source["name"], "etag": current["@odata.etag"],
        "definition_digest": digest(search_reconcile._definition(current)),
    }
    if (
        prior["boundary"] != boundary
        or any(prior["source"].get(field) != source[field] for field in ("endpoint", "name", "api_version"))
        or not search_reconcile.definitions_match(prior["source"]["desired"], current)
        or result.get("resources", {}).get("created") != [observed]
        or result.get("verification", {}).get("readback") != observed
        or result.get("source", {}).get("generated") != generated
    ):
        raise _failure("source-binding-unverified", "Retained creation evidence does not match the fresh source identity/ETag.")


def plan_source(
    request: dict[str, Any], *,
    token_provider: TokenProvider = azure_cli_token, transport: Transport = http_request,
    storage_transport: Transport = http_request, monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise _failure("input-schema-invalid", "Planning input must be an object.")
    reject_secrets(request)
    require_allowed_fields(
        request,
        {"schema_version", "endpoint", "name", "owner", "storage_id", "container", "prefix", "is_adls",
         "api_version", "processing", "network_access", "identity", "permission_options",
         "ingestion_schedule", "description", "rbac", "network", "inventory_limits", "poll",
         "reuse_input_file", "reuse_result_file", "embedding", "content_understanding"},
        label="Blob planning input",
    )
    try:
        json.dumps(request, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (UnicodeError, TypeError, ValueError) as exc:
        raise _failure("input-schema-invalid", "Planning choices must be valid UTF-8 JSON.") from exc
    if request.get("schema_version") != "1.0" or not isinstance(request.get("owner"), str) or not request["owner"].strip():
        raise _failure("input-schema-invalid", "schema_version 1.0 and an explicit owner are required.")
    boundary = blob_inventory.validate_boundary({
        field: request.get(field) for field in ("storage_id", "container", "prefix", "is_adls")
    })
    limits = copy.deepcopy(blob_inventory.validate_limits(request.get("inventory_limits")))
    poll = copy.deepcopy(_poll_limits(request.get("poll")))
    if (
        request.get("processing") not in ("minimal-lexical", "minimal-vector", "standard-cu") or request.get("network_access") != "public"
        or request.get("identity") != "system-assigned" or request.get("permission_options") != []
        or "ingestion_schedule" not in request or request["ingestion_schedule"] is not None
        or not isinstance(request.get("api_version"), str)
        or request["api_version"] not in {"2026-04-01", "2026-08-01-preview"}
        or boundary["is_adls"] and request["api_version"] != "2026-08-01-preview"
    ):
        raise _failure(
            "planning-processing-unsupported",
            "This planner supports Blob 2026-04-01/2026-08-01-preview and ADLS 2026-08-01-preview: "
            "Internal presets: minimal-lexical = minimal extraction without vectors; "
            "minimal-vector = minimal extraction with embeddings; standard-cu = standard CU with optional embeddings. "
            "These are not API enums or KB reasoning modes. Requires public, system-assigned, no permissions/schedule. "
            "Other requested versions/features need a compatible owner; never change them silently.",
        )
    embedding = source_vector.validate_choice(
        request.get("embedding"), enabled=(
            request["processing"] == "minimal-vector"
            or request["processing"] == "standard-cu" and request.get("embedding") is not None
        ),
        api_version=request["api_version"],
    )
    cu = validate_content_understanding(
        request.get("content_understanding"), enabled=request["processing"] == "standard-cu",
    )
    if "description" not in request or not (
        request["description"] is None or isinstance(request["description"], str)
    ):
        raise _failure("input-schema-invalid", "description must be explicit text or null.")
    rbac, network = request.get("rbac"), request.get("network")
    if (
        not isinstance(rbac, dict) or not isinstance(rbac.get("assignments"), list)
        or not rbac["assignments"] or not all(isinstance(item, dict) and item for item in rbac["assignments"])
        or not isinstance(network, dict) or network.get("posture") != "public"
        or not isinstance(network.get("evidence"), str) or not network["evidence"].strip()
    ):
        raise _failure("planning-evidence-missing", "Supply observed RBAC assignments and public network evidence; the owner verifies effective access and policy.")
    ingestion = {
        "contentExtractionMode": "minimal", "disableImageVerbalization": True,
        "identity": None, "ingestionSchedule": None,
    }
    if request["api_version"].endswith("-preview"):
        ingestion.update(networkAccessMode="public", ingestionPermissionOptions=[])
    if embedding is not None:
        ingestion["embeddingModel"] = source_vector.model_definition(embedding)
    if cu is not None:
        ingestion.update(contentExtractionMode="standard", aiServices={"uri": cu["endpoint"].rstrip("/")})
    source = {
        "operation": "reconcile", "resource_type": "knowledge-source",
        "outcome": "create-blob-knowledge-source",
        "endpoint": request.get("endpoint"), "name": request.get("name"),
        "api_version": request["api_version"], "action": "create",
        "owner": request["owner"], "cleanup_approved": False,
        "rbac": copy.deepcopy(rbac), "network": copy.deepcopy(network),
        "desired": {
            "name": request.get("name"), "kind": "azureBlob", "description": request["description"],
            "azureBlobParameters": {
                "connectionString": f"ResourceId={boundary['storage_id']}",
                "containerName": boundary["container"], "folderPath": boundary["prefix"] or None,
                "isADLSGen2": boundary["is_adls"], "ingestionParameters": ingestion,
            },
        },
    }
    # Validate the shared control sections and exact address before any authentication.
    for section, fields in ((rbac, {"assignments"}), (network, {"posture", "evidence"})):
        require_allowed_fields(section, fields, label="planning controls")
    url = search_reconcile.resource_url(source)
    receipt_paths = _receipt_paths(request)
    receipts = None

    def load_receipts() -> tuple[dict[str, Any], dict[str, Any]] | None:
        nonlocal receipts
        if receipts is None:
            receipts = _reuse_receipts(receipt_paths)
        return receipts

    deadline = monotonic() + limits["deadline_seconds"]

    def read_search() -> tuple[dict[str, Any] | None, str | None]:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise _failure("planning-deadline-exceeded", "Planning read deadline elapsed.")

        def bounded(method: str, target: str, token: str, **kwargs: Any) -> Any:
            if method != "GET" or target != url:
                raise _failure("planning-write-forbidden", "Planning reads only the exact Search source.")
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise _failure("planning-deadline-exceeded", "Planning read deadline elapsed during authentication.")
            return transport(
                method, target, token, timeout=min(30, remaining), follow_redirects=False,
                max_response_bytes=8 * 1024 * 1024, response_deadline=time.monotonic() + remaining,
            )

        current, request_id = search_reconcile.read_resource(url, token_provider(SEARCH_AUDIENCE), transport=bounded)
        try:
            source_vector.verify_source_readback(embedding, current)
            verify_content_understanding_readback(cu, current)
        except HelperFailure as failure:
            failure.request_id = request_id
            raise
        return current, request_id

    current, first_id = read_search()
    generated = []
    if current is not None:
        if not search_reconcile.definitions_match(source["desired"], current):
            raise _failure("definition-conflict", "The exact source has a different definition; do not overwrite, suffix or repair it.")
        if not isinstance(current.get("@odata.etag"), str) or not current["@odata.etag"]:
            raise _failure("definition-evidence-missing", "Exact reuse requires the current source ETag.")
        generated = generated_resources(current, strict=True)
        _verify_storage_binding(source, boundary, current, generated, load_receipts)
    snapshot = blob_inventory.discover(
        boundary, limits, token_provider=token_provider, transport=storage_transport,
        monotonic=monotonic, deadline=deadline,
    )
    refreshed, last_id = read_search()
    if (current is None) != (refreshed is None) or current is not None and (
        refreshed.get("@odata.etag") != current["@odata.etag"]
        or not search_reconcile.definitions_match(source["desired"], refreshed)
        or generated_resources(refreshed, strict=True) != generated
    ):
        raise _failure("definition-drift", "Source identity/ETag or generated resources changed during Storage observation.")
    if refreshed is not None:
        _verify_storage_binding(source, boundary, refreshed, generated, load_receipts)
        source.update(action="reuse", expected_etag=refreshed["@odata.etag"])
    if monotonic() >= deadline:
        raise _failure("planning-deadline-exceeded", "Planning read deadline elapsed during Search readback.")
    evidence = {"verified": True, "inventory_digest": snapshot["inventory_digest"]}
    if boundary["is_adls"]:
        evidence.update(path_verified=True, acl_verified=True)
    source["source_evidence"] = evidence
    plan = {
        "operation": "reconcile-and-monitor", "owner": request["owner"], "cleanup_approved": False,
        "boundary": boundary, "inventory_digest": snapshot["inventory_digest"],
        "inventory_limits": limits, "poll": poll, "source": source,
    }
    if embedding is not None:
        plan["embedding"] = embedding
    if cu is not None:
        plan["content_understanding"] = cu
        plan["cu_plan_version"] = "1.0"
    if current is not None:
        plan["expected_generated"] = generated
    else:
        plan["expected_source_absent"] = True
    _validate_plan(plan)
    fingerprint = digest(plan)
    mutation = source["action"] == "create"
    return {
        "status": "planned", "outcome": "create-blob-knowledge-source",
        "plan_fingerprint": fingerprint,
        "execution_input": {
            "schema_version": "1.0", "plan": plan,
            "approval": {"confirmed": False, "fingerprint": fingerprint},
        },
        "approval_summary": {
            "target": {"endpoint": source["endpoint"], "name": source["name"], "api_version": source["api_version"]},
            "storage_account": boundary["storage_id"].rsplit("/", 1)[1],
            "source_kind": "adls-gen2" if boundary["is_adls"] else "azure-blob",
            "scope": "selected folder/directory" if boundary["prefix"] else "explicit container/filesystem root",
            "object_count": len(snapshot["objects"]), "total_bytes": sum(item["size"] for item in snapshot["objects"]),
            "adls_paths_observed": len(snapshot["adls_paths"]),
            "processing": (
                f"standard Content Understanding extraction {'with selected embeddings' if embedding else 'without source vectors'}; no image verbalization, chat, permission ingestion or schedule"
                if cu else
                "minimal extraction with embeddings; no image verbalization, permission ingestion or schedule"
                if embedding else "minimal lexical; image verbalization disabled; no models, permission ingestion or schedule"
            ),
            **({"embedding": source_vector.summary(embedding)} if embedding else {}),
            **({"content_understanding": {
                "purpose": "Standard document extraction only; not source vectorization or KB answer synthesis.",
                "endpoint": cu["endpoint"].rstrip("/"), "auth": cu["auth"],
                "authentication": cu_ingestion_auth.approval_summary(
                    "adlsGen2" if request["is_adls"] else "azureBlob", cu["auth"], creating=mutation,
                ),
                "kb_reasoning": "Unchanged; KB chat requires separate selection, access and approval.",
                "cost_and_data": "Creation sends selected documents to billable CU processing (no free document allowance); generated Search content is retained. Cross-region processing may apply. Selected source embeddings have separate costs.",
                "source_vectorization": "azureOpenAI" if embedding else "none",
                "prerequisites": "Owner-verified references only, not effective access or successful processing proof. No local auth, role, model or defaults changes.",
            }} if cu else {}),
            "network": "public; supplied access evidence remains owner-verified",
            "supplied_role_assignments": len(rbac["assignments"]),
            "source_action": source["action"], "execution_required": mutation,
            "mutation_approval_required": mutation,
            "ownership": "Only a newly created source and its service-generated children become run-owned; existing Search/Storage/objects/roles remain shared.",
            "verification": "Fresh identity/inventory and ADLS owner/ACL metadata only; effective Search access, ingestion readiness and retrieval are unverified.",
            "cost_and_retention": "Creation starts indexing and retains generated Search resources; existing charges/schedules continue on reuse.",
            "cleanup": "Separate run-owned source cleanup only; never delete Storage objects or shared resources.",
            "next_step": (
                "Owner refreshes identity, RBAC, network, source state and cost/data consent, then approves these changes before applying the unchanged private artifact."
                if mutation else "Reuse without mutation approval or executor invocation. Refresh discovery before later use; evidence is not future consent."
            ),
        },
        "read_only_evidence": {"request_ids": [item for item in [first_id, *snapshot["request_ids"], last_id] if item]},
        "writes_performed": [], "warnings": [SNAPSHOT_WARNING],
    }


def _failure(code: str, message: str, *, request_id: str | None = None) -> HelperFailure:
    return HelperFailure(code, message, blocked_at="verification", request_id=request_id)


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise _failure("ingestion-status-invalid", "Synchronization timestamp is missing.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _failure("ingestion-status-invalid", "Synchronization timestamp is invalid.") from exc
    if parsed.tzinfo is None:
        raise _failure("ingestion-status-invalid", "Synchronization timestamp needs a time zone.")
    return parsed


def _poll_limits(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        raise _failure("input-schema-invalid", "poll must be an object.")
    require_allowed_fields(
        value, {"deadline_seconds", "max_requests", "interval_seconds"}, label="poll"
    )
    for field, maximum in (
        ("deadline_seconds", 3600), ("max_requests", 1000), ("interval_seconds", 60)
    ):
        if type(value.get(field)) is not int or not 1 <= value[field] <= maximum:
            raise _failure("input-schema-invalid", "Polling limits must be bounded positive integers.")
    return value


def _validate_plan(plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    reject_secrets(plan)
    require_allowed_fields(
        plan,
        {"operation", "owner", "cleanup_approved", "source", "boundary", "inventory_digest",
         "inventory_limits", "poll", "expected_generated", "expected_source_absent", "embedding",
         "content_understanding", "cu_plan_version"},
        label="Blob source plan",
    )
    if plan.get("operation") != "reconcile-and-monitor" or plan.get("cleanup_approved") is not False:
        raise _failure("operation-invalid", "Blob application requires reconcile-and-monitor without cleanup.")
    source = plan.get("source")
    if not isinstance(source, dict) or not isinstance(plan.get("owner"), str) or not plan["owner"]:
        raise _failure("input-schema-invalid", "A source plan and owner are required.")
    if (
        source.get("operation") != "reconcile"
        or source.get("resource_type") != "knowledge-source"
        or source.get("action") not in ("create", "reuse")
        or not isinstance(source.get("api_version"), str)
        or source.get("owner") != plan["owner"]
        or not isinstance(source.get("desired"), dict)
        or source["desired"].get("kind") != "azureBlob"
        or source.get("ai_services_api_key_environment") is not None
        or source.get("ai_services_key_acquisition") is not None
    ):
        raise _failure("step-contract-mismatch", "Only same-owner Blob creation or exact reuse is supported.")
    search_reconcile._validate_plan(source)
    search_reconcile._resource_url(source)
    boundary = blob_inventory.validate_boundary(plan.get("boundary"))
    blob_inventory.validate_limits(plan.get("inventory_limits"))
    _poll_limits(plan.get("poll"))
    if "expected_source_absent" in plan and (
        plan["expected_source_absent"] is not True or source["action"] != "create"
        or source.get("expected_etag") is not None
    ):
        raise _failure("step-contract-mismatch", "Expected absence is only valid for a creation plan.")
    if "expected_generated" in plan and (
        source["action"] != "reuse"
        or not isinstance(plan["expected_generated"], list)
        or len(plan["expected_generated"]) != 4
        or any(not isinstance(item, dict) or set(item) != {"type", "name", "service_managed"}
               or item["service_managed"] is not True
               or not isinstance(item["type"], str)
               or not isinstance(item["name"], str)
               or re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}", item["name"]) is None
               for item in plan["expected_generated"])
        or {item["type"] for item in plan["expected_generated"]} != {"datasource", "indexer", "skillset", "index"}
    ):
        raise _failure("generated-resources-unverified", "Expected generated identities require a complete reuse plan.")
    parameters = source["desired"]["azureBlobParameters"]
    if (
        parameters["connectionString"].removesuffix(";") != f"ResourceId={boundary['storage_id']}"
        or parameters["containerName"] != boundary["container"]
        or parameters["folderPath"] != (boundary["prefix"] or None)
        or parameters["isADLSGen2"] != boundary["is_adls"]
        or "createdResources" in parameters
        or source["source_evidence"]["inventory_digest"] != plan.get("inventory_digest")
    ):
        raise _failure("boundary-mismatch", "Source definition must bind the exact discovered boundary and inventory.")
    if (
        not isinstance(plan.get("inventory_digest"), str)
        or search_reconcile.SHA256.fullmatch(plan["inventory_digest"]) is None
    ):
        raise _failure("source-evidence-invalid", "The approved inventory digest is required.")
    ingestion = parameters.get("ingestionParameters")
    if not isinstance(ingestion, dict) or ingestion.get("assetStore") is not None:
        raise _failure(
            "source-write-forbidden",
            "Ingestion parameters are required; asset-store writes are outside this read-only-source workflow.",
        )
    source_vector.validate_plan_choice(plan)
    standard = ingestion.get("contentExtractionMode") == "standard"
    if "cu_plan_version" in plan and (plan["cu_plan_version"] != "1.0" or not standard):
        raise _failure("cu-plan-version-invalid", "CU planner artifacts require version 1.0 and standard extraction.")
    # Absence/generated guards predate CU planning and remain valid on legacy
    # wire-only artifacts. Only CU-specific provenance selects the new contract.
    planner_cu = standard and any(field in plan for field in (
        "cu_plan_version", "embedding", "content_understanding",
    ))
    cu = validate_content_understanding(
        plan.get("content_understanding"), enabled=planner_cu,
    )
    if cu is not None:
        expected = {
            "contentExtractionMode": "standard", "disableImageVerbalization": True,
            "identity": None, "ingestionSchedule": None,
            "aiServices": {"uri": cu["endpoint"].rstrip("/")},
        }
        if "embedding" in plan:
            expected["embeddingModel"] = source_vector.model_definition(plan["embedding"])
        if source["api_version"].endswith("-preview"):
            expected.update(networkAccessMode="public", ingestionPermissionOptions=[])
        if ingestion != expected or boundary["is_adls"] and source["api_version"] != "2026-08-01-preview":
            raise _failure("cu-plan-mismatch", "Standard CU requires the unchanged keyless public definition, matching optional embeddings and no chat, asset store, permissions or schedule.")
    return source, boundary


def _first_error(state: dict[str, Any]) -> dict[str, Any] | None:
    errors = state.get("errors")
    if errors is None or errors == []:
        return None
    if not isinstance(errors, list) or any(not isinstance(error, dict) for error in errors):
        raise _failure("ingestion-status-invalid", "Ingestion errors have an invalid shape.")
    error = errors[0]
    # Document errors can contain content, SAS URLs, and credentials in free text.
    return {
        "status": error.get("statusCode") if type(error.get("statusCode")) is int else None,
        "message": "Document-level ingestion error; sensitive service text withheld.",
        "diagnostic_digest": digest(error),
    }


def _synchronization_state(state, request_id=None):
    if state is None:
        return None
    if not isinstance(state, dict):
        raise _failure("ingestion-status-invalid", "Synchronization state must be an object.", request_id=request_id)
    return dict(state)


def _retry_after(value, *, now=None):
    now = now or datetime.now(timezone.utc)
    kind = getattr(value, "kind", None)
    try:
        if kind is not None:
            if kind == "overlong":
                return math.inf
            payload = getattr(value, "value", None)
            if (not isinstance(kind, str) or kind not in {"seconds", "date", "date-rfc850"}
                    or type(payload) not in (int, float)
                    or (type(payload) is float and not math.isfinite(payload))):
                return None
            if kind == "seconds":
                return payload if payload >= 0 and payload == int(payload) else None
            parsed = datetime.fromtimestamp(payload, timezone.utc)
            obsolete_date = kind == "date-rfc850"
        else:
            if not isinstance(value, str) or len(value) > 128:
                return None
            if value.isascii() and value.isdigit() and len(value) <= 10:
                return int(value)
            parsed = parsedate_to_datetime(value)
            obsolete_date = bool(re.fullmatch(r"[A-Za-z]+, \d{2}-[A-Za-z]{3}-\d{2} \d{2}:\d{2}:\d{2} GMT", value))
        if obsolete_date:
            year = now.year // 100 * 100 + parsed.year % 100
            if year > now.year + 50:
                year -= 100
            parsed = parsed.replace(year=year)
        if parsed.tzinfo is not None:
            return max(0, (parsed - now).total_seconds())
    except (ValueError, OverflowError, TypeError, OSError):
        pass
    return None


def _execution_progress(body, not_before):
    if (not isinstance(body, dict) or not isinstance(body.get("status"), str)
            or body["status"] not in {"running", "error", "unknown"}):
        raise _failure("indexer-status-invalid", "Indexer status must be an object.")
    if body["status"] == "error":
        raise _failure("indexer-status-error", "Indexer availability reports an error; execution success is not inferred.")
    run = body.get("lastResult")
    if run is None:
        return None
    if not isinstance(run, dict):
        raise _failure("indexer-status-invalid", "Latest indexer execution must be an object.")
    start = _timestamp(run.get("startTime"))
    if start < not_before:
        return None
    status = run.get("status")
    if not isinstance(status, str) or status not in {"inProgress", "success", "transientFailure", "persistentFailure", "reset"}:
        raise _failure("indexer-status-invalid", "Unknown latest execution status; top-level running is not execution proof.")
    result = {"startTime": run["startTime"], "run_status": status}
    if run.get("endTime") is not None:
        if _timestamp(run["endTime"]) < start:
            raise _failure("indexer-status-invalid", "Indexer execution interval is invalid.")
        result["endTime"] = run["endTime"]
    for field, target in (("itemsProcessed", "items_attempted"), ("itemsFailed", "items_failed")):
        if field in run:
            if type(run[field]) is not int or run[field] < 0:
                raise _failure("indexer-status-invalid", "Indexer execution counters are invalid.")
            result[target] = run[field]
    if result.get("items_failed", 0) > result.get("items_attempted", result.get("items_failed", 0)):
        raise _failure("indexer-status-invalid", "Failed item count exceeds attempted items.")
    errors = run.get("errors", [])
    if errors is not None and (not isinstance(errors, list) or any(not isinstance(item, dict) for item in errors)):
        raise _failure("indexer-status-invalid", "Indexer execution errors are malformed.")
    result["error_count"] = len(errors or [])
    return result


def _execution_completed_by(execution, end, not_before):
    required = {"startTime", "endTime", "run_status", "error_count"}
    if (not isinstance(execution, dict) or not required <= execution.keys()
            or execution.keys() - required - {"items_attempted", "items_failed"}
            or execution["run_status"] != "success"
            or type(execution["error_count"]) is not int or execution["error_count"] != 0
            or any(type(execution[key]) is not int or execution[key] < 0
                   for key in ("items_attempted", "items_failed") if key in execution)
            or execution.get("items_failed", 0)):
        return False
    try:
        return not_before <= _timestamp(execution["startTime"]) <= _timestamp(execution["endTime"]) <= end
    except HelperFailure:
        return False


@reporting("blob-monitor")
def monitor(
    source: dict[str, Any],
    *,
    not_before: datetime,
    limits: dict[str, int],
    token_provider: TokenProvider,
    transport: Transport,
    require_new_cycle: bool = False,
    excluded_cycle: list[str] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    progress: Progress | None = None,
    cancelled: Callable[[], bool] = lambda: False,
    indexer_name: str | None = None,
) -> dict[str, Any]:
    _poll_limits(limits)
    progress.update("ingestion-cycle")
    excluded = tuple(_timestamp(value) for value in excluded_cycle) if excluded_cycle is not None else None
    url = (
        f"{source['endpoint'].rstrip('/')}/knowledgesources('{search_reconcile._odata_name(source['name'])}')/status?"
        + urlencode({"api-version": source["api_version"]})
    )
    token = token_provider(SEARCH_AUDIENCE)
    started = monotonic()
    deadline = started + limits["deadline_seconds"]
    request_ids: list[str] = []
    first_error: dict[str, Any] | None = None
    first_retry: dict[str, Any] | None = None
    observed = "no-completed-cycle"
    initial_cycle: tuple[Any, Any] | None = None
    first_response = True
    checks = 0
    delay = limits["interval_seconds"]
    latest = {}
    previous = None
    previous_execution = None
    execution_guard = None
    pause_reason = "request-limit"
    newest_run = None
    synchronization_status = "not-reported"

    def report(phase, next_check=None):
        value = {
            "schema_version": "1.0", "phase": phase,
            "run_start": _timestamp(latest["startTime"]).isoformat() if latest.get("startTime") else None,
            "processed": latest.get("itemsUpdatesProcessed"), "failed": latest.get("itemsUpdatesFailed"),
            "skipped": latest.get("itemsSkipped"), "unit": "item-updates",
            "total": None, "remaining": None, "denominator": "not-comparable-to-files",
            "synchronization_status": synchronization_status,
            "elapsed_seconds": max(0, monotonic() - started), "next_check_seconds": next_check,
        }
        progress.counts["status_checks"] = checks
        progress.blob_update(value)
        return value

    def failure_result(*args):
        result = _readiness_failure(*args)
        result["progress"] = report("failed")
        result["watch"] = {"schema_version": "1.0", "state": "blocked", "reason": "evidence-failure",
                           "elapsed_seconds": max(0, monotonic() - started),
                           "status_checks": checks, "latest": copy.deepcopy(latest)}
        return result

    def read_status(target):
        nonlocal checks, retry_after
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise _failure("ingestion-watch-expired", "The client watch window elapsed before this read.")
        checks += 1
        response = transport(
            "GET", target, token, timeout=min(30, remaining),
            max_response_bytes=8 * 1024 * 1024, follow_redirects=False,
            response_deadline=monotonic() + min(30, remaining),
        )
        if response.request_id:
            request_ids.append(response.request_id)
        if response.status != 200:
            value = getattr(response, "retry_after", None)
            if value is None:
                value = next((v for k, v in response.headers.items() if k.lower() == "retry-after"), None)
            retry_after = _retry_after(value)
            raise HelperFailure("ingestion-inaccessible", "Status read is inaccessible.",
                                blocked_at="verification", status=response.status, request_id=response.request_id)
        return response

    while checks < limits["max_requests"]:
        remaining = deadline - monotonic()
        if cancelled():
            pause_reason = "cancelled"
            break
        if remaining <= 0:
            pause_reason = "deadline"
            break
        retry_after = None
        throttled = False
        try:
            response = read_status(url)
        except KeyboardInterrupt:
            pause_reason = "cancelled"
            break
        except HelperFailure as failure:
            if failure.request_id and failure.request_id not in request_ids:
                request_ids.append(failure.request_id)
            if failure.code == "response-deadline-exceeded":
                first_retry = first_retry or {"code": failure.code, "status": failure.http_status,
                                              "request_id": failure.request_id}
                if monotonic() >= deadline:
                    pause_reason = "deadline"
                    break
            if failure.code == "ingestion-watch-expired":
                pause_reason = "deadline"
                break
            if retry_after is None:
                retry_after = _retry_after(failure.retry_after)
            if (failure.http_status not in RETRY_STATUS
                    and failure.code not in {"azure-response-ambiguous", "response-deadline-exceeded"}):
                return failure_result("ingestion-inaccessible", failure.request_id, request_ids,
                                          first_error, first_retry, failure.http_status)
            if first_retry is None:
                first_retry = {"code": failure.code, "status": failure.http_status,
                               "request_id": failure.request_id}
            throttled = failure.http_status == 429
            delay = min(60, max(limits["interval_seconds"], delay * 2))
        else:
            if monotonic() >= deadline:
                pause_reason = "deadline"
                break
            body = response.body
            if not isinstance(body, dict) or body.get("kind") != "azureBlob":
                raise _failure("ingestion-status-invalid", "Expected azureBlob status.", request_id=response.request_id)
            synchronization_status = body.get("synchronizationStatus", "not-reported")
            if synchronization_status not in ("not-reported", "active", "creating", "deleting"):
                raise _failure("ingestion-status-invalid", "Unknown knowledge-source synchronization availability.",
                               request_id=response.request_id)
            current = _synchronization_state(body.get("currentSynchronizationState"), response.request_id)
            last = _synchronization_state(body.get("lastSynchronizationState"), response.request_id)
            for state in (current, last):
                if state is not None:
                    _timestamp(state.get("startTime"))
                    _first_error(state)
            state = current or last
            start = _timestamp(state["startTime"]) if state else None
            if start is not None and start >= not_before and (newest_run is None or start >= newest_run):
                newest_run = start
                error = _first_error(state)
                if first_error is None and error:
                    first_error = {**error, "request_id": response.request_id}
                latest = {"startTime": state["startTime"],
                          "state": "in-progress" if current else "completed-cycle-observed"}
                for field in ("itemsUpdatesProcessed", "itemsUpdatesFailed", "itemsSkipped"):
                    if field in state:
                        if type(state[field]) is not int or state[field] < 0:
                            raise _failure("ingestion-status-invalid", "Observed synchronization counters are invalid.",
                                           request_id=response.request_id)
                        latest[field] = state[field]
                if current:
                    observed = "in-progress"
                signature = digest(latest)
                delay = (limits["interval_seconds"] if signature != previous
                         else min(60, delay * 2))
                previous = signature
            else:
                latest = {}
                observed = "stale-success-or-unrelated-cycle" if state else "no-completed-cycle"
                signature = digest({})
                delay = limits["interval_seconds"] if signature != previous else min(60, delay * 2)
                previous = signature
            if execution_guard is not None:
                latest["indexer_execution"] = copy.deepcopy(execution_guard)
            if first_response and require_new_cycle and last:
                initial_cycle = (last.get("startTime"), last.get("endTime"))
            first_response = False
            if (
                last and last.get("endTime") is not None
                and _timestamp(last.get("startTime")) >= max(not_before, newest_run or not_before)
                and (last.get("startTime"), last.get("endTime")) != initial_cycle
                and (excluded is None or (_timestamp(last.get("startTime")), _timestamp(last.get("endTime"))) != excluded)
            ):
                status = last.get("status")
                if status is not None and not isinstance(status, str):
                    raise _failure("ingestion-status-invalid", "Synchronization status must be a string when present.")
                if status in {"failure", "partialSuccess"}:
                    return failure_result(f"ingestion-{status}", response.request_id,
                                              request_ids, first_error, first_retry)
                if status in {None, "success"}:
                    start = _timestamp(last.get("startTime"))
                    end = _timestamp(last.get("endTime"))
                    failed = last.get("itemsUpdatesFailed")
                    processed = last.get("itemsUpdatesProcessed")
                    skipped = last.get("itemsSkipped")
                    if end < start or any(type(count) is not int or count < 0 for count in (failed, processed, skipped)):
                        raise _failure("ingestion-status-invalid", "Completed synchronization counters or interval are invalid.")
                    if failed or first_error:
                        return failure_result("ingestion-partialSuccess", response.request_id,
                                                  request_ids, first_error, first_retry)
                    if (not current and synchronization_status in ("active", "not-reported")
                            and (execution_guard is None
                                 or _execution_completed_by(execution_guard, end, not_before))):
                        return {
                            "status": "verified",
                            "progress": report("completed"),
                            "synchronization": {
                                field: last[field] for field in
                                ("startTime", "endTime", "itemsUpdatesProcessed", "itemsUpdatesFailed", "itemsSkipped")
                            },
                            "not_before": not_before.isoformat(),
                            "request_ids": request_ids,
                            "first_retry": first_retry,
                            "watch": {"schema_version": "1.0", "state": "completed",
                                      "elapsed_seconds": max(0, monotonic() - started),
                                      "status_checks": checks, "latest": latest},
                        }
                else:
                    raise _failure("ingestion-status-invalid", "Unknown synchronization completion status.")
            elif last and not current:
                observed = "stale-success-or-unrelated-cycle"
            if indexer_name and checks < limits["max_requests"] and monotonic() < deadline and not cancelled():
                target = (f"{source['endpoint'].rstrip('/')}/indexers('{search_reconcile._odata_name(indexer_name)}')/status?"
                          + urlencode({"api-version": source["api_version"]}))
                run_response = None
                try:
                    run_response = read_status(target)
                    cutoff = max(not_before, newest_run or not_before)
                    if execution_guard is not None:
                        cutoff = min(cutoff, _timestamp(execution_guard["startTime"]))
                    execution = _execution_progress(run_response.body, cutoff)
                    if (execution is not None and execution_guard is not None
                            and _timestamp(execution["startTime"]) < _timestamp(execution_guard["startTime"])):
                        execution = None
                    if execution is not None:
                        if execution_guard is not None or execution["run_status"] == "inProgress":
                            execution_guard = copy.deepcopy(execution)
                        execution_signature = digest(execution)
                        if execution_signature != previous_execution:
                            delay = limits["interval_seconds"]
                        previous_execution = execution_signature
                        latest["indexer_execution"] = execution
                        if (execution.get("items_failed", 0) or execution["error_count"]
                                or execution["run_status"] in {"transientFailure", "persistentFailure"}):
                            first_error = first_error or {
                                "status": None, "message": "Latest relevant indexer execution reports failures; details withheld.",
                                "request_id": run_response.request_id,
                            }
                except KeyboardInterrupt:
                    pause_reason = "cancelled"
                    break
                except HelperFailure as failure:
                    if failure.request_id is None and run_response is not None:
                        failure.request_id = run_response.request_id
                    if failure.request_id and failure.request_id not in request_ids:
                        request_ids.append(failure.request_id)
                    if failure.code == "response-deadline-exceeded":
                        first_retry = first_retry or {"code": failure.code, "status": failure.http_status,
                                                      "request_id": failure.request_id}
                        if monotonic() >= deadline:
                            pause_reason = "deadline"
                            break
                    if failure.code == "ingestion-watch-expired":
                        pause_reason = "deadline"
                        break
                    if (failure.http_status not in RETRY_STATUS
                            and failure.code not in {"azure-response-ambiguous", "response-deadline-exceeded"}):
                        code = failure.code if failure.code in {"indexer-status-invalid", "indexer-status-error"} else "indexer-status-unverified"
                        return failure_result(code, failure.request_id, request_ids,
                                                  first_error, first_retry, failure.http_status)
                    first_retry = first_retry or {"code": failure.code, "status": failure.http_status,
                                                  "request_id": failure.request_id}
                    throttled = failure.http_status == 429
                    if retry_after is None:
                        retry_after = _retry_after(failure.retry_after)
                    delay = min(60, delay * 2)
        remaining = deadline - monotonic()
        if cancelled():
            pause_reason = "cancelled"
            break
        if retry_after is not None and retry_after > min(60, remaining):
            report("throttled" if throttled else "waiting")
            pause_reason = "retry-after"
            break
        if remaining > 0 and checks < limits["max_requests"]:
            try:
                wait = min(max(delay, retry_after or 0), remaining)
                report("throttled" if throttled else
                       "ingesting" if observed == "in-progress" else "waiting", wait)
                sleep(wait)
            except KeyboardInterrupt:
                pause_reason = "cancelled"
                break
        if monotonic() >= deadline:
            pause_reason = "deadline"
    result = _readiness_failure(
        "ingestion-timeout", request_ids[-1] if request_ids else None,
        request_ids, first_error, first_retry,
    )
    result["observed"] = observed
    result["watch"] = {"schema_version": "1.0", "state": "paused", "reason": pause_reason,
                       "elapsed_seconds": max(0, monotonic() - started),
                       "status_checks": checks, "latest": latest,
                       "service_execution": "not-modified"}
    if first_error or latest.get("itemsUpdatesFailed"):
        result["code"] = "ingestion-partialSuccess"
    result["progress"] = report("failed" if result["code"] == "ingestion-partialSuccess" else "paused")
    result["safe_next_decision"] = (
        "Service reports item failures; retain the partial work and inspect exact private error evidence read-only. "
        "A new watch does not repair failures; do not replay writes or default to cleanup."
    ) if result["code"] == "ingestion-partialSuccess" else (
        "Client watch paused; this is not an ingestion failure. Resume GET-only with the unchanged input "
        "and readiness receipt using blob_recheck.py --input <original-input> --receipt <checkpoint>. "
        "Do not recreate, run/reset, delete, or infer corpus completion."
    )
    return result


def _readiness_failure(
    code: str, request_id: str | None, request_ids: list[str],
    first_error: dict[str, Any] | None, first_retry: dict[str, Any] | None,
    status: int | None = None,
) -> dict[str, Any]:
    return {
        "status": "unverified", "code": code, "request_id": request_id,
        "http_status": status, "request_ids": request_ids,
        "first_error": first_error, "first_retry": first_retry,
    }


@reporting("blob-source")
def execute(
    document: dict[str, Any],
    *,
    token_provider: TokenProvider = azure_cli_token,
    transport: Transport = http_request,
    storage_transport: Transport = http_request,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    checkpoint: Any = None,
    progress: Progress | None = None,
) -> dict[str, Any]:
    progress.update("validation")
    reject_secrets(document)
    require_allowed_fields(document, {"schema_version", "plan", "approval", "_computed_fingerprint"},
                           label="input envelope")
    plan = document.get("plan")
    approval = document.get("approval")
    if document.get("schema_version") != "1.0" or not isinstance(plan, dict) or not isinstance(approval, dict):
        raise _failure("input-schema-invalid", "A typed user-approved envelope is required.")
    require_allowed_fields(approval, {"confirmed", "fingerprint"}, label="approval")
    fingerprint = digest(plan)
    if approval.get("confirmed") is not True or approval.get("fingerprint") != fingerprint:
        raise _failure("approval-mismatch", "The exact recomputed plan fingerprint must be approved.")
    source, boundary = _validate_plan(plan)
    progress.update("blob-inventory")
    before = blob_inventory.discover(
        boundary, plan["inventory_limits"], token_provider=token_provider, transport=storage_transport,
    )
    if before["inventory_digest"] != plan["inventory_digest"]:
        raise _failure("source-drift", "Current source evidence differs from approval; reconfirmation is required.")
    not_before = now()
    generated: list[dict[str, Any]] = []
    write_generated: list[dict[str, Any]] = []
    initial_read = True
    creation_etag = None
    embedding_transport = source_vector.guard_readback_transport(plan, transport)

    def reconcile_transport(method: str, url: str, token: str, **kwargs: Any) -> Any:
        nonlocal initial_read
        first_read = method == "GET" and initial_read
        if first_read:
            initial_read = False
        kwargs.update(max_response_bytes=8 * 1024 * 1024, follow_redirects=False)
        try:
            response = embedding_transport(method, url, token, **kwargs)
        except HelperFailure as failure:
            if (
                first_read and failure.http_status == 404 and source["action"] == "create"
                and source.get("expected_etag") is not None
            ):
                raise _failure(
                    "definition-drift", "The source bound by the approved ETag is absent; rebuild the plan.",
                    request_id=failure.request_id,
                ) from failure
            raise
        if method == "GET" and response.status == 200 and isinstance(response.body, dict):
            etag = search_reconcile.resolve_etag(search_reconcile.response_etags(response), response.request_id)
            if etag is not None:
                response = HttpResult(response.status, {**response.body, "@odata.etag": etag},
                                      response.headers, response.etag_values)
            if creation_etag is not None and etag != creation_etag:
                raise _failure("definition-drift", "Source version differs from the acknowledged create response.",
                               request_id=response.request_id)
        if isinstance(response.body, dict):
            if method == "GET" and response.status == 200:
                parameters = response.body.get("azureBlobParameters")
                if isinstance(parameters, dict):
                    try:
                        _connection_binding(parameters.get("connectionString"), boundary)
                    except HelperFailure as failure:
                        failure.request_id = response.request_id
                        raise
            if first_read and response.status == 200:
                if plan.get("expected_source_absent"):
                    raise _failure("definition-drift", "A source appeared after planning; rebuild the plan.", request_id=response.request_id)
                if source.get("expected_etag") is not None and response.body.get("@odata.etag") != source["expected_etag"]:
                    raise _failure("definition-drift", "Source ETag differs from the approved readback.", request_id=response.request_id)
            if method == "GET" and response.status == 200 and (
                plan.get("expected_source_absent") or "expected_generated" in plan
            ):
                if not isinstance(response.body.get("@odata.etag"), str) or not response.body["@odata.etag"]:
                    raise _failure("definition-evidence-missing", "Source readback must include its ETag.", request_id=response.request_id)
                parameters = response.body.get("azureBlobParameters")
                connection = parameters.get("connectionString") if isinstance(parameters, dict) else None
                if isinstance(connection, str) and connection.startswith("ResourceId="):
                    if connection.removesuffix(";") != f"ResourceId={boundary['storage_id']}":
                        raise _failure("boundary-mismatch", "Readback targets a different Storage account.", request_id=response.request_id)
                elif plan.get("expected_source_absent") and (
                    not creation_etag or response.body.get("@odata.etag") != creation_etag
                ):
                    raise _failure("source-binding-unverified", "Redacted creation readback lacks a matching acknowledged PUT ETag.", request_id=response.request_id)
            generated.clear()
            generated.extend(generated_resources(response.body))
            if method == "GET" and "expected_generated" in plan and generated != plan["expected_generated"]:
                raise _failure("definition-drift", "Generated identities differ from the approved reuse plan.", request_id=response.request_id)
            if method == "PUT" and response.status in {200, 201}:
                write_generated[:] = generated
        return response

    def created(*, response, url, body, headers):
        nonlocal creation_etag
        if (source["action"] != "create" or url != search_reconcile.resource_url(source)
                or headers.get("If-None-Match") != "*" or "If-Match" in headers
                or body != canonical_bytes(source["desired"])):
            raise _failure("recheck-ownership-unproven", "Creation acknowledgement must bind the exact approved conditional wire.")
        if checkpoint is not None:
            checkpoint.acknowledge(plan, response, not_before, url=url, body=body, headers=headers)
        creation_etag = search_reconcile.resolve_etag(search_reconcile.response_etags(response), response.request_id)
        if creation_etag is None:
            raise _failure("creation-version-unproven", "Successful create returned no ETag in body or HTTP headers; a later GET cannot prove its version.",
                           request_id=response.request_id)

    progress.update("source-reconciliation")
    try:
        result = search_reconcile.execute(
            {"plan": source, "_computed_fingerprint": fingerprint},
            token_provider=token_provider, transport=reconcile_transport, on_created=created,
        )
    except HelperFailure as failure:
        if failure.writes:
            failure.resources_remaining.extend(write_generated or generated)
        elif failure.partial:
            failure.resources_reused.extend(generated)
        if checkpoint is not None and failure.writes:
            result = blocked_result(failure, outcome="create-blob-knowledge-source",
                                    fingerprint=fingerprint, owner=plan["owner"])
            result.update(readiness={"status": "unverified"}, knowledge_base="not-verified", retrieval="unverified")
            return _checkpoint_result(result, checkpoint)
        raise
    writes = [
        {"action": "created", "type": item["type"], "name": item["name"]}
        for item in result["resources"]["created"]
    ]
    readiness: dict[str, Any] = {"status": "unverified"}
    after = None
    owned_generated = list(generated or write_generated) if writes else []
    try:
        expected_generated = list(generated)
        if checkpoint is not None:
            if source["action"] == "create" and (
                not creation_etag or creation_etag != result["verification"]["readback"]["etag"]
                or write_generated and generated != write_generated
            ):
                raise _failure("recheck-ownership-unproven", "Checkpoint requires an acknowledged PUT ETag and unchanged generated identities.")
            checkpoint.persist(plan, result, generated, not_before,
                               token_provider=token_provider, transport=transport)
        readiness = monitor(
            source, not_before=not_before, limits=plan["poll"], token_provider=token_provider,
            transport=transport, require_new_cycle=not bool(writes) and checkpoint is None,
            excluded_cycle=checkpoint.excluded_cycle if checkpoint is not None else None,
            monotonic=monotonic, sleep=sleep,
            progress=progress,
            indexer_name=next((item["name"] for item in generated if item["type"] == "indexer"), None),
        )
        if readiness["status"] != "verified":
            raise HelperFailure(
                readiness["code"], "Source reconciliation completed but ingestion readiness is unverified.",
                blocked_at="verification", request_id=readiness["request_id"],
                status=readiness["http_status"],
            )
        progress.update("blob-readback")
        after = blob_inventory.discover(
            boundary, plan["inventory_limits"], token_provider=token_provider, transport=storage_transport,
        )
        if after["inventory_digest"] != before["inventory_digest"]:
            raise _failure("source-drift", "Source changed during ingestion; reconfirmation is required.")
        progress.update("source-readback")
        current, request_id = search_reconcile._get(
            search_reconcile._resource_url(source), token_provider(SEARCH_AUDIENCE), transport=reconcile_transport,
        )
        if (
            current is None
            or search_reconcile._definition(current) != search_reconcile._definition(source["desired"])
            or current.get("@odata.etag") != result["verification"]["readback"]["etag"]
            or generated != expected_generated
        ):
            raise _failure("definition-drift", "Source definition or ETag changed while monitoring.", request_id=request_id)
        if request_id:
            result["verification"]["request_ids"].append(request_id)
        if len(generated) != 4 or {item["type"] for item in generated} != {"datasource", "indexer", "skillset", "index"}:
            raise _failure("generated-resources-unverified", "Exact service-generated resource identities could not be read back.")
        if checkpoint is not None:
            checkpoint.verify(plan, token_provider=token_provider, transport=transport)
    except HelperFailure as failure:
        confirmed = copy.deepcopy(result)
        result = blocked_result(
            HelperFailure(
                failure.code, failure.message, blocked_at=failure.blocked_at, writes=writes,
                resources_remaining=result["ownership"]["run_owned"] + owned_generated,
                request_id=failure.request_id, status=failure.http_status, partial=bool(writes),
            ),
            outcome="create-blob-knowledge-source", fingerprint=fingerprint, owner=plan["owner"],
        )
        result["reconciliation"] = "completed"
        result["writes_performed"] = writes
        result["read_only_evidence"] = {
            "inventory_request_ids": before["request_ids"] + (after["request_ids"] if after else []),
            "configuration_request_ids": checkpoint.request_ids if checkpoint is not None else [],
        }
        result["confirmed_reconciliation"] = {
            key: confirmed[key] for key in ("resources", "verification", "ownership")
        }
        result["readiness"] = {**readiness, "status": "unverified"}
        if readiness.get("watch", {}).get("state") == "paused":
            result["safe_next_decision"] = readiness["safe_next_decision"]
        if not writes:
            result["ownership"]["reused_not_owned"] = [
                {"type": "knowledge-source", "name": source["name"]}, *generated
            ]
    else:
        result["outcome"] = "create-blob-knowledge-source"
        result["readiness"] = readiness
        result["verification"]["source_digest"] = after["inventory_digest"]
    result["source"] = {
        "type": "knowledge-source", "name": source["name"],
        "generated": owned_generated if writes else generated,
        "observed_generated": generated,
    }
    result["writes_performed"] = writes
    result["source_evidence"] = {
        "inventory_digest": before["inventory_digest"], "boundary": boundary,
        "operator_reachability": "verified", "managed_ingestion_reachability": result["readiness"]["status"],
    }
    result.setdefault("warnings", []).append(SNAPSHOT_WARNING)
    return _checkpoint_result(result, checkpoint)


def _checkpoint_result(result, checkpoint):
    if "completed_writes" in result:
        result["writes_performed"] = copy.deepcopy(result["completed_writes"])
    if checkpoint is not None:
        result["warnings"].extend(checkpoint.recovery_warnings)
        result["creation_acknowledgement"] = checkpoint.write_observation or {
            "schema_version": "1.0", "state": "unavailable",
        }
        result["indexer_diagnostics"] = [
            item for item in checkpoint.diagnostics
            if not item["field"].startswith(("datasource.", "indexer.", "skillset.", "index."))
        ]
        result["generated_diagnostics"] = checkpoint.diagnostics
        result["indexer_observations"] = checkpoint.observations
        result["datasource_binding_observations"] = checkpoint.binding_observations
        for item in checkpoint.diagnostics:
            if item["severity"] == "warning" and item["message"] not in result.setdefault("warnings", []):
                result["warnings"].append(item["message"])
        result["recheck_checkpoint"] = checkpoint.summary or {"status": "unavailable"}
        result["recheck_write_acknowledgement"] = checkpoint.write_acknowledgement or {"status": "unavailable"}
        result["recheck_acknowledgement"] = checkpoint.acknowledgement or checkpoint.write_acknowledgement or {"status": "unavailable"}
        if checkpoint.summary is None:
            result["safe_next_decision"] = "Preserve the first failure and resources. Use blob_recheck.py --recover with unchanged approved input and the retained acknowledgement, then --input/--receipt. Missing/conflicting write ETags or absent private evidence remain blockers; never borrow a GET version, replay creation or default to cleanup."
        try:
            checkpoint.finish(result)
        except HelperFailure as failure:
            if result["status"] == "completed":
                original = result
                result = blocked_result(
                    HelperFailure(failure.code, failure.message, blocked_at="evidence-retention",
                                  writes=original["writes_performed"],
                                  resources_remaining=original["ownership"]["run_owned"],
                                  partial=bool(original["writes_performed"])),
                    outcome=original["outcome"], fingerprint=checkpoint.plan_digest,
                )
                result["confirmed_reconciliation"] = original
                result["writes_performed"] = original["writes_performed"]
            result["result_evidence"] = {"status": "unavailable", "code": failure.code}
            result.setdefault("warnings", []).append("Final private evidence retention failed; preserve the native result and first failure. No retry was performed.")
    return result


def main(argv: list[str] | None = None) -> int:
    try:
        from .private_artifacts import add_execution_output_argument, emit_plan_result, validate_execution_output_mode
    except ImportError:
        from private_artifacts import add_execution_output_argument, emit_plan_result, validate_execution_output_mode
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--discover", type=Path)
    modes.add_argument("--plan", type=Path)
    add_execution_output_argument(parser)
    modes.add_argument("--input", type=Path)
    parser.add_argument("--receipt-dir", type=Path)
    parser.add_argument("--compact", action="store_true")
    add_progress_argument(parser)
    args = parser.parse_args(argv)
    if args.compact and (not args.input or not args.receipt_dir):
        parser.error("--compact requires --input and --receipt-dir to retain full private evidence.")
    fingerprint = None
    owner = None
    progress = Progress("blob-source", enabled=args.progress) if args.input else None
    execution_started = False
    try:
        validate_execution_output_mode(args)
        if progress is not None:
            progress.update("validation")
        if args.receipt_dir and not args.input:
            raise _failure("input-schema-invalid", "--receipt-dir requires --input; read-only reuse capture uses blob_recheck.py.")
        if args.plan:
            result = plan_source(_read_intent(args.plan))
            emit_plan_result(result, args.execution_output, preserve_unapproved_input=result["status"] == "planned")
            return 0 if result["status"] == "planned" else 2
        elif args.discover:
            try:
                document = json.loads(args.discover.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise _failure("input-unreadable", "Discovery input must be readable UTF-8 JSON.") from exc
            if not isinstance(document, dict):
                raise _failure("input-schema-invalid", "Discovery input must be an object.")
            reject_secrets(document)
            require_allowed_fields(document, {"boundary", "inventory_limits"}, label="discovery input")
            result = blob_inventory.discover(document.get("boundary"), document.get("inventory_limits"))
        else:
            document, plan, fingerprint = load_approved_input(args.input)
            owner = plan.get("owner")
            checkpoint = None
            if args.receipt_dir:
                try:
                    from . import blob_recheck
                except ImportError:
                    import blob_recheck
                checkpoint = blob_recheck.Checkpoint(args.receipt_dir, plan)
            execution_started = True
            if checkpoint is not None:
                result = execute(document, checkpoint=checkpoint, progress=progress)
            else:
                result = execute(document, progress=progress)
    except HelperFailure as failure:
        if progress is not None and not execution_started:
            progress.finish(failure=failure)
        result = blocked_result(failure, outcome="blob-source-lifecycle", fingerprint=fingerprint, owner=owner)
        if failure.partial and not failure.writes:
            result["safe_next_decision"] = "Original create outcome is unproven. Preserve the mutation error and inspect observed resources read-only; no creation ownership, write replay or cleanup is authorized."
    if args.compact:
        try:
            try:
                from . import blob_recheck
            except ImportError:
                import blob_recheck
            result = blob_recheck.compact_result(result, args.receipt_dir)
        except HelperFailure as failure:
            result.setdefault("warnings", []).append("compact-evidence-persistence-failed: full native result retained in output.")
            result["presentation_failure"] = {"code": failure.code}
            emit_result(result)
            return 3 if result["status"] == "partial" else 2
    emit_result(result, preserve_unapproved_input=result["status"] == "planned")
    return {"completed": 0, "discovered": 0, "planned": 0, "blocked": 2, "partial": 3}[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
