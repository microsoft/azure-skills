from __future__ import annotations

import re
import time
from typing import Any, Callable
from urllib.parse import quote, unquote, urlencode
from xml.etree import ElementTree

try:
    from ._common import (
        MANAGEMENT_AUDIENCE, HelperFailure, TokenProvider, Transport, azure_cli_token,
        digest, http_request, reject_secrets, require_allowed_fields,
    )
except ImportError:
    from _common import (  # type: ignore[no-redef]
        MANAGEMENT_AUDIENCE, HelperFailure, TokenProvider, Transport, azure_cli_token,
        digest, http_request, reject_secrets, require_allowed_fields,
    )


STORAGE_AUDIENCE = "https://storage.azure.com/"
ARM_VERSION = "2025-06-01"
STORAGE_VERSION = "2025-05-05"
ACCOUNT_ID = re.compile(
    r"^/subscriptions/[0-9a-fA-F-]{36}/resourceGroups/[^/;?#\r\n]+/"
    r"providers/Microsoft\.Storage/storageAccounts/([a-z0-9]{3,24})$"
)
CONTAINER = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$")


def _fail(code: str, message: str, request_id: str | None = None) -> HelperFailure:
    return HelperFailure(code, message, blocked_at="source-preflight", request_id=request_id)


def _strip_etag_quotes(value: str) -> str:
    # Blob List XML returns unquoted ETags; DFS HTTP responses return
    # RFC 7232-quoted ETags for the identical underlying value.
    return value[1:-1] if len(value) >= 2 and value[0] == '"' and value[-1] == '"' else value


def validate_boundary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail("boundary-invalid", "An explicitly selected Storage boundary is required.")
    reject_secrets(value)
    require_allowed_fields(value, {"storage_id", "container", "prefix", "is_adls"}, label="boundary")
    if (
        not isinstance(value.get("storage_id"), str)
        or ACCOUNT_ID.fullmatch(value["storage_id"]) is None
        or not isinstance(value.get("container"), str)
        or CONTAINER.fullmatch(value["container"]) is None
        or "--" in value["container"]
        or not isinstance(value.get("prefix"), str)
        or type(value.get("is_adls")) is not bool
    ):
        raise _fail("boundary-invalid", "Exact Storage ID, container, explicit prefix (including empty root), and subtype are required.")
    prefix = value["prefix"]
    try:
        value["storage_id"].encode("utf-8")
        prefix.encode("utf-8")
    except UnicodeError as exc:
        raise _fail("boundary-invalid", "Storage ID and prefix must be valid UTF-8.") from exc
    if (
        prefix.startswith("/")
        or "\\" in prefix
        or any(ord(c) < 32 for c in prefix)
        or (any(part in {".", "..", ""} for part in prefix.rstrip("/").split("/")) and prefix != "")
        or "//" in prefix
        or value["is_adls"] and prefix.endswith("/")
        or not value["is_adls"] and prefix and not prefix.endswith("/")
    ):
        raise _fail(
            "boundary-ambiguous",
            "Use explicit empty root, a Blob folder prefix ending in '/', or an ADLS directory path without a trailing '/'. Arbitrary partial-name prefixes are not verified.",
        )
    return dict(value)


def validate_limits(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        raise _fail("input-schema-invalid", "inventory_limits must be an object.")
    require_allowed_fields(value, {"max_pages", "max_objects", "max_requests", "deadline_seconds"},
                           label="inventory limits")
    for field, maximum in (
        ("max_pages", 1000), ("max_objects", 100000), ("max_requests", 200000),
        ("deadline_seconds", 3600),
    ):
        if type(value.get(field)) is not int or not 1 <= value[field] <= maximum:
            raise _fail("input-schema-invalid", "Inventory limits must be bounded positive integers.")
    return value


class _Reader:
    def __init__(
        self, limits: dict[str, int], token_provider: TokenProvider,
        transport: Transport, monotonic: Callable[[], float],
        deadline: float | None = None,
    ) -> None:
        self.limits = limits
        self.transport = transport
        self.monotonic = monotonic
        self.deadline = monotonic() + limits["deadline_seconds"]
        if deadline is not None:
            self.deadline = min(self.deadline, deadline)
        self.token_provider = token_provider
        self.tokens: dict[str, str] = {}
        self.request_ids: list[str] = []
        self.requests = 0

    def read(self, method: str, url: str, *, arm: bool = False, raw: bool = False) -> Any:
        if method not in {"GET", "HEAD"}:
            raise _fail("source-write-forbidden", "Storage probes may only read.")
        remaining = self.deadline - self.monotonic()
        if self.requests >= self.limits["max_requests"] or remaining <= 0:
            raise _fail("inventory-incomplete", "Inventory exceeded the approved request or time bound.")
        audience = MANAGEMENT_AUDIENCE if arm else STORAGE_AUDIENCE
        if audience not in self.tokens:
            self.tokens[audience] = self.token_provider(audience)
        remaining = self.deadline - self.monotonic()
        if remaining <= 0:
            raise _fail("inventory-incomplete", "Inventory deadline elapsed during authentication.")
        self.requests += 1
        try:
            result = self.transport(
                method, url, self.tokens[audience], timeout=min(30, remaining),
                headers={} if arm else {"x-ms-version": STORAGE_VERSION, "Accept": "application/xml"},
                raw_response=raw, max_response_bytes=8 * 1024 * 1024, follow_redirects=False,
                response_deadline=time.monotonic() + remaining,
            )
        except HelperFailure as failure:
            if failure.code in {"response-too-large", "response-deadline-exceeded"}:
                raise HelperFailure(
                    "inventory-incomplete", "Source evidence exceeded the body or time bound.",
                    blocked_at="source-preflight", request_id=failure.request_id, status=failure.http_status,
                ) from failure
            raise HelperFailure(
                "source-inaccessible", "Source evidence could not be read; inaccessible is not absent.",
                blocked_at="source-preflight", request_id=failure.request_id, status=failure.http_status,
            ) from failure
        if result.request_id:
            self.request_ids.append(result.request_id)
        if result.status != 200:
            raise HelperFailure(
                "source-inaccessible", "Source evidence could not be read; inaccessible is not absent.",
                blocked_at="source-preflight", request_id=result.request_id, status=result.status,
            )
        if self.monotonic() >= self.deadline:
            raise _fail("inventory-incomplete", "Inventory deadline elapsed during a read.", result.request_id)
        return result


def _account(boundary: dict[str, Any], reader: _Reader) -> dict[str, Any]:
    response = reader.read(
        "GET", f"https://management.azure.com{quote(boundary['storage_id'], safe='/')}?api-version={ARM_VERSION}", arm=True,
    )
    body = response.body
    if not isinstance(body, dict) or body.get("id") != boundary["storage_id"]:
        raise _fail("storage-identity-mismatch", "Storage readback does not match the selected resource.", response.request_id)
    properties = body.get("properties")
    if not isinstance(properties, dict):
        raise _fail("hns-unverified", "Storage readback must explicitly establish HNS.", response.request_id)
    # isHnsEnabled is set only at account creation and is immutable thereafter; ARM omits it
    # from readback whenever it was never explicitly enabled, which documented behavior treats
    # as a permanent, unambiguous false (Blob, not ADLS) rather than an unknown/undetermined state.
    raw_hns = properties.get("isHnsEnabled")
    if type(raw_hns) is not bool:
        if raw_hns is not None:
            raise _fail("hns-unverified", "Storage readback must explicitly establish HNS.", response.request_id)
        hns_value = False
    else:
        hns_value = raw_hns
    if hns_value != boundary["is_adls"]:
        raise _fail("source-drift", "Storage HNS differs from the selected subtype.", response.request_id)
    if properties.get("provisioningState") != "Succeeded":
        raise _fail("storage-not-ready", "Storage account provisioning is not complete.", response.request_id)
    endpoints = properties.get("primaryEndpoints")
    account = boundary["storage_id"].rsplit("/", 1)[1]
    selected_endpoints = {}
    for kind in ("blob", "dfs") if boundary["is_adls"] else ("blob",):
        expected = f"https://{account}.{kind}.core.windows.net/"
        if not isinstance(endpoints, dict) or endpoints.get(kind) != expected:
            raise _fail("storage-endpoint-unverified", "Storage service endpoint is not the selected public-cloud account endpoint.", response.request_id)
        selected_endpoints[kind] = expected
    return {
        "id": body["id"], "hns": hns_value, "endpoints": selected_endpoints,
        "network_digest": digest({k: properties.get(k) for k in
                                 ("publicNetworkAccess", "networkAcls", "privateEndpointConnections")}),
    }


def _object_name(element: Any) -> str:
    if element is None or not isinstance(element.text, str) or not element.text:
        raise _fail("inventory-invalid", "Listed object has no exact name.")
    name = element.text
    if element.get("Encoded") == "true":
        if re.search(r"%(?![0-9A-Fa-f]{2})", name):
            raise _fail("inventory-invalid", "Listed encoded name is ambiguous.")
        try:
            name = unquote(name, errors="strict")
        except UnicodeError as exc:
            raise _fail("inventory-invalid", "Listed encoded name is invalid.") from exc
    elif element.get("Encoded") not in {None, "false"}:
        raise _fail("inventory-invalid", "Unknown listed-name encoding.")
    if any(ord(c) < 32 for c in name):
        raise _fail("inventory-invalid", "Control characters in object names are unsupported.")
    return name


def _objects(
    boundary: dict[str, Any], account: dict[str, Any], reader: _Reader,
) -> list[dict[str, Any]]:
    prefix = boundary["prefix"]
    if boundary["is_adls"] and prefix:
        prefix += "/"
    base = account["endpoints"]["blob"] + boundary["container"]
    marker = ""
    markers: set[str] = set()
    objects: dict[str, dict[str, Any]] = {}
    for _ in range(reader.limits["max_pages"]):
        query = {"restype": "container", "comp": "list", "prefix": prefix,
                 "maxresults": str(min(5000, reader.limits["max_objects"])), "marker": marker}
        response = reader.read("GET", base + "?" + urlencode(query), raw=True)
        payload = response.body
        if not isinstance(payload, bytes) or b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
            raise _fail("inventory-invalid", "Expected bounded Blob listing XML without declarations.", response.request_id)
        try:
            root = ElementTree.fromstring(payload)
        except ElementTree.ParseError as exc:
            raise _fail("inventory-invalid", "Blob listing XML is invalid.", response.request_id) from exc
        if root.tag != "EnumerationResults" or len(root.findall("Blobs")) != 1 or len(root.findall("NextMarker")) != 1:
            raise _fail("inventory-incomplete", "Blob listing must contain objects and an explicit continuation marker.", response.request_id)
        if any(child.tag != "Blob" for child in root.find("Blobs")):
            raise _fail("inventory-incomplete", "Hierarchical listing cannot prove complete flat inventory.", response.request_id)
        for item in root.findall("Blobs/Blob"):
            name = _object_name(item.find("Name"))
            etag = item.findtext("Properties/Etag")
            size = item.findtext("Properties/Content-Length")
            kind = item.findtext("Properties/ResourceType")
            if (
                not name.startswith(prefix) or name in objects or not etag
                or not isinstance(size, str) or re.fullmatch(r"[0-9]+", size) is None
                or boundary["is_adls"] and kind not in {"file", "directory"}
                or boundary["is_adls"] and (
                    "\\" in name or any(part in {"", ".", ".."} for part in name.split("/"))
                )
                or item.find("Snapshot") is not None
            ):
                raise _fail("inventory-invalid", "Object identity is duplicate, outside scope, or incomplete.", response.request_id)
            objects[name] = {
                "path": name, "url": base + "/" + quote(name, safe="/"), "etag": etag,
                "size": int(size), "version": item.findtext("VersionId"),
                "kind": kind if boundary["is_adls"] else "file",
            }
            if len(objects) > reader.limits["max_objects"]:
                raise _fail("inventory-incomplete", "Inventory exceeds the approved object bound.", response.request_id)
        marker = root.findtext("NextMarker") or ""
        if not marker:
            return [objects[name] for name in sorted(objects)]
        if marker in markers:
            raise _fail("inventory-incomplete", "Storage repeated a continuation token.", response.request_id)
        markers.add(marker)
    raise _fail("inventory-incomplete", "Unconsumed pages exceed the approved page bound.")


def _adls_paths(
    boundary: dict[str, Any], account: dict[str, Any], objects: list[dict[str, Any]], reader: _Reader,
) -> list[dict[str, Any]]:
    paths: dict[str, str] = {"": "directory", boundary["prefix"]: "directory"}
    identities = {item["path"]: item for item in objects}
    for name, kind in [(boundary["prefix"], "directory")] + [(item["path"], item["kind"]) for item in objects]:
        paths[name] = kind
        parts = name.split("/")
        for index in range(1, len(parts)):
            paths["/".join(parts[:index])] = "directory"
    records = []
    for path in sorted(paths):
        base_url = account["endpoints"]["dfs"] + boundary["container"] + "/" + quote(path, safe="/")
        acl_response = reader.read("HEAD", base_url + "?action=getAccessControl&upn=false")
        headers = {key.lower(): value for key, value in acl_response.headers.items()}
        fields = ("x-ms-owner", "x-ms-group", "x-ms-permissions", "x-ms-acl", "etag")
        if any(not headers.get(field) for field in fields):
            raise _fail("adls-evidence-unverified", "Exact ADLS path type and ACL/property readback are required.", acl_response.request_id)
        # getAccessControl never returns x-ms-resource-type; the filesystem root itself has
        # no resource type either, so only non-root paths can be, and must be, type-verified
        # via a separate plain getProperties HEAD.
        if path:
            props_response = reader.read("HEAD", base_url)
            properties = {key.lower(): value for key, value in props_response.headers.items()}
            resource_type = properties.get("x-ms-resource-type")
            if resource_type != paths[path]:
                raise _fail("adls-evidence-unverified", "Exact ADLS path type and ACL/property readback are required.", props_response.request_id)
            if (
                not properties.get("etag")
                or _strip_etag_quotes(properties["etag"]) != _strip_etag_quotes(headers["etag"])
            ):
                raise _fail("source-drift", "ADLS access-control and properties ETags disagree.", props_response.request_id)
        if path in identities and _strip_etag_quotes(headers["etag"]) != _strip_etag_quotes(identities[path]["etag"]):
            raise _fail("source-drift", "Blob and DFS path ETags disagree.", acl_response.request_id)
        records.append({"path": path, "kind": paths[path],
                        "properties_digest": digest({field: headers[field] for field in fields})})
    return records


def _snapshot(boundary: dict[str, Any], reader: _Reader) -> dict[str, Any]:
    account = _account(boundary, reader)
    objects = _objects(boundary, account, reader)
    adls = _adls_paths(boundary, account, objects, reader) if boundary["is_adls"] else []
    return {"boundary": boundary, "account": account, "objects": objects, "adls_paths": adls}


def discover(
    boundary: Any, limits: Any, *,
    token_provider: TokenProvider = azure_cli_token, transport: Transport = http_request,
    monotonic: Callable[[], float] = time.monotonic,
    deadline: float | None = None,
) -> dict[str, Any]:
    boundary = validate_boundary(boundary)
    reader = _Reader(validate_limits(limits), token_provider, transport, monotonic, deadline)
    first = _snapshot(boundary, reader)
    second = _snapshot(boundary, reader)
    if digest(first) != digest(second):
        raise _fail("source-drift", "Consecutive complete source observations differ; no stable evidence is available.")
    return {
        "status": "discovered", **second, "inventory_digest": digest(second),
        "mutation": "none", "writes_performed": [], "request_ids": reader.request_ids,
        "operator_reachability": "verified", "managed_ingestion_reachability": "not-proven",
        "warnings": [
            "Observations are not an atomic Storage snapshot or a lock; source objects can change afterward.",
            "ACL readback establishes observed metadata, not effective Search principal permissions.",
        ],
    }
