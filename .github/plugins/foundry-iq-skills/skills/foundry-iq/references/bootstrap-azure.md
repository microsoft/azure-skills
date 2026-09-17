# Native prerequisite bootstrap

Use signed-in `az`, never evaluation fixtures or credentials in chat.
Missing CLI/access returns `bootstrap-tool-unavailable`/`bootstrap-access-denied`.
Invoke `az` as subprocess argument lists, never shell strings; platform support varies.
Keep sanitized evidence in private receipts; show status/IDs, never raw stdout/stderr.

Search: [owner](../search-services/create.md).
Here: RG/models/roles/CU and separately approved cleanup.

## Resource-group-only prerequisite

For an absent group, execute **RG-only**:
resolve subscription/group/region/tags/owner, approve its concrete plan,
use only the R row below with fresh absence/readback.
Require `provisioningState == Succeeded`; return the ready group ID to the caller.
Do not dispatch Search, models, roles, Storage or CU, or re-enter the Search
procedure from this branch. Search planning resumes only after RG readiness;
no unknown future Search body is approved here.

## Discover and approve

Use `az account show`, then exact ARM GETs for supplied IDs/names.
Reuse resolved selections; otherwise propose CLI default subscription,
explicit scope taking precedence. Never silently switch context.
Reuse supplied resource/intent; else ask USE EXISTING / FIND CANDIDATES / CREATE NEW.
Ask only unresolved choices, not discovery outputs.
Only FIND enumerates: `az group list --subscription
<sub>` if no group is selected. Only model-dependent paths with no
selected account and FIND use `az cognitiveservices account list --subscription <sub>`.
Add a known `--resource-group <group>`; otherwise browse the selected subscription.
Read all pages in scope.
Only target ResourceNotFound proves absence, not 403/timeouts/empty output.

Models: read [choices](resource-intake.md#existing-model-choices).
Existing: exact readback. CREATE: collision/quota/region/cost, no service inventory.
Retain choices. Model-free lexical paths skip model calls.
New embeddings: propose 100K TPM if quota allows; otherwise ask. Approve model/SKU integer units.
Verify region/network/prices; quota is not capacity.

Internal plan fingerprint: SHA-256 of sorted-key, ASCII-escaped, compact UTF-8 JSON. Bind IDs/URLs,
before-state, bodies/tags, owner/model/version/SKU/capacity/cost/network/known requirements,
deadline/readbacks/cleanup. Propose nonce names within user constraints.
Actual approval precedes writes; new MI readback needs separate role approval.
No routine policy reads. Only creation failures implicating policy trigger
targeted diagnostics in the shared prerequisite contract.

## Native ARM actions

Let `R=/subscriptions/<sub>/resourceGroups/<group>`,
`A=R/providers/Microsoft.CognitiveServices/accounts/<account>`.
`https://management.azure.com<ID>?api-version=<version>`.
GET immediately before each absent-resource PUT; existing means reuse/replan,
never overwrite. ARM does not document `If-None-Match`: GET/PUT is not atomic.
Require exclusive authority over new names; disclose the race. Unavailable
required atomic protection blocks with `bootstrap-concurrency-unresolved`.

`az rest --method get --url <url>` then `az rest --method put --url <url>
--headers Content-Type=application/json --body @<approved-body-file>`.
`@` loads an Azure CLI body file, not shell expansion. Pass `"@" + str(body_path)`
as one subprocess argument, including paths with spaces; a bare path sends text, not JSON.

Apply retained approved bodies in dependency order:

| ID / API | JSON body (substitute approved values) |
|---|---|
| R / `2022-09-01` | `{"location":"<region>","tags":{}}` |
| A / `2025-06-01` | `{"location":"<region>","tags":{},"kind":"OpenAI","sku":{"name":"S0"},"properties":{"customSubDomainName":"<name>","publicNetworkAccess":"<approved>","disableLocalAuth":true}}` |
| A/deployments/name / `2025-06-01` | `{"sku":{"name":"<deployment-SKU>","capacity":<approved-capacity>},"properties":{"model":{"format":"OpenAI","name":"<model>","version":"<version>"}}}` |

Use required tags/settings; read back TPM/RPM.
Poll GET to `provisioningState == Succeeded`; compare ID/body/tags and read
principalId/endpoint/model/version/SKU/capacity. Accepted is not ready.
Retain first error/request ID; reconcile ambiguous writes read-only,
never blind retry or suffix-create.

## Roles, readiness and return

Offer approved missing-role setup.
Freshly read Search's `identity.principalId`, never assume it.
For Blob/ADLS, recommend `Storage Blob Data Reader` for that `ServicePrincipal`
at `<storage-id>/blobServices/default/containers/<container>`.
This grants container-wide access even when ingestion selects a folder.
Disclose scope; block if unacceptable, never broaden.
Account scope requires explicit selection/approval, never a fallback for denial.
`az role definition list --name <role> --subscription <sub>` resolves role IDs;
`az role assignment list --scope <id> --include-inherited --subscription <sub>
--fill-principal-name false --fill-role-definition-name false` inventories roles.
Match principal/role/scope and inherited access; read all pages.
Reuse sufficient grants; preserve unrelated roles. Unreadable inventories or
uncertain conditions/deny assignments are not proof of missing access.
Bind missing grants to principal/role/scope/GUID and RBAC approval;
source approval alone is insufficient; caller needs
`Microsoft.Authorization/roleAssignments/write` at that scope.
No approval/authority: return owner action;
never self-elevate or switch identity. Recheck identity and assignments before
writing; drift needs a new plan, a newly sufficient grant needs no write.

`az role assignment create --subscription <sub> --name <approved-guid>
--assignee-object-id <principal> --assignee-principal-type <User-or-ServicePrincipal>
--role <role-id> --scope <exact-id>`.

Use the target scope's subscription; read back assignment ID and exact
principal/role/scope; keep ownership private. Ambiguous create: reconcile
read-only with the same GUID, never retry using a new GUID or broaden scope.
Return observed assignments to the source planner; do not fabricate RBAC evidence.

Search scope: operator `Search Service Contributor`, ingestion
`Search Index Data Contributor`, retrieval `Search Index Data Reader`.
Search MI: `Cognitive Services User` on model account; Blob additionally
`Storage Blob Data Reader` on approved Storage scope. No unnecessary roles.
For Search, bounded propagation waits use fresh CLI Entra auth:
`az rest --method get --url "<search-endpoint>/knowledgesources?api-version=2026-08-01-preview" --resource https://search.azure.com/`.
Require `disableLocalAuth == true`; no `authOptions` with it. Never call
`listAdminKeys`, `listQueryKeys`, `regenerateAdminKey` or `createQueryKey`.
Prove denial with `az rest --skip-authorization-header --method get --url <probe-url>
--headers api-key=phase1-key-denial-probe`. Never acquire a real key.
Missing readiness is partial, never permission to weaken security.
Search metadata GET or operator Blob listing does not prove Search MI Storage access.
After RBAC readback, resume the approved source workflow; require its relevant
successful ingestion cycle. Pending propagation is unverified within the agreed
deadline, not permission to regrant, bypass access or reset generated indexers.

CU ingestion: [shared auth/setup](cu-ingestion.md); connection-only/minimal skip CU.

## Cleanup

After source/KB removal, separately approve `az role assignment delete --ids <id>`
then `az rest --method delete --url <approved-ARM-url>`; verify absence.
Require fresh exclusive ownership/configuration/children/scoped-role inventory;
no invented ARM ETags or reused/foreign deletion. Return observed dependencies;
failure retains partial writes.

Optional [schemas](platform-interfaces.md).

Authorities: failure/conflict/uncertainty only.
[Search Storage identity](https://learn.microsoft.com/azure/search/search-howto-managed-identities-storage);
[Blob RBAC](https://learn.microsoft.com/azure/storage/blobs/assign-azure-role-data-access).
