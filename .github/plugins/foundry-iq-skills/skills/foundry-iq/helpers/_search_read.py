"""Search definition, version evidence and read-only resource access."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode

try:
    from ._common import (
        HelperFailure, HttpResult, ReadRecovery, Transport, odata_name, validate_search_endpoint,
    )
except ImportError:
    from _common import (
        HelperFailure, HttpResult, ReadRecovery, Transport, odata_name, validate_search_endpoint,
    )


SUPPORTED_API_VERSIONS = {"2026-04-01", "2026-08-01-preview"}


RESOURCE_SEGMENTS = {
    "knowledge-source": "knowledgesources",
    "knowledge-base": "knowledgebases",
}


DYNAMIC_FIELDS = {
    "@odata.context",
    "@odata.etag",
    "currentSynchronizationState",
    "lastSynchronizationState",
    "synchronizationStatus",
    "apiKey",
    "createdResources",
    # Azure Search always returns "<redacted>" for connectionString on GET
    # (secret redaction), never the submitted value, so it can never be
    # compared for exact equality against a desired definition.
    "connectionString",
}


# Search normalizes these endpoint fields inconsistently on readback.
URI_FIELDS = {"resourceUri", "uri"}


SHA256 = re.compile(r"^sha256:[a-f0-9]{64}$")


def _odata_name(name: Any) -> str:
    return odata_name(name)


def _resource_url(plan: dict[str, Any]) -> str:
    endpoint = validate_search_endpoint(plan.get("endpoint"))
    resource_type = plan.get("resource_type")
    segment = RESOURCE_SEGMENTS.get(resource_type)
    if segment is None:
        raise HelperFailure(
            "resource-type-invalid",
            "resource_type must be knowledge-source or knowledge-base.",
            blocked_at="input-resolution",
        )
    api_version = plan.get("api_version")
    if api_version not in SUPPORTED_API_VERSIONS:
        raise HelperFailure(
            "api-version-invalid",
            "API version must be 2026-04-01 or 2026-08-01-preview.",
            blocked_at="input-resolution",
        )
    return (
        f"{endpoint}/{segment}('{_odata_name(plan.get('name'))}')?"
        + urlencode({"api-version": api_version})
    )


def _definition(value: Any, *, key: str | None = None) -> Any:
    if isinstance(value, dict):
        result = {
            child_key: _definition(child, key=child_key)
            for child_key, child in sorted(value.items())
            if child_key not in DYNAMIC_FIELDS and child is not None
        }
        # Preview returns this documented default even when omitted on creation.
        if value.get("kind") == "azureBlob" and result.get("resultsProcessing") == "rerank":
            result.pop("resultsProcessing")
        return {
            child_key: child
            for child_key, child in result.items()
            if child not in ({}, [])
        }
    if isinstance(value, list):
        return [_definition(child) for child in value]
    # Azure Search silently strips a single trailing slash from
    # azureOpenAIParameters.resourceUri on readback (while preserving it
    # verbatim on aiServices.uri), so a byte-exact comparison would
    # false-negative on functionally identical endpoints that differ only
    # by a trailing slash. Normalize both known endpoint-URI field names.
    if (
        key in URI_FIELDS
        and isinstance(value, str)
        and value.endswith("/")
        and len(value) > 1
    ):
        # Remove only one trailing slash; preserve intentional extra
        # slashes (e.g. "https://example.com//") for exact comparison.
        return value[:-1]
    return value


def response_etags(result: HttpResult) -> dict[str, Any]:
    return {
        "body": result.body.get("@odata.etag") if isinstance(result.body, dict) else None,
        "headers": list(result.etag_values) if result.etag_values is not None else [
            value for name, value in result.headers.items() if name.lower() == "etag"
        ],
    }


def resolve_etag(evidence: dict[str, Any], request_id: str | None = None) -> str | None:
    values = [*evidence["headers"]]
    if evidence["body"] is not None:
        values.append(evidence["body"])
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise HelperFailure("etag-invalid", "Search returned malformed version evidence.",
                            blocked_at="verification", request_id=request_id)
    if len(set(values)) > 1:
        raise HelperFailure("etag-conflict", "Search response header/body ETags conflict.",
                            blocked_at="verification", request_id=request_id)
    return values[0] if values else None


def _get(
    url: str,
    token: str,
    *,
    transport: Transport,
    recovery: ReadRecovery | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        result = (recovery.get(url, token, transport=transport) if recovery is not None
                  else transport("GET", url, token))
    except HelperFailure as failure:
        if failure.http_status == 404 and failure.blocked_at != "local-persistence":
            return None, failure.request_id
        raise
    if result.status != 200 or not isinstance(result.body, dict):
        raise HelperFailure(
            "readback-invalid",
            "Search resource readback did not return one JSON object.",
            blocked_at="reconciliation",
            request_id=result.request_id,
            status=result.status,
        )
    etag = resolve_etag(response_etags(result), result.request_id)
    body = {**result.body, "@odata.etag": etag} if etag is not None else result.body
    return body, result.request_id


def resource_url(plan: dict[str, Any]) -> str:
    """Validate and address the exact selected Search resource."""
    return _resource_url(plan)


def read_resource(
    url: str, token: str, *, transport: Transport
) -> tuple[dict[str, Any] | None, str | None]:
    """Read one identity; only a definitive 404 means absent."""
    return _get(url, token, transport=transport)


def definitions_match(desired: dict[str, Any], current: dict[str, Any]) -> bool:
    return _definition(desired) == _definition(current)
