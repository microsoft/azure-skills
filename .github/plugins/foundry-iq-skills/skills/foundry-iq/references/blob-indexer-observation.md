# Generated Blob indexer observations

Read when Blob/ADLS generated schedule or version readback differs, including
checkpoint recovery. Minimal/Standard/CU, lexical/vector use the same verifier.
This is not schedule management, write resumption or a new planner.

## Binding versus timing

| Observation | Decision |
|---|---|
| Wrong `dataSourceName`, `targetIndexName` or `skillsetName` | Hard binding failure; never a schedule warning |
| Equivalent interval/start-time formats | INFO; continue all readiness checks |
| Valid timing differs without an explicit approved constraint on that field | WARNING about possible recurring work/cost; continue verification |
| Explicit approved interval/start-time differs | Block constraint acceptance, not evidence that ingestion failed |
| Malformed/unknown schedule | Block; do not infer defaults |
| ETag-only revision | V3 core-equal observation: INFO; legacy unexplained revision: block |
| Any other indexer field changes | Hard drift failure, even alongside schedule changes |

The approved original wire's `ingestionSchedule` constrains a supplied interval
and non-null `startTime`. An omitted/null start time is unconstrained. New typed
planners require `ingestion_schedule: null`: **no schedule override**, not
guaranteed one-shot processing or absence of recurring work.
No monetary cap, no-run constraint or cost acceptance is inferred from absent
fields. Those constraints have no supported planner representation; if required,
keep their acceptance unresolved with the caller/owner, not silently verified.
Unknown schedule properties block rather than becoming invented approval.

Missing, null and scheduled observations remain distinct; pinned defaults below
are not substituted for a run's readback. If an authorized GET observes `P1D`,
disclose daily cadence and possible recurring processing/cost. Otherwise do not
invent that cadence. Neither observation is cost approval or ingestion proof.
Schedules contain only `interval` and optional `startTime`; empty objects,
null/missing intervals, unexpected properties and invalid types block.

Normalize bounded XSD day/time durations, 5 minutes through 24 hours inclusive:
`P1D`, `PT24H`, `PT1440M`, `PT86400S` are equivalent. Calendar years/months,
weeks, negatives and unsupported forms do not pass. Timestamp equivalence
requires a valid explicit timezone and exact instant, preserving up to seven
fractional digits (100 ns). Reject naive/unknown-offset timestamps, invalid dates,
leap seconds, excess precision and offsets outside +/-14:00; no rounding.

## Versioned private proof

New immutable checkpoints use `3.0` creation, `3.1` reuse, or `3.2` reuse with
paired creation binding. Write/source acknowledgements remain `1.0`.
`configuration.indexer` retains the actual ETag and:

- `digest`: complete returned child definition.
- `non_schedule_digest`: every field except `schedule` and `@odata.etag`.
- `schedule_digest`: validated canonical timing, including presence state.
- `schedule_raw_digest`: actual schedule representation and presence.
- V3 `core_digest`/`field_digests`: independent semantic configuration and safe field diagnostics.

All other fields, including unknown fields, mappings, parameters, identity and
description, remain in the non-schedule hash. V3 other-child core/binding policy:
[readiness recheck](blob-readiness-recheck.md). Source identity stays strict.

Exact snapshots pass. In V2, a changed ETag/full hash can pass only when an observed
schedule change explains it, every other observed field matches and current
approved timing constraints hold. V2 ETag-only/unexplained changes block.
V3 core-equal ETag-only changes are INFO; all explicit timing constraints still apply.
Equal full hashes with inconsistent projection/version evidence block.
Always retain actual current hashes; never substitute the old ETag as readback.
Comparisons do not modify receipts or lock resources and cannot prove unseen
intervening revisions.

Legacy `1.0`/`1.1`/`1.2` checkpoints retain exact full-hash/ETag comparison.
Legacy `1.2` still requires paired creation proof; `1.1` does not.
A changed legacy snapshot lacks a schedule preimage/projection and stays blocked;
neither a warning nor a schema-version edit upgrades that proof. Preserve it.
GET current definitions and compare legitimately retained preimages if available.
Separately planned fresh read-only reuse capture is a new observation, not
recovered historical configuration, cutoff or ownership.

## Lifecycle and safe continuation

Keep [acknowledgement-before-GET](blob-binding-evidence.md) unchanged.
Checkpointed creation captures generated configuration before polling and
rechecks after successful ingestion/source/Storage readback. Recheck observes
configuration before and after inventory/status; recovery brackets its inventory
with configuration observations before retaining a checkpoint.
Both capture/recovery results still mean **readiness unverified**.

Use existing commands with unchanged private inputs and genuine receipts:

```text
python helpers/blob_recheck.py --recover <approved.json> --receipt <acknowledgement.json> --receipt-dir <absolute-private-directory>
python helpers/blob_recheck.py --input <original.json> --receipt <checkpoint.json>
```

For a separate unowned reuse operation:

```text
python helpers/blob_recheck.py --capture <reuse.json> --receipt-dir <absolute-private-directory>
```

Follow [recheck contracts](blob-readiness-recheck.md) for private files, paired
creation proof when needed, original context/ownership/cutoff, and excluded reuse
cycles. Recovery cannot erase known contradictory retained configuration.

`indexer_diagnostics` contains severity/code, a safe field name, static message
and request ID. `indexer_observations` contains actual hashes and hashed ETag,
not raw timing/resource content. WARNING messages also appear in `warnings`;
INFO is not promoted to WARNING. First failures and acknowledged partial ownership
remain intact. A qualified cycle observed before later drift is retained, but
overall readiness returns unverified.

Warnings never bypass native cycle/error checks, Storage/ACL inventory or source
bindings. Read-only recheck additionally requires nonempty, zero-skip completion
and rejects future completion; this does not change the original monitor's
counter semantics. A checkpoint is not the separate nonempty creation proof
required for zero-work vector reuse. Snippets cannot substitute.
Denied/missing reads and unknown evidence remain
blockers with provenance. GET/ADLS metadata HEAD only; no schedule edit,
run/reset, PUT replay, new source, cleanup, query or model calls.
KB/retrieval completion and separate cleanup approval remain with their owners.

## Authorities

Authorities: failure/conflict/uncertainty only.
On uncertainty, consult [indexer scheduling](https://learn.microsoft.com/azure/search/search-howto-schedule-indexers)
for documented duration bounds, and the
[Blob generated pipeline](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-blob)
for generated resources/status. Neither proves a particular unread generated
schedule or a null knowledge-source schedule default.

Supplied read-only implementation trace: AzureSearch commit
`2e241af8939a0891836b78278df113dab31a5964`,
`Source\Search\Product\SearchAgentCore\RestClient\SearchRestIndexingPipelineManager.cs`:
`DefaultIndexingScheduleDays` is 1 (line 64); extraction passes the nullable
ingestion schedule (521-548) through indexer creation/payload construction
(297-301, 1497-1504, 1540-1544). `BuildScheduleJson` (1798-1816) maps null to
`{"interval":"P1D","startTime":null}`. This establishes that pinned implementation,
not every deployment or the reported manual run. Null-to-daily stays WARNING
when unconstrained, never semantic equivalence; explicit constraints still block.
