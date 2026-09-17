# Deterministic helper contracts

Read before planning/approval; scope discovery.
Owners assess content/ambiguity/roles/consent. [Private output](private-artifacts.md).
Inspect source only on `blocked`/`partial`.

## Common envelope and process contract

UTF-8 JSON:

```json
{"schema_version":"1.0","plan":{},"approval":{"confirmed":true,"fingerprint":"sha256:<canonical-plan-digest>"}}
```

Canonical JSON: UTF-8, key-sorted, ASCII-escaped, compact. Approve the unchanged
plan; helpers verify fingerprints. Exclude credentials, tokens, keys, SAS,
passwords, content and secret-bearing connection strings.
Use CLI tokens. File CU: MI or approved ARM/ENV; never retain secrets.
Envelope, approval, plan, nested controls and file records are
closed schemas: undeclared fields block before authentication.
`desired` remains a complete service body. Results recursively redact secret fields.
Azure Policy evaluation belongs to the creation owner, not these helpers.
[Bootstrap](bootstrap-contracts.md): no preflight policy reads.
Bind known requirements and child fingerprint in the parent plan; no policy precheck.
Never add undeclared policy/tag fields; if required settings cannot reach the supported request body,
return `azure-policy-setting-unsupported` before creation.

Mutation commands emit compact JSON to stdout: exit `0` is `completed`, `2` no-write `blocked`,
`3` written/ambiguous `partial`. Preserve JSON/exit status.
Read same identity after ambiguous writes. Unacknowledged Search creates stay
`partial`: `resources_remaining.reused`, not owned. Otherwise prove approved state/absence.

429: [read recovery](throttle-recovery.md), plus File queue retry below.

File/Blob/ADLS and Search apply: [_progress.py](_progress.py):
stderr JSONL; `--no-progress` disables. Planning/discovery stays quiet.
Libraries: `progress=Progress("<workflow>")`; children share one terminal event.
Bounded activity/remaining checks, elapsed seconds and counts.
Same stage: once/second; transitions/terminal: immediate.
File POST: five-second heartbeat, no polling/ETA; metadata proves File ingestion;
cycle updates aren't unique documents; ARM readiness isn't KB/retrieval/data-plane proof.
I/O failure: `progress-output-failed` warning; primary failures/execution unchanged.
Failed native stderr drains to null at shutdown; custom sinks untouched. Final JSON is authoritative.

## File source application

`python helpers/file_source.py --plan request.json`: read-only;
unapproved `execution_input`/`approval_summary`; exit `0` is `planned`, not readiness.
See [request/example](../knowledge-sources/create-file.md#proposed-plan).
Require `extraction_mode`; [optional embeddings](vector-contracts.md) are independent.
Planning: no bootstrap/roles/uploads/cleanup/approval; owner-owned requirements.
Fresh exact reuse sets `execution_required`/`mutation_approval_required` false;
no approval/execution. Create: approve the unchanged envelope:

```text
python helpers/file_source.py --input approved.json --cleanup-receipt-dir <private> --upload-receipt-dir <journal>
```

Require `operation: reconcile-and-ingest`, `cleanup_approved: false`,
`owner`, `source` and `ingestion`. Children target the same endpoint/name/API/owner.
Validate both before mutation; reconcile before upload/readback.
ACKs/journal: [resume](file-upload-recovery.md).
Reuse requires exact markers, never new files or per-file cleanup.
Parent/approved upload-only routes. `source` uses the
[reconciliation shape](#search-resource-reconciliation) with `kind: "file"`;
`ingestion`:

```json
{"operation":"ingest","endpoint":"https://svc.search.windows.net","name":"src","api_version":"2026-08-01-preview","local_root":"<root>","service_tier":"basic","extraction_mode":"minimal","owner":"o@x","cleanup_approved":false,"files":[{"path":"guide.txt","size":123,"mtime_ns":1700000000000000000,"sha256":"sha256:<64-hex>","media_type":"text/plain"}],"inventory_digest":"sha256:<64-hex>","expected_server_inventory_digest":"sha256:<64-hex>"}
```

## Search resource reconciliation

```text
python helpers/search_reconcile.py --input <approved-envelope.json>
```

Require `operation: reconcile`, `outcome`, `resource_type`, `endpoint`, `name`,
`api_version`, `action`, complete approved `desired`, `owner`, and
`cleanup_approved: false`. Use `action: create`, or approved `action: update`
with `expected_etag`. Exact existing state is zero-write.

Blob/ADLS plans also require `source_evidence` with `verified: true` and an
`inventory_digest`. ADLS requires `path_verified: true`, `acl_verified: true`.
These attest reconciliation, not evidence collection/readiness: apply through
the Blob parent. File `standard`: `ai_services_managed_identity` or
`ai_services_key_acquisition` via File parent, or existing `ai_services_api_key_environment`.

KB `--plan`: [intent/wire/approval](kb-contracts.md); save unapproved `execution_input`,
never hand-build bodies/hashes. `verified_source` binds `verified: true`, `name`,
normalized `definition_digest`; fresh same-API GET must match before create/update/reuse.
GA omits preview fields/models. Low/medium needs a separate chat model;
model-free agent retrieval requires preview minimal/extractive.

For cleanup, [plan](../lifecycle/cleanup.md), then use the same executor.
Bind `operation: delete`, `plan_kind: cleanup`, `cleanup_approved: true`,
`expected_etag`, and `owned_definition_digest`. Recheck ownership; verify absence.

## Blob/ADLS source application

Blob/ADLS alone loads [folder scope/bounds/drift/cleanup](blob-contracts.md).
`blob_source.py --discover` inventories; `--plan` builds unapproved artifacts
or verifies approval-free reuse;
`--input` applies the approved parent and monitors ingestion. Search
reconciliation alone never proves Blob readiness.

## File ingestion internals

`file_source.py` invokes this child after validating both plans.
Standalone CLI never authorizes new uploads.

Reject path/inventory/extraction/server-state/marker drift. Sequential uploads;
one final inventory. Only per-file 415 permits continuation; systemic failures stop.
[File 429](file-upload-recovery.md): one bounded retry. POST: 180s; reads: 60s.
Timeout/409/5xx: read proof, never POST replay. Metadata proves ingestion, not
retrieval; status-only ACKs remain pending.
Never return bytes/local root.

## Existing Prompt Agent fallback

Only for unavailable MCP/missing connection/version operations;
never authorization denial/conflicting state:

```text
python helpers/prompt_connect.py --input <approved-envelope.json>
```

The plan requires `operation: connect`, `sdk_major: 2`, exact project resource
ID and matching endpoint identity, `connection`, `agent`, `rbac_verified`, `allowed_tools:
["knowledge_base_retrieve"]`, `require_approval: "never"`,
`permission_forwarding`, `owner`, and `cleanup_approved: false`.
The [fallback](../agents/connect-prompt-sdk-fallback.md) defines `--plan`:
intent yields unapproved `execution_input` + summary; hashes stay internal.
Legacy inputs omit dependency/version snapshots.
Approve grounding changes. Forwarding
is either `{"mode":"not-applicable"}` or
`{"mode":"structured-input","name":"search_auth_token"}`.
Reuse one complete match; multiple matches block.
ARM uses `Microsoft.CognitiveServices/accounts/projects/connections`.
Optional boolean `connection.is_shared_to_all` defaults to `true`.
Fallback defines normalization/bounded warnings for creation,
ambiguous-write recovery/reuse. `agent_invocation: not-run` isn't E2E proof.

Prompt cleanup (planner above blocks unproven connection consumers):

```text
python helpers/prompt_cleanup.py --input <approved-envelope.json>
```

Bind `operation: delete`, `plan_kind: cleanup`, `cleanup_approved: true`,
`sdk_major: 2`, exact project identity and `agent`/`connection` with
`run_owned: true`, exact identity and `owned_definition_digest`.
Connections also bind `expected_etag`. Delete version before connection;
verify absence; preserve prior versions/project/model/KB/roles.
