# Portal Monitoring Links

Generate the portal link BEFORE deploying — the deployment name is deterministic, so the link works before the deployment even starts. The user wants to watch resources being created in real time.

## Generate via PowerShell — NEVER construct manually

The `%2F` encoding is critical and models consistently decode it back to `/` during text generation, producing broken links. Always use `.Replace('/', '%2F')`.

```powershell
# Subscription-scope deployment
$deploymentName = "app-onboard-deploy-$("{sessionId}".Substring(0,8))"
$resId = "/subscriptions/{subscriptionId}/providers/Microsoft.Resources/deployments/$deploymentName"
$link = "https://portal.azure.com/#view/HubsExtension/DeploymentDetailsBlade/~/overview/id/$($resId.Replace('/', '%2F'))"
Write-Output "LINK=$link"
Start-Process $link 2>$null
```

Read `LINK=` from terminal output and print the URL in chat on its own bare line — no backticks, no markdown. Then deploy:
```powershell
az deployment sub create --name $deploymentName --subscription {subscriptionId} --location {location} --template-file infra/main.bicep --parameters @infra/main.parameters.json
```

### RG-scope (403 fallback)

Use `az deployment group create --name $deploymentName --resource-group {rg}` and adjust `$resId` to include `/resourceGroups/{rg}`:
```powershell
$resId = "/subscriptions/{subscriptionId}/resourceGroups/{rg}/providers/Microsoft.Resources/deployments/$deploymentName"
$link = "https://portal.azure.com/#view/HubsExtension/DeploymentDetailsBlade/~/overview/id/$($resId.Replace('/', '%2F'))"
Write-Output "LINK=$link"
Start-Process $link 2>$null
```

For Terraform (no single ARM deployment): `https://portal.azure.com/#@{tenantId}/resource/subscriptions/{subscriptionId}/resourceGroups/{resourceGroup}/activitylog`

> 💡 Resolve `{subscriptionId}` and `{resourceGroup}` from `context.json`. For Terraform, resolve `{tenantId}` via `az account show --query tenantId -o tsv`.

## Same-Scope Retries vs New Names

The portal link stays valid for same-scope retries — ARM overwrites in-place. Generate a new name (e.g., `$deploymentName = "app-onboard-deploy-{first8}-2"`) **only** when scope or RG changes.

## Chat Output Rules

1. **Terminal command:** the PowerShell snippet above (outputs the bare URL and auto-opens it in the default browser via `Start-Process`)
2. **Read the terminal output** — find the line starting with `LINK=` and extract the URL
3. **Chat output:** paste the bare URL on its own line — no backticks, no markdown, no emoji on the same line

⛔ **Link must be ctrl+clickable.** The URL MUST be the ONLY content on its line — no emoji, no text, no backticks, no markdown formatting, no markdown link syntax on the same line. Terminals auto-linkify bare URLs but ONLY when the URL is alone on the line.

⛔ **Emit a NEW link whenever deployment name changes.** When healing causes a redeploy with a different `--name`, you MUST re-run the PowerShell snippet with the new name and print the new link:
```
⚠️ Previous deployment link is stale — use this one:
https://portal.azure.com/.../{newDeploymentName}
```
