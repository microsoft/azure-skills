# Create a Blob or ADLS Gen2 knowledge source

## When to use

One Blob/ADLS; [types/API](../references/platform-interfaces.md#source-formats).

## Do not use

No uploads/unselected boundaries/other connectors. Never modify objects.

## Inputs and discovery order

Resolve prompt/session/workspace, then
`az account show` for caller/tenant/default subscription. Explicit scope wins;
never silently switch context. Missing CLI/sign-in blocks discovery, not proof of absence.
Reads need no approval except content inspection: exact sample authorization.
Silence is not approval.
Recommend; after discovery batch compatible choices only for unresolved decisions.
Reuse informed choices; separate sample-content consent from
resource/permission/CU/source/KB approvals.

| Input | Why needed | Required? | Discovery order | Safe default | If missing or unanswered | Reconfirmation trigger |
|---|---|---|---|---|---|---|
| Scope/Search/access | Target | Pre-write | Exact Azure GET | Reuse/new | Choices | Scope/access |
| Storage/container/prefix | Data | Pre-list | URL/name | No implicit root | Choose boundary | Scope |
| Objects/ETags/versions/ACLs | Drift | Yes | Inventory | None | Read/block | Any |
| Processing/API/models | Mode | Yes | Content | No extraction default | Assess/choose | Content/mode |
| Owner/name/cost/network/cleanup | Owner | Pre-plan | Caller | [Azure user](../references/owner.md) | Override | Any |

## Decisions

Opt-in [title/content](../helpers/retrieval-verification-contracts.md); no Q&A required.
No auto-sample/query or filename defaults.

[Search operation](../search-services/create.md); [bootstrap](../references/search-substrate.md).
No routine policy reads.
Reuse Storage; never create data or a KB.

Names/URLs/unresolved accounts:
read [resource intake](../references/resource-intake.md); reuse derived fields.
After account selection, enumerate only unresolved containers:
`az storage container list --account-name <account>
--auth-mode login --subscription <sub> --num-results '*'`.
Known containers skip enumeration; validate the selected boundary directly.
Denied listing: ask for an exact container, never broaden access or infer absence.
Resolve scope; root `""` requires explicit choice.
No object inventory/download before boundary selection.
No keys/SAS; missing Storage/content: separate provisioning/upload workflow.

Missing roles: [RBAC](../references/bootstrap-azure.md#roles-readiness-and-return).
Propose least privilege; obtain consent/readback; resume planning.

Honor explicit processing choices only when informed and compatible.
Unknown content or mode/goal conflicts: read [content-fit](../references/content-fit.md).
MUST assess/clarify before planning: bounded authorized samples or questions about
text-only versus multimodal content and answer dependence.
Reuse answers; honor informed reduced outcomes.
Unavailable/declined/unreadable inspection means ask, not assume text-only.
No filename/MIME inference, silent default/downgrade or model calls.
Explain tradeoffs; obtain concrete-plan/CU/data approvals.
Vectors are independent. New unresolved search: recommend Hybrid;
confirm [tradeoffs/opt-out](../references/intent-routing.md#search-mode-choice).
Keyword-only: no embedding discovery. Lexical skips vector references.
Do not download blobs to decide.
If CU/models: [discovery](../helpers/model-discovery-contracts.md).

HNS selects ADLS; preserve case.
Blob non-root prefixes end in `/`; ADLS directories do not.
Arbitrary partial-name prefixes: never append `/` or widen.
GA `2026-04-01` minimal is Blob-only extractive; synthesis/agents/permissions
need approved preview. Permission retrieval forwards the caller's Entra token
per-request through `x-ms-query-source-authorization`, scoped to
`https://search.azure.com/.default`; never persist it.

Read [Blob contract](../helpers/blob-contracts.md); run read-only
`python helpers/blob_source.py --discover <selected-boundary.json>`.

## Proposed plan

```text
python helpers/blob_source.py --plan intent.json
```

[Intent](../helpers/blob-contracts.md#planning).
Bind dependencies/boundary/API/processing/access/read/poll limits;
public/system-assigned; no image verbalization, permissions or schedule settings.
Vectors use `processing: minimal-vector` and
[embedding choices](../helpers/vector-contracts.md).

### Opt-in Content Understanding

`processing: standard-cu`: read [CU branch](../helpers/blob-cu-contracts.md).
No provisioning/default-model/local-auth changes or probes.
`cu-prerequisite-missing`: return missing evidence to owner; never downgrade.
Combine CU/auth/data consent; no manual auth questions.

CU-only omits `embedding`. Verify CU-capable
`services.ai.azure.com` region/required models/effective access, not existence.
Search's system identity needs Cognitive Services User on CU.
Verify embedding access separately; Storage stays keyless.
No File keys/chat/asset store; CU isn't KB reasoning.

Return `planned`, `execution_input` (`approval.confirmed: false`),
`approval_summary`: changes/counts/bytes/processing/access/cost/ownership/cleanup.
Keep evidence private.

Exact reuse: no mutation approval/executor. Read source,
observe selected Storage twice; reread source/ETag/generated IDs.
Redacted bindings need approved input/successful creation result matching fresh
ETag. Unproven provenance blocks; never infer accounts from containers.
Identity/inventory/ACLs aren't ingestion readiness/retrieval.

## Confirmation

Keep immutable `plan_fingerprint`/`cleanup_approved: false`;
approve changes, not hashes; save only `execution_input`.
Refresh access/cost/data consent pre-write. Scope/object/access/definition/
model/ETag/known-requirement drift: rerun `--plan`, replace artifact and discard old consent.
Never edit nested plans or recompute hashes manually; receipts are not future consent.

## Mutation

New minimal or Standard/CU, with/without vectors: read [checkpoint/recheck](../references/blob-readiness-recheck.md);
Select an existing operator-private directory; retain approved input there before writes.
Reuse: read-only capture, never replay.

```text
python helpers/blob_source.py --input <approved-envelope.json> --receipt-dir <absolute-private-directory> --compact
```

`reconcile-and-monitor` revalidates then creates/reuses. Never update drift,
suffix-create, change schedules, or patch children.
Source helpers never assign roles; bootstrap owns access gaps.
Private ADLS needs both `blob` and `dfs` links/DNS.

## Verification

Verify core configuration/children and relevant completed cycle: zero failed items.
Require actual Storage binding. Unscheduled reuse/old success/`active` are not proof.
Inventories detect drift, not atomic snapshots; schedules evolve.
Vectors: [query verification](../helpers/vector-contracts.md#read-only-verification-plan);
deployment isn't readiness/retrieval.

## Failure and partial completion

Preserve first failure/request ID and creation. Watch expiry pauses;
resume GET-only by receipt. 403 is inaccessible, not absent.
Exit `2`: blocked/no-write; `3`: partial/ownership/separate cleanup.
No alternate name or unapproved recreate.
Use [recovery](../references/blob-binding-evidence.md); no replay.

## Cleanup

Separately approved `search_reconcile.py`: delete only run-owned source
with current ETag/owned digest; Search deletes children.
Never delete Storage, objects or reused resources.
Bootstrap owns separately approved role cleanup; unclear ownership blocks.

## Return contract

Return compact status/readiness/failure/warnings/private evidence; updates aren't files.
Pass assessment/uncertainty/answer needs/mode through prerequisites to the KB owner;
resume KB plus validated retrieval.

## References

Authorities: failure/conflict/uncertainty only.

[Official Blob procedure](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-blob).
[ADLS HEAD](https://learn.microsoft.com/rest/api/storageservices/datalakestoragegen2/path/get-properties).
