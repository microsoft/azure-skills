from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any

try:
    from ._progress import Progress, add_progress_argument, reporting
    from ._common import (
        SEARCH_AUDIENCE, HelperFailure, ReadRecovery, TokenProvider, Transport, azure_cli_token,
        blocked_result, digest, emit_result, http_request, load_approved_input,
    )
    from . import _file_inventory
except ImportError:
    from _progress import Progress, add_progress_argument, reporting
    from _common import (
        SEARCH_AUDIENCE, HelperFailure, ReadRecovery, TokenProvider, Transport, azure_cli_token,
        blocked_result, digest, emit_result, http_request, load_approved_input,
    )
    import _file_inventory


def _confirm_ambiguous_upload(
    list_url: str,
    token: str,
    transport: Transport,
    record: dict[str, Any],
    plan: dict[str, Any],
    request_ids: list[str],
    failure: HelperFailure,
    warnings: list[str],
) -> dict[str, Any] | None:
    """Resolve an ambiguous upload with bounded readback, never upload replay.

    Only ambiguous outcomes (transport failure, timeout, 409/429/5xx) reach
    this helper. A definitive 200/201 response never calls it. Returns the
    matching server record when the readback proves the approved file
    exists, otherwise ``None`` so the caller reports ``partial``.
    """
    recovery = ReadRecovery()
    try:
        recovery.delay(failure)
        observed, _ = _file_inventory._list_files(
            list_url, token, transport=transport, recovery=recovery,
        )
    except HelperFailure as read_failure:
        warnings.append(f"Upload readback failed ({read_failure.code}); original upload failure retained.")
        return None
    finally:
        request_ids.extend(recovery.request_ids)
        warnings.extend(recovery.diagnostics())
    matches = [item for item in observed if item.get("fileName") == record["path"]]
    if len(matches) != 1 or not _file_inventory._matches(matches[0], plan, record):
        return None
    return matches[0]


@reporting("file-upload")
def execute(
    document: dict[str, Any],
    *,
    token_provider: TokenProvider = azure_cli_token,
    transport: Transport = http_request,
    allow_new_uploads: bool = False,
    progress: Progress | None = None,
    upload_session=None,
    source_check=None,
    allow_upload_retry=True,
) -> dict[str, Any]:
    if allow_new_uploads or upload_session is not None or len(document.get("plan", {}).get("files", [])) > 1:
        try:
            from .file_upload import run_batch
        except ImportError:
            from file_upload import run_batch
        return run_batch(document, token_provider=token_provider, transport=transport, progress=progress,
                         allow_new_uploads=allow_new_uploads, session=upload_session,
                         source_check=source_check, allow_upload_retry=allow_upload_retry)
    progress.update("file-inventory")
    plan = document["plan"]
    fingerprint = document["_computed_fingerprint"]
    root, records = _file_inventory._validate_plan(plan)
    list_url = _file_inventory._list_url(plan)
    token = token_provider(SEARCH_AUDIENCE)
    readonly = ReadRecovery() if not allow_new_uploads else None
    before, request_ids = _file_inventory._list_files(list_url, token, transport=transport, recovery=readonly)
    warnings: list[str] = list(readonly.warnings) if readonly is not None else []
    if _file_inventory.inventory_digest(before) != plan.get("expected_server_inventory_digest"):
        raise HelperFailure(
            "server-inventory-drift",
            "Server file inventory changed after approval.",
            blocked_at="reconciliation",
            warnings=readonly.diagnostics() if readonly is not None else [],
        )
    matched = _file_inventory.reconcile_inventory(plan, before, allow_new_uploads=allow_new_uploads)

    created: list[dict[str, Any]] = []
    reused: list[dict[str, Any]] = []
    acknowledged_ids: list[str] = []
    progress.update("file-upload", uploads_acknowledged=0, files_reused=0)
    for record in records:
        progress.update("file-upload", uploads_acknowledged=len(created), files_reused=len(reused))
        if record["path"] in matched:
            reused.append(
                {
                    "fileId": matched[record["path"]].get("fileId"),
                    "fileName": record["path"],
                    "sha256": record["sha256"],
                }
            )
            continue

        path = _file_inventory._resolve_file(root, record)
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise HelperFailure(
                "inventory-unreadable",
                f"Approved file became unreadable: {record['path']}.",
                blocked_at="execution",
                writes=created,
                resources_remaining=_file_inventory._remaining_files(created),
                partial=bool(created),
            ) from exc
        try:
            post_read_stat = path.stat()
        except OSError as exc:
            raise HelperFailure(
                "inventory-unreadable",
                f"Approved file became unreadable: {record['path']}.",
                blocked_at="execution",
                writes=created,
                resources_remaining=_file_inventory._remaining_files(created),
                partial=bool(created),
            ) from exc
        content_digest = "sha256:" + hashlib.sha256(content).hexdigest()
        if (
            content_digest != record["sha256"]
            or len(content) != record["size"]
            or post_read_stat.st_mtime_ns != record["mtime_ns"]
        ):
            raise HelperFailure(
                "inventory-drift",
                f"Approved file changed before upload: {record['path']}.",
                blocked_at="confirmation",
                writes=created,
                resources_remaining=_file_inventory._remaining_files(created),
                partial=bool(created),
            )
        body, boundary = _file_inventory._multipart(plan, record, content, fingerprint)
        try:
            result = transport(
                "POST",
                list_url,
                token,
                body=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            )
        except HelperFailure as failure:
            if failure.http_status is not None and 400 <= failure.http_status < 500 and failure.http_status not in {408, 409, 429}:
                raise HelperFailure(
                    failure.code, failure.message, blocked_at=failure.blocked_at,
                    writes=created, resources_remaining=_file_inventory._remaining_files(created),
                    request_id=failure.request_id, status=failure.http_status, partial=bool(created),
                ) from failure
            # The transport outcome is ambiguous (we do not know whether the
            # server received the write): attempt one readback before
            # concluding partial, per the ambiguous-write contract.
            confirmed = _confirm_ambiguous_upload(
                list_url, token, transport, record, plan, request_ids, failure, warnings
            )
            if confirmed is not None:
                created.append({"fileName": record["path"], "sha256": record["sha256"]})
                if failure.request_id:
                    request_ids.append(failure.request_id)
                continue
            uncertain = {
                "action": "upload-unverified",
                "type": "knowledge-source-file",
                "fileName": record["path"],
                "sha256": record["sha256"],
            }
            raise HelperFailure(
                failure.code,
                failure.message,
                blocked_at=failure.blocked_at,
                writes=created + [uncertain],
                resources_remaining=_file_inventory._remaining_files(created) + [uncertain],
                request_id=failure.request_id,
                status=failure.http_status,
                partial=True,
                warnings=warnings,
            ) from failure
        if result.status not in {200, 201}:
            ambiguous = result.status in {408, 409, 429} or result.status >= 500
            if ambiguous:
                confirmed = _confirm_ambiguous_upload(
                    list_url, token, transport, record, plan, request_ids,
                    HelperFailure("upload-failed", "Upload response is ambiguous.",
                                  blocked_at="execution", status=result.status,
                                  request_id=result.request_id, retry_after=result.retry_after,
                                  recovery_deadline=result.recovery_deadline),
                    warnings,
                )
                if confirmed is not None:
                    created.append(
                        {"fileName": record["path"], "sha256": record["sha256"]}
                    )
                    if result.request_id:
                        request_ids.append(result.request_id)
                    continue
            uncertain = {
                "action": "upload-unverified",
                "type": "knowledge-source-file",
                "fileName": record["path"],
                "sha256": record["sha256"],
            }
            raise HelperFailure(
                "upload-failed",
                f"Upload returned unexpected HTTP {result.status}.",
                blocked_at="execution",
                writes=created + ([uncertain] if ambiguous else []),
                resources_remaining=(
                    _file_inventory._remaining_files(created) + ([uncertain] if ambiguous else [])
                ),
                request_id=result.request_id,
                status=result.status,
                partial=bool(created) or ambiguous,
                warnings=warnings,
            )
        # A definitive 200/201 response is not ambiguous: trust it rather than
        # re-listing the whole source after every single file. The complete
        # inventory is verified once, in bulk, after the loop.
        created.append({"fileName": record["path"], "sha256": record["sha256"]})
        if result.request_id:
            request_ids.append(result.request_id)
            acknowledged_ids.append(ReadRecovery.safe_id(result.request_id))

    progress.update("file-readback", uploads_acknowledged=len(created), files_reused=len(reused))
    ack_warnings = (["Acknowledged upload request IDs: " + ", ".join(acknowledged_ids)]
                    if acknowledged_ids else [])
    recovery = ReadRecovery()
    try:
        after, after_request_ids = _file_inventory._list_files(
            list_url, token, transport=transport, recovery=recovery,
        )
    except HelperFailure as failure:
        raise HelperFailure(
            failure.code,
            failure.message,
            blocked_at=failure.blocked_at,
            writes=created + failure.writes,
            resources_remaining=(
                _file_inventory._remaining_files(created) + failure.resources_remaining
            ),
            resources_reused=failure.resources_reused,
            resources_unverified=failure.resources_unverified,
            warnings=[*warnings, *ack_warnings, *failure.warnings, *recovery.diagnostics()],
            request_id=failure.request_id,
            status=failure.http_status,
            partial=bool(created or failure.partial),
        ) from failure
    request_ids.extend(after_request_ids)
    warnings.extend(recovery.warnings)
    if len(after) != len(records):
        raise HelperFailure(
            "readback-mismatch",
            "Final server inventory count differs from the approved inventory.",
            blocked_at="verification",
            writes=created,
            resources_remaining=_file_inventory._remaining_files(created),
            request_id=request_ids[-1] if request_ids else None,
            partial=bool(created),
            warnings=[*warnings, *ack_warnings, *recovery.diagnostics()],
        )
    verified: list[dict[str, Any]] = []
    for record in records:
        matches = [item for item in after if item.get("fileName") == record["path"]]
        if len(matches) != 1 or not _file_inventory._matches(matches[0], plan, record):
            raise HelperFailure(
                "readback-mismatch",
                f"File readback failed for {record['path']}.",
                blocked_at="verification",
                writes=created,
                resources_remaining=_file_inventory._remaining_files(created),
                request_id=request_ids[-1] if request_ids else None,
                partial=bool(created),
                warnings=[*warnings, *ack_warnings, *recovery.diagnostics()],
            )
        verified.append(
            {
                "fileId": matches[0].get("fileId"),
                "fileName": record["path"],
                "sha256": record["sha256"],
                "size": record["size"],
            }
        )

    progress.update("file-readback", files_verified=len(verified))
    return {
        "status": "completed",
        "outcome": str(plan.get("outcome") or "file-knowledge-source-ingestion"),
        "approved_plan": {"fingerprint": fingerprint, "confirmed": True},
        "resources": {
            "created": created,
            "reused": reused,
            "updated": [],
            "skipped": [],
        },
        "api_contracts": [
            {"operation": "upload-file", "version": _file_inventory.API_VERSION, "preview": True}
        ],
        "data_movement": {
            "boundary": {"local_root_digest": digest(str(root))},
            "result": "exact approved files uploaded directly to Search",
        },
        "auth": {"mode": "entra-user", "principals": []},
        "rbac": plan.get("rbac", {"assignments": []}),
        "network": plan.get("network", {"posture": "preserved", "evidence": None}),
        "verification": {
            "readback": verified,
            "server_inventory_digest": digest(_file_inventory._normalize_inventory(after)),
            "request_ids": request_ids,
            "idempotency": "matching marker metadata is zero-write",
        },
        "warnings": warnings,
        "ownership": {
            "run_owned": created,
            "reused_not_owned": reused,
            "owner": plan.get("owner"),
        },
        "cleanup": {
            "status": "not-requested",
            "separate_confirmation_required": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    add_progress_argument(parser)
    args = parser.parse_args(argv)
    fingerprint: str | None = None
    owner: Any = None
    outcome = "file-knowledge-source-ingestion"
    try:
        document, plan, fingerprint = load_approved_input(args.input)
        document["_computed_fingerprint"] = fingerprint
        owner = plan.get("owner")
        outcome = str(plan.get("outcome") or outcome)
        result = execute(document, progress=Progress("file-upload", enabled=args.progress))
    except HelperFailure as failure:
        result = blocked_result(
            failure,
            outcome=outcome,
            fingerprint=fingerprint,
            owner=owner,
        )
        emit_result(result)
        return 3 if result["status"] == "partial" else 2
    emit_result(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
