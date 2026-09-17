# Concealed Blob binding and read-only recovery

For concealed Blob/ADLS credentials or missing checkpoints; no repair/cleanup.

## What proves binding

Redaction is **not a mismatch**. Source and mutable datasource binding are distinct:

1. Fresh `azureBlobParameters.connectionString` exposes selected `ResourceId`;
   or unchanged approved keyless wire/creation acknowledgement binds source
   endpoint/name/API/ETag/definition and generated IDs.
2. Source and generated definitions match selected type/container/prefix,
   system-assigned identity, datasource/indexer/skillset/index relationships and
   approved timing. Child Storage binding requires current ResourceId readback,
   including the sanitized read below when concealed. Read all four.
3. Bounded Storage inventories and ADLS ACL/property observations match the original
   inventory. CLI context remains unchanged throughout observation.

Missing/null/empty or `<redacted>` connection values disclose no credential.
Opaque strings, malformed credential objects, another ResourceId, account keys/SAS
(even masked keys), another identity or conflicting relationships still block.
Planning/execution/vector source readbacks share this rule; never echo credentials.

V3 compares credential-free core separately from ETags. Initially hidden snapshots
retain `binding_proof: unverified`, not readiness; actual binding must be observed.
Concealment changes warn. Each verification pass permits one extra exact HTTPS GET:
`GET datasources('{name}')?api-version={original-version}&includeConnectionString=true`.
Both APIs support **sanitized** Blob/ADLS readback: ResourceId for managed identity,
masked keys/SAS; never raw credentials.
Require the exact selected keyless ResourceId and identical **current**
plain/sanitized ETag/core; the original checkpoint ETag may differ.
No redirects/other options/retries; 60-second/8-MiB bounds.
Sanitization/decryption failure can return null: not proof.
Concealed, masked, malformed, wrong-account or raced readback remains
`datasource-binding-unverified`. Retain resources; investigate the specific gap.
Root identity/names/old receipts cannot prove mutable child credentials.
No key retrieval, source repair or invented immutability.
Retain current proof separately in `datasource_binding_observations`;
never relabel checkpoint hashes.
Legacy full-hash changes fail closed; no core projection is reconstructed.
Legacy concealed readback may match a retained visible-ResourceId full preimage
at the unchanged child ETag; a concealed-only preimage still needs sanitized proof.
Cleanup always retains strict original full-digest/ETag checks.
See [readiness semantics](blob-readiness-recheck.md) and
[indexer timing](blob-indexer-observation.md). Readback is not a lock.

## Checkpoint missing after creation

New-source modes retain private approved input and use:

```text
python helpers/blob_source.py --input <approved.json> --receipt-dir <absolute-private-directory>
```

After successful `If-None-Match: *` PUT, **before the first post-write GET**, retain exclusive/
flushed `<operation_id>.blob-write.json`: approved wire digest/URL/condition,
response status/request ID/ETags/generated IDs, original operation/cutoff/context.
`recheck_write_acknowledgement` identifies it. No tokens/credentials/text;
acknowledgement is not readback/readiness.

Use body `@odata.etag` or HTTP `ETag`; conflicts block.
Missing both: never borrow a later GET ETag. Retain acknowledgement and report
`creation-version-unproven`; intervening edits are possible.
Duplicate/conflicting ETags stay recorded. Ambiguous creates retain the original error;
`resources_remaining.reused` means observation, never creation ownership.
After exact version-bound source readback, retain separate `.blob-ack.json`;
after generated checks, `.blob-readiness.json`. Never overwrite earlier evidence.
`recheck_acknowledgement` selects the enriched record, or write record if enrichment
failed; `recheck_checkpoint` describes the full checkpoint. Persistence failure
preserves the first error and acknowledged owned resources; no write retry.
429: [read recovery](../helpers/throttle-recovery.md); no ownership proof.

After denied/interrupted GET, retain first error/request ID and acknowledgement.
When authorized reads resume:

```text
python helpers/blob_recheck.py --recover <original-approved.json> --receipt <acknowledgement.json> --receipt-dir <absolute-private-directory>
python helpers/blob_recheck.py --input <original-approved.json> --receipt <operation_id.blob-readiness.json>
```

`--recover` accepts either acknowledgement. Verify original context, successful
conditional-write provenance, exact response/source ETag, definition/generated
bindings, inventory and before/after configuration. Missing PUT-generated IDs
require fresh exact source-version readback, never inferred names.
Preserve original operation/cutoff/ownership; no timestamp or write proof is invented.
Only a new local checkpoint is written; never overwrite evidence.
`outcome: blob-readiness-recovery-capture`, `status: completed` means checkpoint
retained, with `readiness.status: unverified`. Run the second command next.
Recovery observes current configuration, never a historical revision.

## Older creation, no checkpoint

Planner `reuse_input_file`/`reuse_result_file` bind concealed source accounts;
retain fresh unapproved reuse `execution_input`.
Never edit creation artifacts into reuse.

```text
python helpers/blob_recheck.py --capture <reuse-input.json> --receipt-dir <absolute-private-directory> --reuse-input-file <approved-create.json> --reuse-result-file <completed-create.json>
python helpers/blob_recheck.py --input <reuse-input.json> --receipt <new-operation.blob-readiness.json> --reuse-input-file <approved-create.json> --reuse-result-file <completed-create.json>
```

Private reuse schema `3.2` binds the pair's canonical digest; recheck requires that
validated pair. Verify current source identity/ETag/definition/generated IDs,
owner/inventory against creation proof. Booleans/snippets/partial results cannot prove it.

Fresh observation, not recovered creation/consent/ownership/historical CLI identity.
Bind current context/cutoff and exclude first completion. Without a later qualifying
cycle, unscheduled reuse remains unverified; never start/reset an indexer to force it.

## Readiness and next action

Recovery: Search/Storage GETs and ADLS metadata HEADs only.
No queries/model calls, PUT, indexer run/reset, deletes, RBAC or data mutation.

Native verification requires a relevant nonempty completed cycle, zero failed/skipped
items, valid times/counters, no active cycle/relevant errors/future completion.
Checkpoints/acknowledgements cannot replace
[nonempty creation proof](blob-vector-readiness.md) for zero-work vector reuse.

Snippets prove only query text. Report actually observed indexed content separately
from unverified source/KB readiness. Never issue queries solely for this report.

Unknown binding: inspect exact definitions/retained evidence. Resolve denied reads
with the access owner; not CU unsupported or cleanup-only.

Lost cutoff/readback/context, ambiguous PUTs or missing records cannot prove
ownership/readiness. Name missing evidence; no manufactured receipts or guessed times.

Preserve original failure; return to finish authorized KB attachment, retrieval and agent steps;
not overall completion. Cleanup needs separate approval; preserve shared data/roles.

## Authorities

Authorities: failure/conflict/uncertainty only.
[Blob source/generated pipeline](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-blob),
[datasource GET identity/credentials](https://learn.microsoft.com/rest/api/searchservice/data-sources/get?view=rest-searchservice-2026-04-01).
Supplied service-source contract: AzureSearch
`2e241af8939a0891836b78278df113dab31a5964` datasource GET and
`GetSanitizedBlobConnectionString`; source inspection, not live evidence or immutability.
