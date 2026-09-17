# Shared CU ingestion contract

For Standard File and indexed Blob/ADLS;
adapters own source-specific wire/auth and ingestion lifecycle.
Existing index/source/KB connection or query does not trigger CU setup or reingestion.
Unsupported connectors remain unsupported; do not add SharePoint/OneLake adapters.
Use native Azure AI Services; no project, agent, external setup skill or `azd`,
not agent-tool discovery or general AI-app setup.

## Independent dependencies

Input modality is text-only, multimodal or mixed/unknown, not a model choice.
Ask only unknown answer dependence: layout/text versus visual semantics.
Minimal extracts supported basic text; Standard CU already supports OCR/layout
to structured Markdown/text chunks without optional image descriptions.

Plan each purpose, endpoint/deployment, access and cost.
Shared accounts do not merge these choices:

| Dependency | Selected when | Purpose and boundary |
|---|---|---|
| Content Understanding | Standard extraction | Billable extraction through `AIServices`; neither source vectors nor KB reasoning. |
| Ingestion chat model | Optional image/figure descriptions selected on a supported path | Descriptions also yield text. Separate ingestion-model purpose, not an Azure RBAC role or necessarily a new physical deployment; compatible deployment reuse still requires path-specific access/cost approval. |
| Source embedding model | Hybrid/vector search selected | Azure OpenAI models (e.g. `text-embedding-3-small`), in standalone or CU's `AIServices` account; no separate account required. Embedding/data movement/vector storage costs; not extraction/chat. |
| KB chat model | Reasoning or answer synthesis selected | KB reasoning/answers: independent model/access/cost, not source embeddings. |

Current typed File/Blob planners set `disableImageVerbalization: true` and omit
`chatCompletionModel`; their new-CU validators enforce this profile. Basic CU
OCR/layout extraction remains supported. Broader service/API and generic/legacy
complete-wire compatibility is unchanged, not universally disabled.
There is no typed planner opt-in here: do not toggle flags or bypass validation.
Require only models the selected CU operation uses; a CU deployment prerequisite
does not enable Search `embeddingModel`. Never add CU because hybrid was chosen,
add source vectors because CU was chosen, or require KB chat merely for ingestion.
Preserve existing selections; changing any dependency needs concrete approval.

### Output and API distinctions

The CU skill outputs `text_sections.content` as Markdown; `normalized_images`
is a separate optional output. This describes processing, not new source request
fields or a promise to persist generated `.md` files. No guarantee covers every
table/chart.
Since `2026-05-01-preview`, the CU skill's description opt-in pairs `modelName`
and `modelDeployment` for deployed Azure OpenAI chat in its attached account.
Knowledge-source APIs instead expose `chatCompletionModel` and
`disableImageVerbalization`; do not transplant skill fields into source requests.
File's example supplies independent `aiServices`, `embeddingModel`
and `chatCompletionModel`; it does not make every example option mandatory.
Blob documents a multimodal chat deployment **if image verbalization is enabled**.
Do not infer ingestion verbalization from any chat dependency or KB synthesis.

## Necessary checks, not extra configuration

Use verified adapter auth, not nullable shared schema:
Blob/ADLS prefer established Search system MI plus Cognitive Services User on CU;
no keys or fallback after denial. File MI is implemented; live compatibility unverified.
Never transplant Blob MI to File. Shared `cu_ingestion_auth.py` discloses auth;
private ARM listKeys execution remains File-only.

No "can you configure credentials/MI?" or ENV-ready confirmation. Disclose exact
auth scope/cost/data/access in one concrete approval. Reuse verified dependencies;
no setup for exact reuse. Planning is GET-only, with no credential reads.
Key acquisition is helper-internal
only after unchanged fingerprinted approval; never return or persist secrets.

Reuse fresh readbacks; no account-configuration/defaults confirmation or direct CU
analysis probe. Verify through approved ingestion, not by a new billable preflight.
[File auth](standard-cu.md) GETs
`https://management.azure.com<cu-resource-id>?api-version=2024-10-01`
and matches resource ID, `kind: AIServices`, `properties.provisioningState: Succeeded`,
endpoint/location/network; key modes need local auth, MI does not.
Use published operation-region support.
Blob: [identity/role readbacks](bootstrap-azure.md#roles-readiness-and-return).
CU `aiServices.uri` and embedding `embeddingModel.azureOpenAIParameters.resourceUri`
need independent readiness. [Embedding URI/auth](../helpers/vector-contracts.md#supported-choices)
must match the connector/API, not generic embedding-skill aliases.
`prerequisites.configuration` records selected processing/deployment facts, not
extra settings or success proof. Metadata is not effective-access/ingestion proof.
Explain actual key/deployment/network failures; never invent analyzers/defaults.
Preserve first status/request ID and ownership.

## Keep a useful draft when one dependency is pending

Return "Draft ready; one dependency check remains", not rejection or execution input:

```json
{"planning_status":"blocked_pending_dependency","execution_input":null,"resolved_choices_ref":"<retained private intent/readbacks>","remaining_checks":[{"target":"<exact selected dependency>","action":"<necessary GET or owner action>","success_criteria":"<specific required fields/access>","reason":"<actual execution risk>"}],"next_step":"Complete only the remaining checks, then resume planning."}
```

Retain resolved names/boundaries/model choices/caller/owner/readbacks/approvals
privately. Do not rediscover or re-question unchanged choices.
List only unresolved checks; missing generic attestation does not prove a missing
dependency. Retain actual failures and earlier completed writes/ownership;
the draft performs none.
Never pass this summary to `--input`, fabricate execution input or seek execution
approval with unresolved dependencies. Never fill future verification fields or
transfer infrastructure consent to source/KB writes.
Resume `--plan` with retained choices and fresh readbacks; approve only new/material
changes, preserving valid independent approvals. No silent extraction downgrade.

## Only missing resources need setup

Use [packaged native bootstrap](bootstrap-azure.md#native-arm-actions) for missing
account/identity/role/local-auth plans and scoped execution/readback;
never ask the user to configure them manually.
Consolidate already-resolved changes when approving; retain fingerprints and
explicit RBAC/local-auth consent. Source-only consent never grants permission changes.
New principals/drift need new approval, not repeated consent for unchanged actions.
No new RBAC engine or silent grants.
Unsupported updates: `bootstrap-cu-contract-unresolved`; name the missing operation,
never invent PATCH.
For CU, use account A's body with `kind: AIServices`, API `2024-10-01`.
Only approved File key setup enables local auth; MI stays keyless.
Retain approved region/tags/network/cost/ownership. Obtain separate approval for
resource/access changes; verify IDs, endpoint, deployments and settings before resuming.

## Authorities

Authorities: failure/conflict/uncertainty only.

[CU account PUT](https://learn.microsoft.com/rest/api/aiservices/accountmanagement/accounts/create?view=rest-aiservices-accountmanagement-2024-10-01),
[CU skill and supported regions](https://learn.microsoft.com/azure/search/cognitive-search-skill-content-understanding),
[File standard](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-file#configure-standard-extraction),
[Blob prerequisites](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-blob#prerequisites).
