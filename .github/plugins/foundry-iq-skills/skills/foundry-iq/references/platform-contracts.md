# Shared workflow contract

Resolve each value only from: current prompt, explicit session choice,
unambiguous selected workspace configuration, exact-scope Azure readback,
documented safe default that does not choose identity/geography/cost/data/
security/mutation scope, then one focused question. Label the source. Missing
required or applicable conditional input pauses for that question; silence is
not approval, an empty boundary, or fallback selection.

Progress semantically through routing, read-only discovery, input resolution,
reconciliation, proposed-plan review, confirmation, mutation, verification, and
a completed, partial, or blocked result. Cleanup is a separate planned,
approved, executed, and verified lifecycle. Read-only discovery needs no
approval.

Do not read policy as a prerequisite to plans or writes. Use
[policy diagnostics](search-substrate.md#azure-policy-diagnostics-after-creation-failure)
only when Azure creation fails with evidence implicating policy. Preserve known
requirements, security settings and actual Azure denials. Missing diagnostic
details warn without replacing the original failure; no scan is not compliance.

Absent prerequisite IDs are outputs: call the shared bootstrap directly, not
File-to-KB-to-File delegation. Classify each dependency independently for reuse,
creation or conflict. Never alter compatible shared infrastructure.
Bootstrap, observed-principal role assignment, source and verified-source KB
plans have separate actual approvals. No future identity/source verification.

Before mutation, emit one immutable proposed mutation plan with
`plan_fingerprint`, named `outcome`, exact tenant/subscription/group/
Search/project targets, ordered actions with before/after, API version and
GA/preview status, exact data boundary and processing, network and permission
mode, principal/role/scope/assignment IDs, existing/new cost, verification,
rollback owner, retained resources, and `cleanup_approved: false`.
The fingerprint and any definition or content digests are generic integrity
checks over concrete proposed or read-back state, not workflow identifiers.

Plain `yes`, `proceed`, or `go ahead` approves only when exactly one unchanged
proposed mutation plan is pending and its fingerprint still matches. Silence,
emoji, partial language, or multiple pending plans do not approve. Any material
input, inventory, identity, ETag, boundary, model, network, role, definition, or
endpoint or known applicable requirement change invalidates the plan and requires
a new fingerprint and review. Do not refresh policy routinely.
Ambiguous writes are reconciled by reading the same deterministic identity,
never blind retry.

When an owning workflow selects a checked-in helper, read its contract in
`../helpers/contracts.md` before constructing or approving the plan; do not reread.
The helper consumes a
UTF-8 JSON envelope with `schema_version: "1.0"`, the complete `plan`, and
`approval: {confirmed: true, fingerprint: "sha256:<canonical-plan-digest>"}`.
Canonical plan JSON is key-sorted, ASCII-escaped (`ensure_ascii=True`), compact UTF-8.
Helper exit `0` is
`completed`, `2` is a no-write `blocked` result, and `3` is `partial`; callers
must preserve the emitted JSON and nonzero status. Plans never contain tokens,
keys, SAS, passwords, file content, or secret-bearing connection strings.
Helpers do not resolve ambiguity, choose resources, approve plans, diagnose
open-ended failures, or infer cleanup.
Read-only `--plan` exit `0` returns `planned`, unapproved `execution_input`
and an approval summary, not ingestion success.
Use the [selected helper contract](../helpers/contracts.md).
The helper computes integrity values; users approve concrete changes, not hashes.
Fresh exact no-write reuse requires no mutation approval or helper execution;
its identity/marker checks do not prove ingestion readiness. Planning evidence
never carries consent forward. Creation requires current security/known-requirement
evidence and explicit approval before executing the unchanged envelope.
Keep failure-driven policy evidence in the revised parent plan, binding each supported
child plan's fingerprint. Closed helper envelopes do not accept arbitrary policy/tag
fields or evaluate Azure Policy. Required settings must reach the actual
supported request body; otherwise return `azure-policy-setting-unsupported`.

Exact reuse is zero-write and idempotent. Inaccessible is not absent. Multiple compatible
resources without an existing anchor require exact resource-ID selection.
Conflicts stop; never suffix-duplicate or patch drift into conformance.

Use the applicable shape; never manufacture approval.
Planning, fresh exact reuse:

```yaml
status: planned
approval_summary:
  execution_required: false
  mutation_approval_required: false
  verification: identity/markers checked; ingestion/readiness and retrieval unverified
execution_input:
  schema_version: "1.0"
  plan: exact machine plan
  approval: {confirmed: false, fingerprint: machine integrity field}
writes_performed: []
```

Creation: flags true, approval false; no mutation helper for reuse.
File lists: **200 GET pages (empty included), 200 records, 1 MiB body/page**.
Shared **60s** deadline interrupts body sockets; watchdogs are joined.
DNS/connect/headers: inactivity timeouts, not a hard wall limit.
Interrupts may lag; redirects/unsupported readers block. Fail closed;
never truncate; failures after writes stay `partial`. Limits aren't consent.
Only approved mutation completion uses:

```yaml
status: completed
outcome: exact named outcome
approved_plan: {fingerprint: exact, confirmed: true}
resources: {created: [], reused: [], updated: [], skipped: []}
api_contracts: [{operation: exact, version: exact, preview: true|false}]
data_movement: {boundary: exact, result: exact}
auth: {mode: managed-identity|entra-user, principals: []}
rbac: {assignments: []}
network: {posture: exact, evidence: exact}
verification: {ingestion: exact, retrieval: exact, citations: [], abstention: exact, tool_or_toolbox_readback: exact, idempotency: exact}
warnings: []
ownership: {run_owned: [], reused_not_owned: []}
cleanup: {status: not-requested|planned|completed|failed, separate_confirmation_required: true}
```

```yaml
status: blocked
outcome: exact named outcome
blocked_at: discovery|input-resolution|reconciliation|confirmation|verification
first_blocker: {code: exact, message: exact, status: exact|null, request_id: exact|null}
missing_or_conflicting_input: exact
read_only_evidence: []
writes_performed: []
warnings: []
safe_next_decision: one focused question or explicit handoff
ownership: no new resources
cleanup: not applicable
```

```yaml
status: partial
outcome: exact named outcome
first_failure: {operation: exact, status: exact, message: exact, request_id: exact}
completed_writes: []
failed_or_unverified_postconditions: []
resources_remaining: {run_owned: [], reused: []}
rollback: {possible: true|false, exact_plan: []}
cleanup: {status: separate-plan-and-approval-required}
owner: exact
warnings: []
```

Unavailable HTTP status/request IDs are `null`, never invented. Diagnostic
warnings never replace the original failure; empty warnings may be omitted.
Never output content, credentials, tokens, keys, SAS, or connection strings.

Cleanup requires a separate cleanup plan and explicit approval; delete only
run-owned dependents in reverse order. Never delete reused resources, original
files/blobs, prior agent versions, or generated children independently of their
source. Search cleanup binds run-owned definition digest/current ETag.
Prompt cleanup binds exact run-owned version/connection digests; delete the
version first. Hosted cleanup is unsupported: return `hosted-cleanup-unsupported`,
retain resources/charges and name the owner/handoff. Never improvise teardown.

[Interfaces](platform-interfaces.md) and [Search substrate](search-substrate.md)
add technical detail.
