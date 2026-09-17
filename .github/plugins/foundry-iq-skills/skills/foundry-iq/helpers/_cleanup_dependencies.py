from __future__ import annotations

import inspect
import re
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

try:
    from ._common import HelperFailure, digest, odata_name, require_allowed_fields, sdk_error_metadata
except ImportError:
    from _common import HelperFailure, digest, odata_name, require_allowed_fields, sdk_error_metadata


COLLECTIONS = {"index": "indexes", "indexer": "indexers", "skillset": "skillsets", "datasource": "datasources"}
SHA = re.compile(r"sha256:[a-f0-9]{64}\Z")


def fail(code, message):
    return HelperFailure(code, message, blocked_at="cleanup-dependencies")


def limits(value=None):
    value = {"max_pages": 20, "max_resources": 500} if value is None else value
    if not isinstance(value, dict) or set(value) != {"max_pages", "max_resources"}:
        raise fail("input-schema-invalid", "Inventory limits require max_pages and max_resources.")
    if any(type(value[key]) is not int or not 1 <= value[key] <= maximum
           for key, maximum in (("max_pages", 100), ("max_resources", 5000))):
        raise fail("input-schema-invalid", "Inventory limits exceed supported bounded discovery.")
    return dict(value)


def generated(current):
    kind = current.get("kind")
    if kind not in ("file", "azureBlob"):
        raise fail("source-cleanup-kind-unsupported", "Only File and Blob/ADLS generated ownership is supported.")
    parameters = current.get("fileParameters" if kind == "file" else "azureBlobParameters")
    raw = parameters.get("createdResources") if isinstance(parameters, dict) else None
    required = {"index"} if kind == "file" else set(COLLECTIONS)
    if not isinstance(raw, dict):
        raise fail("generated-ownership-unproven", "The exact source must expose its generated resource identities.")
    names = {("datasource" if key == "dataSourceConnection" else key): value for key, value in raw.items()}
    if set(names) != required or len(names) != len(raw):
        raise fail("generated-ownership-unproven", "Unexpected, missing or colliding generated child identities.")
    for name in names.values():
        odata_name(name)
    return names


def validate_guard(plan):
    guard = plan.get("dependency_guard")
    if guard is None:
        return
    if not isinstance(guard, dict) or plan.get("operation") != "delete":
        raise fail("input-schema-invalid", "Dependency guards belong only to cleanup deletion plans.")
    kind = guard.get("kind")
    if kind == "search-source" and plan.get("resource_type") == "knowledge-source":
        fields, records, record_fields = (
            {"kind", "limits", "generated", "inventory_digest"},
            guard.get("generated"), {"type", "name", "etag", "definition_digest"},
        )
        if not isinstance(guard.get("inventory_digest"), str) or not SHA.fullmatch(guard["inventory_digest"]):
            raise fail("input-schema-invalid", "A complete scoped inventory digest is required.")
    elif kind == "prompt-connection" and isinstance(plan.get("connection"), dict):
        fields, records, record_fields = (
            {"kind", "limits", "versions", "toolboxes"}, guard.get("versions"), {"name", "version", "definition_digest"},
        )
        if not isinstance(guard.get("toolboxes"), list):
            raise fail("input-schema-invalid", "Complete toolbox version snapshots are required.")
        records = records + guard["toolboxes"] if isinstance(records, list) else records
    else:
        raise fail("input-schema-invalid", "Dependency guard and cleanup target must agree.")
    require_allowed_fields(guard, fields, label="Cleanup dependency guard")
    if set(guard) != fields or not isinstance(records, list):
        raise fail("input-schema-invalid", "The dependency snapshot must be complete.")
    bounds = limits(guard["limits"])
    if len(records) > bounds["max_resources"]:
        raise fail("input-schema-invalid", "The dependency snapshot exceeds approved limits.")
    identities = set()
    for record_index, record in enumerate(records):
        if not isinstance(record, dict) or set(record) != record_fields:
            raise fail("input-schema-invalid", "Dependency snapshot records are closed objects.")
        if any(not isinstance(value, str) or not value.strip() for value in record.values()):
            raise fail("input-schema-invalid", "Dependency snapshots require exact nonempty identities and versions.")
        if not SHA.fullmatch(record["definition_digest"]):
            raise fail("input-schema-invalid", "Dependency snapshots require canonical definition digests.")
        domain = "toolbox" if kind == "prompt-connection" and record_index >= len(guard["versions"]) else "agent"
        identity = (domain, record.get("type", record.get("version")), record["name"])
        if identity in identities:
            raise fail("input-schema-invalid", "Duplicate dependency snapshot identity.")
        identities.add(identity)
    if kind == "search-source":
        kinds = {record["type"] for record in records}
        if kinds not in ({"index"}, set(COLLECTIONS)) or len(kinds) != len(records):
            raise fail("input-schema-invalid", "Generated snapshots must identify one complete supported cascade.")


def _list_search(plan, collection, token, transport, bounds):
    base = f"{plan['endpoint'].rstrip('/')}/{collection}"
    url = base + "?" + urlencode({"api-version": plan["api_version"]})
    seen, names, records = set(), set(), []
    for _ in range(bounds["max_pages"]):
        if url in seen:
            raise fail("dependency-inventory-partial", "A continuation cycle prevents complete dependency discovery.")
        seen.add(url)
        response = transport("GET", url, token)
        body = response.body
        if response.status != 200:
            raise HelperFailure("dependency-inventory-failed", "Scoped collection GET failed; consumer absence is unproven.",
                                blocked_at="cleanup-dependencies", status=response.status, request_id=response.request_id)
        if not isinstance(body, dict) or not isinstance(body.get("value"), list):
            raise fail("dependency-inventory-invalid", "Scoped collection GET did not return a complete JSON page.")
        if set(body) - {"value", "@odata.nextLink", "@odata.context"}:
            raise fail("dependency-inventory-partial", "An unsupported pagination contract cannot prove absence.")
        for item in body["value"]:
            if not isinstance(item, dict):
                raise fail("dependency-inventory-invalid", "A dependency inventory item is not an object.")
            name = item.get("name")
            odata_name(name)
            if name in names:
                raise fail("dependency-inventory-changed", "Duplicate identities across inventory pages require fresh planning.")
            names.add(name)
            records.append(item)
            if len(records) > bounds["max_resources"]:
                raise fail("dependency-inventory-limit", "Complete scoped discovery exceeds the approved object bound.")
        next_link = body.get("@odata.nextLink")
        if next_link is None:
            return sorted(records, key=lambda item: item["name"])
        if len(records) >= bounds["max_resources"]:
            raise fail("dependency-inventory-limit", "More inventory pages exceed the approved object bound.")
        if not isinstance(next_link, str) or not next_link:
            raise fail("dependency-inventory-partial", "Malformed continuation is not an empty final page.")
        candidate = urljoin(base, next_link)
        parsed, expected = urlsplit(candidate), urlsplit(base)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if (
            parsed.scheme != expected.scheme or parsed.netloc != expected.netloc or parsed.path != expected.path
            or parsed.fragment or parsed.username or parsed.password
            or query.get("api-version") != [plan["api_version"]]
            or set(query) - {"api-version", "$skiptoken", "service", "pageSize", "search", "searchType"}
            or query.get("search", [""]) != [""]
            or ("service" in query and query["service"][0].casefold()
                not in {expected.hostname.casefold(), expected.hostname.split(".")[0].casefold()})
            or any(len(values) != 1 for values in query.values())
        ):
            raise fail("dependency-inventory-scope", "Continuation changed the selected service, collection, API or filter.")
        url = candidate
    raise fail("dependency-inventory-limit", "Complete dependency discovery exceeds the approved page bound.")


def _projections(skillset):
    projections = skillset.get("indexProjections")
    if projections is None:
        return []
    if not isinstance(projections, dict) or not isinstance(projections.get("selectors"), list):
        raise fail("dependency-inventory-invalid", "Skillset projection consumers are incomplete.")
    names = []
    for selector in projections["selectors"]:
        if not isinstance(selector, dict):
            raise fail("dependency-inventory-invalid", "A skillset projection selector is incomplete.")
        name = selector.get("targetIndexName")
        odata_name(name)
        names.append(name)
    return names


def search_snapshot(plan, current, token, *, transport, bounds):
    try:
        from . import search_reconcile
    except ImportError:
        import search_reconcile
    names = generated(current)
    inventories = {}
    bases = _list_search(plan, "knowledgebases", token, transport, bounds)
    inventories["knowledgebases"] = bases
    for base in bases:
        sources = base.get("knowledgeSources")
        if not isinstance(sources, list) or any(not isinstance(item, dict) or not isinstance(item.get("name"), str) for item in sources):
            raise fail("dependency-inventory-invalid", "Every KB definition must expose its complete source references.")
        if any(item["name"] == plan["name"] for item in sources):
            raise HelperFailure(
                "source-in-use", "A retained KB still references this source; separately plan that KB first, never detach it.",
                blocked_at="cleanup-dependencies", warnings=["referencing-kb:" + base["name"]],
            )
    sources = _list_search(plan, "knowledgesources", token, transport, bounds)
    inventories["knowledgesources"] = sources
    if sum(item["name"] == plan["name"] for item in sources) != 1:
        raise fail("dependency-inventory-changed", "The selected source disappeared from the complete service inventory.")
    for source in sources:
        if source["name"] == plan["name"]:
            if generated(source) != names or source.get("@odata.etag") != current.get("@odata.etag"):
                raise fail("definition-drift", "Source inventory and exact readback disagree.")
            continue
        if source.get("kind") == "searchIndex":
            parameters = source.get("searchIndexParameters")
            index = parameters.get("searchIndexName") if isinstance(parameters, dict) else None
            if not isinstance(index, str):
                raise fail("dependency-inventory-invalid", "An existing-index source has unknown target identity.")
            shared = index == names["index"]
        elif source.get("kind") in ("file", "azureBlob"):
            other = generated(source)
            shared = any(other.get(kind) == name for kind, name in names.items())
        else:
            raise fail("dependency-consumer-opaque", "An unsupported source kind prevents complete generated-index consumer proof.")
        if shared:
            raise fail("generated-resource-shared", "Another knowledge source references a generated cleanup resource.")
    indexers = _list_search(plan, "indexers", token, transport, bounds)
    inventories["indexers"] = indexers
    for indexer in indexers:
        if not all(isinstance(indexer.get(key), str) for key in ("dataSourceName", "targetIndexName")):
            raise fail("dependency-inventory-invalid", "Indexer dependency identities are incomplete.")
        if indexer.get("skillsetName") is not None and not isinstance(indexer["skillsetName"], str):
            raise fail("dependency-inventory-invalid", "Indexer skillset identity is malformed.")
        if indexer["name"] == names.get("indexer"):
            if any(indexer.get(field) != names[kind] for field, kind in (
                ("dataSourceName", "datasource"), ("targetIndexName", "index"), ("skillsetName", "skillset"),
            )):
                raise fail("definition-drift", "The generated indexer no longer binds the exact owned pipeline.")
        elif any(indexer.get(field) == names[kind] for field, kind in (
            ("dataSourceName", "datasource"), ("targetIndexName", "index"), ("skillsetName", "skillset"),
        ) if kind in names):
            raise fail("generated-resource-shared", "Another indexer consumes a generated cleanup resource.")
    skillsets = _list_search(plan, "skillsets", token, transport, bounds)
    inventories["skillsets"] = skillsets
    for skillset in skillsets:
        if skillset["name"] == names.get("skillset"):
            if any(index != names["index"] for index in _projections(skillset)):
                raise fail("generated-resource-shared", "The generated skillset also serves an outside-plan index.")
            continue
        skills = skillset.get("skills")
        if not isinstance(skills, list) or any(not isinstance(skill, dict) or not isinstance(skill.get("@odata.type"), str) for skill in skills):
            raise fail("dependency-inventory-invalid", "Skillset consumers are incomplete.")
        if any(".Custom." in skill["@odata.type"] for skill in skills):
            raise fail("dependency-consumer-opaque", "Custom skill code has no complete native generated-resource consumer contract.")
        if names["index"] in _projections(skillset):
            raise fail("generated-resource-shared", "Another skillset projects into the generated index.")
    snapshots = []
    for kind, name in sorted(names.items()):
        url = f"{plan['endpoint'].rstrip('/')}/{COLLECTIONS[kind]}('{odata_name(name)}')?api-version={plan['api_version']}"
        child, _ = search_reconcile.read_resource(url, token, transport=transport)
        if child is None:
            raise fail("generated-resource-missing", "A generated child is missing; source absence alone cannot prove the remaining cascade.")
        etag = child.get("@odata.etag")
        if child.get("name") != name or not isinstance(etag, str) or not etag.strip():
            raise fail("generated-version-unavailable", "Every generated object requires an exact name and fresh ETag.")
        snapshots.append({"type": kind, "name": name, "etag": etag, "definition_digest": digest(child)})
    refreshed, _ = search_reconcile.read_resource(search_reconcile.resource_url(plan), token, transport=transport)
    if (refreshed is None or search_reconcile._definition(refreshed) != search_reconcile._definition(current)
            or refreshed.get("@odata.etag") != current.get("@odata.etag") or generated(refreshed) != names):
        raise fail("definition-drift", "The source changed during dependency discovery.")
    inventory_state = {
        kind: [
            {"name": item["name"], "etag": item.get("@odata.etag"),
             "definition": search_reconcile._definition(item),
             "generated": generated(item) if kind == "knowledgesources" and item.get("kind") in ("file", "azureBlob") else None}
            for item in items
        ]
        for kind, items in inventories.items()
    }
    return {"kind": "search-source", "limits": bounds, "generated": snapshots, "inventory_digest": digest(inventory_state)}


def verify_search(plan, current, token, *, transport):
    guard = plan["dependency_guard"]
    if search_snapshot(plan, current, token, transport=transport, bounds=guard["limits"]) != guard:
        raise fail("dependency-drift", "A generated ETag/definition or scoped dependency inventory changed after approval.")


def _paged(items, bounds):
    if not callable(getattr(items, "by_page", None)):
        raise fail("connection-consumer-api-unavailable", "SDK ItemPaged.by_page is required to prove complete project inventory.")
    pages = iter(items.by_page())
    if not hasattr(pages, "continuation_token"):
        raise fail("connection-consumer-api-unavailable", "SDK page continuation state is required for bounded complete discovery.")
    count = 0
    for _ in range(bounds["max_pages"]):
        try:
            page = next(pages)
        except StopIteration:
            return
        for item in page:
            count += 1
            if count > bounds["max_resources"]:
                raise fail("dependency-inventory-limit", "Project inventory exceeds the approved object bound.")
            yield item
        if pages.continuation_token is None:
            return
        if count >= bounds["max_resources"]:
            raise fail("dependency-inventory-limit", "More project pages exceed the approved object bound.")
    raise fail("dependency-inventory-limit", "Project inventory exceeds the approved page bound.")


def _connection_use(definition, plan, connection):
    if definition.get("kind") != "prompt":
        raise fail("connection-consumer-opaque", "Project inventory contains Hosted/workflow/external consumers; their runtime connection use is not enumerable here.")
    if set(definition) - {"rai_config", "kind", "model", "instructions", "temperature", "top_p", "reasoning",
                          "tools", "tool_choice", "text", "structured_inputs"}:
        raise fail("connection-consumer-opaque", "Unknown Prompt definition fields prevent complete consumer interpretation.")
    tools = definition.get("tools")
    if not isinstance(tools, list):
        raise fail("connection-consumer-opaque", "A Prompt version has no complete tool definition.")
    expected = f"{plan['project_resource_id']}/connections/{connection['name']}".casefold()
    uses = False
    for tool in tools:
        if not isinstance(tool, dict) or tool.get("type") != "mcp":
            raise fail("connection-consumer-opaque", "A non-MCP tool needs a verified native connection-consumer contract.")
        if (set(tool) - {"type", "name", "description", "tool_configs", "server_label", "server_url", "connector_id",
                         "authorization", "server_description", "headers", "allowed_tools", "require_approval",
                         "defer_loading", "project_connection_id"} or tool.get("connector_id") is not None):
            raise fail("connection-consumer-opaque", "Unknown tool fields or connector resolution cannot prove project-connection absence.")
        configurations = tool.get("tool_configs")
        if configurations is not None and (
            not isinstance(configurations, dict) or any(
                not isinstance(value, dict) or set(value) - {"pin", "additional_search_text"}
                or (value.get("pin") is not None and type(value["pin"]) is not bool)
                or (value.get("additional_search_text") is not None and not isinstance(value["additional_search_text"], str))
                for value in configurations.values()
            )
        ):
            raise fail("connection-consumer-opaque", "Tool configuration is not the documented visibility/search-only contract.")
        reference = tool.get("project_connection_id")
        if reference is None:
            if not isinstance(tool.get("server_url"), str):
                raise fail("connection-consumer-opaque", "An MCP tool lacks an explicit connection or server target.")
            continue
        if (not isinstance(reference, str) or not reference.strip() or reference != reference.strip()
                or any(character in reference for character in ("%", "?", "#", "{", "}", "\\", "\r", "\n", "\t"))):
            raise fail("connection-consumer-opaque", "An MCP connection reference is malformed.")
        if "/" in reference:
            try:
                from .prompt_connect import PROJECT_ID
            except ImportError:
                from prompt_connect import PROJECT_ID
            project, _, leaf = reference.rstrip("/").casefold().rpartition("/connections/")
            if PROJECT_ID.fullmatch(project) is None or not leaf or "/" in leaf:
                raise fail("connection-consumer-opaque", "An MCP reference is neither a project connection name nor an exact ARM ID.")
            uses |= reference.rstrip("/").casefold() == expected
        else:
            uses |= reference.casefold() == connection["name"].casefold()
    return uses


def prompt_snapshot(plan, current, *, sdk_loader, bounds, allow_selected=True):
    properties = current.get("properties")
    if not isinstance(properties, dict) or properties.get("isSharedToAll") is not False or properties.get("sharedUserList") not in (None, []):
        raise fail("connection-sharing-unverified", "Shared/unknown connection scope requires account/external consumer enumeration, not project-only inventory.")
    AIProjectClient, _, _, _, extras = sdk_loader()
    AzureCliCredential, AzureError = extras
    client = AIProjectClient(endpoint=plan["project_endpoint"], credential=AzureCliCredential())
    selected = plan.get("agent")
    selected_id = (selected["name"], selected["version"]) if selected else None
    versions, toolboxes, names, identities = [], [], set(), set()
    try:
        if "include_drafts" not in inspect.signature(client.agents.list_versions).parameters:
            raise fail("connection-consumer-api-unavailable", "agents.list_versions(include_drafts=True) is required; this SDK cannot prove draft-consumer absence.")
        for agent in _paged(client.agents.list(), bounds):
            name = getattr(agent, "name", None)
            if not isinstance(name, str) or not name or name in names:
                raise fail("dependency-inventory-changed", "Project agent inventory contains missing or duplicate identities.")
            names.add(name)
            for item in _paged(client.agents.list_versions(agent_name=name, include_drafts=True), bounds):
                version = str(getattr(item, "version", ""))
                identity = (name, version)
                if not re.fullmatch(r"[1-9][0-9]*", version) or identity in identities:
                    raise fail("dependency-inventory-changed", "Version inventory contains missing or duplicate identities.")
                identities.add(identity)
                if len(identities) > bounds["max_resources"]:
                    raise fail("dependency-inventory-limit", "Total project versions exceed the approved object bound.")
                observed = client.agents.get_version(agent_name=name, agent_version=version)
                definition = observed.definition.as_dict()
                if observed.name != name or str(observed.version) != version or not isinstance(definition, dict):
                    raise fail("dependency-inventory-changed", "Exact version readback disagrees with project inventory.")
                uses = _connection_use(definition, plan, plan["connection"])
                if identity == selected_id and digest(definition) != selected["owned_definition_digest"]:
                    raise fail("definition-drift", "The explicitly selected version changed during consumer discovery.")
                if identity == selected_id and not allow_selected:
                    raise fail("agent-absence-unverified", "The selected version must be absent before connection deletion.")
                if uses and identity != selected_id:
                    raise HelperFailure(
                        "connection-shared-consumer", "A retained agent version consumes this connection.",
                        blocked_at="cleanup-dependencies", warnings=[f"consumer:{name}:{version}"],
                    )
                versions.append({"name": name, "version": version, "definition_digest": digest(definition)})
        names, identities = set(), set()
        for toolbox in _paged(client.toolboxes.list(), bounds):
            name = getattr(toolbox, "name", None)
            if not isinstance(name, str) or not name.strip() or name in names:
                raise fail("dependency-inventory-changed", "Toolbox inventory contains missing or duplicate names.")
            names.add(name)
            for item in _paged(client.toolboxes.list_versions(name=name), bounds):
                version = getattr(item, "version", None)
                identity = (name, version)
                if not isinstance(version, str) or not version.strip() or identity in identities:
                    raise fail("dependency-inventory-changed", "Toolbox version inventory is incomplete or duplicated.")
                identities.add(identity)
                if len(versions) + len(identities) > bounds["max_resources"]:
                    raise fail("dependency-inventory-limit", "Combined agent/toolbox versions exceed approved bounds.")
                observed = client.toolboxes.get_version(name=name, version=version)
                definition = observed.as_dict()
                if (not isinstance(definition, dict) or definition.get("name") != name
                        or definition.get("version") != version):
                    raise fail("dependency-inventory-changed", "Exact toolbox version disagrees with inventory.")
                if (set(definition) - {"metadata", "id", "name", "version", "description", "created_at", "tools", "skills", "policies"}
                        or definition.get("skills") not in (None, []) or definition.get("policies") not in (None, {})):
                    raise fail("connection-consumer-opaque", "Toolbox skills/policies have no complete connection-consumer contract.")
                if _connection_use({"kind": "prompt", "tools": definition.get("tools")}, plan, plan["connection"]):
                    raise HelperFailure(
                        "connection-shared-consumer", "A retained toolbox version consumes this connection.",
                        blocked_at="cleanup-dependencies", warnings=[f"toolbox-consumer:{name}:{version}"],
                    )
                toolboxes.append({"name": name, "version": version, "definition_digest": digest(definition)})
    except AzureError as exc:
        raise HelperFailure(message="Complete project agent/version GET inventory failed; absence is unproven.",
                            blocked_at="cleanup-dependencies", **sdk_error_metadata(exc, "connection-inventory-failed")) from exc
    except (AttributeError, TypeError, ValueError) as exc:
        raise fail("connection-consumer-api-unavailable", "The installed SDK lacks complete typed agent/version inventory readback.") from exc
    finally:
        client.close()
    return {"kind": "prompt-connection", "limits": bounds,
            "versions": sorted(versions, key=lambda item: (item["name"], item["version"])),
            "toolboxes": sorted(toolboxes, key=lambda item: (item["name"], item["version"]))}


def verify_prompt(plan, current, *, sdk_loader, allow_selected=True):
    connection = plan["connection"]
    if (digest(current) != connection["owned_definition_digest"]
            or (current.get("etag") or current.get("@odata.etag")) != connection["expected_etag"]):
        raise fail("definition-drift", "The connection definition or ETag changed after cleanup approval.")
    guard = plan["dependency_guard"]
    actual = prompt_snapshot(plan, current, sdk_loader=sdk_loader, bounds=guard["limits"], allow_selected=allow_selected)
    expected_versions = guard["versions"]
    selected = plan.get("agent")
    if selected and not any(item["name"] == selected["name"] and item["version"] == selected["version"] for item in actual["versions"]):
        expected_versions = [item for item in expected_versions if (item["name"], item["version"]) != (selected["name"], selected["version"])]
    if actual["versions"] != expected_versions or actual["toolboxes"] != guard["toolboxes"]:
        raise fail("dependency-drift", "Protected project agent/version definitions changed after cleanup approval.")
