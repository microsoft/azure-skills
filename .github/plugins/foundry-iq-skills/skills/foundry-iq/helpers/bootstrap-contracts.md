# Search bootstrap

**New Basic/standard Search in an existing group**.
Other prerequisites/cleanup: [native bootstrap](../references/bootstrap-azure.md).

Progress: stderr; `--no-progress` disables.

## Choices

Python 3.12+, signed-in CLI on Windows/POSIX; no login/install/context switch.
No preflight policy reads.
Prerequisites: **owner-verified references**, not helper-verified.
1–256 printable characters; punctuation allowed.
Errors omit values.

Creation: `search`/`create`. Existing operations: [intake](search-intake-contracts.md);
legacy `reuse` stays strict, never hardens.
New locations fold ASCII case/whitespace (`East US` → `eastus`);
Not availability proof; bodies/hashes stay unchanged.
Basic: 1–3 replicas/one partition; standard: 1–12 replicas/1/2/3/4/6/12 partitions.
Fixed `SystemAssigned`, keyless auth and public networking; no role changes.
Non-secret tags; creation adds operation/owner tags.

```json
{"schema_version":"2.0","resource_kind":"search","action":"create",
"subscription_id":"00000000-0000-0000-0000-000000000001","tenant_id":"00000000-0000-0000-0000-000000000002",
"resource_group":"rg1","name":"mysearchservice","location":"westus","sku":"basic","replicas":1,"partitions":1,
"public_network_access":"Enabled","tags":{"project":"knowledge"},"owner":"operator",
"prerequisites":{"quota":"checked; enough","pricing":"approved","network":"approved public","requirements":"settings","exclusive_name_authority":"exclusive name"},
"limits":{"command_seconds":5,"wait_seconds":10,"wait_interval_seconds":1},"receipt_dir":"<absolute-private-directory>"}
```

Replace examples/limits. Reuse: `exclusive_name_authority: null`;
required tags match; no ownership transfer.

Region scope (closed):

```json
{"schema_version":"2.0","subscription_id":"<guid>","tenant_id":"<guid>","receipt_dir":"<private-dir>","limits":{"command_seconds":5}}
```

No RG/name/SKU: account check plus one `az rest` GET:
`/subscriptions/<sub>/providers/Microsoft.Search?api-version=2021-04-01`.
`searchServices.locations` supplies canonical `available_locations` (1–256).
Exit 0: `discovered`, no approval/artifact.
Create plan/apply: one fresh region GET each, including retained artifacts; no cache.
Unknown: `bootstrap-region-unsupported` plus choices;
denied/malformed: blocked. Reuse skips catalogs. Not SKU/quota/capacity/model/residency proof.

```text
python "<skill-root>/helpers/bootstrap_azure.py" --regions scope.json
python "<skill-root>/helpers/bootstrap_azure.py" --plan choices.json
python "<skill-root>/helpers/bootstrap_azure.py" --apply "<private-directory>/<artifact_id>.plan.json" --approve
```

`--plan` uses Azure reads/**local private writes**: `<artifact_id>.plan.json`
body, before-state, choices, time, unapproved envelope.
Stdout: `artifact_id`/`approval_summary`, no paths/errors/hashes.
Labels: caller attestation, not helper verification; exact references stay private.
Show resource/network/capacity/tags/cost/limits; `--approve` consents once.
No cached consent or user checksums.

15-minute expiry; submission markers prevent retries.
On drift/failure/expiry/changed choices, rerun `--plan`; discard consent.
Reconcile uncertainty; no suffix-create/body/hash edits.
Schema 1.0: regenerate (`bootstrap-contract-version`). Removed inputs
`max_polls`/`poll_seconds`/`poll_interval_seconds` are rejected.

## Execution

Argv: `az account show --subscription`, `az group show --name --subscription`,
Search ARM GET/PUT API `2025-05-01`. PUT uses `--body` then **one**
`"@" + str(body_path)` argument, Content-Type/client-request-ID headers.
POSIX runs `az` directly; Windows MSI/ZIP uses bundled `python.exe -IBm azure.cli`.
Other Windows layouts block.

Only normally returned target `ResourceNotFound` proves absence.
Fresh principal/tenant/subscription/group/exact-name absence precede one PUT.
GET/PUT is **not atomic**: require exclusive name authority.
Mandatory atomicity: `bootstrap-concurrency-unresolved`, no invented conditionals.

Reuse: two fresh material readbacks, required configuration/tags,
keyless identity/principal/tenant, endpoint, provisioning succeeded/status running.
`reused`: no mutation approval/executor or ownership adoption.
Wait uses the same identity; existence is not readiness.

After PUT: `az resource wait --ids <id> --api-version 2025-05-01
--custom <generated-condition> --interval <wait_interval_seconds> --timeout <wait_seconds>`.
Fixed `properties`: succeeded/running or terminal states, lower/title/uppercase.
No caller expressions/custom polling.
Final raw GET establishes material match/ownership **before** readiness.
Wait failure remains primary even with ready GET; provider evidence is secondary.

Limits: command 1–60 seconds, wait 1–900, interval 1–30.
Wait/final GET: separate `wait_seconds`/`command_seconds`;
sum is not an end-to-end deadline.
`subprocess.run`: argv, `shell=False`, best-effort timeout/cleanup.
CLI/OS/filesystems prevent hard time/process-tree/request-count guarantees.
No PID or confirmed-cleanup claim. Captured output is rejected **after capture**
above 1 MiB per stream: not a streaming cap or memory bound. Input/body/receipt
limits remain 1 MiB. Timeout/execution/receipt failure after attempted PUT is partial.

Checks: target, principal/tenant, capacity/SKU, auth/network, identity,
required tags, ARM readiness. Metadata/ordering/unrelated tags, ID/enum casing,
equivalent optional defaults do not need another approval.
Never default missing material fields or return extra tags.
Material conflict, unknown ownership or failed readiness blocks/returns partial.

## Evidence and failure

Existing absolute private directory **outside the plugin**.
No symlinks/reparse paths. POSIX: directory-FD creation, identity/owner/private-mode
rechecks; exclusive safe leaves, mode 0600.
POSIX semantics required; later pathname uses are not pinned.
Windows checks owner/DACL (owner, SYSTEM, Administrators), not handle-relative
creation; `chmod` does not establish Windows privacy. No ACL changes.
Same-user/admin tampering is possible; unprovable privacy blocks.
Mocked/DrvFS is not native-filesystem or Azure evidence.

Flushed receipts: operation/target/body/argv, client-request ID, readbacks/digests,
first error code/status/request ID, ownership. No raw errors/output/policy values/tokens/documents.
Message digest/`message_withheld`; secret-free labels/tags.
CLI file logging/dynamic installation: process-disabled.

Creation-only policy diagnostics:
`RequestDisallowedByPolicy`, supported policy IDs or policy-violation details.
Provider error/statusDetails, never tags/configuration.
A bare 403/RBAC/network/quota failure triggers no policy calls.
Preserve first failure; diagnostic/receipt errors are secondary warnings.
At most eight referenced assignments/selected-subscription definitions
within 60 seconds: `az policy assignment show --name --scope`
and `az policy definition show --name --subscription`. No lists or global scans.
Built-ins/management groups/initiatives/exemptions/missing references need
the policy owner. No compliance/applicability proof, policy changes, write retries
or correction approval.

Exit 0: `planned`/fresh `reused`/applied `completed` (ARM only).
Data-plane access/ingestion/retrieval stay **unverified**.
Exit 2: `blocked`, no confirmed/ambiguous Azure writes.
Exit 3: `partial`, `first_failure`, `attempted_writes`, `resources_remaining`;
unproven ownership is `unverified`, never run-owned.
Receipt failure: block before submission, partial handoff afterward.
No automatic rollback/deletion. Cleanup always needs separate consent and fresh
ownership/configuration/children/scoped-role evidence.

Authorities: failure/conflict/uncertainty only.

[Native wait](https://learn.microsoft.com/en-us/cli/azure/resource#az-resource-wait);
[location metadata](https://learn.microsoft.com/rest/api/resources/subscriptions/list-locations);
[provider GET](https://learn.microsoft.com/rest/api/resources/providers/get?view=rest-resources-2021-04-01).
