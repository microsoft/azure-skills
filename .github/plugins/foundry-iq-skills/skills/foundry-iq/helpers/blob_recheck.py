"""Retained Blob creation/reuse observations and read-only readiness follow-up."""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import stat
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

try:
    from . import _bootstrap_io as private_io
    from ._progress import Progress, add_progress_argument, reporting
    from . import blob_inventory, blob_source, search_reconcile, source_vector, _indexer_observation as indexer
    from . import _blob_observation as semantic
    from ._common import (
        HelperFailure, SEARCH_AUDIENCE, azure_cli_token, blocked_result, digest,
        emit_result, http_request, reject_secrets,
    )
except ImportError:
    import _bootstrap_io as private_io
    from _progress import Progress, add_progress_argument, reporting
    import blob_inventory, blob_source, search_reconcile, source_vector
    import _indexer_observation as indexer
    import _blob_observation as semantic
    from _common import (
        HelperFailure, SEARCH_AUDIENCE, azure_cli_token, blocked_result, digest,
        emit_result, http_request, reject_secrets,
    )


fail = blob_source._failure
COLLECTIONS = {"datasource": "datasources", "indexer": "indexers",
               "skillset": "skillsets", "index": "indexes"}


def _json(raw):
    def unique(pairs):
        value = {}
        for key, child in pairs:
            if key in value:
                raise ValueError("Duplicate field")
            value[key] = child
        return value
    try:
        value = json.loads(raw, object_pairs_hook=unique)
        json.dumps(value, allow_nan=False, ensure_ascii=False).encode("utf-8")
        if not isinstance(value, dict):
            raise ValueError("Expected object")
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise fail("recheck-evidence-invalid", "Retain bounded, unmodified UTF-8 object evidence.") from exc


def read_private(path):
    path = Path(path)
    private_io.private_directory(str(path.parent))
    try:
        selected = path.lstat()
        if (not stat.S_ISREG(selected.st_mode) or selected.st_nlink != 1
                or getattr(selected, "st_file_attributes", 0) & 0x400):
            raise OSError("Not an ordinary private file")
        if os.name == "nt":
            private_io._windows_private(path)
        elif selected.st_uid != os.getuid() or stat.S_IMODE(selected.st_mode) & 0o077:
            raise OSError("Not private")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as handle:
            opened = os.fstat(handle.fileno())
            if (selected.st_dev, selected.st_ino) != (opened.st_dev, opened.st_ino):
                raise OSError("Evidence changed identity")
            raw = handle.read(private_io.MAX_BYTES + 1)
        if len(raw) > private_io.MAX_BYTES:
            raise OSError("Evidence exceeds bound")
        return _json(raw.decode("utf-8"))
    except (OSError, UnicodeError) as exc:
        raise fail("recheck-evidence-unreadable", "Select existing private, unlinked evidence files; no permissions were changed.") from exc


def account_context():
    code, stdout, _ = private_io.run_cli(["account", "show"], 30)
    if code:
        raise fail("recheck-auth-context-unavailable", "Current signed-in CLI context is inaccessible; details withheld.")
    account = _json(stdout)
    user = account.get("user")
    if (account.get("environmentName") != "AzureCloud" or account.get("state") != "Enabled"
            or not isinstance(user, dict) or user.get("type") not in ("user", "servicePrincipal")
            or any(not isinstance(value, str) or not value.strip() for value in
                   (account.get("id"), account.get("tenantId"), user.get("name")))):
        raise fail("recheck-auth-context-unavailable", "An enabled public-cloud tenant/subscription/principal context is required.")
    return digest({key: account[key] for key in ("id", "tenantId", "environmentName")}
                  | {"principal": {"name": user["name"], "type": user["type"]}})


def _supported(plan):
    try:
        source, _ = blob_source._validate_plan(plan)
        ingestion = source["desired"]["azureBlobParameters"]["ingestionParameters"]
    except (KeyError, TypeError, AttributeError, RecursionError) as exc:
        raise fail("recheck-evidence-invalid", "Original Blob creation plan is malformed.") from exc
    if (ingestion.get("contentExtractionMode") not in ("minimal", "standard") or ingestion.get("identity") is not None
            or source["api_version"] not in {"2026-04-01", "2026-08-01-preview"}
            or plan["boundary"]["is_adls"] and source["api_version"] != "2026-08-01-preview"):
        raise fail("recheck-scope-unsupported", "Checkpointing requires supported Blob extraction and provable system-assigned authentication.")
    schedule = ingestion.get("ingestionSchedule")
    indexer.schedule(schedule)


def _etag(value):
    etag = value.get("@odata.etag") if isinstance(value, dict) else None
    if not isinstance(etag, str) or not etag.strip():
        raise fail("recheck-evidence-missing", "Every source/generated readback requires a nonempty string ETag.")
    return etag


def _processing_readback(plan, current):
    desired = plan["source"]["desired"]["azureBlobParameters"]["ingestionParameters"]
    if desired.get("contentExtractionMode") == "standard":
        ai = desired.get("aiServices")
        if not isinstance(ai, dict) or not isinstance(ai.get("uri"), str) or not ai["uri"].strip():
            raise fail("recheck-processing-unverified", "Standard extraction needs its original CU endpoint evidence.")
        blob_source.verify_content_understanding_readback({"endpoint": ai["uri"]}, current)
    source_vector.verify_source_readback(plan.get("embedding"), current)
    model = desired.get("embeddingModel")
    if model is not None and "embedding" not in plan:
        parameters = model.get("azureOpenAIParameters") if isinstance(model, dict) else None
        if (not isinstance(parameters, dict) or model.get("kind") != "azureOpenAI"
                or any(not isinstance(parameters.get(key), str) or not parameters[key].strip()
                       for key in ("resourceUri", "deploymentId", "modelName"))):
            raise fail("recheck-processing-unverified", "Legacy embedding configuration cannot be verified by this client.")
        source_vector.verify_source_readback({
            "endpoint": parameters["resourceUri"], "deployment": parameters["deploymentId"],
            "model": parameters["modelName"],
        }, current)


def _binding(plan, record, current, generated, binding_receipts=None):
    source = plan["source"]
    observed = {"type": "knowledge-source", "name": source["name"], "etag": _etag(current),
                "definition_digest": digest(search_reconcile._definition(current))}
    if source["action"] == "create":
        blob_source._verify_creation_binding(source, plan["boundary"], current, generated, (plan, record))
    elif (record["verification"]["readback"] != observed
          or not search_reconcile.definitions_match(source["desired"], current)
          or source.get("expected_etag", observed["etag"]) != observed["etag"]):
        raise fail("source-binding-unverified", "Reused source does not match its retained read-only identity/configuration.")
    if (blob_source.generated_resources(current, strict=True) != generated
            or plan.get("expected_generated", generated) != generated):
        raise fail("definition-drift", "Generated source identities changed.")
    if binding_receipts is not None and (
        binding_receipts[0]["owner"] != plan["owner"]
        or binding_receipts[0]["inventory_digest"] != plan["inventory_digest"]
    ):
        raise fail("source-binding-unverified", "Retained creation must bind the same owner and Storage inventory.")
    blob_source._verify_storage_binding(
        source, plan["boundary"], current, generated,
        lambda: (plan, record) if source["action"] == "create" else binding_receipts,
    )
    _processing_readback(plan, current)


def _sanitized_datasource_url(url):
    parsed = urlsplit(url)
    search_reconcile.validate_search_endpoint(f"{parsed.scheme}://{parsed.netloc}")
    if (parsed.fragment or parsed.query not in {
            f"api-version={version}" for version in search_reconcile.SUPPORTED_API_VERSIONS}
            or re.fullmatch(r"/datasources\('[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}'\)", parsed.path) is None):
        raise fail("recheck-read-url-invalid", "Sanitized binding requires one exact datasource identity and the bound supported API version.")
    return url + "&includeConnectionString=true"


def _reader(transport, token_provider, *, warnings=None):
    recovery = None
    recovery_warnings = warnings if warnings is not None else []

    def tracked(method, url, token, **kwargs):
        try:
            parsed = urlsplit(url)
            search_reconcile.validate_search_endpoint(f"{parsed.scheme}://{parsed.netloc}")
            if parsed.fragment:
                raise fail("recheck-read-url-invalid", "Read-only Search URLs cannot contain fragments.")
            if parsed.query not in {
                    f"api-version={version}" for version in search_reconcile.SUPPORTED_API_VERSIONS}:
                suffix = "&includeConnectionString=true"
                if not url.endswith(suffix) or _sanitized_datasource_url(url[:-len(suffix)]) != url:
                    raise fail("recheck-read-url-invalid", "Only the exact sanitized datasource GET option is permitted.")
            kwargs["timeout"] = min(60, kwargs.get("timeout", 60))
            if recovery is None:
                response = transport(method, url, token, **kwargs)
            else:
                response = recovery.get(
                    url, token, transport=transport,
                    max_requests=1 if url.endswith("&includeConnectionString=true") else 2,
                    **kwargs,
                )
                ids.extend(recovery.request_ids[:-1])
            if method == "GET" and response.status == 200 and isinstance(response.body, dict):
                etag = search_reconcile.resolve_etag(search_reconcile.response_etags(response), response.request_id)
                if etag is not None:
                    response = search_reconcile.HttpResult(
                        response.status, {**response.body, "@odata.etag": etag}, response.headers, response.etag_values,
                    )
            return response
        except HelperFailure as failure:
            if recovery is not None:
                ids.extend(recovery.request_ids)
            elif failure.request_id:
                ids.append(failure.request_id)
            raise
    read, original_get, ids = source_vector._reader(tracked, token_provider)

    def get(url):
        nonlocal recovery
        recovery = search_reconcile.ReadRecovery()
        try:
            result = original_get(url)
            get.request_id = ids[-1] if ids else None
            return result
        except HelperFailure as failure:
            if failure.code in {"vector-resource-missing", "vector-evidence-missing", "etag-invalid"}:
                missing = failure.code == "vector-resource-missing"
                raise HelperFailure(
                    "recheck-resource-missing" if missing else "recheck-evidence-missing",
                    "An exact original source/generated definition or ETag is unavailable.",
                    blocked_at="verification", status=404 if missing else failure.http_status,
                    request_id=ids[-1] if ids else failure.request_id,
                ) from failure
            raise
        finally:
            recovery_warnings.extend(recovery.warnings)
            recovery = None
    get.recovery_warnings = recovery_warnings
    return read, get, ids


def _configuration(plan, creation, generated, get, *, binding_receipts=None, expected=None,
                   diagnostics=None, observations=None, binding_observations=None):
    diagnostics = diagnostics if diagnostics is not None else []
    source = plan["source"]
    current = get(search_reconcile.resource_url(source))
    _binding(plan, creation, current, generated, binding_receipts)
    names = {item["type"]: item["name"] for item in generated}
    snapshots = {}
    failures = []
    for kind, collection in COLLECTIONS.items():
        name = names[kind]
        url = f"{source['endpoint'].rstrip('/')}/{collection}('{name}')?api-version={source['api_version']}"
        try:
            snapshots[kind] = _child_configuration(
                plan, kind, name, names, get, url, expected, diagnostics, observations, binding_observations,
            )
        except HelperFailure as failure:
            if failure.request_id is None:
                failure.request_id = getattr(get, "request_id", None)
            semantic.note(diagnostics, kind, "error", failure.code, "definition", failure.request_id)
            failures.append(failure)
        else:
            semantic.note(diagnostics, kind, "info", "generated-configuration-verified", "definition",
                          getattr(get, "request_id", None))
    refreshed = get(search_reconcile.resource_url(source))
    _binding(plan, creation, refreshed, generated, binding_receipts)
    if failures:
        raise failures[0]
    return snapshots


def _child_configuration(plan, kind, name, names, get, url, expected, diagnostics, observations,
                         binding_observations=None):
        source = plan["source"]
        child = get(url)
        etag = _etag(child)
        if child.get("name") != name:
            raise fail("definition-drift", "Generated configuration returned an unrelated identity.")
        if kind == "datasource":
            boundary = plan["boundary"]
            container, credentials = child.get("container"), child.get("credentials")
            invariants = {
                "type": child.get("type") == ("adlsgen2" if boundary["is_adls"] else "azureblob"),
                "container.name": isinstance(container, dict) and container.get("name") == boundary["container"],
                "container.query": isinstance(container, dict) and container.get("query") in
                    (boundary["prefix"], None if not boundary["prefix"] else boundary["prefix"]),
                "credentials": credentials is None or
                    isinstance(credentials, dict) and not set(credentials) - {"connectionString"},
                "identity": child.get("identity") is None,
            }
            for field, valid in invariants.items():
                if not valid:
                    semantic.note(diagnostics, kind, "error", "source-binding-unverified", field,
                                  getattr(get, "request_id", None))
            if not all(invariants.values()):
                raise fail("source-binding-unverified", "Generated datasource type/container/prefix/identity or credential shape conflicts with the bound source.",
                           request_id=getattr(get, "request_id", None))
            try:
                binding = blob_source._connection_binding(
                    credentials.get("connectionString") if isinstance(credentials, dict) else None, boundary,
                )
            except HelperFailure as failure:
                failure.request_id = getattr(get, "request_id", None)
                semantic.note(diagnostics, kind, "error", failure.code, "credentials.connectionString", failure.request_id)
                raise
        if kind == "indexer":
            request_id = getattr(get, "request_id", None)
            for field, target in (("dataSourceName", "datasource"), ("targetIndexName", "index"), ("skillsetName", "skillset")):
                if child.get(field) != names[target]:
                    raise indexer.failure(diagnostics, "indexer-binding-mismatch", field,
                                          f"Generated indexer {field} does not match the bound resource; details withheld.", request_id)
            observed = indexer.observe(child, source["desired"]["azureBlobParameters"]["ingestionParameters"].get("ingestionSchedule"),
                                       diagnostics, request_id)
            if observations is not None:
                observations.append({"request_id": request_id, "etag_digest": digest(etag),
                                     **{key: value for key, value in observed.items() if key != "etag"}})
            snapshot = observed if expected is None or indexer.PROJECTION_FIELDS <= set(expected[kind]) else {
                "etag": etag, "digest": digest(child),
            }
            if expected is None or semantic.PROJECTION_FIELDS <= set(expected[kind]):
                snapshot.update(semantic.observe(child, kind))
            if expected is not None:
                if semantic.PROJECTION_FIELDS <= set(expected[kind]):
                    semantic.compare(snapshot, expected[kind], kind, diagnostics, request_id)
                    # A core-equal ETag-only revision is not schedule or configuration drift.
                    if snapshot["schedule_raw_digest"] != expected[kind]["schedule_raw_digest"]:
                        indexer.compare(snapshot, expected[kind], diagnostics, request_id)
                else:
                    indexer.compare(snapshot, expected[kind], diagnostics, request_id)
            return snapshot
        # Keep only integrity observations, never generated credentials or skill text.
        snapshot = {"etag": etag, "digest": digest(child)}
        if expected is None or semantic.PROJECTION_FIELDS <= set(expected[kind]):
            snapshot.update(semantic.observe(child, kind))
            if kind == "datasource":
                snapshot["binding_proof"] = "resource-id" if binding == "visible" else "unverified"
            if expected is not None:
                semantic.compare(snapshot, expected[kind], kind, diagnostics, getattr(get, "request_id", None))
                if kind == "datasource" and binding == "concealed":
                    _current_datasource_binding(get, url, snapshot, plan["boundary"], diagnostics,
                                                binding_observations)
            elif kind == "datasource" and binding == "concealed":
                semantic.note(diagnostics, kind, "info", "datasource-credential-projection-concealed",
                              "credentials.connectionString", getattr(get, "request_id", None))
            return snapshot
        visible_preimage = False
        if kind == "datasource" and expected and expected[kind]["etag"] == etag:
            # Only concealed/verified credentials may vary; every other byte and the ETag stay bound.
            for credentials in (
                None, {}, {"connectionString": None}, {"connectionString": ""},
                {"connectionString": "<redacted>"}, {"connectionString": "<REDACTED>"},
                {"connectionString": f"ResourceId={plan['boundary']['storage_id']}"},
                {"connectionString": f"ResourceId={plan['boundary']['storage_id']};"},
            ):
                candidate = {**child, "credentials": credentials}
                if digest(candidate) == expected[kind]["digest"]:
                    snapshot["digest"] = expected[kind]["digest"]
                    if isinstance(credentials, dict) and isinstance(credentials.get("connectionString"), str):
                        visible_preimage = credentials["connectionString"].startswith("ResourceId=")
            candidate = {key: value for key, value in child.items() if key != "credentials"}
            if digest(candidate) == expected[kind]["digest"]:
                snapshot["digest"] = expected[kind]["digest"]
        if snapshot != expected[kind]:
            raise fail("generated-legacy-evidence-insufficient",
                       "Legacy generated full-hash evidence differs; no core projection was retained.",
                       request_id=getattr(get, "request_id", None))
        if kind == "datasource" and binding == "concealed":
            if visible_preimage:
                semantic.note(diagnostics, kind, "warning", "datasource-credential-projection-changed",
                              "credentials", getattr(get, "request_id", None))
            else:
                _current_datasource_binding(get, url, {"etag": etag, "digest": digest(child), **semantic.observe(child, kind)},
                                            plan["boundary"], diagnostics, binding_observations)
        return snapshot


def _current_datasource_binding(get, url, snapshot, boundary, diagnostics, observations=None):
    observation = {
        "schema_version": "1.0", "status": "unverified", "request_id": None,
        "plain": {"etag_digest": digest(snapshot["etag"]), "definition_digest": snapshot["digest"],
                  "core_digest": snapshot["core_digest"]},
        "sanitized": None,
    }
    if observations is not None:
        observations.append(observation)
    # The service sanitizes internally; this option never requests raw keys or SAS.
    try:
        current = get(_sanitized_datasource_url(url))
    except HelperFailure as failure:
        observation["request_id"] = failure.request_id
        raise
    credentials = current.get("credentials")
    request_id = getattr(get, "request_id", None)
    observation["request_id"] = request_id
    projection = semantic.observe(current, "datasource")
    observation["sanitized"] = {
        "etag_digest": digest(_etag(current)), "definition_digest": digest(current),
        "core_digest": projection["core_digest"],
    }
    if (_etag(current) != snapshot["etag"]
            or observation["sanitized"]["core_digest"] != snapshot["core_digest"]):
        fields = projection["field_digests"].keys() | snapshot["field_digests"].keys()
        changed = [field for field in sorted(fields)
                   if projection["field_digests"].get(field) != snapshot["field_digests"].get(field)]
        if _etag(current) != snapshot["etag"]:
            changed.append("@odata.etag")
        for field in changed:
            semantic.note(diagnostics, "datasource", "error", "datasource-binding-unverified", field, request_id)
        raise fail("datasource-binding-unverified",
                   "Independent datasource binding readback changed revision or configuration; no stable current proof is available.",
                   request_id=request_id)
    try:
        visible = (isinstance(credentials, dict) and set(credentials) == {"connectionString"}
                   and blob_source._connection_binding(credentials["connectionString"], boundary) == "visible")
    except HelperFailure:
        visible = False
    if not visible:
        semantic.note(diagnostics, "datasource", "error", "datasource-binding-unverified",
                      "credentials.connectionString", request_id)
        raise fail("datasource-binding-unverified",
                   "Sanitized current datasource readback does not prove the exact selected keyless ResourceId; values withheld. Retain resources and investigate this evidence gap read-only.",
                   request_id=request_id)
    observation["status"] = "verified"
    semantic.note(diagnostics, "datasource", "info", "datasource-current-binding-verified",
                  "credentials.connectionString", request_id)


def _baseline_cycle(source, read, token_provider):
    url = search_reconcile.resource_url(source).replace(")?", ")/status?")
    response = read("GET", url, token_provider(SEARCH_AUDIENCE))
    body = response.body
    if response.status != 200 or not isinstance(body, dict) or body.get("kind") != "azureBlob":
        raise HelperFailure("ingestion-inaccessible", "Initial reuse status is unavailable.",
                            blocked_at="verification", status=response.status, request_id=response.request_id)
    last = body.get("lastSynchronizationState")
    if last is None:
        return None
    if not isinstance(last, dict):
        raise fail("ingestion-status-invalid", "Initial reuse synchronization must be an object.")
    if last.get("endTime") is None:
        blob_source._timestamp(last.get("startTime"))
        return None
    cycle = [last.get("startTime"), last.get("endTime")]
    _validate_cycle(cycle)
    return cycle


def _validate_cycle(cycle):
    if cycle is None:
        return
    if not isinstance(cycle, list) or len(cycle) != 2:
        raise fail("recheck-evidence-invalid", "Retain the original observed reuse cycle, not a reconstructed bound.")
    if blob_source._timestamp(cycle[1]) < blob_source._timestamp(cycle[0]):
        raise fail("ingestion-status-invalid", "Initial synchronization interval is invalid.")


def _binding_receipts(paths):
    if paths is None:
        return None
    if (not isinstance(paths, (tuple, list)) or len(paths) != 2
            or any(not isinstance(path, (str, Path)) or not str(path).strip() for path in paths)):
        raise fail("reuse-evidence-invalid", "Select both existing private creation evidence files.")
    _, prior, fingerprint = _document(paths[0])
    result = read_private(paths[1])
    blob_source._validate_reuse_receipts(prior, fingerprint, result)
    return prior, result


class Checkpoint:
    def __init__(self, directory, plan, *, context_provider=account_context, binding_receipts=None):
        _supported(plan)
        self.directory = private_io.private_directory(str(directory))
        self.context_provider = context_provider
        self.context = context_provider()
        self.plan_digest = digest(plan)
        self.operation_id = uuid.uuid4().hex
        self.summary = None
        self.excluded_cycle = None
        self.request_ids = []
        self.recovery_warnings = []
        self.acknowledgement = None
        self.write_acknowledgement = None
        self.write_observation = None
        self.binding_receipts = binding_receipts
        self.diagnostics = []
        self.observations = []
        self.binding_observations = []
        self.configuration = None
        self.creation = None

    def acknowledge(self, plan, response, not_before, *, url, body, headers):
        if (digest(plan) != self.plan_digest or plan["source"]["action"] != "create"
                or response.status not in {200, 201}
                or url != search_reconcile.resource_url(plan["source"])
                or headers.get("If-None-Match") != "*" or "If-Match" in headers
                or body != search_reconcile.canonical_bytes(plan["source"]["desired"])):
            raise fail("recheck-ownership-unproven", "Only the exact successful conditional create can retain a write acknowledgement.")
        self.write_observation = {
            "schema_version": "1.0", "state": "acknowledged", "type": "knowledge-source",
            "name": plan["source"]["name"], "http_status": response.status, "request_id": response.request_id,
        }
        if self.context_provider() != self.context:
            raise fail("recheck-auth-context-drift", "CLI context changed before write acknowledgement retention.")
        receipt = {
            "schema_version": "1.0", "kind": "blob-write-acknowledgement",
            "operation_id": self.operation_id, "plan_digest": self.plan_digest,
            "not_before": not_before.isoformat(), "context_digest": self.context,
            "write": {
                "method": "PUT", "url": url, "if_none_match": headers["If-None-Match"],
                "body_digest": digest(plan["source"]["desired"]), "status": response.status,
                "request_id": response.request_id, "response_etags": search_reconcile.response_etags(response),
                "generated": blob_source.generated_resources(response.body) if isinstance(response.body, dict) else [],
            },
        }
        reject_secrets(receipt)
        receipt["integrity"] = digest(receipt)
        path = private_io.private_file(self.directory, self.operation_id + ".blob-write.json", receipt)
        self.write_acknowledgement = {"operation_id": self.operation_id, "receipt_file": path.name,
                                      "evidence_digest": receipt["integrity"], "status": "retained"}

    def persist(self, plan, result, generated, not_before, *, token_provider, transport):
        reused = plan["source"]["action"] == "reuse"
        selected, other = ("reused", "created") if reused else ("created", "reused")
        owned = "reused_not_owned" if reused else "run_owned"
        if (digest(plan) != self.plan_digest or len(result["resources"][selected]) != 1
                or result["resources"][other] or result["resources"][selected] != result["ownership"][owned]):
            raise fail("recheck-ownership-unproven", "Retain exact acknowledged creation or read-only reuse; never adopt shared resources.")
        generated = copy.deepcopy(generated)
        creation = {key: copy.deepcopy(result[key]) for key in
                    ("approved_plan", "resources", "verification", "ownership")}
        creation["source"] = {"generated": generated}
        seed = {
            "schema_version": "1.0", "kind": "blob-source-acknowledgement",
            "operation_id": self.operation_id, "plan_digest": digest(plan),
            "not_before": not_before.isoformat(), "context_digest": self.context,
            "creation": creation, "request_ids": [],
        }
        if not reused:
            if self.context_provider() != self.context:
                raise fail("recheck-auth-context-drift", "CLI context changed before acknowledgement retention.")
            seed["integrity"] = digest(seed)
            path = private_io.private_file(self.directory, self.operation_id + ".blob-ack.json", seed)
            self.acknowledgement = {"operation_id": self.operation_id, "receipt_file": path.name,
                                    "evidence_digest": seed["integrity"], "status": "retained"}
        read, get, ids = _reader(transport, token_provider, warnings=self.recovery_warnings)
        self.request_ids = ids
        configuration = _configuration(plan, creation, generated, get, binding_receipts=self.binding_receipts,
                                       diagnostics=self.diagnostics, observations=self.observations)
        if reused:
            self.excluded_cycle = _baseline_cycle(plan["source"], read, token_provider)
        if self.context_provider() != self.context:
            raise fail("recheck-auth-context-drift", "CLI context changed during checkpoint capture; no checkpoint was retained.")
        receipt = {
            "schema_version": "3.1" if reused else "3.0", "kind": "blob-readiness-checkpoint",
            "operation_id": self.operation_id, "plan_digest": digest(plan),
            "not_before": not_before.isoformat(), "context_digest": self.context,
            "creation": creation, "configuration": configuration, "request_ids": ids,
        }
        if reused:
            receipt["excluded_cycle"] = self.excluded_cycle
            if self.binding_receipts is not None:
                receipt["schema_version"] = "3.2"
                receipt["binding_digest"] = digest(self.binding_receipts)
        receipt["integrity"] = digest(receipt)
        path = private_io.private_file(self.directory, self.operation_id + ".blob-readiness.json", receipt)
        self.request_ids = ids
        self.summary = {"operation_id": self.operation_id, "receipt_file": path.name,
                        "evidence_digest": receipt["integrity"], "status": "retained"}
        self.configuration, self.creation = configuration, creation

    def verify(self, plan, *, token_provider, transport):
        _, get, ids = _reader(transport, token_provider, warnings=self.recovery_warnings)
        try:
            _configuration(plan, self.creation, self.creation["source"]["generated"], get,
                           expected=self.configuration, binding_receipts=self.binding_receipts,
                           diagnostics=self.diagnostics, observations=self.observations,
                           binding_observations=self.binding_observations)
        finally:
            self.request_ids.extend(ids)
        if self.context_provider() != self.context:
            raise fail("recheck-auth-context-drift", "CLI context changed during generated readback.")

    def finish(self, result):
        record = {"schema_version": "1.0", "kind": "blob-operation-result",
                  "operation_id": self.operation_id, "plan_digest": self.plan_digest,
                  "result": copy.deepcopy(result)}
        reject_secrets(record)
        record["integrity"] = digest(record)
        path = private_io.private_file(self.directory, self.operation_id + ".blob-result.json", record)
        result["result_evidence"] = {"receipt_file": path.name, "status": "retained"}


def _document(input_path):
    document = read_private(input_path)
    reject_secrets(document)
    if set(document) != {"schema_version", "plan", "approval"} or document["schema_version"] != "1.0":
        raise fail("recheck-evidence-invalid", "Retain the original source envelope.")
    plan = document["plan"]
    if not isinstance(plan, dict):
        raise fail("recheck-evidence-invalid", "The original plan is unavailable.")
    _supported(plan)
    fingerprint = digest(plan)
    approval = document["approval"]
    if (not isinstance(approval, dict) or set(approval) != {"confirmed", "fingerprint"}
            or type(approval["confirmed"]) is not bool or approval["fingerprint"] != fingerprint
            or plan["source"]["action"] == "create" and approval["confirmed"] is not True):
        raise fail("approval-mismatch", "Retain unchanged creation consent or the fingerprinted read-only reuse plan.")
    return document, plan, fingerprint


def _load(input_path, receipt_path, *, acknowledgement=False, binding_receipts=None):
    document, plan, fingerprint = _document(input_path)
    receipt = read_private(receipt_path)
    reject_secrets(receipt)
    if acknowledgement and receipt.get("kind") == "blob-write-acknowledgement":
        _validate_write(plan, receipt)
        return plan, receipt
    reused = plan["source"]["action"] == "reuse"
    version = receipt.get("schema_version")
    if not isinstance(version, str):
        raise fail("recheck-evidence-invalid", "Checkpoint schema version must be a supported string.")
    core_projected = version in {"3.0", "3.1", "3.2"} and not acknowledgement
    projected = (version in {"2.0", "2.1", "2.2"} or core_projected) and not acknowledgement
    bound = reused and version in {"1.2", "2.2", "3.2"}
    fields = {"schema_version", "kind", "operation_id", "plan_digest", "not_before",
              "context_digest", "creation", "configuration", "request_ids", "integrity"}
    if reused:
        fields.add("excluded_cycle")
    if bound:
        fields.add("binding_digest")
    if acknowledgement:
        fields.remove("configuration")
    expected_version = ("3" if core_projected else "2" if projected else "1") + (".2" if bound else ".1" if reused else ".0")
    if (set(receipt) != fields or version != expected_version
            or receipt["kind"] != ("blob-source-acknowledgement" if acknowledgement else "blob-readiness-checkpoint")
            or acknowledgement and reused
            or bound and (binding_receipts is None or receipt["binding_digest"] != digest(binding_receipts))
            or receipt["plan_digest"] != fingerprint
            or not isinstance(receipt["operation_id"], str)
            or re.fullmatch("[0-9a-f]{32}", receipt["operation_id"]) is None
            or receipt["integrity"] != digest({k: v for k, v in receipt.items() if k != "integrity"})):
        raise fail("recheck-evidence-invalid", "Original operation/cutoff/checkpoint integrity is missing or changed; never reconstruct it.")
    blob_source._timestamp(receipt["not_before"])
    if reused:
        _validate_cycle(receipt["excluded_cycle"])
    creation = receipt["creation"]
    try:
        observed = creation["verification"]["readback"]
        generated = creation["source"]["generated"]
        expected = {"type": "knowledge-source", "name": plan["source"]["name"],
                    "etag": observed["etag"],
                    "definition_digest": digest(search_reconcile._definition(plan["source"]["desired"]))}
        valid = (
            set(creation) == {"approved_plan", "resources", "verification", "ownership", "source"}
            and set(creation["source"]) == {"generated"}
            and set(creation["verification"]) == {"readback", "absence", "request_ids", "idempotency"}
            and creation["verification"]["absence"] is False
            and creation["verification"]["idempotency"] == "exact readback is zero-write"
            and isinstance(creation["verification"]["request_ids"], list)
            and all(isinstance(item, str) for item in creation["verification"]["request_ids"])
            and creation["approved_plan"] == document["approval"]
            and creation["resources"] == {"created": [] if reused else [expected],
                                          "reused": [expected] if reused else [], "updated": [], "skipped": []}
            and creation["ownership"] == {"run_owned": [] if reused else [expected],
                                          "reused_not_owned": [expected] if reused else [], "owner": plan["owner"]}
            and observed == expected and isinstance(expected["etag"], str) and bool(expected["etag"].strip())
            and generated == blob_source.generated_resources(
                {"azureBlobParameters": {"createdResources": {item["type"]: item["name"] for item in generated}}},
                strict=True,
            )
            and (acknowledgement or set(receipt["configuration"]) == set(COLLECTIONS))
            and isinstance(receipt["request_ids"], list)
            and all(isinstance(item, str) for item in receipt["request_ids"])
            and isinstance(receipt["context_digest"], str)
            and search_reconcile.SHA256.fullmatch(receipt["context_digest"])
        )
        for kind, item in ({} if acknowledgement else receipt["configuration"]).items():
            if core_projected:
                valid = valid and semantic.valid(item, kind, search_reconcile.SHA256)
                if kind == "indexer":
                    valid = valid and item.get("core_digest") == item.get("non_schedule_digest")
                if kind == "datasource" and item.get("binding_proof") == "resource-id":
                    valid = valid and item["credential_digest"] in {
                        digest({"present": True, "value": {"connectionString": f"ResourceId={plan['boundary']['storage_id']}{suffix}"}})
                        for suffix in ("", ";")
                    }
                continue
            hashes = {"digest"} | (indexer.PROJECTION_FIELDS if projected and kind == "indexer" else set())
            valid = valid and set(item) == {"etag"} | hashes and isinstance(item["etag"], str) and bool(item["etag"].strip())
            valid = valid and all(isinstance(item[key], str) and search_reconcile.SHA256.fullmatch(item[key]) for key in hashes)
    except (KeyError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise fail("recheck-ownership-unproven", "Checkpoint must retain exact acknowledged ownership, generated configuration and provenance.")
    return plan, receipt


def _historical_result(receipt_path, receipt):
    path = Path(receipt_path).parent / (receipt["operation_id"] + ".blob-result.json")
    if not path.exists():
        return "not-recorded-by-pre-monitor-checkpoint"
    record = read_private(path)
    reject_secrets(record)
    if (set(record) != {"schema_version", "kind", "operation_id", "plan_digest", "result", "integrity"}
            or record["schema_version"] != "1.0" or record["kind"] != "blob-operation-result"
            or record["operation_id"] != receipt["operation_id"] or record["plan_digest"] != receipt["plan_digest"]
            or record["integrity"] != digest({key: value for key, value in record.items() if key != "integrity"})
            or not isinstance(record["result"], dict)):
        raise fail("recheck-evidence-invalid", "Historical operation result is malformed or changed; preserve original evidence.")
    result = record["result"]
    readiness = result.get("readiness", {})
    if not isinstance(readiness, dict):
        raise fail("recheck-evidence-invalid", "Historical readiness must be an object.")
    watch = readiness.get("watch")
    if watch is not None and (
            not isinstance(watch, dict) or watch.get("schema_version") != "1.0"
            or not isinstance(watch.get("state"), str)
            or watch.get("state") not in {"paused", "completed", "blocked"}):
        raise fail("recheck-evidence-invalid", "Historical watch metadata is malformed or unsupported.")
    return {"receipt_file": path.name, "status": result.get("status"),
            "first_failure": result.get("first_failure", result.get("first_blocker")),
            "watch": copy.deepcopy(watch),
            "writes_performed": result.get("writes_performed", result.get("completed_writes", []))}


def _validate_write(plan, receipt):
    try:
        write = receipt["write"]
        valid = (
            set(receipt) == {"schema_version", "kind", "operation_id", "plan_digest", "not_before",
                             "context_digest", "write", "integrity"}
            and receipt["schema_version"] == "1.0" and plan["source"]["action"] == "create"
            and receipt["plan_digest"] == digest(plan)
            and isinstance(receipt["operation_id"], str)
            and re.fullmatch("[0-9a-f]{32}", receipt["operation_id"]) is not None
            and isinstance(receipt["context_digest"], str)
            and search_reconcile.SHA256.fullmatch(receipt["context_digest"]) is not None
            and receipt["integrity"] == digest({k: v for k, v in receipt.items() if k != "integrity"})
            and set(write) == {"method", "url", "if_none_match", "body_digest", "status",
                               "request_id", "response_etags", "generated"}
            and write["method"] == "PUT" and write["if_none_match"] == "*"
            and type(write["status"]) is int and write["status"] in {200, 201}
            and write["url"] == search_reconcile.resource_url(plan["source"])
            and write["body_digest"] == digest(plan["source"]["desired"])
            and isinstance(write["request_id"], str) and bool(write["request_id"].strip())
            and set(write["response_etags"]) == {"body", "headers"}
            and isinstance(write["response_etags"]["headers"], list)
            and isinstance(write["generated"], list)
        )
        if write["generated"]:
            valid = valid and write["generated"] == blob_source.generated_resources(
                {"azureBlobParameters": {"createdResources": {
                    item["type"]: item["name"] for item in write["generated"]}}}, strict=True,
            )
    except (KeyError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise fail("recheck-ownership-unproven", "Retain the private authenticated conditional-write receipt; input booleans or observed existence cannot replace it.")
    blob_source._timestamp(receipt["not_before"])
    if search_reconcile.resolve_etag(write["response_etags"], write["request_id"]) is None:
        raise fail("creation-version-unproven", "Write acknowledgement has no response ETag; never borrow a later GET version.",
                   request_id=write["request_id"])


@reporting("blob-capture")
def capture(input_path, directory, *, token_provider=azure_cli_token, transport=http_request,
            storage_transport=http_request, context_provider=account_context,
            now=lambda: datetime.now(timezone.utc), progress: Progress | None = None,
            binding_paths=None):
    progress.update("evidence-validation")
    document, plan, fingerprint = _document(input_path)
    if plan["source"]["action"] != "reuse":
        raise fail("recheck-scope-unsupported", "Fresh capture accepts only a reuse plan; it cannot recover missing original creation proof.")
    binding_receipts = _binding_receipts(binding_paths)
    progress.update("context-check")
    checkpoint = Checkpoint(directory, plan, context_provider=context_provider, binding_receipts=binding_receipts)
    cutoff = now()
    progress.update("source-binding")
    _, get, ids = _reader(transport, token_provider)
    current = get(search_reconcile.resource_url(plan["source"]))
    generated = blob_source.generated_resources(current, strict=True)
    result = search_reconcile._completed(
        "blob-readiness-capture", fingerprint, plan["source"], action="reused",
        readback=current, request_ids=ids, absence=False,
    )
    result["approved_plan"] = document["approval"]
    progress.update("blob-inventory")
    inventory = blob_inventory.discover(plan["boundary"], plan["inventory_limits"],
                                       token_provider=token_provider, transport=storage_transport)
    if inventory["inventory_digest"] != plan["inventory_digest"]:
        raise fail("source-drift", "Selected Storage/ACL evidence differs from the reuse plan.")
    result["verification"]["request_ids"].extend(inventory["request_ids"])
    progress.update("checkpoint")
    checkpoint.persist(plan, result, generated, cutoff, token_provider=token_provider, transport=transport)
    return {
        "status": "completed", "outcome": "blob-readiness-capture",
        "recheck_checkpoint": checkpoint.summary, "writes_performed": [],
        "readiness": {"status": "unverified"}, "retrieval": "unverified", "knowledge_base": "not-verified",
        "ownership": result["ownership"], "cleanup": {"separate_confirmation_required": True},
        "read_only_evidence": {"request_ids": result["verification"]["request_ids"] + checkpoint.request_ids},
        "indexer_diagnostics": semantic.indexer_only(checkpoint.diagnostics),
        "generated_diagnostics": checkpoint.diagnostics, "indexer_observations": checkpoint.observations,
        "warnings": [blob_source.SNAPSHOT_WARNING, "Fresh reuse observation is not recovered creation ownership or ingestion proof.",
                     *get.recovery_warnings, *checkpoint.recovery_warnings,
                     *indexer.warnings(checkpoint.diagnostics)],
    }


@reporting("blob-capture")
def recover(input_path, acknowledgement_path, directory, *, token_provider=azure_cli_token,
            transport=http_request, storage_transport=http_request, context_provider=account_context,
            progress: Progress | None = None):
    progress.update("evidence-validation")
    plan, acknowledgement = _load(input_path, acknowledgement_path, acknowledgement=True)
    historical = _historical_result(acknowledgement_path, acknowledgement)
    directory = private_io.private_directory(str(directory))
    progress.update("context-check")
    if context_provider() != acknowledgement["context_digest"]:
        raise fail("recheck-auth-context-drift", "Current context differs from the acknowledged original run.")
    progress.update("source-binding")
    _, get, ids = _reader(transport, token_provider)
    diagnostics, observations, binding_observations = [], [], []
    if acknowledgement["kind"] == "blob-write-acknowledgement":
        write = acknowledgement["write"]
        current = get(search_reconcile.resource_url(plan["source"]))
        if (_etag(current) != search_reconcile.resolve_etag(write["response_etags"], write["request_id"])
                or search_reconcile._definition(current) != search_reconcile._definition(plan["source"]["desired"])):
            raise fail("definition-drift", "Current source differs from the acknowledged conditional-write version/definition.",
                       request_id=getattr(get, "request_id", None))
        generated = blob_source.generated_resources(current, strict=True)
        if write["generated"] and generated != write["generated"]:
            raise fail("definition-drift", "Generated identities differ from the create response.")
        verified = search_reconcile._completed(
            "create-blob-knowledge-source", acknowledgement["plan_digest"], plan["source"],
            action="created", readback=current, request_ids=[write["request_id"], *ids], absence=False,
        )
        creation = {key: verified[key] for key in ("approved_plan", "resources", "verification", "ownership")}
        creation["source"] = {"generated": generated}
    else:
        creation = acknowledgement["creation"]
    configuration = _configuration(plan, creation, creation["source"]["generated"], get,
                                   diagnostics=diagnostics, observations=observations)
    progress.update("blob-inventory")
    inventory = blob_inventory.discover(plan["boundary"], plan["inventory_limits"],
                                       token_provider=token_provider, transport=storage_transport)
    ids.extend(inventory["request_ids"])
    if inventory["inventory_digest"] != plan["inventory_digest"]:
        raise fail("source-drift", "Storage/ACL inventory differs from the acknowledged original run.")
    progress.update("checkpoint")
    _configuration(plan, creation, creation["source"]["generated"], get, expected=configuration,
                   diagnostics=diagnostics, observations=observations, binding_observations=binding_observations)
    if context_provider() != acknowledgement["context_digest"]:
        raise fail("recheck-auth-context-drift", "CLI context changed during recovery observation.")
    receipt = {**acknowledgement, "schema_version": "3.0", "kind": "blob-readiness-checkpoint", "configuration": configuration,
               "creation": creation, "request_ids": ids}
    receipt.pop("write", None)
    receipt.pop("integrity")
    receipt["integrity"] = digest(receipt)
    path = private_io.private_file(directory, receipt["operation_id"] + ".blob-readiness.json", receipt)
    return {
        "status": "completed", "outcome": "blob-readiness-recovery-capture", "writes_performed": [],
        "recheck_checkpoint": {"operation_id": receipt["operation_id"], "receipt_file": path.name,
                              "evidence_digest": receipt["integrity"], "status": "retained"},
        "readiness": {"status": "unverified"}, "retrieval": "unverified", "knowledge_base": "not-verified",
        "ownership": {"run_owned": [], "reused_not_owned": []},
        "original_run": {"ownership": creation["ownership"], "not_before": receipt["not_before"],
                         "historical_created": copy.deepcopy(creation["resources"]["created"]),
                         "original_failure": historical,
                         "acknowledgement_digest": acknowledgement["integrity"]},
        "read_only_evidence": {"request_ids": ids},
        "indexer_diagnostics": semantic.indexer_only(diagnostics),
        "generated_diagnostics": diagnostics, "indexer_observations": observations,
        "datasource_binding_observations": binding_observations,
        "safe_next_decision": "Run blob_recheck.py --input with the unchanged original input and --receipt with this checkpoint; then return to the KB/retrieval owner. Preserve the original first failure separately.",
        "warnings": [blob_source.SNAPSHOT_WARNING, "Configuration was observed during recovery; no earlier generated revision or new ownership is asserted.",
                     *get.recovery_warnings,
                     *indexer.warnings(diagnostics)],
    }


@reporting("blob-recheck")
def recheck(input_path, receipt_path, *, token_provider=azure_cli_token,
            transport=http_request, storage_transport=http_request,
            context_provider=account_context, monotonic=time.monotonic, sleep=time.sleep,
            now=lambda: datetime.now(timezone.utc), progress: Progress | None = None,
            binding_paths=None, watch_limits=None, cancelled=lambda: False):
    progress.update("evidence-validation")
    binding_receipts = _binding_receipts(binding_paths)
    plan, receipt = _load(input_path, receipt_path, binding_receipts=binding_receipts)
    limits = blob_source._poll_limits(watch_limits if watch_limits is not None else plan["poll"])
    creation = receipt["creation"]
    generated = creation["source"]["generated"]
    readiness = {"status": "unverified"}
    historical = "not-recorded-by-pre-monitor-checkpoint"
    ids = []
    recovery_warnings = []
    diagnostics, observations, binding_observations = [], [], []
    try:
        historical = _historical_result(receipt_path, receipt)
        progress.update("context-check")
        if context_provider() != receipt["context_digest"]:
            raise fail("recheck-auth-context-drift", "Current CLI tenant/subscription/principal differs from the original run; no auth changes were made.")
        read, get, ids = _reader(transport, token_provider)
        recovery_warnings = get.recovery_warnings

        def inventory():
            inventory = blob_inventory.discover(
                plan["boundary"], plan["inventory_limits"], token_provider=token_provider,
                transport=storage_transport,
            )
            ids.extend(inventory["request_ids"])
            if inventory["inventory_digest"] != plan["inventory_digest"]:
                raise fail("source-drift", "Selected Storage/ACL evidence differs from original creation.")

        for stage in ("before", "after"):
            if stage == "after":
                progress.update("blob-readback")
                inventory()
            progress.update("source-binding" if stage == "before" else "source-readback")
            _configuration(plan, creation, generated, get, binding_receipts=binding_receipts,
                           expected=receipt["configuration"], diagnostics=diagnostics, observations=observations,
                           binding_observations=binding_observations)
            if stage == "before":
                progress.update("blob-inventory")
                inventory()
                readiness = blob_source.monitor(
                    plan["source"], not_before=blob_source._timestamp(receipt["not_before"]),
                    limits=limits, token_provider=token_provider, transport=read,
                    monotonic=monotonic, sleep=sleep, progress=progress,
                    excluded_cycle=receipt.get("excluded_cycle"),
                    cancelled=cancelled,
                    indexer_name=next(item["name"] for item in generated if item["type"] == "indexer"),
                )
                if readiness["status"] != "verified":
                    raise HelperFailure(
                        readiness["code"], "Original-run ingestion remains unverified.",
                        blocked_at="verification", request_id=readiness.get("request_id"),
                        status=readiness.get("http_status"),
                    )
                cycle = readiness["synchronization"]
                if (cycle["itemsUpdatesProcessed"] == 0 or cycle["itemsSkipped"]
                        or blob_source._timestamp(cycle["endTime"]) > now()):
                    raise fail("ingestion-unverified", "A checkpoint is not prior ingestion proof; nonempty zero-skip completion is required.")
        progress.update("context-readback")
        if context_provider() != receipt["context_digest"]:
            raise fail("recheck-auth-context-drift", "CLI context changed during recheck.")
    except HelperFailure as failure:
        recovery_warnings.extend(failure.warnings)
        if failure.request_id and failure.request_id not in ids:
            ids.append(failure.request_id)
        safe_failure = HelperFailure(
            failure.code, failure.message if failure.blocked_at == "indexer-verification" else
            "Read-only evidence could not verify readiness; service details withheld.",
            blocked_at=failure.blocked_at, status=failure.http_status, request_id=failure.request_id,
        )
        result = blocked_result(safe_failure, outcome="blob-readiness-recheck", fingerprint=None)
        result["safe_next_decision"] = "Preserve the first failure. GET the exact source/generated definitions; for a concealed source binding supply --reuse-input-file/--reuse-result-file from its successful creation. Fix access or investigate actual drift read-only; do not replay creation, run/reset an indexer or default to cleanup."
        if failure.code == "datasource-binding-unverified":
            result["first_blocker"]["message"] = (
                "The datasource revision lacks independently observed current Storage binding; "
                "this is unverified, not evidence of misconfiguration."
            )
            result["safe_next_decision"] = (
                "Retain source and checkpoint. One exact datasource GET with includeConnectionString=true did not "
                "provide stable sanitized ResourceId proof. "
                "Ask the service owner for authoritative current child binding evidence; root identity and historical "
                "receipts are insufficient. Resume the same GET-only recheck if that readback becomes available. "
                "Do not retrieve keys, patch/recreate the source, run/reset an indexer, or delete resources."
            )
        if failure.code == "indexer-legacy-evidence-insufficient":
            result["safe_next_decision"] = "Retain the legacy checkpoint unchanged; GET current definitions and compare any legitimately retained preimage. This helper cannot infer its missing projection. A separately planned --capture reuse operation may observe fresh readiness, not recover historical configuration/ownership. Do not replay writes."
        readiness = {**readiness, "status": "unverified"}
        if readiness.get("watch", {}).get("state") == "paused":
            result["safe_next_decision"] = readiness["safe_next_decision"]
    else:
        result = {"status": "completed", "outcome": "blob-readiness-recheck", "writes_performed": []}
    result.update(
        readiness=readiness, retrieval="unverified", knowledge_base="not-verified",
        original_run={"operation_id": receipt["operation_id"], "plan_digest": receipt["plan_digest"],
                      "source_action": plan["source"]["action"],
                      "evidence_digest": receipt["integrity"], "not_before": receipt["not_before"],
                      "request_ids": creation["verification"]["request_ids"],
                      "checkpoint_request_ids": receipt["request_ids"],
                      "original_failure": historical,
                      "historical_created": copy.deepcopy(creation["resources"]["created"]),
                      "ownership": copy.deepcopy(creation["ownership"]), "generated": generated},
        ownership={"run_owned": [], "reused_not_owned": []},
        read_only_evidence={"request_ids": ids},
        indexer_diagnostics=semantic.indexer_only(diagnostics),
        generated_diagnostics=diagnostics, indexer_observations=observations,
        datasource_binding_observations=binding_observations,
        cleanup={"status": "not-requested", "separate_confirmation_required": True},
        recheck_checkpoint={"operation_id": receipt["operation_id"], "receipt_file": Path(receipt_path).name,
                            "evidence_digest": receipt["integrity"], "status": "retained"},
        warnings=[blob_source.SNAPSHOT_WARNING,
                  *recovery_warnings,
                  "Local checkpoint integrity is not a service signature or new ownership/cleanup authorization.",
                  *indexer.warnings(diagnostics)],
    )
    return result


def compact_result(result, directory):
    """Opt-in versioned presentation; retain the native result privately first."""
    reject_secrets(result)
    directory = private_io.private_directory(str(directory))
    path = private_io.private_file(directory, uuid.uuid4().hex + ".blob-result.json", result)
    ids = []

    def collect(value, key=None):
        if isinstance(value, dict):
            for field, child in value.items():
                collect(child, field)
        elif isinstance(value, list):
            for child in value:
                collect(child, key)
        elif (key in {"request_id", "request_ids"} or isinstance(key, str) and key.endswith("_request_ids")) and isinstance(value, str):
            ids.append(value)

    collect(result)
    failure = result.get("first_failure", result.get("first_blocker"))
    original = result.get("original_run", {})
    writes = result.get("writes_performed", result.get("completed_writes", []))
    readiness = result.get("readiness", {"status": "unverified"})
    item_error = readiness.get("first_error")
    if readiness.get("code") == "ingestion-timeout" and readiness.get("watch", {}).get("state") == "paused":
        failure = None
    elif failure and isinstance(item_error, dict) and item_error.get("request_id"):
        failure = {**failure, "request_id": item_error["request_id"]}
    historical = original.get("original_failure")
    historical_failure = historical.get("first_failure") if isinstance(historical, dict) else None
    historical_watch = historical.get("watch") if isinstance(historical, dict) else None
    if (historical_failure and historical_failure.get("code") == "ingestion-timeout"
            and isinstance(historical_watch, dict) and historical_watch.get("schema_version") == "1.0"
            and historical_watch.get("state") == "paused"):
        historical_failure = None
    generated = original.get("generated", result.get("source", {}).get("generated", []))
    diagnostic_keys = ("severity", "code", "field")
    diagnostics = dict.fromkeys(
        tuple(item[key] for key in diagnostic_keys)
        for item in result.get("generated_diagnostics", result.get("indexer_diagnostics", []))
    )
    return {
        "schema_version": "1.1" if "progress" in readiness else "1.0", "kind": "blob-operation-summary",
        "status": result["status"], "outcome": result["outcome"],
        "writes_performed": writes,
        "creation_acknowledgement": result.get("creation_acknowledgement"),
        "historical_created": [
            {"type": item["type"], "name": item["name"]}
            for item in original.get("historical_created", [])
        ],
        "generated_resources": [{"type": item["type"], "name": item["name"]} for item in generated],
        "readiness": {"status": readiness["status"], "watch": readiness.get("watch"),
                      **({"progress": readiness["progress"]} if "progress" in readiness else {})},
        "first_failure": ({key: failure.get(key) for key in ("code", "status", "request_id")}
                          if failure else None),
        "historical_failure": ({key: historical_failure.get(key) for key in ("code", "status", "request_id")}
                               if historical_failure else None),
        "first_retry": readiness.get("first_retry"),
        "diagnostics": [dict(zip(diagnostic_keys, item)) for item in diagnostics],
        "request_id_count": len(set(ids)), "evidence_file": path.name,
        "checkpoint_file": result.get("recheck_checkpoint", {}).get("receipt_file"),
        "retrieval": "unverified", "knowledge_base": "not-verified",
        "safe_next_decision": result.get("safe_next_decision",
                                       "Return to the KB/retrieval owner; no cleanup or new writes are authorized."
                                       if readiness["status"] == "verified" else
                                       "Retain resources and inspect the named source/indexer and private evidence. "
                                       "Use receipt-backed GET-only recheck when evidence is available; no write replay or cleanup."),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--input", type=Path)
    modes.add_argument("--capture", type=Path)
    modes.add_argument("--recover", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--receipt-dir", type=Path)
    parser.add_argument("--reuse-input-file", type=Path)
    parser.add_argument("--reuse-result-file", type=Path)
    parser.add_argument("--watch-seconds", type=int)
    parser.add_argument("--watch-max-requests", type=int)
    parser.add_argument("--watch-interval", type=int)
    parser.add_argument("--compact", action="store_true")
    add_progress_argument(parser)
    args = parser.parse_args(argv)
    if (args.capture and (not args.receipt_dir or args.receipt)
            or args.input and (not args.receipt or args.receipt_dir)
            or args.recover and (not args.receipt or not args.receipt_dir)):
        parser.error("--capture needs --receipt-dir; --input needs --receipt; --recover needs both.")
    if bool(args.reuse_input_file) != bool(args.reuse_result_file) or args.recover and args.reuse_input_file:
        parser.error("Select both reuse evidence files, only with --capture or --input.")
    options = {"binding_paths": (args.reuse_input_file, args.reuse_result_file)} if args.reuse_input_file else {}
    watch = (args.watch_seconds, args.watch_max_requests, args.watch_interval)
    if any(value is not None for value in watch):
        if not args.input or any(value is None for value in watch):
            parser.error("Explicit GET-only watch needs --input and all three --watch-* limits.")
        options["watch_limits"] = dict(zip(("deadline_seconds", "max_requests", "interval_seconds"), watch))
    try:
        if args.capture:
            result = capture(args.capture, args.receipt_dir, progress=Progress("blob-capture", enabled=args.progress), **options)
        elif args.recover:
            result = recover(args.recover, args.receipt, args.receipt_dir,
                             progress=Progress("blob-capture", enabled=args.progress))
        else:
            result = recheck(args.input, args.receipt, progress=Progress("blob-recheck", enabled=args.progress), **options)
    except HelperFailure as failure:
        outcome = "blob-readiness-recovery-capture" if args.recover else "blob-readiness-capture" if args.capture else "blob-readiness-recheck"
        result = blocked_result(failure, outcome=outcome, fingerprint=None)
        result["safe_next_decision"] = (
            "Preserve original error/resources. Inspect the exact source and genuine private evidence: "
            "--recover needs its retained acknowledgement; --capture needs a reuse plan and any required "
            "creation proof. If a checkpoint already exists, inspect it and use --input/--receipt. "
            "No write replay, new ownership or cleanup is authorized."
        )
    if args.compact:
        try:
            result = compact_result(result, args.receipt_dir or args.receipt.parent)
        except HelperFailure as failure:
            result.setdefault("warnings", []).append("compact-evidence-persistence-failed: full native result retained in output.")
            result["presentation_failure"] = {"code": failure.code}
            emit_result(result)
            return 2
    emit_result(result)
    return 0 if result["status"] == "completed" else 2


if __name__ == "__main__":
    sys.exit(main())
