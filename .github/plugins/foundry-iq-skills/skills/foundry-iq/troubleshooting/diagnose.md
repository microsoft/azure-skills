# Diagnose and repair Foundry IQ

## When to use

For Foundry IQ access/ingestion/retrieval/citation/connection/toolbox/identity/network
or preserved-agent deployment failures. Diagnose read-only; external causes get owner/handoff.

Scope-only: unsupported connector provisioning or multi-source KB creation/reconfiguration.
Read this procedure, state the boundary and stop: no credentials, Azure discovery,
repair, source substitution or partial compound execution.
Existing multi-source KB connection uses [Connect](../agents/connect.md), without KB mutation.
Read-only operations retain their owners/helper constraints, not new source/retrieval support.
Unclear scope: [intent-routing](../references/intent-routing.md), clarify before discovery.
Operational failures follow below.

## Do not use

Do not patch source content, inventory, boundary, schedule, extraction,
permissions, definition, or generated children; those require separately
planned source recreation. Never broaden RBAC/network, switch region/SKU/model,
use keys, create parallel resources, or repeat arbitrary retries.

## Inputs and discovery order

Resolve prompt, explicit session choice, unambiguous workspace, exact Azure
readback, documented non-consequential default, then one focused question.
Label the source; missing required input blocks, silence is not approval, and
read-only diagnosis needs no approval.

| Input | Why needed | Required? | Discovery order | Safe default | If missing or unanswered | Reconfirmation trigger |
|---|---|---|---|---|---|---|
| Operation/time and expected/observed | Reproduce | Required | Prompt, baseline, direct check | None | Ask | Expectation change |
| Status/message/request ID | First failure | When emitted | Exact response/log | None | Record unavailable | New first failure |
| API/plane/target ID | Interface | Required | Trace/readback | None | Block | API/target change |
| Principal/auth/RBAC | Identity | Required/roles conditional | Claims metadata/readback | None | Block | Identity/assignment change |
| Network/reachability | Security | Required | Resource/execution readback | Preserve posture | Block | Network or reachability posture changed |
| Source/base definition digest | Drift | Required | Readback/baseline | None | Block | Source or base definition changed |
| Agent connection/tool/toolbox/environment | Binding | Conditional | Exact readback | Preserve unrelated state | Block | Connection, tool/toolbox, or environment changed |
| Retry evidence | Bounded transient | Conditional | Service status/readback | One service-signaled 408/429/5xx | No retry otherwise | Service status or retry evidence changed |
| Repair/cleanup owner | Accountability | Conditional for write | Prompt, session | None | Block mutation | Owner change |

## Decisions

Preserve the first failure. Run the nearest read-only discriminator in order:
target/API existence and access, source/base definition equality, ingestion,
identity/exact roles, network, connection, tool/toolbox/environment, direct base
response, agent invocation. Stop at first proven cause; unknown stays unknown.

For Hosted connection failures, use [Hosted connection](../agents/connect-hosted.md):
an omitted audience/unknown typed auth may be a projection gap, not resource
drift. Verify through its nonsecret ARM readback before declaring incompatibility;
do not rewrite a matching connection. An explicitly empty `TOOLBOX_ENDPOINT`
can prevent name fallback and crash startup despite `active` deployment metadata.
Inspect emitted environment and validate resolution offline; any binding repair
and required redeployment need a new fingerprinted plan, not a source patch,
permission increase or speculative retry.

Repair only exact identity/RBAC, network reachability without downgrade, project
connection, MCP tool, toolbox, environment binding, or preserved deployment.
Source content/inventory/schedule/extraction/permissions/definition/generated
drift is `recreate required`: report exact diff and hand off. Replacement cannot
start until exact absence or approved replacement identity/ownership proof;
never suffix. Unsupported source, generic lifecycle, classic Search, or outage
gets explicit owner/handoff.

If an Azure creation failure implicates policy, use targeted
[policy diagnostics](../references/search-substrate.md#azure-policy-diagnostics-after-creation-failure);
pass findings to the creation owner and obtain approval for changed repair plans.
Do not scan policy before repair creation. A 403 alone is not proof of a
policy denial or missing role; preserve the response and distinguish the cause.

## Proposed plan

Show first proven cause and at most one exact repair with before/after, target,
API/plane, principal/role/scope, network, protected-state diff, verification,
rollback/cleanup owner, retained resources, and cost. No mutation occurs.

## Confirmation

Present one immutable proposed repair plan with complete `plan_fingerprint` and
`cleanup_approved: false`. Plain approval applies only to one unchanged pending
plan. Any target/status/definition/identity/role/network/connection/protected
readback change requires new review. Recreation uses its own plan.

## Mutation

After approval, perform exactly one bounded repair and no adjacent improvement.
Use only the authoritative owning surface: `helpers/search_reconcile.py` for an
exact Search source/base identity or role-free definition repair,
`helpers/prompt_connect.py` for the conditional existing-Prompt fallback, or
the exact Hosted `azd` sequence in [Connect](../agents/connect.md). There is no
generic diagnosis repair script. Open-ended cause selection, ambiguity
resolution, approval, and unsupported Hosted states remain human decisions.
If no listed surface owns the proven repair, return
`repair-surface-unavailable` with the required owner/handoff; do not improvise
REST, SDK, CLI, or MCP syntax.
Preserve unrelated fields, sources/children, models, telemetry, versions,
network, and permissions. For service-signaled 408/429/5xx only, wait the
indicated/bounded delay, read back, and retry once within the approved operation;
never a new name.

## Verification

Rerun failed check plus one adjacent invariant: permission/exact scope, network/
unchanged posture, connection/tool/full agent baseline, or deployment/model/
telemetry/source digest. Require exact readback and request evidence. A repaired
call without citation/grounding proof is incomplete.

## Failure and partial completion

Return first failure unchanged plus repair result. Unproven cause, insufficient
rights, inaccessible readback, failed retry, or protected drift stops. `blocked`
records phase/blocker/input, read evidence, no writes/ownership, and safe next
decision. `partial` records completed write, failed/unverified condition,
remaining run-owned/reused resources, exact rollback, separate cleanup, owner,
and warnings.

## Cleanup

Repair approval excludes cleanup. A separate fingerprinted cleanup plan and
explicit approval may revert only the run-owned repair artifact with exact
ownership/dependency order. Never delete reused resources, source content,
generated children independently, or prior versions. Unclear ownership blocks.

## Return contract

Return `completed`, `blocked`, or `partial` with named diagnosis/handoff,
fingerprint when applicable, `blocked_at`, first failure status/message/request
ID/time/API/plane/target, discriminators, repair identity/before/after,
auth/RBAC/network/protected-state verification, retry count, warnings,
ownership, and cleanup.

## References

- [Shared audit schemas](../references/platform-contracts.md) add canonical field
  detail but are not required for ordinary execution.
- [Interface versions](../references/platform-interfaces.md) add supporting
  request detail.

Authorities: failure/conflict/uncertainty only.

- [Troubleshoot agentic retrieval](https://learn.microsoft.com/azure/search/search-agentic-retrieval-how-to-troubleshoot)
