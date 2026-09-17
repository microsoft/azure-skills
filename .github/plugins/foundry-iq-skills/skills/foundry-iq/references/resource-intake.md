# Select resources from names, URLs or observed choices

For unresolved names/URLs/choices, helpers still receive their documented, resolved JSON inputs.
Execute only the applicable branch, not every discovery command on this page.

Search validation is not AI-host readiness. CU (`AIServices`) and model
(`OpenAI`/`AIServices`) selections use their purpose-specific owners below.

Before expensive enumeration, reuse supplied resource/intent; otherwise ask one
**USE EXISTING / FIND CANDIDATES / CREATE NEW** choice. USE asks only for a missing
locator. Only FIND enumerates. CREATE checks its proposed name and necessary
region/quota/cost, not existing-service inventory; approval remains separate.
Carry intent and resolved IDs/modes through source/KB/CU/model handoffs.

Reuse prompt/session choices. Otherwise use `az account show` and assume its
default subscription, stating that assumption; an explicit subscription wins.
Pass `--subscription <sub>` on reads; never silently change CLI context.
Account context and candidate listings are not access/readiness proof.

Exact supplied IDs need exact readback, not enumeration. Only FIND browses relevant
types in the known group, else selected subscription. Read all pages within that
query, never fan out across subscriptions or enumerate unrelated resource types.
Offer choices, not a questionnaire about IDs.

## Search reuse

Read [Search intake](../helpers/search-intake-contracts.md); execute its native
`search_intake.py --select` surface, not improvised filtering/glue.
Exact ID/name+group skips enumeration. Name/endpoint without group gets only exact
name/type resolution in the selected subscription; do not fetch arbitrary URLs.
FIND uses known RG before selected-subscription fallback; bounded metadata/pages,
five-row presentation and unassessed counts, no megabyte inventory dump.
Explicit choice wins; retain cross-region candidates. Observed source-region
proximity is latency/data movement preference, not Search/CU compatibility.
Never infer location from names, absence/uniqueness from top five, or broaden denial.
Use returned `selection_input`; users need not copy IDs.

Recheck selected operation, not new-resource hardening defaults.
Keys-enabled Search may support Entra; never disable keys/change identity/firewall/
tags to satisfy a template. Actual File CU-MI/Blob/vector/KB-chat MI remains required.
Private/UAMI-selected unsupported paths return capability/access blockers, not
global compliance failures. Caller-to-Search and Search-to-dependency access are
separate; metadata/read proof is not write permission or outbound readiness.
No Search/Storage keys or billable readiness probes.
The [Search owner](../search-services/create.md) preserves exact approval boundaries.

## Blob or ADLS container/folder URL

Accept `https://example.blob.core.windows.net/documents` as intake:
account `example`, container `documents`. A URL does not identify its Azure
subscription or resource group; the CLI default is only the initial lookup scope.
Also accept separately supplied names/IDs; do not ask again for URL-derived fields.

Also accept `https://example.dfs.core.windows.net/documents/onboarding`:
account `example`, filesystem/container `documents`, directory `onboarding`.
Keep the observed endpoint type (Blob or DFS); do not infer HNS from the hostname.

Parse locally: HTTPS, exact `<account>.blob.core.windows.net` or
`<account>.dfs.core.windows.net` host and an explicit container/filesystem path.
Reject user-info, query/SAS, fragments, custom hosts/ports and
malformed encoding without echoing the input; request a clean locator.
Decode path segments once, preserve case, and reject ambiguous encoded separators,
dot segments and control characters. Never use credentials from a pasted URL or
fetch its content during intake. Do not guess a folder from an individual blob URL.

Resolve the account by exact name/type in the selected subscription:

`az resource list --name <account> --resource-type Microsoft.Storage/storageAccounts
--subscription <sub>`.

Add `--resource-group <group>` when known. Read the returned exact ARM resource
and verify its account name, corresponding Blob/DFS endpoint and HNS setting.
DFS/ADLS intent requires verified HNS; resolve mismatches rather than silently
converting to Blob. A Blob hostname on an HNS account still uses ADLS rules.
Obtain the Storage
ID/group from that readback; do not invent them from the URL.
If inaccessible or absent from the selected scope, ask for the correct scope/ID;
do not scan every subscription, provision Storage or request broader access automatically.

Keep the supplied container; no container enumeration is needed. If it is unknown,
the Blob owner offers observed containers in the selected account using Entra login.
Only FIND with an unknown account offers Storage-account choices with
`az storage account list --subscription <sub>`, adding the known group filter.
Choose a returned account before enumerating its containers.

A container locator does not silently select every object. Preserve an explicit
folder choice, or resolve whole-container versus folder scope before inventory.
Ambiguous folder/blob paths need clarification, never automatic slash-appending
or parent-container expansion. Carry endpoint type and verified HNS to the owner:
Blob non-root prefixes end in `/`; ADLS directories do not. Never append `/`
merely to turn a file or arbitrary partial prefix into a folder.
No object inventory/download occurs before the data boundary is selected.

## Existing model choices

Keyword-only skips embedding discovery; other dependencies remain conditional.
Carry the early service choice: supplied account/deployment uses exact reads;
only FIND lists accounts/deployments. CREATE uses required catalog/quota checks,
not an existing-account inventory. Never reopen resolved CU/model selections.
Use [typed discovery](../helpers/model-discovery-contracts.md), not ad hoc
CLI filtering/glue. Exact model IDs first; otherwise
selected RG/subscription only. Choose account before its deployments. Reuse
returned `selection_input`; show deployment versus model/version and account/region.
CU uses `purpose: cu`; [shared CU ingestion](cu-ingestion.md) owns necessary
checks and pending drafts, not generic configuration attestations.
Retrieval effort alone never makes a route model-free. Minimal+extractive can
skip chat; minimal+answerSynthesis requires chat-model discovery (`purpose: chat`).
Keep extraction mode, source embeddings and CU independent. The KB/retrieve owner
verifies API support; this intake does not establish availability or change validators.

For new deployments the native owner uses `az cognitiveservices model list` and
`az cognitiveservices usage list` with `--location <region> --subscription <sub>`
for model/version/SKU/quota before approval. Existing deployments need readback,
not catalogs. Retain capacity/price/residency checks; execute only approved changes.

Return selections without restarting intake. Selection is not mutation approval.
Preserve boundaries, complete inventories, fresh pre-write and ownership/access checks.
After discovery, batch compatible unresolved Search, processing/search and model/CU
choices with recommendations; reuse informed answers. Account selection precedes
deployment listing, so do not batch a deployment guess. Keep exact sample-content
consent and actual resource/permission/CU/source/KB approvals distinct; no approval
of unknown future bodies. Source planners already own exact-name collision checks.

## References

Authorities: failure/conflict/uncertainty only.

[Filtered ARM resources](https://learn.microsoft.com/rest/api/resources/resources/list).
[Blob resource URIs](https://learn.microsoft.com/rest/api/storageservices/naming-and-referencing-containers--blobs--and-metadata).
[ADLS filesystem/path](https://learn.microsoft.com/rest/api/storageservices/datalakestoragegen2/path/get-properties).
