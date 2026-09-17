# Shared prerequisite owner

File/Blob/KB call this directly, never each other for infrastructure.
Search selection/create/ready-reuse belongs to the [Search service owner](../search-services/create.md).
For other unresolved dependencies use [native bootstrap](bootstrap-azure.md), then resume.
An absent RG uses its RG-only branch before Search planning, never a recursive
full-bootstrap call. Already verified ready infrastructure needs no setup.
ARM-ready does not prove role propagation, ingestion or retrieval.
No agents/apps, Storage content or unrequested networking. Absent IDs are outputs.

## Discovery-first recommendations

Reuse resolved prompt/session/workspace choices; do not restart intake on handoff.
Read `az account show` for caller/tenant/default subscription; explicit scope wins.
Use that default unless overridden, never silently switch CLI context.
Account context does not prove live access; missing CLI/sign-in or denied reads
are blockers, not evidence that resources need creation.
Pass chosen `--subscription`. Reuse supplied resource/intent, else ask
USE EXISTING / FIND CANDIDATES / CREATE NEW before enumeration:
[resource intake](resource-intake.md). Only FIND lists, known RG before selected sub.
Only a new group decision needs `az group list --subscription <sub>`.
Do not fan out resource scans across all groups or subscriptions.

Inputs are required before execution, not necessarily questions for the user.
Read IDs, roles, network state and inventories at the appropriate selected scope.
Offer observed reuse/create/choose-another options and recommended names,
region/capacity/costs; ask only the unresolved decision. Proposed owner/settings
are not verified facts. Missing evidence blocks execution after discovery/handoff.
Selection is not mutation consent; preserve valid concrete approval, never
extend it to unknown future actions. Keep local roots and Blob container/folder
boundaries explicit; discovery does not authorize uploads or whole-container ingestion.
During source setup, not every retrieve request, source owners must learn content
structure and answer needs before recommending unresolved Minimal/Standard:
authorized representative samples or customer description, never filename/MIME
inference or a silent Minimal default. Honor explicit choices and reuse supplied
information; unavailable inspection means ask, not assume text-only.
Scans/important visual or table layout can justify CU; a table alone does not require it.
New unresolved search: [recommend Hybrid; confirm tradeoffs](intent-routing.md#search-mode-choice).
Hybrid needs selected embeddings. Neither choice determines KB reasoning effort or synthesis.
Existing retrieval remains read-only; missing vectors: approved setup,
never a silent configuration change.

| Dependency state | Action |
|---|---|
| Empty | Search intent first; RG-only only for approved creation |
| RG-only | Reuse group; Search owner resolves selected service |
| Search-only | Reuse supplied Search through operation checks; no re-selection |
| Ready infrastructure | No infrastructure writes |
| Exact source/KB | Caller reconciles zero-write |
| Multiple compatible | Ask exact-ID selection |
| Same-name incompatible/unowned drift | Conflict; never overwrite |
| Denied/unreadable | Unknown, not absent |

Read exact dependency IDs first. Enumerate only FIND selections within the chosen
scope, all pages. Offer choices rather than demanding remembered IDs/model names.
Never scan unrelated resource types/subscriptions. Reuse resolved choices,
not stale verification; retain complete selected-boundary inventories and fresh
pre-write checks.
Search owner separates operation-compatible reuse from new-service defaults;
no existing keys/identity/network/tag changes to fit provisioning.
Other selected dependencies still require material region/SKU/capacity,
identity/network/auth/tags/model/version/access readback.
Never alter shared configuration to fit. Minimal lexical File needs no model;
vectorization adds embeddings; synthesis/nonminimal KB reasoning adds chat;
standard File adds CU, with independently selected embeddings/chat, not a KB.
Skip model discovery on minimal lexical/extractive paths without model dependencies.

## Azure Policy diagnostics after creation failure

Do not enumerate or refresh policy as a preflight for plans, approvals, creation,
delegation, retrieval or reuse. Ordinary resource, identity, quota, network,
cost and definition checks still apply. Preserve known organizational requirements
and user-approved security settings; no policy scan is not a compliance claim.
Do not knowingly submit a noncompliant request just to obtain an error.

Only read policy when an Azure resource creation failure gives evidence that
policy may be responsible, such as `RequestDisallowedByPolicy`, a policy
assignment/definition ID, or policy evaluation details in deployment errors.
First inspect the actual failure: a 403 alone is not proof of policy denial.
Authentication, RBAC, network, quota and invalid-body errors use their own
diagnostics, not a policy scan. Distinguish ARM from data-plane operations.

Preserve the original status/code/message/request ID, operation, exact target,
approved body and completed writes. Follow referenced assignment/definition IDs
and relevant initiative members first. Only if that evidence requires it,
inspect assignments at the failed target's scope and applicable ancestors,
following every page within that narrowed scope. Never audit the whole
subscription or management-group hierarchy by default; no global azqr scan.
Resolve relevant parameters/defaults, effects, modes, enforcementMode,
overrides/selectors, notScopes and exemptions/expiry only to explain this failure.
Audit/disabled/non-enforcing policy is not an enforced denial.

Missing/unreadable policy details are diagnostic warnings, not new pre-creation
blockers or proof of compliance. Keep the original creation failure unresolved
if the cause or remedy cannot be established; hand off exact missing IDs to the
resource/policy owner. Never turn an actual Azure denial into a warning/success.

Propose only a compliant correction, retaining exact required settings and tag
values from authoritative input or one focused question. Never invent an owner
or silently change region/SKU, permissions, networking or cost. Bind diagnostic
evidence and body changes to a new `plan_fingerprint` and confirmation; pass
them to delegated owners. A changed plan needs approval before retry.
No unconditional policy refresh is required. Read back required settings and
policy-applied changes after creation.

Known noncompliance (`azure-policy-noncompliant`) or a known required setting
that cannot reach the request (`azure-policy-setting-unsupported`) still blocks.
Never disable policy, create an exemption, alter an assignment, or retry through
another name/surface to bypass it. Reconcile ambiguous writes read-only before
any retry; never assume a failed command created nothing.
If no writes occurred, use the [shared blocked shape](platform-contracts.md):
`blocked_at: verification`, original code/message in `first_blocker`,
HTTP status in `first_blocker.status`, request ID in `first_blocker.request_id`,
and diagnostic `warnings`. Unavailable status/request IDs are `null`.
After completed or ambiguous writes, return `partial` with remaining ownership.
Cleanup remains separately approved.

Return dependencies/ownership and content assessment/uncertainty,
answer needs and source mode for the calling KB owner; resume KB plus validated
retrieval, never downscope to infrastructure/source-only. Technical-plan approval
does not resolve unknown content structure; unavailable CU never implies Minimal.
Preserve approval for its concrete unchanged Search artifact; never preapprove unknown bodies.
Source/KB mutations and cleanup need their own approvals.
Checkpoints are partial; preserve shared/reused resources.
