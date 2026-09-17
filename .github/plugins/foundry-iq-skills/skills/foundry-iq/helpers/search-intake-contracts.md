# Reuse-first Search intake

Use before service enumeration/provisioning, not for existing KB retrieval or
agent connection (their owners keep their actual read-only checks).
No supplied service/intent: ask **USE EXISTING / FIND CANDIDATES / CREATE NEW**
once before expensive discovery. Supplied IDs/names/endpoints imply USE EXISTING
unless creation was explicit. Carry resolved intent and selections through
File/Blob/KB/CU/model handoffs; never reopen informed answers.
A supplied candidate completes FIND as USE EXISTING, without another inventory.

This checker is Search-only. For CU/model dependencies use
[purpose-specific discovery](model-discovery-contracts.md):
CU uses `AIServices`; embedding/chat use `OpenAI` or `AIServices` (Foundry).
Carry separate selections; USE/FIND/CREATE is workflow state, not a model-helper
input field. Call model discovery for supplied selectors or FIND; CREATE goes to
its native owner, never an empty selector. No generic AI-host bootstrap/quota/RBAC
automation. [CU](../references/cu-ingestion.md), [vectors](vector-contracts.md) and
[KB](kb-contracts.md) own API, auth/MI, RBAC, network and actual processing checks.
File Standard defaults to system MI (v1.2), implemented but not live-verified.
Explicit legacy ARM-key v1.1 and ENV-key v1.0 remain; no fallback.
[File auth](../references/standard-cu.md) checks exact CU/role/identity/network.
Blob CU uses Search system MI; neither mode selects embeddings or KB chat.

## Native helper

```text
python helpers/search_intake.py --select intake.json
```

Closed UTF-8 input; only `schema_version` is required:

```json
{"schema_version":"1.0","intent":null,"service":null,"subscription_id":null,
"resource_group":null,"source_region":null,"page":0,"operation":null}
```

`intent`: null, `use-existing`, `find-candidates`, `create-new`.
`service`: exact Search ARM ID, service name or clean HTTPS Search root.
Names: 2-60 lowercase ASCII letters/digits/dashes; first, second and last
characters alphanumeric, no consecutive dashes. Thus `ab-c` is valid, `a-b` is not.
Full ARM IDs are matched case-insensitively, then their service names validated.
GUID subscription; group names follow ARM rules. IDs supply scope; conflicts
block. `source_region`: observed source region, only a latency/data-movement
preference, never inferred from names or used as compatibility proof.
No default location or subscription scanning. Explicit subscription wins;
otherwise `az account show` supplies the stated default. No context switch.

| Intent | Reads/result |
|---|---|
| Missing | `intent-required`, three choices; zero CLI/auth calls |
| USE EXISTING without locator | `service-required`; ask for locator, no inventory |
| Supplied ID or name+group | Exact ARM GET only, plus selected account context |
| Name/endpoint without group | One `az resource list --name <name> --resource-type Microsoft.Search/searchServices --subscription <sub>`, then exact GET if unique |
| FIND CANDIDATES | Known group: `az search service list --resource-group <group> --subscription <sub>`; otherwise type-filtered `az resource list` in selected subscription |
| CREATE NEW | Require name/group, exact collision GET; `creation-plan-required` only on exact ResourceNotFound. No service inventory or implicit reuse |

Lists use `--query "[].{id:id,name:name,location:location}"`; native CLI consumes
pages in that scope. Keep the complete bounded inventory internally; return at
most five rows, total/remaining/unassessed counts and `next_page`.
`page` is zero-based, below 40; each page refreshes the scoped inventory.
All candidates remain unassessed, not recommended or unique from a top-five view.
Same observed source region first; retain cross-region rows. Explicit choice wins.
Use the row's `selection_input` for exact readback, not another list.
No model calls, cross-subscription fanout, arbitrary URL fetches or writes.
More than 200 rows, duplicates, scope escape, malformed/denied reads block without
partial choices or absence claims. Shared native reader: 20s/command, 120s total,
one MiB post-capture limit, not a hard capture-memory bound.

## Operation-specific reuse

Initially `operation: null` selects ARM metadata, not compatibility/readiness.
Once the actual mode is chosen, rerun the same selected ID with one operation:

```json
{"kind":"file-source","api_version":"2026-08-01-preview","extraction_mode":"minimal","vectorization":"none"}
```

Closed variants:

| kind | Other required fields |
|---|---|
| `service` | `api_version` |
| `file-source` / `blob-source` | `api_version`, `extraction_mode`: minimal/standard, `vectorization`: none/azureOpenAI |
| `knowledge-base` | `api_version`, `reasoning_effort`: minimal/low/medium, `output_mode`: extractiveData/answerSynthesis |

APIs: `2026-04-01` or `2026-08-01-preview`; File, Standard extraction and
nonminimal/synthesis KB require preview. Downstream source/KB validators retain
their additional API, source-kind, tier/size, regional capability and data-boundary
constraints; these variants are not a new capability matrix.

Existing keys may remain enabled when ARM shows `aadOrApiKey` and Entra read works.
No Search/Storage keys, key retrieval, secret input, identity/firewall/network/tag
changes, or hardening to fit creation defaults.
Require running/succeeded, exact endpoint/ID and recognized observed SKU/region.
Public firewall restrictions are preserved; actual caller read must succeed.
Private/perimeter access is unsupported here: report `search-network-unsupported`,
not a global compliance failure or instruction to open networking.

Search system MI is required for Blob (Storage/CU), source embeddings and KB
chat/nonminimal reasoning, not lexical File or minimal/extractive KB alone.
`file-source` does not encode CU auth: File's owner verifies MI or explicit
legacy keys before its plan; this Search read is not File CU readiness.
Verify required system principal/tenant; never accept a missing MI by request.
UAMI selection is unsupported; an unused UAMI is not caller authentication.

For a selected operation, scoped `az rest --method get --resource https://search.azure.com`
reads `<endpoint>/servicestats?api-version=<selected-api>` using CLI Entra auth,
then exact ARM reread rejects access/identity drift. No billable write/model probes.
Statistics GET proves **only that metadata read**, not source/KB write RBAC,
feature-region support, Search-to-Storage/CU/model access, ingestion or retrieval.
Verify these separate edges with the owning procedure before its plan/approval;
no success-shaped fallback or permission relaxation on denial.

## Handoff

`selected`: observed ID/endpoint/SKU/tier/location and qualified read evidence.
After unique name/endpoint resolution, `scope.resource_group` and
`selection_input.resource_group` carry the observed group in the selected
subscription. Unresolved/ambiguous names and FIND retain their original scope;
candidate rows carry each group's exact handoff without narrowing that inventory.
`operation_required` means mode unresolved. Reuse `selection_input`; no receipt,
approval envelope, ownership claim or creation-profile matching.
Fresh selection/readback is not future consent.
Creation delegates to unchanged [bootstrap choices](bootstrap-contracts.md):
secure new-service defaults, required region/quota/cost checks, exact collision
reread and separate approval. Never run strict legacy bootstrap reuse merely to
validate an existing operation.

## Authorities

Authorities: failure/conflict/uncertainty only.
[Service naming rules](https://learn.microsoft.com/rest/api/searchservice/naming-rules),
[Entra and keys together](https://learn.microsoft.com/azure/search/search-security-enable-roles),
[statistics GET](https://learn.microsoft.com/rest/api/searchservice/get-service-statistics).
