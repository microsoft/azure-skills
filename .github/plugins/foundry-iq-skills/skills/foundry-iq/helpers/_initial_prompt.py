"""Receipt-producing form of the existing local Foundry v1 create-agent fallback."""
from __future__ import annotations

import re
from urllib.parse import quote

try:
    from . import prompt_connect, _cleanup_dependencies as dependencies, _cleanup_receipts as receipts
    from ._common import HelperFailure, canonical_bytes, digest, reject_secrets, require_allowed_fields, sdk_error_status, sdk_error_metadata
except ImportError:
    import prompt_connect, _cleanup_dependencies as dependencies, _cleanup_receipts as receipts
    from _common import HelperFailure, canonical_bytes, digest, reject_secrets, require_allowed_fields, sdk_error_status, sdk_error_metadata


def fail(code, message):
    return HelperFailure(code, message, blocked_at="initial-prompt-creation")


def validate(plan):
    reject_secrets(plan)
    require_allowed_fields(plan, {"operation", "sdk_major", "project_resource_id", "project_endpoint",
                                 "agent", "owner", "cleanup_approved", "inventory_limits", "absence_inventory_digest",
                                 "prerequisites"}, label="Initial Prompt creation")
    prompt_connect._project_identity(plan)
    if (plan.get("operation") != "create-initial-prompt-agent" or plan.get("sdk_major") != 2
            or plan.get("cleanup_approved") is not False or not isinstance(plan.get("owner"), str) or not plan["owner"].strip()):
        raise fail("input-schema-invalid", "Initial Prompt creation needs separate approved creation intent and owner.")
    agent = plan.get("agent")
    if not isinstance(agent, dict) or set(agent) != {"name", "definition"}:
        raise fail("input-schema-invalid", "Select one exact initial agent name and complete definition.")
    if not isinstance(agent["name"], str) or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", agent["name"]):
        raise fail("input-schema-invalid", "Select a v1 agent name, never a suffix or latest.")
    definition = agent["definition"]
    if (not isinstance(definition, dict) or set(definition) != {"kind", "model", "instructions", "tools"}
            or definition["kind"] != "prompt" or not isinstance(definition["model"], str) or not definition["model"].strip()
            or not isinstance(definition["instructions"], str) or definition["tools"] != []):
        raise fail("input-schema-invalid", "Initial creation permits only an explicit Prompt model/instructions with no tools.")
    prerequisites = plan.get("prerequisites")
    if (not isinstance(prerequisites, dict) or set(prerequisites) != {"project", "model", "identity", "network"}
            or any(not isinstance(v, str) or not v.strip() for v in prerequisites.values())):
        raise fail("initial-prerequisites-unverified", "Retain the existing local-creation procedure's project/model/identity/network evidence.")
    dependencies.limits(plan.get("inventory_limits"))
    if not isinstance(plan.get("absence_inventory_digest"), str) or not dependencies.SHA.fullmatch(plan["absence_inventory_digest"]):
        raise fail("input-schema-invalid", "The complete scoped absence inventory must be fingerprinted.")


def absence(plan, sdk_loader):
    Client, _, _, _, extras = sdk_loader()
    Credential, AzureError = extras
    client = Client(endpoint=plan["project_endpoint"], credential=Credential())
    try:
        names = []
        for item in dependencies._paged(client.agents.list(), dependencies.limits(plan["inventory_limits"])):
            name = getattr(item, "name", None)
            if not isinstance(name, str) or not name.strip() or name in names:
                raise fail("initial-inventory-incomplete", "Agent absence needs a complete, unambiguous project inventory.")
            names.append(name)
        if plan["agent"]["name"] in names:
            raise fail("initial-agent-exists", "Retain the existing agent; return to Connect rather than creating a version.")
        try:
            client.agents.get(agent_name=plan["agent"]["name"])
        except AzureError as exc:
            if sdk_error_status(exc) == 404:
                return digest(sorted(names))
            raise
        raise fail("initial-agent-exists", "Exact agent GET found an existing identity.")
    except AzureError as exc:
        raise HelperFailure(message="Complete initial-agent absence discovery failed.", blocked_at="initial-prompt-creation",
                            **sdk_error_metadata(exc, "initial-inventory-failed")) from exc
    except (AttributeError, TypeError, ValueError) as exc:
        raise fail("initial-api-unavailable", "SDK complete agent listing and exact agent GET are required.") from exc
    finally:
        client.close()


def plan(request, sdk_loader):
    if not isinstance(request, dict):
        raise fail("input-schema-invalid", "Initial creation request must be a closed object.")
    require_allowed_fields(request, {"schema_version", "project_resource_id", "project_endpoint", "agent",
                                     "owner", "inventory_limits", "prerequisites"}, label="Initial Prompt request")
    if request.get("schema_version") != "1.0":
        raise fail("input-schema-invalid", "Initial request requires schema_version 1.0.")
    proposed = {k: v for k, v in request.items() if k != "schema_version"}
    proposed.update(operation="create-initial-prompt-agent", sdk_major=2, cleanup_approved=False,
                    inventory_limits=dependencies.limits(request.get("inventory_limits")),
                    absence_inventory_digest="sha256:" + "0" * 64)
    validate(proposed)
    proposed["absence_inventory_digest"] = absence(proposed, sdk_loader)
    fingerprint = digest(proposed)
    return {"status": "planned", "outcome": "create-initial-prompt-agent", "plan_fingerprint": fingerprint,
            "execution_required": True, "mutation_approval_required": True,
            "execution_input": {"schema_version": "1.0", "plan": proposed,
                                "approval": {"confirmed": False, "fingerprint": fingerprint}},
            "approval_summary": {"create": [proposed["agent"]["name"]], "retain": ["existing agents", "projects", "models", "grants"],
                                 "model_readiness": "Provided prerequisite evidence must be independently verified before approval.",
                                 "invocation": "not performed", "cleanup": "separate owned-version approval; container retained"}}


def verify_created(plan, target, birth, sdk_loader):
    Client, _, _, _, extras = sdk_loader()
    Credential, AzureError = extras
    client = Client(endpoint=plan["project_endpoint"], credential=Credential())
    try:
        agent = client.agents.get(agent_name=target["name"])
        if agent.name != target["name"]:
            raise fail("initial-readback-invalid", "Initial agent identity readback changed.")
        versions = [
            str(item.version) for item in dependencies._paged(
                client.agents.list_versions(agent_name=target["name"], include_drafts=True),
                dependencies.limits(plan["inventory_limits"]))
        ]
        if versions != [target["version"]]:
            raise fail("initial-version-inventory-changed", "Initial creation must retain exactly its acknowledged version, with no duplicates or unexpected versions.")
        current = client.agents.get_version(agent_name=target["name"], agent_version=target["version"])
        if (current.name != target["name"] or str(current.version) != target["version"]
                or current.definition.as_dict() != plan["agent"]["definition"]
                or receipts.version_identity(current) != birth):
            raise fail("definition-drift", "Exact initial version differs from its native birth snapshot.")
    except AzureError as exc:
        raise HelperFailure(message="Initial agent/version verification failed.", blocked_at="initial-prompt-creation",
                            **sdk_error_metadata(exc, "initial-readback-failed")) from exc
    except (AttributeError, TypeError, ValueError) as exc:
        raise fail("initial-api-unavailable", "Complete draft-inclusive agent/version readback is required.") from exc
    finally:
        client.close()


def execute(document, *, capture, token_provider, transport, sdk_loader):
    plan = document["plan"]
    validate(plan)
    if capture is None or capture.plan_digest != document["_computed_fingerprint"] or capture.owner != plan["owner"]:
        raise fail("cleanup-receipt-required", "Initial creation requires its original approved input and protected receipt directory.")
    if absence(plan, sdk_loader) != plan["absence_inventory_digest"]:
        raise fail("initial-inventory-drift", "Project inventory changed; replan rather than weakening absence protection.")
    token = token_provider("https://ai.azure.com/")
    url = plan["project_endpoint"].rstrip("/") + "/agents?api-version=v1"
    target = receipts.project_target(plan, "prompt-agent-version", name=plan["agent"]["name"], version="unverified")
    try:
        result = transport("POST", url, token, body=canonical_bytes(plan["agent"]), headers={"Content-Type": "application/json"})
    except HelperFailure as failure:
        if failure.http_status in (None, 408, 429) or (failure.http_status or 0) >= 500:
            failure.partial = True
            failure.warnings.append("Initial creation outcome unproven; no replay, ownership adoption or automatic cleanup.")
        raise
    write = {"action": "created", "type": "prompt-agent-version", "name": plan["agent"]["name"]}
    if result.status != 200:
        raise HelperFailure("initial-create-failed", "Create-agent returned an unexpected status; no replay or ownership adoption.",
                            blocked_at="initial-prompt-creation", status=result.status,
                            request_id=result.request_id, partial=(200 <= result.status < 300 or result.status in (408, 429) or result.status >= 500))
    try:
        if not isinstance(result.body, dict):
            raise fail("initial-create-response-invalid", "Foundry v1 create-agent did not return the documented HTTP 200 AgentObject.")
        versions = result.body.get("versions")
        latest = versions.get("latest") if isinstance(versions, dict) else None
        latest = latest if isinstance(latest, dict) else {}
        target["version"] = latest.get("version", "unverified")
        capture.start(target, {"operation": "agents.create", "status": result.status, "request_id": result.request_id,
                              "definition_digest": digest(latest.get("definition")), "version": target["version"],
                              "etag_evidence": None, "generated": None, "version_identity": receipts.version_identity(latest)})
        if (result.body.get("name") != plan["agent"]["name"] or latest.get("name") != plan["agent"]["name"]
                or not isinstance(target["version"], str) or not re.fullmatch(r"[1-9][0-9]*", target["version"])
                or latest.get("definition") != plan["agent"]["definition"] or receipts.version_identity(latest) is None):
            raise fail("initial-create-response-invalid", "Native created agent/version differs from approved initial intent.")
        write["version"] = target["version"]
        readback = transport("GET", plan["project_endpoint"].rstrip("/") + "/agents/" + quote(target["name"], safe="")
                             + "/versions/" + quote(target["version"], safe="") + "?api-version=v1", token)
        if (readback.status != 200 or not isinstance(readback.body, dict)
                or readback.body.get("name") != target["name"] or readback.body.get("version") != target["version"]
                or readback.body.get("definition") != latest["definition"]):
            raise fail("definition-drift", "Initial version readback differs from the original successful create-agent response.")
        verify_created(plan, target, receipts.version_identity(latest), sdk_loader)
        capture.finish(target, {"definition_digest": digest(latest["definition"]), "etag": None, "generated": [],
                                "version_identity": receipts.version_identity(readback.body)})
    except HelperFailure as failure:
        failure.partial = True
        failure.writes.insert(0, write)
        raise
    return {"status": "completed", "outcome": "create-initial-prompt-agent",
            "approved_plan": document["approval"], "resources": {"created": [target], "reused": []},
            "ownership": {"owner": plan["owner"], "run_owned": [target], "reused_not_owned": []},
            "agent_invocation": "not-run", "cleanup": "separate version-only approval; never delete the container"}
