"""Synchronous File batches; one in-operation queue-429 retry, never unknown-outcome replay."""
from __future__ import annotations

import argparse
import copy
import hashlib
import re
import sys
import time
import uuid
from dataclasses import replace
from pathlib import Path

try:
    from . import _bootstrap_io as private_io, cu_ingestion_auth, file_ingest, search_reconcile
    from ._common import (HelperFailure, ReadRecovery, RetryAfter, RetryAfterTiming, SEARCH_AUDIENCE,
                          retry_after_timing, retry_after_not_before, valid_utc_timestamp, azure_cli_token, blocked_result,
                          digest, emit_result, http_request, load_approved_input, reject_secrets, require_allowed_fields)
    from ._progress import Progress, add_progress_argument, reporting
except ImportError:
    import _bootstrap_io as private_io, cu_ingestion_auth, file_ingest, search_reconcile
    from _common import (HelperFailure, ReadRecovery, RetryAfter, RetryAfterTiming, SEARCH_AUDIENCE,
                         retry_after_timing, retry_after_not_before, valid_utc_timestamp, azure_cli_token, blocked_result,
                         digest, emit_result, http_request, load_approved_input, reject_secrets, require_allowed_fields)
    from _progress import Progress, add_progress_argument, reporting


RETAIN = " Retain the source and evidence; no creation replay, reset, deletion or new roles."
UPLOAD_TIMEOUT = 180
MAX_BACKOFF_RECORDS = 200


def _rejected(status):
    return type(status) is int and 400 <= status < 500 and status not in (408, 409)


def fail(code, message):
    return HelperFailure(code, message + RETAIN, blocked_at="file-upload-resume")


class Session:
    def __init__(self, directory, document=None, *, context_provider=cu_ingestion_auth.account_context):
        self.directory = private_io.validate_private_artifact_directory(str(directory))
        self.context_provider = context_provider
        self.records = {}
        self.network_failure = None
        self.active_attempt = None
        if document is not None:
            self._validate_document(document)
            if any(self.directory.iterdir()):
                raise fail("file-upload-journal-exists", "Use a new empty private receipt directory for original creation.")
            context = context_provider()
            cu_ingestion_auth.validate_context(context)
            self.seed = {"document": {key: copy.deepcopy(document[key]) for key in ("schema_version", "plan", "approval")},
                         "context": context, "backoff_version": "1.0"}
            self._write("run.json", self.seed)
        else:
            self._load()
            self.seed = self.records["run.json"]
            self._validate_document(self.seed["document"])
            cu_ingestion_auth.validate_context(self.seed["context"])
        self.document = self.seed["document"]
        self.plan = self.document["plan"]
        self.ingestion = self.plan["ingestion"]

    @staticmethod
    def _validate_document(document):
        try:
            from . import file_source
        except ImportError:
            import file_source
        if (not isinstance(document, dict) or document.get("schema_version") != "1.0"
                or not isinstance(document.get("plan"), dict)
                or "_computed_fingerprint" in document and document["_computed_fingerprint"] != digest(document.get("plan"))
                or not isinstance(document.get("approval"), dict) or document["approval"].get("confirmed") is not True
                or document.get("approval") != {"confirmed": True, "fingerprint": digest(document.get("plan"))}):
            raise fail("file-upload-approval-missing", "Original unchanged File creation approval is required.")
        require_allowed_fields(document, {"schema_version", "plan", "approval", "_computed_fingerprint"}, label="original File envelope")
        file_source._validate_plan(document["plan"])
        if document["plan"]["source"]["action"] != "create":
            raise fail("file-upload-provenance-missing", "This continuation is only for original acknowledged creation, not generic reuse.")

    def _write(self, name, payload):
        value = {"schema_version": "1.0", "kind": "file-upload-journal", "payload": payload, "integrity": digest(payload)}
        reject_secrets(value)
        try:
            private_io.atomic_private_file(self.directory, name, value, max_bytes=private_io.MAX_BYTES)
        except HelperFailure as error:
            raise HelperFailure("file-upload-receipt-failed", "Private upload evidence persistence failed." + RETAIN,
                                blocked_at="local-persistence", warnings=error.warnings) from error
        self.records[name] = copy.deepcopy(payload)

    def _load(self):
        # Reuse the existing bounded, private, no-link evidence reader.
        try:
            from .blob_recheck import read_private
        except ImportError:
            from blob_recheck import read_private
        try:
            paths = list(self.directory.iterdir())
        except OSError as error:
            raise fail("file-upload-evidence-unreadable", "Original upload evidence is inaccessible.") from error
        if len(paths) > 803 + MAX_BACKOFF_RECORDS or not {"run.json", "source-ack.json"}.issubset({p.name for p in paths}):
            raise fail("file-upload-provenance-missing", "Necessary original ACK and journal were not retained.")
        for path in paths:
            if (path.name not in {"run.json", "source-ack.json", "pending-request.json"}
                    and not re.fullmatch(r"(?:[0-9]{4}-(retry-)?(attempt|result)|backoff-[0-9]{4})\.json", path.name)):
                raise fail("file-upload-evidence-invalid", "Unexpected or incomplete journal entry; do not discard it to resume.")
            value = read_private(path)
            if (set(value) != {"schema_version", "kind", "payload", "integrity"}
                    or value["schema_version"] != "1.0" or value["kind"] != "file-upload-journal"
                    or value["integrity"] != digest(value["payload"])):
                raise fail("file-upload-evidence-invalid", "Original private upload evidence changed.")
            self.records[path.name] = value["payload"]
        seed = self.records["run.json"]
        if (not isinstance(seed, dict) or set(seed) not in ({"document", "context"}, {"document", "context", "backoff_version"})
                or "backoff_version" in seed and seed["backoff_version"] != "1.0"):
            raise fail("file-upload-evidence-invalid", "Original approval/context evidence is incomplete.")

    def acknowledge(self, metadata):
        self._write("source-ack.json", {"original_plan_digest": digest(self.plan),
                                       "source_url": search_reconcile.resource_url(self.plan["source"]),
                                       "acknowledgement": metadata})

    def require_ack(self):
        value = self.records.get("source-ack.json")
        if (not isinstance(value, dict) or set(value) != {"original_plan_digest", "source_url", "acknowledgement"}
                or value["original_plan_digest"] != digest(self.plan)
                or value["source_url"] != search_reconcile.resource_url(self.plan["source"])):
            raise fail("file-upload-provenance-missing", "An original acknowledged conditional source creation must be retained.")
        ack = value["acknowledgement"]
        if (not isinstance(ack, dict) or set(ack) != {"status", "request_id", "etag_evidence"}
                or ack["status"] not in (200, 201) or not ack["request_id"]
                or not isinstance(ack["request_id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", ack["request_id"])
                or not isinstance(ack["etag_evidence"], dict) or set(ack["etag_evidence"]) != {"body", "headers"}
                or not isinstance(ack["etag_evidence"]["headers"], list)):
            raise fail("file-upload-provenance-missing", "Original successful creation ACK/request ID is required, not GET ownership.")
        etag = search_reconcile.resolve_etag(ack["etag_evidence"], ack["request_id"])
        if not etag:
            raise fail("file-upload-provenance-missing", "The original creation ACK lacks version proof; GET cannot supply it.")
        return etag

    def states(self):
        states = []
        events = self.backoff_events()
        allowed = {"run.json", "source-ack.json", "pending-request.json"} | set(events)
        pending = self.records.get("pending-request.json")
        if "pending-request.json" in self.records and (
            not isinstance(pending, dict) or set(pending) != {"version", "plan_digest", "nonce", "method", "url_digest"}
            or pending["version"] != "1.0" or pending["plan_digest"] != digest(self.plan)
            or not isinstance(pending["nonce"], str) or not re.fullmatch(r"[0-9a-f]{32}", pending["nonce"])
            or pending["method"] not in ("GET", "POST", "PUT", "HEAD")
            or not isinstance(pending["url_digest"], str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", pending["url_digest"])
        ):
            raise fail("file-upload-evidence-invalid", "Pending request evidence is invalid.")
        for index, record in enumerate(self.ingestion["files"]):
            state = {"upload": "not_attempted", "request_ids": [], "ingested": False}
            for retry in (False, True):
                prefix = f"{index:04}-" + ("retry-" if retry else "")
                attempt_name, result_name = prefix + "attempt.json", prefix + "result.json"
                allowed.update((attempt_name, result_name))
                attempt, result = self.records.get(attempt_name), self.records.get(result_name)
                expected = self._attempt_record(index, retry=retry) if attempt is not None else None
                if attempt is not None and attempt != expected or result is not None and attempt is None:
                    raise fail("file-upload-evidence-invalid", "Upload attempt evidence does not bind the original source/corpus.")
                if attempt is not None:
                    state.update(upload="unverified", ingested=False)
                    state.pop("file_proof", None)
                    state.pop("ack_file_id", None)
                if result is not None:
                    if (not isinstance(result, dict) or not {"upload", "status", "request_id"} <= set(result)
                            or set(result) - {"upload", "status", "request_id", "file_proof", "file_id", "throttle_event"}
                            or not isinstance(result["upload"], str)
                            or result["upload"] not in {"accepted", "rejected", "unverified"}
                            or result["upload"] == "accepted" and result["status"] not in (200, 201)
                            or result["upload"] == "rejected" and not _rejected(result["status"])
                            or result["status"] is not None and (type(result["status"]) is not int or not 100 <= result["status"] <= 599)
                            or result["request_id"] is not None and ReadRecovery.safe_id(result["request_id"]) != result["request_id"]):
                        raise fail("file-upload-evidence-invalid", "Upload result is not an original supported ACK or failure.")
                    linked = [event for event in events.values() if event["attempt"] == attempt_name]
                    if "throttle_event" in result:
                        if (result["status"] != 429 or len(linked) != 1
                                or result["throttle_event"] != digest(linked[0])
                                or result["request_id"] != linked[0]["request_id"]):
                            raise fail("file-upload-evidence-invalid", "Upload 429 timing does not bind its original attempt/result.")
                    elif result["status"] == 429 and self.seed.get("backoff_version") is not None:
                        raise fail("file-upload-evidence-invalid", "Required original upload 429 timing evidence is missing.")
                    if "file_id" in result:
                        if result["upload"] != "accepted" or not _file_id(result["file_id"]):
                            raise fail("file-upload-evidence-invalid", "Original upload ACK file identity is invalid.")
                        state["ack_file_id"] = result["file_id"]
                    proof = result.get("file_proof")
                    if proof is not None:
                        if (result["upload"] != "accepted" or not isinstance(proof, dict)
                                or set(proof) != {"file_id", "record_digest"} or not _file_id(proof["file_id"])
                                or proof["record_digest"] != digest(record)
                                or result.get("file_id", proof["file_id"]) != proof["file_id"]):
                            raise fail("file-upload-evidence-invalid", "Persisted File completion proof does not match the approved record.")
                        state.update(file_proof=proof, ingested=True)
                    state.update(upload=result["upload"], status=result["status"])
                    if result["request_id"]:
                        state["request_ids"].append(result["request_id"])
            states.append(state)
        if set(self.records) - allowed:
            raise fail("file-upload-evidence-invalid", "Upload journal contains records outside the approved corpus.")
        return states

    def _attempt_record(self, index, *, retry=False):
        record = {
            "original_plan_digest": digest(self.plan), "record_digest": digest(self.ingestion["files"][index]),
            "creation_ack_digest": digest(self.records["source-ack.json"]),
        }
        if retry:
            rejection = self.records.get(f"{index:04}-result.json")
            if not isinstance(rejection, dict) or rejection.get("status") != 429 or rejection.get("upload") != "rejected":
                raise fail("file-upload-replay-forbidden", "A retry attempt requires the same operation's retained File upload 429.")
            record["rejected_result_digest"] = digest(rejection)
        return record

    def attempt(self, index, *, retry=False):
        prefix = f"{index:04}-" + ("retry-" if retry else "")
        self._write(prefix + "attempt.json", self._attempt_record(index, retry=retry))
        self.active_attempt = prefix + "attempt.json"

    def result(self, index, upload, status, request_id, *, retry=False, proof=None, file_id=None):
        prefix = f"{index:04}-" + ("retry-" if retry else "")
        event = {}
        if status == 429:
            linked = [value for value in self.backoff_events().values() if value["attempt"] == prefix + "attempt.json"]
            if len(linked) != 1:
                raise fail("file-upload-evidence-invalid", "Original upload 429 timing was not retained.")
            event["throttle_event"] = digest(linked[0])
        self._write(prefix + "result.json", {"upload": upload, "status": status,
                    "request_id": ReadRecovery.safe_id(request_id) if request_id else None,
                    **({"file_id": file_id} if file_id is not None else {}),
                    **({"file_proof": proof} if proof is not None else {}), **event})
        self.active_attempt = None

    def backoff_events(self):
        events = {key: self.records[key] for key in sorted(self.records) if key.startswith("backoff-")}
        if len(events) > MAX_BACKOFF_RECORDS:
            raise fail("file-upload-evidence-invalid", "Too many retained backoff records.")
        plan_digest = digest(self.plan)
        previous = None
        for index, (name, event) in enumerate(events.items()):
            if (name != f"backoff-{index:04}.json" or not isinstance(event, dict)
                    or set(event) != {"version", "plan_digest", "previous", "method", "url_digest",
                                      "attempt", "attempt_digest", "request_id", "metadata", "timing", "origin"}
                    or event["version"] != "1.0" or event["plan_digest"] != plan_digest
                    or event["previous"] != previous or event["method"] not in ("GET", "POST", "PUT", "HEAD")
                    or not isinstance(event["url_digest"], str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", event["url_digest"])
                    or event["request_id"] is not None and ReadRecovery.safe_id(event["request_id"]) != event["request_id"]
                    or event["origin"] not in ("response-headers", "native-http-error", "typed-metadata", "unavailable")):
                raise fail("file-upload-evidence-invalid", "Original backoff provenance is invalid or incomplete.")
            if event["attempt"] is not None:
                attempt = self.records.get(event["attempt"]) if isinstance(event["attempt"], str) else None
                if (attempt is None or not re.fullmatch(r"[0-9]{4}-(retry-)?attempt\.json", event["attempt"])
                        or event["attempt_digest"] != digest(attempt) or event["method"] != "POST"
                        or event["url_digest"] != digest(file_ingest._list_url(self.ingestion))):
                    raise fail("file-upload-evidence-invalid", "Backoff does not bind the original upload attempt.")
            elif event["attempt_digest"] is not None:
                raise fail("file-upload-evidence-invalid", "Backoff attempt provenance is inconsistent.")
            metadata, timing = event["metadata"], event["timing"]
            if (not isinstance(metadata, dict) or set(metadata) != {"kind", "value"}
                    or metadata["kind"] not in ("seconds", "date", "date-rfc850", "missing", "invalid", "overlong")
                    or not valid_utc_timestamp(metadata["value"])
                    or metadata["kind"] == "seconds" and (type(metadata["value"]) is not int or not 0 <= metadata["value"] <= 30)
                    or metadata["kind"] in ("missing", "invalid", "overlong") and metadata["value"] != 0
                    or not isinstance(timing, dict) or set(timing) != {"received_at_utc", "not_before_utc", "server_delay_seconds"}):
                raise fail("file-upload-evidence-invalid", "Retained Retry-After metadata is invalid.")
            received, deadline = timing["received_at_utc"], timing["not_before_utc"]
            seconds = timing["server_delay_seconds"]
            if (received is not None and not valid_utc_timestamp(received)
                    or deadline is not None and (received is None or not valid_utc_timestamp(deadline))
                    or seconds is not None and (type(seconds) is not int or not 0 <= seconds < 315537897600
                                               or metadata["kind"] not in ("seconds", "overlong"))
                    or metadata["kind"] == "seconds" and seconds not in (None, metadata["value"])):
                raise fail("file-upload-evidence-invalid", "Retained backoff UTC timing is invalid.")
            if deadline is not None:
                if (event["origin"] == "unavailable"
                        or event["origin"] == "typed-metadata" and metadata["kind"] not in ("seconds", "date", "date-rfc850")
                        or metadata["kind"] == "overlong" and (seconds is None or seconds <= 30 or deadline != received + seconds)
                        or metadata["kind"] != "overlong"
                        and deadline != retry_after_not_before(RetryAfter(**metadata), received)):
                    raise fail("file-upload-evidence-invalid", "Retained backoff deadline contradicts original metadata.")
            previous = digest(event)
        return events

    def backoff_status(self):
        events = self.backoff_events()
        attempts = {name: value for name, value in self.records.items()
                    if re.fullmatch(r"[0-9]{4}-(retry-)?(attempt|result)\.json", name)}
        if any(not isinstance(value, dict) for value in attempts.values()):
            raise fail("file-upload-evidence-invalid", "Attempt/result evidence is malformed.")
        # Legacy 429 or an interrupted receipt cannot prove what restriction was received.
        unknown = "pending-request.json" in self.records or any(
            name.endswith("result.json") and value.get("status") == 429 and "throttle_event" not in value
            or name.endswith("attempt.json") and name.replace("attempt.json", "result.json") not in self.records
            and name != self.active_attempt
            for name, value in attempts.items()
        )
        now = time.time()
        if unknown or any(event["timing"]["not_before_utc"] is None for event in events.values()):
            return {"status": "unresolved", "reason": "Original response timing is unavailable; no deadline is inferred."}
        if not events:
            return {"status": "clear"}
        if (not valid_utc_timestamp(now)
                or any(now < event["timing"]["received_at_utc"] for event in events.values())):
            return {"status": "unresolved", "reason": "UTC clock is invalid or precedes retained response receipt."}
        deadline = max(event["timing"]["not_before_utc"] for event in events.values())
        return {"status": "waiting" if now < deadline else "elapsed", "not_before_utc": deadline,
                "seconds_remaining": max(0, deadline - now)}

    def require_backoff(self):
        status = self.backoff_status()
        if status["status"] in ("waiting", "unresolved"):
            error = fail("file-upload-backoff-" + status["status"],
                         "Server backoff still applies; fresh approval does not waive it. "
                         + ("Wait until the retained UTC not-before time." if status["status"] == "waiting"
                            else "Original timing evidence or scoped operator recovery is required."))
            error.partial = "source-ack.json" in self.records
            error.file_batch = _summary(self.ingestion, self.states(), self)
            raise error

    def transport(self, raw):
        if getattr(raw, "_file_journal_owner", None) is self:
            return raw

        def invoke(method, url, token, **kwargs):
            if self.network_failure is not None:
                raise self.network_failure
            self.require_backoff()
            if len(self.backoff_events()) >= MAX_BACKOFF_RECORDS:
                raise fail("file-upload-backoff-limit", "Backoff journal limit reached; no more requests.")
            pending = {"version": "1.0", "plan_digest": digest(self.plan), "nonce": uuid.uuid4().hex,
                       "method": method, "url_digest": digest(url)}
            self._write("pending-request.json", pending)
            try:
                response = raw(method, url, token, **kwargs)
            except HelperFailure as error:
                if error.http_status == 429:
                    self.record_backoff(method, url, error, None)
                self.finish_request(error)
                raise
            if response.status == 429:
                error = HelperFailure("azure-http-error", "Azure request failed with HTTP 429.",
                                      blocked_at="execution", status=429, request_id=response.request_id,
                                      retry_after=response.retry_after, recovery_deadline=response.recovery_deadline)
                self.record_backoff(method, url, error, response.headers)
            try:
                self.finish_request()
            except HelperFailure as persistence:
                if method in ("PUT", "POST") and response.status in (200, 201):
                    return replace(response, ack_failure=persistence)
                raise
            return response

        invoke._file_journal_owner = self
        return invoke

    def finish_request(self, original=None):
        try:
            path = self.directory / "pending-request.json"
            expected = self.records["pending-request.json"]
            retained = private_io.read_json(path)
            if not isinstance(retained, dict) or retained.get("payload") != expected or retained.get("integrity") != digest(expected):
                raise fail("file-upload-evidence-invalid", "Pending request receipt changed.")
            path.unlink()
            self.records.pop("pending-request.json")
        except (OSError, HelperFailure) as cleanup:
            error = original or HelperFailure("file-upload-receipt-failed", "Pending request evidence could not be finalized.",
                                              blocked_at="local-persistence")
            error.blocked_at = "local-persistence"
            error.warnings.append("Pending request evidence remains unresolved; no further requests.")
            self.network_failure = error
            raise error from cleanup

    def record_backoff(self, method, url, error, headers):
        metadata = error.retry_after
        origin = "response-headers" if headers is not None else "native-http-error"
        timing = retry_after_timing(headers) if headers is not None else error.retry_after_timing
        if timing is None:
            received = time.time()
            received = received if valid_utc_timestamp(received) else None
            known = isinstance(metadata, RetryAfter) and metadata.kind in ("seconds", "date", "date-rfc850")
            timing = RetryAfterTiming(received, retry_after_not_before(metadata, received) if known else None,
                                      metadata.value if known and metadata.kind == "seconds" else None)
            origin = "typed-metadata" if known else "unavailable"
        if not isinstance(metadata, RetryAfter):
            metadata, origin = RetryAfter("missing"), "unavailable"
            timing = RetryAfterTiming(timing.received_at_utc, None)
        events = self.backoff_events()
        attempt = self.active_attempt if method == "POST" and url == file_ingest._list_url(self.ingestion) else None
        event = {"version": "1.0", "plan_digest": digest(self.plan),
                 "previous": digest(next(reversed(events.values()))) if events else None,
                 "method": method, "url_digest": digest(url), "attempt": attempt,
                 "attempt_digest": digest(self.records[attempt]) if attempt else None,
                 "request_id": ReadRecovery.safe_id(error.request_id) if error.request_id else None,
                 "metadata": metadata._asdict(), "timing": timing._asdict(), "origin": origin}
        try:
            self._write(f"backoff-{len(events):04}.json", event)
        except HelperFailure as persistence:
            error.blocked_at = "local-persistence"
            error.warnings.extend(persistence.warnings)
            error.warnings.append("Original HTTP 429 retained; backoff receipt persistence failed. No further requests.")
            self.network_failure = error
            raise error from persistence


def _file_id(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value) is not None


def _proof(plan, record, item):
    if isinstance(item, dict) and _file_id(item.get("fileId")) and file_ingest._matches(item, plan, record):
        return {"file_id": item["fileId"], "record_digest": digest(record)}
    return None


def _observe(plan, states, files):
    names = {record["path"] for record in plan["files"]}
    if any(item.get("fileName") not in names for item in files):
        raise fail("server-inventory-conflict", "File inventory contains an unapproved identity.")
    observed = {}
    for index, record in enumerate(plan["files"]):
        matches = [item for item in files if item.get("fileName") == record["path"]]
        if len(matches) > 1 or matches and not file_ingest._matches({**matches[0], "errorMessage": None}, plan, record):
            raise fail("file-record-conflict", "File inventory has duplicate or conflicting approved markers.")
        state = states[index]
        state["verification"] = {"accepted": "pending", "rejected": "failed"}.get(state["upload"], state["upload"])
        if matches:
            item = matches[0]
            proof = _proof(plan, record, item)
            if (proof and state.get("file_proof") and proof != state["file_proof"]
                    or state.get("ack_file_id") and item.get("fileId") is not None
                    and item["fileId"] != state["ack_file_id"]):
                raise fail("file-record-conflict", "Current File identity differs from the persisted upload ACK.")
            state["verification"] = ("failed" if state["upload"] == "rejected" and state.get("status") != 429
                                     or item.get("errorMessage") is not None else
                                     "confirmed" if proof else "unverified")
            state["ingested"] = state["verification"] == "confirmed"
            observed[index] = item
    return observed


def _summary(plan, states, session):
    counts = {name: 0 for name in ("accepted", "confirmed", "failed", "pending", "unverified", "not_attempted")}
    files = []
    for record, state in zip(plan["files"], states):
        counts["accepted"] += state["upload"] == "accepted"
        verification = state.get("verification", {"accepted": "pending", "rejected": "failed"}.get(state["upload"], state["upload"]))
        counts[verification] += 1
        files.append({"fileName": record["path"], "sha256": record["sha256"], "upload": state["upload"],
                      "verification": verification, "http_status": state.get("status"),
                      "request_ids": state["request_ids"][:3]})
    ingested = sum(bool(state.get("ingested")) for state in states)
    return {"counts": counts, "files": files, "ingested": ingested,
            "readiness": "ingested" if ingested == len(states) and counts["confirmed"] == len(states) else "partial",
            "retrieval": "unverified",
            **({"backoff": session.backoff_status()} if session else {}),
            **({"upload_retry": {
                "status": "blocked", "code": "file-upload-retry-safety-unproven",
                "reason": "Unknown upload outcomes cannot be replayed; only a received File upload 429 permits one bounded in-operation retry.",
            }} if counts["unverified"] else {}),
            "resume": ("Plan newly approved upload-only continuation for never-attempted files; uncertain attempts are never replayed."
                       if session else "Original durable ACK/attempt evidence was not retained; uploads cannot safely resume from GET alone."),
            "subset_handoff": "Report the proved ingested subset and remaining outcomes; subset isolation and KB retrieval are separate. KB changes need separate approval."}


def _progress(progress, plan, states):
    summary = _summary(plan, states, None)
    counts = summary["counts"]
    progress.update("file-upload", uploads_acknowledged=counts["accepted"], files_verified=counts["confirmed"],
                    files_ingested=summary["ingested"],
                    files_reused=sum(state["upload"] == "not_attempted" and state.get("verification") == "confirmed" for state in states),
                    files_failed=counts["failed"], files_unverified=counts["unverified"],
                    files_not_attempted=counts["not_attempted"], files_pending=counts["pending"])


def run_batch(document, *, token_provider, transport, progress, allow_new_uploads=False, session=None,
              eligible=None, source_check=None, allow_upload_retry=True):
    plan, fingerprint = document["plan"], document["_computed_fingerprint"]
    root, records = file_ingest._validate_plan(plan)
    states = session.states() if session else [{"upload": "not_attempted", "request_ids": []} for _ in records]
    if session:
        session.require_backoff()
        transport = session.transport(transport)
    created, reused, request_ids, warnings = [], [], [], []
    primary = None
    stopped = False
    retry_used = False
    readback_failed = False
    token = token_provider(SEARCH_AUDIENCE)
    url = file_ingest._list_url(plan)
    recovery = ReadRecovery(on_wait=progress.waiting)
    progress.update("file-inventory")
    try:
        before, ids = file_ingest._list_files(url, token, transport=transport, recovery=recovery)
        request_ids.extend(ids)
        if session is None and file_ingest.inventory_digest(before) != plan["expected_server_inventory_digest"]:
            raise fail("server-inventory-drift", "Approved initial file inventory changed.")
        observed = _observe(plan, states, before)
        if not allow_new_uploads and len(observed) != len(records):
            raise fail("reused-source-upload-forbidden", "Generic reuse cannot authorize new uploads.")
    except HelperFailure as failure:
        failure.file_batch = _summary(plan, states, session)
        failure.file_batch["request_ids"] = recovery.request_ids
        raise
    warnings.extend(recovery.warnings)
    eligible = set(range(len(records))) if eligible is None else set(eligible)
    after = None
    for index, record in enumerate(records):
        _progress(progress, plan, states)
        state = states[index]
        if index in observed:
            reused.append({"fileId": observed[index].get("fileId"), "fileName": record["path"], "sha256": record["sha256"]})
            continue
        if index not in eligible or state["upload"] != "not_attempted":
            continue
        try:
            path = file_ingest._resolve_file(root, record)
            content = path.read_bytes()
            if (len(content) != record["size"] or "sha256:" + hashlib.sha256(content).hexdigest() != record["sha256"]
                    or path.stat().st_mtime_ns != record["mtime_ns"]):
                raise fail("inventory-drift", "Approved corpus changed before upload.")
        except OSError:
            primary = primary or fail("inventory-unreadable", "Approved corpus became inaccessible.")
            warnings.append("Batch stopped: approved corpus became inaccessible.")
            stopped = True
            break
        except HelperFailure as failure:
            primary = primary or failure
            warnings.append(f"Batch stopped ({failure.code}); no further uploads were attempted.")
            stopped = True
            break
        body, boundary = file_ingest._multipart(plan, record, content, fingerprint)
        for attempt in range(2):
            try:
                if attempt:
                    file_ingest._resolve_file(root, record)
                if session:
                    session.attempt(index, retry=bool(attempt))
            except HelperFailure as failure:
                primary = primary or failure
                warnings.append(f"Upload attempt evidence/drift check failed ({failure.code}); no further requests.")
                stopped = True
                break
            state.update(upload="unverified", verification="unverified", status=None)
            _progress(progress, plan, states)
            response = None
            transport_failed = False
            try:
                with progress.processing_file(index + 1, len(records), attempt + 1):
                    response = transport("POST", url, token, body=body,
                                         headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                                         follow_redirects=False, timeout=UPLOAD_TIMEOUT,
                                         response_deadline=time.monotonic() + UPLOAD_TIMEOUT,
                                         max_response_bytes=1024 * 1024)
            except HelperFailure as caught:
                transport_failed = True
                failure = caught
                failure_status, failure_id = failure.http_status, failure.request_id
            else:
                failure_status, failure_id = response.status, response.request_id
                failure = HelperFailure("upload-failed", f"Upload returned HTTP {response.status}.",
                                        blocked_at="execution", status=response.status, request_id=response.request_id,
                                        retry_after=response.retry_after, recovery_deadline=response.recovery_deadline)
            if failure_id:
                safe_id = ReadRecovery.safe_id(failure_id)
                failure.request_id = safe_id
                state["request_ids"].append(safe_id)
                request_ids.append(safe_id)
            state["status"] = failure_status
            proof = None
            if failure_status in (200, 201):
                state.update(upload="accepted", verification="pending")
                created.append({"fileName": record["path"], "sha256": record["sha256"]})
                if response is not None:
                    proof = _proof(plan, record, response.body)
                    if isinstance(response.body, dict) and _file_id(response.body.get("fileId")):
                        state["ack_file_id"] = response.body["fileId"]
            elif _rejected(failure_status):
                state.update(upload="rejected", verification="failed")
            try:
                if response is not None and response.ack_failure is not None:
                    raise response.ack_failure
                if session:
                    session.result(index, state["upload"], failure_status, failure_id, retry=bool(attempt),
                                   proof=proof, file_id=state.get("ack_file_id"))
            except HelperFailure as persistence:
                primary = primary or (failure if failure_status not in (200, 201) else persistence)
                primary.warnings.extend(persistence.warnings)
                warnings.append("Upload journal persistence failed; no further requests were issued.")
                stopped = True
                break
            if failure_status in (200, 201) and not transport_failed:
                if proof:
                    state.update(file_proof=proof, ingested=True, verification="confirmed")
                elif isinstance(response.body, dict) and (
                    response.body.get("errorMessage") is not None
                    or "fileName" in response.body and not file_ingest._matches(response.body, plan, record)
                ):
                    primary = primary or fail("upload-metadata-unverified", "Upload ACK metadata conflicts with the approved file.")
                    stopped = True
                _progress(progress, plan, states)
                break
            primary = primary or failure
            if failure_status == 415:
                break
            _progress(progress, plan, states)
            if failure_status == 429 and not retry_used and allow_upload_retry and failure.blocked_at != "local-persistence":
                retry_used = True
                recovery = ReadRecovery(on_wait=progress.waiting)
                try:
                    recovery.delay(failure)
                    if source_check is not None:
                        source_check(recovery, token)
                    inventory, _ = file_ingest._list_files(url, token, transport=transport, recovery=recovery)
                    seen = _observe(plan, states, inventory)
                    if index in seen:
                        if state["verification"] != "confirmed":
                            raise fail("file-upload-retry-conflict", "Existing file does not prove the approved completed upload.")
                        created.append({"fileName": record["path"], "sha256": record["sha256"]})
                        break
                    file_ingest._resolve_file(root, record)
                    if time.monotonic() >= recovery.deadline:
                        raise fail("read-recovery-budget-exhausted", "Retry preflight exceeded its complete read budget.")
                    warnings.append("File upload HTTP 429: one same-operation retry after bounded backoff; no source recreation.")
                except HelperFailure as read_failure:
                    warnings.append(f"File retry stopped ({read_failure.code}; HTTP {read_failure.http_status}).")
                    warnings.extend(read_failure.warnings)
                    stopped = True
                finally:
                    request_ids.extend(recovery.request_ids)
                    warnings.extend(recovery.diagnostics())
                if not stopped:
                    continue
            else:
                stopped = True
                warnings.append(f"Batch stopped ({failure.code}; HTTP {failure_status}); no further uploads.")
                if failure.blocked_at != "local-persistence" and (
                    failure_status in (408, 409) or failure_status is None or failure_status >= 500
                ):
                    recovery = ReadRecovery(on_wait=progress.waiting)
                    try:
                        after, _ = file_ingest._list_files(url, token, transport=transport, recovery=recovery)
                        _observe(plan, states, after)
                        if state["verification"] == "confirmed":
                            created.append({"fileName": record["path"], "sha256": record["sha256"]})
                    except HelperFailure as read_failure:
                        warnings.append(f"File readback stopped ({read_failure.code}; HTTP {read_failure.http_status}).")
                        warnings.extend(read_failure.warnings)
                    request_ids.extend(recovery.request_ids)
                    warnings.extend(recovery.diagnostics())
            break
        if stopped:
            break
    if session:
        session.active_attempt = None
    _progress(progress, plan, states)
    progress.update("file-readback")
    if all(state["upload"] == "rejected" and state["verification"] != "confirmed" for state in states):
        stopped = True
    if after is None and not stopped:
        recovery = ReadRecovery(on_wait=progress.waiting)
        try:
            after, ids = file_ingest._list_files(url, token, transport=transport, recovery=recovery)
            _observe(plan, states, after)
        except HelperFailure as failure:
            primary = primary or failure
            readback_failed = True
            warnings.append(f"File readback stopped ({failure.code}; HTTP {failure.http_status}).")
        request_ids.extend(recovery.request_ids)
        warnings.extend(recovery.diagnostics())
    batch = _summary(plan, states, session)
    batch["request_ids"] = request_ids[:804]
    batch["upload_retry_used"] = retry_used
    progress.update("file-readback", files_verified=batch["counts"]["confirmed"], files_failed=batch["counts"]["failed"],
                    files_pending=batch["counts"]["pending"], files_unverified=batch["counts"]["unverified"],
                    files_not_attempted=batch["counts"]["not_attempted"], files_ingested=batch["ingested"])
    if batch["counts"]["confirmed"] != len(records) or readback_failed:
        failure = primary or fail("readback-mismatch", "Some approved files remain pending, failed or unverified.")
        uncertain = [{"action": "upload-unverified", "type": "knowledge-source-file",
                      "fileName": record["path"], "sha256": record["sha256"]}
                     for record, state in zip(records, states)
                     if state["upload"] == "unverified" and state["verification"] != "confirmed"]
        failure.writes = created + uncertain + failure.writes
        failure.resources_remaining = file_ingest._remaining_files(created) + uncertain + failure.resources_remaining
        failure.partial = bool(created) or any(s["upload"] == "unverified" for s in states) or (
            failure.partial and not _rejected(failure.http_status))
        failure.warnings.extend(warnings)
        failure.file_batch = batch
        raise failure
    verified = [{"fileId": item.get("fileId"), "fileName": record["path"], "sha256": record["sha256"], "size": record["size"]}
                for record in records for item in after or before if item.get("fileName") == record["path"]]
    return {"status": "completed", "outcome": plan.get("outcome", "file-knowledge-source-ingestion"),
            "approved_plan": {"fingerprint": fingerprint, "confirmed": True},
            "resources": {"created": created, "reused": reused, "updated": [], "skipped": []},
            "api_contracts": [{"operation": "upload-file", "version": file_ingest.API_VERSION, "preview": True}],
            "data_movement": {"boundary": {"local_root_digest": digest(str(root))}, "result": "Approved direct File uploads"},
            "auth": {"mode": "entra-user", "principals": []}, "rbac": plan.get("rbac", {"assignments": []}),
            "network": plan.get("network", {"posture": "preserved", "evidence": None}),
            "verification": {"readback": verified, "request_ids": request_ids, "server_inventory_digest": file_ingest.inventory_digest(after or before),
                             "idempotency": "Only a received File upload 429 permits one bounded same-operation retry; unknown outcomes are never replayed."},
            "warnings": warnings, "file_batch": batch,
            "ownership": {"run_owned": created, "reused_not_owned": reused, "owner": plan["owner"]},
            "cleanup": {"status": "not-requested", "separate_confirmation_required": True}}


def _source_check(session, token, transport, recovery):
    try:
        from . import source_vector
    except ImportError:
        import source_vector
    plan = session.plan
    file_ingest._validate_plan(session.ingestion)
    etag = session.require_ack()
    current, _ = search_reconcile._get(search_reconcile.resource_url(plan["source"]), token,
                                       transport=source_vector.guard_readback_transport(plan, transport), recovery=recovery)
    if (current is None or current.get("@odata.etag") != etag
            or not search_reconcile.definitions_match(plan["source"]["desired"], current)):
        raise fail("file-upload-source-drift", "Current source does not match original acknowledged identity/version/definition.")
    return current


def _verify(session, token_provider, transport, context_provider):
    try:
        from . import file_source, file_cu_mi
    except ImportError:
        import file_source, file_cu_mi
    session.require_ack()
    session.states()
    session.require_backoff()
    transport = session.transport(transport)
    context = context_provider()
    cu_ingestion_auth.validate_context(context)
    if context != session.seed["context"]:
        raise fail("file-upload-context-drift", "Original tenant/subscription/principal changed.")
    plan = session.plan
    if "content_understanding" in plan:
        state, _ = file_source.read_content_understanding(plan["content_understanding"], token_provider=token_provider, transport=transport)
        if not file_source._cu_states_match(state, plan["cu_resource_state"]):
            raise fail("file-upload-auth-drift", "Original CU account/auth/network state changed.")
        if plan["source"].get("ai_services_managed_identity"):
            binding, _ = file_cu_mi.read_binding(plan["content_understanding"], plan["source"]["endpoint"],
                                               token_provider=token_provider, transport=transport)
            if binding != plan["cu_identity_state"]:
                raise fail("file-upload-auth-drift", "Original Search MI/CU role/network binding changed.")
    return _source_check(session, token_provider(SEARCH_AUDIENCE), transport, ReadRecovery())


def plan_resume(request, *, token_provider=azure_cli_token, transport=http_request,
                context_provider=cu_ingestion_auth.account_context):
    if not isinstance(request, dict) or not isinstance(request.get("receipt_directory"), str):
        raise fail("file-upload-input-invalid", "Use an object with the original private receipt directory.")
    require_allowed_fields(request, {"schema_version", "receipt_directory"}, label="upload resume request")
    if request.get("schema_version") != "1.0":
        raise fail("file-upload-input-invalid", "Use the supported resume request schema.")
    session = Session(request.get("receipt_directory"))
    transport = session.transport(transport)
    _verify(session, token_provider, transport, context_provider)
    states = session.states()
    inventory, _ = file_ingest._list_files(file_ingest._list_url(session.ingestion), token_provider(SEARCH_AUDIENCE),
                                         transport=transport, recovery=ReadRecovery())
    observed = _observe(session.ingestion, states, inventory)
    eligible = [i for i, state in enumerate(states) if state["upload"] == "not_attempted" and i not in observed]
    plan = {"operation": "resume-file-uploads", "version": "1.0", "receipt_directory": str(session.directory),
            "original_plan_digest": digest(session.plan), "creation_ack_digest": digest(session.records["source-ack.json"]),
            "journal_digest": digest(session.records), "eligible": eligible, "owner": session.plan["owner"], "cleanup_approved": False}
    return {"status": "planned", "execution_input": {"schema_version": "1.0", "plan": plan,
                                                   "approval": {"confirmed": False, "fingerprint": digest(plan)}},
            "approval_summary": {"execution_required": bool(eligible), "mutation_approval_required": bool(eligible), "uploads": len(eligible)},
            "file_batch": _summary(session.ingestion, states, session), "writes_performed": [],
            "next_step": "Approve only never-attempted uploads. No eligible files: retain this observation; do not replay uncertain files."}


@reporting("file-source")
def execute(document, *, token_provider=azure_cli_token, transport=http_request,
            context_provider=cu_ingestion_auth.account_context, progress=None):
    if not isinstance(document, dict) or not isinstance(document.get("plan"), dict):
        raise fail("file-upload-input-invalid", "Use the newly approved upload-only envelope.")
    require_allowed_fields(document, {"schema_version", "plan", "approval", "_computed_fingerprint"}, label="upload resume envelope")
    plan = document.get("plan")
    reject_secrets(document)
    require_allowed_fields(plan, {"operation", "version", "receipt_directory", "original_plan_digest", "creation_ack_digest",
                                 "journal_digest", "eligible", "owner", "cleanup_approved"}, label="upload resume plan")
    if (document.get("schema_version") != "1.0" or plan.get("operation") != "resume-file-uploads" or plan.get("version") != "1.0"
            or set(plan) != {"operation", "version", "receipt_directory", "original_plan_digest", "creation_ack_digest",
                             "journal_digest", "eligible", "owner", "cleanup_approved"}
            or not isinstance(document.get("approval"), dict) or document["approval"].get("confirmed") is not True
            or plan.get("cleanup_approved") is not False or document.get("approval") != {"confirmed": True, "fingerprint": digest(plan)}
            or document.get("_computed_fingerprint") != digest(plan)):
        raise fail("file-upload-approval-missing", "A newly approved unchanged upload-only plan is required.")
    session = Session(plan.get("receipt_directory"))
    transport = session.transport(transport)
    if (plan["original_plan_digest"] != digest(session.plan) or plan["journal_digest"] != digest(session.records)
            or plan["creation_ack_digest"] != digest(session.records["source-ack.json"]) or plan["owner"] != session.plan["owner"]
            or not isinstance(plan["eligible"], list) or any(type(i) is not int or not 0 <= i < len(session.ingestion["files"]) for i in plan["eligible"])
            or len(set(plan["eligible"])) != len(plan["eligible"])):
        raise fail("file-upload-plan-drift", "Original approval/ACK/journal changed; refresh the upload-only plan.")
    states = session.states()
    if any(states[i]["upload"] != "not_attempted" for i in plan["eligible"]):
        raise fail("file-upload-replay-forbidden", "Attempted files cannot be submitted again, even after an empty inventory.")
    progress.update("source-reconciliation")
    try:
        _verify(session, token_provider, transport, context_provider)
        result = run_batch({"plan": session.ingestion, "_computed_fingerprint": digest(session.plan)}, token_provider=token_provider,
                           transport=transport, progress=progress, allow_new_uploads=True, session=session, eligible=plan["eligible"],
                           source_check=lambda recovery, token: _source_check(session, token, transport, recovery))
    except HelperFailure as failure:
        if failure.file_batch is None:
            failure.file_batch = _summary(session.ingestion, states, session)
        failure.partial = True
        failure.resources_remaining.insert(0, {"type": "knowledge-source", "name": session.plan["source"]["name"]})
        raise
    result["approved_plan"] = document["approval"]
    result["original_run"] = {"plan_digest": digest(session.plan), "creation_ack_digest": plan["creation_ack_digest"],
                              "source_retained": session.plan["source"]["name"]}
    return result


def main(argv=None):
    try:
        from .private_artifacts import add_execution_output_argument, emit_plan_result, validate_execution_output_mode
    except ImportError:
        from private_artifacts import add_execution_output_argument, emit_plan_result, validate_execution_output_mode
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--plan", type=Path)
    modes.add_argument("--input", type=Path)
    add_execution_output_argument(parser)
    add_progress_argument(parser)
    args = parser.parse_args(argv)
    fingerprint = None
    try:
        validate_execution_output_mode(args)
        if args.plan:
            emit_plan_result(plan_resume(private_io.read_json(args.plan)), args.execution_output)
            return 0
        document, _, fingerprint = load_approved_input(args.input)
        document["_computed_fingerprint"] = fingerprint
        result = execute(document, progress=Progress("file-source", enabled=args.progress))
    except HelperFailure as failure:
        result = blocked_result(failure, outcome="resume-file-uploads", fingerprint=fingerprint)
        result["safe_next_decision"] = "Retain the source. Missing/changed original evidence blocks upload continuation, not retention; no creation replay or cleanup workaround."
        emit_result(result)
        return 3 if result["status"] == "partial" else 2
    emit_result(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
