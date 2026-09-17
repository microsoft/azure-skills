from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import time
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

try:
    from ._progress import Progress, add_progress_argument, reporting
except ImportError:
    from _progress import Progress, add_progress_argument, reporting

try:
    from ._common import (
        SEARCH_AUDIENCE,
        HelperFailure,
        ReadRecovery,
        TokenProvider,
        Transport,
        azure_cli_token,
        blocked_result,
        digest,
        emit_result,
        file_digest,
        http_request,
        load_approved_input,
        odata_name,
        reject_secrets,
        require_allowed_fields,
        validate_search_endpoint,
    )
except ImportError:
    from _common import (  # type: ignore[no-redef]
        SEARCH_AUDIENCE,
        HelperFailure,
        ReadRecovery,
        TokenProvider,
        Transport,
        azure_cli_token,
        blocked_result,
        digest,
        emit_result,
        file_digest,
        http_request,
        load_approved_input,
        odata_name,
        reject_secrets,
        require_allowed_fields,
        validate_search_endpoint,
    )


API_VERSION = "2026-08-01-preview"
MAX_INVENTORY_PAGES = 200
MAX_SERVER_FILES = 200
INVENTORY_READ_TIMEOUT_SECONDS = 60
MAX_INVENTORY_RESPONSE_BYTES = 1024 * 1024
MAX_FILE_BYTES = {
    "free": 50 * 1024 * 1024,
    "basic": 50 * 1024 * 1024,
    "dedicated": 100 * 1024 * 1024,
    "serverless": 100 * 1024 * 1024,
}
MEDIA_TYPE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*$"
)
FILE_MEDIA_HINTS = {
    ".txt": "text/plain", ".md": "text/markdown",
    ".pdf": "application/pdf", ".html": "text/html", ".htm": "text/html",
    ".csv": "text/csv", ".json": "application/json", ".sh": "application/x-sh",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".jpeg": "image/jpeg", ".jpg": "image/jpeg", ".png": "image/png",
    ".bmp": "image/bmp", ".heif": "image/heif", ".heic": "image/heic",
    ".tiff": "image/tiff", ".tif": "image/tiff", ".gif": "image/gif",
    ".webp": "image/webp", ".svg": "image/svg+xml", ".avif": "image/avif",
    ".ico": "image/vnd.microsoft.icon",
}


def validate_api_version(value: Any) -> None:
    if value != API_VERSION:
        raise HelperFailure(
            "api-version-invalid",
            f"This File helper requires {API_VERSION} for its metadata upload contract. "
            "The service also supports 2026-05-01-preview minimal extraction; use a compatible client "
            "or explicitly approve August, never silently change the requested API.",
            blocked_at="input-resolution",
        )


def media_type_hint(path: str) -> str:
    """Return a portable filename hint, never a claim of server content detection."""
    return FILE_MEDIA_HINTS.get(PurePosixPath(path).suffix.lower(), "application/octet-stream")


def _reject_credential_path(path: Path) -> None:
    lowered = [part.lower() for part in path.parts]
    if (
        any(part in {".ssh", ".aws", ".azure", ".git", "credentials"} or part == ".env" or part.startswith(".env.")
            for part in lowered)
        or lowered[-1] in {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
        or path.suffix.lower() in {".pem", ".key", ".pfx", ".p12", ".kdbx"}
    ):
        raise HelperFailure(
            "credential-file-forbidden", "Credential files are outside document ingestion.",
            blocked_at="input-resolution",
        )


def _odata_name(name: Any) -> str:
    return odata_name(name)


def _list_url(plan: dict[str, Any]) -> str:
    endpoint = validate_search_endpoint(plan.get("endpoint"))
    validate_api_version(plan.get("api_version"))
    name = _odata_name(plan.get("name"))
    return (
        f"{endpoint}/knowledgesources('{name}')/files?"
        + urlencode({"api-version": API_VERSION, "pageSize": 200})
    )


def _normalize_inventory(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "fileId",
        "fileName",
        "prefix",
        "metadata",
        "parsingMode",
        "extractionMode",
        "fileSizeBytes",
        "errorMessage",
    )
    normalized = [
        {field: item.get(field) for field in fields if field in item}
        for item in files
    ]
    return sorted(
        normalized,
        key=lambda item: (str(item.get("fileName")), str(item.get("fileId"))),
    )


def _list_files(
    url: str,
    token: str,
    *,
    transport: Transport,
    recovery: ReadRecovery | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        origin = urlsplit(url)
        origin_port = origin.port
    except ValueError as exc:
        raise HelperFailure(
            "continuation-url-invalid", "File inventory URL is malformed.",
            blocked_at="verification",
        ) from exc
    current_url: str | None = url
    seen: set[str] = set()
    files: list[dict[str, Any]] = []
    request_ids: list[str] = []
    requests = 0
    deadline = time.monotonic() + INVENTORY_READ_TIMEOUT_SECONDS
    if recovery is not None:
        deadline = min(deadline, recovery.deadline)

    def inventory_transport(method, target, credential, **options):
        nonlocal requests
        if requests >= MAX_INVENTORY_PAGES:
            raise HelperFailure(
                "file-list-limit-exceeded", "Complete file inventory exceeds 200 pages/requests.",
                blocked_at="verification",
            )
        requests += 1
        return transport(method, target, credential, **options)

    while current_url:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise HelperFailure(
                "file-list-timeout", "Complete file inventory read exceeded its 60-second deadline.",
                blocked_at="verification",
                request_id=request_ids[-1] if request_ids else None,
            )
        if len(seen) >= MAX_INVENTORY_PAGES:
            raise HelperFailure(
                "file-list-limit-exceeded", "Complete file inventory exceeds 200 pages/requests.",
                blocked_at="verification",
                request_id=request_ids[-1] if request_ids else None,
            )
        try:
            current_url.encode("ascii")
            current = urlsplit(current_url)
            current_port = current.port
        except (ValueError, UnicodeEncodeError) as exc:
            raise HelperFailure(
                "continuation-url-invalid", "Search returned a malformed continuation URL.",
                blocked_at="verification",
            ) from exc
        query = parse_qs(current.query)
        if (
            current_url in seen
            or current.scheme != "https"
            or current.hostname != origin.hostname
            or current_port != origin_port
            or current.path != origin.path
            or query.get("api-version") != [API_VERSION]
            or current.username
            or current.password
        ):
            raise HelperFailure(
                "continuation-url-invalid",
                "Search returned a continuation URL outside the approved service.",
                blocked_at="verification",
            )
        seen.add(current_url)
        try:
            options = dict(timeout=remaining, response_deadline=deadline,
                           max_response_bytes=MAX_INVENTORY_RESPONSE_BYTES, follow_redirects=False)
            result = (recovery.get(current_url, token, transport=inventory_transport,
                                   max_requests=MAX_INVENTORY_PAGES - requests, **options)
                      if recovery is not None else inventory_transport("GET", current_url, token, **options))
        except HelperFailure as failure:
            if failure.code not in {"response-deadline-exceeded", "read-recovery-budget-exhausted"}:
                raise
            raise HelperFailure(
                "file-list-timeout", "Complete file inventory read exceeded its effective deadline (at most 60 seconds).",
                blocked_at="verification", request_id=failure.request_id,
                status=failure.http_status, warnings=failure.warnings,
            ) from failure
        if time.monotonic() >= deadline:
            raise HelperFailure(
                "file-list-timeout", "Complete file inventory read exceeded its 60-second deadline.",
                blocked_at="verification",
                request_id=result.request_id,
            )
        if result.status != 200 or not isinstance(result.body, dict):
            raise HelperFailure(
                "file-list-invalid",
                "File-list readback did not return a JSON object.",
                blocked_at="reconciliation",
                request_id=result.request_id,
                status=result.status,
            )
        values = result.body.get("value")
        if isinstance(values, list) and len(files) + len(values) > MAX_SERVER_FILES:
            raise HelperFailure(
                "file-list-limit-exceeded", "Complete file inventory exceeds 200 records.",
                blocked_at="verification",
                request_id=result.request_id,
            )
        if not isinstance(values, list) or not all(
            isinstance(item, dict) for item in values
        ):
            raise HelperFailure(
                "file-list-invalid",
                "File-list readback did not contain an object array.",
                blocked_at="reconciliation",
                request_id=result.request_id,
            )
        files.extend(values)
        if result.request_id:
            request_ids.append(result.request_id)
        next_link = result.body.get("@odata.nextLink")
        if next_link is not None and not isinstance(next_link, str):
            raise HelperFailure(
                "continuation-url-invalid",
                "Search returned an invalid continuation URL.",
                blocked_at="verification",
            )
        current_url = next_link
    return files, recovery.request_ids if recovery is not None else request_ids


def _validate_relative_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise HelperFailure(
            "inventory-path-invalid",
            "Every inventory path must be a non-empty normalized POSIX path.",
            blocked_at="input-resolution",
        )
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise HelperFailure(
            "inventory-path-invalid",
            f"Inventory path is not safely relative: {value!r}.",
            blocked_at="input-resolution",
        )
    if any("\r" in part or "\n" in part or ":" in part for part in path.parts):
        raise HelperFailure(
            "inventory-path-invalid",
            f"Inventory path contains a forbidden segment: {value!r}.",
            blocked_at="input-resolution",
        )
    return path.as_posix()


def _reject_links(path: Path) -> None:
    for probe in reversed((path, *path.parents)):
        attributes = getattr(probe.lstat(), "st_file_attributes", 0)
        if probe.is_symlink() or attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise HelperFailure(
                "inventory-path-invalid",
                "Local inventory cannot traverse links or reparse points.",
                blocked_at="input-resolution",
            )


def resolve_local_root(value: Any) -> Path:
    """Resolve the explicit data boundary without following links or reparse points."""
    if not isinstance(value, str) or not os.path.isabs(value):
        raise HelperFailure(
            "local-root-invalid",
            "local_root must be an explicit absolute path.",
            blocked_at="input-resolution",
        )
    try:
        path = Path(value)
        _reject_links(path)
        root = path.resolve(strict=True)
        if not root.is_dir():
            raise OSError("not a directory")
    except OSError as exc:
        raise HelperFailure(
            "local-root-invalid",
            "local_root must be an existing readable real directory.",
            blocked_at="input-resolution",
        ) from exc
    return root


def _resolve_inventory_path(root: Path, value: Any) -> Path:
    relative = _validate_relative_path(value)
    path = root.joinpath(*PurePosixPath(relative).parts)
    try:
        _reject_links(path)
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise HelperFailure(
            "inventory-path-invalid",
            f"Inventory path escapes or is unreadable: {relative}.",
            blocked_at="input-resolution",
        ) from exc
    if not resolved.is_file() or resolved.is_symlink():
        raise HelperFailure(
            "inventory-path-invalid",
            f"Inventory entry is not a regular file: {relative}.",
            blocked_at="input-resolution",
        )
    _reject_credential_path(resolved)
    return resolved


def _resolve_file(root: Path, record: dict[str, Any]) -> Path:
    relative = _validate_relative_path(record.get("path"))
    resolved = _resolve_inventory_path(root, relative)
    try:
        observed = resolved.stat()
        matches = (
            record.get("size") == observed.st_size
            and record.get("mtime_ns") == observed.st_mtime_ns
            and record.get("sha256") == file_digest(resolved)
        )
    except OSError as exc:
        raise HelperFailure(
            "inventory-unreadable", f"Selected file cannot be read: {relative}.",
            blocked_at="input-resolution",
        ) from exc
    if not matches:
        raise HelperFailure(
            "inventory-drift",
            f"Size, modification time, or SHA-256 changed for {relative}.",
            blocked_at="confirmation",
        )
    return resolved


def snapshot_inventory(
    root: Path, paths: list[str], *, service_tier: str
) -> list[dict[str, Any]]:
    """Freeze selected files with MIME hints; Search determines actual support."""
    if not isinstance(service_tier, str) or service_tier not in MAX_FILE_BYTES:
        raise HelperFailure(
            "service-tier-invalid", "Select a supported service_tier.",
            blocked_at="input-resolution",
        )
    if not isinstance(paths, list) or not 1 <= len(paths) <= 200:
        raise HelperFailure(
            "inventory-invalid", "Select between 1 and 200 explicit file paths.",
            blocked_at="input-resolution",
        )
    relative_paths = [_validate_relative_path(path) for path in paths]
    if len(set(relative_paths)) != len(relative_paths):
        raise HelperFailure(
            "inventory-invalid", "Selected file paths must be unique.",
            blocked_at="input-resolution",
        )
    records = []
    for relative in sorted(relative_paths):
        path = _resolve_inventory_path(root, relative)
        media_type = media_type_hint(relative)
        try:
            observed = path.stat()
            if not 0 < observed.st_size <= MAX_FILE_BYTES[service_tier]:
                raise HelperFailure(
                    "inventory-invalid", "File size is empty or exceeds the selected tier limit.",
                    blocked_at="input-resolution",
                )
            record = {
                "path": relative, "size": observed.st_size,
                "mtime_ns": observed.st_mtime_ns, "sha256": file_digest(path),
                "media_type": media_type,
            }
            _resolve_file(root, record)
        except OSError as exc:
            raise HelperFailure(
                "inventory-unreadable", "Selected file cannot be read.",
                blocked_at="input-resolution",
            ) from exc
        records.append(record)
    return records


def read_inventory(
    plan: dict[str, Any], token: str, *, transport: Transport
) -> tuple[list[dict[str, Any]], list[str]]:
    """Read all pages for the exact File source, using guarded continuations."""
    return _list_files(_list_url(plan), token, transport=transport)


def inventory_digest(files: list[dict[str, Any]]) -> str:
    return digest(_normalize_inventory(files))


def reconcile_inventory(
    plan: dict[str, Any],
    before: list[dict[str, Any]],
    *,
    allow_new_uploads: bool = False,
) -> dict[str, dict[str, Any]]:
    """Validate all existing markers before planning or performing any upload."""
    expected_names = {record["path"] for record in plan["files"]}
    if any(item.get("fileName") not in expected_names for item in before):
        raise HelperFailure(
            "server-inventory-conflict",
            "The server inventory contains files outside the approved inventory.",
            blocked_at="reconciliation",
        )
    matched = {}
    for record in plan["files"]:
        matches = [item for item in before if item.get("fileName") == record["path"]]
        if len(matches) > 1:
            raise HelperFailure(
                "duplicate-file-record", f"Multiple server records exist for {record['path']}.",
                blocked_at="reconciliation",
            )
        if matches:
            if not _matches(matches[0], plan, record):
                raise HelperFailure(
                    "file-record-conflict", f"Server record conflicts with approved file {record['path']}.",
                    blocked_at="reconciliation",
                )
            matched[record["path"]] = matches[0]
        elif not allow_new_uploads:
            raise HelperFailure(
                "reused-source-upload-forbidden",
                "New files cannot be uploaded into a reused source because individual-file cleanup is unsupported.",
                blocked_at="reconciliation",
            )
    return matched


def _metadata(plan: dict[str, Any], record: dict[str, Any]) -> dict[str, str]:
    supplied = record.get("metadata") or {}
    if not isinstance(supplied, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in supplied.items()
    ):
        raise HelperFailure(
            "file-metadata-invalid",
            "File metadata must contain only string keys and values.",
            blocked_at="input-resolution",
        )
    metadata = dict(supplied)
    metadata.update(
        {
            "foundryIqSha256": record["sha256"],
            "foundryIqSizeBytes": str(record["size"]),
            "foundryIqInventory": plan["inventory_digest"],
            "foundryIqOwner": str(plan["owner"]),
            "foundryIqSource": str(plan["name"]),
        }
    )
    return metadata


def _matches(
    server: dict[str, Any],
    plan: dict[str, Any],
    record: dict[str, Any],
) -> bool:
    metadata = server.get("metadata") or {}
    expected = _metadata(plan, record)
    return (
        server.get("fileName") == record["path"]
        and server.get("fileSizeBytes") == record["size"]
        and server.get("errorMessage") is None
        and isinstance(metadata, dict)
        and all(metadata.get(key) == value for key, value in expected.items())
    )


def _multipart(
    plan: dict[str, Any],
    record: dict[str, Any],
    content: bytes,
    fingerprint: str,
) -> tuple[bytes, str]:
    boundary = "foundry-iq-" + fingerprint.removeprefix("sha256:")[:24]
    metadata = {
        "fileName": record["path"],
        "metadata": _metadata(plan, record),
    }
    media_type = record.get("media_type")
    if not isinstance(media_type, str) or not media_type:
        media_type = media_type_hint(record["path"])
    pieces = [
        f"--{boundary}\r\n".encode("ascii"),
        b'Content-Disposition: form-data; name="metadata"\r\n',
        b"Content-Type: application/json\r\n\r\n",
        json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        b"\r\n",
        f"--{boundary}\r\n".encode("ascii"),
        b'Content-Disposition: form-data; name="content"; filename="upload"\r\n',
        f"Content-Type: {media_type}\r\n\r\n".encode("ascii"),
        content,
        b"\r\n",
        f"--{boundary}--\r\n".encode("ascii"),
    ]
    return b"".join(pieces), boundary


def _validate_plan(plan: dict[str, Any]) -> tuple[Path, list[dict[str, Any]]]:
    reject_secrets(plan)
    require_allowed_fields(
        plan,
        {
            "operation",
            "outcome",
            "endpoint",
            "name",
            "api_version",
            "local_root",
            "files",
            "inventory_digest",
            "expected_server_inventory_digest",
            "service_tier",
            "extraction_mode",
            "rbac",
            "network",
            "owner",
            "cleanup_approved",
        },
        label="File ingestion plan",
    )
    for field, allowed in (
        ("rbac", {"assignments"}),
        ("network", {"posture", "evidence"}),
    ):
        section = plan.get(field)
        if section is not None:
            if not isinstance(section, dict):
                raise HelperFailure(
                    "input-schema-invalid",
                    f"{field} must be an object.",
                    blocked_at="input-resolution",
                )
            require_allowed_fields(section, allowed, label=field)
    if plan.get("operation") != "ingest" or plan.get("cleanup_approved") is not False:
        raise HelperFailure(
            "operation-invalid",
            "File ingestion requires operation ingest and cleanup_approved false.",
            blocked_at="input-resolution",
        )
    if not isinstance(plan.get("name"), str) or not plan["name"]:
        raise HelperFailure(
            "name-invalid",
            "Knowledge source name is required.",
            blocked_at="input-resolution",
        )
    if not isinstance(plan.get("owner"), str) or not plan["owner"]:
        raise HelperFailure(
            "owner-invalid",
            "File ingestion owner is required.",
            blocked_at="input-resolution",
        )
    root = resolve_local_root(plan.get("local_root"))
    records = plan.get("files")
    if not isinstance(records, list) or not records or len(records) > 200:
        raise HelperFailure(
            "inventory-invalid",
            "files must contain between 1 and 200 entries.",
            blocked_at="input-resolution",
        )
    if not all(isinstance(record, dict) for record in records):
        raise HelperFailure(
            "inventory-invalid",
            "Every file inventory entry must be an object.",
            blocked_at="input-resolution",
        )
    for record in records:
        require_allowed_fields(
            record,
            {"path", "size", "mtime_ns", "sha256", "media_type", "metadata"},
            label="File inventory record",
        )
    service_tier = plan.get("service_tier")
    if service_tier not in MAX_FILE_BYTES:
        raise HelperFailure(
            "service-tier-invalid",
            "service_tier must be free, basic, dedicated, or serverless.",
            blocked_at="input-resolution",
        )
    extraction_mode = plan.get("extraction_mode")
    if extraction_mode not in {"minimal", "standard"}:
        raise HelperFailure(
            "extraction-mode-invalid",
            "extraction_mode must be minimal or standard.",
            blocked_at="input-resolution",
        )
    paths = [_validate_relative_path(record.get("path")) for record in records]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise HelperFailure(
            "inventory-invalid",
            "File inventory paths must be unique and byte-sorted.",
            blocked_at="input-resolution",
        )
    if digest(records) != plan.get("inventory_digest"):
        raise HelperFailure(
            "inventory-drift",
            "inventory_digest does not match the approved file records.",
            blocked_at="confirmation",
        )
    for record in records:
        size = record.get("size")
        mtime_ns = record.get("mtime_ns")
        media_type = record.get("media_type")
        if (
            not isinstance(size, int)
            or size <= 0
            or size > MAX_FILE_BYTES[service_tier]
            or not isinstance(mtime_ns, int)
            or mtime_ns <= 0
            or not isinstance(media_type, str)
            or MEDIA_TYPE.fullmatch(media_type) is None
        ):
            raise HelperFailure(
                "inventory-invalid",
                "Every file requires positive size/mtime, media type, and a tier-valid size.",
                blocked_at="input-resolution",
            )
        _resolve_file(root, record)
        _metadata(plan, record)
    return root, records


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
        observed, _ = _list_files(
            list_url, token, transport=transport, recovery=recovery,
        )
    except HelperFailure as read_failure:
        warnings.append(f"Upload readback failed ({read_failure.code}); original upload failure retained.")
        return None
    finally:
        request_ids.extend(recovery.request_ids)
        warnings.extend(recovery.diagnostics())
    matches = [item for item in observed if item.get("fileName") == record["path"]]
    if len(matches) != 1 or not _matches(matches[0], plan, record):
        return None
    return matches[0]


def _remaining_files(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "knowledge-source-file",
            "fileName": resource["fileName"],
            "sha256": resource["sha256"],
        }
        for resource in resources
    ]


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
    root, records = _validate_plan(plan)
    list_url = _list_url(plan)
    token = token_provider(SEARCH_AUDIENCE)
    readonly = ReadRecovery() if not allow_new_uploads else None
    before, request_ids = _list_files(list_url, token, transport=transport, recovery=readonly)
    warnings: list[str] = list(readonly.warnings) if readonly is not None else []
    if inventory_digest(before) != plan.get("expected_server_inventory_digest"):
        raise HelperFailure(
            "server-inventory-drift",
            "Server file inventory changed after approval.",
            blocked_at="reconciliation",
            warnings=readonly.diagnostics() if readonly is not None else [],
        )
    matched = reconcile_inventory(plan, before, allow_new_uploads=allow_new_uploads)

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

        path = _resolve_file(root, record)
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise HelperFailure(
                "inventory-unreadable",
                f"Approved file became unreadable: {record['path']}.",
                blocked_at="execution",
                writes=created,
                resources_remaining=_remaining_files(created),
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
                resources_remaining=_remaining_files(created),
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
                resources_remaining=_remaining_files(created),
                partial=bool(created),
            )
        body, boundary = _multipart(plan, record, content, fingerprint)
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
                    writes=created, resources_remaining=_remaining_files(created),
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
                resources_remaining=_remaining_files(created) + [uncertain],
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
                    _remaining_files(created) + ([uncertain] if ambiguous else [])
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
        after, after_request_ids = _list_files(
            list_url, token, transport=transport, recovery=recovery,
        )
    except HelperFailure as failure:
        raise HelperFailure(
            failure.code,
            failure.message,
            blocked_at=failure.blocked_at,
            writes=created + failure.writes,
            resources_remaining=(
                _remaining_files(created) + failure.resources_remaining
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
            resources_remaining=_remaining_files(created),
            request_id=request_ids[-1] if request_ids else None,
            partial=bool(created),
            warnings=[*warnings, *ack_warnings, *recovery.diagnostics()],
        )
    verified: list[dict[str, Any]] = []
    for record in records:
        matches = [item for item in after if item.get("fileName") == record["path"]]
        if len(matches) != 1 or not _matches(matches[0], plan, record):
            raise HelperFailure(
                "readback-mismatch",
                f"File readback failed for {record['path']}.",
                blocked_at="verification",
                writes=created,
                resources_remaining=_remaining_files(created),
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
            {"operation": "upload-file", "version": API_VERSION, "preview": True}
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
            "server_inventory_digest": digest(_normalize_inventory(after)),
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
