# Blob ingestion status and customer progress

Use when interpreting Blob/ADLS watch output, pauses, or requests for file x/y.
This is asynchronous Blob observation, not the synchronous File upload contract.
No new SDK, authentication, private-network/UAMI/asset-store or RBAC capability.
Normal invocation and receipt-backed continuation: [recheck](blob-readiness-recheck.md).

## Primary service evidence

The primary read is the selected knowledge source's
`GET knowledgesources/{name}/status?api-version={original-version}`.
The helper preserves its equivalent exact OData identity syntax.
Use the admitted `2026-04-01` or `2026-08-01-preview` version; no API substitution.
`synchronizationStatus` describes source availability, not successful ingestion.

The actual service fields are:

- `currentSynchronizationState.startTime`, `itemsUpdatesProcessed`,
  `itemsUpdatesFailed`, `itemsSkipped`, `errors`.
- `lastSynchronizationState.status`, `startTime`, `endTime`, and the same counters/errors.

Missing counters stay unknown, never zero. A missing completion `endTime` means
keep observing within the watch bounds, not a timestamp failure or completed run.

Require completion after the original cutoff, valid times/counters, zero failed
updates, no relevant errors or current cycle. `partialSuccess`/`failure` blocks
readiness even when successful work remains. Recheck also requires nonempty,
zero-skip completion and unchanged source/configuration/Storage evidence.
Source readiness is not verified KB retrieval or whole-corpus content coverage.

Current-run observations take precedence over an older last run. A newer run
replaces counters; never add runs together as unique files. After observing a
newer start, an older completion cannot finish that watch. Counter decreases
replace the observation; never infer a reset is an ingestion failure.
The guide does not promise monotonically increasing counters.

Generated indexer `/status` is supplemental, sharing the status-request/time budget.
Its top-level `running` means available, not executing/success.
Only a relevant `lastResult` supplies execution status/start/end and
`itemsProcessed` (**attempted**) / `itemsFailed`. Neither attempted items nor index
documents/chunks are unique input files; execution success can include item errors.
The indexer cannot supply missing primary source counters or readiness.
An observed active execution remains unresolved across primary reads. Require
fresh same-indexer terminal success and a primary completion ending no earlier
than that execution; start times need not be identical. Older executions cannot
clear a newer observation. Retain the resolved execution in private watch evidence.

## Customer presentation

Show the bounded helper's `message`, for example:

```text
Blob ingestion observation ingesting: item updates processed=13; failed=1; skipped=0; file total/remaining unknown (not comparable); elapsed=675s; next check=5s.
```

Do **not** turn this into "13/25 files ingested; 11 remaining".
The guide does not establish unique-file identity, processed/failed overlap, or
counter-to-snapshot equivalence. Inventory size, filtered prefixes,
`statistics.totalSynchronizations`, average items, chunks and index documents
cannot establish that denominator. This helper therefore admits no file-fraction
conversion: total/remaining stay unknown even when an inventory count is known.
No percentages, subtraction, summed retries, ETA or assumed 25-file corpus.

Unchanged observations back off; throttling and the next bounded check are visible.
Watch expiry/cancellation pauses observation; service execution is not modified.
Resume with the original input/receipt, not another create/run/reset/delete.
Repeated unchanged counters alone do not prove a stall.
Watch limits remain 3600 seconds/1000 status requests, 60-second initial interval
and backoff cap, 30-second status reads. One window per invocation; no daemon.
Native response-body deadline exhaustion also pauses when the watch expires.
A shorter read deadline with watch budget remaining is a retryable observation,
not remote ingestion failure; retain its code/ID and use the existing backoff.
Retry-After accepts bounded scalar headers or typed seconds/UTC-date metadata,
including the frozen typed protocol's year-only RFC850 century correction.
Missing/invalid metadata uses bounded backoff;
an overlong marker or delay outside this watch's wait budget pauses, never retries
early. No transport-wide retry or change to the shared File metadata contract.

Errors can contain document keys, URLs, SAS and content in `key`, `docURL`,
`componentName`, `errorMessage`, `details` and `documentationLink`.
Never echo them or follow their links. Customer errors retain sanitized
status/code and the relevant request ID; full bounded ID trace and error digests
stay private, not in progress messages. No full status JSON or ID wall.

## Narrow output contracts

Native `readiness.progress` and stderr `blob_progress` share closed schema `1.0`:

- `schema_version`, `unit: item-updates`, `denominator: not-comparable-to-files`;
  `total` and `remaining` are null.
- `phase`: ingesting, waiting, throttled, paused, completed or failed.
- `run_start`: canonical timestamp or null; `processed`, `failed`, `skipped`:
  observed nonnegative integers or null.
- `synchronization_status`: active, creating, deleting or not-reported.
- `elapsed_seconds`: finite nonnegative number; `next_check_seconds`: null
  or a finite number from 0 through 60.

Stderr adds this record and a content-free `message` only for Blob workflows.
Same-phase updates are throttled; phase changes and terminal events are immediate.
`--no-progress` suppresses stderr without changing HTTP sequence or results.

Legacy retained creation/vector receipts remain readable; new progress must match
its own completed cycle and never substitutes for ingestion proof.

Closed compact `blob-operation-summary` is `1.1` when it includes
`readiness.progress`; results without progress retain `1.0`. Original full private
results, v3 checkpoints, acknowledgements, sanitized binding proof and strict
cleanup ownership are unchanged. No generated-child edits or cleanup on timeout.

Authorities: failure/conflict/uncertainty only.
[Official Blob guide](https://learn.microsoft.com/en-us/azure/search/agentic-knowledge-source-how-to-blob?tabs=2026-08-01-preview&pivots=csharp),
updated 2026-09-02, source commit `78d82fc1240820245ee4143df9f5296641986171`.
[Indexer status](https://learn.microsoft.com/azure/search/search-monitor-indexers).
Public documentation inspection is not live ingestion evidence.
