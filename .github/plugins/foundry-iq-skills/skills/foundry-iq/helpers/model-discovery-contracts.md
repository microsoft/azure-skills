# Read-only model and CU selection

`purpose: none` means no dependencies,
not minimal retrieval effort. Minimal+extractive can be model-free;
minimal+answerSynthesis needs `purpose: chat`.
Only FIND inventories; supplied IDs exact-read. KB/retrieve verifies API;
no readiness/access/approval proof.

## Invocation and closed input

From skill directory:

```text
python helpers/model_discovery.py --input choices.json
```

Required JSON (UTF-8):

```json
{"schema_version":"1.0","purpose":"embedding","subscription_id":null,"resource_group":null,"account_id":null,"account_name":null,"deployment":null}
```

`purpose`: `none`, `embedding`, `chat`, `cu`. Null is unresolved.
GUID subscription; ARM names.
RGs: 1-90 Unicode letters/decimal digits or `_-.()`; no final period.
`account_id`: exact Cognitive Services account ARM ID. `deployment`: name or
deployment ARM ID. IDs supply parent/scope; conflicting fields block before CLI.
CU/none reject deployment selectors.
Optional `endpoint`: observed HTTPS origin, only with an exact account selector.
Null/omitted requires a unique origin; explicit selection must match ARM.
Reuse IDs/choices; no setup attestations during discovery.

Three dependency types: CU service capability (Content Understanding, Standard extraction);
embedding deployment (vectorization); chat deployment (enabled image verbalization/KB synthesis).
No project/agent gate.
Keep separate CU, embedding and chat selections. CU never selects models.
Unresolved models keep scope; set
`account_id`, `account_name`, `deployment` and `endpoint` to null; never repurpose
CU's `selection_input`. Explicit model selectors win.
Prefer one compatible existing Foundry/AIServices account:
CU capability + two model deployments.
Separate embedding/KB-chat: per consumer contract. CU image-description models
must be in the Foundry resource attached to the skillset.
Never provision/migrate/redeploy to consolidate.
CU proves no model deployments. Empty model lists are not scope-wide absence:
inspect another selected candidate before proposing creation.
A 403/timeout is unresolved, not absence; no denied-scope broadening.

- Known account ID or account name plus group: exact account GET.
- Name without group: selected-subscription typed listing; unique match exact GET,
  otherwise choices.
- Unknown account: group-scoped, otherwise subscription-scoped Cognitive Services
  accounts: AIServices/OpenAI for models; AIServices for CU.
  No deployment listing until an account is selected, even if only one exists.
- Selected model account: exact deployment GET when named, else its deployment list.
  Validate each role's deployment/capabilities/auth; never infer support
  from names. Missing capabilities need owner validation.
- CU: exact account metadata only; no deployment reads.

Bootstrap's shell-free runner disables installs/auto-upgrade/telemetry and raw logs.
No login/context changes, secrets, writes, role/Policy/catalog/quota scans,
content reads/uploads or model calls.

## Exact CLI surfaces

Unresolved subscription only: `az account show --query "{id:id}" --output json --only-show-errors`.
Otherwise skip context lookup; explicit scope wins.
ARM calls:

```text
az rest --method get --url <URL> --query <helper-projection> --subscription <GUID> --output json --only-show-errors
```

`URL`: `https://management.azure.com<path>?api-version=2024-10-01`.
Encode paths, not IDs. `A` is the exact account path:
`/subscriptions/<sub>/resourceGroups/<group>/providers/Microsoft.CognitiveServices/accounts/<name>`.

| Read | Path |
| --- | --- |
| Accounts in subscription | `/subscriptions/<sub>/providers/Microsoft.CognitiveServices/accounts` |
| Accounts in group | `/subscriptions/<sub>/resourceGroups/<group>/providers/Microsoft.CognitiveServices/accounts` |
| Exact account | `A` |
| Selected account deployments | `A/deployments` |
| Exact deployment | `A/deployments/<name>` |

Complete pagination: 10 pages/200 raw rows aggregate; 20 seconds/command,
120 seconds total. Partial results block; narrow `resource_group` or use an exact ID.
At most ten supported endpoint origins per account.
Continuation retains ARM host/collection/API; only skip-token parameters.
Native CLI JMESPath projects before capture: inventory IDs/names/kinds/locations,
exact account endpoints/state, deployment identity/model/state/public capabilities.
No ARM `$select`; all rows and `nextLink` survive. One MiB per stream, aggregate
captured bytes and final JSON; post-capture checks are not memory bounds.
No retries, fanout, denied-scope broadening or absence inference.

## Closed output

Fields: `schema_version`, `status`, `purpose`, `scope`,
`accounts`, `deployments`, `selected`, `limits`, `warnings`, `first_failure`,
`writes_performed` (always `[]`). Exit 0 returns `skipped`, `no-candidates`,
`account-choice-required`, `deployment-choice-required` or `selected`;
exit 2: `blocked`. No-candidates covers only the completed query.
Scope: null or `{subscription_id, resource_group}`; `limits`: bounds above.
`first_failure` is null or `{code, status, message, request_id, message_digest}`.
Original service code/status/request ID and message digest survive CLI failure;
No raw text/invented IDs; unreadable is not absent.

Account rows: `{account_id, name, resource_group, location, kind,
provisioning_state, endpoint, endpoint_sources, endpoint_state, endpoint_candidates, selection_input}`.
Deployment rows: `{deployment_id, name, model_name, model_version, model_format,
capabilities, provisioning_state, selection_input}`. Metadata fields may be null;
capabilities: safe string map, not support/capacity proof:
`embeddings`, `chatCompletion` and validated numeric `maxContextToken`, `maxOutputToken`
only. Missing/invalid values remain unknown; internal/unknown fields never emit.
`selected` is null or `{account, deployment}` (deployment null for CU).
`endpoint_candidates` is the sorted observed-origin list. Endpoint resolution
failure retains the exact account row, never deployments or a selected result.
Other failures discard choices.
Inventory `endpoint_state` is `not-assessed`; endpoints/state are null/empty until GET.

Present observed compatible deployments together in existing flow.
Keep complete scoped rows internally for ambiguity checks; never paste full
inventories/JSON to the customer. Show at most five concise account/deployment
choices, total count and a more/other choice from retained rows, not new discovery.
Show account/group/region and deployment/model names distinctly. Known Storage
location or selected region can rank suggestions, not prove CU/model availability.
Explicit locations/reuse win; no hidden regional filter or absence claim.
For choices, save the chosen row's **`selection_input`** unchanged.
For ambiguous origins, copy it and set `endpoint` to a listed origin; rerun.
No caller filtering, ID stitching or CLI glue.
Exact readback revalidates choices. Selection is metadata only: owner verifies
model suitability, version/capacity/cost/residency,
selected CU dependencies, actual access and network before concrete approval.

## Endpoint metadata, not a CU readiness assertion

ARM `2024-10-01` does **not** document `endpoints["ContentUnderstanding"]` as a
stable CU discriminator. Never infer hosts from map keys/customSubDomainName.

Inspect the exact account's primary endpoint and every map **value** locally.
CU: `services.ai.azure.com`; embedding/chat also accept `openai.azure.com` and
`cognitiveservices.azure.com`. HTTPS origins only; strip only a trailing slash;
without a selector require exactly one matching origin.
Missing/multiple matching origins block; no rewriting, arbitrary fetch,
paths/query/user-info/ports or readiness inference. For diagnostics:
[scope/endpoint rules](model-discovery-scopes.md).

File CU MI/explicit key and Blob Search identity stay distinct; neither is accessed.
Existing source planners own exact-name collision checks; no extra preflight,
suffixes, writes or auth changes.
