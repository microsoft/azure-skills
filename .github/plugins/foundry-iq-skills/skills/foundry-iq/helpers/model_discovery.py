"""Bounded metadata-only model/CU intake; never a provisioning or readiness probe."""
from __future__ import annotations

import argparse
import json
import re
import time
from urllib.parse import parse_qs, quote, unquote, urlsplit

try:
    from ._bootstrap_io import MAX_BYTES, failure, read_json, run_cli
    from ._common import HelperFailure, canonical_bytes
    from .bootstrap_azure import _error
except ImportError:
    from _bootstrap_io import MAX_BYTES, failure, read_json, run_cli
    from _common import HelperFailure, canonical_bytes
    from bootstrap_azure import _error

API = "2024-10-01"
HOST = "https://management.azure.com"
GUID = r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
NAME = r"[A-Za-z0-9][A-Za-z0-9_.()-]{0,89}"
ACCOUNT = re.compile(
    rf"/subscriptions/({GUID})/resourceGroups/([^/]{{1,90}})"
    rf"/providers/Microsoft.CognitiveServices/accounts/({NAME})", re.I | re.ASCII
)
DEPLOYMENT = re.compile(ACCOUNT.pattern + rf"/deployments/({NAME})", ACCOUNT.flags)
ENDPOINT_SUFFIXES = {
    "embedding": ("openai.azure.com", "services.ai.azure.com", "cognitiveservices.azure.com"),
    "chat": ("openai.azure.com", "services.ai.azure.com", "cognitiveservices.azure.com"),
    "cu": ("services.ai.azure.com",),
}
LIMITS = {"pages": 10, "rows": 200, "endpoints": 10, "command_seconds": 20, "total_seconds": 120}
BOOLEAN_CAPABILITIES = ("embeddings", "chatCompletion")
# Public examples: https://github.com/Azure/azure-cli/blob/dev/src/azure-cli/azure/cli/command_modules/cognitiveservices/tests/latest/recordings/test_cognitiveservices_deployment.yaml
TOKEN_CAPABILITIES = ("maxContextToken", "maxOutputToken")
MAX_TOKEN_LIMIT = 2147483647
ACCOUNT_INVENTORY = "{id:id,name:name,kind:kind,location:location}"
ACCOUNT_METADATA = (
    "{id:id,name:name,kind:kind,location:location,properties:"
    "(type(properties) == 'object' && "
    "{endpoint:properties.endpoint,endpoints:((contains(keys(properties), 'endpoints') && "
    "[properties.endpoints] || [`{}`]) | [0]),"
    "provisioningState:properties.provisioningState} || `false`)}"
)


def capability_query():
    fields = []
    for key in BOOLEAN_CAPABILITIES:
        value = "properties.capabilities." + key
        # JMESPath 0.9.5 equates 1.0/0.0 with true/false; check types before equality.
        fields.append(f"{key}:((type({value}) == 'string' && {value} == 'true' || "
                      f"type({value}) == 'boolean' && {value} == `true`) && 'true' || "
                      f"(type({value}) == 'string' && {value} == 'false' || "
                      f"type({value}) == 'boolean' && {value} == `false`) && 'false' || `null`)")
    for key in TOKEN_CAPABILITIES:
        value = "properties.capabilities." + key
        number = f"to_number({value})"
        # Canonical decimal integers only; never echo a string based on its field name.
        fields.append(f"{key}:({number} > `0` && {number} <= `{MAX_TOKEN_LIMIT}` && "
                      f"to_string({number}) == to_string({value}) && "
                      f"!contains(to_string({number}), '.') && to_string({number}) || `null`)")
    return ("(type(properties.capabilities) == 'object' && {"
            + ",".join(fields) + "} || `{}`)")


DEPLOYMENT_METADATA = (
    "{id:id,name:name,properties:(type(properties) == 'object' && "
    "{model:((type(properties.model) == 'object' || !contains(keys(properties), 'model')) && "
    "{name:properties.model.name,version:properties.model.version,format:properties.model.format} || `false`),"
    "capabilities:" + capability_query() + ",provisioningState:properties.provisioningState} || `false`)}"
)
WARNINGS = [
    "Metadata candidates only: not CU defaults/configuration, capacity, effective RBAC, network or model-call proof.",
    "Only the selected/default subscription and optional group were searched; no cross-subscription discovery.",
    "Public Azure ARM only; bounded discovery is not proof of absence outside its scope.",
    "Missing/invalid purpose capabilities are unknown; selection is not model suitability.",
]


def invalid(message="Use exactly the documented discovery fields and selectors."):
    return failure("discovery-input-invalid", message)


def scalar(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_. ()/-]{1,256}", value):
        raise failure("discovery-readback-invalid", "Metadata text is missing or unsafe; raw values withheld.")
    return value


def public_capabilities(value):
    if not isinstance(value, dict):
        return {}
    projected = {}
    for key in BOOLEAN_CAPABILITIES:
        child = value.get(key)
        if type(child) is bool:
            projected[key] = "true" if child else "false"
        elif isinstance(child, str) and child in ("true", "false"):
            projected[key] = child
    for key in TOKEN_CAPABILITIES:
        child = value.get(key)
        if type(child) is int:
            child = str(child)
        if (isinstance(child, str) and re.fullmatch(r"[1-9][0-9]{0,9}", child)
                and int(child) <= MAX_TOKEN_LIMIT):
            projected[key] = child
    return projected


def safe_result(result):
    """Defend the public boundary as well as the CLI/input normalization boundary."""
    for row in result["deployments"]:
        row["capabilities"] = public_capabilities(row["capabilities"])
    if result["selected"] and result["selected"]["deployment"]:
        row = result["selected"]["deployment"]
        row["capabilities"] = public_capabilities(row["capabilities"])
    if len(canonical_bytes(result)) + 1 > MAX_BYTES:
        result.update(status="blocked", accounts=[], deployments=[], selected=None)
        result["first_failure"] = {
            "code": "discovery-limit", "status": None,
            "message": "Required output exceeds one MiB; supply resource_group or an exact ID. No absence conclusion.",
            "request_id": None, "message_digest": None,
        }
    return result


def resource_group(value):
    # Microsoft.Resources: Unicode letters/decimal digits and _-().; no final period.
    return (isinstance(value, str) and 1 <= len(value) <= 90 and not value.endswith(".")
            and all(c in "_-()." or c.isalpha() or c.isdecimal() for c in value))


def resource_match(value, *, deployment=False):
    pattern = DEPLOYMENT if deployment else ACCOUNT
    match = pattern.fullmatch(value) if isinstance(value, str) else None
    return match if match and resource_group(match.group(2)) else None


def identity_key(value):
    # Do not merge distinct Unicode names through multi-character folds (sharp-s -> ss).
    return "".join(folded if len(folded := c.casefold()) == 1 else c.lower() for c in value)


def origin(value, purpose):
    if not isinstance(value, str):
        return None
    suffixes = "|".join(re.escape(suffix) for suffix in ENDPOINT_SUFFIXES.get(purpose, ()))
    if suffixes and re.fullmatch(r"https://[a-z0-9][a-z0-9-]{0,62}\.(?:" + suffixes + r")/?", value):
        return value.rstrip("/")
    return None


def validate(request):
    keys = {"schema_version", "purpose", "subscription_id", "resource_group",
            "account_id", "account_name", "deployment"}
    if not isinstance(request, dict) or not keys <= set(request) or set(request) - keys - {"endpoint"}:
        raise invalid()
    if request["schema_version"] != "1.0" or request["purpose"] not in ("none", "embedding", "chat", "cu"):
        raise invalid()
    for field, pattern in (("subscription_id", GUID), ("account_name", NAME)):
        value = request[field]
        if value is not None and (not isinstance(value, str) or not re.fullmatch(pattern, value)):
            raise invalid()
    if request["resource_group"] is not None and not resource_group(request["resource_group"]):
        raise invalid()
    aid, deployment = request["account_id"], request["deployment"]
    if aid is not None and not resource_match(aid):
        raise invalid()
    if deployment is not None and (
        not isinstance(deployment, str) or not (re.fullmatch(NAME, deployment) or resource_match(deployment, deployment=True))
    ):
        raise invalid()
    if request["purpose"] in ("none", "cu") and deployment is not None:
        raise invalid()
    dep = resource_match(deployment, deployment=True)
    if dep:
        parent = deployment.rsplit("/", 2)[0]
        if aid and identity_key(aid) != identity_key(parent):
            raise invalid("Deployment and account selectors disagree.")
        aid = parent
    if aid:
        sub, group, name = resource_match(aid).groups()
        for field, observed in (("subscription_id", sub), ("resource_group", group), ("account_name", name)):
            if request[field] and identity_key(request[field]) != identity_key(observed):
                raise invalid("Explicit scope and exact resource selector disagree.")
    if request.get("endpoint") is not None and (
        not origin(request["endpoint"], request["purpose"])
        or not (aid or (request["account_name"] and request["resource_group"]))
    ):
        raise invalid("An endpoint selector requires a supported origin and an exact account selector.")
    return aid, dep.group(4) if dep else deployment


def endpoint(properties, purpose, selected=None):
    """Endpoint map keys are not a documented CU discriminator."""
    values = [("properties.endpoint", properties.get("endpoint"))]
    mapping = properties.get("endpoints", {})
    if not isinstance(mapping, dict):
        raise failure("discovery-readback-invalid", "ARM endpoints metadata is malformed.")
    values += [("properties.endpoints", value) for value in mapping.values()]
    candidates = {}
    for source, value in values:
        if value is None:
            continue
        if not isinstance(value, str):
            raise failure("discovery-readback-invalid", "ARM endpoint metadata is malformed.")
        # Match an observed origin only; never rewrite hosts, append paths or fetch it.
        normalized = origin(value, purpose)
        if normalized:
            candidates.setdefault(normalized, set()).add(source)
            if len(candidates) > LIMITS["endpoints"]:
                raise failure("discovery-limit", "More than ten supported endpoint origins; no partial choices.")
    choices = sorted(candidates)
    if selected is not None:
        value = origin(selected, purpose)
        if value not in candidates:
            return None, [], "endpoint-selection-not-observed", choices
    elif len(candidates) != 1:
        return None, [], "endpoint-missing-or-ambiguous", choices
    else:
        value = choices[0]
    return value, sorted(candidates[value]), "candidate-only", choices


class Reader:
    def __init__(self, cli, clock, *, aggregate=False):
        self.cli, self.clock, self.start = cli, clock, clock()
        self.page_count, self.row_count, self.byte_count = 0, 0, 0
        self.aggregate = aggregate

    def call(self, arguments):
        remaining = LIMITS["total_seconds"] - (self.clock() - self.start)
        if remaining <= 0:
            raise failure("discovery-limit", "Discovery deadline reached; narrow scope or supply an exact ID.")
        code, out, err = self.cli(arguments, min(LIMITS["command_seconds"], remaining))
        if len(out) > MAX_BYTES or len(err) > MAX_BYTES:
            raise failure("discovery-limit", "CLI output exceeded one MiB; narrow scope. No absence conclusion.")
        if code:
            raw = err or out
            error = _error(raw)
            match = re.search(r"request[\s-]?id[\"'\s:]+(" + GUID + ")",
                              raw.decode("utf-8", errors="replace"), re.I)
            if match:
                error.request_id = match.group(1)
            raise error
        self.byte_count += len(out) + len(err)
        if self.aggregate and self.byte_count > MAX_BYTES:
            raise failure("discovery-limit", "Aggregate CLI output exceeds one MiB; supply resource_group or an exact ID.")
        try:
            return json.loads(out)
        except (ValueError, UnicodeError, RecursionError):
            raise failure("discovery-readback-invalid", "CLI did not return valid JSON; no absence conclusion.")

    def get(self, path, sub, projection=ACCOUNT_METADATA):
        return self.call(["rest", "--method", "get", "--url", HOST + quote(path, safe="/") + "?api-version=" + API,
                          "--query", projection, "--subscription", sub])

    def pages(self, path, sub, projection=ACCOUNT_INVENTORY):
        encoded = quote(path, safe="/")
        url, rows, seen = HOST + encoded + "?api-version=" + API, [], set()
        # map preserves null/malformed entries and raw counts, unlike a filtering projection.
        projection_query = "{value:map(&" + projection + ",value),nextLink:nextLink}"
        while self.page_count < LIMITS["pages"]:
            if url in seen:
                raise failure("discovery-limit", "Repeated ARM page; discovery incomplete.")
            seen.add(url)
            self.page_count += 1
            result = self.call(["rest", "--method", "get", "--url", url,
                                "--query", projection_query, "--subscription", sub])
            if not isinstance(result, dict) or not isinstance(result.get("value"), list):
                raise failure("discovery-readback-invalid", "ARM listing is incomplete or malformed.")
            rows.extend(result["value"])
            self.row_count += len(result["value"])
            if self.row_count > LIMITS["rows"]:
                raise failure("discovery-limit", "More than 200 aggregate rows; supply resource_group or an exact ID.")
            url = result.get("nextLink")
            if not url:
                return rows
            if not isinstance(url, str):
                raise failure("discovery-readback-invalid", "ARM nextLink is malformed.")
            try:
                parts = urlsplit(url)
                decoded_path = unquote(parts.path, errors="strict")
            except (ValueError, UnicodeError):
                raise failure("discovery-readback-invalid", "ARM nextLink is malformed.")
            query = parse_qs(parts.query, keep_blank_values=True)
            if (any(ord(c) < 33 or ord(c) == 127 or c.isspace() for c in url)
                    or parts.scheme != "https" or parts.netloc != "management.azure.com"
                    or identity_key(decoded_path) != identity_key(path) or parts.fragment
                    or query.get("api-version") != [API]
                    or set(query) - {"api-version", "$skiptoken", "skiptoken"}):
                raise failure("discovery-scope-mismatch", "ARM nextLink escaped the selected collection; not followed.")
            url = HOST + encoded + "?" + parts.query
        raise failure("discovery-limit", "Ten aggregate pages reached; supply resource_group or an exact ID. No partial choices.")


def account_row(raw, sub, group, purpose, selected_endpoint=None, *, inventory=False):
    if not isinstance(raw, dict):
        raise failure("discovery-readback-invalid", "Account readback is malformed.")
    match = resource_match(raw.get("id"))
    if not match or match.group(1).casefold() != sub.casefold() or (
        group and identity_key(match.group(2)) != identity_key(group)
    ):
        raise failure("discovery-scope-mismatch", "Account readback does not match the selected scope.")
    if not isinstance(raw.get("name"), str) or raw["name"].casefold() != match.group(3).casefold():
        raise failure("discovery-readback-invalid", "Account name does not match its ARM ID.")
    kind = scalar(raw.get("kind"))
    if kind not in (("AIServices",) if purpose == "cu" else ("AIServices", "OpenAI")):
        return None
    props = {} if inventory else raw.get("properties", {})
    if not isinstance(props, dict):
        raise failure("discovery-readback-invalid", "Account properties are malformed.")
    uri, sources, state, candidates = endpoint(props, purpose, selected_endpoint)
    if inventory:
        state = "not-assessed"
    return {"account_id": raw["id"], "name": match.group(3), "resource_group": match.group(2),
            "location": scalar(raw.get("location")), "kind": kind,
            "provisioning_state": scalar(props.get("provisioningState")),
            "endpoint": uri, "endpoint_sources": sources, "endpoint_state": state,
            "endpoint_candidates": candidates, "selection_input": None}


def discover(request, *, cli=run_cli, clock=time.monotonic):
    result = {"schema_version": "1.0", "status": "blocked", "purpose": None, "scope": None,
              "accounts": [], "deployments": [], "selected": None,
              "limits": dict(LIMITS), "warnings": list(WARNINGS), "first_failure": None,
              "writes_performed": []}
    endpoint_unresolved = False
    try:
        aid, deployment = validate(request)
        result["purpose"] = purpose = request["purpose"]
        if purpose == "none":
            result.update(status="skipped", warnings=["Model-free route: zero CLI or Azure calls."])
            return result
        reader = Reader(cli, clock, aggregate=True)
        sub, group = request["subscription_id"], request["resource_group"]
        if aid:
            sub, group, _ = resource_match(aid).groups()
        if sub is None:
            context = reader.call(["account", "show", "--query", "{id:id}"])
            if not isinstance(context, dict) or not re.fullmatch(GUID, str(context.get("id", ""))):
                raise failure("discovery-context-unavailable", "No valid signed-in default subscription; no account scan.")
            sub = context["id"]
        result["scope"] = {"subscription_id": sub, "resource_group": group}
        name = request["account_name"]
        base = "/subscriptions/" + sub
        if group:
            base += "/resourceGroups/" + group
        if aid is None and name and group:
            aid = base + "/providers/Microsoft.CognitiveServices/accounts/" + name
        if aid is None:
            rows = reader.pages(base + "/providers/Microsoft.CognitiveServices/accounts", sub)
            accounts = [account_row(row, sub, group, purpose, inventory=True) for row in rows]
            accounts = [row for row in accounts if row and (not name or row["name"].casefold() == name.casefold())]
            for candidate in accounts:
                candidate["selection_input"] = dict(
                    request, subscription_id=sub, resource_group=candidate["resource_group"],
                    account_id=candidate["account_id"], account_name=candidate["name"],
                    endpoint=candidate["endpoint"])
            if len({identity_key(row["account_id"]) for row in accounts}) != len(accounts):
                raise failure("discovery-readback-invalid", "Duplicate account IDs; selection is ambiguous.")
            result["accounts"] = sorted(accounts, key=lambda row: identity_key(row["account_id"]))
            if not name or len(accounts) != 1:
                result["status"] = "account-choice-required" if accounts else "no-candidates"
                return safe_result(result)
            aid = accounts[0]["account_id"]
            group = accounts[0]["resource_group"]
        raw = reader.get(aid, sub)
        row = account_row(raw, sub, group, purpose, request.get("endpoint"))
        if row is None or identity_key(row["account_id"]) != identity_key(aid):
            raise failure("discovery-scope-mismatch", "Exact account is not a matching model/CU candidate.")
        result["accounts"] = [row]
        row["selection_input"] = dict(request, subscription_id=sub, resource_group=row["resource_group"],
                                      account_id=aid, account_name=row["name"],
                                      endpoint=row["endpoint"] or request.get("endpoint"))
        if row["endpoint"] is None:
            endpoint_unresolved = True
            raise failure("discovery-endpoint-unresolved",
                          "Resolve the endpoint using observed endpoint_candidates and selection_input; no deployment read, never guess.")
        if purpose == "cu":
            result.update(status="selected", selected={"account": row, "deployment": None})
            return safe_result(result)
        path = aid + "/deployments"
        raws = ([reader.get(path + "/" + deployment, sub, DEPLOYMENT_METADATA)] if deployment
                else reader.pages(path, sub, DEPLOYMENT_METADATA))
        for raw in raws:
            if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
                raise failure("discovery-readback-invalid", "Deployment metadata is malformed.")
            match = resource_match(raw["id"], deployment=True)
            if not match or identity_key(raw["id"].rsplit("/", 2)[0]) != identity_key(aid) or (
                deployment and match.group(4).casefold() != deployment.casefold()
            ):
                raise failure("discovery-scope-mismatch", "Deployment readback escaped the selected account/name.")
            if not isinstance(raw.get("name"), str) or raw["name"].casefold() != match.group(4).casefold():
                raise failure("discovery-readback-invalid", "Deployment name does not match its ARM ID.")
            props = raw.get("properties")
            if not isinstance(props, dict):
                raise failure("discovery-readback-invalid", "Deployment properties metadata is malformed.")
            model = props.get("model", {})
            if not isinstance(model, dict):
                raise failure("discovery-readback-invalid", "Deployment model metadata is malformed.")
            capabilities = public_capabilities(props.get("capabilities"))
            item = {"deployment_id": raw["id"], "name": match.group(4),
                    "model_name": scalar(model.get("name")), "model_version": scalar(model.get("version")),
                    "model_format": scalar(model.get("format")), "capabilities": capabilities,
                    "provisioning_state": scalar(props.get("provisioningState")),
                    "selection_input": dict(request, subscription_id=sub, resource_group=group,
                                           account_id=aid, account_name=row["name"], deployment=match.group(4),
                                           endpoint=row["endpoint"])}
            result["deployments"].append(item)
        result["deployments"].sort(key=lambda row: identity_key(row["deployment_id"]))
        if len({identity_key(row["deployment_id"]) for row in result["deployments"]}) != len(result["deployments"]):
            raise failure("discovery-readback-invalid", "Duplicate deployment IDs; selection is ambiguous.")
        if deployment:
            result.update(status="selected", selected={"account": row, "deployment": result["deployments"][0]})
        else:
            result["status"] = "deployment-choice-required" if raws else "no-candidates"
    except HelperFailure as exc:
        result.update(status="blocked", selected=None, deployments=[])
        if exc.code == "bootstrap-cli-output-limit":
            result["warnings"].append(
                "Required metadata exceeded discovery bounds; supply resource_group or an exact ID. No absence conclusion.")
        if not endpoint_unresolved:
            result["accounts"] = []
        result["first_failure"] = {"code": exc.code, "status": exc.http_status, "message": exc.message,
                                   "request_id": exc.request_id, "message_digest": getattr(exc, "message_digest", None)}
        result["warnings"].extend(exc.warnings)
    return safe_result(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    try:
        request = read_json(args.input)
    except HelperFailure as exc:
        result = discover({})
        result["first_failure"].update(code=exc.code, message=exc.message)
    else:
        result = discover(request)
    print(json.dumps(safe_result(result), sort_keys=True, separators=(",", ":")))
    return 2 if result["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
