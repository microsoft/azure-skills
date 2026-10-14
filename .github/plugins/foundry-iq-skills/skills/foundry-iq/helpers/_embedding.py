"""Shared embedding choices and readback validation, without workflow orchestration."""
from __future__ import annotations

import copy
import json
import re
from typing import Any
from urllib.parse import urlsplit

try:
    from ._common import HelperFailure, reject_secrets, require_allowed_fields, model_definition
    from . import _search_read
except ImportError:
    from _common import HelperFailure, reject_secrets, require_allowed_fields, model_definition
    import _search_read


MODELS = {"text-embedding-ada-002": (1536, 1536),
          "text-embedding-3-small": (1, 1536), "text-embedding-3-large": (1, 3072)}


def fail(code: str, message: str) -> HelperFailure:
    return HelperFailure(code, message, blocked_at="vector-verification")


def _text(value: Any, *, maximum: int = 4096) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def _json_valid(value: Any) -> None:
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (UnicodeError, TypeError, ValueError) as exc:
        raise fail("input-schema-invalid", "Evidence must be finite, valid UTF-8 JSON.") from exc


def validate_choice(value: Any, *, enabled: bool, api_version: str) -> dict[str, Any] | None:
    if not enabled:
        if value is not None:
            raise fail("embedding-choice-conflict", "Lexical planning must omit embedding configuration.")
        return None
    if not isinstance(value, dict):
        raise fail("embedding-prerequisite-missing", "Vector planning requires resolved embedding choices.")
    reject_secrets(value)
    require_allowed_fields(value, {
        "endpoint", "deployment", "model", "dimensions", "model_version", "auth", "prerequisites",
    }, label="embedding choices")
    if api_version not in {"2026-04-01", "2026-08-01-preview"}:
        raise fail("embedding-version-unsupported", "Unsupported Search embedding API version.")
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        uri = urlsplit(value.get("endpoint") if isinstance(value.get("endpoint"), str) else "")
        valid_endpoint = (
            uri.scheme == "https" and uri.port is None and not uri.username and not uri.password
            and not uri.query and not uri.fragment and uri.path in {"", "/"}
            and re.fullmatch(
                r"[a-z0-9][a-z0-9-]{0,62}\.(openai\.azure\.com|services\.ai\.azure\.com|cognitiveservices\.azure\.com)",
                uri.netloc,
            )
        )
    except (UnicodeError, ValueError, TypeError) as exc:
        raise fail("embedding-choice-invalid", "Embedding choices must be valid UTF-8 and an exact HTTPS endpoint.") from exc
    if (
        not valid_endpoint or not _text(value.get("deployment"), maximum=64)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value["deployment"])
        or not isinstance(value.get("model"), str) or value["model"] not in MODELS
    ):
        raise fail("embedding-choice-invalid", "Select a supported Azure OpenAI endpoint, deployment and embedding model.")
    if value.get("dimensions") != "service-managed" or value.get("model_version") != "deployment-managed":
        raise fail("embedding-parameter-unsupported", "Knowledge-source APIs expose neither dimensions nor a model-version pin; custom values are unsupported.")
    if value.get("auth") != "system-assigned":
        raise fail("embedding-auth-unsupported", "This planner supports only the existing Search system-assigned identity; no keys or identity changes.")
    prerequisites = value.get("prerequisites")
    if not isinstance(prerequisites, dict):
        raise fail("embedding-prerequisite-missing", "Provide current deployment, identity and network evidence references.")
    require_allowed_fields(prerequisites, {"deployment", "identity", "network"}, label="embedding prerequisites")
    if any(not _text(prerequisites.get(key)) for key in ("deployment", "identity", "network")):
        raise fail("embedding-prerequisite-missing", "Owner-verified deployment/model, Search identity/RBAC and network evidence is required.")
    return copy.deepcopy(value)


def verify_model_readback(choice: dict[str, Any], model: Any) -> None:
    parameters = model.get("azureOpenAIParameters") if isinstance(model, dict) else None
    if not isinstance(parameters, dict):
        raise fail("embedding-readback-invalid", "Observed embedding parameters must be an object.")
    # Generic definition normalization omits apiKey; check auth evidence before matching.
    api_key = parameters.get("apiKey")
    if (
        api_key is not None and not (isinstance(api_key, str) and api_key == "")
        or parameters.get("authIdentity") is not None
    ):
        raise fail("embedding-auth-conflict", "Observed embedding authentication does not prove the selected system-assigned mode; key/identity details withheld.")
    if not _search_read.definitions_match(model_definition(choice), model):
        raise fail("embedding-readback-mismatch", "Observed embedding endpoint/deployment/model differs from the selected configuration.")


def verify_source_readback(choice: dict[str, Any] | None, current: Any) -> None:
    if choice is None or current is None:
        return
    kind = current.get("kind") if isinstance(current, dict) else None
    if kind not in ("file", "azureBlob"):
        raise fail("embedding-readback-invalid", "Expected a File/Blob embedding source readback.")
    parameters = current.get("fileParameters" if kind == "file" else "azureBlobParameters")
    ingestion = parameters.get("ingestionParameters") if isinstance(parameters, dict) else None
    verify_model_readback(choice, ingestion.get("embeddingModel") if isinstance(ingestion, dict) else None)


def validate_plan_choice(plan: dict[str, Any]) -> None:
    if "embedding" not in plan:
        return
    source = plan.get("source", {})
    choice = validate_choice(plan["embedding"], enabled=True, api_version=source.get("api_version"))
    desired = source.get("desired", {})
    parameters = desired.get("fileParameters" if desired.get("kind") == "file" else "azureBlobParameters", {})
    ingestion = parameters.get("ingestionParameters", {})
    if ingestion.get("contentExtractionMode") not in ("minimal", "standard") or ingestion.get("embeddingModel") != model_definition(choice):
        raise fail("embedding-plan-mismatch", "Embedding choices and the selected extraction definition must match.")


def summary(choice: dict[str, Any]) -> dict[str, Any]:
    return {
        key: choice[key] for key in ("endpoint", "deployment", "model", "dimensions", "model_version", "auth")
    } | {
        "purpose": "Source vectors for hybrid/vector search; not CU extraction or KB chat.",
        "cost": "Creating/ingesting this source invokes billable embeddings and moves content to the selected model. Query vectorization needs separate approval.",
        "prerequisites": "Supplied evidence references are owner-verified, not proof of effective access or deployed model version.",
        "answer_synthesis": "Not configured; ingestion dependencies do not configure KB reasoning, reranking or answer synthesis.",
    }
