# Deploy Safety

Hook-based safety rules for the deploy phase. Block destructive operations.

## deploy-result.json Skeleton

Created by scaffold validate sub-agent. If missing at deploy Step 5b, create from [`deploy-schemas.ts`](deploy-schemas.ts) with `status: "in-progress"`. Append to `deploymentNames[]` on each healing retry.

## Deploy Checklist (compaction-safe — generated at Step 5b)

> ⛔ **You MUST read [`deploy-checklist-template.md`](deploy-checklist-template.md)** at Step 5b to generate the checklist. Write the result to `.copilot-azure/sessions/{id}/deploy-checklist.md`. Re-read the generated checklist after every long-running command, failed health check, and conversation compaction.

## Finalize deploy-result.json (Step 8)

Overwrite the skeleton with real values:
- `status` → `"succeeded"` or `"failed"`
- `deploymentNames` → ALL names used (initial + retries)
- `healthStatus` → worst across endpoints
- `duration.completedUtc` → now
- `resourceResults` → one entry per resource from `az deployment operation list`

## Blocked Patterns

> ⛔ **You MUST read [`blocked-patterns.md`](blocked-patterns.md)** before running ANY `az` command during the deploy phase. This file contains every command the agent is forbidden from executing. Block decisions are non-negotiable — user must run blocked commands manually outside AppOnboard.

## 403 Scope Fallback

When `az deployment sub create` returns 403 (insufficient subscription-scope permissions), do NOT halt immediately:

1. **Restructure Bicep to RG-scope** — change `targetScope = 'subscription'` to resource-group scope, remove the `Microsoft.Resources/resourceGroups` resource.
2. **Create the RG via CLI** — `az group create -n {rg} -l {region} --tags app-onboard-skill=true app-onboard-session-id={sessionId} created-at={createdAt} environment={environmentName} deployed-by={deployedBy}`. All 5 AppOnboard tags MUST be included.
3. **Retry with `az deployment group create`** — use `--resource-group {rg}` instead of subscription scope.
4. **Regenerate portal link** for RG-scope — `$resId` must include `/resourceGroups/{rg}`: `$resId = "/subscriptions/{subscriptionId}/resourceGroups/{rg}/providers/Microsoft.Resources/deployments/$deploymentName"`. Re-run `Write-Output "LINK=$l"; Start-Process $l 2>$null` and print new bare URL.
5. **If retry ALSO fails with 403** → classify as `ENVIRONMENT_BLOCKING`. Surface required role: `az role assignment create --role Contributor --assignee {user} --scope /subscriptions/{sub}/resourceGroups/{rg}`.

## Deploy Checklist

> ⛔ **Use sync shells** so state persists. **Persist secrets** to `.copilot-azure/sessions/{id}/deploy-secrets.env` — generate each secret ONCE (URL-safe, no `/+=`), reload in every later shell. Never regenerate an existing key. Key Vault is the durable source of truth for every secret (the file is only a cross-shell reload cache and is git-ignored via `.copilot-azure/`). NEVER echo or log rendered secret values.
>
> ⛔ **URL-safe passwords required** when app uses URL-based connection strings. Forbidden chars: `# @ / ? % : & = + ;`.
> ⛔ **`az webapp deploy` does NOT support `--track-status`.**
> ⛔ **`az rest` on Windows PowerShell:** ALWAYS include `--headers "Content-Type=application/json"`.
> ⛔ **Suppress deployment output:** Add `--query properties.provisioningState -o tsv` to deployment commands. For `az acr build`, append `--no-logs`.

## Post-Deploy Tag Verification

After deployment, verify all 5 AppOnboard tags: `az group show -n {rg} --query tags -o json`. Re-apply missing via `az tag update`.

## Deployment Operation Polling

For deployments with >5 resources, poll every 30s: `az deployment operation list --name {name} --subscription {sub} --query "[?properties.provisioningState=='Failed']" -o table`. Wait for FULL completion before healing — collect ALL errors in one pass.

## Re-Approval Gates

Region, service type, or SKU changes from user-approved values → re-present approval gate. Resource name changes → informational only. Same-deployment retries → no re-approval.

## Antipatterns

⛔ Do NOT `az group delete --no-wait` then `az group create` same name — background deletion takes 5-15 min and destroys the new RG. Use a different name or wait: `az group wait --name {rg} --deleted --timeout 900`.

## Artifact Reconciliation After Healing

After ANY healing that changes deployed resources, update `prepare-plan.json`, `scaffold-manifest.json`, and `context.json` to reflect actual state. Track orphaned RGs in `deploy-result.json.orphanedResourceGroups[]` immediately when switching to a new RG.
