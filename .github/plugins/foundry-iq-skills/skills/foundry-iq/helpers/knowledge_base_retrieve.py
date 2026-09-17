from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

try:
    from ._common import (
        SEARCH_AUDIENCE, HelperFailure, HttpResult, TokenProvider, Transport,
        azure_cli_token, blocked_result, emit_result, http_request,
        reject_secrets, require_allowed_fields, validate_search_endpoint,
    )
except ImportError:
    from _common import (  # type: ignore[no-redef]
        SEARCH_AUDIENCE, HelperFailure, HttpResult, TokenProvider, Transport,
        azure_cli_token, blocked_result, emit_result, http_request,
        reject_secrets, require_allowed_fields, validate_search_endpoint,
    )


API_VERSIONS = {"2026-04-01", "2026-08-01-preview"}


def _invalid(message: str) -> HelperFailure:
    return HelperFailure("input-schema-invalid", message, blocked_at="input-resolution")


def _target(endpoint: Any, name: Any, api_version: Any) -> str:
    if not isinstance(api_version, str) or api_version not in API_VERSIONS:
        raise _invalid("Unsupported API version.")
    if not isinstance(name, str) or not name.strip() or any(ord(c) < 32 for c in name):
        raise _invalid("An exact nonempty resource name is required.")
    try:
        return validate_search_endpoint(endpoint)
    except ValueError as exc:
        raise _invalid("Invalid Search endpoint.") from exc


def retrieval_request(
    endpoint: str, name: str, api_version: str, effort: str, query: str,
) -> tuple[str, str, dict[str, Any]]:
    base = _target(endpoint, name, api_version) + "/knowledgebases"
    if not isinstance(effort, str) or effort not in {"minimal", "low", "medium"}:
        raise _invalid("Unsupported reasoning effort.")
    if api_version == "2026-04-01" and effort != "minimal":
        raise _invalid("GA requires minimal retrieval.")
    if not isinstance(query, str) or not query.strip():
        raise _invalid("A nonempty query is required.")
    definition_url = base + "('" + quote(name.replace("'", "''"), safe="") + "')"
    retrieve_url = base + "/" + quote(name, safe="") + "/retrieve"
    suffix = "?api-version=" + api_version
    body = (
        {"intents": [{"type": "semantic", "search": query}]}
        if effort == "minimal" else
        {"messages": [{"role": "user", "content": [{"type": "text", "text": query}]}]}
    )
    return definition_url + suffix, retrieve_url + suffix, body


def read_json(
    method: str, url: str, body: dict[str, Any] | None = None,
    forward_permissions: bool = False, *,
    token_provider: TokenProvider = azure_cli_token,
    transport: Transport = http_request,
) -> HttpResult:
    token = token_provider(SEARCH_AUDIENCE)
    headers = {"Content-Type": "application/json"}
    if forward_permissions:
        headers["x-ms-query-source-authorization"] = token
    result = transport(
        method, url, token,
        body=json.dumps(body).encode("utf-8") if body is not None else None,
        headers=headers, follow_redirects=False, max_response_bytes=5 * 1024 * 1024,
    )
    if result.status != 200 or not isinstance(result.body, dict):
        raise HelperFailure(
            "retrieval-incomplete", "Expected complete JSON response.",
            blocked_at="verification", status=result.status, request_id=result.request_id,
        )
    return result


def _verify_signed_in_user() -> None:
    executable = shutil.which("az")
    if executable is None:
        raise HelperFailure(
            "azure-cli-unavailable", "Azure CLI is required for keyless authentication.",
            blocked_at="execution",
        )
    try:
        result = subprocess.run(
            [executable, "account", "show", "--query", "user.type", "--output", "tsv"],
            check=True, capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise HelperFailure(
            "permission-forwarding-unavailable", "Could not verify the signed-in user.",
            blocked_at="input-resolution",
        ) from exc
    if result.stdout.strip().casefold() != "user":
        raise HelperFailure(
            "permission-forwarding-unavailable", "Permission forwarding requires a signed-in user.",
            blocked_at="input-resolution",
        )


def execute(
    document: Any, *, token_provider: TokenProvider = azure_cli_token,
    transport: Transport = http_request,
) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise _invalid("Input must be a JSON object.")
    reject_secrets(document)
    operation = document.get("operation")
    if not isinstance(operation, str) or operation not in {
        "get-knowledge-base", "get-knowledge-source", "retrieve",
    }:
        raise _invalid("Choose get-knowledge-base, get-knowledge-source, or retrieve.")
    fields = {"operation", "endpoint", "name", "api_version"}
    if operation == "retrieve":
        fields |= {"effort", "query", "forward_permissions"}
    require_allowed_fields(document, fields, label="read-only request")
    endpoint = _target(document.get("endpoint"), document.get("name"), document.get("api_version"))
    name, api_version = document["name"], document["api_version"]
    body = None
    forwarding = False
    if operation == "retrieve":
        forwarding = document.get("forward_permissions")
        if type(forwarding) is not bool:
            raise _invalid("Explicit forward_permissions true or false is required.")
        _, url, body = retrieval_request(
            endpoint, name, api_version, document.get("effort"), document.get("query"),
        )
        if forwarding:
            _verify_signed_in_user()
        method = "POST"
    else:
        collection = "knowledgebases" if operation == "get-knowledge-base" else "knowledgesources"
        url = endpoint + "/" + collection + "('" + quote(name.replace("'", "''"), safe="") + "')"
        url += "?api-version=" + api_version
        method = "GET"
    result = read_json(
        method, url, body, forwarding, token_provider=token_provider, transport=transport,
    )
    return {
        "status": "response-received", "operation": operation, "mutation": "none",
        "writes_performed": [], "http_status": result.status, "request_id": result.request_id,
        "response_body": result.body, "verification": "not-performed", "cleanup": "not-applicable",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read Search KB/source definitions or retrieve from one KB.")
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        try:
            document = json.loads(args.input.read_text(encoding="utf-8"))
        except OSError as exc:
            raise HelperFailure("input-unreadable", "Input file cannot be read.", blocked_at="input-resolution") from exc
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise HelperFailure("input-invalid-json", "Input must be UTF-8 JSON.", blocked_at="input-resolution") from exc
        result = execute(document)
    except HelperFailure as failure:
        # POST retrieve is read-only even when the generic transport marks it ambiguous.
        readonly_failure = HelperFailure(
            failure.code, failure.message, blocked_at=failure.blocked_at,
            status=failure.http_status, request_id=failure.request_id,
        )
        result = blocked_result(readonly_failure, outcome="knowledge-base-retrieval", fingerprint=None)
        result.update(
            mutation="none", cleanup="not-applicable",
            safe_next_decision="Resolve the first blocker before repeating this read-only request.",
        )
        emit_result(result)
        return 2
    emit_result(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
