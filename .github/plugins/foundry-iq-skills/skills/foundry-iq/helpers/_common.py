from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from http.client import HTTPException
from pathlib import Path
from typing import Any, Callable, NamedTuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen


SEARCH_AUDIENCE = "https://search.azure.com"
MANAGEMENT_AUDIENCE = "https://management.azure.com"
SEARCH_HOST = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,58}[a-z0-9])?\.search\.windows\.net$"
)
SECRET_FIELDS = {
    "accesskey",
    "accesstoken",
    "accountkey",
    "apikey",
    "applicationsecret",
    "authorization",
    "clientsecret",
    "credential",
    "connectionsecret",
    "key",
    "password",
    "privatekey",
    "refreshtoken",
    "sas",
    "sastoken",
    "secret",
    "sharedaccesskey",
    "storageaccountkey",
    "token",
}
RESOURCE_ID_CONNECTION = re.compile(r"^ResourceId=/[^;\r\n]+;?$")


def normalize_azure_location(value: Any) -> str | None:
    """Normalize ASCII case/whitespace only; this does not validate region availability."""
    if not isinstance(value, str) or len(value) > 128 or not value.isascii():
        return None
    compact = re.sub(r"\s+", "", value, flags=re.ASCII).lower()
    return compact if re.fullmatch(r"[a-z][a-z0-9]{1,40}", compact) else None


def _normalize_response_headers(headers: Mapping[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for name, value in headers.items():
        key = name.lower()
        if key in {"x-ms-request-id", "request-id"} and normalized.get(key):
            continue
        if key == "retry-after" and key in normalized:
            normalized[key] = ""
            continue
        normalized[key] = value
    return normalized


def _request_id(headers: Mapping[str, str]) -> str | None:
    normalized = _normalize_response_headers(headers)
    return normalized.get("x-ms-request-id") or normalized.get("request-id") or None


@dataclass(frozen=True)
class HttpResult:
    status: int
    body: Any
    headers: dict[str, str]
    etag_values: tuple[str, ...] | None = None
    recovery_deadline: float | None = None
    ack_failure: HelperFailure | None = None

    @property
    def request_id(self) -> str | None:
        return _request_id(self.headers)

    @property
    def retry_after(self) -> RetryAfter:
        return retry_after_metadata(self.headers)


class RetryAfter(NamedTuple):
    kind: str
    value: float = 0


class RetryAfterTiming(NamedTuple):
    received_at_utc: float | None
    not_before_utc: float | None
    server_delay_seconds: int | None = None


def valid_utc_timestamp(value):
    return type(value) in (int, float) and -62135596800 <= value < 253402300800 and math.isfinite(value)


def retry_after_not_before(metadata, received_at):
    """Resolve typed metadata against UTC, without shortening a server interval."""
    if not valid_utc_timestamp(received_at) or not isinstance(metadata, RetryAfter):
        return None
    value = metadata.value
    if not valid_utc_timestamp(value):
        return None
    if metadata.kind == "seconds":
        value = received_at + value if value >= 0 else math.inf
    elif metadata.kind == "date-rfc850":
        try:
            epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
            parsed = epoch + timedelta(seconds=value)
            current_year = (epoch + timedelta(seconds=received_at)).year
            year = current_year // 100 * 100 + parsed.year % 100
            if year > current_year + 50:
                year -= 100
            value = parsed.replace(year=year).timestamp()
        except (ValueError, OverflowError):
            return None
    elif metadata.kind in {"missing", "invalid"}:
        value = received_at + 1
    elif metadata.kind != "date":
        return None
    return value if valid_utc_timestamp(value) else None


def retry_after_timing(headers, *, received_at=None):
    """Portable timing alongside the unchanged, capped RetryAfter protocol."""
    received_at = time.time() if received_at is None else received_at
    if not valid_utc_timestamp(received_at):
        return RetryAfterTiming(None, None)
    metadata = retry_after_metadata(headers)
    deadline = retry_after_not_before(metadata, received_at)
    server_delay = metadata.value if metadata.kind == "seconds" else None
    if metadata.kind == "overlong":
        values = [value for name, value in headers.items()
                  if isinstance(name, str) and name.lower() == "retry-after"]
        if (len(values) == 1 and isinstance(values[0], str) and len(values[0]) <= 128
                and re.fullmatch(r"[0-9]+", values[0].strip(" \t"))):
            seconds = int(values[0].strip(" \t"))
            if seconds < 253402300800 - received_at:
                deadline = received_at + seconds
                server_delay = seconds
    return RetryAfterTiming(received_at, deadline, server_delay)


def retry_after_metadata(headers: Mapping[str, str]) -> RetryAfter:
    """Retain only a bounded delay/date, never raw server header text."""
    values = []
    for name, value in headers.items():
        if isinstance(name, str) and name.lower() == "retry-after":
            values.append(value)
            if len(values) > 1:
                return RetryAfter("invalid")
    if not values:
        return RetryAfter("missing")
    value = values[0]
    if not isinstance(value, str):
        return RetryAfter("invalid")
    # An unbounded field cannot safely authorize an early request.
    if len(value) > 128:
        return RetryAfter("overlong")
    if not value.isascii():
        return RetryAfter("invalid")
    value = value.strip(" \t")
    if re.fullmatch(r"[0-9]+", value):
        seconds = int(value)
        return RetryAfter("seconds", seconds) if seconds <= 30 else RetryAfter("overlong")
    # HTTP-date includes obsolete RFC850/asctime forms, but not arbitrary email dates.
    if not re.fullmatch(
        r"(?:[A-Z][a-z]{2}, [0-9]{2} [A-Z][a-z]{2} [0-9]{4} [0-9:]{8} GMT"
        r"|[A-Z][a-z]+, [0-9]{2}-[A-Z][a-z]{2}-[0-9]{2} [0-9:]{8} GMT"
        r"|[A-Z][a-z]{2} [A-Z][a-z]{2} [ 0-9][0-9] [0-9:]{8} [0-9]{4})", value
    ):
        return RetryAfter("invalid")
    try:
        parsed = parsedate_to_datetime(value)
        stamp = parsed.replace(tzinfo=timezone.utc).timestamp()
        return RetryAfter("date-rfc850" if "-" in value else "date", stamp)
    except (TypeError, ValueError, OverflowError):
        return RetryAfter("invalid")


class HelperFailure(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        blocked_at: str,
        writes: list[dict[str, Any]] | None = None,
        resources_remaining: list[dict[str, Any]] | None = None,
        resources_reused: list[dict[str, Any]] | None = None,
        resources_unverified: list[dict[str, Any]] | None = None,
        request_id: str | None = None,
        status: int | None = None,
        partial: bool = False,
        warnings: list[str] | None = None,
        retry_after: RetryAfter | None = None,
        recovery_deadline: float | None = None,
        retry_after_timing: RetryAfterTiming | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.blocked_at = blocked_at
        self.writes = writes or []
        self.resources_remaining = resources_remaining or []
        self.resources_reused = resources_reused or []
        self.resources_unverified = resources_unverified or []
        self.request_id = request_id
        self.http_status = status
        self.partial = partial
        self.warnings = warnings or []
        self.retry_after = retry_after or RetryAfter("missing")
        self.recovery_deadline = recovery_deadline
        self.retry_after_timing = retry_after_timing
        self.response_close_failed = False
        self.file_batch = None


class ReadRecovery:
    """One 429 delay opportunity and one deadline across an explicit read sequence."""

    def __init__(self, *, monotonic=None, wall_clock=None, sleeper=None, deadline=None, on_wait=None):
        self.monotonic = monotonic or time.monotonic
        self.wall_clock = wall_clock or time.time
        self.sleeper = sleeper or time.sleep
        self.deadline = min(self.monotonic() + 60, deadline if deadline is not None else math.inf)
        self.delayed = False
        self.request_ids: list[str] = []
        self.warnings: list[str] = []
        self.on_wait = on_wait

    @staticmethod
    def safe_id(request_id):
        return request_id if isinstance(request_id, str) and re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", request_id
        ) else "[withheld]"

    def record(self, request_id):
        if request_id and len(self.request_ids) < 202:
            self.request_ids.append(self.safe_id(request_id))

    def diagnostics(self):
        return [*self.warnings, *(
            ["Read-only request IDs: " + ", ".join(self.request_ids)] if self.request_ids else []
        )]

    def annotate(self, failure):
        for warning in self.diagnostics():
            if warning not in failure.warnings:
                failure.warnings.append(warning)
        return failure

    def _stop(self, code, message):
        self.warnings.append(message)
        raise self.annotate(HelperFailure(
            code, message + " Stop; resume only read-only verification, never replay the write.",
            blocked_at="verification",
            request_id=self.request_ids[-1] if self.request_ids else None,
        ))

    def delay(self, failure):
        if failure.blocked_at == "local-persistence":
            self._stop("read-recovery-persistence-failed", "Required receipt persistence failed; recovery is terminal.")
        if failure.response_close_failed:
            self._stop("read-recovery-response-close-failed", "HTTP error response cleanup failed; delayed recovery is blocked.")
        if failure.http_status != 429:
            return
        if failure.recovery_deadline is not None:
            self.deadline = min(self.deadline, failure.recovery_deadline)
        if self.delayed:
            self._stop("read-recovery-exhausted", "The single HTTP 429 delay opportunity is exhausted.")
        metadata = failure.retry_after
        delay = metadata.value
        if metadata.kind in {"date", "date-rfc850"}:
            now = self.wall_clock()
            deadline = retry_after_not_before(metadata, now)
            if deadline is None:
                self._stop("read-recovery-delay-exceeded", "Retry-After date cannot be represented safely.")
            delay = max(0, deadline - now)
        elif metadata.kind in {"missing", "invalid"}:
            delay = 1
            self.warnings.append("Retry-After missing/invalid; using the fixed 1-second fallback.")
        if metadata.kind == "overlong" or not math.isfinite(delay) or delay > 30:
            self._stop("read-recovery-delay-exceeded", "Retry-After exceeds the 30-second wait allowance; it was not shortened.")
        remaining = self.deadline - self.monotonic()
        if remaining <= delay:
            self._stop("read-recovery-budget-exhausted", "Insufficient recovery read budget for Retry-After.")
        self.delayed = True
        start = self.monotonic()
        if self.on_wait is not None:
            self.on_wait(delay)
        self.sleeper(delay)
        elapsed = self.monotonic() - start
        if elapsed < delay:
            self._stop("read-recovery-wait-incomplete", "The required Retry-After delay did not elapse.")
        if self.monotonic() >= self.deadline:
            self._stop("read-recovery-budget-exhausted", "Recovery read deadline elapsed during the wait.")

    def get(self, url, token, *, transport, max_requests=2, **kwargs):
        self.deadline = min(self.deadline, kwargs.get("response_deadline", math.inf))
        first = None
        for attempt in range(2):
            try:
                remaining = self.deadline - self.monotonic()
                if remaining <= 0 or attempt >= max_requests:
                    self._stop("read-recovery-budget-exhausted", "The recovery read deadline elapsed.")
                options = {**kwargs, "follow_redirects": False, "response_deadline": self.deadline,
                           "timeout": min(kwargs.get("timeout", 180), remaining),
                           "max_response_bytes": kwargs.get("max_response_bytes", 1024 * 1024)}
                result = transport("GET", url, token, **options)
                if result.recovery_deadline is not None:
                    self.deadline = min(self.deadline, result.recovery_deadline)
                self.record(result.request_id)
                if self.monotonic() >= self.deadline:
                    self._stop("read-recovery-budget-exhausted", "The recovery response exceeded its read deadline.")
                if result.status != 429:
                    return result
                raise HelperFailure(
                    "azure-http-error", "Azure request failed with HTTP 429.",
                    blocked_at="verification", status=429, request_id=result.request_id,
                    retry_after=result.retry_after,
                    recovery_deadline=result.recovery_deadline,
                )
            except HelperFailure as failure:
                if not self.request_ids or self.request_ids[-1] != failure.request_id:
                    self.record(failure.request_id)
                if failure.http_status != 429 or attempt:
                    if first is not None:
                        self.warnings.append(
                            f"Recovery read stopped ({failure.code}); delay opportunity exhausted; "
                            "initial read failure retained. Resume read-only; never replay the write."
                        )
                        raise self.annotate(first) from failure
                    raise self.annotate(failure)
                first = failure
                try:
                    if attempt + 1 >= max_requests:
                        self._stop("read-recovery-exhausted", "No requests remain in the recovery read allowance.")
                    self.delay(failure)
                except HelperFailure as stopped:
                    self.warnings.append(stopped.message)
                    raise self.annotate(first) from stopped
        raise AssertionError("unreachable")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def digest(value: Any) -> str:
    return f"sha256:{hashlib.sha256(canonical_bytes(value)).hexdigest()}"


def file_digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return f"sha256:{hasher.hexdigest()}"


def load_approved_input(path: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise HelperFailure(
            "input-unreadable",
            "Input file cannot be read.",
            blocked_at="input-resolution",
        ) from exc
    except json.JSONDecodeError as exc:
        raise HelperFailure(
            "input-invalid-json",
            f"Input file is not valid JSON: {exc}",
            blocked_at="input-resolution",
        ) from exc
    if not isinstance(document, dict) or document.get("schema_version") != "1.0":
        raise HelperFailure(
            "input-schema-invalid",
            "Input must be an object with schema_version 1.0.",
            blocked_at="input-resolution",
        )
    reject_secrets(document)
    require_allowed_fields(
        document,
        {"schema_version", "plan", "approval"},
        label="input envelope",
    )
    plan = document.get("plan")
    approval = document.get("approval")
    if not isinstance(plan, dict) or not isinstance(approval, dict):
        raise HelperFailure(
            "input-schema-invalid",
            "Input must contain plan and approval objects.",
            blocked_at="input-resolution",
        )
    require_allowed_fields(
        approval,
        {"confirmed", "fingerprint"},
        label="approval",
    )
    computed = digest(plan)
    if approval.get("confirmed") is not True:
        raise HelperFailure(
            "approval-missing",
            "The exact plan has not been explicitly approved.",
            blocked_at="confirmation",
        )
    if approval.get("fingerprint") != computed:
        raise HelperFailure(
            "approval-mismatch",
            "The approved fingerprint does not match the canonical plan.",
            blocked_at="confirmation",
        )
    return document, plan, computed


def reject_secrets(value: Any, *, path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            child_path = f"{path}/{key}"
            if normalized in SECRET_FIELDS and child not in (None, "", []):
                raise HelperFailure(
                    "secret-input-forbidden",
                    f"Secret-bearing field is forbidden at {child_path}.",
                    blocked_at="input-resolution",
                )
            if normalized == "connectionstring" and child not in (None, ""):
                if (
                    not isinstance(child, str)
                    or RESOURCE_ID_CONNECTION.fullmatch(child) is None
                ):
                    raise HelperFailure(
                        "secret-input-forbidden",
                        "Only one ResourceId storage connectionString component is allowed.",
                        blocked_at="input-resolution",
                    )
            reject_secrets(child, path=child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_secrets(child, path=f"{path}/{index}")


def require_allowed_fields(
    value: dict[str, Any],
    allowed: set[str],
    *,
    label: str,
) -> None:
    if set(value) - allowed:
        raise HelperFailure(
            "input-schema-invalid",
            f"{label} contains unsupported fields.",
            blocked_at="input-resolution",
        )


def is_ambiguous_mutation_failure(failure: HelperFailure) -> bool:
    return (
        failure.partial
        or failure.code == "azure-response-ambiguous"
        or failure.http_status in {408, 429}
        or (
            isinstance(failure.http_status, int)
            and failure.http_status >= 500
        )
    )


def is_ambiguous_status(status: int) -> bool:
    return status in {408, 429} or status >= 500


def sdk_error_status(error: Exception) -> int | None:
    for source in (error, getattr(error, "response", None)):
        status = getattr(source, "status_code", None)
        if type(status) is int and 100 <= status <= 599:
            return status
    return None


def sdk_error_metadata(error: Exception, fallback_code: str | None = None) -> dict[str, Any]:
    """Read only bounded identifier fields, never exception text or response bodies."""
    def identifier(value: Any) -> str | None:
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value):
            return value
        return None

    response = getattr(error, "response", None)
    raw_headers = getattr(response, "headers", None)
    headers = {}
    if isinstance(raw_headers, Mapping):
        headers = _normalize_response_headers({
            key: identifier(value)
            for key, value in raw_headers.items()
            if isinstance(key, str) and key.lower() in {"x-ms-request-id", "request-id", "x-ms-error-code"}
        })
    result = {"status": sdk_error_status(error), "request_id": _request_id(headers)}
    if fallback_code is not None:
        detail = getattr(error, "error", None)
        code = detail.get("code") if isinstance(detail, Mapping) else getattr(detail, "code", None)
        result["code"] = (
            identifier(code) or identifier(getattr(error, "code", None))
            or headers.get("x-ms-error-code") or fallback_code
        )
    return result


def is_ambiguous_sdk_error(error: Exception) -> bool:
    status = sdk_error_status(error)
    return status is None or is_ambiguous_status(status)


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            if normalized in SECRET_FIELDS or normalized == "connectionstring":
                result[str(key)] = "[REDACTED]"
            else:
                result[str(key)] = redact_sensitive(child)
        return result
    if isinstance(value, list):
        return [redact_sensitive(child) for child in value]
    return value


def validate_search_endpoint(endpoint: Any) -> str:
    if not isinstance(endpoint, str):
        raise HelperFailure(
            "endpoint-invalid",
            "Search endpoint must be a string.",
            blocked_at="input-resolution",
        )
    try:
        endpoint.encode("utf-8")
        parsed = urlsplit(endpoint)
        port = parsed.port
    except (ValueError, UnicodeEncodeError) as exc:
        raise HelperFailure(
            "endpoint-invalid",
            "Search endpoint must be a valid UTF-8 HTTPS service root.",
            blocked_at="input-resolution",
        ) from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or SEARCH_HOST.fullmatch(parsed.hostname) is None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
        or port not in {None, 443}
    ):
        raise HelperFailure(
            "endpoint-invalid",
            "Search endpoint must be an HTTPS search.windows.net service root.",
            blocked_at="input-resolution",
        )
    return endpoint.rstrip("/")


def odata_name(name: Any) -> str:
    if not isinstance(name, str) or not name or len(name) > 128:
        raise HelperFailure(
            "name-invalid",
            "Resource name must be a non-empty string no longer than 128 characters.",
            blocked_at="input-resolution",
        )
    try:
        return quote(name.replace("'", "''"), safe="")
    except UnicodeEncodeError as exc:
        raise HelperFailure(
            "name-invalid",
            "Resource name must be valid UTF-8 text.",
            blocked_at="input-resolution",
        ) from exc


def azure_cli_token(resource: str) -> str:
    try:
        executable = shutil.which("az")
        if executable is None:
            raise FileNotFoundError("Azure CLI executable was not found on PATH.")
        completed = subprocess.run(
            [
                executable,
                "account",
                "get-access-token",
                "--resource",
                resource,
                "--query",
                "accessToken",
                "--output",
                "tsv",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError as exc:
        raise HelperFailure(
            "azure-cli-unavailable",
            "Azure CLI is required for keyless authentication.",
            blocked_at="execution",
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise HelperFailure(
            "azure-authentication-failed",
            "Azure CLI could not acquire the required access token.",
            blocked_at="execution",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise HelperFailure(
            "azure-authentication-timeout",
            "Azure CLI did not return an access token within 60 seconds.",
            blocked_at="execution",
        ) from exc
    token = completed.stdout.strip()
    if not token:
        raise HelperFailure(
            "azure-authentication-failed",
            "Azure CLI returned an empty access token.",
            blocked_at="execution",
        )
    return token


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def _read_response_with_deadline(
    response: Any, deadline: float, max_bytes: int, *, method: str
) -> bytes:
    def timed_out() -> HelperFailure:
        return HelperFailure(
            "response-deadline-exceeded",
            "HTTP response body exceeded its monotonic deadline.",
            blocked_at="verification",
            request_id=_request_id(response.headers),
            status=response.status,
            partial=method not in {"GET", "HEAD"},
        )

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise timed_out()
    connection = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
    if not isinstance(connection, socket.socket):
        raise HelperFailure(
            "response-deadline-unsupported",
            "Deadline reads require an interruptible urllib HTTP socket.",
            blocked_at="verification",
            request_id=_request_id(response.headers),
            status=response.status,
            partial=method not in {"GET", "HEAD"},
        )
    expired = threading.Event()

    def interrupt() -> None:
        expired.set()
        # BufferedReader.close can wait on the active read lock; interrupt its socket instead.
        with suppress(OSError):
            connection.shutdown(socket.SHUT_RDWR)
        with suppress(OSError):
            connection.close()

    watchdog = threading.Timer(max(0, deadline - time.monotonic()), interrupt)
    watchdog.start()
    try:
        if expired.is_set() or time.monotonic() >= deadline:
            raise timed_out()
        try:
            payload = response.read(max_bytes + 1)
        except (OSError, HTTPException, ValueError) as exc:
            if expired.is_set() or time.monotonic() >= deadline:
                raise timed_out() from exc
            raise HelperFailure(
                "response-read-failed", "HTTP response body could not be read.",
                blocked_at="verification",
                request_id=_request_id(response.headers),
                status=response.status,
                partial=method not in {"GET", "HEAD"},
            ) from exc
        if expired.is_set() or time.monotonic() >= deadline:
            raise timed_out()
        return payload
    finally:
        watchdog.cancel()
        watchdog.join()


def http_request(
    method: str,
    url: str,
    token: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 180,
    raw_response: bool = False,
    max_response_bytes: int | None = None,
    follow_redirects: bool = True,
    response_deadline: float | None = None,
) -> HttpResult:
    if response_deadline is not None:
        if (
            not isinstance(response_deadline, (int, float))
            or not math.isfinite(response_deadline)
            or response_deadline - time.monotonic() > threading.TIMEOUT_MAX
        ):
            raise HelperFailure(
                "response-deadline-invalid", "Response deadline must be a supported finite monotonic time.",
                blocked_at="input-resolution",
            )
        if max_response_bytes is None:
            max_response_bytes = 1024 * 1024
        if not isinstance(max_response_bytes, int) or max_response_bytes < 0:
            raise HelperFailure(
                "response-limit-invalid", "Response byte limit must be a nonnegative integer.",
                blocked_at="input-resolution",
            )
        if response_deadline <= time.monotonic():
            raise HelperFailure(
                "response-deadline-exceeded", "HTTP deadline elapsed before the request.",
                blocked_at="verification",
            )
    request_headers = {
        "Accept": "application/json;odata.metadata=minimal",
        "Authorization": f"Bearer {token}",
        "x-ms-client-request-id": str(uuid.uuid4()),
    }
    request_headers.update(headers or {})
    request = Request(url=url, data=body, headers=request_headers, method=method)
    try:
        open_request = urlopen if follow_redirects else build_opener(_NoRedirect).open
        with open_request(request, timeout=timeout) as response:
            if response_deadline is not None:
                payload = _read_response_with_deadline(
                    response, response_deadline, max_response_bytes, method=method
                )
            else:
                payload = (
                    response.read(max_response_bytes + 1)
                    if max_response_bytes is not None
                    else response.read()
                )
            etag_values = tuple(value for name, value in response.headers.items() if name.lower() == "etag")
            response_headers = _normalize_response_headers(response.headers)
            if max_response_bytes is not None and len(payload) > max_response_bytes:
                raise HelperFailure(
                    "response-too-large",
                    "Azure response exceeded the bounded read limit.",
                    blocked_at="verification",
                    request_id=_request_id(response_headers),
                    status=response.status,
                    partial=method not in {"GET", "HEAD"},
                )
            if raw_response:
                parsed: Any = payload
            elif not payload:
                parsed = None
            else:
                try:
                    parsed = json.loads(payload.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise HelperFailure(
                        "response-invalid-json",
                        "Azure returned a non-JSON response where JSON was required.",
                        blocked_at="verification",
                        request_id=_request_id(response_headers),
                        status=response.status,
                        partial=method not in {"GET", "HEAD"},
                    ) from exc
            return HttpResult(response.status, parsed, response_headers, etag_values, response_deadline)
    except HTTPError as exc:
        retry_after = retry_after_metadata(exc.headers)
        timing = retry_after_timing(exc.headers)
        response_headers = _normalize_response_headers(exc.headers)
        status = int(exc.code)
        close_failed = False
        if status == 429:
            try:
                exc.close()
            except (OSError, HTTPException):
                close_failed = True
        elif response_deadline is not None:
            exc.close()
        ambiguous = method not in {"GET", "HEAD"} and is_ambiguous_status(status)
        failure = HelperFailure(
            "azure-http-error",
            f"Azure request failed with HTTP {status}.",
            blocked_at="execution",
            request_id=_request_id(response_headers),
            status=status,
            partial=ambiguous,
            retry_after=retry_after,
            recovery_deadline=response_deadline,
            retry_after_timing=timing,
            warnings=(["response-close-failed: HTTP 429 response cleanup failed; "
                       "original HTTP failure retained and delayed recovery blocked."] if close_failed else []),
        )
        failure.response_close_failed = close_failed
        raise failure from exc
    except (URLError, TimeoutError) as exc:
        raise HelperFailure(
            "azure-response-ambiguous",
            "Azure request did not return an authoritative response.",
            blocked_at="verification",
            partial=method not in {"GET", "HEAD"},
        ) from exc


def blocked_result(
    failure: HelperFailure,
    *,
    outcome: str,
    fingerprint: str | None,
    owner: Any = None,
) -> dict[str, Any]:
    result = _blocked_result(failure, outcome=outcome, fingerprint=fingerprint, owner=owner)
    if failure.file_batch is not None:
        result["file_batch"] = failure.file_batch
        result["safe_next_decision"] = (
            "Retain the source and original ACK/journal. Do not rerun creation, replay an uncertain upload, "
            "or delete/reset resources. Plan upload-only continuation for never-attempted files with "
            "file_upload.py --plan; missing original evidence blocks continuation, not retention."
        )
    return result


def _blocked_result(failure, *, outcome, fingerprint, owner):
    if failure.partial or failure.writes:
        return {
            "status": "partial",
            "outcome": outcome,
            "approved_plan": {
                "fingerprint": fingerprint,
                "confirmed": fingerprint is not None,
            },
            "first_failure": {
                "code": failure.code,
                "operation": failure.blocked_at,
                "status": failure.http_status,
                "message": failure.message,
                "request_id": failure.request_id,
            },
            "completed_writes": failure.writes,
            "failed_or_unverified_postconditions": [failure.code],
            "resources_remaining": {
                "run_owned": failure.resources_remaining,
                "reused": failure.resources_reused,
                **({"unverified": failure.resources_unverified} if failure.resources_unverified else {}),
            },
            "rollback": {"possible": False, "exact_plan": []},
            "cleanup": {"status": "separate-plan-and-approval-required"},
            "owner": owner,
            "warnings": failure.warnings,
        }
    result = {
        "status": "blocked",
        "outcome": outcome,
        "blocked_at": failure.blocked_at,
        "first_blocker": {
            "code": failure.code,
            "message": failure.message,
            "status": failure.http_status,
            "request_id": failure.request_id,
        },
        "missing_or_conflicting_input": failure.code,
        "read_only_evidence": [],
        "writes_performed": [],
        "safe_next_decision": "Resolve the first blocker, rebuild the plan, and obtain new approval.",
        "ownership": {"run_owned": [], "reused_not_owned": []},
        "cleanup": "not applicable",
    }
    if fingerprint is not None:
        result["approved_plan"] = {
            "fingerprint": fingerprint,
            "confirmed": True,
        }
    if failure.warnings:
        result["warnings"] = failure.warnings
    return result


def emit_result(
    result: dict[str, Any], *, stream: Any = None, preserve_unapproved_input: bool = False
) -> None:
    if stream is None:
        stream = sys.stdout
    safe = redact_sensitive(result)
    if preserve_unapproved_input:
        document = result.get("execution_input")
        if (
            result.get("status") != "planned" or not isinstance(document, dict)
            or document.get("schema_version") != "1.0" or not isinstance(document.get("plan"), dict)
            or not isinstance(document.get("approval"), dict)
            or document["approval"].get("confirmed") is not False
            or document.get("approval") != {"confirmed": False, "fingerprint": digest(document["plan"])}
        ):
            raise HelperFailure(
                "planning-output-invalid", "Only an exact unapproved execution input can retain ResourceId bindings.",
                blocked_at="verification",
            )
        reject_secrets(document)
        require_allowed_fields(document, {"schema_version", "plan", "approval"}, label="planning envelope")
        safe["execution_input"] = document
    stream.write(
        json.dumps(
            safe,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


TokenProvider = Callable[[str], str]
Transport = Callable[..., HttpResult]
