# Create a File knowledge source

## When to use

Direct uploads; no customer Storage.

## Do not use

Changing/scheduled corpora, lifecycle/DLP/permissions or overflow:
[Blob/ADLS](create-azure-blob.md). Unsupported content blocks. Never stage to Blob,
split silently, alter files or upload outside the approved root.

## Inputs and discovery order

Resolve prompt/session/workspace, then
`az account show` for caller/tenant/default subscription. Explicit scope wins;
never silently switch context. Missing CLI/sign-in blocks discovery, not proof of absence.
Reads need no approval except content inspection: exact sample authorization.
Silence is not approval.
Recommend; after discovery batch compatible choices only for unresolved decisions.
Reuse informed choices; separate sample-content consent from actual
resource/permission/CU/source/KB approvals.

| Input | Why needed | Required? | Discovery order | Safe default | If missing or unanswered | Reconfirmation trigger |
|---|---|---|---|---|---|---|
| Scope/Search/access | Target | Output before upload | Exact Azure GET | Reuse/new | Choices | Scope/access |
| Root/inventory | Data | Pre-upload | Selection/list | Never `.` | Choose root | Files |
| Owner/name/purpose/cleanup | Owner | Pre-write | Caller | [Azure user](../references/owner.md) | Override | Owner |
| Processing/models | Search | Yes | Content/choice | No extraction default | Assess/choose | Content/mode |
| API/cost/network/consent | Security | Yes | GET | Preserve | Approve plan | Cost/access |

## Decisions

Opt-in [title/content](../helpers/retrieval-verification-contracts.md); no Q&A required.
No auto-sample/query or filename defaults.

[Search operation](../search-services/create.md); [bootstrap](../references/search-substrate.md).
Resume after readback, never call Create KB.
No routine policy reads.
File-only creates no KB/synthesis model. Minimal lexical extraction needs no model;
standard independently selects CU.

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
If CU/models: [discovery](../helpers/model-discovery-contracts.md).

Reject absolute/traversing/unreadable paths or escaping links/reparse points.
Freeze path/MIME/bytes/mtime/SHA-256 in byte order; recheck pre-upload.

Prove formats, at most 200 files, per-file maximum: 50 MB for Free/Basic,
100 MB otherwise. Unknown/overflow: Blob.

- `minimal`: supported non-image content with `contentExtractionMode: minimal`.
- `standard`: `contentExtractionMode: standard`, `2026-08-01-preview`,
  CU and approved cost/security/data movement; source embeddings are optional.
  Detected images with minimal are invalid; never downgrade.

GET exact source; only FIND lists candidates. Read all file pages each run.
Reuse exact definition/inventory/index/markers.
Duplicates/inaccessible/drift block; no suffixing/upload repair.

## Proposed plan

Read [helper contracts](../helpers/contracts.md) before planning.
For standard planning, read [CU choices](../references/standard-cu.md); minimal skips it.
CU auth: verified Search MI or explicit ARM/ENV; never expose secrets.

```text
python helpers/file_source.py --plan request.json --execution-output <new-private-plan.json>
```

UTF-8:

```json
{"schema_version":"1.0","endpoint":"https://svc.search.windows.net","name":"manuals","owner":"team","local_root":"C:\\docs","paths":["guide.txt"],"service_tier":"basic","extraction_mode":"minimal","vectorization":"none","rbac":{"assignments":[{"id":"<role>","principalId":"<principal>"}]},"network":{"posture":"<posture>","evidence":"<readback>"}}
```

Tier: `free`/`basic`/`dedicated`/`serverless`. Require RBAC and
`network.posture`/`network.evidence`.
`paths`: 1–200 unique relative POSIX paths; no globs; MIME hint only.
[Types/API](../references/platform-interfaces.md#source-formats).
Vectors: `vectorization: azureOpenAI`; [choices](../helpers/vector-contracts.md).

Exit `0`: planned, not ready. [Private output](../helpers/private-artifacts.md):
retain unapproved input privately; show reference/counts, not file hashes.
Review actions/mode/access/cost/retention/cleanup.
Verify known/security requirements before consent; unapproved input blocks.
Exact reuse: `execution_required: false` and
`mutation_approval_required: false`: no approval or executor.
Reread definition/ETag after all pages; ingestion isn't retrieval.
No writes/installs/identity changes/cached consent.

## Confirmation

Retain immutable plan/`plan_fingerprint`/`cleanup_approved: false`; review choices, not hashes.
Requirements/inventory/endpoint/API/model/identity/network/role/definition/ETag
drift voids consent. Rerun `--plan`, replace the saved
`execution_input` and discard old consent; approve only new actual mutations.
Never edit nested plans or recompute hashes manually.

## Mutation

After approval:

```text
python helpers/file_source.py --input <approved.json> --cleanup-receipt-dir <private-receipts> --upload-receipt-dir <separate-empty-dir>
```

Require validated private receipts pre-write; no inferred paths/GET ownership.
`reconcile-and-ingest` validates `source`/`ingestion` agreement before writes.
Synchronous POST: 180s; final inventory.
[429](../helpers/file-upload-recovery.md): one bounded retry; create once.
Timeout/409/5xx: readback only.
Exit `2`: blocked; `3`: partial.
Never invoke children alone. Create absent sources only; reuse never uploads.
`fileParameters.ingestionParameters` binds `contentExtractionMode`;
lexical omits `embeddingModel`; vectors bind observed azureOpenAI endpoint/deployment/model.
Standard binds `aiServices.uri`; no verbalization/`chatCompletionModel`.

Block rather than downgrade to minimal.
Reject `networkAccessMode`: one index, no indexer/schedule; never patch children.

List `/knowledgesources('<source-name>')/files`; upload only absent exact inventory
entries by multipart POST; read stable file IDs.
Never modify/stage files, use Search/Storage keys/SAS, or rename an ambiguous retry.

## Verification

Verify definition/mode/dependencies, count/path/type/size/hash-to-file-ID,
zero ingestion failures, generated index/child ownership, keyless Search access,
network and unchanged inventory. Rerun discovery: stable IDs/zero writes.
Vectors: [staged verification](../helpers/vector-contracts.md);
deployment/lexical results aren't vector proof.

## Failure and partial completion

Report first failure/proved counts and progress.
[Resume](../helpers/file-upload-recovery.md); never recreate, replay uncertain
files or suggest cleanup.

## Cleanup

[Receipts](../lifecycle/cleanup.md): retain pre-create.
Separate cleanup plan/approval: delete run-owned source/children.
Never delete or alter local files, reused resources or shared roles.
`operation: delete`: owned digest/ETag; unclear ownership blocks.

## Return contract

Return status/fingerprint/IDs/API/boundary/inventory,
auth/RBAC/network/ingestion/idempotency/ownership/warnings/cleanup.
Pass assessment/uncertainty/answer needs/mode through prerequisites to the KB owner;
resume KB plus validated retrieval.
Never return content/credentials.

## References

- [Audit fields](../references/platform-contracts.md).

Authorities: failure/conflict/uncertainty only.

- [File source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-file)
