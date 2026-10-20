# App Creation

## Step 4: Create the Flex Consumption App

Since `az functionapp flex-migration` does not support Windows, each migration step is performed explicitly.

> **Resume guard**: If the user supplies an existing target resource ID after a provisioning handoff, follow [Adopt a User-Provisioned Target](#adopt-a-user-provisioned-target) before naming or storage-selection defaults. Do not run resource creation or post-create storage conversion against that target.

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

**Storage authentication preflight (before creating the app):**

Read the selected account's configuration without retrieving storage keys:

```bash
az storage account show --ids <STORAGE_RESOURCE_ID> --query "{id:id,allowSharedKeyAccess:allowSharedKeyAccess}" -o json
```

Require a successful command and the expected account ID. In PowerShell, check `$LASTEXITCODE` immediately. A failed read or missing account is a blocker, not evidence that Shared Key access is allowed. On a successful read, `false` prohibits Shared Key authentication; `true` or an unset (`null`) property permits it at the account level. Also confirm any policy requirements with the user. Repeat this check for deployment storage if it uses a different account.

If either account prohibits Shared Key access, or policy requires identity-based storage, **do not run the `az functionapp create` command below**. Its basic flow configures host storage with a connection string; deployment-storage identity flags alone don't make host storage identity-based. Record Step 4b as blocked in `<UPGRADE_DIR>/upgrade-status.md`, explain the limitation, and direct the user to identity-first ARM/Bicep provisioning using the [Flex Consumption IaC samples](https://github.com/Azure-Samples/azure-functions-flex-consumption-samples/tree/main/IaC). Do not enable Shared Key access, retrieve keys, or attempt connection-string creation followed by conversion.

**When blocked on keyless provisioning, provide this handoff:** Show the user the assessed target name, region, runtime/version, selected storage resource IDs, and progress-file path. Explain that they must provision an **empty target dedicated to this migration**, with managed identity authentication and roles for both storage connections and the agreed monitoring configuration. Do not deploy function code yet: built-in authentication and non-HTTP trigger safety still need migration checks. Leave the source unchanged. Ask them to return with the target's full Azure resource ID, not credentials, using:

```text
Resume the Flex Consumption migration for <SOURCE_APP_NAME> using progress at <UPGRADE_DIR>/upgrade-status.md.
I provisioned a keyless target at <TARGET_RESOURCE_ID>. Use that existing target; do not create another app.
```

#### Adopt a User-Provisioned Target

1. Load and reconcile the saved progress using [Migration Progress](../progress-tracking.md). Keep Step 4b blocked while checking the target. If the progress file is missing, stop and ask for its location rather than guessing prior work. If it already identifies a different adopted target, stop and ask; never carry completed target work across different apps.
2. Require a full `Microsoft.Web/sites` resource ID, not a slot, and reject the source app itself. Resolve the target read-only. Require the source and target to be in the active subscription because subsequent migration commands assume that scope; don't silently switch subscriptions. Verify its name, resource group, region, Flex plan, runtime/version, and storage accounts against the saved decisions. Report mismatches and ask the user to resolve them or approve a revised plan before adopting the target.
3. Verify managed identity configuration and effective role assignments for **both** [host storage](https://learn.microsoft.com/en-us/azure/azure-functions/manage-connections?pivots=functions-auth-identity&tabs=host) and [deployment storage](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to#configure-deployment-settings), and the monitoring configuration expected by Step 4k. Resolve the target's configured Application Insights component read-only; bind `<TARGET_AI_NAME>`, `<TARGET_AI_RESOURCE_ID>`, and `<TARGET_AI_RESOURCE_GROUP>` from the verified component and its resource ID. Do not assume it is in the function app's resource group. Missing or ambiguous component metadata is a blocker; ask the user to identify the configured component rather than guessing. Host storage needs `Storage Blob Data Owner` plus permissions required by its triggers, bindings, and diagnostics. Deployment storage needs blob read/write access, normally `Storage Blob Data Contributor`; an existing `Storage Blob Data Owner` assignment covers this for the same identity and scope. Confirm permission to create missing role assignments; Contributor alone doesn't grant it. Read failures, missing permissions, incomplete configuration, and failed access validation remain blockers. Don't display secrets or automatically repair the target.
4. Check the target's deployed-function inventory and use `ask_user` to confirm it is an empty app dedicated to this migration and approve adopting it for the remaining configuration and deployment steps. A failed inventory isn't proof the target is empty. If code is already deployed or the app serves another workload, keep the migration blocked and request an empty target.
5. After verification and approval, bind `<NEW_APP_NAME>` and `<RESOURCE_GROUP>` from the resolved target, and `<STORAGE_NAME>` and `<STORAGE_RESOURCE_ID>` from its verified host storage. Preserve all source identifiers. Record the target resource ID, deployment storage resource ID, storage identity IDs, and all three monitoring placeholders above in progress Notes; never record keys or connection strings. Mark Step 4b `complete` with note `externally provisioned and verified`; mark pending 4a `skipped — storage provisioned externally` and 4b.opt `skipped — target storage identities verified; no conversion required`. Preserve already completed work. Resume at the first unfinished step at or after 4c, retaining all app-setting, authentication, trigger-safety, deployment, and source-change approval gates.

After adoption, do not fall through to the basic creation flow below or rerun storage conversion.

Continue with the basic creation flow only when Shared Key authentication is permitted for both storage connections.

Use `<RUNTIME>` and `<TARGET_RUNTIME_VERSION>` resolved and recorded in Step 2c. Do not derive the target version from `FUNCTIONS_WORKER_RUNTIME_VERSION` at creation time; that setting is not guaranteed to be present or authoritative, and Windows Consumption leaves `siteConfig.windowsFxVersion` empty.

```bash
az functionapp list-flexconsumption-runtimes --location <REGION> --runtime <RUNTIME> --query "[?version=='<TARGET_RUNTIME_VERSION>'].version | [0]" -o tsv
```

Require the command to return `<TARGET_RUNTIME_VERSION>`. If it returns empty, stop and reassess the target version rather than creating the app with a guessed or unsupported value.

Create the new app. Set `<STORAGE_CREATE_REFERENCE>` to `<STORAGE_NAME>` when the account is in `<RESOURCE_GROUP>`; otherwise set it to `<STORAGE_RESOURCE_ID>`:

```bash
az functionapp create --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --storage-account <STORAGE_CREATE_REFERENCE> --flexconsumption-location <REGION> --runtime <RUNTIME> --runtime-version <TARGET_RUNTIME_VERSION>
```

> 💡 This command matches the basic Flex Consumption create flow documented in [Create a Flex Consumption app (MS Learn)](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to?tabs=azure-cli%2Cazure-cli-publish&pivots=programming-language-csharp#create-a-flex-consumption-app). The platform sets `AzureWebJobsStorage` to a fresh connection string for `<STORAGE_NAME>` and uses the same value for the One Deploy package container (`DEPLOYMENT_STORAGE_CONNECTION_STRING`). Identity-based runtime storage is **not** the default — see [4b.opt](#4bopt-identity-based-storage) for conversion only where Shared Key authentication is permitted during creation.
>
> 💡 Unless Application Insights creation is explicitly disabled or blocked by policy, `az functionapp create` also creates a target Application Insights component and sets `APPLICATIONINSIGHTS_CONNECTION_STRING`. Resolve the configured component read-only and bind `<TARGET_AI_NAME>`, `<TARGET_AI_RESOURCE_ID>`, and `<TARGET_AI_RESOURCE_GROUP>` from its verified metadata, not the function app's resource group. Record all three in progress Notes for [4k](trigger-safety-and-monitoring.md#4k-verify-application-insights-monitoring); missing, unreadable, or ambiguous component metadata remains a blocker.

### 4b.opt. Identity-Based Storage

For an app created through the permitted connection-string flow, run this sub-step if the user requested identity-based storage or Step 3a reported identity-based source storage; otherwise skip it. This post-create conversion isn't a workaround for the blocked preflight above. When Shared Key authentication is prohibited, identity-based host and deployment storage are functional requirements that must be satisfied through identity-first provisioning before resuming.

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

> 💡 **Deployment storage is separate**: The commands above configure only runtime `AzureWebJobsStorage`. To also move the One Deploy package container off the connection string, follow [Configure deployment settings](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to?tabs=azure-cli%2Cazure-cli-publish&pivots=programming-language-csharp#configure-deployment-settings) with `--deployment-storage-auth-type SystemAssignedIdentity` (or `UserAssignedIdentity`) and verify the deployment identity's blob permissions. Do not report deployment storage as identity-based just because runtime storage was converted.
