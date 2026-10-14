# Code Deployment

## Step 5: Deploy Code

> ⚠️ **Code is NOT automatically migrated.** The new app is created with config only — you must deploy code separately.
>
> ✅ **Trigger safety when all disable-capable functions were approved and verified disabled**: Only HTTP triggers and any hyphenated functions following their recorded Step 4j path will be live after the runtime starts; per-function cutover for disable-capable functions happens in Step 6.
>
> ⚠️ **If disablement was declined**: Do not deploy until the required Step 4j warning and explicit deployment approval have been completed. Non-HTTP functions may begin processing or running schedules immediately after deployment.
>
> ⛔ **Built-in authentication gate**: If the source used Easy Auth, Step 4f.auth must be complete before deployment. If it is deferred or blocked, stop before placing application code on the target; otherwise previously protected endpoints could become publicly accessible.
>
> ✅ **Access-key decision**: Step 4l must record either target-generated keys or source-key preservation before deployment. Key values are applied only after functions synchronize.

### Confirm Deferred App Settings Are Ready

If Step 4c deferred source app settings, list target setting names without values:

```bash
az functionapp config appsettings list --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --query "[].name" -o tsv
```

Then use `ask_user`:

> Source app settings were deferred. Have all application-specific settings required by this deployment been configured on `<NEW_APP_NAME>` using target-specific or intentionally shared dependencies?

Do not deploy until the user confirms. Target-generated settings such as `AzureWebJobsStorage` and `APPLICATIONINSIGHTS_CONNECTION_STRING` do not replace application-specific connection settings required by bindings or code.

### ask_user: Choose Deployment Method

Present these options to the user:

> Your new Flex Consumption app `<NEW_APP_NAME>` has been created and configured. Now we need to deploy your function code. How would you like to proceed?
>
> 1. **Update CI/CD pipeline** — I'll help you update your Azure Pipelines or GitHub Actions workflow to target the new app
> 2. **Deploy from local project** — I'll run `func azure functionapp publish <NEW_APP_NAME>` from your project directory
> 3. **Deploy existing package** — I'll deploy the package we downloaded earlier from the original app

---

### Hyphenated-Function Source-First Deployment Cutover

Run this only when Step 4j recorded **Source-first deployment cutover** for production-connected non-HTTP functions whose names contain `-`. Prepare the selected deployment method first, including any pipeline changes. Immediately before executing the actual deployment, use `ask_user` for the complete transaction:

For CI/CD, first verify that preparing or committing the pipeline change cannot automatically deploy the target. Require a manually dispatched deployment or have the user pause the automatic trigger; if deployment timing cannot be controlled, use the local-project or existing-package method instead. Do not disable source functions until the pipeline is ready for an immediate, deliberate deployment.

> May I disable the listed hyphenated functions on Windows source app `<SOURCE_APP_NAME>`, verify they are disabled, and deploy the Linux Flex target? Processing may pause and events may backlog. If any disablement, deployment, or validation step fails, I will restore and verify any source functions already changed; after deployment starts, I will stop the entire target app before restoring them. This approval applies only to the listed functions and this deployment attempt.

After approval, repeat these commands for every affected source function:

```bash
az functionapp config appsettings set --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP> --settings "AzureWebJobs.<FUNCTION_NAME>.Disabled=true" --output none
az functionapp function list --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP> --query "[?config.name=='<FUNCTION_NAME>'].{name:config.name,disabled:isDisabled}" -o table
```

Track each source function that successfully reports `disabled=true`. Do not deploy until every affected source function reports `disabled=true`. If setting or verifying any function fails before deployment starts, immediately re-enable and verify every function already disabled, then report the failure. Run the selected deployment method below only after all functions pass, then perform the ARM function-state verification under **After Successful Deployment**.

If deployment fails, an affected target function reports unexpectedly, or initial validation fails, use the rollback included in the approval:

```bash
az functionapp stop --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP>
az functionapp config appsettings set --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP> --settings "AzureWebJobs.<FUNCTION_NAME>.Disabled=false" --output none
az functionapp function list --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP> --query "[?config.name=='<FUNCTION_NAME>'].{name:config.name,disabled:isDisabled}" -o table
```

Repeat the final two commands for every affected source function and verify each reports `disabled=false`. Report that stopping the target affects all its functions; obtain new approval before another deployment attempt.

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

Functions Core Tools performs a host health request after publishing. If the deployment pipeline and trigger synchronization complete but Option B ends with `403 Ip Forbidden`, the copied access restrictions blocked only that health request. Continue with the ARM verification below; do not modify access restrictions automatically.

### Option C: Deploy Existing Package (if user selects option 3)

Deploy the zip package downloaded in Step 3 (resolves to `<UPGRADE_DIR>/<PACKAGE_NAME>` per the [Artifact Output Policy](../../../../../global-rules.md#artifact-output-policy)):

```bash
az functionapp deployment source config-zip --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --src <UPGRADE_DIR>/<PACKAGE_NAME>
```

### After Successful Deployment

For every deployment method, verify deployment through ARM:

```bash
az functionapp show --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --query "{name:name,state:state,runtimeAvailabilityState:runtimeAvailabilityState}" -o table
```

```bash
az functionapp function list --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --query "[].{name:config.name,triggerType:(config.bindings[?ends_with(type, 'Trigger')] | [0].type),disabled:isDisabled}" -o table
```

For every non-hyphenated function that Step 4j intended to disable, require `disabled=true`. If any reports false or null, stop and treat trigger safety as failed. Hyphenated functions must match the Step 4j path: isolated dependencies, source-first cutover, or explicit active-deployment approval. Never infer effective disablement from app-setting presence.

If the app is running with normal runtime availability and all expected functions are synchronized, treat deployment as successful but record functional smoke testing as deferred. Do not modify access restrictions automatically.

Inform the user:

> Code deployed. Continue to **Step 5a** to apply or confirm the selected access-key strategy before HTTP validation. If Step 4j disablement was approved, only HTTP endpoints are live; per-function cutover for non-HTTP functions happens in Step 6. If disablement was declined, report that non-HTTP functions are already active.
>
> The source app is still processing all events as before. Keep it running until cutover is complete; the Consumption plan only bills for actual usage.

---
