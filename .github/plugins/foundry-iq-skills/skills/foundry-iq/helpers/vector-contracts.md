# Embeddings and vector verification

File/Blob/ADLS; existing models only. No provisioning/catalogs/role changes/
installs/index repairs/cleanup.
New unresolved intent: recommend hybrid; keyword-only skips this contract.

## Supported choices

`minimal` is extraction, not retrieval mode. Lexical omits `embeddingModel`:
no source embedding model. Vectors and CU are independent choices for both
File/local uploads and Blob/ADLS containers; see the [source matrix](blob-cu-contracts.md).
File `--plan` supports minimal and standard CU.
KB reasoning/answer
synthesis and agent tool use are separate; index verification proves neither.

File/ADLS: `2026-08-01-preview`; Blob also `2026-04-01`.
Set File `vectorization: "azureOpenAI"` or Blob `processing: "minimal-vector"` / `"standard-cu"`;
add this **closed** `embedding` object to the owning procedure's intent:

```json
{"endpoint":"https://models.openai.azure.com","deployment":"embed","model":"text-embedding-3-large","dimensions":"service-managed","model_version":"deployment-managed","auth":"system-assigned","prerequisites":{"deployment":"<fresh selected deployment/model readback>","identity":"<Search managed identity and model role assignment readback>","network":"<approved model network reachability evidence>"}}
```

All fields required; `deployment` is not a model family.
Models: `text-embedding-ada-002`, `text-embedding-3-small`,
`text-embedding-3-large`. HTTPS endpoints:
`openai.azure.com`, `services.ai.azure.com`, `cognitiveservices.azure.com`;
no keys, credentials, paths, query strings, explicit ports or APIM in this slice.
`auth`: `system-assigned`, using existing Search identity. Ingestion/query readbacks
allow only absent/null/empty-string `apiKey` and absent/null `authIdentity`.
Masked/nonempty/malformed keys or other identities block without echoing values.
Embedding guards preserve File CU's MI or explicit ARM/ENV channel;
legacy modes remain.

Owner: read deployment/model and effective Search-to-model RBAC/network:
`az cognitiveservices account deployment show --subscription <sub> --resource-group <group> --name <account> --deployment-name <deployment>`
plus identity/role/network readbacks, not test embeddings. Record evidence
references: **not independently verified by the planner**. Missing evidence
blocks; refresh before approval.

Source guidance requires Cognitive Services User; the Azure OpenAI vectorizer
also documents Cognitive Services OpenAI User. Policy owner verifies effective
model data actions at that scope; never guess equivalence or assign roles.

Wire: `embeddingModel.kind: azureOpenAI`,
`azureOpenAIParameters.resourceUri/deploymentId/modelName/authIdentity`.
Neither API exposes dimensions or model-version pins: custom values block.
Observe generated dimensions: ada-002 requires 1536; 3-small allows 1–1536;
3-large allows 1–3072. Deployment upgrades remain owner-managed; Search readback
cannot pin or prove a model version.

## Source application

Planners return `planned`, unapproved `execution_input`, hash-free
`approval_summary` of endpoint/deployment/auth/cost/data movement.
No model/query calls; inconsistent choices/definitions block.
Save only `execution_input`; apply via the owner's `--input` after explicit
mutation/embedding-cost/data-transfer consent. Fresh exact reuse needs no
mutation approval/executor: not readiness or retrieval.

## Read-only verification plan

Retain artifact; use generated fields, never inferred names.
Use index-get or REST GET
`/indexes('<index>')?api-version=<source-api>` provides fields/profiles/vectorizers. Never modify or switch indexes.

```text
python helpers/source_vector.py --plan verify.json
```

File:

```json
{"schema_version":"1.0","source_plan_file":"source-execution.json","vector_field":"vector","content_field":"content","citation_field":"citation","expected_citation":"guide.txt","expected_text":"Example local data","query":"Where are examples?","mode":"vector","k":3,"not_before":null}
```

`mode`: vector/hybrid; `k`: 1–10. Query/citation/text: nonempty,
at most 4096 characters. Three distinct simple field names; use actual schema
and corpus provenance, not illustrative names. No credentials/tokens.
Blob/ADLS `not_before`: explicit UTC synchronization start lower bound for this
ingestion, never an arbitrary old success. Redacted Storage bindings need paired
`reuse_input_file`/`reuse_result_file` creation receipts per the
[Blob proof contract](blob-contracts.md), loaded only when needed.

Checks: artifact/source/index identities/ETags, dimensions/profile/algorithm/vectorizer,
endpoint/deployment/model/auth, retrievable content/citation/key. Unknown/redacted/
duplicate/conflicting metadata blocks. Permission sources/indexes require KB retrieval.

File: complete matching IDs/markers, no reported errors; uploads are synchronous.
Blob/ADLS: bounded complete Storage/ACL observations; relevant completed nonempty
cycle, zero failures/skips, no current cycle. Never start indexers.
Zero-work: [required proof](../references/blob-vector-readiness.md).
Stale/missing readiness blocks. Reread source/index; snapshots are not locks.

Exit `0`: `planned`, configuration/ingestion observations, retrieval **unverified**,
unapproved `execution_input`, query/model/cost summary. Retain referenced artifacts;
keep private paths/fingerprints machine-only, never ask users to repeat hashes.

## Separately approved query

Save `execution_input`; explicitly approve query text, model calls/cost and
content transfer, then:

```text
python helpers/source_vector.py --input approved-vector-query.json
```

Reobserve source, inventories/readiness and index; drift blocks before POST.
One vector-only request to the source-owned index:
`POST /indexes('<index>')/docs/search.post.search?api-version=<source-api>`,
`vectorQueries: [{kind: text, text: <query>, fields: <vector-field>, k: <k>}]`,
`top: k`, `minimumCoverage: 100`, selected key/content/citation fields.
Hybrid additionally sends `search`, `searchFields`, `queryType: simple` in a
second request **only after independent vector-only success**. Never fall back
to lexical retrieval. No KB/chat/semantic answers.

Require HTTP 200/request ID, full coverage, nonempty bounded unique hits, finite
scores, matching expected citation **and** content. Partial/error/continuation/
malformed/mismatched responses block. Reobserve afterward and reject drift.
`retrieval-verified`: this runtime probe passed, not corpus-wide quality.
Evidence: request IDs/digests/counts, not raw documents/citations.
Tests/mocks are never cloud evidence.

Blocked queries: exit `2`, zero resource writes, attempted count/possible billing;
no ambiguous-query retries. Source writes retain `partial`/separate cleanup.
After definition/model/identity/policy/data drift, rerun source/verification
`--plan`, replace artifacts and discard consent.

Bounds: each observation uses existing File limits (200 pages/records, 60-second
listing budget, 1 MiB/page) or the source artifact's complete Blob/ADLS discovery
limits. It adds four Search definition/index GETs and, for Blob, one status GET.
One planning observation; two bracket approved queries. At most two query
POSTs, each capped at 8 MiB and a 60-second body-read budget; added GETs use
the same caps. Overflow blocks. No redirects or unbounded background work.
Body budgets are **not** hard DNS/connect/header/scheduling deadlines.

## Schemas

Authorities: failure/conflict/uncertainty only.

- [Preview schema](https://learn.microsoft.com/rest/api/searchservice/knowledge-sources/create?view=rest-searchservice-2026-08-01-preview) and [GA schema](https://learn.microsoft.com/rest/api/searchservice/knowledge-sources/create?view=rest-searchservice-2026-04-01)
- [Vectorizer parameters/dimensions/auth](https://learn.microsoft.com/azure/search/vector-search-vectorizer-azure-open-ai)
- [Search POST](https://learn.microsoft.com/rest/api/searchservice/documents/search-post?view=rest-searchservice-2026-04-01)
