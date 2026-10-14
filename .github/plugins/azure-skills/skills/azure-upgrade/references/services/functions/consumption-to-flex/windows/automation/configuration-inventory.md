# Configuration Inventory

## Step 3: Pre-Migration — Collect Settings

> 💡 App settings themselves are migrated in Step 4c using a safe two-phase pattern. This section collects the *other* configuration (site config, identities, auth, access restrictions, deployment package) that must be replicated on the new app.

### 3a. Collect Application Configurations

Common site settings:

```bash
az functionapp config show --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query "{http20Enabled:http20Enabled, httpsOnly:httpsOnly, minTlsVersion:minTlsVersion, minTlsCipherSuite:minTlsCipherSuite, clientCertEnabled:clientCertEnabled, clientCertMode:clientCertMode, clientCertExclusionPaths:clientCertExclusionPaths}"
```

SCM basic publishing credentials policies:

```bash
az resource show --resource-group <RESOURCE_GROUP> --name scm --namespace Microsoft.Web --resource-type basicPublishingCredentialsPolicies --parent sites/<APP_NAME> --query properties
```

Maximum scale-out limit:

```bash
az functionapp config appsettings list --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query "[?name=='WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT'].value" -o tsv
```

Runtime storage account:

`AzureWebJobsStorage__accountName` is safe to read directly when the source uses identity-based storage. Otherwise, extract `AccountName` from the secret-bearing `AzureWebJobsStorage` connection string in scoped memory. Display and record only the resolved storage resource metadata.

**Bash:**

```bash
(
  set -e
  trap 'unset storageConnection' EXIT
  storageName=$(az functionapp config appsettings list --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query "[?name=='AzureWebJobsStorage__accountName'].value | [0]" -o tsv)
  if [[ -z "$storageName" ]]; then
    storageAuthMode=connection-string
    storageConnection=$(az functionapp config appsettings list --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query "[?name=='AzureWebJobsStorage'].value | [0]" -o tsv)
    storageName=$(printf '%s' "$storageConnection" | awk -F';' '{for(i=1;i<=NF;i++){split($i,a,"="); if(tolower(a[1])=="accountname"){print a[2]; exit}}}')
  else
    storageAuthMode=identity-based
  fi
  if [[ ! "$storageName" =~ ^[a-z0-9]{3,24}$ ]]; then
    echo "Could not resolve a valid runtime storage account name." >&2
    exit 1
  fi
  storageJson=$(az graph query -q "resources | where type =~ 'microsoft.storage/storageaccounts' | where name =~ '$storageName' | project name, resourceGroup, subscriptionId, id" --query "data[0]" -o json)
  if [[ -z "$storageJson" || "$storageJson" == "null" ]]; then
    echo "Runtime storage account '$storageName' was not found in accessible subscriptions." >&2
    exit 1
  fi
  printf '%s\n' "$storageJson"
  printf 'Runtime storage authentication: %s\n' "$storageAuthMode"
)
```

**PowerShell 7:**

```powershell
$storageConnection = $null
try {
    $storageName = az functionapp config appsettings list --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query "[?name=='AzureWebJobsStorage__accountName'].value | [0]" -o tsv
    if ([string]::IsNullOrWhiteSpace($storageName)) {
        $storageAuthMode = 'connection-string'
        $storageConnection = az functionapp config appsettings list --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query "[?name=='AzureWebJobsStorage'].value | [0]" -o tsv
        if ($storageConnection -match '(?:^|;)AccountName=([^;]+)') { $storageName = $Matches[1] }
    }
    else {
        $storageAuthMode = 'identity-based'
        $storageName = $storageName.Trim()
    }
    if ($storageName -notmatch '^[a-z0-9]{3,24}$') { throw 'Could not resolve a valid runtime storage account name.' }
    $storage = az graph query -q "resources | where type =~ 'microsoft.storage/storageaccounts' | where name =~ '$storageName' | project name, resourceGroup, subscriptionId, id" --query "data[0]" -o json | ConvertFrom-Json
    if ($null -eq $storage) { throw "Runtime storage account '$storageName' was not found in accessible subscriptions." }
    $storage | ConvertTo-Json
    Write-Output "Runtime storage authentication: $storageAuthMode"
}
finally {
    $storageConnection = $null
}
```

Record the safe `name`, `resourceGroup`, `subscriptionId`, `id`, and authentication mode. Never record or display the connection string. If the account cannot be resolved uniquely, stop and ask the user for its resource ID.

File share mount metadata:

```bash
az webapp config storage-account list --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query "[].{customId:name,accountName:value.accountName,shareName:value.shareName,type:value.type,mountPath:value.mountPath,state:value.state}" -o table
```

Record the custom ID, storage account name, share name, type, and mount path for every result. Windows Consumption doesn't support explicit storage mounts, even though the control plane can retain and return this metadata. Catalog it as **not migrated** and explain that it might be stale or never exercised by the source runtime. Don't retrieve storage keys or configure a target mount.

Custom domains (excluding the default `*.azurewebsites.net`):

```bash
az functionapp config hostname list --webapp-name <APP_NAME> --resource-group <RESOURCE_GROUP> --query "[?!contains(name, 'azurewebsites.net')]" --output table
```

CORS settings:

```bash
az functionapp cors show --name <APP_NAME> --resource-group <RESOURCE_GROUP>
```

### 3b. Identify Managed Identities and Role Assignments

Get the system-assigned identity's principal ID:

```bash
az functionapp identity show --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query principalId -o tsv
```

> If the principal ID above is non-empty, list its role assignments (substitute `<PRINCIPAL_ID>`):

```bash
az role assignment list --assignee <PRINCIPAL_ID> --all
```

List user-assigned managed identities attached to the app:

```bash
az functionapp identity show --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query userAssignedIdentities -o json
```

> For each identity in the output, copy its `principalId` and list its role assignments using the same `az role assignment list --assignee <PRINCIPAL_ID> --all` command above.

### 3c. Check Built-in Authentication

```bash
az webapp auth show --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query "{enabled:enabled,unauthenticatedClientAction:unauthenticatedClientAction,defaultProvider:defaultProvider,tokenStoreEnabled:tokenStoreEnabled,allowedAudiences:allowedAudiences,allowedExternalRedirectUrls:allowedExternalRedirectUrls,isAuthFromFile:isAuthFromFile,providers:{aadClientId:clientId,githubClientId:gitHubClientId,googleClientId:googleClientId,facebookAppId:facebookAppId,twitterConsumerKey:twitterConsumerKey,microsoftAccountClientId:microsoftAccountClientId}}" -o json
```

Record only this nonsecret summary. Never query, display, or persist provider secret fields. If `isAuthFromFile` is true or the source uses a provider not represented by this projection, record that provider discovery requires manual review without displaying the auth file. Built-in authentication is handled in [Step 4f.auth](built-in-authentication.md#4fauth-configure-built-in-authentication).

### 3d. Review Inbound Access Restrictions

```bash
az functionapp config access-restriction show --name <APP_NAME> --resource-group <RESOURCE_GROUP>
```
