# Discovery scope and endpoint diagnostics

Read for ambiguous/missing endpoints, CU/model handoff confusion, unusual RG names
or selector/readback errors.
Metadata only; no setup or billable probes.

## Separate dependency selections

CU extraction uses `content_understanding.endpoint` / `aiServices.uri`; source
vectors use `embedding.endpoint` / `embeddingModel.azureOpenAIParameters.resourceUri`.
Retain each role's account ID, observed origin and selected deployment separately.
The CU key/identity is not evidence of embedding access.

For example, CU account A can have no embedding deployment while model account B
already hosts a suitable one. Leave A selected for CU; start unresolved
`purpose: embedding` discovery in the agreed scope without A's account/name/endpoint.
The returned model candidates include `OpenAI` and `AIServices` accounts. A Foundry
resource is an `AIServices` model-hosting account, not another mandatory resource.
Choose a model account before listing its deployments. An account-list result is
not a deployment search; one empty deployment list does not exhaust the scope.
Keep the shortlist and choose another candidate, not repeated reads of A.

An explicit embedding deployment fixes its own parent account; never overwrite
that binding with CU's. Same-account reuse remains valid when both roles are
independently verified. Carry the selected embedding origin/deployment unchanged
into the source plan; never rewrite hosts or substitute the CU origin.

Prefer compatible existing deployments. If the completed agreed search finds
none suitable, propose a deployment in a compatible existing account before a
new account, with separate approval and model/SKU/quota/access/cost checks.
An explicitly selected target failure, denial, timeout or incomplete inventory
remains unresolved: no automatic scope expansion, creation or silent fallback.

## Resource groups are not account names

`Microsoft.Resources/resourcegroups` permits 1-90 characters: underscores,
hyphens, periods, parentheses, and Unicode categories Lu/Ll/Lt/Lm/Lo/Nd
(letters or decimal digits). No final period. No alphanumeric-first requirement:
`_shared-ai`, `.shared` and `(ops)` are valid. Combining marks, nondecimal numeric
characters, whitespace, slashes, percent escapes and controls are not allowed.
Use literal names in selectors/ARM IDs, not URL-encoded strings.

The helper uses one RG predicate for supplied groups, account/deployment IDs and
observed IDs, before filtering account kinds. Thus an unrelated Speech account
in a valid RG does not poison a model listing; malformed/foreign scope still
blocks the entire result, never silently skips a row. Account/deployment name
rules remain separate. Unicode case handling must not merge distinct groups
through multi-character folds.

Only HTTP paths are UTF-8 percent-encoded. Returned IDs and selection inputs stay
literal. Continuations must decode to the same collection and retain the exact
ARM host/API and allowed skip-token parameters; they are sent on the validated
encoded path. No context change, broader listing or Unicode transliteration.

## Purpose-specific observed origins

| Purpose | Accepted suffixes |
|---|---|
| `embedding` | `openai.azure.com`, `services.ai.azure.com`, `cognitiveservices.azure.com` |
| `chat` | Same model origins, independently checked against the KB consumer |
| `cu` | Only `services.ai.azure.com`; no model-host substitution |

Require `https://<label>.<suffix>`: a 1-63-character lowercase alphanumeric/hyphen
label starting alphanumeric, optionally ending in `/`. Strip only that slash.
No paths (including project/API paths), explicit
ports, user-info, queries, fragments, APIM, sovereign/custom hosts or hostname
rewriting. Unsupported forms are not evidence of resource absence.

Inspect `properties.endpoint` and every `properties.endpoints` map value.
Deduplicate observed origins; map keys have no documented CU discriminator.
Provenance is `properties.endpoint` and/or `properties.endpoints`, not a guessed
meaning for `ContentUnderstanding` or another key. Portal evidence cannot replace
missing ARM metadata. Endpoint selection does not prove path-specific CU/model
readiness or effective access.

Embedding syntax matches `source_vector.validate_choice`. The KB consumer relays
`models[].azureOpenAIParameters` without an additional domain gate; the public KB
SDK examples use `AzureOpenAIVectorizerParameters`. Offline tests pass discovered
chat origins through that consumer's existing validation. This is compatibility
evidence, not live KB/API/model availability proof. CU stays independently bounded.

## Explicit resolution and reuse

An omitted/null `endpoint` selects only a unique observed supported origin.
Multiple supported origins are never resolved by preferring the primary endpoint,
an OpenAI hostname, map order or a familiar deployment name.

`discovery-endpoint-unresolved` retains the freshly read account and its sorted
`endpoint_candidates`; no deployment read occurs. Copy its `selection_input`,
set `endpoint` to the customer's selected candidate, and rerun the same helper.
An explicit endpoint must be supported for the purpose and paired with an exact
account ID (including one derived from a deployment ID), or account name plus RG.
It must still occur in fresh ARM metadata. More than ten supported origins blocks
without partial candidates. No schema fields other than optional `endpoint` were
added to input; the original seven fields remain required.

Deployment `selection_input` retains the chosen origin for exact reuse; extra
observed aliases cannot switch it. Missing/ambiguous metadata has
`endpoint_state: endpoint-missing-or-ambiguous`; an unobserved explicit choice has
`endpoint-selection-not-observed`. Both block; no fallback or absence claim.
Other discovery failures still discard candidates. Original sanitized service
errors/request IDs and source planners' approval/ownership checks remain intact.

## Compact public metadata

CLI `--query` runs before capture, not server-side `$select`. Account inventories
retain ID/name/kind/location; RG comes from the validated ID. Endpoints/state
remain `not-assessed` until exact GET; no unselected account deployment fanout.
`map` retains all raw rows, including malformed ones; `nextLink` is never trimmed.
Bounds aggregate across collections. On overflow, retain scope and request
`resource_group` or an exact ID once; no implicit Search RG or availability claim.

Capabilities: `embeddings`/`chatCompletion` booleans or exact `"true"`/`"false"`;
`maxContextToken`/`maxOutputToken`: decimal integers 1-2147483647 as strings
(safety bound, not a service limit).
No floats, scientific notation, whitespace, leading zeros or arbitrary strings.
Other fields (`_H_*` in any case too) never emit. Invalid/missing values stay unknown;
removal cannot establish suitability or usable capacity.
Non-object capabilities become `{}`; malformed properties/model/IDs block.

## Authorities

Authorities: failure/conflict/uncertainty only. Checked 2026-09-15:

- [RG rules](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/resource-name-rules#microsoftresources)
- [Embedding domains](https://learn.microsoft.com/en-us/azure/search/cognitive-search-skill-azure-openai-embedding)
- [KB model consumer](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-create-knowledge-base)
- [ARM GET](https://learn.microsoft.com/rest/api/aiservices/accountmanagement/accounts/get?view=rest-aiservices-accountmanagement-2024-10-01)
- [ARM schema](https://github.com/Azure/azure-rest-api-specs/blob/main/specification/cognitiveservices/resource-manager/Microsoft.CognitiveServices/stable/2024-10-01/cognitiveservices.json)
- [CU endpoint](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/contentunderstanding/azure-ai-contentunderstanding/README.md)
- [CLI projection](https://learn.microsoft.com/cli/azure/query-azure-cli)
