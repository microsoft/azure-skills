# Retained retrieval verification

[Owner](../knowledge-bases/retrieve.md): **opt-in offline audit**.
Default `audit_status: not-requested`: no paired questions, bundle or helper run.
Skipping the audit never means verified retrieval, nor blocks creation/ordinary queries.
No hand-authored Q&A required. Reuse user questions or propose title/content and
unrelated questions. Authorized content samples support drafts with source locators;
structural assessment alone does not. Never invent ground truth from audited answers.
No samples/questions: defer audit. Assistant assembles approved captures, not users.
Sample, query and retention consent differ; retrieval can invoke models/cost/data.
Expected answers are not inputs; missing opted-in evidence remains unverified.

## Offline CLI

```text
python "<skill-dir>/helpers/retrieval_verify.py" --input "<private-bundle>/audit.json"
```

No network/auth/models/writes/uploads/retries/cleanup or citation-URL following.
Use retained responses, not custom parsers/dumps or new queries.
Never change effort/output/models/permissions/limits.

Exit `0`: `review-required`, **not acceptance**. Exit `2`: `blocked`.
`overall_pass` is always false. `structural_status`: `passed`/`unverified`/`failed`;
failure dominates. Review semantics separately. REST isn't agent proof;
offline timestamps don't prove live provenance.

## Closed input

One source, two exact requests; paths resolve beneath the input's directory.
Reject absolute/traversing/link paths; URI/network paths block before filesystem
parsing on every platform.
UTF-8 JSON: input/snapshot 1 MiB each, response 5 MiB each, nesting 48,
arrays at most 1000 entries. Duplicate keys, malformed/truncated JSON, missing
payloads and non-200 HTTP (including 206) cannot pass.

```json
{
  "schema_version":"1.0","endpoint":"https://svc.search.windows.net",
  "api_version":"2026-08-01-preview","knowledge_base_name":"manuals-kb",
  "source_name":"manuals","source_kind":"file",
  "expected_source":{"path":"manuals/install.md","file_id":"file-123"},
  "before":"before.json","after":"after.json",
  "customer": {
    "query":"What are the installation steps?",
    "approved":true,"basis":"content",
    "request":{"intents":[{"type":"semantic","search":"What are the installation steps?"}]},
    "response":"customer.json","captured_at":"2026-09-14T12:01:00Z"
  },
  "unrelated": {
    "query":"What is the population of Neptune?",
    "approved":true,"basis":"unrelated",
    "request":{"intents":[{"type":"semantic","search":"What is the population of Neptune?"}]},
    "response":"unrelated.json","captured_at":"2026-09-14T12:02:00Z"
  }
}
```

Never refresh timestamps. Questions differ; `basis`: `title`/`content` versus
`unrelated` records judgment, not semantic classification. File `path`: exact `fileName`.
For Blob/ADLS use `source_kind: azureBlob`, `path` as exact native `blobUrl`,
and `etag` instead of `file_id`.

Local snapshot:
`captured_at`, `endpoint`, `api_version`, `knowledge_base`, `knowledge_source`,
`original`. Definitions are complete retained GET bodies with `@odata.etag`;
KB `knowledgeSources` must be exactly `[{"name":"<source_name>"}]`.
`original`: uniquely selected successful File-list record across all retained pages,
with `fileName`, `fileId`, `lastUpdatedAt`, `errorMessage: null`.
For Blob, use `{ "url":"<original blob URL>",
"etag":"<original HEAD ETag>" }`, not an indexed chunk.
Bind to authorized inventory; no file listing/Blob HEAD/content inspection
or verification of the operator's unique selection.

Definitions/originals must match exactly, including ETags/models. Order:
before ≤ both responses ≤ after ≤ current time, with before at most one hour old.
Missing/unsupported/old evidence blocks; retain failure, request evidence, no ingestion
replay. Equality isn't ingestion-version proof or atomic Storage.

Responses: `knowledge_base_retrieve.py` envelopes (`http_status`, `response_body`).
Optional producer metadata: `status` must be `response-received`/`blocked`;
`operation` must be `retrieve`. Other values block. `blocked` needs a
`first_blocker` object and always fails; no blocker on success.
Keep exact errors/request IDs private.
Output: codes/counts/pointers/hashes and first error/warning locations, never
messages/documents/paths/questions/secrets/IDs. Caps: 40 findings/20 diagnostics;
total counts and failure severity stay accurate.

## Wire and identity limits

GA `2026-04-01`: Blob minimal/extractive; GET has no mode/effort fields.
Preview `2026-08-01-preview`: File/Blob/ADLS, minimal/low/medium, extractive/synthesis;
snapshot selects mode/effort/model. Minimal uses `intents` above; low/medium uses
`{"messages":[{"role":"user","content":[{"type":"text","text":"<query>"}]}]}`.
Overrides block. Synthesis/low/medium need KB models, not invocation proof.

REST `response[].content[].text` is JSON-encoded extract rows with `ref_id` in
extractive mode; synthesis uses native `[ref_id:<id>]` markers. All text blocks
are inspected. Used IDs must resolve to unique `references[].id`, then integer
`activitySource` to the selected source activity. `activity[].error` fails;
`activity[].warning` leaves completeness unverified, including token/score drops.
Absent/null diagnostics are empty. Warnings must be strings (empty allowed);
errors must be objects, even `{}` fails. Wrong types block before truthiness.

Native File references expose `docName`, **not File ID**. Blob references expose
`blobUrl`, **not ETag**. Thus path-only native citations correctly return
`original-identity-not-in-native-citation`, not a pass. `docKey`, `citationUrl`,
reference IDs and chunk `sourceData.id` are never original identity/version proof.
`sourceData` is schema-dependent and can be null.

`expected_source.identity_field` is only an operator-declared value comparison.
`declared_identity_value_matches` counts equality, not original-source proof.
`original_identity` stays `unverified`; the native File ID/ETag gap remains even
with matching arbitrary data. Missing values are unverified; mismatches fail.
No attestation upgrades a mapping. No stronger binding contract is implemented.
Don't invent fields, relabel chunks, fill missing data or retrofit indexes.

Unrelated extractive needs serialized `[]` with no references, not missing blocks;
this proves only structural absence. Synthesis without citations/references
**does not prove semantic abstention**: [review](../references/abstention.md) all
claims/exact-output requirements. Unused references aren't answer citations.
No keyword/phrase matching.

## Filename search limitation — explain before ingestion

File/Blob expose no supported switch for searchable generated filenames.
File user metadata isn't searchable/filterable; listing `search`/`prefix` isn't
KB full-text retrieval. Citation/filter fields need actual `searchable: true`.
Filename words can still match document content.
No generated-index patches, reuploads or extra metadata/schema/models.
Customer-managed searchable fields need separate design/cost/data approval,
not an option silently added to these executors.

Authorities: failure/conflict/uncertainty only.
Checked 2026-09-14:
- [Retrieve wire definitions](https://learn.microsoft.com/rest/api/searchservice/knowledge-retrieval/retrieve?view=rest-searchservice-2026-08-01-preview)
- [GA retrieve](https://learn.microsoft.com/rest/api/searchservice/knowledge-retrieval/retrieve?view=rest-searchservice-2026-04-01)
- [Response and references](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve#review-the-response)
- [Synthesis citations](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-answer-synthesis)
- [File metadata and listing](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-file#list-and-filter-files)
- [Source configuration schema](https://learn.microsoft.com/rest/api/searchservice/knowledge-sources/create-or-update?view=rest-searchservice-2026-08-01-preview)
