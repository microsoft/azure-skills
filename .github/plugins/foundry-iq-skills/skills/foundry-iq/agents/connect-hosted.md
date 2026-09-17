# Existing Hosted Agent connection

Branch of [Connect](connect.md), not a creation workflow.
Inspect remotely first; no source path for inspection or exact reuse.
Missing `azure.yaml` in cwd is not a discovery blocker.
Do not reinstall, reinitialize or inspect policy upfront.
Retain resources; Hosted cleanup is unsupported.

## Inspect

Use known project endpoint, exact agent name/version, KB MCP identity, runtime
principal and actual connection/toolbox/binding readbacks through authenticated,
observed read operations. Missing read tooling is a tooling blocker, not a source
request. Run these azd reads only with already available project/environment:

```text
azd ai agent show <service-name> --output json --no-prompt
azd ai connection show <connection-name> --output json --no-prompt
azd ai toolbox show <toolbox-name> --output json --no-prompt
```

Never use `azd ai project set` as a read; context changes require approval.
Inspect compatible connections/toolboxes before choosing a new name. Never
overwrite a Prompt connection using `ProjectManagedIdentity` to make it Hosted.

Compare agent identity/version, model, telemetry, ACR,
network, environment, connection target/auth/audience and toolbox/default tools.
For omitted audience or `UnknownConnectionPropertiesV2`, use the exact
[nonsecret connection readback](../references/platform-interfaces.md#hosted-connection-readback).
Projection gaps are warnings only after authoritative equality is proven;
denial, conflicting properties or still-missing required evidence blocks.

Resolve the actual published agent principal, not its blueprint or project MI.
Check effective runtime access and plan only missing grants:

| Permission | Grant scope |
|---|---|
| Search Index Data Reader | `<search-service-resource-id>` |
| Foundry User or documented equivalent for toolbox access | `<project-resource-id>` |

Reuse compatible effective grants. Disclose that Search service scope covers
its indexes, while Foundry User grants broader project data operations, not just
toolbox reads. No automatic grant, scope widening or caller-role change. A newly
observed principal or access requirement needs a separate approved access plan.

## Select binding before approval

Unchanged consumer: [toolbox-only branch](connect-hosted-toolbox.md); no deploy.

Source-free changes require observed runtime support and an authoritative surface.
Otherwise explain the exact code/config/deploy delta and handoff/request source
only then. Hosted code orchestrates tools: existing agents may need source too;
no arbitrary Hosted tool changes through Prompt APIs.

For the source-backed recipe, inspect its supported mode and emitted environment,
not just local variables. For `FoundryToolbox`, an explicitly
empty `TOOLBOX_ENDPOINT` raises instead of falling back to `TOOLBOX_NAME`.

| Mode | `TOOLBOX_ENDPOINT` | `TOOLBOX_NAME` |
|---|---|---|
| Endpoint | `<consumer-endpoint>` | `""` or absent |
| Name | absent | `<toolbox-name>` |

The consumer endpoint is
`<project-endpoint>/toolboxes/<toolbox-name>/mcp?api-version=v1`.
Do not substitute the version-specific developer endpoint returned by some
toolbox readers. Preserve an already compatible exact binding without
standardizing its mode. For new/repair bindings, select one supported mode:
if the manifest injects an empty endpoint, prefer endpoint mode when supported.
Unsetting a local variable does not remove a manifest's runtime environment key.
If no valid binding is possible without source edits, stop for separate review.

If installed, validate resolution offline with the SDK; do not install it for
this check. No token/model call or standalone
agentic toolbox `tools/list`: runtime identity requires published-agent context.

## Approved changes only

This source-backed recipe requires the approved existing `azd ai agent` source project;
unsupported/image-only source blocks this recipe, not remote inspection.
Retain source/config hashes for source/config changes or source-backed redeployment.
Plan grants/resource/binding deltas, source digest, costs and verification.
Exact state skips every mutation below.
After approved access changes, create only absent exact resources:

```text
azd ai connection create <connection-name> --kind remote-tool --target <exact-kb-mcp-endpoint> --auth-type agentic-identity --audience https://search.azure.com/ --output json --no-prompt
azd ai toolbox create <toolbox-name> --from-file <approved-toolbox-yaml> --output json --no-prompt
```

Verify stored `AgenticIdentityToken`, audience, target and project before
toolbox creation. YAML contains only description and the exact connection name;
no credentials or extra tools. Creation auto-publishes the first toolbox version
and writes `TOOLBOX_<NORMALIZED_NAME>_MCP_ENDPOINT` locally; disclose that write.

Apply only the selected approved binding delta. Endpoint mode:

```text
azd env set TOOLBOX_ENDPOINT <consumer-endpoint> --no-prompt
```

If the source exposes an unused name variable, clear it only as an approved delta:

```text
azd env set TOOLBOX_NAME "" --no-prompt
```

Name mode, only with the endpoint absent from the emitted runtime environment:

```text
azd env set TOOLBOX_NAME <toolbox-name> --no-prompt
```

Deploy only when remote configuration differs, under the same agent name:

```text
azd deploy <service-name> --no-prompt
```

Independently read back the returned version, actual principal, binding and
protected state. `active` metadata is not runtime-health proof. Unknown/changed
identity, source drift or failure stops; no blind retry, `--force`, handcrafted
mutation API, replacement agent or automatic cleanup.

## Verify and reconcile

Pin the observed version at session creation. A new session does not guarantee a new Responses
conversation. Start both fresh:

```text
azd ai agent invoke <service-name> "<supported-question>" --protocol responses --version <verified-version> --new-session --new-conversation --no-prompt
```

Capture the first response's session ID as `<first-response-session-id>` and its
conversation ID. Verify both are distinct from prior trial IDs. Missing or reused
first-response IDs block the second call. Do not rely on automatic session selection;
explicitly pin the captured session while starting a fresh conversation:

```text
azd ai agent invoke <service-name> "<unsupported-question>" --protocol responses --session-id <first-response-session-id> --new-conversation --no-prompt
```

Sessions bind their version at creation; `--version` and `--session-id` are mutually exclusive.
If the installed CLI lacks `--session-id`, block verification rather than falling
back to a saved session. Require the second response's session ID to equal the
captured ID and its conversation ID to differ from the first and all prior trials.
Missing or mismatched IDs make isolation unverified: stop before monitoring or
further invocations. Do not silently add invocations to repair a bounded test.

Correlate actual `knowledge_base_retrieve` success with each request and response,
using returned events or supported logs:

```text
azd ai agent monitor <service-name> --session-id <first-response-session-id> --tail 300 --no-prompt
```

Require supported answers with original citations and unsupported answers exactly
`I don't know.` without citations. Errors are not abstention. Tool success proves
execution, not the contents of an unavailable payload: record missing arguments,
results or usage and leave payload-level faithfulness unverified. Never infer
empty retrieval or change source/telemetry to manufacture proof.

Compare identities, versions, tools, roles, protected source and binding.
Repeat reconciliation through reads only: no setters, create, publish
or deploy calls on exact state. Zero configuration writes excludes authorized
invocation/conversation/session activity and local test metadata; report both.
Retain resources. Cleanup remains separately approved and
`hosted-cleanup-unsupported` in this skill.
