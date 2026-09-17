from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

try:
    from . import prompt_cleanup, prompt_connect, search_reconcile, _cleanup_dependencies as dependencies, _cleanup_receipts as receipts
    from ._common import (
        SEARCH_AUDIENCE, MANAGEMENT_AUDIENCE, HelperFailure, TokenProvider, Transport, azure_cli_token,
        blocked_result, digest, emit_result, http_request, load_approved_input,
        reject_secrets, require_allowed_fields, sdk_error_metadata, sdk_error_status,
        validate_search_endpoint,
    )
except ImportError:
    import prompt_cleanup
    import prompt_connect
    import search_reconcile
    import _cleanup_dependencies as dependencies
    import _cleanup_receipts as receipts
    from _common import (
        SEARCH_AUDIENCE, MANAGEMENT_AUDIENCE, HelperFailure, TokenProvider, Transport, azure_cli_token,
        blocked_result, digest, emit_result, http_request, load_approved_input,
        reject_secrets, require_allowed_fields, sdk_error_metadata, sdk_error_status,
        validate_search_endpoint,
    )


RETAIN = [
    "outside-plan resources and consumers", "original local and Storage documents",
    "Search service", "accounts", "projects", "models", "role assignments",
]
REQUEST_FIELDS = {
    "schema_version", "owner", "target", "creation_input_file",
    "creation_result_file", "creation_response_file",
    "creation_receipt_file", "inventory_limits", "agent_version", "agent_creation_response_file", "agent_creation_receipt_file",
}
SEARCH_FIELDS = {"type", "endpoint", "api_version", "name"}
PROMPT_FIELDS = {"type", "project_resource_id", "project_endpoint", "name", "version"}
RESPONSE_FIELDS = {"schema_version", "target", "operation", "status", "request_id", "body", "generated_resources"}


def _failure(code: str, message: str) -> HelperFailure:
    return HelperFailure(code, message, blocked_at="cleanup-planning")


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _failure("input-schema-invalid", f"{label} must be an object.")
    return value


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _read_json(path: Path) -> dict[str, Any]:
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        json.dumps(result, allow_nan=False)
    except (OSError, UnicodeError, ValueError) as exc:
        raise _failure("input-unreadable", "Select readable retained UTF-8 JSON records.") from exc
    return _object(result, "Record")


def _target(value: Any) -> dict[str, Any]:
    target = copy.deepcopy(_object(value, "Cleanup target"))
    kind = target.get("type")
    if not isinstance(kind, str):
        raise _failure("target-selection-required", "Select one typed cleanup target.")
    if kind == "hosted":
        require_allowed_fields(target, {"type"}, label="Hosted cleanup target")
        raise _failure("hosted-cleanup-unsupported", "Hosted teardown remains unsupported; retain the deployment and toolbox.")
    if kind in {"knowledge-base", "knowledge-source"}:
        require_allowed_fields(target, SEARCH_FIELDS, label="Search cleanup target")
        search_reconcile.resource_url({**target, "resource_type": kind})
        target["endpoint"] = validate_search_endpoint(target["endpoint"])
    elif kind in {"prompt-agent-version", "project-connection"}:
        fields = PROMPT_FIELDS if kind == "prompt-agent-version" else PROMPT_FIELDS - {"version"}
        require_allowed_fields(target, fields, label="Prompt cleanup target")
        project_id, endpoint = prompt_connect._project_identity(target)
        target["project_resource_id"] = project_id.casefold()
        target["project_endpoint"] = endpoint
        if not _text(target.get("name")):
            raise _failure("target-selection-required", "Select one exact agent or connection name.")
        if kind == "prompt-agent-version" and (
            not isinstance(target.get("version"), str)
            or re.fullmatch(r"[1-9][0-9]*", target["version"]) is None
        ):
            raise _failure("target-selection-required", "Select one exact numeric Prompt version, not latest or a list.")
    else:
        raise _failure("target-selection-required", "Select one supported exact cleanup target.")
    return target


def _path(request: dict[str, Any], key: str, base_dir: Path) -> Path:
    value = request.get(key)
    if not _text(value):
        raise _failure("ownership-unproven", "Retained approval, result and definitive create response files are required.")
    path = Path(value)
    return path if path.is_absolute() else base_dir / path


def _records(
    request: dict[str, Any], target: dict[str, Any], base_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if "creation_receipt_file" in request:
        if target["type"] != "knowledge-source" or "creation_response_file" in request:
            raise _failure("input-schema-invalid", "Select either an original Blob checkpoint or native result/response records.")
        try:
            from . import blob_recheck
        except ImportError:
            import blob_recheck
        original = _read_json(_path(request, "creation_result_file", base_dir))
        reject_secrets(original)
        retained = original.get("recheck_checkpoint")
        if (original.get("outcome") != "create-blob-knowledge-source" or original.get("status") not in ("completed", "partial")
                or not isinstance(retained, dict) or retained.get("status") != "retained"):
            raise _failure(
                "generated-creation-evidence-unavailable",
                "Require the original creation result retaining its generated checkpoint; ACK/recovery GETs cannot prove original child versions.",
            )
        prior, receipt = blob_recheck._load(
            _path(request, "creation_input_file", base_dir), _path(request, "creation_receipt_file", base_dir),
        )
        if prior["source"]["action"] != "create" or prior["owner"] != request["owner"]:
            raise _failure("ownership-unproven", "Only an original run-owned creation checkpoint is eligible, never captured reuse.")
        original_ownership = _object(
            original.get("resources_remaining" if original["status"] == "partial" else "ownership"),
            "Original creation ownership",
        )
        original_owner = original.get("owner") if original["status"] == "partial" else original_ownership.get("owner")
        original_owned = original_ownership.get("run_owned")
        if (retained.get("evidence_digest") != receipt["integrity"]
                or retained.get("operation_id") != receipt["operation_id"]
                or original.get("approved_plan") != {"confirmed": True, "fingerprint": receipt["plan_digest"]}
                or original_owner != prior["owner"] or not isinstance(original_owned, list)
                or receipt["creation"]["ownership"]["run_owned"][0] not in original_owned):
            raise _failure("generated-ownership-unproven", "The original creation result must bind this exact checkpoint and approval; never substitute recovery snapshots.")
        result = {"status": "completed", **copy.deepcopy(receipt["creation"])}
        generated = receipt["creation"]["source"]["generated"]
        body = copy.deepcopy(prior["source"]["desired"])
        body["@odata.etag"] = receipt["creation"]["verification"]["readback"]["etag"]
        body["azureBlobParameters"]["createdResources"] = {item["type"]: item["name"] for item in generated}
        snapshots = [
            {"type": item["type"], "name": item["name"], "etag": receipt["configuration"][item["type"]]["etag"],
             "definition_digest": receipt["configuration"][item["type"]]["digest"]}
            for item in generated
        ]
        return prior, result, {"body": body, "_checkpoint_validated": True, "_generated_snapshots": snapshots}
    paths = [_path(request, field, base_dir) for field in (
        "creation_input_file", "creation_result_file", "creation_response_file",
    )]
    try:
        _, prior, fingerprint = load_approved_input(paths[0])
    except UnicodeError as exc:
        raise _failure("input-unreadable", "Retained approval must be UTF-8 JSON.") from exc
    result, response = _read_json(paths[1]), _read_json(paths[2])
    reject_secrets(result)
    reject_secrets(response)
    require_allowed_fields(response, RESPONSE_FIELDS, label="Definitive create response record")
    if (
        response.get("schema_version") != "1.0"
        or not _text(response.get("request_id"))
        or _target(response.get("target")) != target
    ):
        raise _failure("ownership-unproven", "Original create response must bind the exact scope and native request ID.")
    if (
        result.get("status") != "completed"
        or result.get("approved_plan") != {"confirmed": True, "fingerprint": fingerprint}
        or _object(result.get("ownership"), "Creation ownership").get("owner") != prior.get("owner")
        or prior.get("owner") != request["owner"]
    ):
        raise _failure("ownership-unproven", "Retained completed result, approval and accountable owner must agree.")
    _object(response.get("body"), "Create response body")
    return prior, result, response


def _owned_entry(result: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    identity = {key: target[key] for key in ("type", "name", "version") if key in target}

    def matches(item: Any) -> bool:
        return isinstance(item, dict) and all(item.get(key) == value for key, value in identity.items())

    resources = _object(result.get("resources"), "Creation resources")
    ownership = _object(result.get("ownership"), "Creation ownership")
    for container, keys in (
        (resources, ("created", "reused", "updated", "skipped")),
        (ownership, ("run_owned", "reused_not_owned")),
    ):
        for key in keys:
            if not isinstance(container.get(key, []), list):
                raise _failure("ownership-unproven", "Creation resource records must be complete lists.")
    created = [item for item in resources.get("created", []) if matches(item)]
    owned = [item for item in ownership.get("run_owned", []) if matches(item)]
    if (
        len(created) != 1 or len(owned) != 1 or created[0] != owned[0]
        or any(matches(item) for key in ("reused", "updated", "skipped") for item in resources.get(key, []))
        or any(matches(item) for item in ownership.get("reused_not_owned", []))
    ):
        raise _failure("ownership-unproven", "Only one definitively created run-owned resource is eligible; never reused or updated.")
    return created[0]


def _search_prior(prior: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    source = prior
    if prior.get("operation") in ("reconcile-and-ingest", "reconcile-and-monitor"):
        source = _object(prior.get("source"), "Prior source")
        if _object(source.get("desired"), "Prior source definition").get("kind") == "file":
            try:
                from . import file_source
            except ImportError:
                import file_source
            file_source._validate_plan(prior)
        else:
            try:
                from . import blob_source
            except ImportError:
                import blob_source
            blob_source._validate_plan(prior)
    search_reconcile._validate_plan(source)
    if (
        source.get("operation") != "reconcile" or source.get("action") != "create"
        or search_reconcile.resource_url(source) != search_reconcile.resource_url(
            {**target, "resource_type": target["type"]}
        )
    ):
        raise _failure("ownership-unproven", "Creation approval must select this exact source/base with action create.")
    return source


def _summary(target: dict[str, Any]) -> dict[str, Any]:
    is_agent = target["type"] == "prompt-agent-version"
    summary = {
        "delete": [copy.deepcopy(target)],
        "retain": RETAIN + (
            ["agent container", "prior and other agent versions", "project connection", "KB", "KS"]
            if is_agent else ["all KS and generated indexes/pipelines", "agent versions", "project connections"]
        ),
        "blocked": [],
        "order": ["Only this exact target; stop after failure. No dependent cleanup is chained."],
        "impact": (
            "The selected version and its tool binding become unavailable; the project connection remains."
            if is_agent else "The selected KB retrieval endpoint becomes unavailable; retained consumers are not detached."
        ),
        "ownership": "Original successful-create evidence required; owner metadata and equivalent GET are not proof or RBAC.",
        "approval": "Separate cleanup consent: change only approval.confirmed after review.",
        "hosted_cleanup": "unsupported",
    }
    if target["type"] == "knowledge-source":
        summary.update(
            retain=RETAIN + ["all KBs", "other KS/pipelines", "agent versions", "project connections"],
            impact="The selected source, its uploaded File copies/indexed content and exact generated objects are deleted; originals remain.",
            order=["Referencing KBs must already be absent or no longer reference this source; no detach is performed.",
                   "Delete only the source through Search; the service owns the exact approved cascade."],
        )
    elif target["type"] == "project-connection":
        summary.update(
            retain=RETAIN + ["agent containers", "prior/other agent versions", "KBs", "KS/pipelines"],
            impact="The selected project connection is removed; no retained agent version or tool is edited.",
            order=["Verify all consumers; delete and verify the explicitly selected owned version first, if any.",
                   "Rescan protected consumers and conditionally delete only this connection; stop on failure."],
        )
    return summary


def _original_generated(response):
    names = dependencies.generated(response["body"])
    if response.get("_checkpoint_validated") is True:
        snapshots = response["_generated_snapshots"]
    else:
        records = response.get("generated_resources")
        if not isinstance(records, list):
            raise _failure(
                "generated-creation-evidence-unavailable",
                "Original generated-object GET snapshots with ETags are required: source ETag and createdResources names "
                "cannot distinguish a replaced child. Use the retained Blob checkpoint or original generated-object audit records.",
            )
        snapshots = []
        for record in records:
            if not isinstance(record, dict) or set(record) != {"type", "body"}:
                raise _failure("input-schema-invalid", "Original generated records require type and complete native body.")
            if not isinstance(record["type"], str) or record["type"] not in names:
                raise _failure("generated-ownership-unproven", "Unexpected original generated resource type.")
            body = _object(record["body"], "Original generated body")
            snapshots.append({
                "type": record["type"], "name": body.get("name"), "etag": body.get("@odata.etag"),
                "definition_digest": digest(body),
            })
    if (
        len(snapshots) != len(names)
        or any(item.get("type") not in names or item.get("name") != names[item["type"]]
               or not _text(item.get("etag")) for item in snapshots)
        or len({item["type"] for item in snapshots}) != len(names)
    ):
        raise _failure("generated-ownership-unproven", "Original child snapshots must match the exact complete acknowledged cascade.")
    return sorted(snapshots, key=lambda item: item["type"])


def _absent(target: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    summary = _summary(target)
    summary["delete"] = []
    if target["type"] == "knowledge-source":
        summary["impact"] = "Source already absent; generated-object absence is unverified. No independent child deletion is authorized."
        summary["retain"].append("unverified generated objects")
    return {
        "status": "already-absent", "outcome": "plan-cleanup",
        "execution_required": False, "mutation_approval_required": False,
        "approval_summary": summary,
        "verification": {"absence": True, "request_ids": [request_id] if request_id else []},
    }


def _planned(
    target: dict[str, Any], plan: dict[str, Any], executor: str,
    retained_targets: list[dict[str, Any]],
) -> dict[str, Any]:
    fingerprint = digest(plan)
    summary = _summary(target)
    summary["retained_targets"] = retained_targets
    return {
        "status": "planned", "outcome": "plan-cleanup", "executor": executor,
        "execution_required": True, "mutation_approval_required": True,
        "plan_fingerprint": fingerprint,
        "execution_input": {
            "schema_version": "1.0", "plan": plan,
            "approval": {"confirmed": False, "fingerprint": fingerprint},
        },
        "approval_summary": summary,
    }


def _plan_search(
    request: dict[str, Any], target: dict[str, Any], prior: dict[str, Any],
    result: dict[str, Any], response: dict[str, Any], *,
    token_provider: TokenProvider, transport: Transport,
) -> dict[str, Any]:
    source = _search_prior(prior, target)
    owned = _owned_entry(result, target)
    body = response["body"]
    owned_digest = digest(search_reconcile._definition(body))
    etag = body.get("@odata.etag")
    if (
        (response.get("_checkpoint_validated") is not True and (
            response.get("operation") != "search-create" or type(response.get("status")) is not int or response["status"] != 201
        )) or not _text(etag)
        or body.get("name") != target["name"]
        or not search_reconcile.definitions_match(source["desired"], body)
        or owned.get("definition_digest") != owned_digest or owned.get("etag") != etag
    ):
        raise _failure("ownership-unproven", "Require the original HTTP 201 create body and matching retained owned readback, not GET recovery.")
    plan = {
        "operation": "delete", "outcome": "cleanup-search-resource", "plan_kind": "cleanup",
        "cleanup_approved": True, "owner": request["owner"],
        "resource_type": target["type"], "endpoint": target["endpoint"],
        "name": target["name"], "api_version": target["api_version"],
        "owned_definition_digest": owned_digest, "expected_etag": etag,
    }
    token = token_provider(SEARCH_AUDIENCE)
    current, request_id = search_reconcile.read_resource(search_reconcile.resource_url(plan), token, transport=transport)
    if current is None:
        return _absent(target, request_id)
    if (
        digest(search_reconcile._definition(current)) != owned_digest
        or current.get("@odata.etag") != etag
    ):
        raise _failure("definition-drift", "Current definition or creation ETag changed; same-name replacement is not owned.")
    if target["type"] == "knowledge-source":
        original = _original_generated(response)
        if dependencies.generated(current) != dependencies.generated(body):
            raise _failure("generated-ownership-unproven", "Generated identities differ from the acknowledged source creation.")
        snapshot = dependencies.search_snapshot(
            plan, current, token, transport=transport, bounds=dependencies.limits(request.get("inventory_limits")),
        )
        if snapshot["generated"] != original:
            raise _failure("generated-incarnation-drift", "Generated definitions/ETags differ from original retained ownership evidence.")
        plan["dependency_guard"] = snapshot
        search_reconcile._validate_plan(plan)
        planned = _planned(target, plan, "helpers/search_reconcile.py", [])
        planned["approval_summary"]["delete"].extend([
            {"type": item["type"], "name": item["name"], "endpoint": target["endpoint"], "service_managed": True}
            for item in original
        ])
        return planned
    reject_secrets(current)
    plan["desired"] = copy.deepcopy(current)
    search_reconcile._validate_plan(plan)
    retained = [
        {**target, "type": "knowledge-source", "name": source["name"]}
        for source in current["knowledgeSources"]
    ]
    return _planned(target, plan, "helpers/search_reconcile.py", retained)


def _plan_prompt(
    request: dict[str, Any], target: dict[str, Any], prior: dict[str, Any],
    result: dict[str, Any], response: dict[str, Any], *,
    sdk_loader: Callable[[], tuple[Any, Any, Any, Any, Any]],
) -> dict[str, Any]:
    prompt_connect._validate_plan(prior)
    owned = _owned_entry(result, target)
    prior_project, prior_endpoint = prompt_connect._project_identity(prior)
    body = response["body"]
    require_allowed_fields(body, {"name", "version", "definition", "id", "created_at"}, label="SDK create-version response")
    definition = _object(body.get("definition"), "Created Prompt definition")
    if (
        response.get("operation") != "agents.create_version" or response.get("status") != "succeeded"
        or prior_project.casefold() != target["project_resource_id"]
        or prior_endpoint != target["project_endpoint"]
        or prior["agent"]["name"] != target["name"] or prior["agent"]["version"] == target["version"]
        or body.get("name") != target["name"] or body.get("version") != target["version"]
        or definition.get("kind") != "prompt"
        or owned.get("definition_digest") != digest(definition)
        or receipts.version_identity(body) is None
    ):
        raise _failure("ownership-unproven", "Require the original successful SDK new-version return, never the baseline or recovered equivalent.")
    AIProjectClient, _, _, _, extras = sdk_loader()
    AzureCliCredential, AzureError = extras
    client = AIProjectClient(endpoint=target["project_endpoint"], credential=AzureCliCredential())
    try:
        try:
            current = client.agents.get_version(agent_name=target["name"], agent_version=target["version"])
        except AzureError as exc:
            if sdk_error_status(exc) == 404:
                return _absent(target, sdk_error_metadata(exc).get("request_id"))
            raise HelperFailure(
                message="Exact Prompt version readback failed; no inventory or deletion attempted.",
                blocked_at="cleanup-planning", **sdk_error_metadata(exc, "agent-readback-failed"),
            ) from exc
        try:
            actual = current.definition.as_dict()
            identity_matches = current.name == target["name"] and str(current.version) == target["version"]
        except (AttributeError, TypeError, ValueError) as exc:
            raise _failure("agent-readback-invalid", "Exact version readback is incomplete.") from exc
        if (not identity_matches or not isinstance(actual, dict) or digest(actual) != owned["definition_digest"]
                or receipts.version_identity(current) != receipts.version_identity(body)):
            raise _failure("definition-drift", "Exact Prompt version identity or definition changed.")
    finally:
        client.close()
    plan = {
        "operation": "delete", "outcome": "cleanup-prompt-version", "plan_kind": "cleanup",
        "cleanup_approved": True, "sdk_major": 2, "owner": request["owner"],
        "project_resource_id": target["project_resource_id"], "project_endpoint": target["project_endpoint"],
        "agent": {
            "name": target["name"], "version": target["version"], "run_owned": True,
            "owned_definition_digest": owned["definition_digest"],
            "owned_version_identity": receipts.version_identity(body),
        },
    }
    prompt_cleanup._validate_plan(plan)
    return _planned(target, plan, "helpers/prompt_cleanup.py", [
        {**target, "version": prior["agent"]["version"]},
        {
            "type": "project-connection", "project_resource_id": target["project_resource_id"],
            "project_endpoint": target["project_endpoint"], "name": prior["connection"]["name"],
        },
    ])


def _plan_connection(request, target, prior, result, response, *, base_dir, token_provider, transport, sdk_loader):
    prompt_connect._validate_plan(prior)
    project, endpoint = prompt_connect._project_identity(prior)
    body = response["body"]
    created = {"type": "project-connection", "name": target["name"]}
    owned_write = {"action": "created", "connection": target["name"]}
    resources = _object(result.get("resources"), "Creation resources")
    ownership = _object(result.get("ownership"), "Creation ownership")
    verification = _object(result.get("verification"), "Creation verification")
    readback = _object(verification.get("connection_readback"), "Creation connection readback")
    def matches(item):
        return isinstance(item, dict) and (
            (item.get("type") == "project-connection" and item.get("name") == target["name"])
            or item.get("connection") == target["name"]
        )

    if any(not isinstance(container.get(key, []), list) for container, keys in (
        (resources, ("created", "reused", "updated", "skipped")), (ownership, ("run_owned", "reused_not_owned")),
    ) for key in keys):
        raise _failure("ownership-unproven", "Creation resource and ownership lists must be complete.")
    etag = body.get("etag") or body.get("@odata.etag")
    if (
        project.casefold() != target["project_resource_id"] or endpoint != target["project_endpoint"]
        or prior["connection"]["name"] != target["name"] or prior["connection"]["action"] != "create"
        or response.get("operation") != "project-connection-create" or type(response.get("status")) is not int
        or response["status"] != 201 or not _text(etag)
        or [item for item in resources.get("created", []) if matches(item)] != [created]
        or any(matches(item) for key in ("reused", "updated", "skipped") for item in resources.get(key, []))
        or [item for item in ownership.get("run_owned", []) if matches(item)] != [owned_write]
        or any(matches(item) for item in ownership.get("reused_not_owned", []))
        or readback.get("name") != target["name"] or readback.get("definition_digest") != digest(body)
    ):
        raise _failure("ownership-unproven", "Retain the exact acknowledged created project connection; updated/reused/recovered GETs are not create evidence.")
    if not prompt_connect._connection_readback(prior, body)[0]:
        raise _failure("ownership-unproven", "The original connection body must match its approved project and configuration.")
    plan = {
        "operation": "delete", "outcome": "cleanup-prompt-connection", "plan_kind": "cleanup",
        "cleanup_approved": True, "sdk_major": 2, "owner": request["owner"],
        "project_resource_id": target["project_resource_id"], "project_endpoint": target["project_endpoint"],
        "connection": {"name": target["name"], "run_owned": True, "expected_etag": etag, "owned_definition_digest": digest(body)},
    }
    url = prompt_connect._connection_url(plan)
    token = token_provider(MANAGEMENT_AUDIENCE)
    current, request_id = prompt_cleanup._get_connection(url, token, transport=transport)
    if current is not None and current != body:
        raise _failure("definition-drift", "The project connection changed since acknowledged creation.")
    selected = None
    if "agent_version" in request:
        selected_target = {
            **target, "type": "prompt-agent-version", "name": prior["agent"]["name"], "version": request["agent_version"],
        }
        selected_request = {
            "schema_version": "1.0", "owner": request["owner"], "target": selected_target,
            "creation_input_file": request["creation_input_file"], "creation_result_file": request["creation_result_file"],
            "creation_response_file": request["agent_creation_response_file"],
        }
        selected = plan_cleanup(selected_request, base_dir=base_dir, token_provider=token_provider, transport=transport, sdk_loader=sdk_loader)
        if selected["status"] == "planned":
            plan["agent"] = selected["execution_input"]["plan"]["agent"]
    if current is None:
        if selected is not None and selected["status"] == "planned":
            selected["approval_summary"]["already_absent"] = [target]
            return selected
        return _absent(target, request_id)
    plan["dependency_guard"] = dependencies.prompt_snapshot(
        plan, current, sdk_loader=sdk_loader, bounds=dependencies.limits(request.get("inventory_limits")),
    )
    refreshed, _ = prompt_cleanup._get_connection(url, token, transport=transport)
    if refreshed != current:
        raise _failure("definition-drift", "Connection changed during project consumer discovery.")
    prompt_cleanup._validate_plan(plan)
    retained = [
        {**target, "type": "prompt-agent-version", "name": item["name"], "version": item["version"]}
        for item in plan["dependency_guard"]["versions"]
        if not plan.get("agent") or (item["name"], item["version"]) != (plan["agent"]["name"], plan["agent"]["version"])
    ]
    planned = _planned(target, plan, "helpers/prompt_cleanup.py", retained)
    if selected is not None and selected["status"] == "planned":
        planned["approval_summary"]["delete"].insert(0, selected["approval_summary"]["delete"][0])
    return planned


def _plan_protected(request, target, prior, record, *, base_dir, token_provider, transport, sdk_loader):
    snapshot = record["snapshot"]
    outcome = ("cleanup-search-resource" if target["type"] in ("knowledge-base", "knowledge-source")
               else "cleanup-prompt-version" if target["type"] == "prompt-agent-version" else "cleanup-prompt-connection")
    plan = {"operation": "delete", "outcome": outcome, "plan_kind": "cleanup",
            "cleanup_approved": True, "owner": request["owner"]}
    if record["owner"] != request["owner"]:
        raise _failure("ownership-unproven", "Original producer owner and cleanup accountable owner differ.")
    if target["type"] in ("knowledge-base", "knowledge-source"):
        source = _search_prior(prior, target)
        if snapshot["definition_digest"] != digest(search_reconcile._definition(source["desired"])):
            raise _failure("ownership-unproven", "Receipt does not bind the original approved Search definition.")
        plan.update(resource_type=target["type"], **{k: target[k] for k in ("endpoint", "name", "api_version")},
                    owned_definition_digest=snapshot["definition_digest"], expected_etag=snapshot["etag"])
        token = token_provider(SEARCH_AUDIENCE)
        current, request_id = search_reconcile.read_resource(search_reconcile.resource_url(plan), token, transport=transport)
        if current is None:
            return _absent(target, request_id)
        if digest(search_reconcile._definition(current)) != snapshot["definition_digest"] or current.get("@odata.etag") != snapshot["etag"]:
            raise _failure("definition-drift", "Current Search state differs from the original producer snapshot.")
        if target["type"] == "knowledge-source":
            if dependencies.generated(current) != record["acknowledgement"]["generated"]:
                raise _failure("generated-ownership-unproven", "Current generated identities differ from the native create acknowledgement.")
            plan["dependency_guard"] = dependencies.search_snapshot(
                plan, current, token, transport=transport, bounds=dependencies.limits(request.get("inventory_limits")))
            if plan["dependency_guard"]["generated"] != snapshot["generated"]:
                raise _failure("generated-incarnation-drift", "Generated resources differ from original producer snapshots.")
        else:
            reject_secrets(current)
            plan["desired"] = current
        search_reconcile._validate_plan(plan)
        planned = _planned(target, plan, "helpers/search_reconcile.py", [])
        if target["type"] == "knowledge-source":
            planned["approval_summary"]["delete"].extend(
                {"type": child["type"], "name": child["name"], "endpoint": target["endpoint"], "service_managed": True}
                for child in snapshot["generated"])
        else:
            planned["approval_summary"]["retained_targets"] = [
                {**target, "type": "knowledge-source", "name": item["name"]} for item in current["knowledgeSources"]]
        return planned
    if prior.get("operation") == "create-initial-prompt-agent":
        try:
            from . import _initial_prompt
        except ImportError:
            import _initial_prompt
        _initial_prompt.validate(prior)
        if (target["type"] != "prompt-agent-version" or record["acknowledgement"]["operation"] != "agents.create"
                or snapshot["definition_digest"] != digest(prior["agent"]["definition"])):
            raise _failure("ownership-unproven", "Initial receipts authorize only the acknowledged version, never a connection/container.")
    else:
        prompt_connect._validate_plan(prior)
        if target["type"] == "prompt-agent-version" and record["acknowledgement"]["operation"] != "agents.create_version":
            raise _failure("ownership-unproven", "Connect receipts must come from the native new-version operation.")
    project, endpoint = prompt_connect._project_identity(prior)
    if project.casefold() != target["project_resource_id"] or endpoint != target["project_endpoint"]:
        raise _failure("ownership-unproven", "Receipt project differs from original creation approval.")
    plan.update(sdk_major=2, project_resource_id=target["project_resource_id"], project_endpoint=target["project_endpoint"])
    if target["type"] == "prompt-agent-version":
        if prior["agent"]["name"] != target["name"] or prior["agent"].get("version") == target["version"]:
            raise _failure("ownership-unproven", "Only the acknowledged new version is eligible, never the baseline.")
        Client, _, _, _, extras = sdk_loader()
        Credential, AzureError = extras
        client = Client(endpoint=endpoint, credential=Credential())
        try:
            current = client.agents.get_version(agent_name=target["name"], agent_version=target["version"])
            if (current.name != target["name"] or str(current.version) != target["version"]
                    or digest(current.definition.as_dict()) != snapshot["definition_digest"]
                    or receipts.version_identity(current) != snapshot["version_identity"]):
                raise _failure("definition-drift", "Selected version differs from the original SDK return.")
        except AzureError as exc:
            if sdk_error_status(exc) == 404:
                return _absent(target)
            raise HelperFailure(message="Exact version readback failed.", blocked_at="cleanup-planning",
                                **sdk_error_metadata(exc, "agent-readback-failed")) from exc
        finally:
            client.close()
        plan["agent"] = {"name": target["name"], "version": target["version"], "run_owned": True,
                         "owned_definition_digest": snapshot["definition_digest"], "owned_version_identity": snapshot["version_identity"]}
        prompt_cleanup._validate_plan(plan)
        return _planned(target, plan, "helpers/prompt_cleanup.py", [])
    if prior["connection"]["name"] != target["name"] or prior["connection"]["action"] != "create":
        raise _failure("ownership-unproven", "Connection receipt must bind original create intent.")
    plan["connection"] = {"name": target["name"], "run_owned": True, "expected_etag": snapshot["etag"],
                          "owned_definition_digest": snapshot["definition_digest"]}
    token = token_provider(MANAGEMENT_AUDIENCE)
    url = prompt_connect._connection_url(plan)
    current, request_id = prompt_cleanup._get_connection(url, token, transport=transport)
    if current is not None and (digest(current) != snapshot["definition_digest"] or not prompt_connect._connection_readback(prior, current)[0]):
        raise _failure("definition-drift", "Connection differs from its original acknowledged producer state.")
    selected = None
    if "agent_version" in request:
        selected = plan_cleanup({
            "schema_version": "1.0", "owner": request["owner"],
            "target": {**target, "type": "prompt-agent-version", "name": prior["agent"]["name"], "version": request["agent_version"]},
            "creation_input_file": request["creation_input_file"],
            "creation_receipt_file": request["agent_creation_receipt_file"],
        }, base_dir=base_dir, token_provider=token_provider, transport=transport, sdk_loader=sdk_loader)
        if selected["status"] == "planned":
            plan["agent"] = selected["execution_input"]["plan"]["agent"]
    if current is None:
        if selected and selected["status"] == "planned":
            selected["approval_summary"]["already_absent"] = [target]
            return selected
        return _absent(target, request_id)
    plan["dependency_guard"] = dependencies.prompt_snapshot(
        plan, current, sdk_loader=sdk_loader, bounds=dependencies.limits(request.get("inventory_limits")))
    if prompt_cleanup._get_connection(url, token, transport=transport)[0] != current:
        raise _failure("definition-drift", "Connection changed during consumer discovery.")
    prompt_cleanup._validate_plan(plan)
    planned = _planned(target, plan, "helpers/prompt_cleanup.py", [])
    if selected and selected["status"] == "planned":
        planned["approval_summary"]["delete"].insert(0, selected["approval_summary"]["delete"][0])
    return planned


def plan_cleanup(
    request: dict[str, Any], *, base_dir: Path = Path("."),
    token_provider: TokenProvider = azure_cli_token, transport: Transport = http_request,
    sdk_loader: Callable[[], tuple[Any, Any, Any, Any, Any]] = prompt_cleanup.load_cleanup_sdk,
) -> dict[str, Any]:
    _object(request, "Cleanup planning request")
    reject_secrets(request)
    require_allowed_fields(request, REQUEST_FIELDS, label="Cleanup planning request")
    if request.get("schema_version") != "1.0" or not _text(request.get("owner")):
        raise _failure("input-schema-invalid", "schema_version 1.0 and accountable owner are required.")
    target = _target(request.get("target"))
    dependencies.limits(request.get("inventory_limits"))
    selection_fields = {"agent_version", "agent_creation_response_file", "agent_creation_receipt_file"} & set(request)
    evidence_field = "agent_creation_receipt_file" if "agent_creation_receipt_file" in request else "agent_creation_response_file"
    if selection_fields and (selection_fields != {"agent_version", evidence_field} or target["type"] != "project-connection"):
        raise _failure("input-schema-invalid", "Only connection cleanup can explicitly select both agent_version and its original create response.")
    if selection_fields and (
        not isinstance(request["agent_version"], str) or re.fullmatch(r"[1-9][0-9]*", request["agent_version"]) is None
        or not _text(request[evidence_field])
    ):
        raise _failure("target-selection-required", "Select an exact numeric created agent version and original SDK response file.")
    if "creation_receipt_file" in request:
        try:
            from .blob_recheck import read_private
        except ImportError:
            from blob_recheck import read_private
        path = _path(request, "creation_receipt_file", base_dir)
        if read_private(path).get("kind") == "cleanup-creation-receipt":
            if ("creation_response_file" in request or "creation_result_file" in request
                    or (selection_fields and evidence_field != "agent_creation_receipt_file")):
                raise _failure("input-schema-invalid", "Protected receipts cannot be mixed with manual response adapters.")
            prior, record = receipts.load(_path(request, "creation_input_file", base_dir), path, target)
            return _plan_protected(request, target, prior, record, base_dir=base_dir,
                                   token_provider=token_provider, transport=transport, sdk_loader=sdk_loader)
    if evidence_field == "agent_creation_receipt_file":
        raise _failure("input-schema-invalid", "Selected producer receipts require a protected connection receipt.")
    prior, result, response = _records(request, target, base_dir)
    if target["type"] in {"knowledge-base", "knowledge-source"}:
        return _plan_search(
            request, target, prior, result, response, token_provider=token_provider, transport=transport,
        )
    if target["type"] == "project-connection":
        return _plan_connection(
            request, target, prior, result, response, base_dir=base_dir,
            token_provider=token_provider, transport=transport, sdk_loader=sdk_loader,
        )
    return _plan_prompt(request, target, prior, result, response, sdk_loader=sdk_loader)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args(argv)
    request: dict[str, Any] = {}
    try:
        request = _read_json(args.plan)
        result = plan_cleanup(request, base_dir=args.plan.resolve().parent)
        emit_result(result, preserve_unapproved_input=result["status"] == "planned")
    except HelperFailure as failure:
        result = blocked_result(failure, outcome="plan-cleanup", fingerprint=None, owner=request.get("owner"))
        result["approval_summary"] = {
            "delete": [], "retain": RETAIN + ["selected target and all its dependencies"],
            "blocked": [failure.code], "order": [], "hosted_cleanup": "unsupported",
        }
        try:
            result["approval_summary"]["retained_targets"] = [_target(request.get("target"))]
        except HelperFailure:
            pass
        emit_result(result)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
