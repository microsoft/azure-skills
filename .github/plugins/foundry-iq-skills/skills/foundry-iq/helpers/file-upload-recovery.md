# File upload continuation and partial batches

After partial File creation, retain the source. Never rerun creation, infer MI
from redacted GET, or recover by recreation/deletion/reset/new roles.
Generic File MI reuse/provenance guards remain unchanged.

## Retain original evidence before creation

```text
python helpers/file_source.py --input <original-approved.json> --cleanup-receipt-dir <private-receipts> --upload-receipt-dir <separate-private-empty-directory>
```

Use the [private directory helper](private-artifacts.md); no automatic directory/
ACL changes. The required journal retains original approval/context, actual
conditional source PUT ACK/request ID/ETag, exclusive **pre-POST** attempts and
separate upload responses. Never edit/remove/reconstruct entries. Integrity isn't
a service signature: retain exclusive control, no concurrent writers.

File CLI creation requires protected `--cleanup-receipt-dir` and
`--upload-receipt-dir` pre-write; separate directories, no guessed paths. Plan with
`--execution-output <new-private-plan.json>`; show reference/counts, not
hash-bearing envelopes. Plan JSON/library and non-File policies are unchanged.

Persistence failure stops requests. An attempt without result stays uncertain,
even if POST wasn't sent. Missing ACK/ETag cannot come from GET. Journals neither
replace [cleanup provenance](../lifecycle/cleanup.md) nor authorize deletion.
Without originals: retain source, `file-upload-provenance-missing`, not
"recreate required".

## Supported upload-only plan

Closed request:

```json
{"schema_version":"1.0","receipt_directory":"<absolute-original-private-directory>"}
```

```text
python helpers/file_upload.py --plan resume-request.json --execution-output <new-private-resume.json>
python helpers/file_upload.py --input <newly-approved-resume.json>
```

Planning is read-only: an **unapproved**, closed version `1.0` `resume-file-uploads`
envelope binds original plan/creation ACK/journal digests, owner, exact
never-attempted ordinals and receipt directory;
`cleanup_approved` stays false. Review and newly approve these uploads. An empty
eligible list needs no mutation or execution; use the returned observation.
Never edit ordinals/hashes to authorize attempted files.

Execution validates the original unchanged approved corpus (paths, full hashes,
size, timestamps, mode, metadata), tenant/subscription/principal, source URL/API/
definition/ACK ETag, and applicable CU account/Search MI/role/network snapshots.
It neither acquires CU keys nor changes authentication. It invokes only existing
metadata GETs and direct File upload POSTs using the original Search identity;
no source PUT, source update, new role, indexer operation, deletion, KB or model call.
POST targets the original validated
`/knowledgesources('<name>')/files?api-version=2026-08-01-preview&pageSize=200`
multipart contract; approval/privacy gates apply.

Continuation excludes previously attempted files, including exhausted 429 retries,
timeout/409/5xx and interrupted attempts. Only the original operation may retry its
received File-upload 429 once, as below. An immediate or delayed **empty** inventory
never proves in-flight termination for unknown outcomes. Positive exact file-ID/
marker/hash/size readback can prove completed ingestion, but never invents an
upload ACK or source ownership.
Drift blocks; never repair by write.

## Bounded batching and truthful progress

File upload is synchronous: extraction, chunking, embedding, indexing and metadata
persistence finish before success. No File indexer, schedule or asynchronous status
polling. Each sequential POST has a 180-second processing/response allowance,
separate from the 60-second read budget; stricter approved outer deadlines win.
Timeout is not remote cancellation. Retain 200/201 ACKs without relisting source/
full inventory after every healthy file. One final bounded inventory checks the
batch; follow validated `@odata.nextLink` exactly, without rebuilding parameters.
A per-file 415 permits independent continuation. Auth/access, deadlines,
persistence, drift and unknown outcomes stop new uploads. Repeated 429, or later
429 after the operation's one retry opportunity, stops without more reads/sleeps.
Preserve prior confirmed files; never hammer the remaining corpus.

[429 recovery](throttle-recovery.md) supplies one server-respecting delay/read
opportunity, at most 30 seconds waiting/60 seconds per complete read sequence,
including all pages and response reads. Overlong delays stop, not shorten.
Journal-retained UTC backoff blocks resume planning/execution before any network;
fresh approval never waives it. `file_batch.backoff` reports waiting/unresolved/
elapsed. Legacy 429 without timing stays unresolved; no invented deadline.
`--no-progress` disables observations. Otherwise stderr emits counts, a `waiting`
event with the bounded HTTP-429 delay, and terminal state. During POST, an immediate
and then five-second content-free heartbeat reports ordinal/total/attempt, elapsed
time and already ingested count: "1/25 ingested; processing file 2/25". This observer
never makes requests. No within-file percentage, ETA, filenames or private content.
Increment completion only after ACK/metadata proof and required receipt persistence.

`file_batch.files` records bounded relative names/full hashes, upload state,
verification state and sanitized request IDs. Counts distinguish:
`accepted` (original 200/201 ACK), `confirmed` (exact file-ID/markers without
reported error), `failed`, `pending` (ACK but not confirmed),
`unverified` (uncertain attempt), and `not_attempted`.
Accepted overlaps verification counts; do not sum it with them.
`ingested` counts synchronous completion proved by valid ACK metadata or exact
completed-file readback. A status-only ACK is insufficient. Original ACK file IDs
remain binding even if its remaining metadata is incomplete. Failed readback stays
partial while preserving known prior ingestion; `retrieval` stays `unverified`.
File completion does not prove OCR quality or KB retrieval.

Report "24 ingested, one failed/unverified" only with this proof; otherwise
distinguish accepted/pending. Preserve outcomes, not a blanket blocker. A subset
handoff must disclose pending files may appear and subset isolation is not proven;
any KB use still needs its existing separate approval. No automatic KB writes.

## One documented queue-rejection retry

The official File guide identifies upload HTTP 429 as a full processing queue and
recommends bounded parallelism/exponential backoff; Retry-After is not guaranteed.
Only this File upload route permits one same-operation retry across the batch,
not per file. No private throttle marker/error text is required. Honor valid
Retry-After; missing/invalid metadata uses the diagnosed first backoff step of one
second. Shared 30-second wait/60-second complete preflight limits apply.
After waiting, revalidate unchanged source/corpus and one fresh bounded inventory.
Positive proof avoids another POST; absence is not the retry authority: the
received queue-rejection 429 is. Persist exclusive original/retry attempt and
result records when journaling. Retry the original URL, token, multipart bytes/
boundary and approved payload; source creation happens once.

The MI canary's stricter one-upload approval forbids this retry. No PUT/DELETE/
update retry, new roles or auth substitution. Each upload creates a new file ID,
even for the same filename; no filename-idempotency key exists. Timeout/504/409/
5xx remain unknown, never replayable from empty inventory or elapsed time.
`file-upload-retry-safety-unproven` retains that blocker. Exhausted files stay
failed; continuation uploads only never-attempted files under fresh approval,
not another attempt at an exhausted file.

Authorities: failure/conflict/uncertainty only.
[File upload/troubleshooting](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-file).
