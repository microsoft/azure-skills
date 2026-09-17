# Bounded File CU MI validation

Read only for File MI uncertainty or explicitly requested live validation.
Not automatic setup, benchmark or release evidence; live validation needs
separate approval.

## Evidence and limits

Inspected AzureSearch service commit
`2e241af8939a0891836b78278df113dab31a5964`:

`ContentUnderstandingClientBuilder.cs` 33–68 selects MI without a key;
`AIServicesHelpers.cs` 68–126/181 binds Search system MI and Cognitive Services token audience.
The MI test was not run; simulated identity fixtures are not deployment proof.

Mapping paths under `/Source/Search/Product/SearchAgentCore/`:

- `DocumentExtraction/FileUploadProcessor.cs` 38–43,225–246,308–328,547–571:
  Standard CU chunks map `Content` to `snippet`, file ID to `snippet_parent_id`,
  filename to `metadata_storage_path`. Owner metadata is separate; `uid` is a
  chunk key, not the original file ID.
- `Models/KnowledgeSources/Dependencies/FileKnowledgeSourceDependencyHandler.cs`
  81–89,364–368 creates the index through the manager and retains `createdResources.index`.
- `RestClient/SearchRestIndexingPipelineManager.cs` 45–54,564–569,664–705,777–805,895–905:
  File has no language-routed alternate field. `snippet` is `Edm.String`,
  searchable/retrievable true, filterable/sortable/facetable false.

This is a pinned implementation contract, not public documentation or deployed proof.
CU may create an analyzer. One image-only PDF; omit `embeddingModel` and keep
`disableImageVerbalization: true`. No KB/chat is needed.

## Local preparation and proposed plan

Use an **existing private, owner-controlled directory**. Bootstrap primitives
validate it without directory creation or ACL rewrites.
Private output is optional; canary checkpoints are not cleanup producer receipts.

Resolve `<skill-root>` to the loaded skill directory; use native local paths.

```text
python "<skill-root>/helpers/file_cu_canary.py" --prepare "<existing-private-directory>"
```

Local preparation exclusively creates `cu-mi-probe.pdf` and
`cu-mi-probe-manifest.json`; it never overwrites files or calls Azure.
The one-page PDF contains only a generated raster image. Its random
`CUOCR` plus eight-digit marker is not a PDF text layer. Plan/apply inspect the
actual multipart producer's names, owner, metadata and headers for contamination.
Retain the manifest's marker and SHA-256.

Resolve Search/CU/role IDs from read-only discovery. Do not select financial scope,
create roles/accounts, disable local auth, revoke access or probe models to prepare.
Missing prerequisites go to the existing native bootstrap owner with concrete
separate approval. Both CU local-auth-enabled and disabled accounts are eligible;
this typed path requires existing public CU reachability without default-deny ACLs.

Create a UTF-8 canary request using the ordinary File request contract:

```json
{
  "schema_version": "1.0",
  "marker": "<manifest marker>",
  "content_field": "snippet",
  "receipt_directory": "<existing-private-directory>",
  "bounds": {"timeout_seconds":120,"max_requests":60,"max_poll_attempts":3,"poll_interval_seconds":2},
  "file_request": {
    "schema_version":"1.0",
    "api_version":"2026-08-01-preview",
    "endpoint":"https://<selected-search>.search.windows.net",
    "name":"<approved-unique-canary-name>",
    "owner":"<resolved-owner>",
    "local_root":"<prepared-private-directory>",
    "paths":["cu-mi-probe.pdf"],
    "service_tier":"<observed-tier>",
    "extraction_mode":"standard",
    "vectorization":"none",
    "rbac":{"assignments":[{"id":"<observed-caller-assignment>"}]},
    "network":{"posture":"<observed-posture>","evidence":"<readback-reference>"},
    "content_understanding":{
      "endpoint":"https://<selected-cu>.services.ai.azure.com",
      "resource_id":"<exact-CU-ARM-ID>",
      "auth":"system-assigned",
      "managed_identity":{
        "search_resource_id":"<exact-Search-ARM-ID>",
        "role_assignment_id":"<CU-ARM-ID>/providers/Microsoft.Authorization/roleAssignments/<GUID>"
      },
      "prerequisites":{
        "resource":"<capability-region-readback>",
        "configuration":"<selected-CU-processing-evidence>",
        "identity":"<scoped-role-readback>",
        "network":"<CU-reachability-evidence>"
      }
    }
  }
}
```

Replace placeholders; examples never authorize resources or costs.
Canary v1.1 pins this OCR mapping; old/changed plans need fresh approval.
`content_field` must be `snippet`; there is no override or caller-attested mapping.
Missing or mismatched generated schema returns partial, never a fallback field.

```text
python "<skill-root>/helpers/file_cu_canary.py" --plan "<canary-request.json>"
```

Planning uses GETs/local reads only, with Entra authentication for ARM/Search;
no CU key acquisition.
It requires exact-name absence, one immutable synthetic PDF, verified Search
system identity/CU-scoped Cognitive Services User, and fresh account/API/network
bindings. It retains an unapproved private `execution_input_ref` and displays the
source/auth/data/cost scope, bounds and 15-minute expiry.

## Separate live approval and execution

Approve the unchanged outer plan fingerprint only after reviewing synthetic
content movement, possible cross-region processing, CU/analyzer charges, retained
Search data and cleanup ownership. Set its `approval.confirmed` to true; do not
edit nested plans, expiry, bounds or fingerprints.

```text
python "<skill-root>/helpers/file_cu_canary.py" --input "<approved-private-canary-envelope.json>"
```

The executor composes the File planner's approved v1.2 workflow: one conditional
source PUT (`If-None-Match: *`), one multipart file upload, and bounded GETs.
No listKeys, API-key/ENV channel, KB, chat, embeddings, role grants or direct CU calls.
It rechecks identity/role/account and synthetic hash before mutation, then verifies
upload markers, Standard configuration, source ETag and generated schema.
Each of at most three rows per poll must bind the uploaded file's exact ID/path
through `snippet_parent_id`/`metadata_storage_path`; only `snippet` proves OCR.

Timeout/request/poll limits stop client work; they are **not monetary caps or remote
cancellation**. Backend work and costs may continue after a timeout.
This stricter one-upload approval forbids even queue-429 retry, auth changes or cleanup.

## Result, recovery and cleanup

Private checkpoints record start, source/upload HTTP ACK, File result and final result.
Status-only ACK is not ingestion/OCR proof; interruptions are non-atomic. Retain checkpoints
and inspect exact resources; do not replay.
Upload ACK persistence faults are terminal partial results, never ambiguous-upload
recovery. Preserve the first diagnostic and earlier writes even if later receipts fail.

`keyless-functional-pass` requires the indexed OCR marker, not only create/upload.
Search principal/role readbacks are recorded separately; backend CU principal
attribution and deployment provenance remain **unverified** without independent
telemetry. Do not promote this to a full release or universal MI support claim.
Absent OCR, changed bindings, denied access, schema gaps or exhausted bounds return
blocked/partial with existing writes and uncertainty, not a success-shaped stub.

Retain source name/ETag/definition digest, file identity/hash, generated index and
approval records. Cleanup is separately approved through the
[cleanup owner](../lifecycle/cleanup.md), requiring original verified producer
receipts, fresh ETags and exact owned scope. Canary checkpoints cannot substitute;
without those receipts, retain inventory and stop for scoped recovery review.
Do not guess deletion scope, claim ownership from ambiguous CREATE, delete shared
Search/CU/roles, or invent producer receipts.

Authorities: failure/conflict/uncertainty only.

[File source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-file),
[Search documents GET](https://learn.microsoft.com/rest/api/searchservice/documents/search-get).
