from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

try:
    from ._progress import Progress, add_progress_argument, reporting
    from . import (
        file_ingest, search_reconcile, file_cu_mi, cu_ingestion_auth as file_cu_auth, _embedding,
        _file_inventory, _file_source_config, _search_read, _source_readback,
    )
    from ._common import (
        SEARCH_AUDIENCE, HelperFailure, TokenProvider, Transport, azure_cli_token, blocked_result, digest,
        emit_result, http_request, load_approved_input, reject_secrets, require_allowed_fields,
        model_definition,
    )
except ImportError:
    from _progress import Progress, add_progress_argument, reporting
    import file_ingest
    import search_reconcile
    import file_cu_mi
    import cu_ingestion_auth as file_cu_auth
    import _embedding
    import _file_inventory
    import _file_source_config
    import _search_read
    import _source_readback
    from _common import (
        SEARCH_AUDIENCE, HelperFailure, TokenProvider, Transport, azure_cli_token, blocked_result, digest,
        emit_result, http_request, load_approved_input, reject_secrets, require_allowed_fields,
        model_definition,
    )


# File's approved key may be redacted in GET. It is not embedding auth,
    # and source readback cannot prove its value or CU processing readiness.


def plan_source(
    request: dict[str, Any],
    *,
    token_provider: TokenProvider = azure_cli_token,
    transport: Transport = http_request,
    context_provider=file_cu_auth.account_context,
) -> dict[str, Any]:
    """Build an unapproved File workflow using only local reads and GETs."""
    if not isinstance(request, dict):
        raise HelperFailure(
            "input-schema-invalid", "Planning input must be an object.",
            blocked_at="input-resolution",
        )
    reject_secrets(request)
    require_allowed_fields(
        request,
        {"schema_version", "api_version", "endpoint", "name", "owner", "local_root", "paths",
         "service_tier", "extraction_mode", "vectorization", "embedding", "rbac", "network",
         "content_understanding", "reuse_input_file", "reuse_result_file"},
        label="File planning input",
    )
    if request.get("schema_version") != "1.0":
        raise HelperFailure(
            "input-schema-invalid", "Planning requires schema_version 1.0.",
            blocked_at="input-resolution",
        )
    _file_inventory.validate_api_version(request.get("api_version", _file_inventory.API_VERSION))
    for field in ("name", "owner"):
        if not isinstance(request.get(field), str) or not request[field].strip():
            raise HelperFailure(
                "input-schema-invalid", f"An explicit non-empty {field} is required.",
                blocked_at="input-resolution",
            )
    if request.get("extraction_mode") not in ("minimal", "standard") or request.get("vectorization") not in ("none", "azureOpenAI"):
        raise HelperFailure(
            "planning-processing-unsupported",
            "Select minimal or standard extraction and independent vectorization none or azureOpenAI.",
            blocked_at="input-resolution",
        )
    embedding = _embedding.validate_choice(
        request.get("embedding"), enabled=request["vectorization"] == "azureOpenAI",
        api_version=_file_inventory.API_VERSION,
    )
    cu = _file_source_config.validate_content_understanding(
        request.get("content_understanding"), enabled=request["extraction_mode"] == "standard",
    )
    if (request.get("reuse_input_file") is not None or request.get("reuse_result_file") is not None) and (
        cu is None or cu["auth"] != "system-assigned"
    ):
        raise _file_source_config._cu_failure("cu-choice-conflict", "File MI provenance inputs are only for managed-identity exact reuse.")
    rbac, network = request.get("rbac"), request.get("network")
    if (
        not isinstance(rbac, dict)
        or not isinstance(rbac.get("assignments"), list)
        or not rbac["assignments"]
        or not all(isinstance(item, dict) and item for item in rbac["assignments"])
        or not isinstance(network, dict)
        or not isinstance(network.get("posture"), str)
        or not network["posture"].strip()
        or not isinstance(network.get("evidence"), str)
        or not network["evidence"].strip()
    ):
        raise HelperFailure(
            "planning-evidence-missing",
            "Supply observed RBAC assignments and network posture/evidence; the policy owner must refresh and verify them before approval.",
            blocked_at="input-resolution",
        )
    root = _file_inventory.resolve_local_root(request.get("local_root"))
    records = _file_inventory.snapshot_inventory(
        root, request.get("paths"), service_tier=request.get("service_tier")
    )
    common = {
        "endpoint": request.get("endpoint"), "name": request.get("name"),
        "api_version": _file_inventory.API_VERSION, "owner": request.get("owner"),
        "cleanup_approved": False, "rbac": copy.deepcopy(rbac),
        "network": copy.deepcopy(network),
    }
    source = {
        **common, "operation": "reconcile", "resource_type": "knowledge-source",
        "outcome": "create-file-knowledge-source", "action": "create",
        "desired": {
            "name": common["name"], "kind": "file",
            "fileParameters": {"ingestionParameters": {"contentExtractionMode": request["extraction_mode"]}},
        },
    }
    ingestion = {
        **copy.deepcopy(common), "operation": "ingest", "local_root": str(root),
        "files": records, "inventory_digest": digest(records),
        "expected_server_inventory_digest": _file_inventory.inventory_digest([]),
        "service_tier": request["service_tier"], "extraction_mode": request["extraction_mode"],
    }
    plan = {
        "operation": "reconcile-and-ingest", "outcome": "create-file-knowledge-source",
        "owner": common["owner"], "cleanup_approved": False,
        "source": source, "ingestion": ingestion,
    }
    if embedding is not None:
        plan["embedding"] = embedding
        source["desired"]["fileParameters"]["ingestionParameters"]["embeddingModel"] = model_definition(embedding)
    if cu is not None:
        automatic = cu["auth"] == "api-key-arm"
        mi = cu["auth"] == "system-assigned"
        plan.update(file_cu_plan_version="1.2" if mi else "1.1" if automatic else "1.0", content_understanding=cu)
        if automatic:
            source["ai_services_key_acquisition"] = file_cu_auth.acquisition(cu, context_provider())
        elif mi:
            source["ai_services_managed_identity"] = True
        else:
            source["ai_services_api_key_environment"] = cu["api_key_environment"]
        source["desired"]["fileParameters"]["ingestionParameters"].update(
            aiServices={"uri": cu["endpoint"].rstrip("/")}, disableImageVerbalization=True,
        )
    # Validate the local inventory and all choices before any authentication.
    _file_source_config._validate_plan(plan, require_cu_readback=False)
    cu_request_ids = []
    if cu is not None:
        state, cu_request_ids = _file_source_config.read_content_understanding(cu, token_provider=token_provider, transport=transport)
        plan["cu_resource_state"] = state
        if cu["auth"] == "system-assigned":
            plan["cu_identity_state"], ids = file_cu_mi.read_binding(
                cu, common["endpoint"], token_provider=token_provider, transport=transport,
            )
            cu_request_ids.extend(ids)
    _file_source_config._validate_plan(plan)
    transport = _source_readback.guard_readback_transport(plan, transport)
    url = _search_read.resource_url(source)
    token = token_provider(SEARCH_AUDIENCE)
    current, request_id = _search_read.read_resource(url, token, transport=transport)
    request_ids = cu_request_ids + ([request_id] if request_id else [])
    matched = {}
    if current is not None:
        if cu is not None and cu["auth"] == "system-assigned":
            _file_source_config.verify_reuse(request, plan, current)
        if not _search_read.definitions_match(source["desired"], current):
            raise HelperFailure(
                "definition-conflict",
                "The exact source has a different definition; planning never overwrites or chooses another name.",
                blocked_at="reconciliation",
            )
        etag = current.get("@odata.etag")
        if not isinstance(etag, str) or not etag:
            raise HelperFailure(
                "definition-evidence-missing", "Exact reuse requires the current source ETag.",
                blocked_at="reconciliation",
            )
        before, ids = _file_inventory.read_inventory(ingestion, token, transport=transport)
        request_ids.extend(ids)
        matched = _file_inventory.reconcile_inventory(ingestion, before)
        file_ids = [item.get("fileId") for item in matched.values()]
        if (
            not all(isinstance(value, str) and value for value in file_ids)
            or len(set(file_ids)) != len(file_ids)
        ):
            raise HelperFailure(
                "file-identity-ambiguous", "Exact reuse requires unique non-empty server file IDs.",
                blocked_at="reconciliation",
            )
        source.update(action="reuse", expected_etag=etag)
        ingestion["expected_server_inventory_digest"] = _file_inventory.inventory_digest(before)
        refreshed, refresh_id = _search_read.read_resource(url, token, transport=transport)
        if refresh_id:
            request_ids.append(refresh_id)
        if (
            refreshed is None
            or refreshed.get("@odata.etag") != etag
            or not _search_read.definitions_match(source["desired"], refreshed)
        ):
            raise HelperFailure(
                "definition-drift",
                "Source definition or ETag changed during file inventory readback.",
                blocked_at="reconciliation",
            )
    # Do not return a snapshot that changed while Search discovery was running.
    _file_source_config._validate_plan(plan)
    if cu is not None:
        state, ids = _file_source_config.read_content_understanding(cu, token_provider=token_provider, transport=transport)
        request_ids.extend(ids)
        if not _file_source_config._cu_states_match(state, plan["cu_resource_state"]):
            raise _file_source_config._cu_failure(
                "cu-prerequisite-drift", "CU account access or configuration changed during planning; refresh the plan.",
                request_id=ids[-1] if ids else None,
            )
        if cu["auth"] == "api-key-arm":
            file_cu_auth.check_context(source["ai_services_key_acquisition"]["context"], context_provider)
        elif cu["auth"] == "system-assigned":
            binding, ids = file_cu_mi.read_binding(cu, common["endpoint"], token_provider=token_provider, transport=transport)
            request_ids.extend(ids)
            if binding != plan["cu_identity_state"]:
                raise _file_source_config._cu_failure("cu-mi-identity-drift", "Search identity, CU scoped role or network changed during planning.")
    fingerprint = digest(plan)
    mutation_required = source["action"] == "create"
    return {
        "status": "planned", "outcome": plan["outcome"],
        "plan_fingerprint": fingerprint,
        "execution_input": {
            "schema_version": "1.0", "plan": plan,
            "approval": {"confirmed": False, "fingerprint": fingerprint},
        },
        "approval_summary": {
            "target": {"endpoint": common["endpoint"], "name": common["name"],
                       "api_version": common["api_version"], "preview": True},
            "source_action": source["action"], "owner": common["owner"],
            "execution_required": mutation_required,
            "mutation_approval_required": mutation_required,
            "processing": (
                "standard CU extraction" + (" with source embeddings" if embedding else "; source vectors off")
                if cu else "minimal extraction with embeddings" if embedding else "minimal lexical; no models"
            ),
            **({"content_understanding": {
                "purpose": "Standard document extraction only; not source vectorization or KB answer synthesis.",
                "endpoint": cu["endpoint"],
                "authentication": file_cu_auth.approval_summary("file", cu["auth"], creating=mutation_required),
                "auth": (
                    "Search system-assigned MI for CU; no API key or credential reads, no local-auth requirement. Service implementation inspected; live compatibility unverified."
                    if cu["auth"] == "system-assigned" else
                    "Existing File CU key-auth configuration reused; no credential acquisition. Search remains keyless."
                    if not mutation_required else
                    "Approved private ARM listKeys acquisition of key1 for this source PUT only; Search remains keyless. Local authentication means key auth, not manual local setup."
                    if cu["auth"] == "api-key-arm" else "Explicit existing CU API-key ENV channel; Search remains keyless."
                ),
                **({"credential_acquisition": copy.deepcopy(source["ai_services_key_acquisition"])} if cu["auth"] == "api-key-arm" and mutation_required else {}),
                **({"managed_identity": copy.deepcopy(plan["cu_identity_state"])} if cu["auth"] == "system-assigned" else {}),
                "cost_and_data": "Billable CU processing, no daily free document allowance; uploaded content moves from Search to CU, possibly across regions. Search retains outputs.",
                "verification": (
                    "ARM verifies Search identity, exact CU-scoped role and account/network metadata, not backend MI rollout, effective access or extraction. A separately approved bounded OCR canary can validate functionality."
                    if cu["auth"] == "system-assigned" else
                    "ARM verifies account binding/local-auth/network metadata, not effective access, key validity or processing success. Verify selected processing/required deployment evidence; no blanket account-defaults confirmation."
                ),
                "kb_reasoning": "Unchanged; source CU does not enable KB chat or source vectors.",
            }} if cu else {}),
            **({"embedding": _embedding.summary(embedding)} if embedding else {}),
            "data_boundary": {"paths": [r["path"] for r in records],
                              "file_count": len(records), "total_bytes": sum(r["size"] for r in records)},
            "uploads": 0 if matched else len(records),
            "reused_files": [{"path": path, "fileId": item["fileId"]} for path, item in matched.items()],
            "service_tier": request["service_tier"],
            "rbac": rbac, "network": network,
            "cost_and_retention": (
                "Existing Search charges remain; review File ingestion/storage charges and retention before approval."
                if mutation_required else "Existing charges and retention are unchanged; no new uploads or resources."
            ),
            "ownership": "New source and uploaded files only; reused Search/source/files are not run-owned.",
            "format_verification": "Filename/MIME hints are not detected types; Search checks actual content support during ingestion.",
            "verification": (
                "Execution rechecks definition/ETag and local/server inventories, then verifies uploaded file markers."
                if mutation_required else
                "Fresh source definition/ETag and complete file markers/IDs match the local inventory; this does not verify ingestion readiness or retrieval."
            ),
            "cleanup": "Excluded; separate run-owned source cleanup plan and approval required.",
            "next_step": (
                "Creation owner refreshes identity, RBAC, network, source state and cost/data consent, then obtains explicit approval of these changes before applying the unchanged execution input."
                if mutation_required else
                "Reuse the verified identity and file markers without mutation approval or invoking the mutation helper. Refresh discovery before later use; this observation is not future consent."
            ),
        },
        "read_only_evidence": {"request_ids": request_ids, "source_state": source["action"]},
        "writes_performed": [],
        "warnings": [
            "Planning is not approval or completed ingestion. Uploader RBAC/network remain supplied evidence; MI identity/role metadata readbacks do not prove backend attribution or effective access."
            if cu is not None and cu["auth"] == "system-assigned" else
            "Planning is not approval, policy evaluation, or proof of completed ingestion. RBAC/network are caller-supplied evidence, not verified by this helper."
        ],
    }


def _writes(result: dict[str, Any]) -> list[dict[str, Any]]:
    writes: list[dict[str, Any]] = []
    for action in ("created", "updated"):
        for resource in result["resources"].get(action, []):
            writes.append(
                {
                    "action": action,
                    "type": resource["type"],
                    "name": resource["name"],
                }
            )
    return writes


@reporting("file-source")
def execute(
    document: dict[str, Any],
    *,
    token_provider: TokenProvider = azure_cli_token,
    transport: Transport = http_request,
    progress: Progress | None = None,
    context_provider=file_cu_auth.account_context,
    mi_on_created=None,
    cleanup_capture=None,
    upload_receipt_dir=None,
    allow_upload_retry=True,
) -> dict[str, Any]:
    progress.update("validation")
    plan = document["plan"]
    fingerprint = document["_computed_fingerprint"]
    source, ingestion = _file_source_config._validate_plan(plan)
    upload_session = None
    if upload_receipt_dir is not None:
        try:
            from .file_upload import Session
        except ImportError:
            from file_upload import Session
        upload_session = Session(upload_receipt_dir, document, context_provider=context_provider)
    private_key = None
    acquisition = source.get("ai_services_key_acquisition")
    mi = source.get("ai_services_managed_identity") is True
    mi_callback = None
    if mi_on_created is not None and (not mi or not callable(mi_on_created)):
        raise _file_source_config._cu_failure("creation-callback-unsupported", "Private MI checkpoints cannot receive File key-auth wire.")
    if acquisition is not None or mi:
        approval = document.get("approval")
        if (
            not isinstance(approval, dict) or approval.get("confirmed") is not True
            or approval.get("fingerprint") != digest(plan) or fingerprint != digest(plan)
        ):
            raise _file_source_config._cu_failure("approval-missing", "Private credential acquisition requires the unchanged fingerprinted source approval.")
        if acquisition is not None:
            file_cu_auth.check_context(acquisition["context"], context_provider)
    child = {"_computed_fingerprint": fingerprint}
    cu_ids = []
    if "content_understanding" in plan:
        state, cu_ids = _file_source_config.read_content_understanding(
            plan["content_understanding"], token_provider=token_provider, transport=transport,
        )
        if not _file_source_config._cu_states_match(state, plan["cu_resource_state"]):
            raise _file_source_config._cu_failure(
                "cu-prerequisite-drift", "CU account access or configuration changed since approval; refresh the plan.",
                request_id=cu_ids[-1] if cu_ids else None,
            )
        if mi:
            binding, ids = file_cu_mi.read_binding(
                plan["content_understanding"], source["endpoint"], token_provider=token_provider, transport=transport,
            )
            cu_ids.extend(ids)
            if binding != plan["cu_identity_state"]:
                raise _file_source_config._cu_failure("cu-mi-identity-drift", "Search identity, CU role assignment or network changed since approval; refresh the concrete plan.")
            raw_transport = transport

            def recheck_mi():
                state, _ = _file_source_config.read_content_understanding(
                    plan["content_understanding"], token_provider=token_provider, transport=raw_transport,
                )
                binding, _ = file_cu_mi.read_binding(
                    plan["content_understanding"], source["endpoint"], token_provider=token_provider, transport=raw_transport,
                )
                if not _file_source_config._cu_states_match(state, plan["cu_resource_state"]) or binding != plan["cu_identity_state"]:
                    raise _file_source_config._cu_failure("cu-mi-identity-drift", "CU account or Search identity/role/network changed immediately before source PUT.")

            transport, mi_callback = file_cu_mi.guard_create(plan, transport, recheck_mi, mi_on_created)
    if acquisition is not None:
        def recheck():
            current, _ = _file_source_config.read_content_understanding(
                plan["content_understanding"], token_provider=token_provider, transport=transport,
            )
            if not _file_source_config._cu_states_match(current, plan["cu_resource_state"]):
                raise _file_source_config._cu_failure("cu-prerequisite-drift", "CU account changed before credential acquisition; refresh the plan and approval.")

        private_key = file_cu_auth.PrivateKey(
            acquisition, token_provider=token_provider, transport=transport,
            context_provider=context_provider, recheck=recheck,
        )
        transport = private_key.transport

    if upload_session is not None:
        transport = upload_session.transport(transport)
    progress.update("source-reconciliation")
    source_result = search_reconcile.execute(
        {**child, "plan": source},
        token_provider=token_provider,
        transport=_source_readback.guard_readback_transport(plan, transport),
        credential_provider=private_key.acquire if private_key else None,
        **({"managed_identity_verified": True, "on_created": mi_callback} if mi else {}),
        **({"cleanup_capture": cleanup_capture} if cleanup_capture is not None else {}),
        **({"on_file_acknowledged": upload_session.acknowledge} if upload_session is not None else {}),
    )
    source_writes = _writes(source_result)

    def check_retry_source(recovery, token):
        _file_source_config._validate_plan(plan)
        current, _ = _search_read._get(
            _search_read.resource_url(source), token,
            transport=_source_readback.guard_readback_transport(plan, transport), recovery=recovery,
        )
        etag = source_result["verification"]["readback"]["etag"]
        if (not etag or current is None or current.get("@odata.etag") != etag
                or not _search_read.definitions_match(source["desired"], current)):
            raise HelperFailure("file-upload-source-drift", "Retry requires the unchanged acknowledged source version/definition.",
                                blocked_at="verification")

    try:
        if upload_session is not None:
            etag = upload_session.require_ack()
            if source_result["verification"]["readback"]["etag"] != etag:
                raise HelperFailure("file-upload-source-drift", "Source readback differs from the retained creation ACK; retain the source.",
                                    blocked_at="verification")
        ingestion_result = file_ingest.execute(
            {**child, "plan": ingestion},
            token_provider=token_provider,
            transport=transport,
            allow_new_uploads=bool(source_result["resources"]["created"]),
            progress=progress,
            source_check=check_retry_source,
            allow_upload_retry=allow_upload_retry,
            **({"upload_session": upload_session} if upload_session is not None else {}),
        )
    except HelperFailure as failure:
        combined = HelperFailure(
            failure.code,
            failure.message,
            blocked_at=failure.blocked_at,
            writes=source_writes + failure.writes,
            resources_remaining=(
                [
                    {
                        "type": str(write["type"]),
                        "name": str(write["name"]),
                    }
                    for write in source_writes
                ]
                + failure.resources_remaining
            ),
            resources_reused=failure.resources_reused,
            resources_unverified=failure.resources_unverified,
            warnings=failure.warnings,
            request_id=failure.request_id,
            status=failure.http_status,
            partial=bool(source_writes or failure.writes or failure.partial),
        )
        combined.file_batch = failure.file_batch
        raise combined from failure

    resources = {"created": [], "reused": [], "updated": [], "skipped": []}
    for action in resources:
        resources[action].extend(source_result["resources"].get(action, []))
        resources[action].extend(ingestion_result["resources"].get(action, []))
    return {
        "status": "completed",
        "outcome": str(plan.get("outcome") or "create-file-knowledge-source"),
        "approved_plan": {"fingerprint": fingerprint, "confirmed": True},
        "resources": resources,
        "api_contracts": source_result["api_contracts"]
        + ingestion_result["api_contracts"],
        "data_movement": ingestion_result["data_movement"],
        "auth": ingestion_result["auth"],
        "rbac": ingestion_result["rbac"],
        "network": ingestion_result["network"],
        "verification": {
            **({"cu_managed_identity": {
                "mode": "system-assigned", "binding_digest": digest(plan["cu_identity_state"]),
                "processing": "unverified until indexed OCR marker validation",
                "principal_attribution": "unverified; no backend identity telemetry collected",
            }} if mi else {}),
            "readback": {
                "source": source_result["verification"]["readback"],
                "files": ingestion_result["verification"]["readback"],
            },
            "request_ids": cu_ids + source_result["verification"]["request_ids"]
            + ingestion_result["verification"]["request_ids"],
            "idempotency": (
                "exact source and file marker readback is zero-write"
            ),
        },
        "warnings": source_result["warnings"] + ingestion_result["warnings"],
        **({"file_batch": ingestion_result["file_batch"]} if "file_batch" in ingestion_result else {}),
        "ownership": {
            "run_owned": source_result["ownership"]["run_owned"]
            + ingestion_result["ownership"]["run_owned"],
            "reused_not_owned": source_result["ownership"]["reused_not_owned"]
            + ingestion_result["ownership"]["reused_not_owned"],
            "owner": plan.get("owner"),
        },
        "cleanup": {
            "status": "not-requested",
            "separate_confirmation_required": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    try:
        from . import _cleanup_receipts as cleanup_receipts
        from .private_artifacts import add_execution_output_argument, emit_plan_result, validate_execution_output_mode
    except ImportError:
        import _cleanup_receipts as cleanup_receipts
        from private_artifacts import add_execution_output_argument, emit_plan_result, validate_execution_output_mode
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--input", type=Path)
    modes.add_argument("--plan", type=Path)
    add_execution_output_argument(parser)
    add_progress_argument(parser)
    cleanup_receipts.add_argument(parser)
    parser.add_argument("--upload-receipt-dir", type=Path,
                        help="Required for creation: existing empty private directory for original File ACK and pre-upload attempts.")
    args = parser.parse_args(argv)
    fingerprint: str | None = None
    owner: Any = None
    outcome = "create-file-knowledge-source"
    capture = None
    try:
        validate_execution_output_mode(args)
        if args.plan and (args.cleanup_receipt_dir or args.upload_receipt_dir):
            raise HelperFailure("input-schema-invalid", "Creation capture requires approved --input.", blocked_at="confirmation")
        if args.plan:
            try:
                request = json.loads(args.plan.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise HelperFailure(
                    "input-unreadable", "Planning input must be readable UTF-8 JSON.",
                    blocked_at="input-resolution",
                ) from exc
            result = plan_source(request)
            emit_plan_result(result, args.execution_output)
            return 0
        document, plan, fingerprint = load_approved_input(args.input)
        document["_computed_fingerprint"] = fingerprint
        owner = plan.get("owner")
        outcome = str(plan.get("outcome") or outcome)
        source, _ = _file_source_config._validate_plan(plan)
        if source["action"] == "create" and args.cleanup_receipt_dir is None:
            raise HelperFailure(
                "file-creation-receipt-required",
                "File creation requires explicit --cleanup-receipt-dir pointing to an existing protected private directory; no default is inferred.",
                blocked_at="confirmation",
            )
        if args.cleanup_receipt_dir is not None:
            directory = cleanup_receipts.private_io.validate_private_artifact_directory(str(args.cleanup_receipt_dir))
            if args.upload_receipt_dir is not None:
                upload_directory = cleanup_receipts.private_io.validate_private_artifact_directory(str(args.upload_receipt_dir))
                if directory == upload_directory:
                    raise HelperFailure("file-receipt-directory-conflict",
                                        "Use separate private cleanup and upload journal directories.",
                                        blocked_at="confirmation")
            elif source["action"] == "create":
                raise HelperFailure(
                    "file-upload-receipt-required",
                    "File creation requires explicit --upload-receipt-dir for durable original ACK and pre-upload attempt records; use a separate existing empty private directory.",
                    blocked_at="confirmation",
                )
            capture = cleanup_receipts.Capture(directory, document)
        result = execute(document, progress=Progress("file-source", enabled=args.progress),
                         **({"cleanup_capture": capture} if capture else {}),
                         **({"upload_receipt_dir": args.upload_receipt_dir} if args.upload_receipt_dir else {}))
    except HelperFailure as failure:
        result = blocked_result(
            failure,
            outcome=outcome,
            fingerprint=fingerprint,
            owner=owner,
        )
        if capture is not None:
            result["cleanup_receipts"] = capture.summaries
        result["safe_next_decision"] = (
            "Retain any acknowledged source and confirmed uploads. Do not rerun the creation envelope, "
            "replay uncertain uploads, reset or delete resources. Use file_upload.py --plan with the "
            "original upload journal for newly approved never-attempted files; missing evidence blocks continuation, not retention."
        )
        emit_result(result)
        return 3 if result["status"] == "partial" else 2
    if capture is not None:
        result["cleanup_receipts"] = capture.summaries
    emit_result(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
