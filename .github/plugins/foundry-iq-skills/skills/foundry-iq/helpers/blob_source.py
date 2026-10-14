from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from ._progress import Progress, add_progress_argument, reporting
    from . import (
        blob_inventory, search_reconcile, cu_ingestion_auth, _blob_source_read, _embedding, _search_read,
        _source_readback,
    )
    from ._common import (
        SEARCH_AUDIENCE, HelperFailure, TokenProvider, Transport, azure_cli_token, blocked_result,
        canonical_bytes, digest, emit_result, http_request, load_approved_input, HttpResult, reject_secrets,
        require_allowed_fields, model_definition,
    )
except ImportError:
    from _progress import Progress, add_progress_argument, reporting
    import blob_inventory
    import search_reconcile
    import cu_ingestion_auth
    import _blob_source_read
    import _embedding
    import _search_read
    import _source_readback
    from _common import (
        SEARCH_AUDIENCE, HelperFailure, TokenProvider, Transport, azure_cli_token, blocked_result,
        canonical_bytes, digest, emit_result, http_request, load_approved_input, HttpResult, reject_secrets,
        require_allowed_fields, model_definition,
    )


def plan_source(
    request: dict[str, Any], *,
    token_provider: TokenProvider = azure_cli_token, transport: Transport = http_request,
    storage_transport: Transport = http_request, monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise _blob_source_read._failure("input-schema-invalid", "Planning input must be an object.")
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
        raise _blob_source_read._failure("input-schema-invalid", "Planning choices must be valid UTF-8 JSON.") from exc
    if request.get("schema_version") != "1.0" or not isinstance(request.get("owner"), str) or not request["owner"].strip():
        raise _blob_source_read._failure("input-schema-invalid", "schema_version 1.0 and an explicit owner are required.")
    boundary = blob_inventory.validate_boundary({
        field: request.get(field) for field in ("storage_id", "container", "prefix", "is_adls")
    })
    limits = copy.deepcopy(blob_inventory.validate_limits(request.get("inventory_limits")))
    poll = copy.deepcopy(_blob_source_read._poll_limits(request.get("poll")))
    if (
        request.get("processing") not in ("minimal-lexical", "minimal-vector", "standard-cu") or request.get("network_access") != "public"
        or request.get("identity") != "system-assigned" or request.get("permission_options") != []
        or "ingestion_schedule" not in request or request["ingestion_schedule"] is not None
        or not isinstance(request.get("api_version"), str)
        or request["api_version"] not in {"2026-04-01", "2026-08-01-preview"}
        or boundary["is_adls"] and request["api_version"] != "2026-08-01-preview"
    ):
        raise _blob_source_read._failure(
            "planning-processing-unsupported",
            "This planner supports Blob 2026-04-01/2026-08-01-preview and ADLS 2026-08-01-preview: "
            "Internal presets: minimal-lexical = minimal extraction without vectors; "
            "minimal-vector = minimal extraction with embeddings; standard-cu = standard CU with optional embeddings. "
            "These are not API enums or KB reasoning modes. Requires public, system-assigned, no permissions/schedule. "
            "Other requested versions/features need a compatible owner; never change them silently.",
        )
    embedding = _embedding.validate_choice(
        request.get("embedding"), enabled=(
            request["processing"] == "minimal-vector"
            or request["processing"] == "standard-cu" and request.get("embedding") is not None
        ),
        api_version=request["api_version"],
    )
    cu = _blob_source_read.validate_content_understanding(
        request.get("content_understanding"), enabled=request["processing"] == "standard-cu",
    )
    if "description" not in request or not (
        request["description"] is None or isinstance(request["description"], str)
    ):
        raise _blob_source_read._failure("input-schema-invalid", "description must be explicit text or null.")
    rbac, network = request.get("rbac"), request.get("network")
    if (
        not isinstance(rbac, dict) or not isinstance(rbac.get("assignments"), list)
        or not rbac["assignments"] or not all(isinstance(item, dict) and item for item in rbac["assignments"])
        or not isinstance(network, dict) or network.get("posture") != "public"
        or not isinstance(network.get("evidence"), str) or not network["evidence"].strip()
    ):
        raise _blob_source_read._failure("planning-evidence-missing", "Supply observed RBAC assignments and public network evidence; the owner verifies effective access and policy.")
    ingestion = {
        "contentExtractionMode": "minimal", "disableImageVerbalization": True,
        "identity": None, "ingestionSchedule": None,
    }
    if request["api_version"].endswith("-preview"):
        ingestion.update(networkAccessMode="public", ingestionPermissionOptions=[])
    if embedding is not None:
        ingestion["embeddingModel"] = model_definition(embedding)
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
    url = _search_read.resource_url(source)
    receipt_paths = _blob_source_read._receipt_paths(request)
    receipts = None

    def load_receipts() -> tuple[dict[str, Any], dict[str, Any]] | None:
        nonlocal receipts
        if receipts is None:
            receipts = _blob_source_read._reuse_receipts(receipt_paths)
        return receipts

    deadline = monotonic() + limits["deadline_seconds"]

    def read_search() -> tuple[dict[str, Any] | None, str | None]:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise _blob_source_read._failure("planning-deadline-exceeded", "Planning read deadline elapsed.")

        def bounded(method: str, target: str, token: str, **kwargs: Any) -> Any:
            if method != "GET" or target != url:
                raise _blob_source_read._failure("planning-write-forbidden", "Planning reads only the exact Search source.")
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise _blob_source_read._failure("planning-deadline-exceeded", "Planning read deadline elapsed during authentication.")
            return transport(
                method, target, token, timeout=min(30, remaining), follow_redirects=False,
                max_response_bytes=8 * 1024 * 1024, response_deadline=time.monotonic() + remaining,
            )

        current, request_id = _search_read.read_resource(url, token_provider(SEARCH_AUDIENCE), transport=bounded)
        try:
            _embedding.verify_source_readback(embedding, current)
            _blob_source_read.verify_content_understanding_readback(cu, current)
        except HelperFailure as failure:
            failure.request_id = request_id
            raise
        return current, request_id

    current, first_id = read_search()
    generated = []
    if current is not None:
        if not _search_read.definitions_match(source["desired"], current):
            raise _blob_source_read._failure("definition-conflict", "The exact source has a different definition; do not overwrite, suffix or repair it.")
        if not isinstance(current.get("@odata.etag"), str) or not current["@odata.etag"]:
            raise _blob_source_read._failure("definition-evidence-missing", "Exact reuse requires the current source ETag.")
        generated = _blob_source_read.generated_resources(current, strict=True)
        _blob_source_read._verify_storage_binding(source, boundary, current, generated, load_receipts)
    snapshot = blob_inventory.discover(
        boundary, limits, token_provider=token_provider, transport=storage_transport,
        monotonic=monotonic, deadline=deadline,
    )
    refreshed, last_id = read_search()
    if (current is None) != (refreshed is None) or current is not None and (
        refreshed.get("@odata.etag") != current["@odata.etag"]
        or not _search_read.definitions_match(source["desired"], refreshed)
        or _blob_source_read.generated_resources(refreshed, strict=True) != generated
    ):
        raise _blob_source_read._failure("definition-drift", "Source identity/ETag or generated resources changed during Storage observation.")
    if refreshed is not None:
        _blob_source_read._verify_storage_binding(source, boundary, refreshed, generated, load_receipts)
        source.update(action="reuse", expected_etag=refreshed["@odata.etag"])
    if monotonic() >= deadline:
        raise _blob_source_read._failure("planning-deadline-exceeded", "Planning read deadline elapsed during Search readback.")
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
    _blob_source_read._validate_plan(plan)
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
            **({"embedding": _embedding.summary(embedding)} if embedding else {}),
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
        "writes_performed": [], "warnings": [_blob_source_read.SNAPSHOT_WARNING],
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
        raise _blob_source_read._failure("input-schema-invalid", "A typed user-approved envelope is required.")
    require_allowed_fields(approval, {"confirmed", "fingerprint"}, label="approval")
    fingerprint = digest(plan)
    if approval.get("confirmed") is not True or approval.get("fingerprint") != fingerprint:
        raise _blob_source_read._failure("approval-mismatch", "The exact recomputed plan fingerprint must be approved.")
    source, boundary = _blob_source_read._validate_plan(plan)
    progress.update("blob-inventory")
    before = blob_inventory.discover(
        boundary, plan["inventory_limits"], token_provider=token_provider, transport=storage_transport,
    )
    if before["inventory_digest"] != plan["inventory_digest"]:
        raise _blob_source_read._failure("source-drift", "Current source evidence differs from approval; reconfirmation is required.")
    not_before = now()
    generated: list[dict[str, Any]] = []
    write_generated: list[dict[str, Any]] = []
    initial_read = True
    creation_etag = None
    embedding_transport = _source_readback.guard_readback_transport(plan, transport)

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
                raise _blob_source_read._failure(
                    "definition-drift", "The source bound by the approved ETag is absent; rebuild the plan.",
                    request_id=failure.request_id,
                ) from failure
            raise
        if method == "GET" and response.status == 200 and isinstance(response.body, dict):
            etag = _search_read.resolve_etag(_search_read.response_etags(response), response.request_id)
            if etag is not None:
                response = HttpResult(response.status, {**response.body, "@odata.etag": etag},
                                      response.headers, response.etag_values)
            if creation_etag is not None and etag != creation_etag:
                raise _blob_source_read._failure("definition-drift", "Source version differs from the acknowledged create response.",
                               request_id=response.request_id)
        if isinstance(response.body, dict):
            if method == "GET" and response.status == 200:
                parameters = response.body.get("azureBlobParameters")
                if isinstance(parameters, dict):
                    try:
                        _blob_source_read._connection_binding(parameters.get("connectionString"), boundary)
                    except HelperFailure as failure:
                        failure.request_id = response.request_id
                        raise
            if first_read and response.status == 200:
                if plan.get("expected_source_absent"):
                    raise _blob_source_read._failure("definition-drift", "A source appeared after planning; rebuild the plan.", request_id=response.request_id)
                if source.get("expected_etag") is not None and response.body.get("@odata.etag") != source["expected_etag"]:
                    raise _blob_source_read._failure("definition-drift", "Source ETag differs from the approved readback.", request_id=response.request_id)
            if method == "GET" and response.status == 200 and (
                plan.get("expected_source_absent") or "expected_generated" in plan
            ):
                if not isinstance(response.body.get("@odata.etag"), str) or not response.body["@odata.etag"]:
                    raise _blob_source_read._failure("definition-evidence-missing", "Source readback must include its ETag.", request_id=response.request_id)
                parameters = response.body.get("azureBlobParameters")
                connection = parameters.get("connectionString") if isinstance(parameters, dict) else None
                if isinstance(connection, str) and connection.startswith("ResourceId="):
                    if connection.removesuffix(";") != f"ResourceId={boundary['storage_id']}":
                        raise _blob_source_read._failure("boundary-mismatch", "Readback targets a different Storage account.", request_id=response.request_id)
                elif plan.get("expected_source_absent") and (
                    not creation_etag or response.body.get("@odata.etag") != creation_etag
                ):
                    raise _blob_source_read._failure("source-binding-unverified", "Redacted creation readback lacks a matching acknowledged PUT ETag.", request_id=response.request_id)
            generated.clear()
            generated.extend(_blob_source_read.generated_resources(response.body))
            if method == "GET" and "expected_generated" in plan and generated != plan["expected_generated"]:
                raise _blob_source_read._failure("definition-drift", "Generated identities differ from the approved reuse plan.", request_id=response.request_id)
            if method == "PUT" and response.status in {200, 201}:
                write_generated[:] = generated
        return response

    def created(*, response, url, body, headers):
        nonlocal creation_etag
        if (source["action"] != "create" or url != _search_read.resource_url(source)
                or headers.get("If-None-Match") != "*" or "If-Match" in headers
                or body != canonical_bytes(source["desired"])):
            raise _blob_source_read._failure("recheck-ownership-unproven", "Creation acknowledgement must bind the exact approved conditional wire.")
        if checkpoint is not None:
            checkpoint.acknowledge(plan, response, not_before, url=url, body=body, headers=headers)
        creation_etag = _search_read.resolve_etag(_search_read.response_etags(response), response.request_id)
        if creation_etag is None:
            raise _blob_source_read._failure("creation-version-unproven", "Successful create returned no ETag in body or HTTP headers; a later GET cannot prove its version.",
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
                raise _blob_source_read._failure("recheck-ownership-unproven", "Checkpoint requires an acknowledged PUT ETag and unchanged generated identities.")
            checkpoint.persist(plan, result, generated, not_before,
                               token_provider=token_provider, transport=transport)
        readiness = _blob_source_read.monitor(
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
            raise _blob_source_read._failure("source-drift", "Source changed during ingestion; reconfirmation is required.")
        progress.update("source-readback")
        current, request_id = _search_read._get(
            _search_read._resource_url(source), token_provider(SEARCH_AUDIENCE), transport=reconcile_transport,
        )
        if (
            current is None
            or _search_read._definition(current) != _search_read._definition(source["desired"])
            or current.get("@odata.etag") != result["verification"]["readback"]["etag"]
            or generated != expected_generated
        ):
            raise _blob_source_read._failure("definition-drift", "Source definition or ETag changed while monitoring.", request_id=request_id)
        if request_id:
            result["verification"]["request_ids"].append(request_id)
        if len(generated) != 4 or {item["type"] for item in generated} != {"datasource", "indexer", "skillset", "index"}:
            raise _blob_source_read._failure("generated-resources-unverified", "Exact service-generated resource identities could not be read back.")
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
    result.setdefault("warnings", []).append(_blob_source_read.SNAPSHOT_WARNING)
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
            raise _blob_source_read._failure("input-schema-invalid", "--receipt-dir requires --input; read-only reuse capture uses blob_recheck.py.")
        if args.plan:
            result = plan_source(_blob_source_read._read_intent(args.plan))
            emit_plan_result(result, args.execution_output, preserve_unapproved_input=result["status"] == "planned")
            return 0 if result["status"] == "planned" else 2
        elif args.discover:
            try:
                document = json.loads(args.discover.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise _blob_source_read._failure("input-unreadable", "Discovery input must be readable UTF-8 JSON.") from exc
            if not isinstance(document, dict):
                raise _blob_source_read._failure("input-schema-invalid", "Discovery input must be an object.")
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
