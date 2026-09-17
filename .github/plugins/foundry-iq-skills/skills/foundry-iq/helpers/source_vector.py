from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    from . import search_reconcile
    from ._common import (
        SEARCH_AUDIENCE, HelperFailure, TokenProvider, Transport, azure_cli_token,
        blocked_result, digest, emit_result, http_request, load_approved_input,
        odata_name, reject_secrets, require_allowed_fields,
    )
except ImportError:
    import search_reconcile
    from _common import (
        SEARCH_AUDIENCE, HelperFailure, TokenProvider, Transport, azure_cli_token,
        blocked_result, digest, emit_result, http_request, load_approved_input,
        odata_name, reject_secrets, require_allowed_fields,
    )


MODELS = {"text-embedding-ada-002": (1536, 1536),
          "text-embedding-3-small": (1, 1536), "text-embedding-3-large": (1, 3072)}
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")


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


def model_definition(choice: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "azureOpenAI", "azureOpenAIParameters": {
        "resourceUri": choice["endpoint"].rstrip("/"), "deploymentId": choice["deployment"],
        "modelName": choice["model"], "authIdentity": None,
    }}


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
    if not search_reconcile.definitions_match(model_definition(choice), model):
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


def guard_readback_transport(plan: dict[str, Any], transport: Transport) -> Transport:
    if "embedding" not in plan and "content_understanding" not in plan:
        return transport
    url = search_reconcile.resource_url(plan["source"])

    def guarded(method: str, target: str, token: str, **kwargs: Any):
        response = transport(method, target, token, **kwargs)
        if method == "GET" and target == url and response.status == 200:
            try:
                verify_source_readback(plan.get("embedding"), response.body)
                if "content_understanding" in plan:
                    try:
                        from . import blob_source, file_source
                    except ImportError:
                        import blob_source, file_source
                    owner = file_source if plan["source"]["desired"]["kind"] == "file" else blob_source
                    owner.verify_content_understanding_readback(plan["content_understanding"], response.body)
            except HelperFailure as failure:
                failure.request_id = response.request_id
                raise
        return response

    return guarded


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


def _read_json(path: Any) -> dict[str, Any]:
    if not _text(path):
        raise fail("input-schema-invalid", "Select an explicit JSON file.")
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise fail("input-unreadable", "Selected evidence must be readable UTF-8 JSON.") from exc
    if not isinstance(value, dict):
        raise fail("input-schema-invalid", "Selected JSON must contain an object.")
    _json_valid(value)
    return value


def _source_plan(path: str) -> dict[str, Any]:
    document = _read_json(path)
    reject_secrets(document)
    require_allowed_fields(document, {"schema_version", "plan", "approval"}, label="source artifact")
    plan, approval = document.get("plan"), document.get("approval")
    if (
        document.get("schema_version") != "1.0" or not isinstance(plan, dict)
        or not isinstance(approval, dict) or type(approval.get("confirmed")) is not bool
        or approval.get("fingerprint") != digest(plan)
    ):
        raise fail("source-artifact-invalid", "Retain the unchanged source execution_input; prior consent is not query consent.")
    require_allowed_fields(approval, {"confirmed", "fingerprint"}, label="source approval")
    source = plan.get("source")
    desired = source.get("desired") if isinstance(source, dict) else None
    if (
        not isinstance(desired, dict) or desired.get("kind") not in ("file", "azureBlob")
        or not isinstance(source.get("api_version"), str)
        or source["api_version"] not in search_reconcile.SUPPORTED_API_VERSIONS
        or source.get("action") not in ("create", "reuse") or not _text(plan.get("owner"))
    ):
        raise fail("source-artifact-invalid", "Source artifact needs a supported same-owner File/Blob definition and API.")
    parameters = desired.get("fileParameters" if desired["kind"] == "file" else "azureBlobParameters")
    if not isinstance(parameters, dict) or not isinstance(parameters.get("ingestionParameters"), dict):
        raise fail("source-artifact-invalid", "Source ingestion parameters must be an object.")
    try:
        from . import file_source, blob_source
    except ImportError:
        import file_source, blob_source
    if plan.get("operation") == "reconcile-and-ingest":
        file_source._validate_plan(plan)
    elif plan.get("operation") == "reconcile-and-monitor":
        blob_source._validate_plan(plan)
    else:
        raise fail("source-artifact-invalid", "Only File/Blob source execution artifacts are supported.")
    if "embedding" not in plan:
        if parameters["ingestionParameters"].get("embeddingModel") is None:
            raise fail("embedding-not-configured", "Source vectorization is not configured; CU extraction does not enable vectors.")
        raise fail("embedding-prerequisite-missing", "The source has vectors but lacks resolved embedding choice evidence; retain the original artifact and resolve a new plan, never rewrite historical consent.")
    validate_plan_choice(plan)
    if parameters["ingestionParameters"].get("ingestionPermissionOptions") not in (None, []):
        raise fail("permission-query-unsupported", "Permission-aware retrieval belongs to the KB workflow; direct-index verification is unsupported.")
    return plan


def _request(request: Any) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise fail("input-schema-invalid", "Verification input must be an object.")
    reject_secrets(request)
    require_allowed_fields(request, {
        "schema_version", "source_plan_file", "vector_field", "content_field", "citation_field",
        "expected_citation", "expected_text", "query", "mode", "k", "not_before",
        "reuse_input_file", "reuse_result_file",
    }, label="vector verification intent")
    try:
        json.dumps(request, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (UnicodeError, ValueError, TypeError) as exc:
        raise fail("input-schema-invalid", "Verification choices must be valid UTF-8 JSON.") from exc
    if (
        request.get("schema_version") != "1.0" or request.get("mode") not in ("vector", "hybrid")
        or type(request.get("k")) is not int or not 1 <= request["k"] <= 10
        or any(not _text(request.get(key)) for key in ("query", "expected_citation", "expected_text"))
        or any(not isinstance(request.get(key), str) or not IDENTIFIER.fullmatch(request[key])
               for key in ("vector_field", "content_field", "citation_field"))
        or len({request["vector_field"], request["content_field"], request["citation_field"]}) != 3
    ):
        raise fail("input-schema-invalid", "Resolve vector/hybrid, k 1–10, three distinct simple field names, query and expected citation/text.")
    plan = _source_plan(request.get("source_plan_file"))
    try:
        from . import blob_source
    except ImportError:
        import blob_source
    blob_source._receipt_paths(request)
    if plan["source"]["desired"]["kind"] == "azureBlob":
        blob_source._timestamp(request.get("not_before"))
    elif "not_before" not in request or request["not_before"] is not None:
        raise fail("input-schema-invalid", "File verification requires explicit not_before null; uploads are synchronous.")
    return plan


def _named(items: Any, name: str) -> dict[str, Any]:
    if (
        not _text(name, maximum=128) or not isinstance(items, list)
        or not all(isinstance(item, dict) and _text(item.get("name"), maximum=128) for item in items)
        or len({item["name"] for item in items}) != len(items)
    ):
        raise fail("vector-configuration-invalid", "Expected complete generated metadata arrays.")
    selected = [item for item in items if item.get("name") == name]
    if len(selected) != 1:
        raise fail("vector-configuration-invalid", "Generated field/profile/vectorizer identity is absent or ambiguous.")
    return selected[0]


def verify_index(index: dict[str, Any], choice: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    fields = index.get("fields")
    vector = _named(fields, request["vector_field"])
    if index.get("permissionFilterOption") not in (None, "disabled") or any(field.get("permissionFilter") for field in fields):
        raise fail("permission-query-unsupported", "Permission-enabled indexes require the owning permission-aware retrieval workflow.")
    low, high = MODELS[choice["model"]]
    dimensions = vector.get("dimensions")
    if (
        vector.get("type") != "Collection(Edm.Single)" or vector.get("searchable") is not True
        or type(dimensions) is not int or not low <= dimensions <= high
    ):
        raise fail("vector-configuration-invalid", "Generated vector field type/searchability/dimensions do not match the selected model.")
    configuration = index.get("vectorSearch")
    if not isinstance(configuration, dict):
        raise fail("vector-configuration-invalid", "Generated index has no vectorSearch configuration.")
    profile = _named(configuration.get("profiles"), vector.get("vectorSearchProfile"))
    algorithm = _named(configuration.get("algorithms"), profile.get("algorithm"))
    if algorithm.get("kind") not in {"hnsw", "exhaustiveKnn"}:
        raise fail("vector-configuration-invalid", "Unsupported generated vector algorithm.")
    vectorizer = _named(configuration.get("vectorizers"), profile.get("vectorizer"))
    verify_model_readback(choice, {key: value for key, value in vectorizer.items() if key != "name"})
    for key in ("content_field", "citation_field"):
        field = _named(fields, request[key])
        if field.get("type") != "Edm.String" or field.get("retrievable") is not True:
            raise fail("vector-configuration-invalid", "Content and citation fields must be retrievable strings.")
        if key == "content_field" and request["mode"] == "hybrid" and field.get("searchable") is not True:
            raise fail("vector-configuration-invalid", "Hybrid requires the selected content field to be searchable.")
    keys = [field for field in fields if field.get("key") is True]
    if len(keys) != 1 or keys[0].get("type") != "Edm.String" or keys[0].get("retrievable") is not True:
        raise fail("vector-configuration-invalid", "Require one retrievable string document key.")
    return {"dimensions": dimensions, "profile": profile["name"], "vectorizer": vectorizer["name"], "document_id_field": keys[0]["name"]}


def _reader(transport: Transport, token_provider: TokenProvider):
    request_ids: list[str] = []

    def read(method: str, url: str, token: str, **kwargs: Any):
        if method != "GET":
            raise fail("planning-write-forbidden", "Verification observation permits only GETs.")
        kwargs.update(
            follow_redirects=False,
            max_response_bytes=min(8 * 1024 * 1024, kwargs.get("max_response_bytes", 8 * 1024 * 1024)),
            response_deadline=min(
                time.monotonic() + min(60, kwargs.get("timeout", 60)),
                kwargs.get("response_deadline", float("inf")),
            ),
        )
        result = transport(method, url, token, **kwargs)
        _json_valid(result.body)
        if result.request_id:
            request_ids.append(result.request_id)
        return result

    def get(url: str):
        value, _ = search_reconcile.read_resource(url, token_provider(SEARCH_AUDIENCE), transport=read)
        if value is None:
            raise fail("vector-resource-missing", "An exact selected source/generated index is absent.")
        if not _text(value.get("@odata.etag")):
            raise fail("vector-evidence-missing", "Fresh source and index ETags are required.")
        return value

    return read, get, request_ids


def _prior_blob_ingestion(
    plan: dict[str, Any], request: dict[str, Any], current: dict[str, Any],
    generated: list[dict[str, Any]], readiness: dict[str, Any],
    receipts: tuple[dict[str, Any], dict[str, Any]] | None,
) -> dict[str, Any]:
    try:
        from . import blob_source
    except ImportError:
        import blob_source
    if receipts is None:
        raise fail("ingestion-unverified", "A zero-work cycle requires retained approved input and successful nonempty creation result files.")
    prior, result = receipts
    _json_valid({"plan": prior, "result": result})
    blob_source._verify_creation_binding(
        plan["source"], plan["boundary"], current, generated, receipts,
    )
    if (
        prior["owner"] != plan["owner"] or prior["inventory_digest"] != plan["inventory_digest"]
        or result["verification"].get("source_digest") != plan["inventory_digest"]
    ):
        raise fail("ingestion-unverified", "Prior ingestion must bind the same owner and unchanged before/after Storage inventory.")
    previous = result.get("readiness")
    if not isinstance(previous, dict) or previous.get("status") != "verified":
        raise fail("ingestion-unverified", "Retained creation must include verified ingestion readiness.")
    require_allowed_fields(previous, {
        "status", "synchronization", "not_before", "request_ids", "first_retry", "watch", "progress",
    }, label="retained ingestion readiness")
    cycle = previous.get("synchronization")
    fields = {"startTime", "endTime", "itemsUpdatesProcessed", "itemsUpdatesFailed", "itemsSkipped"}
    if not isinstance(cycle, dict) or set(cycle) != fields:
        raise fail("ingestion-unverified", "Retain the complete creation synchronization interval and counters.")
    if "progress" in previous:
        try:
            from ._progress import validate_blob_progress
        except ImportError:
            from _progress import validate_blob_progress
        display = previous["progress"]
        try:
            validate_blob_progress(display)
        except ValueError as exc:
            raise fail("verification-drift", "Retained Blob progress metadata is malformed.") from exc
        if (display["phase"] != "completed"
                or display["synchronization_status"] not in ("active", "not-reported")
                or display["next_check_seconds"] is not None
                or display["run_start"] != blob_source._timestamp(cycle["startTime"]).isoformat()
                or [display[key] for key in ("processed", "failed", "skipped")] !=
                [cycle[key] for key in ("itemsUpdatesProcessed", "itemsUpdatesFailed", "itemsSkipped")]):
            raise fail("verification-drift", "Retained Blob progress must describe its own completed cycle.")
    if "watch" in previous:
        watch = previous["watch"]
        expected_latest = {key: cycle[key] for key in fields - {"endTime"}}
        expected_latest["state"] = "completed-cycle-observed"
        latest = watch.get("latest") if isinstance(watch, dict) else None
        if isinstance(latest, dict) and "indexer_execution" in latest:
            execution = latest["indexer_execution"]
            if not blob_source._execution_completed_by(
                execution, blob_source._timestamp(cycle["endTime"]),
                max(blob_source._timestamp(request["not_before"]), blob_source._timestamp(previous.get("not_before"))),
            ):
                raise fail("verification-drift", "Retained active execution must be resolved before its primary cycle ends.")
            expected_latest["indexer_execution"] = execution
        if (not isinstance(watch, dict)
                or set(watch) != {"schema_version", "state", "elapsed_seconds", "status_checks", "latest"}
                or watch["schema_version"] != "1.0" or watch["state"] != "completed"
                or type(watch["elapsed_seconds"]) not in (int, float)
                or not math.isfinite(watch["elapsed_seconds"]) or watch["elapsed_seconds"] < 0
                or type(watch["status_checks"]) is not int or not 1 <= watch["status_checks"] <= 1000
                or watch["latest"] != expected_latest):
            raise fail("verification-drift", "Retained watch metadata must match its completed cycle; it cannot replace ingestion proof.")
    counts = [cycle[key] for key in ("itemsUpdatesProcessed", "itemsUpdatesFailed", "itemsSkipped")]
    if any(type(count) is not int or count < 0 for count in counts) or counts[0] == 0 or any(counts[1:]):
        raise fail("ingestion-unverified", "Prior creation must have processed content without failures or skipped items.")
    start, end = (blob_source._timestamp(cycle[key]) for key in ("startTime", "endTime"))
    if (
        start < max(blob_source._timestamp(request["not_before"]), blob_source._timestamp(previous.get("not_before")))
        or end < start or end > blob_source._timestamp(readiness["synchronization"]["startTime"])
    ):
        raise fail("ingestion-unverified", "Prior ingestion must follow both lower bounds and complete before the current zero-work cycle.")
    return {
        "synchronization": copy.deepcopy(cycle),
        "evidence_digest": digest({"creation_plan": prior, "creation_result": result}),
    }


def observe(request: dict[str, Any], *, token_provider: TokenProvider, transport: Transport,
            storage_transport: Transport) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = _request(request)
    source = plan["source"]
    try:
        from . import file_ingest, blob_inventory, blob_source
    except ImportError:
        import file_ingest, blob_inventory, blob_source
    read, get, ids = _reader(guard_readback_transport(plan, transport), token_provider)
    url = search_reconcile.resource_url(source)
    current = get(url)
    if not search_reconcile.definitions_match(source["desired"], current):
        raise fail("definition-conflict", "Fresh source differs from the selected source artifact.")
    if source.get("expected_etag") and current["@odata.etag"] != source["expected_etag"]:
        raise fail("definition-drift", "Selected reuse source ETag changed; rerun the source planner.")
    kind = source["desired"]["kind"]
    if kind == "file":
        created = current.get("fileParameters", {}).get("createdResources")
        if not isinstance(created, dict) or set(created) != {"index"}:
            raise fail("vector-evidence-missing", "Require the File source's generated index identity.")
        files, _ = file_ingest.read_inventory(plan["ingestion"], token_provider(SEARCH_AUDIENCE), transport=read)
        matches = file_ingest.reconcile_inventory(plan["ingestion"], files)
        identities = [item.get("fileId") for item in matches.values()]
        if not identities or not all(_text(item) for item in identities) or len(set(identities)) != len(identities):
            raise fail("ingestion-unverified", "Require complete unique ingested File identities and markers.")
        inventory = file_ingest.inventory_digest(files)
        readiness = {"status": "verified", "files": len(matches), "basis": "synchronous File ingestion markers; no reported file errors"}
    else:
        created = {item["type"]: item["name"] for item in blob_source.generated_resources(current, strict=True)}
        generated = blob_source.generated_resources(current, strict=True)
        if "expected_generated" in plan and generated != plan["expected_generated"]:
            raise fail("definition-drift", "Generated Blob identities changed.")
        receipts: tuple[dict[str, Any], dict[str, Any]] | None = None

        def load_receipts() -> tuple[dict[str, Any], dict[str, Any]] | None:
            nonlocal receipts
            if receipts is None:
                receipts = blob_source._reuse_receipts(blob_source._receipt_paths(request))
            return receipts

        blob_source._verify_storage_binding(
            source, plan["boundary"], current, generated, load_receipts,
        )
        snapshot = blob_inventory.discover(plan["boundary"], plan["inventory_limits"],
                                           token_provider=token_provider, transport=storage_transport)
        ids.extend(snapshot["request_ids"])
        inventory = snapshot["inventory_digest"]
        if inventory != plan["inventory_digest"]:
            raise fail("inventory-drift", "Storage content or ACL evidence changed; rerun source planning.")
        readiness = blob_source.monitor(
            source, not_before=blob_source._timestamp(request["not_before"]),
            limits={"max_requests": 1, "interval_seconds": 1, "deadline_seconds": 60},
            token_provider=token_provider, transport=read, sleep=lambda _: None,
        )
        if readiness.get("status") != "verified":
            raise fail("ingestion-unverified", "No relevant completed zero-failure Blob synchronization; do not query.")
        cycle = readiness["synchronization"]
        if cycle["itemsSkipped"]:
            raise fail("ingestion-unverified", "A completed cycle with no skipped items is required.")
        if cycle["itemsUpdatesProcessed"] == 0:
            readiness["prior_ingestion"] = _prior_blob_ingestion(
                plan, request, current, generated, readiness, load_receipts(),
            )
            readiness["basis"] = "Current zero-work success plus same-source, same-inventory nonempty creation proof."
    index_name = created.get("index")
    index_url = f"{source['endpoint'].rstrip('/')}/indexes('{odata_name(index_name)}')?api-version={source['api_version']}"
    index = get(index_url)
    if index.get("name") != index_name:
        raise fail("vector-configuration-mismatch", "Generated index name does not match its source identity.")
    metadata = verify_index(index, plan["embedding"], request)
    refreshed, refreshed_index = get(url), get(index_url)
    source_changed = digest(current) != digest(refreshed)
    if "content_understanding" in plan:
        source_changed = (
            current["@odata.etag"] != refreshed["@odata.etag"]
            or not search_reconcile.definitions_match(current, refreshed)
            or (
                refreshed.get("fileParameters", {}).get("createdResources") != created
                if kind == "file" else blob_source.generated_resources(refreshed, strict=True) != generated
            )
        )
    if source_changed or digest(index) != digest(refreshed_index):
        raise fail("definition-drift", "Source or index changed during observation.")
    snapshot = {
        "source_plan_digest": digest(plan), "source_etag": current["@odata.etag"],
        "source_definition": digest(search_reconcile._definition(current)),
        "index": index_name, "index_etag": index["@odata.etag"], "index_digest": digest(index),
        "inventory_digest": inventory, "vector": metadata,
    }
    if "prior_ingestion" in readiness:
        snapshot["ingestion_evidence_digest"] = readiness["prior_ingestion"]["evidence_digest"]
    return snapshot, {"readiness": readiness, "request_ids": ids}


def plan_verification(request: dict[str, Any], *, token_provider: TokenProvider = azure_cli_token,
                      transport: Transport = http_request, storage_transport: Transport = http_request) -> dict[str, Any]:
    source_plan = _request(request)
    snapshot, evidence = observe(request, token_provider=token_provider, transport=transport, storage_transport=storage_transport)
    if digest(source_plan) != snapshot["source_plan_digest"]:
        raise fail("source-artifact-drift", "Source artifact changed while planning verification.")
    plan = {"operation": "verify-source-vector", "owner": source_plan["owner"], "cleanup_approved": False,
            "request": copy.deepcopy(request), "snapshot": snapshot}
    fingerprint = digest(plan)
    return {
        "status": "planned", "plan_fingerprint": fingerprint,
        "execution_input": {"schema_version": "1.0", "plan": plan, "approval": {"confirmed": False, "fingerprint": fingerprint}},
        "approval_summary": {
            "source": source_plan["source"]["name"], "index": snapshot["index"],
            "search_endpoint": source_plan["source"]["endpoint"], "api_version": source_plan["source"]["api_version"],
            "mode": request["mode"], "queries": 2 if request["mode"] == "hybrid" else 1,
            "k": request["k"], "query": request["query"],
            "embedding": summary(source_plan["embedding"]), "dimensions_observed": snapshot["vector"]["dimensions"],
            "configuration": "verified", "ingestion": "verified", "retrieval": "unverified",
            "next_step": "Approve the exact query/content transfer and embedding cost, then apply this unchanged artifact. No index repair or cleanup.",
        },
        "evidence": evidence, "writes_performed": [],
    }


def query_body(request: dict[str, Any], metadata: dict[str, Any], *, hybrid: bool) -> dict[str, Any]:
    body = {
        "vectorQueries": [{"kind": "text", "text": request["query"], "fields": request["vector_field"], "k": request["k"]}],
        "select": ",".join(dict.fromkeys((metadata["document_id_field"], request["content_field"], request["citation_field"]))),
        "top": request["k"], "minimumCoverage": 100,
    }
    if hybrid:
        body.update(search=request["query"], searchFields=request["content_field"], queryType="simple")
    return body


def verify_response(body: Any, request: dict[str, Any], metadata: dict[str, Any]) -> int:
    _json_valid(body)
    if (
        not isinstance(body, dict) or type(body.get("@search.coverage")) not in (int, float)
        or body["@search.coverage"] != 100
        or any(body.get(key) is not None for key in
               ("@odata.nextLink", "@search.nextPageParameters", "@search.semanticPartialResponseReason", "error"))
        or not isinstance(body.get("value"), list) or not 1 <= len(body["value"]) <= request["k"]
    ):
        raise fail("vector-query-incomplete", "Require a nonempty, complete, full-coverage query response without continuation or partial errors.")
    identities, matched = set(), 0
    for hit in body["value"]:
        if not isinstance(hit, dict):
            raise fail("vector-query-invalid", "Malformed query hit.")
        key, text, citation = (hit.get(field) for field in (metadata["document_id_field"], request["content_field"], request["citation_field"]))
        score = hit.get("@search.score")
        if (
            not all(_text(value, maximum=1024 * 1024) for value in (key, text, citation))
            or key in identities or type(score) not in (int, float) or not math.isfinite(score) or score < 0
        ):
            raise fail("vector-query-invalid", "Require unique document IDs, content, provenance and finite scores.")
        identities.add(key)
        matched += citation == request["expected_citation"] and request["expected_text"].casefold() in text.casefold()
    if not matched:
        raise fail("vector-query-mismatch", "No retrieved document matches both the expected source citation and expected content.")
    return matched


def _validate_snapshot(value: Any) -> None:
    fields = {"source_plan_digest", "source_etag", "source_definition", "index",
              "index_etag", "index_digest", "inventory_digest", "vector"}
    if not isinstance(value, dict) or set(value) not in (fields, fields | {"ingestion_evidence_digest"}):
        raise fail("input-schema-invalid", "Retain the complete generated verification snapshot.")
    hashes = {"source_plan_digest", "source_definition", "index_digest", "inventory_digest"}
    for key in hashes | ({"ingestion_evidence_digest"} & value.keys()):
        if not isinstance(value[key], str) or not search_reconcile.SHA256.fullmatch(value[key]):
            raise fail("input-schema-invalid", "Invalid generated snapshot integrity value; rerun planning.")
    if not all(_text(value[key]) for key in ("source_etag", "index_etag", "index")):
        raise fail("input-schema-invalid", "Snapshot identities and ETags are required.")
    odata_name(value["index"])
    vector = value["vector"]
    if (
        not isinstance(vector, dict)
        or set(vector) != {"dimensions", "profile", "vectorizer", "document_id_field"}
        or type(vector.get("dimensions")) is not int or not 1 <= vector["dimensions"] <= 3072
        or not all(_text(vector[key], maximum=128) for key in ("profile", "vectorizer", "document_id_field"))
    ):
        raise fail("input-schema-invalid", "Invalid generated vector snapshot; rerun planning.")


def execute(document: dict[str, Any], *, token_provider: TokenProvider = azure_cli_token,
            transport: Transport = http_request, storage_transport: Transport = http_request) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise fail("input-schema-invalid", "Query execution needs an approved artifact.")
    _json_valid(document)
    require_allowed_fields(document, {"schema_version", "plan", "approval"}, label="query artifact")
    plan = document.get("plan")
    if not isinstance(plan, dict):
        raise fail("input-schema-invalid", "Query execution needs a planned artifact.")
    reject_secrets(document)
    require_allowed_fields(plan, {"operation", "owner", "cleanup_approved", "request", "snapshot"}, label="vector query plan")
    fingerprint = digest(plan)
    approval = document.get("approval")
    if (
        document.get("schema_version") != "1.0" or not isinstance(approval, dict)
        or approval.get("confirmed") is not True
        or approval != {"confirmed": True, "fingerprint": fingerprint}
    ):
        raise fail("approval-required", "Explicit approval of this unchanged billable query plan is required.")
    if plan.get("operation") != "verify-source-vector" or plan.get("cleanup_approved") is not False:
        raise fail("input-schema-invalid", "Only separately approved vector verification is supported.")
    _validate_snapshot(plan.get("snapshot"))
    request = plan.get("request")
    source_plan = _request(request)
    if plan.get("owner") != source_plan["owner"]:
        raise fail("source-artifact-invalid", "Query owner must match the source artifact.")
    snapshot, evidence = observe(request, token_provider=token_provider, transport=transport, storage_transport=storage_transport)
    if snapshot != plan.get("snapshot") or digest(source_plan) != snapshot["source_plan_digest"]:
        raise fail("verification-drift", "Evidence changed; rerun --plan, replace the artifact and discard consent.")
    source = source_plan["source"]
    url = f"{source['endpoint'].rstrip('/')}/indexes('{odata_name(snapshot['index'])}')/docs/search.post.search?api-version={source['api_version']}"
    queries = []
    attempted = 0
    try:
        for hybrid in ([False, True] if request["mode"] == "hybrid" else [False]):
            token = token_provider(SEARCH_AUDIENCE)
            attempted += 1
            response = transport(
                "POST", url, token,
                headers={"Content-Type": "application/json"},
                body=json.dumps(query_body(request, snapshot["vector"], hybrid=hybrid)).encode("utf-8"),
                follow_redirects=False, max_response_bytes=8 * 1024 * 1024,
                timeout=60, response_deadline=time.monotonic() + 60,
            )
            if response.status != 200 or not _text(response.request_id):
                raise fail("vector-query-incomplete", "Require HTTP 200 and observed Search request provenance.")
            count = verify_response(response.body, request, snapshot["vector"])
            queries.append({"mode": "hybrid" if hybrid else "vector", "request_id": response.request_id,
                            "matched_documents": count, "response_digest": digest(response.body)})
        after, _ = observe(request, token_provider=token_provider, transport=transport, storage_transport=storage_transport)
        if after != snapshot:
            raise fail("verification-drift", "Source, index or inventory changed across query execution.")
    except HelperFailure as failure:
        result = blocked_result(
            HelperFailure(failure.code, failure.message, blocked_at=failure.blocked_at,
                          status=failure.http_status, request_id=failure.request_id),
            outcome="source-vector-verification", fingerprint=fingerprint, owner=plan["owner"],
        )
        result.update(queries_attempted=attempted, billing_possible=attempted > 0, queries=queries, writes_performed=[])
        return result
    return {
        "status": "retrieval-verified", "outcome": "source-vector-verification",
        "approved_plan": {"confirmed": True, "fingerprint": fingerprint},
        "verification": {"configuration": "verified", "ingestion": "verified",
                         "retrieval": request["mode"], "queries": queries, "evidence": evidence},
        "writes_performed": [], "cleanup": "not-applicable",
        "warnings": ["Observed index retrieval only: not KB synthesis, agent tool use, or a corpus-wide relevance guarantee. Reobserve before later use."],
    }


def main(argv: list[str] | None = None) -> int:
    try:
        from .private_artifacts import add_execution_output_argument, emit_plan_result, validate_execution_output_mode
    except ImportError:
        from private_artifacts import add_execution_output_argument, emit_plan_result, validate_execution_output_mode
    parser = argparse.ArgumentParser(description="Plan or apply separately approved File/Blob vector verification.")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--plan", type=Path)
    modes.add_argument("--input", type=Path)
    add_execution_output_argument(parser)
    args = parser.parse_args(argv)
    try:
        validate_execution_output_mode(args)
        if args.plan:
            result = plan_verification(_read_json(str(args.plan)))
            emit_plan_result(result, args.execution_output)
            return 0 if result["status"] == "planned" else 2
        else:
            document, _, _ = load_approved_input(args.input)
            result = execute(document)
    except HelperFailure as failure:
        result = blocked_result(failure, outcome="source-vector-verification", fingerprint=None)
    emit_result(result)
    return 0 if result["status"] in {"planned", "retrieval-verified"} else 2


if __name__ == "__main__":
    sys.exit(main())
