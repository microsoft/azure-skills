# Validation and Cutover

## Step 6: Post-Upgrade Validation

Enter Step 6 only after Step 5a is complete or skipped because target-generated keys were selected. If key preservation was selected but any host or HTTP-function key failed verification, stop.

### Confirm the source app is still healthy

Before touching the new app, verify the source is still serving traffic and processing events as expected. The cutover that follows assumes the source remains the system of record until each trigger is flipped over individually.

```bash
az functionapp show --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP> --query "{name:name, state:state, hostNames:hostNames[0]}" -o table
```

Expected: `state` is `Running`. If anything looks off (state is `Stopped`, hostname is null, etc.), pause the cutover and investigate before proceeding — the cleanup steps later in this phase assume the source app is healthy.

### Smoke Test (run this first)

Get the new app's default hostname:

```bash
az functionapp show --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --query defaultHostName -o tsv
```

> ⚠️ **Flex propagation**: On a freshly-created Flex Consumption app, `defaultHostName` from `az functionapp show` can briefly return null while the platform finishes provisioning. If the command above returns empty, fall back to:
>
> ```bash
> az functionapp list --resource-group <RESOURCE_GROUP> --query "[?name=='<NEW_APP_NAME>'].defaultHostName | [0]" -o tsv
> ```
>
> The list endpoint populates the field as soon as the app exists.

Confirm the host is reachable (substitute `<HOSTNAME>` with the value above):

```bash
curl -s -o /dev/null -w "%{http_code}\n" "https://<HOSTNAME>"
```

Expected: a 2xx, 401, or 404 (the host is up). If the response is `403 Ip Forbidden` and the target has an intentional deny-by-default policy, record the HTTP smoke test as deferred until it can run from an already allowed client. Confirm the app and functions through the ARM commands from Step 5; do not add or relax access rules automatically.

If you get 503 or a connection refusal, the app failed to start — check logs:

```bash
az functionapp log tail --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP>
```

> 💡 On PowerShell 7+, `curl` resolves to the real `curl.exe` (the legacy `Invoke-WebRequest` alias was removed in 7.x). Confirm with `Get-Command curl` if unsure.

### Verify Plan

```bash
az functionapp show --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --query serverFarmId
```

### Test HTTP Endpoints

Test an individual HTTP trigger (substitute `<HOSTNAME>` and `<FUNCTION_NAME>`):

```bash
curl -s -o /dev/null -w "%{http_code}\n" "https://<HOSTNAME>/api/<FUNCTION_NAME>"
```

For a function that requires a function or host key, use the selected target key in the `x-functions-key` header without printing or persisting it. If target-generated keys were selected, don't treat HTTP cutover as complete until every key-dependent client or workflow has been updated and validated.

### Validate Built-in Authentication

Step 4f.auth must be complete or skipped because source Easy Auth was disabled before entering Step 6. If it is deferred or blocked, do not deploy code or run target HTTP checks.

If Step 4f.auth was completed, test an endpoint that requires authentication and confirm its anonymous behavior matches the verified target configuration: `401`/`403` for rejection or the expected provider redirect. Then complete one authenticated request using a test identity and confirm the expected authorization result without recording tokens.

### Per-Function Cutover (event-driven triggers)

For non-hyphenated functions effectively disabled and verified after Step 5, handle them one at a time. Never enable a production-connected target function before approval to disable its source counterpart; otherwise both apps can process the same event source while approval is pending. If Step 4j disablement was declined, report that controlled cutover protection was not established and validate for concurrent processing before any source change.

Do not use the target app-setting disable/enable transaction below for a function whose name contains `-`; Linux does not support disabling that name through `AzureWebJobs.<FUNCTION_NAME>.Disabled`. Use isolated target dependencies or the source-first deployment cutover recorded in Step 4j. If a hyphenated function was deployed active with explicit approval, validate for concurrent processing and do not claim controlled per-function cutover.

> ⚠️ **Per-trigger mitigations apply first**: Even with this controlled per-function cutover, the [Trigger Migration Risks](../workflow.md#trigger-migration-risks) table lists per-trigger-type prerequisites — new consumer group for Event Hubs, dedicated lease container for Cosmos DB, new event subscription for blob/EventGrid, etc. Apply the relevant mitigation **before** flipping the disable flag for the corresponding function.

For each event-driven function, choose one of these paths:

#### Path A: Isolated Target Validation

Point the target binding at an isolated test queue, consumer group, lease container, event subscription, or equivalent resource. For a non-hyphenated function, enable and validate the target, then disable it again until production cutover is approved. A hyphenated function is already active after deployment; validate it only against isolated dependencies and do not restore its production binding until the transaction below is approved.

#### Hyphenated-Function Production Cutover

For a hyphenated function already validated against isolated dependencies, use `ask_user` for a transaction that:

1. Stops the entire target app and verifies it is stopped.
2. Disables the corresponding function on the Windows source and verifies `isDisabled=true`.
3. Replaces the target's isolated binding configuration with the production configuration.
4. Starts the target app and validates one normal execution cycle.
5. On failure, stops the target, restores its isolated binding configuration, re-enables and verifies the source function, and reports the failure.

Explain that stopping the Flex app affects every target function and that events may backlog during this transaction. Approval applies only to the named function, binding changes, and this cutover attempt.

#### Path B: Production Cutover

Use this path only for target function names that do not contain `-`.

1. Use `ask_user` **before enabling the target or changing the source**. Request approval for the complete function-specific transaction, including conditional rollback:

   > May I cut over `<FUNCTION_NAME>` by disabling it on source app `<SOURCE_APP_NAME>`, verifying the source is disabled, and then enabling it on target app `<NEW_APP_NAME>`? This may briefly pause processing and allow events to backlog. If target activation or validation fails, I will disable the target and restore the source function. This approval applies only to this function and this cutover attempt.

   Do not continue unless the user approves. If approval is declined, leave the source enabled and target disabled. Approval for one function does not cover another function or a later retry.

2. Disable the source function and suppress command output because app-setting responses can contain secrets:

   ```bash
   az functionapp config appsettings set --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP> --settings "AzureWebJobs.<FUNCTION_NAME>.Disabled=true" --output none
   ```

3. Verify the source reports the function as disabled before enabling the target:

   ```bash
   az functionapp function list --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP> --query "[?config.name=='<FUNCTION_NAME>'].{name:config.name,disabled:isDisabled}" -o table
   ```

4. Enable the target:

   ```bash
   az functionapp config appsettings set --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --settings "AzureWebJobs.<FUNCTION_NAME>.Disabled=false" --output none
   ```

5. Verify target processing after one full execution cycle or controlled test event:

   ```kql
   requests
   | where cloud_RoleName == "<NEW_APP_NAME>"
   | where operation_Name == "<FUNCTION_NAME>"
   | where timestamp > ago(15m)
   | summarize count(), avg(duration), countif(success == false) by bin(timestamp, 1m)
   ```

6. If target activation or validation fails, use the rollback authorized in step 1: disable and verify the target first, then re-enable and verify the source. Report the failure and obtain new approval before another cutover attempt.

> ⚠️ **Pause versus duplication**: Source-first cutover can briefly delay processing or miss a timer occurrence, but queued/event-stream work normally remains available as backlog. This is safer than enabling both production-connected functions concurrently, which can cause duplicate or competing processing.

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
