# Optional Blob Content Understanding branch

Read only for `processing: standard-cu` in the [Blob procedure](../knowledge-sources/create-azure-blob.md).
Selected Search/Storage/AI Services only; no provisioning, uploads, asset store,
permission changes or KB creation. Resolve processing before planning; never
downgrade CU or add it to minimal-vector.

## Availability and dependencies

Read [shared CU ingestion](../references/cu-ingestion.md) for independent model
purposes, necessary checks and non-executable pending-dependency drafts.
For portal/required-field questions,
use the [API/service/helper settings matrix](../references/standard-cu.md#source-settings-api-versus-helper).

Blob requires CU-capable `AIServices` in a supported region with an embedding deployment,
not Search `embeddingModel` or source vectors.
Image verbalization/source chat are disabled.
Ingestion does not choose KB reasoning, reranking, query mode or synthesis.

Use the existing Search system-assigned identity with Cognitive Services User
on that account; Storage stays ResourceId/keyless with Storage
Blob Data Reader. Do not copy File CU credential channels or enable local auth.
The Blob documentation's `aiServices` keyless configuration omits `apiKey`.
Keys, user-assigned identities, private networking, schedules, asset stores and
permission ingestion are outside this standard branch.

Verify CU capability/region/deployments, effective Search identity/RBAC and
reachability through exact readbacks.
`configuration` references selected processing/required deployment evidence.
Existing dependencies permit planning; no setup-owner or `azd` prerequisite.
Do not ask for a separate account-configuration confirmation.
Default mappings need contract/observed-error evidence; never change them.
`cu-prerequisite-missing`: name missing evidence, not a generic setup gate.
No provisioning/model tests or default extraction downgrade.

## Closed intent

Use the ordinary [Blob intent](blob-contracts.md#planning), set
`processing: standard-cu` and add this required object:

```json
{"content_understanding":{"endpoint":"https://models.services.ai.azure.com","auth":"system-assigned","prerequisites":{"resource":"<CU capability/region readback>","configuration":"<selected processing/required deployment evidence>","identity":"<Search identity and AI Services role readback>","network":"<AI Services reachability evidence>"}}}
```

Fields required; references: 1–4096 characters.
Omit `embedding` (or use null in the intent) to leave source vectors off.
Only when selected, add the closed [embedding choice](vector-contracts.md).
CU and source-vector endpoints are independently validated; they need not match.
Combine CU/auth/source/vector costs and data consent; no manual credential/MI
confirmation. Missing setup uses approved native bootstrap.
A single trailing slash is immaterial.
Custom CU endpoints, URL paths/queries/ports and credentials block.
Minimal modes omit `content_understanding`.
Private artifacts retain choices; summaries omit references, which are attestations, not CU calls.

New CU plans emit fingerprint-bound `cu_plan_version: "1.0"`. This CU-specific
marker requires the CU choice and exact presence/value binding of optional embeddings.
Legacy approved wire-only standard artifacts, including `expected_source_absent`
and `expected_generated`, retain their original admission, guards and fingerprints.
Those generic guards predate CU planning; they do not select the new contract.
Never rewrite historical approved artifacts/receipts. Removing choices from a
marked CU artifact blocks if CU is missing or the wire still requests removed
embeddings; changing/removing its marker invalidates existing
approval. No new field is sent in the Search request.

## Wire and approval

Both GA `2026-04-01` and preview `2026-08-01-preview`
expose `azureBlobParameters.ingestionParameters` with
`contentExtractionMode: standard`, `aiServices: {"uri": "<selected-endpoint>"}`,
`disableImageVerbalization: true`, null identity/schedule.
Set `embeddingModel` only for selected source vectorization; otherwise omit it.
Preview also sets public networking and empty permission options.
ADLS remains preview-only in this helper with unchanged path/ACL controls.

Use the same `blob_source.py --plan` → private unapproved `execution_input` →
one explicit unchanged-plan approval → `--input` flow. Execution uses conditional
PUT `/knowledgesources('<name>')?api-version=<selected-version>` with
`If-None-Match: *`, exact definition GET and status GET; no direct CU API call.
Never overwrite or suffix around a collision.

CU creation also retains approved input and uses `--receipt-dir`.
Timeout/interruption: [read-only recheck](../references/blob-readiness-recheck.md),
not another PUT or direct CU call. Fresh reuse capture carries no creation ownership.

Show combined source/CU/embedding cost, access and processing changes before
approval. CU is billable with no free document allowance; selected documents
move to CU and, only if selected, source embeddings, possibly across regions.
Search retains outputs.
The CU skill uses underlying CU `2025-11-01`; Search manages that call, not a user-selectable
version. Both GA and preview Swagger
declare `embeddingModel` optional/nullable, with no required or conditional
standard-extraction vectorizer constraint. CU deployment prerequisites
must not be substituted for Search wire-field requirements.
Search and CU limits apply, including five-minute analysis timeout with possible charges.
No universal quality claim. Acceptance does not prove CU support; see
[format limits](../references/platform-interfaces.md#source-formats).

## Verification and failure

Require exact CU mode/endpoint/auth readback. Allow only absent/null/empty-string
`aiServices.apiKey` and null/absent ingestion identity. Masked/nonempty/malformed
keys or another identity return `cu-auth-conflict`, without echoing values.
Known null metadata, a single endpoint trailing slash and the documented
`resultsProcessing: rerank` default do not require manual plan edits.
Different endpoints, models, extraction, auth, scope, ETags or generated identities
block; rerun planning and discard old consent.

Acceptance proves configuration only. The owning executor requires a relevant
completed zero-failure ingestion cycle, not `active` or old success.
[Vector verification](vector-contracts.md#read-only-verification-plan), only when configured, additionally
observes generated dimensions/profile/vectorizer and nonempty zero-skip readiness.
Retrieval needs its separately approved query; neither proves extraction quality
or corpus-wide relevance. CU-only vector probes return `embedding-not-configured`,
not “CU unsupported.” Fresh exact reuse remains mutation-approval-free,
not ingestion/retrieval proof. Tests/mocks are not live evidence.

Keep the first failure/request ID. A failed post-write check is partial with
run-owned source/children retained; never automatically delete anything.
Use existing separately approved source cleanup only, never Storage,
dependencies, shared resources or role assignments.

## Authorities

Authorities: failure/conflict/uncertainty only.

[Blob prerequisites](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-blob#prerequisites),
[GA create](https://learn.microsoft.com/rest/api/searchservice/knowledge-sources/create?view=rest-searchservice-2026-04-01),
[preview create](https://learn.microsoft.com/rest/api/searchservice/knowledge-sources/create?view=rest-searchservice-2026-08-01-preview),
[CU skill](https://learn.microsoft.com/azure/search/cognitive-search-skill-content-understanding),
[GA Swagger](https://github.com/Azure/azure-rest-api-specs/blob/main/specification/search/data-plane/Search/stable/2026-04-01/search.json),
[preview Swagger](https://github.com/Azure/azure-rest-api-specs/blob/main/specification/search/data-plane/Search/preview/2026-08-01-preview/search.json).
