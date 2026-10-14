# App Settings

### 4c. Migrate App Settings

> 🔒 **Security**: App settings contain secrets (connection strings, storage keys, API keys). The skill first reviews setting **names only**. If the user chooses to copy settings, a local pipeline streams values directly from the source ARM endpoint to the new app's ARM endpoint via process memory only — no temp file is ever written to disk.

**Phase 1 — Skill reviews setting names (no values)**

```bash
az functionapp config appsettings list --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP> --query "[].name" -o tsv
```

> ⚠️ **Skill instruction**: Confirm none of the names above look surprising before proceeding — the 4c filter already strips Flex-deprecated names. Cross-reference [Deprecated Settings](../workflow.md#deprecated-settings-do-not-migrate) if anything is unfamiliar. Do NOT request values.
>
> Linux app-setting names cannot contain `:`. For every surviving source name containing `:`, show the user the planned `:` → `__` mapping before the copy decision (for example, `FunctionsHostingConfig:CustomSetting` → `FunctionsHostingConfig__CustomSetting`). .NET configuration maps `__` back to `:` on Linux. For other runtimes, record the rename for application-specific validation.
>
> Before reading values, compare mapped source names case-insensitively. If two source names map to the same target name, stop and use `ask_user`; never silently choose between them. An existing target name is not a collision: after the user approves the mapping, the source value replaces it using the same idempotent merge behavior as an unchanged setting name.
>
> Surface this once as a **post-migration follow-up** (do not block 4c on it): connection strings or keys for **Azure services** (Storage, Service Bus, Event Hubs, Cosmos DB, Key Vault) can be replaced with [identity-based connections](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference#configure-an-identity-based-connection) for better security — see the [identities-instead-of-secrets tutorial](https://learn.microsoft.com/en-us/azure/azure-functions/functions-identity-based-connections-tutorial). The user owns the conversion (code + role assignments), and it only applies to Azure services that support Microsoft Entra ID auth — settings for third-party services stay as-is.

**Decision — Copy or defer source app settings**

Before reading any setting values or changing the target, use `ask_user`:

> Should I copy the filtered source app settings to `<NEW_APP_NAME>` now?
>
> - **Copy filtered settings** — preserves application configuration, but may connect the target code to the same production dependencies after deployment. Target-owned storage and Application Insights settings remain unchanged.
> - **Defer source settings** — leaves only target-generated settings in place so you can configure isolated or target-specific dependencies before deployment.

Record the choice in `<UPGRADE_DIR>/upgrade-status.md`.

- If the user chooses **copy**, continue to Phase 2.
- If the user chooses **defer**, do not fetch source setting values and do not run either Phase 2 block. Before Step 5, require confirmation that all required application-specific target settings have been configured. Reviewing setting names is allowed; never display their values.

**Phase 2 — Copy locally (values never leave the terminal, never touch disk)**

The `az functionapp config appsettings set` CLI surface only accepts `KEY=VALUE` pairs or `@file.json`, so PATCH the underlying ARM endpoint directly via `az rest`. Fetch both apps' settings, filter the source settings, and merge them into the target's existing dictionary. This preserves target-owned settings created by Step 4b, including `AzureWebJobsStorage`, `DEPLOYMENT_STORAGE_CONNECTION_STRING`, and the target-specific `APPLICATIONINSIGHTS_CONNECTION_STRING`.

The deny list and storage prefix are normalized to lowercase at runtime, so source apps with non-canonical key casing (e.g. `azurewebjobsstorage`) are stripped correctly and future contributors can add new deny-list entries in whichever casing reads best. Surviving source names replace every `:` with `__` before merging.

**Bash:**

```bash
(
  set -e
  trap 'unset SOURCE_SETTINGS TARGET_SETTINGS BODY' EXIT
  SUB=$(az account show --query id -o tsv)
  API='2024-04-01'
  SOURCE_SETTINGS=$(az rest --method post --uri "/subscriptions/$SUB/resourceGroups/<SOURCE_RESOURCE_GROUP>/providers/Microsoft.Web/sites/<SOURCE_APP_NAME>/config/appsettings/list?api-version=$API")
  TARGET_SETTINGS=$(az rest --method post --uri "/subscriptions/$SUB/resourceGroups/<RESOURCE_GROUP>/providers/Microsoft.Web/sites/<NEW_APP_NAME>/config/appsettings/list?api-version=$API")
  BODY=$(printf '%s\n%s\n' "$SOURCE_SETTINGS" "$TARGET_SETTINGS" | jq -s '
    (["WEBSITE_CONTENTAZUREFILECONNECTIONSTRING","WEBSITE_CONTENTSHARE","WEBSITE_CONTENTOVERVNET","WEBSITE_SKIP_CONTENTSHARE_VALIDATION","WEBSITE_RUN_FROM_PACKAGE","WEBSITE_RUN_FROM_ZIP","WEBSITE_USE_ZIP","FUNCTIONS_EXTENSION_VERSION","FUNCTIONS_WORKER_RUNTIME","FUNCTIONS_WORKER_RUNTIME_VERSION","FUNCTIONS_MAX_HTTP_CONCURRENCY","FUNCTIONS_WORKER_PROCESS_COUNT","FUNCTIONS_WORKER_DYNAMIC_CONCURRENCY_ENABLED","WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT","WEBSITE_USE_PLACEHOLDER_DOTNETISOLATED","WEBSITE_LOAD_CERTIFICATES","WEBSITE_MOUNT_ENABLED","ENABLE_ORYX_BUILD","SCM_DO_BUILD_DURING_DEPLOYMENT","WEBSITE_DNS_SERVER","WEBSITE_NODE_DEFAULT_VERSION","WEBSITE_VNET_ROUTE_ALL","AzureWebJobsDashboard","APPLICATIONINSIGHTS_CONNECTION_STRING"] | map(ascii_downcase)) as $deny |
    (.[0].properties | to_entries | map(select((.key | ascii_downcase) as $k | ($deny | index($k) | not) and ($k | startswith("azurewebjobsstorage") | not))) | map(. + {targetKey: (.key | gsub(":"; "__"))})) as $mapped |
    ($mapped | group_by(.targetKey | ascii_downcase) | map(select(length > 1) | map(.key))) as $sourceCollisions |
    if ($sourceCollisions | length) > 0
    then error("Mapped app-setting name collision; review setting names before retrying.")
    else {properties: (.[1].properties + ($mapped | map({key: .targetKey, value: .value}) | from_entries))}
    end')
  az rest --method patch --uri "/subscriptions/$SUB/resourceGroups/<RESOURCE_GROUP>/providers/Microsoft.Web/sites/<NEW_APP_NAME>/config/appsettings?api-version=$API" --headers 'Content-Type=application/json' --body "$BODY" --output none
)
```

> 💡 **App Insights**: `APPLICATIONINSIGHTS_CONNECTION_STRING` is intentionally **excluded** to preserve the target-specific value created by Step 4b. Step [4k](trigger-safety-and-monitoring.md#4k-verify-application-insights-monitoring) verifies monitoring and preserves AAD ingestion only when the source already used it.

> 💡 **Storage (`AzureWebJobsStorage*`)**: Every setting whose name starts with `AzureWebJobsStorage` is intentionally **excluded**, matching the published migration filter. Step 4b owns runtime storage end-to-end — the platform sets a fresh connection string for `<STORAGE_NAME>` matching the [MS Learn flex-consumption-how-to](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to?tabs=azure-cli%2Cazure-cli-publish&pivots=programming-language-csharp#create-a-flex-consumption-app) flow. If the source app was identity-based and you want to preserve that posture on the new app, run optional [4b.opt](app-creation.md#4bopt-identity-based-storage-optional-security-hardening) to re-derive the required variants against `<STORAGE_NAME>`.

> 💡 **Casing is preserved on the wire**: The `ascii_downcase` step is comparison-only. Surviving settings keep the exact key casing the source app had — they're PATCHed back unchanged.

**PowerShell 7:**

```powershell
$sourceJson = $targetJson = $sourceSettings = $targetSettings = $body = $accessToken = $secureToken = $null
try {
    $sub = az account show --query id -o tsv
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($sub)) { throw 'Failed to resolve the current subscription.' }
    $api = '2024-04-01'
    $base = "/subscriptions/$sub/resourceGroups"
    $sourceJson = az rest --method post --uri "$base/<SOURCE_RESOURCE_GROUP>/providers/Microsoft.Web/sites/<SOURCE_APP_NAME>/config/appsettings/list?api-version=$api"
    if ($LASTEXITCODE -ne 0) { throw 'Failed to read source app settings.' }
    $sourceSettings = $sourceJson | ConvertFrom-Json
    $sourceJson = $null
    $targetJson = az rest --method post --uri "$base/<RESOURCE_GROUP>/providers/Microsoft.Web/sites/<NEW_APP_NAME>/config/appsettings/list?api-version=$api"
    if ($LASTEXITCODE -ne 0) { throw 'Failed to read target app settings.' }
    $targetSettings = $targetJson | ConvertFrom-Json
    $targetJson = $null
    $rawDeny = @('WEBSITE_CONTENTAZUREFILECONNECTIONSTRING','WEBSITE_CONTENTSHARE','WEBSITE_CONTENTOVERVNET','WEBSITE_SKIP_CONTENTSHARE_VALIDATION','WEBSITE_RUN_FROM_PACKAGE','WEBSITE_RUN_FROM_ZIP','WEBSITE_USE_ZIP','FUNCTIONS_EXTENSION_VERSION','FUNCTIONS_WORKER_RUNTIME','FUNCTIONS_WORKER_RUNTIME_VERSION','FUNCTIONS_MAX_HTTP_CONCURRENCY','FUNCTIONS_WORKER_PROCESS_COUNT','FUNCTIONS_WORKER_DYNAMIC_CONCURRENCY_ENABLED','WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT','WEBSITE_USE_PLACEHOLDER_DOTNETISOLATED','WEBSITE_LOAD_CERTIFICATES','WEBSITE_MOUNT_ENABLED','ENABLE_ORYX_BUILD','SCM_DO_BUILD_DURING_DEPLOYMENT','WEBSITE_DNS_SERVER','WEBSITE_NODE_DEFAULT_VERSION','WEBSITE_VNET_ROUTE_ALL','AzureWebJobsDashboard','APPLICATIONINSIGHTS_CONNECTION_STRING')
    $deny = $rawDeny | ForEach-Object { $_.ToLowerInvariant() }
    $merged = [ordered]@{}
    foreach ($property in $targetSettings.properties.PSObject.Properties) { $merged[$property.Name] = $property.Value }
    $mappedSourceNames = @{}
    foreach ($property in $sourceSettings.properties.PSObject.Properties) {
        $lower = $property.Name.ToLowerInvariant()
        if ($deny -notcontains $lower -and -not $lower.StartsWith('azurewebjobsstorage')) {
            $targetName = $property.Name.Replace(':', '__')
            $normalizedTargetName = $targetName.ToLowerInvariant()
            if ($mappedSourceNames.ContainsKey($normalizedTargetName)) { throw "Source app-setting names '$($mappedSourceNames[$normalizedTargetName])' and '$($property.Name)' map to the same target name '$targetName'." }
            $mappedSourceNames[$normalizedTargetName] = $property.Name
            $merged[$targetName] = $property.Value
        }
    }
    $body = @{ properties = $merged } | ConvertTo-Json -Compress -Depth 10
    $accessToken = az account get-access-token --resource https://management.azure.com/ --query accessToken -o tsv
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($accessToken)) { throw 'Failed to acquire an Azure Resource Manager access token.' }
    $secureToken = ConvertTo-SecureString ($accessToken.Trim()) -AsPlainText -Force
    $accessToken = $null
    $uri = "https://management.azure.com$base/<RESOURCE_GROUP>/providers/Microsoft.Web/sites/<NEW_APP_NAME>/config/appsettings?api-version=$api"
    Invoke-RestMethod -Method Patch -Uri $uri -Authentication Bearer -Token $secureToken -ContentType 'application/json; charset=utf-8' -Body $body -ErrorAction Stop | Out-Null
}
finally {
    $sourceJson = $targetJson = $sourceSettings = $targetSettings = $body = $accessToken = $secureToken = $null
    Remove-Variable merged,mappedSourceNames -ErrorAction SilentlyContinue
}
```

> 🔒 **No file or secret-bearing command argument**: Unlike a `--settings @file.json` flow, nothing here touches disk. PowerShell sends the JSON body with `Invoke-RestMethod`, avoiding native command-line JSON escaping and keeping app-setting values out of process arguments on Windows, Linux, and macOS. Secret-bearing variables and the ARM access token are cleared whether the PATCH succeeds or fails. If the PATCH fails, re-run the entire block; both GETs and the merged PATCH are idempotent.
>
> If Azure returns extended error `04072` (`AppSetting with name ... is not allowed`), inspect the rejected name for Linux-invalid characters. A `:` rejection does not prove that its prefix is reserved; map `:` to `__`, rerun collision checks, and retry the full block.
