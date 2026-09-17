from __future__ import annotations

import argparse
import inspect
import sys
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
from typing import Any, Callable

try:
    from . import _cleanup_dependencies as cleanup_dependencies
    from ._common import (
        MANAGEMENT_AUDIENCE,
        HelperFailure,
        TokenProvider,
        Transport,
        azure_cli_token,
        blocked_result,
        digest,
        emit_result,
        http_request,
        is_ambiguous_mutation_failure,
        is_ambiguous_sdk_error,
        load_approved_input,
        reject_secrets,
        require_allowed_fields,
        sdk_error_status,
        sdk_error_metadata,
    )
    from .prompt_connect import _connection_url, _load_connection_sdk as _load_sdk, _project_identity
except ImportError:
    import _cleanup_dependencies as cleanup_dependencies
    from _common import (  # type: ignore[no-redef]
        MANAGEMENT_AUDIENCE,
        HelperFailure,
        TokenProvider,
        Transport,
        azure_cli_token,
        blocked_result,
        digest,
        emit_result,
        http_request,
        is_ambiguous_mutation_failure,
        is_ambiguous_sdk_error,
        load_approved_input,
        reject_secrets,
        require_allowed_fields,
        sdk_error_status,
        sdk_error_metadata,
    )
    from prompt_connect import (  # type: ignore[no-redef]
        _connection_url,
        _load_connection_sdk as _load_sdk,
        _project_identity,
    )


def load_cleanup_sdk():
    try:
        installed = version("azure-ai-projects").split(".")
        if int(installed[0]) != 2 or int(installed[1]) < 4:
            raise ValueError
    except (PackageNotFoundError, ValueError, IndexError) as exc:
        raise HelperFailure("sdk-version-invalid", "Cleanup requires azure-ai-projects >=2.4,<3 for complete draft inventories.",
                            blocked_at="execution") from exc
    return _load_sdk()


def _validate_owned_resource(
    resource: Any,
    *,
    label: str,
    identity_fields: tuple[str, ...],
) -> dict[str, Any] | None:
    if resource is None:
        return None
    if (
        not isinstance(resource, dict)
        or resource.get("run_owned") is not True
        or not isinstance(resource.get("owned_definition_digest"), str)
        or not all(isinstance(resource.get(field), str) and resource[field] for field in identity_fields)
    ):
        raise HelperFailure(
            "ownership-unproven",
            f"{label} cleanup requires exact run-owned identity and definition digest.",
            blocked_at="reconciliation",
        )
    return resource


def _validate_plan(
    plan: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    reject_secrets(plan)
    require_allowed_fields(
        plan,
        {
            "operation",
            "outcome",
            "plan_kind",
            "cleanup_approved",
            "sdk_major",
            "project_resource_id",
            "project_endpoint",
            "agent",
            "connection",
            "owner",
            "dependency_guard",
        },
        label="Prompt cleanup plan",
    )
    cleanup_dependencies.validate_guard(plan)
    if (
        plan.get("operation") != "delete"
        or plan.get("plan_kind") != "cleanup"
        or plan.get("cleanup_approved") is not True
        or plan.get("sdk_major") != 2
    ):
        raise HelperFailure(
            "cleanup-approval-mismatch",
            "Prompt cleanup requires a separate approved cleanup plan and SDK major 2.",
            blocked_at="confirmation",
        )
    _project_identity(plan)
    agent = _validate_owned_resource(
        plan.get("agent"),
        label="Agent version",
        identity_fields=("name", "version"),
    )
    connection = _validate_owned_resource(
        plan.get("connection"),
        label="Project connection",
        identity_fields=("name",),
    )
    if agent is not None:
        require_allowed_fields(
            agent,
            {"name", "version", "run_owned", "owned_definition_digest", "owned_version_identity"},
            label="Prompt cleanup agent",
        )
        if "owned_version_identity" in agent:
            try:
                from . import _cleanup_receipts
            except ImportError:
                import _cleanup_receipts
            identity = agent["owned_version_identity"]
            if (not isinstance(identity, dict) or set(identity) != {"id", "created_at"}
                    or _cleanup_receipts.version_identity(identity) != identity):
                raise HelperFailure("ownership-unproven", "Native version birth identity must be exact.", blocked_at="reconciliation")
    if connection is not None:
        require_allowed_fields(
            connection,
            {
                "name",
                "run_owned",
                "owned_definition_digest",
                "expected_etag",
            },
            label="Prompt cleanup connection",
        )
    if connection is not None and not isinstance(connection.get("expected_etag"), str):
        raise HelperFailure(
            "ownership-unproven",
            "Project connection cleanup requires the approved current ETag.",
            blocked_at="reconciliation",
        )
    if agent is None and connection is None:
        raise HelperFailure(
            "ownership-unproven",
            "Prompt cleanup must identify at least one run-owned resource.",
            blocked_at="reconciliation",
        )
    if connection is not None:
        _connection_url({**plan, "connection": connection})
    return agent, connection


def _delete_agent(
    plan: dict[str, Any],
    agent: dict[str, Any],
    *,
    sdk_loader: Callable[[], tuple[Any, Any, Any, Any, Any]],
) -> tuple[str, dict[str, Any]]:
    AIProjectClient, _, _, _, extras = sdk_loader()
    AzureCliCredential, AzureError = extras
    client = AIProjectClient(
        endpoint=_project_identity(plan)[1],
        credential=AzureCliCredential(),
    )
    identity = {"type": "prompt-agent-version", "name": agent["name"], "version": agent["version"]}
    version_options = {"include_drafts": True}
    try:
        signature = inspect.signature(client.agents.list_versions)
        if ("include_drafts" not in signature.parameters
                and not any(p.kind == inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values())):
            raise HelperFailure("sdk-version-invalid", "Cleanup requires draft-inclusive version listing.",
                                blocked_at="execution")
        versions = list(client.agents.list_versions(agent_name=agent["name"], **version_options))
        if agent["version"] not in {str(item.version) for item in versions}:
            return "skipped", identity
        current = client.agents.get_version(
            agent_name=agent["name"],
            agent_version=agent["version"],
        )
        if "owned_version_identity" in agent:
            try:
                from . import _cleanup_receipts
            except ImportError:
                import _cleanup_receipts
            if _cleanup_receipts.version_identity(current) != agent["owned_version_identity"]:
                raise HelperFailure("definition-drift", "Native version identity changed since creation.", blocked_at="reconciliation")
        if digest(current.definition.as_dict()) != agent["owned_definition_digest"]:
            raise HelperFailure(
                "definition-drift",
                "The agent version definition changed after cleanup approval.",
                blocked_at="reconciliation",
            )
        try:
            client.agents.delete_version(
                agent_name=agent["name"],
                agent_version=agent["version"],
            )
        except AzureError as exc:
            status = sdk_error_status(exc)
            if status != 404 and not is_ambiguous_sdk_error(exc):
                raise HelperFailure(
                    message="The Prompt Agent SDK delete operation failed.",
                    blocked_at="execution",
                    **sdk_error_metadata(exc, "agent-cleanup-failed"),
                ) from exc
            try:
                remaining = list(
                    client.agents.list_versions(agent_name=agent["name"], **version_options)
                )
            except AzureError as readback_exc:
                raise HelperFailure(
                    "agent-delete-outcome-ambiguous",
                    "Agent deletion and same-identity readback are ambiguous.",
                    blocked_at="verification",
                    resources_remaining=[identity],
                    partial=True,
                    **sdk_error_metadata(exc),
                ) from readback_exc
            if agent["version"] not in {
                str(item.version) for item in remaining
            }:
                return ("skipped" if status == 404 else "deleted"), identity
            if status == 404:
                raise HelperFailure(
                    "agent-cleanup-failed",
                    "Agent delete returned not found but same-identity readback still found the version.",
                    blocked_at="verification",
                    resources_remaining=[identity],
                    **sdk_error_metadata(exc),
                ) from exc
            raise HelperFailure(
                "agent-delete-outcome-ambiguous",
                "Same-identity readback still found the agent version after an ambiguous delete.",
                blocked_at="verification",
                resources_remaining=[identity],
                partial=True,
                **sdk_error_metadata(exc),
            ) from exc
        try:
            remaining = list(
                client.agents.list_versions(agent_name=agent["name"], **version_options)
            )
        except AzureError as exc:
            raise HelperFailure(
                "agent-delete-outcome-ambiguous",
                "Agent delete completed but absence readback is ambiguous.",
                blocked_at="verification",
                writes=[{"action": "deleted", **identity}],
                resources_remaining=[identity],
                partial=True,
                **sdk_error_metadata(exc),
            ) from exc
        if agent["version"] in {str(item.version) for item in remaining}:
            raise HelperFailure(
                "absence-unverified",
                "The exact agent version still exists after delete.",
                blocked_at="verification",
                writes=[{"action": "deleted", **identity}],
                resources_remaining=[identity],
                partial=True,
            )
        return "deleted", identity
    except AzureError as exc:
        raise HelperFailure(
            message="The Prompt Agent SDK cleanup operation failed.",
            blocked_at="execution",
            partial=False,
            **sdk_error_metadata(exc, "agent-cleanup-failed"),
        ) from exc
    finally:
        client.close()


def _get_connection(
    url: str,
    token: str,
    *,
    transport: Transport,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        result = transport("GET", url, token)
    except HelperFailure as failure:
        if failure.http_status == 404:
            return None, failure.request_id
        raise
    if result.status != 200 or not isinstance(result.body, dict):
        raise HelperFailure(
            "connection-readback-invalid",
            "Project connection readback was not one JSON object.",
            blocked_at="reconciliation",
            request_id=result.request_id,
            status=result.status,
        )
    return result.body, result.request_id


def _delete_connection(
    plan: dict[str, Any],
    connection: dict[str, Any],
    token: str,
    *,
    transport: Transport,
    sdk_loader: Callable[[], tuple[Any, Any, Any, Any, Any]] = load_cleanup_sdk,
) -> tuple[str, dict[str, Any], list[str]]:
    url = _connection_url({**plan, "connection": connection})
    current, initial_request_id = _get_connection(url, token, transport=transport)
    identity = {"type": "project-connection", "name": connection["name"]}
    request_ids = [initial_request_id] if initial_request_id else []
    if current is None:
        return "skipped", identity, request_ids
    if digest(current) != connection["owned_definition_digest"]:
        raise HelperFailure(
            "definition-drift",
            "The project connection changed after cleanup approval.",
            blocked_at="reconciliation",
        )
    current_etag = current.get("etag") or current.get("@odata.etag")
    if current_etag != connection["expected_etag"]:
        raise HelperFailure(
            "definition-drift",
            "The project connection ETag changed after cleanup approval.",
            blocked_at="reconciliation",
        )
    if plan.get("dependency_guard") is not None:
        cleanup_dependencies.verify_prompt(plan, current, sdk_loader=sdk_loader, allow_selected=False)
        refreshed, _ = _get_connection(url, token, transport=transport)
        if refreshed != current:
            raise HelperFailure("definition-drift", "Connection changed during final consumer discovery.", blocked_at="reconciliation")
    try:
        result = transport(
            "DELETE",
            url,
            token,
            headers={"If-Match": connection["expected_etag"]},
        )
    except HelperFailure as failure:
        if failure.http_status == 404:
            return "skipped", identity, request_ids
        if not is_ambiguous_mutation_failure(failure):
            raise
        return _recover_ambiguous_connection_delete(
            url,
            token,
            identity,
            request_ids,
            failure,
            transport=transport,
        )
    if result.status not in {200, 202, 204}:
        if result.status == 404:
            return "skipped", identity, request_ids
        if result.status in {408, 429} or result.status >= 500:
            return _recover_ambiguous_connection_delete(
                url,
                token,
                identity,
                request_ids,
                HelperFailure(
                    "connection-delete-outcome-ambiguous",
                    f"Project connection delete returned ambiguous HTTP {result.status}.",
                    blocked_at="execution",
                    request_id=result.request_id,
                    status=result.status,
                    partial=True,
                ),
                transport=transport,
            )
        raise HelperFailure(
            "connection-cleanup-failed",
            f"Project connection delete returned HTTP {result.status}.",
            blocked_at="execution",
            request_id=result.request_id,
            status=result.status,
        )
    if result.request_id:
        request_ids.append(result.request_id)
    write = {"action": "deleted", **identity}
    try:
        after, verify_request_id = _get_connection(
            url, token, transport=transport
        )
    except HelperFailure as failure:
        raise HelperFailure(
            failure.code,
            failure.message,
            blocked_at=failure.blocked_at,
            writes=[write, *failure.writes],
            resources_remaining=[identity],
            request_id=failure.request_id,
            status=failure.http_status,
            partial=True,
        ) from failure
    if verify_request_id:
        request_ids.append(verify_request_id)
    if after is not None:
        raise HelperFailure(
            "absence-unverified",
            "The project connection still exists after delete.",
            blocked_at="verification",
            writes=[write],
            resources_remaining=[identity],
            request_id=verify_request_id,
            partial=True,
        )
    return "deleted", identity, request_ids


def _recover_ambiguous_connection_delete(
    url: str,
    token: str,
    identity: dict[str, Any],
    request_ids: list[str],
    failure: HelperFailure,
    *,
    transport: Transport,
) -> tuple[str, dict[str, Any], list[str]]:
    if failure.request_id:
        request_ids.append(failure.request_id)
    try:
        after, verify_request_id = _get_connection(
            url, token, transport=transport
        )
    except HelperFailure as readback_failure:
        raise HelperFailure(
            "connection-delete-outcome-ambiguous",
            "Connection deletion and same-identity readback are ambiguous.",
            blocked_at="verification",
            resources_remaining=[identity],
            request_id=readback_failure.request_id or failure.request_id,
            status=failure.http_status,
            partial=True,
        ) from readback_failure
    if verify_request_id:
        request_ids.append(verify_request_id)
    if after is not None:
        raise HelperFailure(
            "connection-delete-outcome-ambiguous",
            "Same-identity readback still found the connection after an ambiguous delete.",
            blocked_at="verification",
            resources_remaining=[identity],
            request_id=verify_request_id or failure.request_id,
            status=failure.http_status,
            partial=True,
        )
    return "deleted", identity, request_ids


def execute(
    document: dict[str, Any],
    *,
    token_provider: TokenProvider = azure_cli_token,
    transport: Transport = http_request,
    sdk_loader: Callable[[], tuple[Any, Any, Any, Any, Any]] = load_cleanup_sdk,
) -> dict[str, Any]:
    plan = document["plan"]
    fingerprint = document["_computed_fingerprint"]
    agent, connection = _validate_plan(plan)
    resources: dict[str, list[dict[str, Any]]] = {
        "created": [],
        "reused": [],
        "updated": [],
        "skipped": [],
        "deleted": [],
    }
    writes: list[dict[str, Any]] = []
    request_ids: list[str] = []

    if connection is not None and plan.get("dependency_guard") is not None:
        current, _ = _get_connection(
            _connection_url({**plan, "connection": connection}),
            token_provider(MANAGEMENT_AUDIENCE), transport=transport,
        )
        if current is not None:
            cleanup_dependencies.verify_prompt(plan, current, sdk_loader=sdk_loader)
            refreshed, _ = _get_connection(
                _connection_url({**plan, "connection": connection}),
                token_provider(MANAGEMENT_AUDIENCE), transport=transport,
            )
            if refreshed != current:
                raise HelperFailure("definition-drift", "Connection changed before the first cleanup write.", blocked_at="reconciliation")

    if agent is not None:
        action, identity = _delete_agent(plan, agent, sdk_loader=sdk_loader)
        resources[action].append(identity)
        if action == "deleted":
            writes.append({"action": action, **identity})

    if connection is not None:
        try:
            token = token_provider(MANAGEMENT_AUDIENCE)
            action, identity, connection_request_ids = _delete_connection(
                plan,
                connection,
                token,
                transport=transport,
                sdk_loader=sdk_loader,
            )
        except HelperFailure as failure:
            raise HelperFailure(
                failure.code,
                failure.message,
                blocked_at=failure.blocked_at,
                writes=writes + failure.writes,
                resources_remaining=(
                    [
                        {
                            "type": "project-connection",
                            "name": connection["name"],
                        }
                    ]
                    + [
                        item
                        for item in failure.resources_remaining
                        if item
                        != {
                            "type": "project-connection",
                            "name": connection["name"],
                        }
                    ]
                ),
                request_id=failure.request_id,
                status=failure.http_status,
                partial=bool(writes or failure.writes or failure.partial),
            ) from failure
        resources[action].append(identity)
        request_ids.extend(connection_request_ids)
        if action == "deleted":
            writes.append({"action": action, **identity})

    return {
        "status": "completed",
        "outcome": str(plan.get("outcome") or "cleanup-prompt-connection"),
        "approved_plan": {"fingerprint": fingerprint, "confirmed": True},
        "resources": resources,
        "api_contracts": [
            {
                "operation": "prompt-agent-version-delete",
                "version": "azure-ai-projects-2.x",
                "preview": True,
            },
            {
                "operation": "project-connection-delete",
                "version": "2025-10-01-preview",
                "preview": True,
            },
        ],
        "data_movement": {"boundary": "none", "result": "none"},
        "auth": {"mode": "entra-user", "principals": []},
        "rbac": {"assignments": []},
        "network": {"posture": "preserved", "evidence": None},
        "verification": {
            "absence": True,
            "request_ids": request_ids,
            "idempotency": "already absent run-owned resources are zero-write",
        },
        "warnings": [],
        "ownership": {
            "run_owned": [],
            "reused_not_owned": [],
            "owner": plan.get("owner"),
        },
        "cleanup": {
            "status": "completed",
            "separate_confirmation_required": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args(argv)
    fingerprint: str | None = None
    owner: Any = None
    outcome = "cleanup-prompt-connection"
    try:
        document, plan, fingerprint = load_approved_input(args.input)
        document["_computed_fingerprint"] = fingerprint
        owner = plan.get("owner")
        outcome = str(plan.get("outcome") or outcome)
        result = execute(document)
    except HelperFailure as failure:
        result = blocked_result(
            failure,
            outcome=outcome,
            fingerprint=fingerprint,
            owner=owner,
        )
        emit_result(result)
        return 3 if result["status"] == "partial" else 2
    emit_result(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
