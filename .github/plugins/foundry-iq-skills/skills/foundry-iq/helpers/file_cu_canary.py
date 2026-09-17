"""Approval-gated one-file OCR canary; never invoked automatically by ingestion."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import secrets
import sys
import time
import zlib
from email import policy
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import urlencode

try:
    from . import _bootstrap_io, file_source, file_ingest, file_cu_mi, search_reconcile
    from ._common import (HelperFailure, MANAGEMENT_AUDIENCE, SEARCH_AUDIENCE, azure_cli_token,
                          blocked_result, digest, emit_result, http_request, load_approved_input,
                          require_allowed_fields, reject_secrets)
except ImportError:
    import _bootstrap_io, file_source, file_ingest, file_cu_mi, search_reconcile
    from _common import (HelperFailure, MANAGEMENT_AUDIENCE, SEARCH_AUDIENCE, azure_cli_token,
                         blocked_result, digest, emit_result, http_request, load_approved_input,
                         require_allowed_fields, reject_secrets)

PDF_NAME = "cu-mi-probe.pdf"
MARKER = re.compile(r"CUOCR[2-9]{8}")
FIELD = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,127}")
# Pinned implementation, not deployed proof; see references/file-cu-canary.md.
# Never populate this from caller attestations or an arbitrary readback field.
OCR_CONTENT_MAPPINGS = {
    "2026-08-01-preview": {
        "field": "snippet", "parent_field": "snippet_parent_id", "path_field": "metadata_storage_path",
        "authority": {
            "repository": "AzureSearch", "commit": "2e241af8939a0891836b78278df113dab31a5964",
            "contract": "file-standard-cu-index-v1",
        },
    },
}
DISCLOSURE = (
    "One synthetic image-only PDF is uploaded to Search and processed by billable CU OCR; "
    "CU may create an analyzer, content may cross regions, and Search retains generated data. "
    "No embeddings, KB/chat or direct CU probes. Existing resources/roles/network/local-auth stay unchanged. "
    "Client time/attempt caps are not a monetary cap or cancellation of remote processing. "
    "Cleanup needs separate approval; retain the private source/file/index inventory."
)
GLYPHS = {
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
}


def fail(code, message, *, partial=False, request_id=None, status=None):
    return HelperFailure(code, message, blocked_at="file-cu-canary", partial=partial, request_id=request_id, status=status)


def pdf_bytes(marker):
    if not isinstance(marker, str) or MARKER.fullmatch(marker) is None:
        raise fail("canary-marker-invalid", "Use CUOCR followed by eight digits 2–9.")
    scale, margin = 12, 24
    width, height = len(marker) * 6 * scale + 2 * margin, 7 * scale + 2 * margin
    image = bytearray(b"\xff" * width * height)
    for n, letter in enumerate(marker):
        for y, row in enumerate(GLYPHS[letter]):
            for x, pixel in enumerate(row):
                if pixel == "1":
                    for yy in range(scale):
                        start = (margin + y * scale + yy) * width + margin + (n * 6 + x) * scale
                        image[start:start + scale] = b"\x00" * scale
    compressed = zlib.compress(bytes(image), 9)
    draw = b"q 600 0 0 84 20 20 cm /Image0 Do Q\n"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 640 124] /Resources << /XObject << /Image0 4 0 R >> >> /Contents 5 0 R >>",
        f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} /ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode /Length {len(compressed)} >>\nstream\n".encode()
        + compressed + b"\nendstream",
        f"<< /Length {len(draw)} >>\nstream\n".encode() + draw + b"endstream",
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for n, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out.extend(f"{n} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(out)
    out.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode())
    out.extend(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    if len(out) > 65536 or marker.encode() in out:
        raise fail("canary-pdf-invalid", "Probe must be bounded image-only bytes without a text marker.")
    return bytes(out)


def prepare(directory, marker=None):
    directory = _bootstrap_io.private_directory(directory)
    marker = marker or "CUOCR" + "".join(secrets.choice("23456789") for _ in range(8))
    data = pdf_bytes(marker)
    _bootstrap_io.private_bytes(directory, PDF_NAME, data)
    manifest = {"file": PDF_NAME, "marker": marker, "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data), "pages": 1, "text_layer": False}
    path = _bootstrap_io.private_file(directory, "cu-mi-probe-manifest.json", manifest)
    return {"status": "prepared", "manifest": str(path), "writes_performed": [],
            "azure_operations": 0, "note": "Local synthetic artifacts only; no live approval or resource selection."}


def _bounds(value):
    if not isinstance(value, dict):
        raise fail("canary-bounds-missing", "Select explicit timeout, HTTP request, polling attempt and interval caps.")
    ranges = {"timeout_seconds": (30, 600), "max_requests": (16, 100),
              "max_poll_attempts": (1, 10), "poll_interval_seconds": (1, 30)}
    require_allowed_fields(value, set(ranges), label="canary bounds")
    if any(type(value.get(k)) is not int or not low <= value[k] <= high for k, (low, high) in ranges.items()):
        raise fail("canary-bounds-invalid", "Use timeout 30–600s, HTTP requests 16–100, polls 1–10 and interval 1–30s.")


def _ocr_mapping(api_version, field):
    mapping = OCR_CONTENT_MAPPINGS.get(api_version)
    if mapping is None:
        raise fail("canary-ocr-mapping-unverified",
                   "No pinned File Standard OCR-to-index field mapping is verified for this API. "
                   "Do not create/upload; verify the first-party mapping and update the supported contract before planning.")
    if field != mapping["field"]:
        raise fail("canary-field-unverified", "The selected field does not match the pinned File Standard OCR-content mapping.")
    return copy.deepcopy(mapping)


def _verified_file(source_result, ingestion):
    files = source_result["verification"]["readback"].get("files")
    expected = ingestion["files"][0]
    if (
        not isinstance(files, list) or len(files) != 1 or not isinstance(files[0], dict)
        or not isinstance(files[0].get("fileId"), str) or not files[0]["fileId"].strip()
        or files[0].get("fileName") != expected["path"]
        or files[0].get("sha256") != expected["sha256"] or files[0].get("size") != expected["size"]
    ):
        raise fail("canary-file-identity-unverified", "Require the uploaded synthetic file's exact ID, path, hash and size readback.")
    return files[0]


def _verify_index_fields(index, mapping):
    fields = index.get("fields")
    if not isinstance(fields, list):
        raise fail("canary-field-unverified", "Generated index fields must match the pinned File OCR mapping.")
    for name in (mapping["field"], mapping["parent_field"], mapping["path_field"]):
        selected = [field for field in fields if isinstance(field, dict) and field.get("name") == name]
        if len(selected) != 1 or selected[0].get("type") != "Edm.String" or selected[0].get("retrievable") is not True:
            raise fail("canary-field-unverified", "Require unique retrievable string fields for pinned OCR content and file identity.")
        if name == mapping["field"] and (
            selected[0].get("searchable") is not True
            or any(selected[0].get(flag) is not False for flag in ("filterable", "sortable", "facetable"))
        ):
            raise fail("canary-field-unverified", "The canonical snippet field does not match the pinned searchable OCR-content schema.")


def _contains_marker(value, marker):
    if isinstance(value, str):
        return marker in re.sub(r"[^A-Z0-9]", "", value.upper())
    if isinstance(value, dict):
        return any(_contains_marker(k, marker) or _contains_marker(v, marker) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_marker(item, marker) for item in value)
    return False


def _check_non_image_channels(plan, marker):
    ingestion = plan["ingestion"]
    # Produce the actual multipart envelope with only the image bytes omitted.
    try:
        body, boundary = file_ingest._multipart(ingestion, ingestion["files"][0], b"", digest(plan))
        message = BytesParser(policy=policy.default).parsebytes(
            f"Content-Type: multipart/form-data; boundary={boundary}\r\n\r\n".encode("ascii") + body
        )
    except (ValueError, UnicodeError, TypeError):
        raise fail("canary-upload-envelope-unverified", "The non-image upload envelope could not be produced safely.") from None
    parts = list(message.iter_parts())
    if (
        message.defects or len(parts) != 2 or any(part.defects for part in parts)
        or [part.get_param("name", header="content-disposition") for part in parts] != ["metadata", "content"]
        or parts[0].get_content_type() != "application/json" or parts[1].get_payload(decode=True) != b""
    ):
        raise fail("canary-upload-envelope-unverified", "The produced non-image upload envelope is not the supported multipart contract.")
    try:
        metadata = json.loads(parts[0].get_payload(decode=True))
        channels = [plan["source"]["desired"], file_ingest._list_url(ingestion),
                    body.decode("utf-8"), metadata, [list(part.items()) for part in parts]]
    except (ValueError, UnicodeError, TypeError):
        raise fail("canary-upload-envelope-unverified", "The produced non-image upload envelope could not be inspected.") from None
    if _contains_marker(channels, marker):
        raise fail("canary-marker-in-metadata", "The OCR marker must not occur in source/upload names, owner, metadata or other non-image upload channels.")


def _file_contract(plan, marker):
    expected = pdf_bytes(marker)
    if not isinstance(plan, dict) or not isinstance(plan.get("ingestion"), dict):
        raise fail("canary-file-contract-invalid", "Retain the complete File plan.")
    root = file_ingest.resolve_local_root(plan["ingestion"].get("local_root"))
    actual = file_ingest._resolve_inventory_path(root, PDF_NAME)
    try:
        if actual.stat().st_size != len(expected):
            raise fail("canary-content-drift", "Probe size differs from the bounded synthetic image-only PDF.")
    except OSError:
        raise fail("canary-content-drift", "Selected synthetic PDF is unreadable.") from None
    file_source._validate_plan(plan)
    source, ingestion = plan["source"], plan["ingestion"]
    settings = source["desired"]["fileParameters"]["ingestionParameters"]
    if (
        plan.get("file_cu_plan_version") != "1.2" or source.get("action") != "create"
        or source["api_version"] != "2026-08-01-preview"
        or settings.get("contentExtractionMode") != "standard" or "embedding" in plan
        or settings.get("embeddingModel") is not None or settings.get("chatCompletionModel") is not None
        or settings.get("disableImageVerbalization") is not True
        or len(ingestion["files"]) != 1 or ingestion["files"][0]["path"] != PDF_NAME
    ):
        raise fail("canary-file-contract-invalid", "Canary requires fresh conditional File Standard MI creation, one synthetic PDF, no embedding/chat and unchanged August API.")
    _check_non_image_channels(plan, marker)
    records = file_ingest.snapshot_inventory(root, [PDF_NAME], service_tier=ingestion["service_tier"])
    if records != ingestion["files"] or records[0]["sha256"] != "sha256:" + hashlib.sha256(expected).hexdigest():
        raise fail("canary-content-drift", "Synthetic inventory changed; regenerate the concrete plan before approval.")


def plan_canary(request, *, token_provider=azure_cli_token, transport=http_request, now=time.time):
    if not isinstance(request, dict):
        raise fail("canary-input-invalid", "Canary intent must be an object.")
    require_allowed_fields(request, {"schema_version", "file_request", "marker", "content_field", "bounds", "receipt_directory"},
                           label="File CU canary intent")
    reject_secrets(request)
    _bounds(request.get("bounds"))
    if request.get("schema_version") != "1.0" or not isinstance(request.get("content_field"), str) or not FIELD.fullmatch(request["content_field"]):
        raise fail("canary-input-invalid", "Use schema 1.0 and an exact simple generated content field name.")
    pdf_bytes(request.get("marker"))
    directory = _bootstrap_io.private_directory(request.get("receipt_directory"))
    fr = request.get("file_request")
    if not isinstance(fr, dict):
        raise fail("canary-input-invalid", "Supply an explicit existing Search/CU File request; no resource defaults or provisioning.")
    # Reject a key mode before even read-only resource discovery.
    cu = fr.get("content_understanding")
    if not isinstance(cu, dict) or cu.get("auth", "system-assigned") != "system-assigned":
        raise fail("canary-auth-invalid", "This canary only tests File managed identity; no keys or fallback.")
    if fr.get("paths") != [PDF_NAME] or fr.get("extraction_mode") != "standard" or fr.get("vectorization") != "none":
        raise fail("canary-file-contract-invalid", "Select exactly the generated probe PDF, Standard extraction and no vectors.")
    version = fr.get("api_version", file_ingest.API_VERSION)
    file_ingest.validate_api_version(version)
    mapping = _ocr_mapping(version, request["content_field"])
    root = file_ingest.resolve_local_root(fr.get("local_root"))
    selected = file_ingest._resolve_inventory_path(root, PDF_NAME)
    try:
        if selected.stat().st_size != len(pdf_bytes(request["marker"])):
            raise fail("canary-content-drift", "Selected PDF is not the bounded synthetic probe.")
    except OSError:
        raise fail("canary-content-drift", "Selected probe is unreadable.") from None
    result = file_source.plan_source(fr, token_provider=token_provider, transport=transport)
    fp = result["execution_input"]["plan"]
    _file_contract(fp, request["marker"])
    created = int(now())
    plan = {
        "operation": "validate-file-cu-mi", "version": "1.1", "file_plan": fp, "ocr_mapping": mapping,
        "marker": request["marker"], "content_field": request["content_field"],
        "bounds": copy.deepcopy(request["bounds"]), "receipt_directory": str(directory),
        "created_at": created, "expires_at": created + 900, "disclosure": DISCLOSURE,
    }
    fingerprint = digest(plan)
    return {
        "status": "planned", "plan_fingerprint": fingerprint,
        "execution_input": {"schema_version": "1.0", "plan": plan,
                            "approval": {"confirmed": False, "fingerprint": fingerprint}},
        "approval_summary": {"source": result["approval_summary"], "bounds": plan["bounds"],
                             "expires_at": plan["expires_at"], "disclosure": DISCLOSURE,
                             "expected_outcome": "Indexed OCR marker without client keys; principal attribution remains separate."},
        "writes_performed": [],
    }


class BoundedTransport:
    def __init__(self, plan, raw, clock, record):
        self.plan, self.raw, self.clock, self.record = plan, raw, clock, record
        self.deadline = clock() + plan["bounds"]["timeout_seconds"]
        self.calls, self.puts, self.uploads = 0, 0, 0
        self.upload_ack_failure = None
        self.index_url = None
        fp = plan["file_plan"]
        self.source_url = search_reconcile.resource_url(fp["source"])
        self.files_prefix = self.source_url.split("?")[0] + "/files"
        cu = fp["content_understanding"]
        mi = cu["managed_identity"]
        self.arm_urls = {
            f"{MANAGEMENT_AUDIENCE}{cu['resource_id']}?api-version=2024-10-01",
            f"{MANAGEMENT_AUDIENCE}{mi['search_resource_id']}?api-version={file_cu_mi.SEARCH_API}",
            f"{MANAGEMENT_AUDIENCE}{mi['role_assignment_id']}?api-version={file_cu_mi.ROLE_API}",
        }

    def __call__(self, method, url, token, **kwargs):
        if self.upload_ack_failure is not None:
            raise self.upload_ack_failure
        remaining = self.deadline - self.clock()
        if remaining <= 0 or self.calls >= self.plan["bounds"]["max_requests"]:
            raise fail("canary-bound-reached", "Client request/deadline cap reached; remote processing may continue.", partial=bool(self.puts))
        file_url = url.startswith(self.files_prefix + "?")
        allowed = method == "GET" and (
            url in self.arm_urls or url == self.source_url or file_url
            or self.index_url is not None and (url == self.index_url or url.startswith(self.index_url.split("?")[0] + "/docs?"))
        )
        if method == "PUT" and url == self.source_url and self.puts == 0 and kwargs.get("headers", {}).get("If-None-Match") == "*":
            allowed = True
            self.puts += 1
        elif method == "POST" and file_url and self.uploads == 0:
            allowed = True
            self.uploads += 1
        if not allowed:
            raise fail("canary-operation-forbidden", "Only exact resource GETs, one conditional source PUT and one selected upload are approved.", partial=bool(self.puts))
        self.calls += 1
        kwargs.update(follow_redirects=False, max_response_bytes=min(524288, kwargs.get("max_response_bytes", 524288)),
                      response_deadline=min(self.deadline, kwargs.get("response_deadline", self.deadline)),
                      timeout=max(0.01, min(float(kwargs.get("timeout", 60)), remaining)))
        try:
            response = self.raw(method, url, token, **kwargs)
        except HelperFailure as failure:
            failure.recovery_deadline = min(self.deadline, failure.recovery_deadline or self.deadline)
            raise
        if method == "POST" and response.status in (200, 201, 202):
            try:
                self.record("upload-http-ack", {"status": response.status, "request_id": response.request_id,
                                               "ingestion": "not yet verified"})
            except HelperFailure as error:
                # Return the real ACK: persistence is not an ambiguous upload.
                self.upload_ack_failure = error
        return search_reconcile.HttpResult(
            response.status, response.body, response.headers, response.etag_values,
            min(self.deadline, response.recovery_deadline or self.deadline),
            self.upload_ack_failure,
        )


def execute(document, *, token_provider=azure_cli_token, transport=http_request, now=time.time,
            clock=time.monotonic, sleep=time.sleep):
    if not isinstance(document, dict):
        raise fail("canary-input-invalid", "Canary execution requires an object envelope.")
    require_allowed_fields(document, {"schema_version", "plan", "approval", "_computed_fingerprint"}, label="canary envelope")
    if document.get("schema_version") != "1.0":
        raise fail("canary-input-invalid", "Use canary envelope schema_version 1.0.")
    plan = document.get("plan")
    if not isinstance(plan, dict):
        raise fail("canary-input-invalid", "Use the unchanged canary execution envelope.")
    require_allowed_fields(plan, {"operation", "version", "file_plan", "marker", "content_field", "ocr_mapping", "bounds",
                                  "receipt_directory", "created_at", "expires_at", "disclosure"}, label="canary plan")
    fingerprint = digest(plan)
    if document.get("approval") != {"confirmed": True, "fingerprint": fingerprint} or document.get("_computed_fingerprint") != fingerprint:
        raise fail("approval-missing", "Exact canary scope, synthetic content/cost and bounded verification need unchanged fingerprinted approval.")
    if (
        plan.get("operation") != "validate-file-cu-mi" or plan.get("version") != "1.1"
        or plan.get("disclosure") != DISCLOSURE or not isinstance(plan.get("content_field"), str)
        or not FIELD.fullmatch(plan["content_field"])
        or type(plan.get("created_at")) is not int or type(plan.get("expires_at")) is not int
        or plan["expires_at"] - plan["created_at"] != 900 or not plan["created_at"] <= now() < plan["expires_at"]
    ):
        raise fail("canary-plan-stale", "Canary plan is invalid or outside its 15-minute approval window; refresh discovery.")
    _bounds(plan.get("bounds"))
    _file_contract(plan["file_plan"], plan["marker"])
    if plan.get("ocr_mapping") != _ocr_mapping(plan["file_plan"]["source"]["api_version"], plan["content_field"]):
        raise fail("canary-ocr-mapping-stale", "The approved OCR mapping differs from the pinned helper contract; a fresh plan and approval are required.")
    directory = _bootstrap_io.private_directory(plan["receipt_directory"])
    prefix = "cu-mi-" + fingerprint.split(":")[1][:16]
    refs = []

    def record(stage, value):
        path = _bootstrap_io.private_file(directory, prefix + "-" + stage + ".json", {
            "fingerprint": fingerprint, "stage": stage, "value": value,
        })
        refs.append(str(path))

    record("started", {"approved_input": {k: v for k, v in document.items() if k != "_computed_fingerprint"},
                       "state": "No Azure mutation yet; later completion is not atomic."})
    bounded = BoundedTransport(plan, transport, clock, record)
    fp = plan["file_plan"]
    child_digest = digest(fp)
    source_result = None
    def source_ack(**evidence):
        response = evidence["response"]
        record("source-http-ack", {"status": response.status, "request_id": response.request_id,
                                   "etag_evidence": search_reconcile.response_etags(response)})

    try:
        source_result = file_source.execute(
            {"schema_version": "1.0", "plan": fp, "_computed_fingerprint": child_digest,
             "approval": {"confirmed": True, "fingerprint": child_digest}},
            token_provider=token_provider, transport=bounded, mi_on_created=source_ack,
            allow_upload_retry=False,
        )
        if bounded.upload_ack_failure is not None:
            raise bounded.upload_ack_failure
        record("file-completed", source_result)
        original_file = _verified_file(source_result, fp["ingestion"])
        mapping = plan["ocr_mapping"]
        token = token_provider(SEARCH_AUDIENCE)
        current, _ = search_reconcile.read_resource(bounded.source_url, token, transport=bounded)
        file_source.verify_content_understanding_readback(fp["content_understanding"], current)
        created = current.get("fileParameters", {}).get("createdResources")
        if not isinstance(created, dict) or set(created) != {"index"} or not isinstance(created["index"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,127}", created["index"]):
            raise fail("canary-index-unverified", "Fresh File readback must identify exactly one generated index.")
        retained = source_result["verification"]["readback"]["source"]
        if current.get("@odata.etag") != retained["etag"] or not search_reconcile.definitions_match(fp["source"]["desired"], current):
            raise fail("canary-source-drift", "Source version changed before indexed OCR verification.")
        version = fp["source"]["api_version"]
        bounded.index_url = f"{fp['source']['endpoint'].rstrip('/')}/indexes('{created['index']}')?api-version={version}"
        index, _ = search_reconcile.read_resource(bounded.index_url, token, transport=bounded)
        if not isinstance(index, dict) or index.get("name") != created["index"] or not isinstance(index.get("@odata.etag"), str) or not index["@odata.etag"]:
            raise fail("canary-index-unverified", "Require the generated index's matching name and fresh ETag.")
        _verify_index_fields(index, mapping)
        query = bounded.index_url.split("?")[0] + "/docs?" + urlencode({
            "api-version": version, "search": "*",
            "$select": ",".join((mapping["field"], mapping["parent_field"], mapping["path_field"])), "$top": 3,
        })
        matched = False
        for attempt in range(plan["bounds"]["max_poll_attempts"]):
            response = bounded("GET", query, token)
            if response.status != 200 or not isinstance(response.body, dict) or not isinstance(response.body.get("value"), list):
                raise fail("canary-index-query-failed", "Generated-index query did not return bounded document rows.",
                           request_id=response.request_id, status=response.status)
            rows = response.body["value"]
            if len(rows) > 3:
                raise fail("canary-index-query-failed", "Generated-index response exceeded the approved row cap.")
            if any(
                not isinstance(row, dict) or not isinstance(row.get(mapping["field"]), str)
                or row.get(mapping["parent_field"]) != original_file["fileId"]
                or row.get(mapping["path_field"]) != original_file["fileName"]
                for row in rows
            ):
                raise fail("canary-document-binding-unverified", "Indexed rows must contain canonical OCR text and the uploaded file's exact parent ID/path; chunk IDs or metadata alone are not proof.")
            matched = any(_contains_marker(row[mapping["field"]], plan["marker"]) for row in rows)
            if matched:
                break
            if attempt + 1 < plan["bounds"]["max_poll_attempts"]:
                sleep(min(plan["bounds"]["poll_interval_seconds"], max(0, bounded.deadline - clock())))
        if not matched:
            raise fail("canary-ocr-unverified", "Upload/source creation is not extraction proof: indexed OCR marker was not observed within the caps.")
        after, _ = search_reconcile.read_resource(bounded.source_url, token, transport=bounded)
        if not isinstance(after, dict) or after.get("@odata.etag") != current.get("@odata.etag") or after.get("fileParameters", {}).get("createdResources") != created:
            raise fail("canary-source-drift", "Generated source/index binding changed during OCR verification.")
        final_index, _ = search_reconcile.read_resource(bounded.index_url, token, transport=bounded)
        if final_index != index:
            raise fail("canary-index-drift", "Generated index changed during OCR verification.")
        binding, _ = file_cu_mi.read_binding(fp["content_understanding"], fp["source"]["endpoint"],
                                             token_provider=token_provider, transport=bounded)
        if binding != fp["cu_identity_state"]:
            raise fail("canary-identity-drift", "Search/CU identity-role binding changed during validation.")
        result = {**copy.deepcopy(source_result), "outcome": "validate-file-cu-mi",
                  "approved_plan": {"fingerprint": fingerprint, "confirmed": True},
                  "status": "completed", "verdict": "keyless-functional-pass", "indexed_ocr_marker": True,
                  "principal_attribution": "unverified", "backend_rollout": "unverified",
                  "identity_evidence": fp["cu_identity_state"], "source_result": source_result,
                  "ocr_evidence": {"mapping": mapping, "file": original_file},
                  "index": created["index"], "request_count": bounded.calls,
                  "cleanup": {"status": "separate-plan-and-approval-required",
                              "instructions": "Retain inventory; separately approved guarded source cleanup only."},
                  "warnings": ["Functional evidence is for this run only, not an atomic deployment or release claim.",
                               "No backend CU principal/telemetry was observed."]}
    except HelperFailure as error:
        if bounded.upload_ack_failure is not None and error is not bounded.upload_ack_failure:
            checkpoint_error = bounded.upload_ack_failure
            checkpoint_error.writes = error.writes
            checkpoint_error.resources_remaining = error.resources_remaining
            checkpoint_error.resources_reused = error.resources_reused
            checkpoint_error.resources_unverified = error.resources_unverified
            checkpoint_error.warnings.extend(error.warnings)
            checkpoint_error.partial = error.partial
            error = checkpoint_error
        if source_result is not None:
            error.partial = True
            error.writes = [
                {**resource, "action": "created", "type": resource.get("type", "knowledge-source-file")}
                for resource in source_result["resources"]["created"]
            ] + error.writes
            error.resources_remaining = source_result["ownership"]["run_owned"] + error.resources_remaining
        result = blocked_result(error, outcome="validate-file-cu-mi", fingerprint=fingerprint, owner=fp["owner"])
        result.update(verdict="unverified", indexed_ocr_marker=False, principal_attribution="unverified",
                      backend_rollout="unverified", request_count=bounded.calls)
        result.setdefault("warnings", []).append("Remote processing/costs may continue; do not replay mutations or infer ownership from an ambiguous create.")
        if bounded.upload_ack_failure is not None:
            result["warnings"].append("Upload HTTP ACK could not be retained; validation stopped. Only listed receipt_refs are confirmed; do not replay the upload.")
    try:
        record("result", result)
    except HelperFailure:
        if result["status"] == "completed":
            error = fail("canary-receipt-failed", "Validation finished but its final private receipt could not be persisted.", partial=True)
            error.writes = [
                {**resource, "action": "created", "type": resource.get("type", "knowledge-source-file")}
                for resource in source_result["resources"]["created"]
            ]
            error.resources_remaining = source_result["ownership"]["run_owned"]
            result = {**blocked_result(error, outcome="validate-file-cu-mi", fingerprint=fingerprint, owner=fp["owner"]),
                      "indexed_ocr_marker": True, "principal_attribution": "unverified", "backend_rollout": "unverified",
                      "source_result": source_result, "request_count": bounded.calls}
        result["verdict"] = "unverified"
        result.setdefault("warnings", []).append("Final private receipt persistence failed; retain this ownership handoff and existing checkpoints. Do not replay.")
    return {**result, "receipt_refs": refs}


def main(argv=None):
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", metavar="EXISTING_PRIVATE_DIRECTORY")
    modes.add_argument("--plan", type=Path)
    modes.add_argument("--input", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.prepare:
            result = prepare(args.prepare)
        elif args.plan:
            result = plan_canary(_bootstrap_io.read_json(args.plan))
            directory = result["execution_input"]["plan"]["receipt_directory"]
            path = _bootstrap_io.private_file(directory, "cu-mi-plan-" + result["plan_fingerprint"].split(":")[1][:16] + ".json",
                                               result["execution_input"])
            result = {k: v for k, v in result.items() if k != "execution_input"}
            result["execution_input_ref"] = str(path)
        else:
            document, _, fingerprint = load_approved_input(args.input)
            document["_computed_fingerprint"] = fingerprint
            result = execute(document)
        emit_result(result)
        return 0 if result["status"] in ("prepared", "planned", "completed") else 3 if result["status"] == "partial" else 2
    except HelperFailure as error:
        emit_result(blocked_result(error, outcome="validate-file-cu-mi", fingerprint=None, owner=None))
        return 3 if error.partial else 2


if __name__ == "__main__":
    sys.exit(main())
