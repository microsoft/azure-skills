"""Filtered, immutable creation evidence; never a credentialized callback surface."""
from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path
import uuid

try:
    from . import _bootstrap_io as private_io
    from ._common import HelperFailure, digest, load_approved_input, reject_secrets, odata_name, validate_search_endpoint
except ImportError:
    import _bootstrap_io as private_io
    from _common import HelperFailure, digest, load_approved_input, reject_secrets, odata_name, validate_search_endpoint


def fail(code, message):
    return HelperFailure(code, message, blocked_at="cleanup-provenance")


def version_identity(value):
    get = value.get if isinstance(value, dict) else lambda key: getattr(value, key, None)
    identifier, created = get("id"), get("created_at")
    if isinstance(created, datetime):
        created = int(created.timestamp()) if created.tzinfo is not None else None
    if not isinstance(identifier, str) or not identifier.strip() or type(created) is not int or created <= 0:
        return None
    return {"id": identifier, "created_at": created}


def add_argument(parser):
    parser.add_argument("--cleanup-receipt-dir", type=Path,
                        help="Existing absolute private directory for filtered original-create evidence.")


class Capture:
    def __init__(self, directory, document):
        self.directory = private_io.private_directory(str(directory))
        self.plan_digest = digest(document["plan"])
        self.owner = document["plan"].get("owner")
        self.records = {}
        self.summaries = []

    def start(self, target, acknowledgement):
        acknowledgement.setdefault("version_identity", None)
        record = {
            "schema_version": "1.0", "kind": "cleanup-creation-receipt",
            "plan_digest": self.plan_digest, "owner": self.owner, "target": target,
            "state": "acknowledged", "acknowledgement": acknowledgement, "snapshot": None,
        }
        key = digest(target)
        self.records[key] = record
        self._persist(record)

    def finish(self, target, snapshot):
        record = copy.deepcopy(self.records[digest(target)])
        ack = record["acknowledgement"]
        snapshot.setdefault("version_identity", None)
        if (snapshot["version_identity"] != ack["version_identity"]
                or (target["type"] == "prompt-agent-version" and ack["version_identity"] is None)):
            raise fail("creation-version-unproven", "Native version identity/creation time must match the original acknowledgement.")
        if not isinstance(ack["request_id"], str) or not ack["request_id"].strip():
            raise fail("creation-request-id-unavailable", "Original native acknowledgement lacks a request ID.")
        if snapshot["definition_digest"] != ack["definition_digest"]:
            raise fail("definition-drift", "Readback differs from the acknowledged original creation.")
        record.update(state="verified", snapshot=snapshot)
        self._persist(record)

    def _persist(self, record):
        reject_secrets(record)
        value = {**record, "integrity": digest(record)}
        try:
            path = private_io.private_file(self.directory, uuid.uuid4().hex + ".cleanup.json", value)
        except OSError as exc:
            raise fail("cleanup-receipt-persistence-failed", "Acknowledged creation evidence could not be retained privately.") from exc
        self.summaries.append({"target": record["target"], "state": record["state"],
                               "receipt_file": str(path), "evidence_digest": value["integrity"]})


def search_target(plan):
    return {"type": plan["resource_type"], "endpoint": validate_search_endpoint(plan["endpoint"]),
            **{key: plan[key] for key in ("name", "api_version")}}


def search_ack(capture, plan, response):
    try:
        from . import search_reconcile as search, _cleanup_dependencies as dependencies
    except ImportError:
        import search_reconcile as search, _cleanup_dependencies as dependencies
    generated = None
    if plan["resource_type"] == "knowledge-source":
        try:
            generated = dependencies.generated(response.body) if isinstance(response.body, dict) else None
        except HelperFailure:
            pass
    capture.start(search_target(plan), {
        "operation": "search-create", "status": response.status, "request_id": response.request_id,
        "definition_digest": digest(search._definition(plan["desired"])),
        "etag_evidence": search.response_etags(response), "generated": generated, "version": None,
    })


def search_finish(capture, plan, current, token, transport):
    try:
        from . import search_reconcile as search, _cleanup_dependencies as dependencies
    except ImportError:
        import search_reconcile as search, _cleanup_dependencies as dependencies
    target = search_target(plan)
    ack = capture.records[digest(target)]["acknowledgement"]
    etag = search.resolve_etag(ack["etag_evidence"], ack["request_id"])
    if ack["status"] != 201 or not etag or current is None or current.get("@odata.etag") != etag:
        raise fail("creation-version-unproven", "Require original HTTP 201 and the unchanged acknowledged ETag, not a later GET version.")
    children = []
    if plan["resource_type"] == "knowledge-source":
        if ack["generated"] is None or dependencies.generated(current) != ack["generated"]:
            raise fail("generated-creation-evidence-unavailable", "The original create response did not identify this exact generated cascade.")
        for kind, name in sorted(ack["generated"].items()):
            url = f"{plan['endpoint'].rstrip('/')}/{dependencies.COLLECTIONS[kind]}('{odata_name(name)}')?api-version={plan['api_version']}"
            child, _ = search.read_resource(url, token, transport=transport)
            if child is None or child.get("name") != name or not child.get("@odata.etag"):
                raise fail("generated-version-unavailable", "An original generated child lacks exact version readback.")
            children.append({"type": kind, "name": name, "etag": child["@odata.etag"], "definition_digest": digest(child)})
        refreshed, _ = search.read_resource(search.resource_url(plan), token, transport=transport)
        if (refreshed is None or refreshed.get("@odata.etag") != etag
                or search._definition(refreshed) != search._definition(current)
                or dependencies.generated(refreshed) != ack["generated"]):
            raise fail("definition-drift", "Source changed during original generated-child capture.")
    capture.finish(target, {"definition_digest": digest(search._definition(current)), "etag": etag, "generated": children})


def project_target(plan, kind, *, name=None, version=None):
    target = {"type": kind, "project_resource_id": plan["project_resource_id"].casefold(),
              "project_endpoint": plan["project_endpoint"].rstrip("/"),
              "name": name or plan["connection"]["name"]}
    if version is not None:
        target["version"] = version
    return target


def connection_ack(capture, plan, response):
    body = response.body if isinstance(response.body, dict) else {}
    capture.start(project_target(plan, "project-connection"), {
        "operation": "project-connection-create", "status": response.status, "request_id": response.request_id,
        "definition_digest": digest(body), "version": None, "generated": None,
        "etag_evidence": {"body": body.get("etag") or body.get("@odata.etag"),
                          "headers": [v for k, v in response.headers.items() if k.casefold() == "etag"]},
    })


def connection_finish(capture, plan, body):
    try:
        from .search_reconcile import resolve_etag
    except ImportError:
        from search_reconcile import resolve_etag
    target = project_target(plan, "project-connection")
    ack = capture.records[digest(target)]["acknowledgement"]
    etag = resolve_etag(ack["etag_evidence"], ack["request_id"])
    if ack["status"] != 201 or not etag or etag != (body.get("etag") or body.get("@odata.etag")):
        raise fail("creation-version-unproven", "Connection readback must retain its original HTTP 201 ETag.")
    capture.finish(target, {"definition_digest": digest(body), "etag": etag, "generated": []})


def sdk_response_hook(metadata):
    def capture(response):
        native = response.http_response
        metadata["request_id"] = next((v for k, v in native.headers.items()
                                       if k.casefold() in ("request-id", "x-request-id", "x-ms-request-id", "apim-request-id")), None)
        metadata["status"] = native.status_code
    return capture


def agent_ack(capture, plan, created, metadata):
    target = project_target(plan, "prompt-agent-version", name=created.name, version=str(created.version))
    capture.start(target, {
        "operation": "agents.create_version", "status": metadata.get("status"), "request_id": metadata.get("request_id"),
        "definition_digest": digest(created.definition.as_dict()), "version": str(created.version),
        "etag_evidence": None, "generated": None,
        "version_identity": version_identity(created),
    })
    if (metadata.get("status") not in (200, 201) or created.name != plan["agent"]["name"]
            or str(created.version) == plan["agent"]["version"] or version_identity(created) is None):
        raise fail("ownership-unproven", "The original SDK return must identify a newly created version in the approved agent.")
    return target


def load(input_path, receipt_path, target):
    try:
        from .blob_recheck import read_private
        from . import search_reconcile as search
    except ImportError:
        from blob_recheck import read_private
        import search_reconcile as search
    _, plan, fingerprint = load_approved_input(input_path)
    record = read_private(receipt_path)
    reject_secrets(record)
    fields = {"schema_version", "kind", "plan_digest", "owner", "target", "state", "acknowledgement", "snapshot", "integrity"}
    if (not isinstance(record, dict) or set(record) != fields or record["schema_version"] != "1.0"
            or record["kind"] != "cleanup-creation-receipt" or record["state"] != "verified"
            or record["plan_digest"] != fingerprint or record["owner"] != plan.get("owner")
            or record["target"] != target
            or record["integrity"] != digest({k: v for k, v in record.items() if k != "integrity"})):
        raise fail("ownership-unproven", "Require the exact original verified producer receipt and original approval; ACK/recovery/reuse cannot substitute.")
    ack, snapshot = record["acknowledgement"], record["snapshot"]
    if (not isinstance(ack, dict) or set(ack) != {"operation", "status", "request_id", "definition_digest", "etag_evidence", "generated", "version", "version_identity"}
            or not isinstance(snapshot, dict) or set(snapshot) != {"definition_digest", "etag", "generated", "version_identity"}
            or not isinstance(ack["request_id"], str) or not ack["request_id"].strip()
            or snapshot["definition_digest"] != ack["definition_digest"]
            or not isinstance(snapshot["definition_digest"], str) or not search.SHA256.fullmatch(snapshot["definition_digest"])
            or not isinstance(snapshot["generated"], list)):
        raise fail("ownership-unproven", "Producer receipt lacks complete acknowledged version evidence.")
    if (snapshot["version_identity"] != ack["version_identity"]
            or (target["type"] == "prompt-agent-version" and (
                not isinstance(snapshot["version_identity"], dict)
                or set(snapshot["version_identity"]) != {"id", "created_at"}
                or version_identity(snapshot["version_identity"]) != snapshot["version_identity"]))):
        raise fail("ownership-unproven", "Native version birth identity is missing or changed.")
    if target["type"] != "prompt-agent-version" and (
        not isinstance(ack["etag_evidence"], dict) or set(ack["etag_evidence"]) != {"body", "headers"}
        or not isinstance(ack["etag_evidence"]["headers"], list)
    ):
        raise fail("ownership-unproven", "Native ETag evidence must be complete.")
    if target["type"] in ("knowledge-base", "knowledge-source"):
        if (ack["operation"] != "search-create" or ack["status"] != 201
                or search.resolve_etag(ack["etag_evidence"], ack["request_id"]) != snapshot["etag"]
                or not isinstance(snapshot["etag"], str) or not snapshot["etag"].strip()):
            raise fail("creation-version-unproven", "Original Search create acknowledgement and snapshot versions disagree.")
    elif target["type"] == "project-connection":
        if (ack["operation"] != "project-connection-create" or ack["status"] != 201
                or search.resolve_etag(ack["etag_evidence"], ack["request_id"]) != snapshot["etag"]
                or not snapshot["etag"] or snapshot["generated"]):
            raise fail("creation-version-unproven", "Original connection acknowledgement and readback versions disagree.")
    elif target["type"] == "prompt-agent-version":
        if (ack["operation"] not in ("agents.create_version", "agents.create") or ack["status"] not in (200, 201)
                or (ack["operation"] == "agents.create" and ack["status"] != 200)
                or ack["version"] != target["version"] or snapshot["etag"] is not None or snapshot["generated"]):
            raise fail("ownership-unproven", "Require original SDK version-create return and its exact readback.")
    else:
        raise fail("cleanup-kind-unsupported", "No producer receipt contract supports this target.")
    return plan, record
