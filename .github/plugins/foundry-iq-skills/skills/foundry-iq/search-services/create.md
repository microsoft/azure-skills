# Create or reuse a Search service

## When to use

Create/ready-reuse Search for direct/File/Blob/KB requests.

## Do not use

Not classic Search index/query/app work or administration.
No existing-resource hardening to fit a template. Unsupported operations block;
never change keys, identity, networking or tags to make reuse pass.

## Inputs and discovery order

Reuse prompt/session/workspace; otherwise `az account show` supplies caller/tenant/default subscription.
Explicit scope wins; no silent `az account set`. Missing CLI/sign-in blocks;
account context is not access proof. Reads need no approval.
One focused question before enumeration if resource/intent unresolved:
**USE EXISTING / FIND CANDIDATES / CREATE NEW**. Carry answers across handoffs.

| Input | Why needed | Required? | Discovery order | Safe default | If missing or unanswered | Reconfirmation trigger |
|---|---|---|---|---|---|---|
| Scope/group/region | Target | Before plan | CLI/IDs | Propose existing | Offer choices | Scope |
| Service/action | Intent | Before plan | Exact Azure GET | Recommend reuse | Reuse/new/another | Action/ID |
| Capacity/auth/network/cost | Cost/access | Before write | Readback/prices | Preserve | Ask | Settings |
| Owner/tags/requirements/receipts/limits | Execution | Before plan | Evidence/contract | Bounded/private | Ask | Requirements/limits |

## Decisions

Honor explicit reuse/new intent; never repeat resolved choices. Read supplied IDs first.
Use [Search intake](../helpers/search-intake-contracts.md):

```text
python helpers/search_intake.py --select intake.json
```

Supplied identity: exact/minimum scoped reads. Only FIND CANDIDATES lists in
known RG, else selected sub; all pages, five-row display, cross-region rows/counts.
Never unrelated resource types/subscriptions or absence/uniqueness from a subset.
CREATE NEW: collision read, no service inventory.

Use the **selected source/KB mode and execution helper**, not creation defaults.
Recheck actual `operation` before planning. Allow keys-enabled Entra-compatible
reuse without key use/configuration changes. MI remains required for actual
File CU-MI/Blob/embedding/KB-chat needs. Private/UAMI selection is unsupported.
Statistics GET proves caller read, not write RBAC/feature-region/outbound access:
owner verifies remaining API/tier/region/data boundaries. Unknown is not a pass.
No speculative model discovery/calls or semantic/vector requirements for model-free lexical paths.
Hybrid embeddings imply neither CU nor KB chat.

After actual compatibility checks, offer compatible choices; never rank by name.
Show excluded/unknown reasons. An incompatible explicit selection stays blocked:
ask another/new; never modify it or silently switch.
FIND still needs a choice even for one candidate;
multiple compatible services require exact-ID selection behind displayed names.
No match in a narrower scope is not subscription-wide absence.
Unreadable/denied is unknown, not absent. New intent requires exact-name absence;
existing/conflicting state is not permission to overwrite or suffix-create.

Only FIND for an unresolved group uses `az group list --subscription <sub>`.
Propose task-derived name/group/owner and supported region near data, respecting
residency. Small public-network trial: recommend Basic, one replica/partition,
subject to price/quota/requirements; offer Standard for scale. Not a production
SLA or automatic capacity choice.

Creation planning requires an **existing ready resource group**.
If absent, use [resource-group-only prerequisite](../references/bootstrap-azure.md#resource-group-only-prerequisite):
approve RG-only, verify readiness, then resume.
No other dispatch or unknown-body approval.

Unresolved region: `--regions scope.json`; present canonical `available_locations`
for selection. Freeform answers need Search-specific `--plan` validation before approval.
New Search: `az search usage list --location <region> --subscription <sub>`;
Quota is not capacity; verify prices/requirements.
Ready reuse skips setup/catalog discovery;
requires no embeddings, chat, CU or Storage provisioning.

## Proposed plan

Operational reuse: qualified `selected` evidence, `mutation_approval_required: false`,
without an apply step or mutation consent.
reuse intent always needs fresh readbacks through Search intake, not strict bootstrap reuse.

Creation only: Read [bootstrap helper contract](../helpers/bootstrap-contracts.md): schema 2.0 choices/storage/limits.
Do not author nested execution envelopes; hashes stay internal.
ASCII case/whitespace: `East US` → `eastus`; not availability proof.
Creation: reuse a valid unexpired artifact for unchanged choices; otherwise plan.
```text
python "<skill-root>/helpers/bootstrap_azure.py" --plan choices.json
```

`action: create`. Planning reads Azure; writes private unapproved
`<artifact_id>.plan.json`, returns approval summary; no Azure writes.
New only: Basic/Standard, disabled local auth, public networking, system MI/capacity/tags.

## Confirmation

Disclose exact target/group/region, SKU/capacity/cost, network/auth,
system identity, tags/owner, limits, intended write and retained resources.
Obtain actual consent before the write; silence or a stored approval flag is not consent.
Reuse valid consolidated approval for this exact retained Search artifact
without another question or regeneration.
Never extend that approval to unknown future bodies, source/KB writes or cleanup.
Target/cost/access/identity/operation drift invalidates it; harmless
metadata/defaults/ordering or casing does not renew consent.

## Mutation

After approval:

```text
python "<skill-root>/helpers/bootstrap_azure.py" --apply "<private-directory>/<artifact_id>.plan.json" --approve
```

Helper revalidates artifact/context/supported region/fresh exact-name absence, then one approved
`az rest` PUT (`2025-05-01`, body-file `@`).
No write retry/deletion/role assignment.
GET/PUT is not atomic: exclusive new-name authority is required.
Expired/used/changed: replan, never edit envelopes.

## Verification

Creation: `az resource wait`, then authoritative raw GET verifies target and
required material settings. Matching precedes
ownership/readiness claims. Require provisioning succeeded, status running,
endpoint and system identity/principal/tenant; existence is not ready.
Wait failure remains primary even if the final GET is ready.
CLI timeout/cleanup: best-effort; rejection is post-capture, not a memory
or hard end-to-end bound.

ARM readiness is **not** Search data-plane authorization, role propagation,
source ingestion, vector verification or KB grounded retrieval; caller checks required.

## Failure and partial completion

Preserve first code/status/request ID, attempted writes and private receipt ID.
Blocked before writes; partial after writes/uncertainty. Retain
run-owned versus unverified resources. Names do not prove ownership.
Only policy-implicated creation failure loads
[policy diagnostics](../references/search-substrate.md#azure-policy-diagnostics-after-creation-failure);
no preflight policy audit. Secondary diagnosis cannot replace the original failure,
authorize changes or prove compliance. Reconcile uncertainty read-only.

## Cleanup

Cleanup is unapproved and separate; the helper does not execute it.
Preserve shared/reused resources. If requested, hand off
[native cleanup](../references/bootstrap-azure.md#cleanup)
with retained operation evidence, fresh exclusive ownership/configuration,
children/scoped roles and separate approval. Never delete services still in use;
failed commands do not prove absence.

## Return contract

Return selection/choice blockers or `planned`, applied `completed`, `blocked`/`partial`;
artifact/receipt/resource IDs, endpoint/settings, writes/ownership/remaining resources.
Planning isn't readiness; ARM isn't data-plane/ingestion/retrieval proof.
Keep paths/raw errors/hashes private.
Resume the original caller, not new KS/KB calls.

## References

Other links conditional.
