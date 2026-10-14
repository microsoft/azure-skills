# Trigger Safety and Monitoring

### 4j. Choose the Pre-Deployment State of Non-HTTP Functions

> ⚠️ **Why this decision exists**: When Step 5 deploys code, enabled non-HTTP functions can immediately consume events or run schedules. The risk is highest when 4c copied production settings, 4b reused the source storage account (including implicit `AzureWebJobsStorage` bindings), or timer triggers are present. Disabling the target functions before deployment makes cutover controllable in Step 6.
>
> HTTP triggers are intentionally left enabled — they don't pull from a queue, so the new app cannot "steal" HTTP traffic. Clients must be redirected to the new hostname explicitly, which gives you the same safety as disabling.
>
> Reference: [Disable functions in Azure Functions](https://learn.microsoft.com/en-us/azure/azure-functions/disable-function).
>
> ⚠️ On Linux, a function whose name contains a hyphen (`-`) cannot be disabled through `AzureWebJobs.<FUNCTION_NAME>.Disabled`. Never claim that this setting protects a hyphenated function on the Flex target.

Read each deployed function's trigger binding from the ARM function metadata:

```bash
az functionapp function list --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP> --query "[].{name:config.name,triggerType:(config.bindings[?ends_with(type, 'Trigger')] | [0].type)}" -o table
```

> 💡 Use the alias `triggerType`, not `type`. Azure CLI's table formatter suppresses common resource metadata fields named `type`, which can make a valid projection appear blank.
>
> ⚠️ **Skill instruction**:
>
> 1. Reconcile the ARM results with the trigger inventory recorded in the assessment report.
> 2. If ARM genuinely returns a blank, missing, or ambiguous trigger, use source attributes or `function.json` as the fallback.
> 3. If a function remains unresolved, stop — never assume it is event-driven or HTTP.
> 4. Confirm that every deployed function has exactly one classified trigger before presenting the disablement decision.
> 5. Split non-HTTP functions into names that contain `-` and names that do not. Record both lists in `<UPGRADE_DIR>/upgrade-status.md`.

Evaluate these risk factors:

- whether source app settings were copied in 4c;
- whether the source storage account was reused in 4b;
- whether timers or unresolved binding sources are present.

If there are no non-HTTP functions, mark Step 4j `skipped — no non-HTTP functions`. If settings were deferred, runtime storage and every trigger dependency are isolated from production, no timer or other autonomous function can affect production, and every binding source is resolved, mark Step 4j `skipped — target fully isolated`. In either case, do not present a disablement prompt or add per-function disable settings; record any hyphenated names and the Linux limitation, then continue to 4k.

If any production-connected non-HTTP function name contains `-`, do not attempt to disable it on the target. Use `ask_user` to list the affected functions, explain that they will be active when the Linux target starts, and offer these choices:

1. **Isolate target dependencies (recommended)** — configure target-specific queues, topics, containers, consumer groups, event subscriptions, schedules, or other bindings, then reassess Step 4j.
2. **Rename and repackage** — change the function names so setting-based disablement is supported, redeploy the source if required, and reassess.
3. **Source-first deployment cutover** — immediately before Step 5, disable and verify the affected functions on the Windows source, deploy the target, and validate it. This can pause processing and backlog events. If deployment or validation fails, stop the entire target app before restoring the source functions.
4. **Deploy active** — explicitly accept that the affected target functions can process production events or schedules as soon as deployment completes.

Record the selected path and affected function names in `<UPGRADE_DIR>/upgrade-status.md`. Choices 1 and 2 block deployment until completed. Choice 3 is executed as the transaction in [Step 5](code-deployment.md#hyphenated-function-source-first-deployment-cutover). Choice 4 requires the same immediate pre-deployment warning and approval as declined disablement.

For the remaining non-HTTP functions whose names do not contain `-`, use `ask_user` to list them and summarize the observed risk factors. Strongly recommend disabling all listed functions when any risk factor is present, but leave the decision to the user. Record the choice in `<UPGRADE_DIR>/upgrade-status.md`.

If the user approves, set a disable flag on the new app for every listed non-HTTP function whose name does not contain `-` (repeat per function name). Leave HTTP and hyphenated functions unchanged:

```bash
az functionapp config appsettings set --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --settings "AzureWebJobs.<FUNCTION_NAME>.Disabled=true" --output none
```

The runtime reads these settings at startup, so they are intended to take effect when Step 5 deploys code. Do not call the functions effectively disabled until their runtime state is verified after deployment.

If disablement was approved, verify that the settings were written before moving on:

```bash
az functionapp config appsettings list --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --query "[?starts_with(name, 'AzureWebJobs.') && ends_with(name, '.Disabled')].{name:name, value:value}" -o table
```

> ⚠️ **Skill instruction**: If the user approves, apply one `--settings` call per function. Each call triggers a soft-restart but the underlying `Microsoft.Web/sites` PATCH has a payload limit, so batching dozens into one call can fail. If the source app has more than ~50 functions, write the disable settings to `<UPGRADE_DIR>/disabled_functions.json` (e.g. `[{"name": "AzureWebJobs.FuncA.Disabled", "value": "true"}, ...]`) and apply via `--settings @<UPGRADE_DIR>/disabled_functions.json` in a single call. Delete the file immediately after the apply succeeds (it does not contain secrets, but follow the [Artifact Output Policy](../../../../../global-rules.md#artifact-output-policy) for cleanup hygiene).
>
> If the user declines, or selects **Deploy active** for a hyphenated function, do not write a disable setting for the affected functions. Immediately before Step 5 deployment, use `ask_user` again to warn that the listed functions may consume shared events or run duplicate schedules as soon as deployment completes, then obtain explicit approval to deploy with them enabled.

### 4k. Verify Application Insights Monitoring

Microsoft Learn requires monitoring to be enabled before deployment but does not require changing workspaces or authentication models during migration. Preserve the monitoring configuration created by Step 4b unless the user explicitly requests customization.

This step verifies that Application Insights is configured and authorized. It does not query telemetry or prove that logs are being ingested; validate runtime behavior and telemetry after code deployment.

Verify the target has an Application Insights connection setting without displaying its value:

```bash
az functionapp config appsettings list --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --query "[?name=='APPLICATIONINSIGHTS_CONNECTION_STRING'].name" -o tsv
```

Verify the Application Insights component recorded from Step 4b:

```bash
az monitor app-insights component show --app <TARGET_AI_NAME> --resource-group <RESOURCE_GROUP> --query "{name:name,id:id,workspaceResourceId:workspaceResourceId}" -o table
```

If either the setting or component is absent, stop and investigate. Use `ask_user` before creating or wiring a replacement monitoring resource. Do not change the automatically selected Log Analytics workspace unless the user explicitly requests monitoring customization.

Check whether the source used AAD-authenticated ingestion:

```bash
az functionapp config appsettings list --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP> --query "[?name=='APPLICATIONINSIGHTS_AUTHENTICATION_STRING'].value | [0]" -o tsv
```

- If the value is not `Authorization=AAD`, keep the target's platform-created monitoring configuration unchanged. Offer AAD ingestion only as optional post-migration hardening.
- If the value is `Authorization=AAD`, preserve that posture on the target:

  ```bash
  az functionapp config appsettings set --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --settings "APPLICATIONINSIGHTS_AUTHENTICATION_STRING=Authorization=AAD" --output none
  ```

  Use `<NEW_PRINCIPAL_ID>` from 4e and grant it `Monitoring Metrics Publisher` on the **target** Application Insights component:

  ```bash
  az role assignment create --assignee-object-id <NEW_PRINCIPAL_ID> --assignee-principal-type ServicePrincipal --role "Monitoring Metrics Publisher" --scope $(az monitor app-insights component show --app <TARGET_AI_NAME> --resource-group <RESOURCE_GROUP> --query id -o tsv)
  ```

Verify setting names and the target-scoped role without displaying connection-string values:

```bash
az functionapp config appsettings list --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --query "[?starts_with(name, 'APPLICATIONINSIGHTS_')].name" -o tsv
```

```bash
az role assignment list --assignee-object-id <NEW_PRINCIPAL_ID> --scope <TARGET_AI_RESOURCE_ID> --query "[?roleDefinitionName=='Monitoring Metrics Publisher'].{role:roleDefinitionName,scope:scope}" -o table
```

### Verify Migration Results

Verify the new app exists and is configured:

```bash
az functionapp show --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --query "{name:name, kind:kind, sku:properties.sku}" --output table
```

Review target app-setting names:

```bash
az functionapp config appsettings list --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --query "[].name" -o tsv
```

Check managed identity:

```bash
az functionapp identity show --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP>
```

Check custom domains:

```bash
az functionapp config hostname list --webapp-name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --output table
```

### Configure Items Requiring Manual Setup

These are not handled by Steps 4a–4i and require manual configuration:

#### TLS/SSL Certificates

If Step 2e identified certificates used by the source app, re-add only those certificates using the documented [site-scoped certificate process](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to#configure-site-scoped-certificates). Confirm the target remains within the limit of three private and three public certificates.

`WEBSITE_LOAD_CERTIFICATES` is not used by Flex Consumption. Make each required certificate accessible to app code through the documented process, and update code that used the Windows certificate store to load from `/var/ssl/certs` for public certificates or `/var/ssl/private` for private certificates.

#### Scale and Concurrency (if custom values needed)

Use the `WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT` value collected in [Step 3a](configuration-inventory.md#3a-collect-application-configurations) as `<MAX_SCALE_SETTING>`. If the source setting was absent, keep the target default and skip this command. If it was set, confirm the value is within the Flex Consumption range of 1–1000 before applying it:

```bash
az functionapp scale config set --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --maximum-instance-count <MAX_SCALE_SETTING>
```

> ⚠️ Reducing below 40 for HTTP apps can cause frequent request failures.

---
