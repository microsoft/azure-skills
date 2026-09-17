# Bounded throttled read recovery

Read on HTTP 429 during Search post-PUT readback, File post-upload/zero-write
inventory verification, or Blob checkpoint source/generated-definition reads.
For File batch partial outcomes and uploads after creation, use
[upload-only continuation](file-upload-recovery.md); do not rerun source creation.

`_common.ReadRecovery`: one delay opportunity per identity read sequence or complete
File inventory, never per page. Wait **before** readback after write 429;
after acknowledged writes, GET 429 permits one delayed GET. This shared transport
never retries mutations. Only the documented [File queue-429 route](file-upload-recovery.md)
permits one bounded same-operation upload retry. Never replay unknown mutations
or change URL/token/endpoint; redirects stay disabled.
Close real HTTP 429 error responses before waiting, without reading their bodies.
Closure failure blocks delayed recovery while preserving the original HTTP
failure/request ID and a sanitized cleanup diagnostic.

`Retry-After`: nonnegative ASCII seconds or HTTP-date (past means zero).
Case-insensitive; duplicates/malformed/missing fields use a diagnosed 1-second
fallback. Oversized fields fail closed. Maximum server-directed wait: 30 seconds;
never shorten longer valid delays. Total sequence: 60 seconds, including waits
and response bodies; stricter request/inventory limits win (200 requests including
the retry). No remaining budget/persistent 429 stops this sequence. File continuation
requires original ACK/journal evidence and new approval for never-attempted files.

Preserve original mutation error/ACK, bounded sanitized failed/successful read IDs
and private receipts. Missing creation ACK never becomes ownership.
Persistence failure is terminal before recovery. Other statuses, planning/discovery,
ARM/Storage, ingestion polling and deletion retain their existing policies.
Clocks/sleeper are internal injectable dependencies, not CLI/approval controls.

File upload proof keeps its existing exact marker/hash semantics; Search GET match
without creation ACK remains partial observation, never cleanup authorization.
Blob checkpoint recovery still requires original ACK/ETag/binding/definition proof.
Do not replace missing proof with successful delayed reads, reset an indexer,
or conflate synchronous File ingestion proof with separate retrieval verification.

## File backoff across invocations

File journals additionally enforce server restrictions across creation, resume
planning and newly approved execution. No context/token lookup or verification
GET bypasses a pending restriction. Fresh approval does not waive server delay.
An in-operation wait above 30s still stops; a valid 60s server interval remains
blocked until its retained **UTC Unix-seconds not-before**, not a new 30s budget.
No cross-invocation sleep/retry loop or portable monotonic deadline is invented.

Canonical `RetryAfter(kind,value)` is unchanged, including `overlong`'s zero
sentinel. Native HTTP errors also carry `RetryAfterTiming(received_at_utc,
not_before_utc, server_delay_seconds)`: sanitized portable timing, not raw headers.
Date/RFC850 resolution uses receipt-time UTC; missing/invalid headers get a
recorded, diagnosed 1s fallback only when that observation is known. Typed-only
missing/invalid/overlong metadata without timing is unresolved, never zero wait.

New private runs declare `backoff_version: "1.0"`. At most 200 immutable chained
`backoff-NNNN.json` entries bind plan, request method/URL digest, request ID,
typed metadata, UTC timing and upload-attempt provenance. Upload 429 results bind
their event digest. One exclusive `pending-request.json` precedes every journaled
request; it clears only after completion/backoff persistence. A crash or failed
receipt cannot silently lose a received restriction. Maximum journal: 1003 files.
Receipt finalization failures retain successful mutation ACKs and stop requests.

`file_batch.backoff` exposes clear/waiting/elapsed/unresolved status and safe UTC
timing. Expired restrictions allow only otherwise eligible uploads under the
unchanged approval/identity/corpus rules. Unrepresentable delays, clock regression,
unfinished requests or legacy 429 without timing block before network access.
Legacy non-429 evidence remains usable under existing guards. No file timestamp,
fresh approval, manual journal edit or GET-derived ownership repairs missing proof;
retain source/receipts and obtain scoped operator recovery review.

## HTTP authorities

Authorities: failure/conflict/uncertainty only.

[RFC 9110 section 10.2.3](https://www.rfc-editor.org/rfc/rfc9110.html#name-retry-after)
defines `Retry-After = HTTP-date / delay-seconds`; `delay-seconds = 1*DIGIT`
is a nonnegative integer measured from receipt of the response.
[RFC 6585 section 4](https://www.rfc-editor.org/rfc/rfc6585.html#section-4)
says 429 may include Retry-After; limiting may apply per resource, server or
credentials. These references do not authorize write retries. Keep the server's
minimum wait; an over-budget delay stops rather than being shortened.
