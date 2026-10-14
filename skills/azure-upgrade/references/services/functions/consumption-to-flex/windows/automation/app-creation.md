# App Creation

## Step 4: Create the Flex Consumption App

Since `az functionapp flex-migration` does not support Windows, each migration step is performed explicitly.

### New app naming (read before running 4b)

The new app's name is bound to `<NEW_APP_NAME>` for use in 4b and every subsequent step (4b.opt, 4c–4k, Step 5 deploy, Step 6 cutover, Step 7 cleanup).

**Default**: `<source>-flex` — e.g. `test-app` → `test-app-flex`.

> ⚠️ **Skill instruction**: Before running 4b, look at the user's original migration request. If they said "as `<name>`" or "named `<name>`" — follow that. Otherwise, **default to `<source>-flex`** and **announce the choice to the user before executing**, e.g.:
>
> > I'll create the new Flex app as `<source>-flex` in resource group `<RESOURCE_GROUP>` (region `<REGION>`). Say so if you'd prefer a different name.
>
> Then bind `<NEW_APP_NAME>` to the chosen name and proceed.

> 💡 Constraints: 2–60 chars, alphanumerics + hyphens, must start with a letter, no consecutive hyphens, globally unique in Azure (becomes `<APP_NAME>.azurewebsites.net`). If the default would exceed 60 chars or collides with an existing app, fall back to a shortened suffix (e.g. `<source>-fc`) and announce the fallback. Verify global uniqueness with `az functionapp show --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP>` (a `ResourceNotFound` error confirms the name is available in your RG; for cross-tenant collisions you'll only find out when 4b fails with a name-conflict error).

### Storage account binding (read before running 4a/4b)

The new Flex app needs a storage account bound at creation time. Track both `<STORAGE_NAME>` and `<STORAGE_RESOURCE_ID>` for the selected account:

| Mode | When to use | Storage metadata |
|------|-------------|------------------|
| **Reuse source** | Most migrations. Matches `az functionapp flex-migration` behavior on Linux. No extra resources. | Use the source runtime storage metadata from Step 3a |
| **Create new** | You want isolated storage for blast-radius, compliance, or test/prod separation | Use the metadata returned by 4a |
| **Use existing different** | You already have a target storage account provisioned (e.g. via IaC) | Resolve and verify its name and resource ID before proceeding |

For an existing different account supplied by name, resolve its metadata before continuing:

```bash
az graph query -q "resources | where type =~ 'microsoft.storage/storageaccounts' | where name =~ '<STORAGE_NAME>' | project name, resourceGroup, subscriptionId, id" --query "data[0]" -o json
```

If the query returns no account, stop and ask the user for the resource ID. Never guess the account's resource group.

> ⚠️ **Skill instruction**: Storage selection is always an explicit user decision. Before running 4a or 4b, use `ask_user` to choose **reuse source**, **create new**, or **use existing different**, even when the original request did not mention storage. Explain that reusing storage avoids another resource but shares runtime/deployment dependencies, while new storage provides isolation. Do not announce a default and proceed without a response.
>
> Bind `<STORAGE_NAME>` and `<STORAGE_RESOURCE_ID>` only after the user selects a mode. If the account is outside `<RESOURCE_GROUP>`, use its resource ID as the `--storage-account` argument in 4b.

> 💡 When reusing the source storage account, keep the deployment storage configuration created for the target Flex app. Do not copy the source app's Windows content-share or run-from-package settings.

### 4a. Create a Storage Account *(only if user chose "create new")*

Skip this entire sub-step if reusing the source account or pointing at an existing different one.

```bash
az storage account create --name <NEW_STORAGE_NAME> --resource-group <RESOURCE_GROUP> --location <REGION> --sku Standard_LRS --allow-blob-public-access false --query "{name:name,id:id}" -o json
```

Then bind `<STORAGE_NAME>` and `<STORAGE_RESOURCE_ID>` from the output for use in 4b.

### 4b. Create the Flex Consumption App

Use `<RUNTIME>` and `<TARGET_RUNTIME_VERSION>` resolved and recorded in Step 2c. Do not derive the target version from `FUNCTIONS_WORKER_RUNTIME_VERSION` at creation time; that setting is not guaranteed to be present or authoritative, and Windows Consumption leaves `siteConfig.windowsFxVersion` empty.

```bash
az functionapp list-flexconsumption-runtimes --location <REGION> --runtime <RUNTIME> --query "[?version=='<TARGET_RUNTIME_VERSION>'].version | [0]" -o tsv
```

Require the command to return `<TARGET_RUNTIME_VERSION>`. If it returns empty, stop and reassess the target version rather than creating the app with a guessed or unsupported value.

Create the new app. Set `<STORAGE_CREATE_REFERENCE>` to `<STORAGE_NAME>` when the account is in `<RESOURCE_GROUP>`; otherwise set it to `<STORAGE_RESOURCE_ID>`:

```bash
az functionapp create --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --storage-account <STORAGE_CREATE_REFERENCE> --flexconsumption-location <REGION> --runtime <RUNTIME> --runtime-version <TARGET_RUNTIME_VERSION>
```

> 💡 This command matches the basic Flex Consumption create flow documented in [Create a Flex Consumption app (MS Learn)](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to?tabs=azure-cli%2Cazure-cli-publish&pivots=programming-language-csharp#create-a-flex-consumption-app). The platform sets `AzureWebJobsStorage` to a fresh connection string for `<STORAGE_NAME>` and uses the same value for the One Deploy package container (`DEPLOYMENT_STORAGE_CONNECTION_STRING`). Identity-based runtime storage is **not** the default — see [4b.opt](#4bopt-identity-based-storage-optional-security-hardening) below if you need it.
>
> 💡 Unless Application Insights creation is explicitly disabled or blocked by policy, `az functionapp create` also creates a target Application Insights component and sets `APPLICATIONINSIGHTS_CONNECTION_STRING`. Record the component name and resource ID from the command output for verification in [4k](trigger-safety-and-monitoring.md#4k-verify-application-insights-monitoring).

### 4b.opt. Identity-Based Storage *(optional, security hardening)*

Skip this sub-step unless the user explicitly asked for identity-based storage on the new app, or Step 3a reported that the source runtime storage authentication was identity-based.

This is a post-create hardening pass that mirrors the optional pattern documented in [Configure deployment settings (MS Learn)](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to?tabs=azure-cli%2Cazure-cli-publish&pivots=programming-language-csharp#configure-deployment-settings) but extended to also cover the runtime `AzureWebJobsStorage` binding (not just the deployment container).

Ensure the system identity is enabled (4e covers this — run that first if you skipped):

```bash
az functionapp identity assign --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP>
```

Grant the system identity the three storage data-plane roles on `<STORAGE_RESOURCE_ID>`:

> 💡 **Why `--assignee-object-id ... --assignee-principal-type ServicePrincipal`?** The bare `--assignee <pid>` form makes the CLI do a Microsoft Graph lookup to determine the principal type, which (a) prints a deprecation warning on every call and (b) intermittently fails with `Cannot find user or service principal in graph database` for managed identities created seconds earlier (Graph propagation race). Specifying `--assignee-object-id` plus `--assignee-principal-type ServicePrincipal` skips the lookup entirely.

```bash
az role assignment create --assignee-object-id $(az functionapp identity show --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --query principalId -o tsv) --assignee-principal-type ServicePrincipal --role "Storage Blob Data Owner" --scope <STORAGE_RESOURCE_ID>
```

```bash
az role assignment create --assignee-object-id $(az functionapp identity show --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --query principalId -o tsv) --assignee-principal-type ServicePrincipal --role "Storage Queue Data Contributor" --scope <STORAGE_RESOURCE_ID>
```

```bash
az role assignment create --assignee-object-id $(az functionapp identity show --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --query principalId -o tsv) --assignee-principal-type ServicePrincipal --role "Storage Table Data Contributor" --scope <STORAGE_RESOURCE_ID>
```

Add the identity-based `AzureWebJobsStorage__*` settings pointing at `<STORAGE_NAME>`:

```bash
az functionapp config appsettings set --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --settings "AzureWebJobsStorage__accountName=<STORAGE_NAME>" "AzureWebJobsStorage__credential=managedidentity" "AzureWebJobsStorage__blobServiceUri=https://<STORAGE_NAME>.blob.core.windows.net" "AzureWebJobsStorage__queueServiceUri=https://<STORAGE_NAME>.queue.core.windows.net" "AzureWebJobsStorage__tableServiceUri=https://<STORAGE_NAME>.table.core.windows.net"
```

Remove the platform-set connection-string binding so the runtime uses identity exclusively:

```bash
az functionapp config appsettings delete --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --setting-names AzureWebJobsStorage
```

> ⚠️ **User-assigned identity variant**: If you want a UMI instead of the system identity, replace the role-assignment `--assignee` with the UMI principal ID, attach the UMI via `az functionapp identity assign --identities <UMI_RESOURCE_ID>` in 4f, and add `AzureWebJobsStorage__clientId=<UMI_CLIENT_ID>` to the appsettings set call above.

> 💡 **Deployment storage**: The recipe above only re-establishes identity for the runtime `AzureWebJobsStorage` binding. To also move the One Deploy package container off the connection string, follow the separate [Configure deployment settings](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to?tabs=azure-cli%2Cazure-cli-publish&pivots=programming-language-csharp#configure-deployment-settings) recipe with `--deployment-storage-auth-type SystemAssignedIdentity` (or `UserAssignedIdentity`).
