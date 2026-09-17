"""Offline, bounded inspection of retained Search retrieval evidence; no transport."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_INPUT_BYTES = 1024 * 1024
MAX_DEPTH = 48
MAX_ITEMS = 1000
VERSIONS = {"2026-04-01", "2026-08-01-preview"}


class EvidenceError(ValueError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise EvidenceError(code)


def _pairs(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate-json-key")
        result[key] = value
    return result


def parse(text: str) -> Any:
    # Bound nesting before the JSON decoder allocates containers or recurses.
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            require(depth <= MAX_DEPTH, "json-depth-exceeded")
        elif char in "]}":
            depth -= 1
    try:
        return json.loads(text, object_pairs_hook=_pairs,
                          parse_constant=lambda _: require(False, "invalid-json-number"))
    except (ValueError, RecursionError) as exc:
        if isinstance(exc, EvidenceError):
            raise
        raise EvidenceError("invalid-json") from None


def load(path: Path, limit: int) -> Any:
    try:
        require(path.is_file() and not path.is_symlink(), "evidence-not-regular-file")
        with path.open("rb") as stream:
            payload = stream.read(limit + 1)
        require(len(payload) <= limit, "evidence-too-large")
        return parse(payload.decode("utf-8"))
    except (OSError, UnicodeError):
        raise EvidenceError("evidence-unreadable") from None


def obj(value: Any, fields: set[str] | None = None) -> dict:
    require(isinstance(value, dict), "object-required")
    if fields is not None:
        require(not (value.keys() - fields), "unknown-input-field")
    return value


def seq(value: Any) -> list:
    require(isinstance(value, list) and len(value) <= MAX_ITEMS, "array-missing-or-oversized")
    return value


def text(value: Any) -> str:
    require(isinstance(value, str) and bool(value.strip()), "nonempty-text-required")
    return value


def timestamp(value: Any) -> datetime:
    try:
        result = datetime.fromisoformat(text(value).replace("Z", "+00:00"))
        require(result.tzinfo is not None, "timestamp-zone-required")
        return result
    except ValueError as exc:
        if isinstance(exc, EvidenceError):
            raise
        raise EvidenceError("invalid-timestamp") from None


def evidence_path(root: Path, value: Any) -> Path:
    raw = text(value)
    require(not re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:", raw.lstrip())
            and not raw.lstrip().startswith(("//", "\\\\")),
            "evidence-path-url-not-supported")
    relative = Path(raw)
    require(not relative.is_absolute() and ".." not in relative.parts,
            "evidence-path-outside-bundle")
    path = root / relative
    require(path.resolve().is_relative_to(root.resolve()), "evidence-path-outside-bundle")
    require(not any(p.is_symlink() for p in [path, *path.parents] if p != root.parent),
            "evidence-link-not-supported")
    return path


class Audit:
    def __init__(self) -> None:
        self.findings: list[dict] = []
        self.diagnostics: list[dict] = []
        self.statuses: set[str] = set()
        self.snapshot_equal: bool | None = None
        self.cases: dict[str, dict] = {}
        self.first_failure: dict | None = None

    def add(self, code: str, where: str, status: str = "failed") -> None:
        self.statuses.add(status)
        if status == "failed" and self.first_failure is None:
            self.first_failure = {"code": code, "at": where, "status": status}
        if len(self.findings) < 40:
            self.findings.append({"code": code, "at": where, "status": status})

    def diagnostic(self, value: Any, where: str, kind: str) -> None:
        # Retain exact first error/warning in the input artifact, not in public output.
        digest = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        self.diagnostics.append({"at": where, "kind": kind, "sha256": digest})
        self.add("activity-" + kind, where, "failed" if kind == "error" else "unverified")

    def check_diagnostic(self, container: dict, field: str, where: str) -> None:
        if field not in container or container[field] is None:
            return
        value = container[field]
        if not isinstance(value, dict if field == "error" else str):
            self.add("diagnostic-shape-invalid", where)
        elif field == "error" or value != "":
            self.diagnostic(value, where, field)

    def result(self) -> dict:
        statuses = self.statuses
        structural = "failed" if "failed" in statuses else (
            "unverified" if "unverified" in statuses else "passed")
        return {
            "status": "blocked" if structural == "failed" else "review-required",
            "outcome": "retained-retrieval-audit", "structural_status": structural,
            "overall_pass": False, "mutation": "none", "writes_performed": [],
            "network_calls": 0, "model_calls": 0, "cleanup": "not-applicable",
            "before_after_snapshot_equal": self.snapshot_equal,
            "cases": self.cases,
            "findings": self.findings,
            "diagnostic_count": len(self.diagnostics), "diagnostics": self.diagnostics[:20],
            "first_issue": self.findings[0] if self.findings else None,
            "first_failure": self.first_failure,
            "first_error": next((d for d in self.diagnostics if d["kind"] == "error"), None),
            "first_warning": next((d for d in self.diagnostics if d["kind"] == "warning"), None),
            "unverified": ["semantic-answer-faithfulness", "semantic-abstention",
                           "live-evidence-provenance", "agent-invocation-proof"],
        }


def snapshot(value: Any, document: dict) -> dict:
    value = obj(value, {"captured_at", "endpoint", "api_version", "knowledge_base",
                        "knowledge_source", "original"})
    require(value.get("endpoint") == document["endpoint"]
            and value.get("api_version") == document["api_version"], "snapshot-target-mismatch")
    kb, source = obj(value.get("knowledge_base")), obj(value.get("knowledge_source"))
    require(kb.get("name") == document["knowledge_base_name"]
            and source.get("name") == document["source_name"]
            and source.get("kind") == document["source_kind"], "snapshot-resource-mismatch")
    text(kb.get("@odata.etag"))
    text(source.get("@odata.etag"))
    parameters = obj(source.get("fileParameters" if source["kind"] == "file"
                                else "azureBlobParameters"))
    obj(parameters.get("ingestionParameters"))
    if source["kind"] == "azureBlob":
        text(parameters.get("containerName"))
    require(kb.get("knowledgeSources") == [{"name": document["source_name"]}],
            "snapshot-source-selection-unsupported")
    obj(value.get("original"))
    timestamp(value.get("captured_at"))
    return value


def inspect_response(audit: Audit, retained: Any, mode: str, label: str,
                     document: dict, original: dict) -> None:
    retained = obj(retained)
    if "status" in retained and retained["status"] not in ("response-received", "blocked"):
        audit.add("retained-status-unsupported", label + "/status")
        return
    if "operation" in retained and retained["operation"] != "retrieve":
        audit.add("retained-operation-unsupported", label + "/operation")
        return
    status = retained.get("http_status")
    if retained.get("status") == "blocked":
        if not isinstance(retained.get("first_blocker"), dict):
            audit.add("retained-blocker-invalid", label + "/first_blocker")
        else:
            audit.diagnostic(retained["first_blocker"], label + "/first_blocker", "error")
        return
    if "first_blocker" in retained:
        audit.add("retained-blocker-without-blocked-status", label + "/first_blocker")
        return
    require(type(status) is int and 100 <= status <= 599, "http-status-missing-or-invalid")
    summary = {"http_status": status, "original_path_matches": 0,
               "declared_identity_value_matches": 0, "original_identity": "unverified",
               "original_identity_requirement": "fileId" if document["source_kind"] == "file" else "etag"}
    audit.cases[label] = summary
    if status != 200:
        audit.add("http-status-" + str(status), label + "/http_status")
    body = obj(retained.get("response_body"))
    audit.check_diagnostic(body, "error", label + "/response_body/error")
    activities = {}
    for i, activity in enumerate(seq(body.get("activity"))):
        activity = obj(activity)
        aid = activity.get("id")
        require(type(aid) is int and aid >= 0 and aid not in activities, "invalid-activity-id")
        activities[aid] = activity
        for field in ("error", "warning"):
            audit.check_diagnostic(activity, field, f"{label}/response_body/activity/{i}/{field}")
        if "knowledgeSourceName" in activity and (
            activity["knowledgeSourceName"] != document["source_name"]
            or activity.get("type") != document["source_kind"]
        ):
            audit.add("extraneous-source-activity", label)
    if not activities:
        audit.add("activity-evidence-missing", label, "unverified")
    if not any(a.get("knowledgeSourceName") == document["source_name"]
               and a.get("type") == document["source_kind"] for a in activities.values()):
        audit.add("selected-source-activity-missing", label, "unverified")
    references = {}
    expected = document["expected_source"]
    for i, reference in enumerate(seq(body.get("references"))):
        reference = obj(reference)
        rid = text(reference.get("id"))
        require(rid not in references, "duplicate-reference-id")
        references[rid] = reference
        where = f"{label}/response_body/references/{i}"
        aid = reference.get("activitySource")
        require(type(aid) is int, "invalid-reference-activity-id")
        activity = activities.get(aid, {})
        if activity.get("knowledgeSourceName") != document["source_name"]:
            audit.add("reference-source-unverified", where, "unverified")
        if reference.get("type") != document["source_kind"]:
            audit.add("citation-type-unsupported", where)
            continue
        native_path = "docName" if document["source_kind"] == "file" else "blobUrl"
        if reference.get(native_path) != expected["path"]:
            audit.add("original-path-missing-or-mismatch", where)
        else:
            summary["original_path_matches"] += 1
        # Native references do not promise a File ID or Blob ETag. Do not use
        # docKey, citationUrl, ref_id, sourceData.id, or chunk IDs as substitutes.
        binding = expected.get("identity_field")
        source_data = reference.get("sourceData")
        identity_key = "fileId" if document["source_kind"] == "file" else "etag"
        audit.add("original-identity-not-in-native-citation", where, "unverified")
        if binding:
            audit.add("operator-identity-binding-unverified", where, "unverified")
            if not isinstance(source_data, dict) or binding not in source_data:
                audit.add("declared-identity-value-missing", where, "unverified")
            elif source_data[binding] != original[identity_key]:
                audit.add("declared-identity-value-mismatch", where)
            else:
                summary["declared_identity_value_matches"] += 1

    used: list[str] = []
    extracts = 0
    blocks = 0
    for message in seq(body.get("response")):
        for content in seq(obj(message).get("content")):
            content = obj(content)
            require(content.get("type") == "text", "response-content-type-unsupported")
            value = text(content.get("text"))
            blocks += 1
            if mode == "extractiveData":
                rows = seq(parse(value))
                extracts += len(rows)
                for row in rows:
                    row = obj(row)
                    used.append(text(row.get("ref_id")))
                    if not any(isinstance(v, str) and v.strip()
                               for k, v in row.items() if k != "ref_id"):
                        audit.add("extract-payload-missing", label)
            else:
                markers = re.findall(r"\[ref_id:([^\]\r\n]+)\]", value)
                if value.count("[ref_id:") != len(markers):
                    audit.add("malformed-citation-marker", label)
                used.extend(markers)
    if not blocks:
        audit.add("response-payload-missing", label, "unverified")
    if len(used) > MAX_ITEMS:
        raise EvidenceError("citation-count-exceeded")
    if mode == "extractiveData" and len(used) != len(set(used)):
        audit.add("duplicate-extract-reference-id", label)
    if set(used) - references.keys():
        audit.add("unknown-citation-id", label)
    if label == "customer" and not used:
        audit.add("customer-grounding-missing", label)
    if label == "unrelated":
        if mode == "extractiveData" and (extracts or references):
            audit.add("unrelated-support-returned", label)
        elif mode == "answerSynthesis" and used:
            audit.add("unrelated-answer-citations-require-review", label, "unverified")
        elif mode == "answerSynthesis":
            audit.add("no-citations-is-not-semantic-abstention", label, "unverified")
    summary.update(response_blocks=blocks, extracts=extracts if mode == "extractiveData" else None,
                   references=len(references), used_citations=len(used),
                   no_support_shape=(blocks > 0 and not extracts and not references)
                   if mode == "extractiveData" else "semantic-review-required")


def verify(document: Any, root: Path, *, now: datetime | None = None) -> dict:
    audit = Audit()
    where = "input"
    try:
        document = obj(document, {"schema_version", "endpoint", "api_version",
                                 "knowledge_base_name", "source_name", "source_kind",
                                 "expected_source", "before", "after", "customer", "unrelated"})
        require(document.get("schema_version") == "1.0", "unsupported-schema")
        require(text(document.get("api_version")) in VERSIONS, "unsupported-api")
        require(text(document.get("source_kind")) in {"file", "azureBlob"}, "unsupported-source")
        for name in ("endpoint", "knowledge_base_name", "source_name"):
            text(document.get(name))
        expected = obj(document.get("expected_source"), {"path", "file_id", "etag",
                                                        "identity_field"})
        text(expected.get("path"))
        if "identity_field" in expected:
            binding = text(expected["identity_field"])
            require(binding not in {"id", "docKey", "ref_id", "chunk_id", "chunkId"},
                    "chunk-identity-binding-forbidden")
        before = snapshot(load(evidence_path(root, document.get("before")), MAX_INPUT_BYTES), document)
        after = snapshot(load(evidence_path(root, document.get("after")), MAX_INPUT_BYTES), document)
        start, end = timestamp(before["captured_at"]), timestamp(after["captured_at"])
        now = now or datetime.now(timezone.utc)
        require(start <= end <= now and (now - start).total_seconds() <= 3600,
                "stale-or-unordered-snapshots")
        audit.snapshot_equal = all(before[key] == after[key] for key in (
            "knowledge_base", "knowledge_source", "original"))
        for key in ("knowledge_base", "knowledge_source", "original"):
            if before[key] != after[key]:
                audit.add("before-after-definition-or-original-changed", key)
        original = before["original"]
        if document["source_kind"] == "file":
            require(original.get("fileName") == expected["path"]
                    and text(original.get("fileId")) == text(expected.get("file_id"))
                    and "errorMessage" in original and original["errorMessage"] is None,
                    "original-file-inventory-mismatch")
            require(timestamp(original.get("lastUpdatedAt")) <= start,
                    "original-version-after-snapshot")
        else:
            require(original.get("url") == expected["path"]
                    and text(original.get("etag")) == text(expected.get("etag")),
                    "original-blob-inventory-mismatch")
        kb = before["knowledge_base"]
        if document["api_version"] == "2026-04-01":
            require("outputMode" not in kb and "retrievalReasoningEffort" not in kb,
                    "ga-preview-fields-not-supported")
            require(document["source_kind"] == "azureBlob" and not obj(
                before["knowledge_source"].get("azureBlobParameters", {})
            ).get("isADLSGen2"), "unsupported-ga-source")
            mode, effort = "extractiveData", "minimal"
        else:
            mode = kb.get("outputMode")
            effort = obj(kb.get("retrievalReasoningEffort")).get("kind")
        require(mode in {"extractiveData", "answerSynthesis"}
                and effort in {"minimal", "low", "medium"}, "unsupported-mode")
        if mode == "answerSynthesis" or effort != "minimal":
            require(bool(seq(kb.get("models"))), "model-definition-missing")
        queries = []
        for label in ("customer", "unrelated"):
            where = label
            case = obj(document.get(label), {"query", "approved", "basis", "request",
                                             "response", "captured_at"})
            query = text(case.get("query"))
            queries.append(query)
            require(case.get("approved") is True, "question-not-approved")
            require(case.get("basis") in ({"title", "content"} if label == "customer"
                                         else {"unrelated"}), "question-basis-invalid")
            require(start <= timestamp(case.get("captured_at")) <= end,
                    "response-outside-snapshot-window")
            request = ({"intents": [{"type": "semantic", "search": query}]} if effort == "minimal"
                       else {"messages": [{"role": "user", "content": [{"type": "text", "text": query}]}]})
            require(case.get("request") == request, "retained-request-mismatch-or-override")
            retained = load(evidence_path(root, case.get("response")), MAX_RESPONSE_BYTES)
            inspect_response(audit, retained, mode, label, document, original)
        require(queries[0] != queries[1], "paired-questions-must-differ")
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        code = str(exc) if isinstance(exc, EvidenceError) else "evidence-schema-invalid"
        audit.add(code, where)
    return audit.result()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify(load(args.input, MAX_INPUT_BYTES), args.input.parent)
    except EvidenceError as exc:
        audit = Audit()
        audit.add(str(exc), "input")
        result = audit.result()
    print(json.dumps(result, sort_keys=True))
    return 2 if result["status"] == "blocked" else 0


if __name__ == "__main__":
    sys.exit(main())
