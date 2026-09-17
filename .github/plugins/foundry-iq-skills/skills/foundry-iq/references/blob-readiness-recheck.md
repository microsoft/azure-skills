# Blob readiness recheck

## Retained evidence

New minimal/Standard/CU, lexical/vector and admitted legacy modes/schedules:
Blob GA `2026-04-01` or preview `2026-08-01-preview`; ADLS requires preview/ACLs.
Keyless/system-assigned only; no asset stores, new settings or other connectors.
Retain original approved input; `--receipt-dir` requires an existing private
directory outside plugin. Check privacy/context before cloud work.
No mkdir/ACL changes/overwrite. Conditional PUT acknowledgement precedes post-write GET.
[Binding/recovery](blob-binding-evidence.md) owns acknowledgement recovery.
Immutable `<operation_id>.blob-readiness.json` binds approval/owner, pre-write cutoff,
context, generated identities/ETags/digests and request IDs. No credentials/text/ACLs.
Persistence failure retains partial ownership, without polling/write retry/cleanup.

### Fresh reuse capture

Retain unchanged private reuse `execution_input` (`approval.confirmed: false`):

```text
python helpers/blob_recheck.py --capture <reuse-input.json> --receipt-dir <absolute-private-directory>
```

Capture checks source/configuration/Storage/context and retains cutoff/first cycle.
Exit `0`, `blob-readiness-capture`: **checkpoint retained**, not readiness.
No writes/new ownership/polling. Creation artifacts/ambiguous PUTs cannot use capture.

Checkpoints: `3.0` creation; `3.1` reuse; `3.2` paired `binding_digest`.
Legacy 1.0/1.1/1.2 and 2.0/2.1/2.2 remain readable, never upgraded; acknowledgements stay `1.0`.
V3 retains full digest/ETag for cleanup, independent `core_digest`, allowlisted
`field_digests`, and datasource `credential_digest`.
Datasource `binding_proof` is observed ResourceId or unverified; hidden initial
snapshots cannot grant readiness. No secrets/skill text; unknown core stays protected.
Reuse retains `excluded_cycle` and no owned resources.

## Recheck only

```text
python helpers/blob_recheck.py --input <original-input.json> --receipt <operation_id.blob-readiness.json> --compact
```

Validate private UTF-8 records: no links/duplicates; bind integrity/approval/owner/
plan/ownership before reads. Public-cloud CLI tenant/subscription/principal must match;
no login/switching/grants. Tokens are ephemeral, not access-proof/locks.

Cloud reads:

- Source `GET knowledgesources('{name}')` and `/status`, original API version.
- Four exact returned `datasources`, `indexers`, `skillsets`, `indexes`:
  `GET {collection}('{name}')?api-version={original-version}`.
  Concealed datasource credentials permit one extra GET per verification pass,
  adding only `&includeConnectionString=true`: sanitized selected keyless ResourceId
  plus matching current plain/sanitized ETag/core is proof. Null/masked keys/SAS
  cannot prove binding. No redirects/retries; 60-second/8-MiB read bounds.
- Existing bounded two-pass Storage inventories plus ADLS metadata HEADs,
  before and after monitoring; both must match the original inventory digest.

Configuration brackets inventory/status: nonempty ETags, exact source/generated
identities and indexer datasource/skillset/index relationships.
For timing read [indexer observations](blob-indexer-observation.md):
equivalent formats are INFO, unconstrained timing WARNING, explicit violations block.
V3 core-equal ETag-only changes are INFO, not readiness failures.
Datasource type/container/prefix/system identity must match.
Concealment requires independent **current child** Storage binding proof.
Root identity/old receipts cannot prove mutable child credentials.
Missing proof is `datasource-binding-unverified`,
not misconfiguration. Visible conflicts/core drift block, even during ingestion.
CU/source-vector endpoint/auth checks still apply. Masked/nonempty/malformed keys
or changed identities block; no model calls or query claims.

Reuse `blob_source.monitor` with retained cutoff and bounded watch limits.
Reuse excludes its **retained** first completion (normalized times).
Require nonempty zero-failure/zero-skip completion, valid times/counters and no
errors/active cycle/future completion. Stale/denied/malformed/missing evidence blocks.
Active work at a watch limit is **paused/in-progress**, not failed ingestion.
Legacy `ingestion-timeout` uses `readiness.watch` to distinguish pauses.
Primary knowledge-source status drives [progress interpretation](blob-ingestion-progress.md).
Missing endTime waits; missing counts stay unknown. Current runs supersede older
last runs; replace counters without cross-run sums or file arithmetic.
Supplemental indexer `lastResult` reports **attempted**/failed items within the
shared status-request/time budget, never primary readiness or unique file counts.
No run/reset, queries/models, PUT/PATCH/DELETE or data/RBAC changes.

### Bounded continuation

```text
python helpers/blob_recheck.py --input <original-input.json> --receipt <checkpoint.json> --watch-seconds 1800 --watch-max-requests 300 --watch-interval 5 --compact
```

Three overrides together, only with `--input`: maxima 3600 seconds,
1000 status requests, 60-second initial interval. Otherwise use original limits.
One bounded window per invocation; no daemon/renewed approval.
Unchanged/transient reads back off exponentially to 60 seconds; progress resets.
Retry-After beyond the window/cap pauses.
Socket timeout ≤30 seconds; windows aren't hard DNS deadlines.
Ctrl+C during polling pauses; library `cancelled()` stops before the next request.
Resume the same receipt after a pause; never recreate/run/reset/delete.
`watch.latest`: actual synchronization start/state/counters, not independently ready
documents. No ETA/percentage/assumed file or pending count. Item errors remain failures;
unchanged observations don't prove a stall.

## Output

Exit `0`: source readiness only. Historical provenance: `original_run`;
fresh IDs: `read_only_evidence.request_ids`. `writes_performed: []`,
no follow-up ownership. Retrieval/KB remain unverified.
`original_run.historical_created` discloses retained creation separately.
`creation_acknowledgement` v1: state/type/name/http_status/request_id, observed before receipt IO.
`<operation_id>.blob-result.json` retains full original result/IDs/integrity for
historical reporting, not authority. `original_run.original_failure.watch` retains
v1 pause context; missing legacy results stay unavailable.
Persistence failure is terminal.
`generated_diagnostics` covers all four children with sanitized field/severity/code;
`indexer_diagnostics` retains its prior timing/binding contract.
`datasource_binding_observations`: v1 records (`schema_version`, `status` verified/
unverified, `request_id`, `plain`, `sanitized`). Read fields: `etag_digest`,
`definition_digest`, `core_digest`; unavailable sanitized read is null.
No checkpoint replacement/cleanup proof.

`--compact`: closed `blob-operation-summary` `1.1` adds versioned `readiness.progress`;
without progress retain `1.0`. Fields: status/outcome,
current writes/acknowledgement, historical creations, generated identities, readiness/watch,
first retry, current/historical failure code/status/ID (watch pauses aren't failures),
diagnostics, unique request-ID count, private evidence/checkpoint leaf files and next
decision. Full native JSON is retained privately first; without the flag output
stays compatible. No hashes/raw skills in summaries. Retention failure emits full
native output and nonzero exit, preserving the original error.

Exit `2`: blocked, not reversed creation. Preserve resources/evidence/first failure.

`--no-progress` disables stderr; libraries default silent.
Local integrity isn't service/lock/initiator proof. No reconstructed cutoffs
or replacement [zero-work vector creation proof](blob-vector-readiness.md).
Return to KB/retrieval/agent owners. Cleanup needs separate approval and strict
full-definition/ETag ownership; semantic exceptions never authorize deletion.

Authorities: failure/conflict/uncertainty only.
[Indexer status](https://learn.microsoft.com/azure/search/search-monitor-indexers).
