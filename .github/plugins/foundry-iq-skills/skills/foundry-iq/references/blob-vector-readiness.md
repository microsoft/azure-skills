# Blob vector readiness after a no-change cycle

For concealed source credentials or missing checkpoints, use
[binding/recovery](blob-binding-evidence.md). Actual conflicting keys/accounts
are not redaction. An acknowledgement is not completed nonempty ingestion proof.

Required for the [vector verifier](../helpers/vector-contracts.md) when the latest
Blob/ADLS synchronization processed zero items. Zero work alone is not ingestion
proof; the original nonempty-cycle rule remains the default.

For a later successful zero-work cycle, retain paired `reuse_input_file`/
`reuse_result_file` creation receipts even with an unredacted Storage binding.
These are the unchanged approved creation input and completed Blob source result,
not hand-authored attestations, indexer history, or a prior query answer.
Missing or invalid receipts block; never rewrite historical evidence.

Require prior nonempty zero-failure/zero-skip ingestion after both recorded
`not_before` bounds: the creation receipt's bound and this verification request's
bound. Its completion must precede the current cycle. Verify the same owner,
source endpoint/name/API/definition/ETag, Storage boundary, generated identities,
and before/after inventory. The latest cycle must still be complete, with valid
counters, zero failures/skips, no relevant errors, and no current synchronization.
Current source/index/vector configuration and complete Storage/ACL checks remain
mandatory. No history lookup or forced sync.

Latest zero-work counters remain unchanged in evidence; `prior_ingestion` records
the earlier synchronization separately. `ingestion_evidence_digest` seals both
retained records into the query snapshot. Changed receipts or readiness basis
require a new plan and approval; existing query consent cannot authorize this
new basis. The digest binds local evidence, not a service signature or source lock.

This adds no cloud calls, uploads, source mutations or indexer runs. Prior
ingestion is not current retrieval proof: the separately approved vector query
must still return matching content/citation, with unchanged post-query snapshots.
Missing historical request IDs remain unavailable, never reconstructed.
Optional `readiness.watch` v1 must match the retained completed cycle; paused,
malformed or inconsistent metadata blocks. Legacy results without it remain valid.
Watch counters never replace the original nonempty zero-failure proof.

A [read-only timeout recheck](blob-readiness-recheck.md) uses a pre-ingestion
checkpoint, not this completed nonempty creation receipt. Neither that checkpoint
nor its recheck output substitutes for this proof; keep the two contracts separate.
