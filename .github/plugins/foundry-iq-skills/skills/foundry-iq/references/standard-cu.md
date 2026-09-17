# Standard File dependency branch

Standard only: provisioning never proves CU readiness.

Use [discovery](../helpers/model-discovery-contracts.md) for ARM `AIServices`
endpoints; never OpenAI hostname replacement.
`ContentUnderstanding` is not a documented endpoint-map key.
Missing/ambiguous metadata blocks selection; endpoints are not readiness.
Read [shared CU ingestion](cu-ingestion.md) for checks, model purposes and pending drafts.
Existing CU/deployment/access evidence permits planning; no setup-owner or `azd` prerequisite.
Do not ask for a separate account-configuration confirmation.
`prerequisites.configuration`: selected processing/required deployment evidence,
not a default-model setup certificate.
Only missing dependencies need native Azure setup; obtain separate approval.
`bootstrap-cu-contract-unresolved`: unresolved required dependency,
not for reuse. Never default to reduced extraction.

Image verbalization/source chat stay off.

Disclose auth in the existing concrete source approval, not a separate
"can you set the key?" or "is ENV ready?" question.
File system MI is implemented in inspected service code; live compatibility is
**unverified**. This is independent evidence, not nullable shared Swagger or Blob MI.
The public File example still uses a key; do not claim public/live MI validation.
New plans default to verified Search system MI; no key fallback or silent setup.

## Standard File planning

Set `extraction_mode: "standard"` and this closed `content_understanding` choice:

```json
{"endpoint":"https://cu.services.ai.azure.com","resource_id":"<CU ARM ID>","auth":"system-assigned","managed_identity":{"search_resource_id":"<Search ARM ID>","role_assignment_id":"<CU ARM ID>/providers/Microsoft.Authorization/roleAssignments/<GUID>"},"prerequisites":{"resource":"<CU readback>","configuration":"<processing/deployment evidence>","identity":"<Search MI/role readback>","network":"<reachability evidence>"}}
```

Evidence: 1–4096 characters; private artifact, not summaries.
`vectorization: "none"` omits `embeddingModel`; `azureOpenAI` needs independent
[embedding choices](../helpers/vector-contracts.md). Endpoints need not match.
Minimal omits CU choices. Neither filename nor MIME selects extraction.

`file_source.py --plan` GETs the exact CU account (`2024-10-01`) before and
after Search discovery: `AIServices`, ready provisioning, endpoint/location/network.
Planning is GET-only: no credential reads, including `listKeys`.
ARM metadata is not effective access or processing proof;
user yes/no answers are not readback proof.

MI artifacts: `file_cu_plan_version: "1.2"`, `cu_identity_state`,
`source.ai_services_managed_identity: true`. GET Search (`2025-05-01`) and the
CU-scoped role (`2022-04-01`): fingerprint running Search principal/tenant, endpoint,
unconditional Cognitive Services User and network; refresh before writes.
Missing identity/roles use packaged bootstrap under separate concrete approval;
source execution changes none. System MI requires existing public CU without
default-deny ACLs; other configurations need verified contracts, not key fallback.
Wire `aiServices.uri` without `apiKey` or ingestion `identity`; optional embedding
identity remains separate. MI does not require or change `disableLocalAuth`.

Redacted CU readback cannot prove auth. MI reuse requires `reuse_input_file` and
`reuse_result_file`: original approved v1.2 File input and completed creation result,
matching fresh definition/ETag/account/identity and complete inventory.
Stale/missing provenance or unexpected creation presence blocks.
No reingestion or key-bearing callbacks.

Legacy complete-wire/1.0 ENV and 1.1 ARM artifacts remain compatible. Explicit
`auth: "api-key-arm"` omits `managed_identity`; its fingerprint binds
`ai_services_key_acquisition`: exact account/endpoint, caller tenant/subscription/
principal, ARM version, key1 and source-PUT purpose. Key modes require explicit
`disableLocalAuth: false`; “local authentication” means key auth, not manual setup.
After approval/fresh checks, ARM `POST <exact-account-id>/listKeys` (`2024-10-01`)
selects key1 once, internally, for the exact source PUT only.
Existing `auth: "api-key-environment"` uses `api_key_environment: "CU_API_KEY"`;
another PowerShell session's ENV does not configure this helper.
Never put keys in chat, plans, logs or command arguments, ENV writes, files or receipts.
No key/account/auth fallback, rotation, permission grant or policy change.
Denied `Microsoft.CognitiveServices/accounts/listKeys/action` needs owner-approved
resolution. No debugger/locals or HTTP body logs; Python cannot guarantee zeroization.

Endpoint/auth/network/identity drift blocks. Tags are immaterial.
Location compares ASCII case/whitespace only (`East US`/`eastus`),
not region guesses or availability. Equivalent readbacks need no new approval;
real region drift blocks. Other fields stay strict; retained snapshots/fingerprints are unchanged.
For evidence uncertainty or an explicitly requested canary only,
read [bounded MI validation](file-cu-canary.md). Do not run it automatically.

Review billable CU (no daily free document allowance), content moving from Search
to CU/selected embeddings, possible cross-region processing, retention and auth.
No CU/model/Storage provisioning or KB changes are included.
Approve credential scope/purpose with these costs/data/access disclosures once,
then run `python helpers/file_source.py --input <approved.json>` from the skill root.
Material changes need refreshed approval, not repeated unchanged consent.
Exact source/ETag/file-marker reuse needs no mutation approval or credential read;
reuse is not processing/retrieval proof. Preserve upload verification, first failure,
partial ownership and separate cleanup.

## Source settings: API versus helper

The table distinguishes API requirements from helper choices.
File standard: `2026-08-01-preview`. Blob CU: GA `2026-04-01` or
August preview. ADLS preview is this helper's boundary.

| Setting | Public contract | Helper boundary |
| --- | --- | --- |
| Name/type | `name`, `kind`, parameters required | Owner/purpose: workflow inputs |
| Description | Optional text | Blob accepts null |
| Location | File: Search-managed; Blob: `connectionString`/`containerName` | No File Storage setup |
| Prefix | Blob `folderPath` optional | `prefix: ""` needs root consent |
| Extraction | `contentExtractionMode` defaults `minimal`; CU `standard` opt-in | Explicit choice; API default is not content-fit guidance |
| Embeddings | Optional/nullable `embeddingModel` | Explicit wire choice; select deployment/auth |
| Source chat | Optional `chatCompletionModel` | Verbalization off; no mandatory KB chat |
| Auth | Caller/dependency access; Blob keys/MI | File MI or explicit ARM/ENV; Search/Storage keyless |
| Advanced | Blob schedules; preview permissions/private ingestion | Blob: public/system MI, no schedule/permissions. File: no indexer/schedule or `networkAccessMode` |

Null/false/empty helper fields aren't mandatory API questions;
portal key choices don't change helper auth.

CU's embedding-deployment prerequisite is not Search `embeddingModel`;
mappings need contract/error evidence, never guesses.

[Source formats](platform-interfaces.md#source-formats) binds detected types/limits/API.
Preserve bytes; never execute scripts. Images need August standard; 415 retains ownership.
No suffix gate/mode switch: inspection informs suitability, not service admission.

File prose requires `fileParameters.ingestionParameters` despite optional Swagger;
source docs override generic inference.

## Authorities

Authorities: failure/conflict/uncertainty only.

[File documentation](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-file),
[CU account listKeys](https://learn.microsoft.com/en-us/rest/api/aiservices/accountmanagement/accounts/list-keys?view=rest-aiservices-accountmanagement-2024-10-01).
