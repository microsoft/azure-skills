# Automation: Consumption to Flex Consumption Upgrade

> These are the Azure CLI scripts to automate the upgrade from Linux Consumption plan to Flex Consumption plan.
> All scripts use `bash` syntax compatible with Azure Cloud Shell. For PowerShell, adapt accordingly.
>
> **Source docs**: [Linux migration guide](https://learn.microsoft.com/en-us/azure/azure-functions/migration/migrate-plan-consumption-to-flex?pivots=platform-linux)

## Prerequisites

```bash
# Verify required tools
az version --query '"azure-cli"' -o tsv
jq --version

# Install resource-graph extension
az extension add --name resource-graph

# Login and set subscription
az login
az account set --subscription <SUBSCRIPTION_ID>
```

If `az` or `jq` is unavailable, stop and provide the relevant installation guidance. If the Azure CLI version is lower than `2.77.0`, stop and require an upgrade before running migration commands.

---

## Step 1: Identify Candidate Apps

```bash
# List all Linux Consumption apps with eligibility status
az functionapp flex-migration list
```

This returns two arrays:
- `eligible_apps` — apps that can be migrated to Flex Consumption
- `ineligible_apps` — apps with specific reasons why not

The output includes app name, resource group, location, and runtime stack for each app.

---

## Step 2: Assessment Checks

Set variables for your app:

```bash
appName=<APP_NAME>
rgName=<RESOURCE_GROUP>
```

### 2a. Confirm Region Compatibility

```bash
# List all regions where Flex Consumption is available
az functionapp list-flexconsumption-locations --query "sort_by(@, &name)[].{Region:name}" -o table
```

### 2b. Verify Language Stack Compatibility

Supported stacks: `dotnet-isolated`, `node`, `java`, `python`, `powershell`, `custom`.
**Not supported**: `dotnet` (in-process) — must migrate to isolated first.

### 2c. Verify Stack Version Compatibility

```bash
# Check supported versions for a specific runtime in a specific region
az functionapp list-flexconsumption-runtimes --location <REGION> --runtime <LANGUAGE_STACK> \
    --query '[].{version:version}' -o tsv
```

Replace `<REGION>` with the app's region and `<LANGUAGE_STACK>` with one of: `dotnet-isolated`, `java`, `node`, `powershell`, `python`.

### 2d. Check Deployment Slots

```bash
# List any deployment slots
az functionapp deployment slot list --name $appName --resource-group $rgName --output table
```

If this returns entries, the app has slots. Flex Consumption does NOT support slots — plan accordingly.

### 2e. Check TLS/SSL Certificates

```bash
# List certificates available to the app
az webapp config ssl list --resource-group $rgName
```

If this returns output, determine whether the source app actually uses those certificates. Plan to re-add used certificates after migration with the documented [site-scoped certificate process](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to#configure-site-scoped-certificates), verify the per-app limits, and update certificate-loading code to use the documented Linux file paths.

### 2f. Check Blob Storage Triggers

```bash
# Find blob triggers NOT using EventGrid source
az functionapp function list --name $appName --resource-group $rgName \
  --query "[?config.bindings[0].type=='blobTrigger' && config.bindings[0].source!='EventGrid'].{Function:name,TriggerType:config.bindings[0].type,Source:config.bindings[0].source}" \
  --output table
```

If this returns rows, convert those blob triggers from `LogsAndContainerScan` to `EventGrid` before upgrading.

---

## Step 3: Pre-Migration — Collect Settings

### 3a. Collect App Settings

```bash
appName=<APP_NAME>
rgName=<RESOURCE_GROUP>

# Inventory setting names only; never display or persist general setting values
az functionapp config appsettings list --name $appName --resource-group $rgName \
    --query "[].name" -o tsv
```

### 3b. Collect Application Configurations

```bash
appName=<APP_NAME>
rgName=<RESOURCE_GROUP>

echo "Getting commonly used site settings..."
az functionapp config show --name $appName --resource-group $rgName \
    --query "{http20Enabled:http20Enabled, httpsOnly:httpsOnly, minTlsVersion:minTlsVersion, \
    minTlsCipherSuite:minTlsCipherSuite, clientCertEnabled:clientCertEnabled, \
    clientCertMode:clientCertMode, clientCertExclusionPaths:clientCertExclusionPaths}"

echo "Checking for SCM basic publishing credentials policies..."
az resource show --resource-group $rgName --name scm --namespace Microsoft.Web \
    --resource-type basicPublishingCredentialsPolicies --parent sites/$appName --query properties

echo "Checking for the maximum scale-out limit configuration..."
az functionapp config appsettings list --name $appName --resource-group $rgName \
    --query "[?name=='WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT'].value" -o tsv

echo "Checking for any file share mount configurations..."
az webapp config storage-account list --name $appName --resource-group $rgName

echo "Checking for any custom domains..."
az functionapp config hostname list --webapp-name $appName --resource-group $rgName \
    --query "[?contains(name, 'azurewebsites.net')==\`false\`]" --output table

echo "Checking for any CORS settings..."
az functionapp cors show --name $appName --resource-group $rgName
```

### 3c. Identify Managed Identities and Role Assignments

```bash
appName=<APP_NAME>
rgName=<RESOURCE_GROUP>

echo "Checking for a system-assigned managed identity..."
systemUserId=$(az functionapp identity show --name $appName --resource-group $rgName \
    --query "principalId" -o tsv)

if [[ -n "$systemUserId" ]]; then
    echo "System-assigned identity principal ID: $systemUserId"
    echo "Checking for role assignments..."
    az role assignment list --assignee $systemUserId --all
else
    echo "No system-assigned identity found."
fi

echo "Checking for user-assigned managed identities..."
userIdentities=$(az functionapp identity show --name $appName --resource-group $rgName \
    --query 'userAssignedIdentities' -o json)

if [[ "$userIdentities" != "{}" && "$userIdentities" != "null" ]]; then
    echo "$userIdentities" | jq -c 'to_entries[]' | while read -r identity; do
        echo "User-assigned identity: $(echo "$identity" | jq -r '.key' | sed 's|.*/userAssignedIdentities/||')"
        echo "Checking for role assignments..."
        az role assignment list --assignee $(echo "$identity" | jq -r '.value.principalId') --all --output json
        echo
    done
else
    echo "No user-assigned identities found."
fi
```

### 3d. Check Built-in Authentication

```bash
az webapp auth show --name $appName --resource-group $rgName
```

### 3e. Review Inbound Access Restrictions

```bash
az functionapp config access-restriction show --name $appName --resource-group $rgName
```

### 3f. Get Deployment Package (if needed)

Ideally your project files are in source control and you can redeploy from there. If not:

#### Check WEBSITE_RUN_FROM_PACKAGE

```bash
UPGRADE_DIR=<UPGRADE_DIR>
(
    set -e
    trap 'unset runFromPackage' EXIT
    echo "Checking run-from-package configuration..."
    runFromPackage=$(az functionapp config appsettings list --name $appName --resource-group $rgName \
        --query "[?name=='WEBSITE_RUN_FROM_PACKAGE'].value | [0]" -o tsv)

    if [[ "$runFromPackage" =~ ^https:// ]]; then
        echo "Downloading the remote deployment package..."
        curl --fail --location --silent --show-error --output "$UPGRADE_DIR/source-package.zip" "$runFromPackage"
        echo "Downloaded the remote deployment package without displaying its URL."
    elif [[ -n "$runFromPackage" ]]; then
        echo "Linux Consumption requires WEBSITE_RUN_FROM_PACKAGE to be a remote URL; found an unsupported non-URL value." >&2
        exit 1
    else
        echo "No run-from-package URL was detected; use the scm-releases fallback below or redeploy from source control."
    fi
)
```

If the remote package was downloaded, skip the storage download below. If no URL was configured, continue with the `scm-releases` fallback.

#### Download from scm-releases blob container

Linux Consumption apps store deployment packages in the `scm-releases` blob container (in `squashfs` format).

> 📁 The download below writes to `<UPGRADE_DIR>` (default: `.azure-upgrade/<source-app-name>/`). See [Artifact Output Policy](../../../../global-rules.md#artifact-output-policy). Resolve `UPGRADE_DIR` once at session start and create the directory before running.

```bash
appName=<APP_NAME>
rgName=<RESOURCE_GROUP>
UPGRADE_DIR=<UPGRADE_DIR>   # e.g. .azure-upgrade/$appName  — see global-rules

(
    set -e
    trap 'unset AZURE_STORAGE_CONNECTION_STRING' EXIT
    echo "Getting the storage account connection string..."
    export AZURE_STORAGE_CONNECTION_STRING=$(az functionapp config appsettings list --name $appName --resource-group $rgName \
        --query "[?name=='AzureWebJobsStorage'].value | [0]" -o tsv)
    if [[ -z "$AZURE_STORAGE_CONNECTION_STRING" ]]; then
        echo "AzureWebJobsStorage was not found." >&2
        exit 1
    fi

    echo "Getting the package name..."
    packageName=$(az storage blob list --container-name scm-releases --query "[0].name" -o tsv)
    if [[ -z "$packageName" ]]; then
        echo "No deployment package was found in the scm-releases container." >&2
        exit 1
    fi

    echo "Downloading package: $packageName -> $UPGRADE_DIR/$packageName"
    az storage blob download --container-name scm-releases --name "$packageName" \
        --file "$UPGRADE_DIR/$packageName" --no-progress --output none
    echo "Downloaded package: $packageName"
)
```

> 💡 If your storage account is restricted to managed identity access only, you may need to grant your Azure account the `Storage Blob Data Reader` role.

---

## Step 4: Create the Flex Consumption App

```bash
# Automated migration — creates new app and migrates most configurations
az functionapp flex-migration start \
    --source-name <SOURCE_APP_NAME> \
    --source-resource-group <SOURCE_RESOURCE_GROUP> \
    --name <NEW_APP_NAME> \
    --resource-group <RESOURCE_GROUP>
```

**Optional flags**:
- `--storage-account <ACCOUNT>` — use a different storage account
- `--maximum-instance-count <COUNT>` — set max scale-out instances
- `--skip-access-restrictions` — skip migrating IP access restrictions
- `--skip-cors` — skip migrating CORS settings
- `--skip-hostnames` — skip migrating custom domains
- `--skip-managed-identities` — skip migrating managed identity configurations
- `--skip-storage-mount` — skip migrating storage mount configurations

The command automatically:
- Assesses your source app for Flex Consumption compatibility
- Creates a new function app in the Flex Consumption plan
- Migrates app settings, identity assignments, storage mounts, CORS, custom domains, and access restrictions

### Verify Migration Results

```bash
# Verify new app exists and is configured
az functionapp show --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> \
    --query "{name:name, kind:kind, sku:properties.sku}" --output table

# Review migrated app-setting names without displaying values
az functionapp config appsettings list --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> \
    --query "[].name" -o tsv

# Check managed identity
az functionapp identity show --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP>

# Check custom domains
az functionapp config hostname list --webapp-name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> \
    --output table
```

### Configure Items Not Auto-Migrated

The `flex-migration start` command handles most settings, but these may need manual configuration:

#### Built-in Authentication

```bash
# Recreate auth settings if your original app used Easy Auth
az webapp auth update --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> \
    --enabled true --action <AUTH_ACTION>
```

#### Scale and Concurrency (if custom values needed)

```bash
# Set maximum scale-out (default: 100, range: 1-1000)
az functionapp scale config set --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> \
    --maximum-instance-count <MAX_SCALE_SETTING>
```

> ⚠️ Reducing below 40 for HTTP apps can cause frequent request failures.

---

## Step 5: Deploy Code

> ⚠️ **Code is NOT automatically migrated.** The new app is created with config only — you must deploy code separately.

### ask_user: Choose Deployment Method

Present these options to the user:

> Your new Flex Consumption app `<NEW_APP_NAME>` has been created and configured. Now we need to deploy your function code. How would you like to proceed?
>
> 1. **Update CI/CD pipeline** — I'll help you update your Azure Pipelines or GitHub Actions workflow to target the new app
> 2. **Deploy from local project** — I'll run `func azure functionapp publish <NEW_APP_NAME>` from your project directory  
> 3. **Deploy existing package** — I'll deploy the package we downloaded earlier from the original app

---

### Option A: Update CI/CD Pipeline (if user selects option 1)

Update your existing pipeline (Azure Pipelines or GitHub Actions) to target the new app name.

- [Build and deploy with Azure Pipelines](https://learn.microsoft.com/en-us/azure/azure-functions/functions-how-to-azure-devops)
- [Build and deploy with GitHub Actions](https://learn.microsoft.com/en-us/azure/azure-functions/functions-how-to-github-actions)

### Option B: Deploy from Local Project (if user selects option 2)

Verify that Azure Functions Core Tools v4 is available:

```bash
func --version
```

If `func` is unavailable or the reported major version is not `4`, stop and provide the [Core Tools installation guidance](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local#install-the-azure-functions-core-tools). Do not install or upgrade Core Tools without user approval; offer the pipeline or existing-package deployment options instead.

```bash
# From your project directory
func azure functionapp publish <NEW_APP_NAME>
```

### Option C: Deploy Existing Package (if user selects option 3)

```bash
# Deploy the zip package downloaded in Step 3 (resolves to <UPGRADE_DIR>/<PACKAGE_NAME>
# per the Artifact Output Policy in references/global-rules.md)
az functionapp deployment source config-zip --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> \
    --src <UPGRADE_DIR>/<PACKAGE_NAME>
```

### After Successful Deployment

Inform the user:

> Code deployed! Next steps to consider:
>
> - The original app is still running — keep it as rollback for a few days
> - Update any clients/pipelines to point to the new URL
> - Enable HTTPS-only and managed identity on the new app for better security
> - When confident, you can delete the original app

---

## Step 6: Post-Upgrade Validation

### Smoke Test (run this first)

```bash
# Minimum viability check — confirm the app is reachable at all
DEFAULT_HOST=$(az functionapp show --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> \
    --query "defaultHostName" -o tsv)

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://$DEFAULT_HOST")
echo "App responded with HTTP $HTTP_STATUS"

# Expected: 2xx or 401/404 (means the host is up). 
# If 503 or connection refused → the app failed to start. Check logs:
#   az functionapp log tail --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP>
```

### Verify Plan

```bash
az functionapp show --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --query "serverFarmId"
```

### Test HTTP Endpoints

```bash
# Test an HTTP trigger function
curl -s -o /dev/null -w "%{http_code}" "https://$DEFAULT_HOST/api/<FUNCTION_NAME>"
```

### Performance Benchmarks (Application Insights KQL)

```kql
requests
| where timestamp > ago(1d)
| summarize percentiles(duration, 50, 95, 99) by bin(timestamp, 1h)
| render timechart
```

### Check for Errors

```kql
traces
| where severityLevel == 3
| where cloud_RoleName == "<NEW_APP_NAME>"
| where timestamp > ago(1d)
| project timestamp, message, operation_Name, customDimensions
| order by timestamp desc
```

---

## Step 7: Cleanup (Optional)

Do not offer source deletion until all of these conditions are verified:

1. all applicable production HTTP traffic, clients, DNS, and custom domains use the target;
2. every applicable production trigger has completed source-first cutover and target validation;
3. no production-readiness work remains deferred;
4. the source no longer processes production workloads.

If any condition is incomplete, retain the source for rollback and record cleanup as skipped or deferred.

Only after every condition passes, use `ask_user` immediately before deletion:

> Production cutover is complete and source app `<SOURCE_APP_NAME>` is no longer processing production workloads. May I permanently delete it? This is irreversible and removes the rollback app.

Run only after that explicit approval:

```bash
az functionapp delete --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP>
```

> 💡 No rush. The Consumption plan only charges for actual usage, so keeping the old app (with triggers disabled) costs very little. We recommend keeping it for a few days/weeks.

---

## Rollback

If the source app was previously stopped, use `ask_user` immediately before restarting it:

> May I restart source app `<SOURCE_APP_NAME>` in resource group `<SOURCE_RESOURCE_GROUP>` to restore processing?

Run only after that explicit approval:

```bash
az functionapp start --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP>
```

Deleting the new Flex app requires a separate confirmation:

```bash
az functionapp delete --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP>
```
