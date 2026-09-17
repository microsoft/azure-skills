"""Intent-first Search selection and read-only operational reuse, never hardening."""
from __future__ import annotations

import argparse
import copy
import re
import time
from urllib.parse import quote

try:
    from ._bootstrap_io import failure, read_json, run_cli
    from ._common import (
        SEARCH_AUDIENCE, HelperFailure, digest, emit_result, normalize_azure_location,
        reject_secrets, require_allowed_fields, validate_search_endpoint,
    )
    from .bootstrap_azure import API
    from .model_discovery import GUID, Reader, identity_key, resource_group
    from .search_reconcile import SUPPORTED_API_VERSIONS
except ImportError:
    from _bootstrap_io import failure, read_json, run_cli
    from _common import (
        SEARCH_AUDIENCE, HelperFailure, digest, emit_result, normalize_azure_location,
        reject_secrets, require_allowed_fields, validate_search_endpoint,
    )
    from bootstrap_azure import API
    from model_discovery import GUID, Reader, identity_key, resource_group
    from search_reconcile import SUPPORTED_API_VERSIONS

# Azure service naming rules require both initial characters to be alphanumeric.
SERVICE_NAME = r"(?=.{2,60}$)[a-z0-9][a-z0-9]+(?:-[a-z0-9]+)*"
SERVICE_ID = re.compile(
    rf"/subscriptions/({GUID})/resourceGroups/([^/]+)/providers/Microsoft\.Search/searchServices/([a-z0-9-]{{2,60}})",
    re.I | re.ASCII,
)
INTENTS = ("use-existing", "find-candidates", "create-new")
PROJECTION = "[].{id:id,name:name,location:location}"
TIERS = {"free": "free", "basic": "basic", "serverless": "serverless",
         **{sku: "dedicated" for sku in ("standard", "standard2", "standard3",
                                        "storage_optimized_l1", "storage_optimized_l2")}}


def fail(code, message):
    return failure("search-" + code, message)


def service_id(value):
    match = SERVICE_ID.fullmatch(value) if isinstance(value, str) else None
    return match if match and resource_group(match[2]) and re.fullmatch(SERVICE_NAME, match[3].lower()) else None


def operation_requirements(value):
    """Derive outbound MI from chosen helper inputs, never from a hardening profile."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise fail("operation-invalid", "Supply the chosen operation, not a compatibility attestation.")
    kind = value.get("kind")
    if not isinstance(kind, str):
        raise fail("operation-invalid", "Select a named helper operation.")
    fields = {
        "service": {"kind", "api_version"},
        "file-source": {"kind", "api_version", "extraction_mode", "vectorization"},
        "blob-source": {"kind", "api_version", "extraction_mode", "vectorization"},
        "knowledge-base": {"kind", "api_version", "reasoning_effort", "output_mode"},
    }.get(kind)
    if (fields is None or set(value) != fields or not isinstance(value.get("api_version"), str)
            or value["api_version"] not in SUPPORTED_API_VERSIONS):
        raise fail("operation-unsupported", "Select exactly the supported helper operation and API fields.")
    mi = False
    if kind in ("file-source", "blob-source"):
        if value["extraction_mode"] not in ("minimal", "standard") or value["vectorization"] not in ("none", "azureOpenAI"):
            raise fail("operation-unsupported", "Preserve explicit extraction and embedding choices.")
        if (kind == "file-source" or value["extraction_mode"] == "standard") and value["api_version"] != "2026-08-01-preview":
            raise fail("operation-unsupported", "File and standard extraction require the supported preview API.")
        mi = kind == "blob-source" or value["vectorization"] == "azureOpenAI"
    elif kind == "knowledge-base":
        if value["reasoning_effort"] not in ("minimal", "low", "medium") or value["output_mode"] not in ("extractiveData", "answerSynthesis"):
            raise fail("operation-unsupported", "Keep KB reasoning/output separate from source embeddings and CU.")
        mi = value["reasoning_effort"] != "minimal" or value["output_mode"] == "answerSynthesis"
        if mi and value["api_version"] != "2026-08-01-preview":
            raise fail("operation-unsupported", "The selected KB model mode requires preview.")
    return mi


def validate(request):
    if not isinstance(request, dict) or request.get("schema_version") != "1.0":
        raise fail("input-invalid", "Supply a schema 1.0 Search intake object.")
    require_allowed_fields(request, {"schema_version", "intent", "service", "subscription_id",
                                    "resource_group", "source_region", "page", "operation"}, label="Search intake")
    reject_secrets(request)
    intent = request.get("intent")
    if intent is not None and intent not in INTENTS:
        raise fail("intent-invalid", "Choose USE EXISTING, FIND CANDIDATES or CREATE NEW.")
    sub, group = request.get("subscription_id"), request.get("resource_group")
    if sub is not None and (not isinstance(sub, str) or not re.fullmatch(GUID, sub)):
        raise fail("scope-invalid", "Select a subscription ID, never an account-wide scan.")
    if group is not None and not resource_group(group):
        raise fail("scope-invalid", "Select a valid resource group.")
    if type(request.get("page", 0)) is not int or not 0 <= request.get("page", 0) < 40:
        raise fail("page-invalid", "Select a zero-based presentation page below 40.")
    region = request.get("source_region")
    if region is not None and normalize_azure_location(region) is None:
        raise fail("region-invalid", "Use an observed source region, not location inferred from a name.")
    operation_requirements(request.get("operation"))
    locator, name, target = request.get("service"), None, None
    if locator is not None:
        match = service_id(locator)
        if match:
            target = locator
            if (sub and sub.lower() != match[1].lower()) or (group and identity_key(group) != identity_key(match[2])):
                raise fail("scope-conflict", "Explicit scope disagrees with the supplied Search ID; no context switch.")
            sub, group, name = match[1], match[2], match[3].lower()
        elif isinstance(locator, str) and re.fullmatch(SERVICE_NAME, locator):
            name = locator
        elif isinstance(locator, str) and locator.startswith("https://"):
            endpoint = validate_search_endpoint(locator)
            name = endpoint.removeprefix("https://").split(".")[0]
            if not re.fullmatch(SERVICE_NAME, name):
                raise fail("selector-invalid", "Supply a clean Search service root, name or ARM ID.")
        else:
            raise fail("selector-invalid", "Supply a clean Search service root, name or ARM ID.")
        intent = "create-new" if intent == "create-new" else "use-existing"
    if request.get("page", 0) and intent != "find-candidates":
        raise fail("page-invalid", "Presentation pages apply only to FIND CANDIDATES.")
    return intent, sub, group, name, target


def row(value, sub, group=None):
    match = service_id(value.get("id")) if isinstance(value, dict) else None
    if not match or match[1].lower() != sub.lower() or (group and identity_key(group) != identity_key(match[2])):
        raise fail("readback-mismatch", "Search inventory/readback escaped the selected scope.")
    name = value.get("name", match[3])
    if not isinstance(name, str) or name.lower() != match[3].lower():
        raise fail("readback-mismatch", "Search name and returned ID disagree.")
    location = normalize_azure_location(value.get("location"))
    if location is None:
        raise fail("readback-invalid", "Search region metadata is unresolved.")
    return {"resource_id": value["id"], "name": match[3].lower(),
            "resource_group": match[2], "location": location}


def get_service(reader, target, sub):
    try:
        value = reader.call(["rest", "--method", "get", "--url",
                             "https://management.azure.com" + quote(target, safe="/") + "?api-version=" + API,
                             "--subscription", sub])
    except HelperFailure as error:
        if error.code == "ResourceNotFound" and error.http_status in (None, 404):
            return None
        raise
    if not isinstance(value, dict) or identity_key(str(value.get("id", ""))) != identity_key(target):
        raise fail("readback-mismatch", "Exact ARM GET returned another Search identity.")
    return value


def operational_state(resource, sub, tenant, operation):
    observed = row(resource, sub)
    props = resource.get("properties")
    identity = resource.get("identity")
    if identity is None:
        identity = {}
    sku = resource.get("sku")
    if not isinstance(props, dict) or not isinstance(identity, dict) or not isinstance(sku, dict):
        raise fail("readback-invalid", "Require complete Search properties, SKU and identity metadata.")
    tier = TIERS.get(str(sku.get("name", "")).lower())
    if tier is None:
        raise fail("tier-unsupported", "The chosen helpers do not recognize this Search tier; no profile conversion.")
    if str(props.get("provisioningState", "")).lower() != "succeeded" or str(props.get("status", "")).lower() != "running":
        raise fail("not-ready", "The selected Search service is not running/succeeded; no replacement or repair.")
    endpoint = validate_search_endpoint(props.get("endpoint"))
    if endpoint.lower().rstrip("/") != "https://" + observed["name"] + ".search.windows.net":
        raise fail("endpoint-mismatch", "The Search endpoint does not match the selected resource.")
    observed.update(endpoint=endpoint, service_tier=tier, sku=sku["name"])
    if operation is not None:
        if str(props.get("publicNetworkAccess", "")).lower() != "enabled":
            raise fail("network-unsupported", "This path cannot establish private/perimeter reachability; preserve networking and use its owner.")
        auth = props.get("authOptions")
        both = isinstance(auth, dict) and isinstance(auth.get("aadOrApiKey"), dict)
        if props.get("disableLocalAuth") is not True and not both:
            raise fail("entra-unavailable", "Entra data-plane authentication is absent or unresolved; never retrieve keys or change authentication.")
        if operation_requirements(operation):
            types = {part.strip().lower() for part in str(identity.get("type", "")).split(",")}
            if "systemassigned" not in types:
                raise fail("outbound-identity-required", "This Blob/embedding/KB-chat path requires the existing Search system identity; UAMI selection is unsupported.")
            if not re.fullmatch(GUID, str(identity.get("principalId", ""))) or str(identity.get("tenantId", "")).lower() != tenant.lower():
                raise fail("outbound-identity-unverified", "Search system principal/tenant readback is unresolved for the selected outbound path.")
            observed["system_principal_id"] = identity["principalId"]
    material = {"observed": observed, "identity": identity,
                "access": {key: props.get(key) for key in ("disableLocalAuth", "authOptions",
                           "publicNetworkAccess", "networkRuleSet", "privateEndpointConnections")}}
    return observed, digest(material)


def select(request, *, cli=run_cli, clock=time.monotonic):
    result = {"schema_version": "1.0", "status": "blocked", "intent": None, "writes_performed": [], "candidates": [],
              "verification": {"caller_to_search": "unverified", "outbound_access": "unverified",
                               "operation_write_access": "unverified", "feature_region_support": "unverified"},
              "mutation_approval_required": False, "execution_required": False,
              "run_owned": False, "first_failure": None}
    try:
        intent, sub, group, name, target = validate(request)
        result["intent"] = intent
        if intent is None:
            result.update(status="intent-required", choices=list(INTENTS))
            return result
        if intent in ("use-existing", "create-new") and name is None:
            result["status"] = "service-required"
            return result
        if intent == "create-new" and group is None:
            result["status"] = "group-required"
            return result
        reader = Reader(cli, clock)
        context = reader.call(["account", "show"] + (["--subscription", sub] if sub else []))
        if (not isinstance(context, dict) or not re.fullmatch(GUID, str(context.get("id", "")))
                or not re.fullmatch(GUID, str(context.get("tenantId", "")))
                or (sub and context["id"].lower() != sub.lower())
                or context.get("environmentName") != "AzureCloud"
                or str(context.get("state", "")).lower() != "enabled"):
            raise fail("context-unavailable", "Require the selected enabled public Azure subscription/tenant; no context switch.")
        sub = context["id"]
        result["scope"] = {"subscription_id": sub, "resource_group": group}
        if target is None and name and group:
            target = f"/subscriptions/{sub}/resourceGroups/{group}/providers/Microsoft.Search/searchServices/{name}"
        if target is None:
            args = (["search", "service", "list", "--resource-group", group] if group else
                    ["resource", "list", "--resource-type", "Microsoft.Search/searchServices"])
            if name:
                args += ["--name", name]
            raw = reader.call(args + ["--subscription", sub, "--query", PROJECTION])
            if not isinstance(raw, list) or len(raw) > 200:
                raise fail("inventory-limit", "Inventory exceeds 200 rows or is malformed; narrow scope, never infer absence.")
            rows = [row(item, sub, group) for item in raw]
            if len({identity_key(item["resource_id"]) for item in rows}) != len(rows):
                raise fail("inventory-ambiguous", "Duplicate Search IDs make inventory ambiguous.")
            if name and any(item["name"] != name for item in rows):
                raise fail("readback-mismatch", "Exact-name resource lookup returned other names.")
            if name and len(rows) == 1:
                target, group = rows[0]["resource_id"], rows[0]["resource_group"]
            else:
                region = normalize_azure_location(request.get("source_region"))
                rows.sort(key=lambda item: (region is not None and item["location"] != region,
                                            identity_key(item["resource_id"])))
                start = request.get("page", 0) * 5
                if start and start >= len(rows):
                    raise fail("page-invalid", "This page is outside the current scoped inventory; do not infer absence.")
                for candidate in rows[start:start + 5]:
                    candidate["selection_input"] = dict(copy.deepcopy(request), intent="use-existing",
                                                        subscription_id=sub, resource_group=candidate["resource_group"],
                                                        service=candidate["resource_id"], page=0)
                result.update(status="candidate-choice-required" if rows else "no-candidates-in-scope",
                              candidates=rows[start:start + 5], total=len(rows),
                              remaining=max(0, len(rows) - start - 5), unassessed=len(rows),
                              inventory_complete=True,
                              warnings=["Metadata only; each page refreshes the complete bounded scope. No absence/uniqueness claim from the displayed subset. Region proximity is not compatibility."],
                              next_page=request.get("page", 0) + 1 if start + 5 < len(rows) else None)
                return result
        result["scope"]["resource_group"] = group
        result["selection_input"] = dict(copy.deepcopy(request), intent=intent, subscription_id=sub,
                                        resource_group=group, service=target, page=0)
        resource = get_service(reader, target, sub)
        if intent == "create-new":
            if resource is not None:
                raise fail("name-conflict", "CREATE NEW collided with existing Search; do not overwrite, reuse or suffix silently.")
            result.update(status="creation-plan-required", resource_id=target)
            return result
        if resource is None:
            raise fail("selected-resource-absent", "The supplied Search is absent in this exact scope; retain USE EXISTING intent.")
        operation = request.get("operation")
        observed, before = operational_state(resource, sub, context["tenantId"], operation)
        if operation is not None:
            stats = reader.call(["rest", "--method", "get", "--url", observed["endpoint"]
                                 + "/servicestats?api-version=" + operation["api_version"],
                                 "--resource", SEARCH_AUDIENCE, "--subscription", sub])
            if not isinstance(stats, dict) or not isinstance(stats.get("counters"), dict) or not isinstance(stats.get("limits"), dict):
                raise fail("readback-invalid", "Search statistics did not establish an authenticated metadata read.")
            refreshed = get_service(reader, target, sub)
            if refreshed is None or operational_state(refreshed, sub, context["tenantId"], operation)[1] != before:
                raise fail("state-drift", "Search identity/access changed during readback; refresh without changing configuration.")
            result["verification"]["caller_to_search"] = "service-statistics GET verified"
        result.update(status="selected", selected=observed, operation=copy.deepcopy(operation),
                      operation_required=operation is None,
                      warnings=["Selection/read access is not source/KB write permission, feature availability, outbound RBAC/network, ingestion or retrieval proof."])
    except HelperFailure as error:
        result.update(status="blocked", first_failure={"code": error.code, "message": error.message,
                                                      "status": error.http_status, "request_id": error.request_id})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--select", required=True)
    args = parser.parse_args(argv)
    try:
        result = select(read_json(args.select))
    except HelperFailure as error:
        result = {"schema_version": "1.0", "status": "blocked", "writes_performed": [],
                  "first_failure": {"code": error.code, "message": error.message}}
    emit_result(result)
    return 2 if result["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
