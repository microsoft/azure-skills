from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

try:
    from . import cu_ingestion_auth as file_cu_auth
    from . import _cleanup_dependencies as cleanup_dependencies, _cleanup_receipts as cleanup_receipts
    from ._common import (
        SEARCH_AUDIENCE,
        HelperFailure,
        HttpResult,
        ReadRecovery,
        TokenProvider,
        Transport,
        azure_cli_token,
        blocked_result,
        canonical_bytes,
        digest,
        emit_result,
        http_request,
        is_ambiguous_mutation_failure,
        load_approved_input,
        odata_name,
        reject_secrets,
        require_allowed_fields,
        validate_search_endpoint,
        RESOURCE_ID_CONNECTION,
    )
except ImportError:
    import cu_ingestion_auth as file_cu_auth
    import _cleanup_dependencies as cleanup_dependencies, _cleanup_receipts as cleanup_receipts
    from _common import (  # type: ignore[no-redef]
        SEARCH_AUDIENCE,
        HelperFailure,
        HttpResult,
        ReadRecovery,
        TokenProvider,
        Transport,
        azure_cli_token,
        blocked_result,
        canonical_bytes,
        digest,
        emit_result,
        http_request,
        is_ambiguous_mutation_failure,
        load_approved_input,
        odata_name,
        reject_secrets,
        require_allowed_fields,
        validate_search_endpoint,
        RESOURCE_ID_CONNECTION,
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
# Endpoint-URI fields where Azure Search's own readback normalization is
# inconsistent (resourceUri loses a trailing slash; aiServices.uri keeps
# whatever was submitted), so both are compared slash-insensitively.
URI_FIELDS = {"resourceUri", "uri"}
SHA256 = re.compile(r"^sha256:[a-f0-9]{64}$")
ENVIRONMENT_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
PLAN_FIELDS = {
    "operation",
    "outcome",
    "plan_kind",
    "resource_type",
    "endpoint",
    "name",
    "api_version",
    "action",
    "desired",
    "source_evidence",
    "verified_source",
    "expected_etag",
    "owned_definition_digest",
    "ai_services_api_key_environment",
    "ai_services_key_acquisition",
    "ai_services_managed_identity",
    "data_movement",
    "rbac",
    "network",
    "owner",
    "cleanup_approved",
    "dependency_guard",
    "kb_plan_version",
    "kb_model",
}
KB_INTENT_FIELDS = {
    "schema_version", "endpoint", "name", "owner", "api_version", "source_name",
    "reasoning_effort", "output_mode", "model", "description",
    "retrieval_instructions", "answer_instructions", "action",
    "data_movement", "rbac", "network",
}
CHAT_MODELS = {
    "gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano",
    "gpt-5", "gpt-5-mini", "gpt-5-nano", "gpt-5.1", "gpt-5.2",
    "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.5",
    "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna",
}


def _kb_failure(code: str, message: str, request_id: str | None = None) -> HelperFailure:
    return HelperFailure(code, message, blocked_at="knowledge-base-planning", request_id=request_id)


def _kb_model(value: Any, *, required: bool) -> dict[str, Any] | None:
    if not required:
        if value is not None:
            raise _kb_failure("kb-model-conflict", "Minimal extractive planning must omit a KB model.")
        return None
    if not isinstance(value, dict):
        raise _kb_failure("kb-model-required", "Low/medium or synthesis requires a selected chat deployment.")
    require_allowed_fields(value, {"endpoint", "deployment", "model", "auth", "prerequisites"},
                           label="KB model choice")
    if (
        not isinstance(value.get("endpoint"), str)
        or re.fullmatch(r"https://[a-z0-9][a-z0-9-]{0,62}\."
                        r"(?:openai\.azure\.com|services\.ai\.azure\.com|cognitiveservices\.azure\.com)/?",
                        value["endpoint"]) is None
        or not isinstance(value.get("deployment"), str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value["deployment"]) is None
        or not isinstance(value.get("model"), str) or value["model"] not in CHAT_MODELS
        or value.get("auth") != "system-assigned"
    ):
        raise _kb_failure("kb-model-invalid", "Select a supported chat model/deployment and exact Azure endpoint with system-assigned auth.")
    evidence = value.get("prerequisites")
    if not isinstance(evidence, dict):
        raise _kb_failure("kb-model-evidence-missing", "Provide owner-verified deployment, identity and network references.")
    require_allowed_fields(evidence, {"deployment", "identity", "network"}, label="KB model prerequisites")
    if any(not isinstance(evidence.get(k), str) or not evidence[k].strip() or len(evidence[k]) > 4096
           for k in ("deployment", "identity", "network")):
        raise _kb_failure("kb-model-evidence-missing", "Provide owner-verified deployment, identity and network references.")
    result = copy.deepcopy(value)
    result["endpoint"] = result["endpoint"].rstrip("/")
    return result


def _kb_model_definition(choice: dict[str, Any]) -> dict[str, Any]:
    try:
        from .source_vector import model_definition
    except ImportError:
        from source_vector import model_definition
    return model_definition(choice)


def _kb_guard(plan: dict[str, Any], transport: Transport) -> Transport:
    target = _resource_url(plan)

    def guarded(method, url, token, **kwargs):
        result = transport(method, url, token, **kwargs)
        if method == "GET" and url == target and result.status == 200 and isinstance(result.body, dict):
            models = result.body.get("models")
            for model in models if isinstance(models, list) else []:
                parameters = model.get("azureOpenAIParameters") if isinstance(model, dict) else None
                if isinstance(parameters, dict) and (
                    parameters.get("apiKey") not in (None, "")
                    or parameters.get("authIdentity") is not None
                ):
                    raise _kb_failure("kb-model-auth-conflict",
                                      "KB readback does not prove keyless system-assigned model auth; details withheld.",
                                      result.request_id)
        return result

    return guarded


def plan_knowledge_base(
    request: dict[str, Any], *, token_provider: TokenProvider = azure_cli_token,
    transport: Transport = http_request,
) -> dict[str, Any]:
    """Compile resolved KB choices into an unapproved artifact using exact GETs."""
    if not isinstance(request, dict) or request.get("schema_version") != "1.0":
        raise _kb_failure("input-schema-invalid", "KB planning requires an object with schema_version 1.0.")
    try:
        json.dumps(request, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise _kb_failure("input-schema-invalid", "KB choices must be finite UTF-8 JSON.") from exc
    reject_secrets(request)
    require_allowed_fields(request, KB_INTENT_FIELDS, label="KB planning input")
    for field in ("name", "source_name"):
        _odata_name(request.get(field))
    if not isinstance(request.get("owner"), str) or not request["owner"].strip() or len(request["owner"]) > 4096:
        raise _kb_failure("input-schema-invalid", "An explicit nonempty owner is required.")
    action = request.get("action", "create-or-reuse")
    effort, output = request.get("reasoning_effort"), request.get("output_mode")
    version = request.get("api_version")
    if (
        not isinstance(version, str) or version not in SUPPORTED_API_VERSIONS
        or action not in ("create-or-reuse", "agent-minimal-transition")
        or effort not in ("minimal", "low", "medium")
        or output not in ("extractiveData", "answerSynthesis")
        or version == "2026-04-01" and (effort != "minimal" or output != "extractiveData")
        or action == "agent-minimal-transition" and (
            version != "2026-08-01-preview" or effort != "minimal" or output != "extractiveData"
        )
    ):
        raise _kb_failure("mode-api-mismatch", "Choose supported KB API/output/effort; transition is preview minimal/extractive only.")
    model = _kb_model(request.get("model"), required=effort in ("low", "medium") or output == "answerSynthesis")
    desired: dict[str, Any] = {"name": request["name"], "knowledgeSources": [{"name": request["source_name"]}]}
    if version == "2026-08-01-preview":
        desired.update(outputMode=output, retrievalReasoningEffort={"kind": effort})
    for key, wire in (("description", "description"), ("retrieval_instructions", "retrievalInstructions"),
                      ("answer_instructions", "answerInstructions")):
        if key in request:
            value = request[key]
            if value is not None and (not isinstance(value, str) or len(value) > 4096):
                raise _kb_failure("input-schema-invalid", "KB description/instructions must be bounded text or null.")
            if action == "agent-minimal-transition" or version == "2026-04-01" and key != "description":
                raise _kb_failure("mode-api-mismatch", "These optional fields are not supported in this planning mode.")
            desired[wire] = value
    if model is not None:
        desired["models"] = [_kb_model_definition(model)]
    plan = {
        "operation": "reconcile", "outcome": "create-knowledge-base", "resource_type": "knowledge-base",
        "endpoint": validate_search_endpoint(request.get("endpoint")), "name": request["name"],
        "api_version": version, "owner": request["owner"], "cleanup_approved": False,
        "action": "create", "desired": desired, "kb_plan_version": "1.0", "kb_model": model,
        **{k: copy.deepcopy(request[k]) for k in ("data_movement", "rbac", "network") if k in request},
    }
    target = _resource_url(plan)
    source_url = _resource_url({**plan, "resource_type": "knowledge-source", "name": request["source_name"]})
    # Validate all local sections before authentication; no invented source proof.
    for key, fields in (("data_movement", {"boundary", "result"}), ("rbac", {"assignments"}),
                        ("network", {"posture", "evidence"})):
        if key in plan:
            if not isinstance(plan[key], dict):
                raise _kb_failure("input-schema-invalid", "Optional controls must be objects.")
            require_allowed_fields(plan[key], fields, label=key)
    transport = _kb_guard(plan, transport)
    token = token_provider(SEARCH_AUDIENCE)
    source, source_id = _get(source_url, token, transport=transport)
    if source is None or source.get("name") != request["source_name"] or source.get("kind") not in ("file", "azureBlob"):
        raise _kb_failure("source-unverified", "Select an existing supported source with exact readback.", source_id)
    parameters = source.get("azureBlobParameters")
    if source["kind"] == "azureBlob" and (
        not isinstance(parameters, dict) or not isinstance(parameters.get("isADLSGen2", False), bool)
    ):
        raise _kb_failure("source-unverified", "Blob source type/boundary metadata is malformed.", source_id)
    if version == "2026-04-01" and (
        source["kind"] != "azureBlob" or parameters.get("isADLSGen2", False)
    ):
        raise _kb_failure("mode-api-mismatch", "File and ADLS knowledge bases require supported preview.", source_id)
    source_digest = digest(_definition(source))
    plan["verified_source"] = {"name": request["source_name"], "verified": True, "definition_digest": source_digest}
    current, current_id = _get(target, token, transport=transport)
    if action == "agent-minimal-transition":
        if current is None:
            raise _kb_failure("target-absent", "Transition requires the exact existing KB.", current_id)
        if (
            current.get("name") != plan["name"]
            or _definition(current.get("knowledgeSources")) != desired["knowledgeSources"]
            or current.get("models") not in (None, [])
            or current.get("outputMode") not in (None, "extractiveData")
            or current.get("retrievalReasoningEffort") not in (None, {"kind": "minimal"}, {"kind": "low"})
        ):
            raise _kb_failure("definition-conflict", "Transition requires a model-free extractive KB with absent/minimal/low effort.", current_id)
        desired = {k: copy.deepcopy(v) for k, v in current.items() if k not in ("@odata.etag", "@odata.context")}
        desired.update(outputMode="extractiveData", retrievalReasoningEffort={"kind": "minimal"})
        plan["desired"] = desired
        plan["action"] = "update"
    if current is not None:
        if not definitions_match(desired, current) and action != "agent-minimal-transition":
            raise _kb_failure("definition-conflict", "The exact KB differs; never overwrite or choose another name.", current_id)
        etag = current.get("@odata.etag")
        if not isinstance(etag, str) or not etag.strip():
            raise _kb_failure("definition-evidence-missing", "Existing KB readback requires an ETag.", current_id)
        plan["expected_etag"] = etag
        if definitions_match(desired, current):
            plan["action"] = "reuse"
    refreshed, refresh_id = _get(source_url, token, transport=transport)
    if refreshed is None or digest(_definition(refreshed)) != source_digest:
        raise _kb_failure("source-drift", "Source changed during planning; refresh its evidence before approval.", refresh_id)
    request_ids = [source_id, current_id, refresh_id]
    if current is not None:
        after, after_id = _get(target, token, transport=transport)
        request_ids.append(after_id)
        if after is None or after.get("@odata.etag") != plan["expected_etag"] or not definitions_match(current, after):
            raise _kb_failure("definition-drift", "KB changed during planning; discard this proposal.", after_id)
    _validate_plan(plan)
    fingerprint = digest(plan)
    mutation_required = plan["action"] != "reuse"
    return {
        "status": "planned", "outcome": plan["outcome"], "plan_fingerprint": fingerprint,
        "execution_input": {"schema_version": "1.0", "plan": plan,
                            "approval": {"confirmed": False, "fingerprint": fingerprint}},
        "approval_summary": {
            "target": {"endpoint": plan["endpoint"], "name": plan["name"], "api_version": version},
            "source": {"name": request["source_name"], "kind": source["kind"]},
            "owner": plan["owner"], "action": plan["action"],
            "execution_required": mutation_required, "mutation_approval_required": mutation_required,
            "reasoning_effort": effort, "output_mode": output,
            **({"previous_mode": {
                "output_mode": current.get("outputMode"),
                "reasoning_effort": current.get("retrievalReasoningEffort"),
            }} if action == "agent-minimal-transition" else {}),
            "model": {k: model[k] for k in ("endpoint", "deployment", "model", "auth")} if model else None,
            "cost_and_data": "Selected KB chat use is billable; retrieved content may move to its endpoint." if model
                             else "No KB chat model; existing Search/source/storage charges still apply.",
            "remaining_checks": ["Source ingestion readiness", "Effective access/network/model prerequisites",
                                 "Supported and unrelated KB queries with original-source citations"],
            "cleanup": "Not approved; retain reused/shared sources, models, roles and data.",
        },
        "verification": {"source_definition": "verified", "knowledge_base": "reused" if not mutation_required else "unverified",
                         "ingestion": "unverified", "retrieval": "unverified",
                         "request_ids": [r for r in request_ids if r]},
        "writes_performed": [],
    }


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


def _creation_callback_response(result: HttpResult) -> HttpResult:
    """Project provenance only, not credential-bearing service bodies or headers."""
    evidence = response_etags(result)
    # Preserve invalidity without forwarding malformed containers that could contain credentials.
    body_etag = evidence["body"] if evidence["body"] is None or isinstance(evidence["body"], str) else []
    etags = tuple(value if isinstance(value, str) else "" for value in evidence["headers"])
    parameters = result.body.get("azureBlobParameters") if isinstance(result.body, dict) else None
    generated = parameters.get("createdResources") if isinstance(parameters, dict) else None
    names = {
        kind: name for kind, name in (generated.items() if isinstance(generated, dict) else ())
        if kind in {"datasource", "dataSourceConnection", "indexer", "skillset", "index"} and isinstance(name, str)
    }
    headers = {"request-id": result.request_id} if isinstance(result.request_id, str) else {}
    return HttpResult(result.status, {
        "@odata.etag": body_etag, "azureBlobParameters": {"createdResources": names},
    }, headers, etags)


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


def _validate_plan(plan: dict[str, Any]) -> None:
    reject_secrets(plan)
    require_allowed_fields(plan, PLAN_FIELDS, label="Search reconciliation plan")
    acquisition = plan.get("ai_services_key_acquisition")
    mi = plan.get("ai_services_managed_identity")
    if mi is not None and (
        mi is not True or plan.get("operation") != "reconcile"
        or plan.get("resource_type") != "knowledge-source"
        or not isinstance(plan.get("desired"), dict) or plan["desired"].get("kind") != "file"
        or acquisition is not None or plan.get("ai_services_api_key_environment") is not None
    ):
        raise file_cu_auth.failure("cu-mi-plan-invalid", "File MI metadata is exclusive to the verified File source workflow, without key channels.")
    if acquisition is not None and (
        plan.get("operation") != "reconcile" or plan.get("resource_type") != "knowledge-source"
        or not isinstance(plan.get("desired"), dict) or plan["desired"].get("kind") != "file"
        or plan.get("ai_services_api_key_environment") is not None
    ):
        raise file_cu_auth.failure("cu-acquisition-invalid", "Private acquisition is exclusive to Standard File source reconciliation, not other resources or auth channels.")
    cleanup_dependencies.validate_guard(plan)
    if "kb_plan_version" in plan or "kb_model" in plan:
        if (
            plan.get("kb_plan_version") != "1.0" or "kb_model" not in plan
            or plan.get("resource_type") != "knowledge-base" or plan.get("operation") != "reconcile"
        ):
            raise _kb_failure("input-schema-invalid", "KB planning metadata requires the versioned KB reconciliation contract.")
        desired = plan.get("desired")
        if not isinstance(desired, dict):
            raise _kb_failure("desired-definition-invalid", "KB desired definition must be an object.")
        effort = desired.get("retrievalReasoningEffort")
        required = desired.get("outputMode") == "answerSynthesis" or (
            isinstance(effort, dict) and effort.get("kind") in ("low", "medium")
        )
        model = _kb_model(plan["kb_model"], required=required)
        expected = [_kb_model_definition(model)] if model else []
        if _definition(desired.get("models", [])) != _definition(expected):
            raise _kb_failure("kb-model-conflict", "KB wire models must match the selected independent chat configuration.")
    for field, allowed in (
        ("data_movement", {"boundary", "result"}),
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
    operation = plan.get("operation")
    if operation not in {"reconcile", "delete"}:
        raise HelperFailure(
            "operation-invalid",
            "operation must be reconcile or delete.",
            blocked_at="input-resolution",
        )
    if operation == "reconcile":
        if plan.get("cleanup_approved") is not False:
            raise HelperFailure(
                "cleanup-boundary-invalid",
                "A reconciliation plan must set cleanup_approved to false.",
                blocked_at="confirmation",
            )
        desired = plan.get("desired")
        if not isinstance(desired, dict) or desired.get("name") != plan.get("name"):
            raise HelperFailure(
                "desired-definition-invalid",
                "desired must be an object whose name matches the target name.",
                blocked_at="input-resolution",
            )
        if plan.get("resource_type") == "knowledge-source":
            kind = desired.get("kind")
            if kind not in {"file", "azureBlob"}:
                raise HelperFailure(
                    "source-kind-invalid",
                    "Only file and azureBlob knowledge sources are supported.",
                    blocked_at="input-resolution",
                )
            if kind == "file" and plan.get("api_version") != "2026-08-01-preview":
                raise HelperFailure(
                    "api-version-invalid",
                    "This helper uses 2026-08-01-preview for multipart metadata and 200-file inventories. "
                    "The service also supports 2026-05-01-preview minimal; use a compatible client or explicitly approve August.",
                    blocked_at="input-resolution",
                )
            if kind == "file":
                ingestion = (
                    desired.get("fileParameters", {}).get("ingestionParameters", {})
                    if isinstance(desired.get("fileParameters"), dict)
                    else {}
                )
                if not isinstance(ingestion, dict):
                    raise HelperFailure(
                        "desired-definition-invalid",
                        "File ingestionParameters must be an object.",
                        blocked_at="input-resolution",
                    )
                mode = ingestion.get("contentExtractionMode")
                if mode not in {"minimal", "standard"}:
                    raise HelperFailure(
                        "desired-definition-invalid",
                        "File contentExtractionMode must be minimal or standard.",
                        blocked_at="input-resolution",
                    )
                credential_environment = plan.get("ai_services_api_key_environment")
                if mode == "standard":
                    if (
                        (acquisition is None and mi is not True and (
                            not isinstance(credential_environment, str)
                            or ENVIRONMENT_NAME.fullmatch(credential_environment) is None
                        ))
                        or not isinstance(ingestion.get("aiServices"), dict)
                        or not ingestion["aiServices"].get("uri")
                    ):
                        raise HelperFailure(
                            "credential-channel-invalid",
                            "Standard extraction requires aiServices.uri and an approved private ARM acquisition or existing API-key environment variable name.",
                            blocked_at="input-resolution",
                        )
                    if acquisition is not None:
                        file_cu_auth.validate_acquisition(acquisition, ingestion["aiServices"]["uri"])
                elif credential_environment is not None or acquisition is not None or mi is not None:
                    raise HelperFailure(
                        "credential-channel-invalid",
                        "Minimal extraction must not declare an AI Services credential channel.",
                        blocked_at="input-resolution",
                    )
            else:
                if plan.get("ai_services_api_key_environment") is not None:
                    raise HelperFailure(
                        "credential-channel-invalid", "Blob ingestion uses keyless dependencies, not File credential channels.",
                        blocked_at="input-resolution",
                    )
                parameters = desired.get("azureBlobParameters")
                evidence = plan.get("source_evidence")
                if isinstance(evidence, dict):
                    require_allowed_fields(
                        evidence,
                        {
                            "verified",
                            "inventory_digest",
                            "path_verified",
                            "acl_verified",
                        },
                        label="Source evidence",
                    )
                if (
                    not isinstance(parameters, dict)
                    or not isinstance(parameters.get("connectionString"), str)
                    or RESOURCE_ID_CONNECTION.fullmatch(
                        parameters["connectionString"]
                    )
                    is None
                    or not isinstance(parameters.get("containerName"), str)
                    or not parameters["containerName"]
                    or "folderPath" not in parameters
                    or not isinstance(parameters.get("isADLSGen2"), bool)
                    or not isinstance(evidence, dict)
                    or evidence.get("verified") is not True
                    or SHA256.fullmatch(str(evidence.get("inventory_digest"))) is None
                ):
                    raise HelperFailure(
                        "source-evidence-invalid",
                        "Blob and ADLS plans require an exact ResourceId boundary and verified immutable inventory evidence.",
                        blocked_at="input-resolution",
                    )
                if parameters["isADLSGen2"] and (
                    evidence.get("path_verified") is not True
                    or evidence.get("acl_verified") is not True
                ):
                    raise HelperFailure(
                        "adls-evidence-unverified",
                        "ADLS reconciliation requires exact path and ACL readback evidence.",
                        blocked_at="reconciliation",
                    )
        if plan.get("resource_type") == "knowledge-base":
            sources = desired.get("knowledgeSources")
            if not isinstance(sources, list) or len(sources) != 1:
                raise HelperFailure(
                    "source-count-invalid",
                    "A knowledge base must name exactly one knowledge source.",
                    blocked_at="input-resolution",
                )
            verified_source = plan.get("verified_source")
            if isinstance(verified_source, dict):
                require_allowed_fields(
                    verified_source,
                    {"name", "verified", "definition_digest"},
                    label="Verified source",
                )
            if (
                not isinstance(sources[0], dict)
                or not isinstance(verified_source, dict)
                or verified_source.get("name") != sources[0].get("name")
                or verified_source.get("verified") is not True
                or SHA256.fullmatch(str(verified_source.get("definition_digest")))
                is None
            ):
                raise HelperFailure(
                    "source-drift",
                    "Knowledge-base reconciliation requires exact verified source readback.",
                    blocked_at="reconciliation",
                )
            _odata_name(verified_source.get("name"))
            if plan.get("api_version") == "2026-04-01":
                preview_fields = {
                    "outputMode",
                    "retrievalReasoningEffort",
                    "retrievalInstructions",
                    "answerInstructions",
                }
                if preview_fields.intersection(desired) or desired.get("models"):
                    raise HelperFailure(
                        "mode-api-mismatch",
                        "GA knowledge bases must omit preview output, reasoning, instruction, and model fields.",
                        blocked_at="input-resolution",
                    )
            else:
                mode = desired.get("outputMode")
                effort = desired.get("retrievalReasoningEffort")
                if (
                    mode not in {"extractiveData", "answerSynthesis"}
                    or not isinstance(effort, dict)
                    or effort.get("kind") not in {"minimal", "low", "medium"}
                    or (
                        (mode == "answerSynthesis" or effort.get("kind") in {"low", "medium"})
                        and (
                            not isinstance(desired.get("models"), list)
                            or len(desired["models"]) != 1
                        )
                    )
                ):
                    raise HelperFailure(
                        "mode-api-mismatch",
                        "Preview knowledge-base output mode, reasoning effort, and model selection are inconsistent.",
                        blocked_at="input-resolution",
                    )
    else:
        if plan.get("plan_kind") != "cleanup" or plan.get("cleanup_approved") is not True:
            raise HelperFailure(
                "cleanup-approval-mismatch",
                "Delete requires a separate cleanup plan with cleanup_approved true.",
                blocked_at="confirmation",
            )
        if not isinstance(plan.get("owned_definition_digest"), str):
            raise HelperFailure(
                "ownership-unproven",
                "Delete requires the approved owned definition digest.",
                blocked_at="reconciliation",
            )


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


def execute(
    document: dict[str, Any],
    *,
    token_provider: TokenProvider = azure_cli_token,
    transport: Transport = http_request,
    credential_provider=None,
    managed_identity_verified: bool = False,
    on_created: Callable[..., None] | None = None,
    cleanup_capture: cleanup_receipts.Capture | None = None,
    on_file_acknowledged: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Full callbacks are keyless Blob/File MI only; File ACK callbacks receive provenance only."""
    guard = document.get("plan", {}).get("dependency_guard")
    if guard is None:
        return _execute(document, token_provider=token_provider, transport=transport, on_created=on_created,
                        cleanup_capture=cleanup_capture, credential_provider=credential_provider,
                        on_file_acknowledged=on_file_acknowledged,
                        managed_identity_verified=managed_identity_verified)
    tokens: dict[str, str] = {}

    def cached_token(audience: str) -> str:
        if audience not in tokens:
            tokens[audience] = token_provider(audience)
        return tokens[audience]

    try:
        result = _execute(document, token_provider=cached_token, transport=transport, on_created=on_created,
                          cleanup_capture=cleanup_capture, credential_provider=credential_provider,
                          on_file_acknowledged=on_file_acknowledged,
                          managed_identity_verified=managed_identity_verified)
    except HelperFailure as failure:
        if isinstance(guard, dict) and guard.get("kind") == "search-source" and (failure.partial or failure.writes):
            failure.resources_remaining.extend(
                {"type": item["type"], "name": item["name"], "absence": "unverified"}
                for item in guard["generated"]
            )
        raise
    if guard is None or guard.get("kind") != "search-source":
        return result
    plan = document["plan"]
    written = bool(result["resources"].get("deleted"))
    writes = [{"action": "deleted", "type": "knowledge-source", "name": plan["name"]}] if written else []
    token = cached_token(SEARCH_AUDIENCE)
    verified = []
    for position, item in enumerate(guard["generated"]):
        pending = [
            f"generated-absence-unverified:{later['type']}:{later['name']}"
            for later in guard["generated"][position + 1:]
        ]
        url = (
            f"{plan['endpoint'].rstrip('/')}/{cleanup_dependencies.COLLECTIONS[item['type']]}"
            f"('{odata_name(item['name'])}')?api-version={plan['api_version']}"
        )
        identity = {"type": item["type"], "name": item["name"], "service_managed": True}
        try:
            child, _ = read_resource(url, token, transport=transport)
        except HelperFailure as failure:
            raise HelperFailure(
                failure.code, "Source is absent but generated-child absence readback failed.",
                blocked_at="verification", writes=writes, partial=written,
                resources_remaining=[{**identity, "absence": "unverified"}],
                warnings=pending,
                request_id=failure.request_id, status=failure.http_status,
            ) from failure
        if child is not None:
            unchanged = child.get("@odata.etag") == item["etag"] and digest(child) == item["definition_digest"]
            raise HelperFailure(
                "generated-absence-unverified", "Source is absent but a generated identity remains; never delete it independently.",
                blocked_at="verification", writes=writes, partial=written,
                resources_remaining=[identity] if unchanged else [],
                warnings=pending + ([] if unchanged else [f"generated-incarnation-unowned:{item['type']}:{item['name']}"]),
            )
        verified.append(identity)
    result["verification"]["generated_absence"] = True
    result["resources"]["deleted" if written else "skipped"].extend(verified)
    return result


def _execute(
    document: dict[str, Any],
    *,
    token_provider: TokenProvider = azure_cli_token,
    transport: Transport = http_request,
    credential_provider=None,
    managed_identity_verified: bool = False,
    on_created: Callable[..., None] | None = None,
    cleanup_capture: cleanup_receipts.Capture | None = None,
    on_file_acknowledged: Callable[..., None] | None = None,
) -> dict[str, Any]:
    plan = document["plan"]
    fingerprint = document["_computed_fingerprint"]
    _validate_plan(plan)
    if on_file_acknowledged is not None and (
        not callable(on_file_acknowledged) or plan.get("operation") != "reconcile"
        or plan.get("action") != "create" or plan.get("resource_type") != "knowledge-source"
        or plan.get("desired", {}).get("kind") != "file"
    ):
        raise HelperFailure("creation-callback-unsupported", "Filtered File ACK capture requires an approved File create.",
                            blocked_at="input-resolution")
    acquisition = plan.get("ai_services_key_acquisition")
    if (plan.get("ai_services_managed_identity") is True) != (managed_identity_verified is True):
        raise file_cu_auth.failure("cu-mi-executor-required", "MI requires the approved versioned File executor and fresh Search identity/CU role readbacks.")
    if cleanup_capture is not None and (
        not isinstance(cleanup_capture, cleanup_receipts.Capture)
        or cleanup_capture.plan_digest != fingerprint or cleanup_capture.owner != plan.get("owner")
        or plan.get("operation") != "reconcile"
    ):
        raise HelperFailure("cleanup-receipt-input-invalid", "Capture must bind this approved creation operation.", blocked_at="confirmation")
    if on_created is not None and (
        not callable(on_created) or plan.get("operation") != "reconcile"
        or plan.get("resource_type") != "knowledge-source"
        or (plan.get("desired", {}).get("kind") != "azureBlob"
            and not (plan.get("ai_services_managed_identity") is True and managed_identity_verified is True))
        or plan.get("ai_services_api_key_environment") is not None
        or acquisition is not None
    ):
        raise HelperFailure(
            "creation-callback-unsupported", "Creation callbacks support only keyless Blob or verified File MI plans, never credentialized File/CU wire.",
            blocked_at="input-resolution",
        )
    if (acquisition is not None) != (credential_provider is not None):
        raise file_cu_auth.failure("cu-executor-required", "Private acquisition requires the approved versioned file_source executor; no standalone credential reads.")
    url = _resource_url(plan)
    if plan.get("kb_plan_version") == "1.0":
        transport = _kb_guard(plan, transport)
    token = token_provider(SEARCH_AUDIENCE)
    current, initial_request_id = _get(url, token, transport=transport)
    operation = plan["operation"]
    outcome = str(plan.get("outcome") or f"search-{operation}")
    owner = plan.get("owner")

    if operation == "delete":
        if current is None:
            return _completed(
                outcome,
                fingerprint,
                plan,
                action="skipped",
                readback=None,
                request_ids=[initial_request_id],
                absence=True,
            )
        current_definition = _definition(current)
        if digest(current_definition) != plan["owned_definition_digest"]:
            raise HelperFailure(
                "ownership-unproven",
                "Current definition no longer matches the approved owned definition.",
                blocked_at="reconciliation",
            )
        expected_etag = plan.get("expected_etag")
        if not expected_etag or current.get("@odata.etag") != expected_etag:
            raise HelperFailure(
                "definition-drift",
                "Current ETag does not match the approved cleanup plan.",
                blocked_at="reconciliation",
            )
        if plan.get("dependency_guard") is not None:
            cleanup_dependencies.verify_search(plan, current, token, transport=transport)
        try:
            result = transport(
                "DELETE",
                url,
                token,
                headers={"If-Match": expected_etag},
            )
        except HelperFailure as failure:
            if failure.http_status == 404:
                return _completed(
                    outcome,
                    fingerprint,
                    plan,
                    action="skipped",
                    readback=None,
                    request_ids=[initial_request_id, failure.request_id],
                    absence=True,
                )
            if not is_ambiguous_mutation_failure(failure):
                raise
            return _recover_ambiguous_delete(
                outcome,
                fingerprint,
                plan,
                url,
                token,
                initial_request_id,
                failure,
                transport=transport,
            )
        if result.status not in {200, 204}:
            if result.status == 404:
                return _completed(
                    outcome,
                    fingerprint,
                    plan,
                    action="skipped",
                    readback=None,
                    request_ids=[initial_request_id, result.request_id],
                    absence=True,
                )
            if result.status in {408, 429} or result.status >= 500:
                return _recover_ambiguous_delete(
                    outcome,
                    fingerprint,
                    plan,
                    url,
                    token,
                    initial_request_id,
                    HelperFailure(
                        "delete-outcome-ambiguous",
                        f"Delete returned ambiguous HTTP {result.status}.",
                        blocked_at="execution",
                        request_id=result.request_id,
                        status=result.status,
                        partial=True,
                    ),
                    transport=transport,
                )
            raise HelperFailure(
                "delete-failed",
                f"Delete returned unexpected HTTP {result.status}.",
                blocked_at="execution",
                request_id=result.request_id,
                status=result.status,
            )
        write = {"action": "deleted", "name": plan["name"]}
        try:
            after, verify_request_id = _get(url, token, transport=transport)
        except HelperFailure as failure:
            raise HelperFailure(
                failure.code,
                failure.message,
                blocked_at=failure.blocked_at,
                writes=[write, *failure.writes],
                resources_remaining=[_target_identity(plan)],
                request_id=failure.request_id,
                status=failure.http_status,
                partial=True,
            ) from failure
        if after is not None:
            raise HelperFailure(
                "absence-unverified",
                "The exact resource still exists after delete.",
                blocked_at="verification",
                writes=[write],
                resources_remaining=[_target_identity(plan)],
                request_id=verify_request_id,
                partial=True,
            )
        return _completed(
            outcome,
            fingerprint,
            plan,
            action="deleted",
            readback=None,
            request_ids=[initial_request_id, result.request_id, verify_request_id],
            absence=True,
        )

    source_request_id = None
    if plan["resource_type"] == "knowledge-base":
        verified_source = plan["verified_source"]
        source_url = _resource_url({
            **plan, "resource_type": "knowledge-source", "name": verified_source["name"],
        })
        source, source_request_id = _get(source_url, token, transport=transport)
        if source is None or digest(_definition(source)) != verified_source["definition_digest"]:
            raise HelperFailure(
                "source-drift",
                "The source is absent or its current definition differs from the approved source.",
                blocked_at="reconciliation",
                request_id=source_request_id,
            )

    desired = plan["desired"]
    if current is not None and _definition(desired) == _definition(current):
        if (
            plan.get("action") == "reuse"
            and plan.get("expected_etag") is not None
            and current.get("@odata.etag") != plan["expected_etag"]
        ):
            raise HelperFailure(
                "definition-drift",
                "Current ETag does not match the approved reuse plan.",
                blocked_at="reconciliation",
            )
        return _completed(
            outcome,
            fingerprint,
            plan,
            action="reused",
            readback=current,
            request_ids=[initial_request_id, source_request_id],
            absence=False,
        )

    action = plan.get("action")
    headers = {
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    if current is None:
        if action != "create":
            raise HelperFailure(
                "target-absent",
                "The approved update target does not exist.",
                blocked_at="reconciliation",
            )
        headers["If-None-Match"] = "*"
        completed_action = "created"
    else:
        if action != "update":
            raise HelperFailure(
                "definition-conflict",
                "An existing non-equivalent resource cannot be overwritten by this plan.",
                blocked_at="reconciliation",
            )
        expected_etag = plan.get("expected_etag")
        if not expected_etag or current.get("@odata.etag") != expected_etag:
            raise HelperFailure(
                "definition-drift",
                "Current ETag does not match the approved update plan.",
                blocked_at="reconciliation",
            )
        headers["If-Match"] = expected_etag
        completed_action = "updated"

    request_desired = copy.deepcopy(desired)
    credential_environment = plan.get("ai_services_api_key_environment")
    if credential_environment is not None or acquisition is not None:
        secret = credential_provider() if acquisition is not None else os.environ.get(credential_environment)
        if not secret:
            raise HelperFailure(
                "credential-unavailable",
                "The approved AI Services credential environment variable is unset.",
                blocked_at="execution",
            )
        request_desired["fileParameters"]["ingestionParameters"]["aiServices"][
            "apiKey"
        ] = secret
    try:
        result = transport(
            "PUT",
            url,
            token,
            body=canonical_bytes(request_desired),
            headers=headers,
        )
    except HelperFailure as failure:
        if not is_ambiguous_mutation_failure(failure):
            raise
        return _recover_ambiguous_put(
            outcome,
            fingerprint,
            plan,
            url,
            token,
            initial_request_id,
            completed_action,
            failure,
            transport=transport,
            source_request_id=source_request_id,
        )
    finally:
        if credential_environment is not None or acquisition is not None:
            request_desired["fileParameters"]["ingestionParameters"]["aiServices"].pop("apiKey", None)
            secret = None
    if result.status not in {200, 201}:
        if result.status in {408, 429} or result.status >= 500:
            return _recover_ambiguous_put(
                outcome,
                fingerprint,
                plan,
                url,
                token,
                initial_request_id,
                completed_action,
                HelperFailure(
                    "mutation-outcome-ambiguous",
                    f"Create or update returned ambiguous HTTP {result.status}.",
                    blocked_at="execution",
                    request_id=result.request_id,
                    status=result.status,
                    partial=True,
                    retry_after=result.retry_after,
                    recovery_deadline=result.recovery_deadline,
                ),
                transport=transport,
                source_request_id=source_request_id,
            )
        raise HelperFailure(
            "mutation-failed",
            f"Create or update returned unexpected HTTP {result.status}.",
            blocked_at="execution",
            request_id=result.request_id,
            status=result.status,
        )
    write = {"action": completed_action, "name": plan["name"]}
    recovery = ReadRecovery(deadline=result.recovery_deadline)
    try:
        if completed_action == "created" and cleanup_capture is not None:
            cleanup_receipts.search_ack(cleanup_capture, plan, result)
        # Outside the ambiguous-PUT handler: callback/IO failure cannot replay or undo this write.
        if completed_action == "created" and (on_created is not None or on_file_acknowledged is not None):
            try:
                if on_created is not None:
                    on_created(
                        response=_creation_callback_response(result), url=url, body=canonical_bytes(request_desired),
                        headers={key: value for key, value in headers.items()
                                 if key in {"Content-Type", "Prefer", "If-None-Match", "If-Match"}},
                    )
                if on_file_acknowledged is not None:
                    on_file_acknowledged({
                        "status": result.status, "request_id": ReadRecovery.safe_id(result.request_id) if result.request_id else None,
                        "etag_evidence": response_etags(_creation_callback_response(result)),
                    })
            except OSError as failure:
                raise HelperFailure(
                    "creation-receipt-persistence-failed",
                    f"Acknowledged creation receipt persistence failed ({type(failure).__name__}); private details withheld.",
                    blocked_at="local-persistence", request_id=result.request_id, status=result.status,
                ) from failure
        after, verify_request_id = _get(url, token, transport=transport, recovery=recovery)
        if completed_action == "created" and cleanup_capture is not None:
            cleanup_receipts.search_finish(cleanup_capture, plan, after, token, transport)
    except HelperFailure as failure:
        recovery.annotate(failure)
        if result.request_id:
            failure.warnings.append("Acknowledged write request ID: " + recovery.safe_id(result.request_id))
        raise HelperFailure(
            failure.code,
            failure.message,
            blocked_at=failure.blocked_at,
            writes=[write, *failure.writes],
            resources_remaining=([_target_identity(plan)] if completed_action == "created" else []) + failure.resources_remaining,
            resources_reused=([_target_identity(plan)] if completed_action == "updated" else []) + failure.resources_reused,
            resources_unverified=failure.resources_unverified,
            warnings=failure.warnings,
            request_id=failure.request_id,
            status=failure.http_status,
            partial=True,
        ) from failure
    if after is None or _definition(desired) != _definition(after):
        raise HelperFailure(
            "readback-mismatch",
            "Readback does not contain the approved definition.",
            blocked_at="verification",
            writes=[write],
            resources_remaining=[_target_identity(plan)] if completed_action == "created" else [],
            resources_reused=[_target_identity(plan)] if completed_action == "updated" else [],
            request_id=verify_request_id,
            partial=True,
            warnings=[*recovery.diagnostics(), *(
                ["Acknowledged write request ID: " + recovery.safe_id(result.request_id)]
                if result.request_id else []
            )],
        )
    completed = _completed(
        outcome,
        fingerprint,
        plan,
        action=completed_action,
        readback=after,
        request_ids=[initial_request_id, source_request_id, result.request_id, *recovery.request_ids],
        absence=False,
    )
    completed["warnings"].extend(recovery.warnings)
    return completed


def _target_identity(plan: dict[str, Any]) -> dict[str, Any]:
    return {"type": plan["resource_type"], "name": plan["name"]}


def _recover_ambiguous_put(
    outcome: str,
    fingerprint: str,
    plan: dict[str, Any],
    url: str,
    token: str,
    initial_request_id: str | None,
    completed_action: str,
    failure: HelperFailure,
    *,
    transport: Transport,
    source_request_id: str | None = None,
) -> dict[str, Any]:
    identity = _target_identity(plan)
    recovery = ReadRecovery()

    def readback():
        recovery.delay(failure)
        return _get(url, token, transport=transport, recovery=recovery)

    if completed_action == "created":
        observed = []
        warnings = list(failure.warnings)
        read_ids = [value for value in (initial_request_id, source_request_id) if value]
        try:
            after, read_id = readback()
        except HelperFailure as readback_failure:
            if readback_failure.request_id:
                read_ids.append(readback_failure.request_id)
            warnings.append(f"Ambiguous-create readback also failed ({readback_failure.code}); original mutation error retained.")
        else:
            if read_id:
                read_ids.append(read_id)
            if after is not None:
                observed.append(identity)
                warnings.append("Readback resources are observations only, not creation ownership or authorized reuse.")
        if read_ids:
            warnings.append("Read-only request IDs: " + ", ".join(recovery.safe_id(value) for value in read_ids))
        warnings.extend(recovery.diagnostics())
        raise HelperFailure(
            failure.code, failure.message, blocked_at=failure.blocked_at,
            resources_reused=observed, request_id=failure.request_id, status=failure.http_status,
            partial=True, warnings=warnings,
        ) from failure
    message = "Same-identity readback did not prove the approved create or update."
    try:
        after, verify_request_id = readback()
    except HelperFailure as readback_failure:
        verify_request_id = readback_failure.request_id
        message = "Create or update outcome and same-identity readback are ambiguous."
        detail = (
            f"{message} Readback failure: {readback_failure.code}; "
            f"HTTP {readback_failure.http_status}; request ID {recovery.safe_id(verify_request_id)}."
        )
    else:
        if after is not None and _definition(plan["desired"]) == _definition(after):
            completed = _completed(
                outcome,
                fingerprint,
                plan,
                action=completed_action,
                readback=after,
                request_ids=[
                    initial_request_id,
                    source_request_id,
                    failure.request_id,
                    *recovery.request_ids,
                ],
                absence=False,
            )
            completed["warnings"].extend(recovery.warnings)
            return completed
        detail = f"{message} Readback request ID: {verify_request_id}."
    if completed_action == "updated":
        raise HelperFailure(
            failure.code,
            failure.message,
            blocked_at=failure.blocked_at,
            writes=failure.writes,
            resources_reused=[identity],
            request_id=failure.request_id,
            status=failure.http_status,
            partial=True,
            warnings=[*failure.warnings, detail, *recovery.diagnostics()],
        )
    raise HelperFailure(
        "mutation-outcome-ambiguous",
        message,
        blocked_at="verification",
        resources_remaining=[identity],
        request_id=verify_request_id or failure.request_id,
        status=failure.http_status,
        partial=True,
    )


def _recover_ambiguous_delete(
    outcome: str,
    fingerprint: str,
    plan: dict[str, Any],
    url: str,
    token: str,
    initial_request_id: str | None,
    failure: HelperFailure,
    *,
    transport: Transport,
) -> dict[str, Any]:
    identity = _target_identity(plan)
    try:
        after, verify_request_id = _get(url, token, transport=transport)
    except HelperFailure as readback_failure:
        raise HelperFailure(
            "delete-outcome-ambiguous",
            "Delete outcome and same-identity readback are ambiguous.",
            blocked_at="verification",
            resources_remaining=[identity],
            request_id=readback_failure.request_id or failure.request_id,
            status=failure.http_status,
            partial=True,
        ) from readback_failure
    if after is not None:
        raise HelperFailure(
            "delete-outcome-ambiguous",
            "Same-identity readback still found the resource after an ambiguous delete.",
            blocked_at="verification",
            resources_remaining=[identity],
            request_id=verify_request_id or failure.request_id,
            status=failure.http_status,
            partial=True,
        )
    return _completed(
        outcome,
        fingerprint,
        plan,
        action="deleted",
        readback=None,
        request_ids=[
            initial_request_id,
            failure.request_id,
            verify_request_id,
        ],
        absence=True,
    )


def _completed(
    outcome: str,
    fingerprint: str,
    plan: dict[str, Any],
    *,
    action: str,
    readback: dict[str, Any] | None,
    request_ids: list[str | None],
    absence: bool,
) -> dict[str, Any]:
    resource = {
        "type": plan["resource_type"],
        "name": plan["name"],
        "etag": readback.get("@odata.etag") if readback else None,
        "definition_digest": digest(_definition(readback)) if readback else None,
    }
    resources = {"created": [], "reused": [], "updated": [], "skipped": []}
    if action in resources:
        resources[action].append(resource)
    elif action == "deleted":
        resources["deleted"] = [resource]
    return {
        "status": "completed",
        "outcome": outcome,
        "approved_plan": {"fingerprint": fingerprint, "confirmed": True},
        "resources": resources,
        "api_contracts": [
            {
                "operation": plan["operation"],
                "version": plan["api_version"],
                "preview": plan["api_version"].endswith("-preview"),
            }
        ],
        "data_movement": plan.get("data_movement", {"boundary": None, "result": "none"}),
        "auth": {"mode": "entra-user", "principals": []},
        "rbac": plan.get("rbac", {"assignments": []}),
        "network": plan.get("network", {"posture": "preserved", "evidence": None}),
        "verification": {
            "readback": resource,
            "absence": absence,
            "request_ids": [item for item in request_ids if item],
            "idempotency": "exact readback is zero-write",
        },
        "warnings": [],
        "ownership": {
            "run_owned": [resource] if action in {"created", "deleted"} else [],
            "reused_not_owned": [resource] if action in {"reused", "updated"} else [],
            "owner": plan.get("owner"),
        },
        "cleanup": {
            "status": (
                "completed"
                if plan["operation"] == "delete" and absence
                else "not-requested"
            ),
            "separate_confirmation_required": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    try:
        from .private_artifacts import add_execution_output_argument, emit_plan_result, validate_execution_output_mode
    except ImportError:
        from private_artifacts import add_execution_output_argument, emit_plan_result, validate_execution_output_mode
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--input", type=Path)
    modes.add_argument("--plan", type=Path, help="Build an unapproved KB plan using exact read-only discovery.")
    cleanup_receipts.add_argument(parser)
    add_execution_output_argument(parser)
    args = parser.parse_args(argv)
    fingerprint: str | None = None
    owner: Any = None
    outcome = "search-resource-reconciliation"
    capture = None
    try:
        validate_execution_output_mode(args)
        if args.plan and args.cleanup_receipt_dir:
            raise HelperFailure("input-schema-invalid", "Creation capture is only available with approved --input.", blocked_at="confirmation")
        if args.plan:
            try:
                from ._bootstrap_io import read_json
            except ImportError:
                from _bootstrap_io import read_json
            outcome = "create-knowledge-base"
            request = read_json(args.plan)
            owner = request.get("owner") if isinstance(request, dict) else None
            result = plan_knowledge_base(request)
            emit_plan_result(result, args.execution_output, preserve_unapproved_input=True)
            return 0
        document, plan, fingerprint = load_approved_input(args.input)
        document["_computed_fingerprint"] = fingerprint
        owner = plan.get("owner")
        outcome = str(plan.get("outcome") or outcome)
        capture = cleanup_receipts.Capture(args.cleanup_receipt_dir, document) if args.cleanup_receipt_dir else None
        result = execute(document, **({"cleanup_capture": capture} if capture else {}))
    except HelperFailure as failure:
        result = blocked_result(
            failure,
            outcome=outcome,
            fingerprint=fingerprint,
            owner=owner,
        )
        if capture is not None:
            result["cleanup_receipts"] = capture.summaries
        emit_result(result)
        return 3 if result["status"] == "partial" else 2
    if capture is not None:
        result["cleanup_receipts"] = capture.summaries
    emit_result(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
