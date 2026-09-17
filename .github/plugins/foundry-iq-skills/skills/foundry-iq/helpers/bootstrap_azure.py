"""Closed Search bootstrap workflow. Never a caller-programmable command runner."""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import time
import uuid
from pathlib import Path

try:
    from ._progress import Progress, add_progress_argument, reporting
    from ._common import HelperFailure, blocked_result, digest, emit_result, normalize_azure_location, reject_secrets
    from ._bootstrap_io import MAX_BYTES, failure, private_directory, private_file, read_json, run_cli
except ImportError:
    from _progress import Progress, add_progress_argument, reporting
    from _common import HelperFailure, blocked_result, digest, emit_result, normalize_azure_location, reject_secrets
    from _bootstrap_io import MAX_BYTES, failure, private_directory, private_file, read_json, run_cli

API = "2025-05-01"
PROVIDER_API = "2021-04-01"
SCHEMA = "2.0"
WAIT_CONDITION = (
    "(contains(['succeeded','Succeeded','SUCCEEDED'], properties.provisioningState) && "
    "contains(['running','Running','RUNNING'], properties.status)) || "
    "contains(['failed','Failed','FAILED','canceled','Canceled','CANCELED','cancelled','Cancelled','CANCELLED',"
    "'deleting','Deleting','DELETING','deleted','Deleted','DELETED'], properties.provisioningState) || "
    "contains(['error','Error','ERROR','degraded','Degraded','DEGRADED'], properties.status)"
)
GUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
HASH = re.compile(r"sha256:[0-9a-f]{64}")
TEXT = re.compile(r"[A-Za-z0-9 ._@:/()-]{1,256}")
POLICY_ID = re.compile(
    r"(?:/subscriptions/[0-9a-f-]{36}(?:/resourceGroups/[A-Za-z0-9_.()-]+"
    r"(?:/providers/Microsoft.Search/searchServices/[a-z0-9-]+)?)?"
    r"|/providers/Microsoft.Management/managementGroups/[A-Za-z0-9_.-]+)?"
    r"/providers/Microsoft.Authorization/(?:policyAssignments|policyDefinitions|policySetDefinitions|policyExemptions)/[A-Za-z0-9_.-]+",
    re.IGNORECASE,
)


def closed(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise failure("bootstrap-input-invalid", label + " needs exactly the documented fields.")


def text(value, pattern=TEXT):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def validate(request):
    closed(request, {
        "schema_version", "resource_kind", "action", "subscription_id", "tenant_id",
        "resource_group", "name", "location", "sku", "replicas", "partitions",
        "public_network_access", "tags", "owner", "prerequisites", "limits", "receipt_dir",
    }, "Bootstrap choices")
    if request["schema_version"] != SCHEMA:
        raise failure("bootstrap-contract-version", "Regenerate choices and artifacts using bootstrap schema 2.0 and native wait limits.")
    reject_secrets(request)
    if (
        request["resource_kind"] != "search"
        or request["action"] not in ("create", "reuse")
        or not text(request["subscription_id"], GUID) or not text(request["tenant_id"], GUID)
        or not text(request["resource_group"], re.compile(r"[A-Za-z0-9_()-][A-Za-z0-9_.()-]{0,89}"))
        or request["resource_group"].endswith(".")
        or not text(request["name"], re.compile(r"(?=.{2,60}$)[a-z0-9][a-z0-9]+(?:-[a-z0-9]+)*"))
        or normalize_azure_location(request["location"]) is None
        or request["sku"] not in ("basic", "standard")
        or type(request["replicas"]) is not int or not 1 <= request["replicas"] <= (3 if request["sku"] == "basic" else 12)
        or type(request["partitions"]) is not int or request["partitions"] not in (
            (1,) if request["sku"] == "basic" else (1, 2, 3, 4, 6, 12))
        or request["public_network_access"] != "Enabled" or not text(request["owner"])
    ):
        raise failure("bootstrap-input-invalid", "Select supported, explicit Search identity, keyless public networking and capacity.")
    tags = request["tags"]
    if not isinstance(tags, dict) or len(tags) > 20 or any(
        not text(k, re.compile(r"[A-Za-z0-9_.-]{1,128}")) or not text(v) for k, v in tags.items()
    ):
        raise failure("bootstrap-input-invalid", "Tags must be bounded non-secret labels.")
    if request["action"] == "create" and any(k in tags for k in ("foundry-iq-owner", "foundry-iq-operation")):
        raise failure("bootstrap-input-invalid", "Creation ownership tags are generated, not caller overrides.")
    closed(request["prerequisites"], {"quota", "pricing", "network", "requirements", "exclusive_name_authority"}, "Prerequisites")
    for key, value in request["prerequisites"].items():
        if key == "exclusive_name_authority" and request["action"] == "reuse" and value is None:
            continue
        field = f"prerequisites.{key}"
        if value is None or isinstance(value, str) and not value.strip(" "):
            raise failure("bootstrap-prerequisite-missing", f"{field} requires nonempty owner-verified evidence.")
        if not isinstance(value, str) or len(value) > 256:
            raise failure("bootstrap-prerequisite-invalid", f"{field} must be a string of 1-256 printable characters.")
        for position, character in enumerate(value, 1):
            if not character.isprintable():
                raise failure(
                    "bootstrap-prerequisite-invalid",
                    f"{field} contains non-printable U+{ord(character):04X} at character {position}; evidence values are withheld.",
                )
    closed(request["limits"], {"command_seconds", "wait_seconds", "wait_interval_seconds"}, "Limits")
    for key, ceiling in (("command_seconds", 60), ("wait_seconds", 900), ("wait_interval_seconds", 30)):
        if type(request["limits"][key]) is not int or not 1 <= request["limits"][key] <= ceiling:
            raise failure("bootstrap-input-invalid", "Select explicit bounded command and readiness limits.")
    private_directory(request["receipt_dir"])
    return request


def ids(request):
    group = "/subscriptions/" + request["subscription_id"] + "/resourceGroups/" + request["resource_group"]
    return group, group + "/providers/Microsoft.Search/searchServices/" + request["name"]


def provider_id(request):
    return "/subscriptions/" + request["subscription_id"] + "/providers/Microsoft.Search"


def search_locations(value, expected_id):
    if (
        not isinstance(value, dict) or folded(value.get("id")) != expected_id.casefold()
        or folded(value.get("namespace")) != "microsoft.search"
        or not isinstance(value.get("resourceTypes"), list)
        or any(not isinstance(item, dict) or not isinstance(item.get("resourceType"), str)
               for item in value["resourceTypes"])
    ):
        raise failure("bootstrap-region-metadata-invalid", "Search provider metadata is incomplete or belongs to another subscription/provider.")
    services = [item for item in value["resourceTypes"] if folded(item["resourceType"]) == "searchservices"]
    if len(services) != 1:
        raise failure("bootstrap-region-metadata-invalid", "Exactly one Search searchServices resource type is required.")
    locations = services[0].get("locations")
    if (
        not isinstance(locations, list) or not 1 <= len(locations) <= 256
        or any(normalize_azure_location(location) is None for location in locations)
    ):
        raise failure("bootstrap-region-metadata-invalid", "Search supported locations are missing, malformed or exceed the bounded list.")
    return sorted({normalize_azure_location(location) for location in locations})


def desired(request, operation_id):
    # Only new planning normalizes choices; retained approved bodies keep their original representation.
    tags = dict(request["tags"])
    if request["action"] == "create":
        tags.update({"foundry-iq-owner": request["owner"], "foundry-iq-operation": operation_id})
    return {
        "location": request["location"], "tags": tags, "sku": {"name": request["sku"]},
        "identity": {"type": "SystemAssigned"},
        "properties": {"replicaCount": request["replicas"], "partitionCount": request["partitions"],
                       "publicNetworkAccess": "Enabled", "disableLocalAuth": True},
    }


def _json(raw):
    if len(raw) > MAX_BYTES:
        raise failure("bootstrap-cli-output-limit", "CLI response exceeds its bound.")
    try:
        value = json.loads(raw.decode("utf-8"))
        json.dumps(value, allow_nan=False)
        if not isinstance(value, dict) or value.get("nextLink") or value.get("nextToken"):
            raise ValueError("Not a complete object")
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise failure("bootstrap-response-invalid", "CLI must return one complete JSON object; empty or truncated output is not evidence.") from exc


def _error(raw):
    """Only codes/UUIDs/reference IDs survive; arbitrary Azure messages are not safe receipts."""
    message = raw.decode("utf-8", errors="replace")
    code_match = re.search(r'"code"\s*:\s*"([A-Za-z][A-Za-z0-9_.-]{0,100})"|(?:ERROR:\s*)?\(([A-Za-z][A-Za-z0-9_.-]{0,100})\)', message)
    code = next((g for g in code_match.groups() if g), None) if code_match else "bootstrap-cli-failed"
    request_match = re.search(r"request[\s-]?id[\"'\s:]+([0-9a-f-]{36})", message, re.I)
    request_id = request_match.group(1).lower() if request_match and GUID.fullmatch(request_match.group(1).lower()) else None
    status_match = re.search(r'"status(?:Code)?"\s*:\s*(4\d\d|5\d\d)', message)
    status = int(status_match.group(1)) if status_match else None
    reason = re.match(r"(?:ERROR:\s*)?([A-Za-z ]+)\(", message.strip())
    if status is None and reason:
        status = {"Bad Request": 400, "Unauthorized": 401, "Forbidden": 403, "Not Found": 404,
                  "Conflict": 409, "Too Many Requests": 429, "Internal Server Error": 500,
                  "Service Unavailable": 503, "Gateway Timeout": 504}.get(reason.group(1))
    references = sorted(set(POLICY_ID.findall(message)))
    implicated = code == "RequestDisallowedByPolicy" or bool(references) or '"PolicyViolation"' in message
    result = failure(code, "Azure CLI failed; untrusted original message text is withheld from output and receipts.")
    result.request_id, result.http_status = request_id, status
    result.policy_ids = references[:8]
    result.policy_implicated = implicated
    result.message_digest = digest(message)
    result.policy_overflow = len(references) > 8
    return result


def projection(resource, required_tags=()):
    """Store selected configuration, not arbitrary provider fields/error text."""
    if resource is None:
        return None
    props, identity = resource.get("properties", {}), resource.get("identity", {})
    if not isinstance(props, dict) or not isinstance(identity, dict):
        raise failure("bootstrap-response-invalid", "Search properties and identity must be objects.")
    tags = resource.get("tags")
    selected = {k.casefold() for k in required_tags}
    return {
        "id": resource.get("id"), "location": resource.get("location"),
        "tags": {k: v for k, v in tags.items() if folded(k) in selected} if isinstance(tags, dict) else tags,
        "sku": {"name": resource["sku"].get("name")} if isinstance(resource.get("sku"), dict) else resource.get("sku"),
        "identity": {k: identity.get(k) for k in ("type", "principalId", "tenantId")},
        "properties": {k: props.get(k) for k in (
            "replicaCount", "partitionCount", "publicNetworkAccess", "disableLocalAuth",
            "provisioningState", "status", "endpoint",
        )},
    }


def matching(resource, request, body):
    value = projection(resource, body["tags"])
    tags = resource.get("tags") if resource is not None else None
    if tags is None and not body["tags"]:
        tags = {}
    group, target = ids(request)
    location = normalize_azure_location(body["location"])
    if (
        value is None or not isinstance(value["id"], str) or value["id"].casefold() != target.casefold()
        or location is None or normalize_azure_location(value["location"]) != location
        or not isinstance(tags, dict)
        or any([v for k, v in tags.items() if folded(k) == key.casefold()] != [expected]
               for key, expected in body["tags"].items())
        or not isinstance(value["sku"], dict) or folded(value["sku"].get("name")) != body["sku"]["name"]
        or folded(value["identity"]["type"]) != "systemassigned"
        or any(type(value["properties"][k]) is not type(v) or (
            folded(value["properties"][k]) != v.casefold() if isinstance(v, str) else value["properties"][k] != v
        ) for k, v in body["properties"].items())
    ):
        raise failure("bootstrap-state-conflict", "Selected Search definition differs; shared or foreign state will not be modified.")
    props = resource["properties"]
    if props.get("authOptions") not in (None, {}) or resource["identity"].get("userAssignedIdentities") not in (None, {}):
        raise failure("bootstrap-state-conflict", "Observed authentication configuration is not the selected keyless system identity.")
    rules = props.get("networkRuleSet")
    if rules is not None and (not isinstance(rules, dict) or rules.get("ipRules") not in (None, [])
                              or (rules.get("bypass") is not None and folded(rules["bypass"]) != "none")):
        raise failure("bootstrap-state-conflict", "Additional network restrictions require the owning procedure.")
    if props.get("privateEndpointConnections") not in (None, []) or props.get("sharedPrivateLinkResources") not in (None, []):
        raise failure("bootstrap-state-conflict", "Private/shared network resources are outside this bootstrap slice.")
    return value


def folded(value):
    return value.casefold() if isinstance(value, str) else None


def reuse_binding(resource, request, body):
    if resource is None:
        return None
    value = ready(resource, request, body)
    if value is None:
        raise failure("bootstrap-not-ready", "Fresh Search readback does not establish ARM readiness.")
    return {"id": folded(value["id"]), "principal": folded(value["identity"]["principalId"]),
            "tenant": folded(value["identity"]["tenantId"])}


def ready(resource, request, body):
    return _readiness(resource, request, matching(resource, request, body))


def _readiness(resource, request, value):
    props = value["properties"]
    if folded(props["provisioningState"]) in ("failed", "canceled", "cancelled", "deleting", "deleted") or folded(props["status"]) in ("error", "degraded"):
        evidence = [resource.get("error"), resource["properties"].get("error"),
                    resource["properties"].get("statusDetails")]
        raw = "\n".join(value if isinstance(value, str) else json.dumps(value)
                        for value in evidence if isinstance(value, (str, dict, list)))
        error = _error(raw.encode("utf-8"))
        if error.code == "bootstrap-cli-failed":
            error.code = "bootstrap-provisioning-failed"
        error.message = "Search entered a failed, deleting or degraded ARM state; provider message text is withheld."
        error.args = (error.message,)
        error.creation_failure = True
        raise error
    if (
        folded(props["provisioningState"]) != "succeeded" or folded(props["status"]) != "running"
        or not text(folded(value["identity"]["principalId"]), GUID)
        or folded(value["identity"]["tenantId"]) != request["tenant_id"]
        or folded(props["endpoint"]) not in (
            "https://" + request["name"] + ".search.windows.net",
            "https://" + request["name"] + ".search.windows.net/",
        )
    ):
        return None
    return value


class Session:
    def __init__(self, request, operation_id, cli=run_cli, clock=time.monotonic, *, target=None):
        self.request, self.operation_id = request, operation_id
        self.cli, self.clock = cli, clock
        self.directory = private_directory(request["receipt_dir"])
        self.sequence = 0
        self.attempted = False
        self.approved = False
        self.owned = False
        self.warnings = []
        self.diagnosed = False
        self.policy_references = []
        self.target = target if target is not None else ids(request)[1]

    def record(self, event, value):
        self.sequence += 1
        private_file(self.directory, f"{self.operation_id}.{self.sequence:03d}.{uuid.uuid4().hex}.receipt.json", {
            "schema_version": "1.0", "operation_id": self.operation_id, "operation": "bootstrap-search",
            "target": self.target, "event": event, "evidence": value,
        })

    def call(self, args, timeout=None, mutation=False, waiting=False):
        self.record("command", {"argv": args})
        if mutation:
            self.attempted = True
        try:
            response = self.cli(
                args + ["--subscription", self.request["subscription_id"]],
                self.request["limits"]["wait_seconds"] if waiting else (
                    min(self.request["limits"]["command_seconds"], timeout) if timeout is not None else self.request["limits"]["command_seconds"]),
            )
        except HelperFailure as error:
            if mutation and error.code in ("bootstrap-tool-unavailable", "bootstrap-cli-start-failed"):
                self.attempted = False
            raise
        rc, stdout, stderr = response
        if len(stdout) > MAX_BYTES or len(stderr) > MAX_BYTES:
            raise failure("bootstrap-cli-output-limit", "CLI output exceeded its bound.")
        if rc:
            error = _error(stderr or stdout)
            try:
                self.record("failure", {"code": error.code, "status": error.http_status, "request_id": error.request_id,
                                        "message_digest": error.message_digest, "message_withheld": True,
                                        "policy_ids": error.policy_ids, "policy_references_limited": error.policy_overflow,
                                        "warnings": error.warnings})
            except HelperFailure:
                self.warnings.append("Original CLI failure could not be persisted; retain the returned failure and ownership.")
            raise error
        if waiting:
            if stdout.strip() not in (b"", b"null"):
                raise failure("bootstrap-wait-result-invalid", "Native wait returned an unexpected result; readiness is unresolved.")
            return None
        return _json(stdout)

    def get(self, timeout=None):
        try:
            result = self.call(["rest", "--method", "get", "--url",
                                "https://management.azure.com" + self.target + "?api-version=" + API], timeout)
        except HelperFailure as exc:
            if (exc.code == "ResourceNotFound" and exc.http_status in (None, 404)
                    and not getattr(exc, "cleanup_unconfirmed", False)):
                self.record("readback", {"id": self.target, "absence": "ResourceNotFound"})
                return None
            raise
        if not isinstance(result.get("id"), str) or result["id"].casefold() != self.target.casefold():
            raise failure("bootstrap-response-invalid", "ARM returned another identity.")
        self.record("readback", {"id": self.target, "digest": digest(result)})
        return result

    def account_context(self):
        account = self.call(["account", "show"])
        if (folded(account.get("id")) != self.request["subscription_id"] or folded(account.get("tenantId")) != self.request["tenant_id"]
                or folded(account.get("state")) != "enabled" or account.get("environmentName") != "AzureCloud"):
            raise failure("bootstrap-context-conflict", "Signed-in subscription/tenant is not the selected enabled context.")
        user = account.get("user")
        if not isinstance(user, dict) or not text(user.get("name")) or folded(user.get("type")) not in ("user", "serviceprincipal"):
            raise failure("bootstrap-context-conflict", "Signed-in principal evidence is missing or unsupported.")
        principal = folded(user["name"]) if text(folded(user["name"]), GUID) else user["name"]
        return {"id": folded(account["id"]), "tenantId": folded(account["tenantId"]), "environmentName": account["environmentName"],
                "user": {"name": principal, "type": folded(user["type"])}}

    def context(self):
        account = self.account_context()
        group = self.call(["group", "show", "--name", self.request["resource_group"]])
        props = group.get("properties")
        if (
            not isinstance(group.get("id"), str) or group["id"].casefold() != ids(self.request)[0].casefold()
            or not isinstance(props, dict) or folded(props.get("provisioningState")) != "succeeded"
        ):
            raise failure("bootstrap-group-not-ready", "The explicitly selected existing resource group must be ready.")
        context = {"account": digest(account), "group": digest({"id": folded(group["id"]), "ready": True})}
        self.record("context", {"account": account, "group_id": ids(self.request)[0], "group_digest": context["group"]})
        return context

    def regions(self, *, selected=None):
        identity = provider_id(self.request)
        value = self.call(["rest", "--method", "get", "--url",
                           "https://management.azure.com" + identity + "?api-version=" + PROVIDER_API])
        locations = search_locations(value, identity)
        self.record("search-regions", {"provider_id": identity, "resource_type": "searchServices",
                                       "api_version": PROVIDER_API, "digest": digest(value), "locations": locations})
        if selected is not None and normalize_azure_location(selected) not in locations:
            error = failure("bootstrap-region-unsupported", "Select an advertised Search region; no typo correction or deployment-capacity inference.")
            error.available_locations = locations
            raise error
        return locations

    def policy_evidence(self, original):
        if self.diagnosed or not getattr(original, "policy_implicated", False):
            return
        self.diagnosed = True
        end = self.clock() + 60
        queue = list(original.policy_ids)
        seen = set()
        self.warnings.append("Policy evidence is diagnostic only; cause/compliance remains unresolved for the policy owner.")
        scopes = {self.target.casefold(), ids(self.request)[0].casefold(), ("/subscriptions/" + self.request["subscription_id"]).casefold()}
        while queue and len(seen) < 8:
            identity = queue.pop(0)
            if identity.casefold() in seen:
                continue
            seen.add(identity.casefold())
            self.policy_references.append(identity)
            remaining = end - self.clock()
            if remaining <= 0:
                break
            scope, tail = re.split(r"/providers/Microsoft.Authorization/", identity, flags=re.I)
            if scope.casefold() not in scopes or "/" not in tail:
                self.warnings.append("Referenced policy scope is unsupported; hand off to the policy owner.")
                continue
            kind, name = tail.split("/", 1)
            if kind.casefold() == "policyassignments":
                args = ["policy", "assignment", "show", "--name", name, "--scope", scope]
            elif kind.casefold() == "policydefinitions" and scope.casefold() == ("/subscriptions/" + self.request["subscription_id"]).casefold():
                args = ["policy", "definition", "show", "--name", name]
            else:
                self.warnings.append("Referenced policy kind requires owner investigation.")
                continue
            try:
                value = self.call(args, remaining)
                if self.clock() >= end:
                    raise failure("bootstrap-policy-timeout", "Policy evidence arrived after the diagnostic budget.")
                if not isinstance(value.get("id"), str) or value["id"].casefold() != identity.casefold():
                    raise failure("bootstrap-policy-evidence-mismatch", "Policy read returned another identity.")
                # Values/rules can contain sensitive literals: retain identity, digest and
                # classification only; the policy owner reads the referenced object.
                properties = value.get("properties", value)
                if not isinstance(properties, dict):
                    raise failure("bootstrap-response-invalid", "Policy properties are malformed.")
                reference = properties.get("policyDefinitionId")
                if isinstance(reference, str) and POLICY_ID.fullmatch(reference):
                    queue.append(reference)
                self.record("policy-evidence", {"id": identity, "digest": digest(value),
                                                "referenced_definition_id": reference if isinstance(reference, str) and POLICY_ID.fullmatch(reference) else None,
                                                "enforcementMode": properties.get("enforcementMode") if properties.get("enforcementMode") in ("Default", "DoNotEnforce", "Enroll") else None,
                                                "interpretation": "unresolved"})
            except HelperFailure as secondary:
                self.warnings.append("Secondary policy diagnostic failed: " + secondary.code)
                self.warnings.extend(secondary.warnings)
        if queue or getattr(original, "policy_overflow", False) or not original.policy_ids:
            self.warnings.append("Policy references are missing or exceed this bounded collector; no truncated completeness claim.")

    def blocked(self, error):
        if self.attempted:
            error.partial = True
            error.writes = [{"operation": "PUT", "resource_id": self.target, "submission": "attempted-unverified"}]
            error.resources_remaining = [{"resource_id": self.target, "run_owned": self.owned,
                                          "cleanup": "separate consent and fresh ownership/children/roles required"}]
        error.warnings.extend(self.warnings)
        result = blocked_result(error, outcome="bootstrap-search", fingerprint=None, owner=self.request.get("owner"))
        if error.code == "bootstrap-region-unsupported" and hasattr(error, "available_locations"):
            result["available_locations"] = error.available_locations
        if result["status"] == "partial":
            result["approved_plan"] = {"confirmed": self.approved, "artifact_id": self.operation_id}
            result["attempted_writes"] = result.pop("completed_writes")
            result["completed_writes"] = []
            if not self.owned:
                result["resources_remaining"]["unverified"] = result["resources_remaining"]["run_owned"]
                result["resources_remaining"]["run_owned"] = []
        result["receipt_id"] = self.operation_id
        if self.diagnosed:
            result["policy_handoff"] = {"referenced_ids": self.policy_references, "complete": False,
                                       "next_step": "Policy owner investigates exact references; no correction or retry is approved."}
        return result


def discover_regions(request, *, cli=run_cli):
    closed(request, {"schema_version", "subscription_id", "tenant_id", "receipt_dir", "limits"}, "Region discovery")
    reject_secrets(request)
    closed(request["limits"], {"command_seconds"}, "Region discovery limits")
    if (
        request["schema_version"] != SCHEMA
        or not text(request["subscription_id"], GUID) or not text(request["tenant_id"], GUID)
        or type(request["limits"]["command_seconds"]) is not int
        or not 1 <= request["limits"]["command_seconds"] <= 60
    ):
        raise failure("bootstrap-input-invalid", "Select subscription/tenant and a 1-60 second region-discovery command limit.")
    session = Session(request, str(uuid.uuid4()), cli, target=provider_id(request))
    try:
        session.record("context", {"account": session.account_context()})
        locations = session.regions()
        return {"status": "discovered", "resource_type": "Microsoft.Search/searchServices",
                "available_locations": locations, "receipt_id": session.operation_id,
                "mutation_approval_required": False, "execution_required": False, "writes_performed": [],
                "verification": "Advertised region support only; not SKU, quota, capacity, models or residency approval."}
    except HelperFailure as error:
        return session.blocked(error)


def plan_request(request, *, cli=run_cli, clock=time.monotonic, execution_output=None):
    validate(request)
    request = copy.deepcopy(request)
    request["location"] = normalize_azure_location(request["location"])
    operation_id = str(uuid.uuid4())
    session = Session(request, operation_id, cli, clock)
    try:
        context = session.context()
        observed = session.get()
        body = desired(request, operation_id)
        if request["action"] == "create":
            if observed is not None:
                raise failure("bootstrap-state-conflict", "New intent requires exact-name absence; never overwrite or silently reuse.")
            session.regions(selected=request["location"])
            refreshed = session.get()
            if refreshed is not None:
                raise failure("bootstrap-state-drift", "Exact-name absence changed; creation is blocked.")
        else:
            binding = reuse_binding(observed, request, body)
            if binding is None:
                raise failure("bootstrap-not-ready", "Reuse requires a running, keyless Search service with identity readback.")
            refreshed = session.get()
            if reuse_binding(refreshed, request, body) != binding:
                raise failure("bootstrap-state-drift", "Selected Search identity changed; obtain fresh evidence.")
        artifact = {
            "operation": "bootstrap-search", "operation_id": operation_id, "created_at": int(time.time()),
            "choices": copy.deepcopy(request),
            "body": body, "before": {**context, "search": digest(observed)},
        }
        envelope = {"schema_version": SCHEMA, "plan": artifact,
                    "approval": {"confirmed": False, "fingerprint": digest(artifact)}}
        if execution_output is None:
            private_file(session.directory, operation_id + ".plan.json", envelope)
        else:
            try:
                from .private_artifacts import retain_execution_input
            except ImportError:
                from private_artifacts import retain_execution_input
            execution_artifact = retain_execution_input(envelope, execution_output)
        session.record("planned", {"body": body, "before": artifact["before"],
                                   "readback": projection(refreshed, body["tags"]), "run_owned": False})
        create = request["action"] == "create"
        if execution_output is not None:
            return {
                "status": "planned" if create else "reused", "artifact_id": operation_id,
                "execution_artifact": execution_artifact, "execution_required": create,
                "mutation_approval_required": create, "azure_mutation_performed": False,
                "local_filesystem": {"artifact_created": True, "receipts_created": True,
                                     "existing_files_changed": False},
                "summary": "Unapproved bootstrap artifact retained privately; review before separate approval.",
            }
        return {
            "status": "planned" if create else "reused", "artifact_id": operation_id,
            "execution_required": create, "mutation_approval_required": create,
            "approval_summary": {"action": request["action"], "resource_id": session.target,
                                 "location": request["location"], "sku": request["sku"],
                                 "replicas": request["replicas"], "partitions": request["partitions"],
                                 "network": "public; local authentication disabled; SystemAssigned",
                                 "tags": body["tags"], "prerequisites": {
                                     key: {"evidence_present": value is not None,
                                           "verification": "caller-attested; not helper-verified" if value is not None else "not required for reuse"}
                                     for key, value in request["prerequisites"].items()
                                 },
                                 "limits": request["limits"], "cleanup": "separate approval"},
            "verification": {"arm_readiness": "verified" if not create else "unverified",
                             "data_plane_access": "unverified", "ingestion": "unverified", "retrieval": "unverified"},
            "writes_performed": [], "run_owned": False,
            "observed_dependency": projection(refreshed, body["tags"]),
        }
    except HelperFailure as error:
        return session.blocked(error)


def validate_artifact(envelope):
    closed(envelope, {"schema_version", "plan", "approval"}, "Execution artifact")
    if envelope["schema_version"] != SCHEMA:
        raise failure("bootstrap-contract-version", "Regenerate the retained artifact with bootstrap schema 2.0; do not edit its checksum.")
    plan, approval = envelope["plan"], envelope["approval"]
    closed(plan, {"operation", "operation_id", "created_at", "choices", "body", "before"}, "Execution plan")
    closed(approval, {"confirmed", "fingerprint"}, "Approval")
    if (
        plan["operation"] != "bootstrap-search"
        or not text(plan["operation_id"], GUID) or type(approval["confirmed"]) is not bool
        or approval["fingerprint"] != digest(plan)
    ):
        raise failure("approval-mismatch", "Retain the unchanged planner artifact; integrity is checked internally.")
    validate(plan["choices"])
    if type(plan["created_at"]) is not int or not plan["created_at"] <= time.time() <= plan["created_at"] + 900:
        raise failure("bootstrap-artifact-expired", "Rerun planning; retained artifacts expire after fifteen minutes.")
    closed(plan["before"], {"account", "group", "search"}, "Before-state")
    if any(not text(v, HASH) for v in plan["before"].values()) or plan["body"] != desired(plan["choices"], plan["operation_id"]):
        raise failure("bootstrap-artifact-invalid", "Artifact body or before-state differs from generated choices.")
    return plan


@reporting("search-bootstrap")
def apply_artifact(envelope, *, approve=False, cli=run_cli, clock=time.monotonic, progress=None):
    progress.update("validation")
    plan = validate_artifact(envelope)
    if approve is not True:
        raise failure("approval-missing", "Explicit approval of the unchanged artifact is required before any execution reads or writes.")
    request = plan["choices"]
    if request["action"] != "create":
        raise failure("bootstrap-execution-unnecessary", "Read-only reuse needs fresh planning, not mutation approval or execution.")
    session = Session(request, plan["operation_id"], cli, clock)
    session.approved = True
    body = plan["body"]
    try:
        session.record("approved", {"plan": plan, "approval": {"confirmed": True, "fingerprint": digest(plan)}})
        progress.update("context-check")
        context = session.context()
        if context != {k: plan["before"][k] for k in ("account", "group")}:
            raise failure("bootstrap-state-drift", "Account/group changed; rerun planning and discard old consent.")
        progress.update("region-check")
        session.regions(selected=request["location"])
        progress.update("absence-check")
        if plan["before"]["search"] != digest(None) or session.get() is not None:
            raise failure("bootstrap-state-drift", "Exact-name absence changed; never overwrite or retry through another name.")
        body_path = private_file(session.directory, plan["operation_id"] + "." + uuid.uuid4().hex + ".body.json", body)
        command = ["rest", "--method", "put", "--url",
                   "https://management.azure.com" + session.target + "?api-version=" + API,
                   "--headers", "Content-Type=application/json", "x-ms-client-request-id=" + str(uuid.uuid4()),
                   "--body", "@" + str(body_path)]
        private_file(session.directory, plan["operation_id"] + ".submission.json",
                     {"operation_id": plan["operation_id"], "target": session.target, "body": body, "command": command})
        progress.update("search-submit")
        try:
            session.call(command, mutation=True)
        except HelperFailure as original:
            if not session.attempted:
                raise
            # Never retry PUT. Neither diagnostics nor a readback replaces the first error.
            progress.update("arm-readback")
            try:
                observed = session.get()
                if observed is not None:
                    matching(observed, request, body)
                    session.owned = True
                session.record("failure-reconciliation", {"readback": projection(observed, body["tags"]), "run_owned": session.owned})
                if (original.code in ("RequestDisallowedByPolicy", "AuthorizationFailed", "InvalidSkuName")
                        and observed is None and not getattr(original, "cleanup_unconfirmed", False)):
                    session.attempted = False
            except HelperFailure as secondary:
                session.warnings.append("Read-only reconciliation failed: " + secondary.code)
                session.warnings.extend(secondary.warnings)
            session.policy_evidence(original)
            raise original
        progress.update("arm-wait")
        try:
            session.call(["resource", "wait", "--ids", session.target, "--api-version", API,
                          "--custom", WAIT_CONDITION, "--interval", str(request["limits"]["wait_interval_seconds"]),
                          "--timeout", str(request["limits"]["wait_seconds"])], waiting=True)
        except HelperFailure as original:
            try:
                progress.update("arm-readback")
                observed = session.get()
                if observed is not None:
                    value = matching(observed, request, body)
                    session.owned = True
                    try:
                        _readiness(observed, request, value)
                    except HelperFailure as provider:
                        session.warnings.append("Terminal provider readback: " + provider.code)
                        session.record("terminal-provider-failure", {
                            "code": provider.code, "status": provider.http_status, "request_id": provider.request_id,
                            "message_digest": provider.message_digest, "message_withheld": True})
                        session.policy_evidence(provider)
                session.record("wait-failure-readback", {"readback": projection(observed, body["tags"]), "run_owned": session.owned})
            except HelperFailure as secondary:
                session.warnings.append("Wait failure readback failed: " + secondary.code)
                session.warnings.extend(secondary.warnings)
            raise original
        progress.update("arm-readback")
        observed = session.get()
        value = matching(observed, request, body) if observed is not None else None
        if value is not None:
            session.owned = True
            value = _readiness(observed, request, value)
        if value is None:
            raise failure("bootstrap-readiness-timeout", "Final ARM readiness was not established; preserve the resource and operation receipts.")
        session.record("arm-ready", {"readback": value, "run_owned": True})
        return {"status": "completed", "receipt_id": session.operation_id, "resource_id": session.target,
                "run_owned": True, "writes_performed": [{"operation": "PUT", "resource_id": session.target}],
                "observed_dependency": value,
                "verification": {"arm_readiness": "verified", "data_plane_access": "unverified",
                                 "ingestion": "unverified", "retrieval": "unverified"},
                "cleanup": "separate approval with fresh ownership/children/roles"}
    except HelperFailure as error:
        if session.attempted and getattr(error, "creation_failure", False):
            session.policy_evidence(error)
        return session.blocked(error)


def main(argv=None):
    try:
        from .private_artifacts import add_execution_output_argument, validate_execution_output_mode
    except ImportError:
        from private_artifacts import add_execution_output_argument, validate_execution_output_mode
    parser = argparse.ArgumentParser(description="Discover Search regions or plan/apply one selected service; no models, roles or cleanup.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", type=Path)
    mode.add_argument("--apply", type=Path)
    mode.add_argument("--regions", type=Path)
    parser.add_argument("--approve", action="store_true")
    add_execution_output_argument(parser)
    add_progress_argument(parser)
    args = parser.parse_args(argv)
    try:
        validate_execution_output_mode(args)
        if (args.plan or args.regions) and args.approve:
            raise failure("bootstrap-input-invalid", "Planning cannot approve mutations.")
        document = read_json(args.plan or args.apply or args.regions)
        result = (discover_regions(document) if args.regions else
                  plan_request(document, **({"execution_output": args.execution_output} if args.execution_output else {})) if args.plan else apply_artifact(
                      document, approve=args.approve, progress=Progress("search-bootstrap", enabled=args.progress)))
    except HelperFailure as error:
        result = blocked_result(error, outcome="bootstrap-search", fingerprint=None)
    emit_result(result)
    return 3 if result["status"] == "partial" else 2 if result["status"] == "blocked" else 0


if __name__ == "__main__":
    sys.exit(main())
