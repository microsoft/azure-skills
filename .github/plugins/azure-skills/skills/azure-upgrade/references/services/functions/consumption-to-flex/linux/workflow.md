# Consumption Plan to Flex Consumption Plan Upgrade

> **Source**: Azure Functions Consumption Plan (Y1/Dynamic) on Linux
> **Target**: Azure Functions Flex Consumption Plan (FC1/FlexConsumption)
> **Platform**: Linux → Linux. For a Windows Consumption source, use the [Windows workflow](../windows/workflow.md).
> **Docs**: [Linux migration guide](https://learn.microsoft.com/en-us/azure/azure-functions/migration/migrate-plan-consumption-to-flex?pivots=platform-linux)

## Why Upgrade?

- **Faster cold starts** — always-ready instances mean functions respond more quickly
- **Better scaling** — per-function scaling and concurrency controls
- **Virtual network support** — connect to private networks and use private endpoints
- **Active investment** — Flex Consumption is where new features land first

## What to Expect

1. Your **code stays the same** — no rewriting required if on a supported language version
2. You'll **create a new app** alongside the existing one
3. New app runs in the **same resource group** with access to the same dependencies
4. You **control the timing** — test thoroughly before switching over

## Platform Notes

- Linux Consumption is being **retired September 30, 2028**
- Azure CLI provides automated migration commands: `az functionapp flex-migration list` and `az functionapp flex-migration start`
- The `flex-migration` commands handle assessment, app creation, and most configuration migration automatically
- Deployment packages are in `squashfs` format stored in `scm-releases` blob container

## Prerequisites

- Azure CLI v2.77.0+
- `resource-graph` extension: `az extension add --name resource-graph`
- `jq` tool for JSON processing
- Owner or Contributor role in the resource group
- Permissions to create and manage function apps, storage accounts, App Insights resources, and managed identity role assignments

## Compatibility Requirements

### Supported Language Stacks

| Stack ID | Language | Supported? |
|----------|----------|------------|
| `dotnet-isolated` | .NET (isolated worker model) | ✅ Yes |
| `node` | JavaScript/TypeScript | ✅ Yes |
| `java` | Java | ✅ Yes |
| `python` | Python | ✅ Yes |
| `powershell` | PowerShell | ✅ Yes |
| `dotnet` | .NET (in-process model) | ❌ No — must migrate to isolated first |
| `custom` | Custom handlers | ✅ Yes |

### Known Limitations (Flex Consumption)

| Feature | Status | Impact |
|---------|--------|--------|
| Deployment slots | ❌ Not supported | Rearchitect to use separate apps |
| TLS/SSL certificates | ⚠️ Site-scoped certificates in preview | Re-add certificates after migration, verify the per-app limits, and update code that loads certificates to use Linux file paths |
| Blob trigger (polling) | ❌ Only EventGrid source | Convert `LogsAndContainerScan` → `EventGrid` |
| Azure Government | ❌ Not available | Cannot migrate yet |

## Upgrade Phases

### Phase 1: Assessment

Run all checks from [assessment.md](assessment.md). Use the automated eligibility check:

```bash
# Automated eligibility check — scans all Linux Consumption apps
az functionapp flex-migration list
```

This returns `eligible_apps` and `ineligible_apps` arrays with specific reasons for any incompatibilities. For detailed manual checks, see [automation.md](automation.md).

### Phase 2: Pre-migration (Collect Everything)

Collect all settings and configurations from the existing app before creating the new one. See **Step-by-step scripts** in [automation.md](automation.md):

1. Collect app settings
2. Collect application configurations (CORS, custom domains, HTTP version, TLS, client certs, etc.)
3. Identify managed identities and RBAC role assignments
4. Identify built-in authentication settings
5. Review inbound access restrictions
6. Get the code deployment package (if source code not in version control)

### Phase 3: Create Flex Consumption App

Run the automated migration command from [automation.md](automation.md) — Step 4.

The `flex-migration start` command automatically:
- Assesses your source app for Flex Consumption compatibility
- Creates a new function app in the Flex Consumption plan
- Migrates app settings, identity assignments, storage mounts, CORS, custom domains, and access restrictions

> 💡 Use Microsoft Entra ID + managed identities instead of connection strings when creating the new app.

### Identity-First Configuration (Functions)

Enterprise subscriptions commonly enforce policies blocking local auth. Configure identity-based access:

- **Storage accounts**: Use `AzureWebJobsStorage__credential`, `__clientId`, and service-specific URIs (`__blobServiceUri`, `__queueServiceUri`, `__tableServiceUri`)
- **Application Insights**: Use `APPLICATIONINSIGHTS_AUTHENTICATION_STRING` with `Authorization=AAD`
- When using User Assigned Managed Identity, pass `managedIdentityClientId` explicitly

### Phase 4: Verify and Configure the New App

The `flex-migration start` command handles most configuration. Verify the results and manually configure anything it doesn't cover (see [automation.md](automation.md)):

1. **Verify** migrated app settings, identities, custom domains
2. **Configure** built-in authentication (if used — not auto-migrated)
3. **Configure** scale and concurrency settings (if custom values needed)
4. **Enable** Application Insights monitoring

### Phase 5: Deploy Code

> ⚠️ **Code is NOT automatically migrated.** The new app is created with config only — you must deploy code separately.

**Use `ask_user` to present these options:**

> Your new Flex Consumption app `<NEW_APP_NAME>` has been created and configured. Now we need to deploy your function code. How would you like to proceed?
>
> 1. **Update CI/CD pipeline** — I'll help you update your Azure Pipelines or GitHub Actions workflow to target the new app
> 2. **Deploy from local project** — I'll run `func azure functionapp publish <NEW_APP_NAME>` from your project directory
> 3. **Deploy existing package** — I'll deploy the package we downloaded earlier from the original app

After user selects an option, execute the corresponding deployment method from [automation.md](automation.md) — Step 5.

> ⚠️ After deployment, triggers immediately start processing. Review mitigation strategies for your trigger types.

**After successful deployment, inform the user:**

> Code deployed! Next steps to consider:
>
> - The original app is still running — keep it as rollback for a few days
> - Update any clients/pipelines to point to the new URL
> - Enable HTTPS-only and managed identity on the new app for better security
> - Do not delete the original app until production traffic and every production trigger have completed cutover and target validation

### Phase 6: Post-Upgrade Validation

1. **Smoke test** — Get the app’s default hostname via `az functionapp show --query defaultHostName -o tsv`, then hit that URL and confirm it returns a non-error response (HTTP 2xx/4xx, not connection refused or 503). This is the minimum bar before proceeding.
2. Verify the app is running on Flex Consumption (`az functionapp show --query sku`)
3. Test HTTP trigger endpoints (e.g. `curl https://<DEFAULT_HOST>/api/<FUNCTION_NAME>`)
4. Capture and compare performance benchmarks
5. Set up monitoring dashboards
6. Refine scale/concurrency settings
7. Update IaC (Bicep/Terraform) to reflect new plan

### Phase 7: Cleanup (Optional)

- Keep the original app for a few days/weeks as rollback
- Consumption plan charges only for actual usage — low cost to keep idle
- Offer deletion only after all production clients, DNS/custom domains, and triggers use the target; target execution is verified; no production-readiness work remains deferred; and the source no longer processes production workloads
- If any condition is incomplete, retain the source and record cleanup as skipped or deferred
- After every condition passes, use the confirmation and command in [automation.md](automation.md) — Step 7

## Trigger Migration Risks

| Trigger Type | Risk | Mitigation |
|-------------|------|------------|
| Azure Blob storage | High | Create separate container for event-based trigger in new app |
| Azure Cosmos DB | High | Create dedicated lease container for new app; set `StartFromBeginning: false` |
| Azure Event Grid | Medium | Recreate event subscriptions; ensure idempotent functions |
| Azure Event Hubs | Medium | Create new consumer group for new app |
| Azure Service Bus | High | Create new topic/queue; update senders; drain original before shutdown |
| Azure Storage Queue | High | Create new queue; update senders; drain original before shutdown |
| HTTP | Low | Update clients to target new app URL |
| Timer | Low | Offset schedules during cutover to avoid simultaneous execution |

## IaC Key Differences

| Property | Consumption | Flex Consumption |
|----------|-------------|------------------|
| SKU | `Y1` (Dynamic) | `FC1` (FlexConsumption) |
| Plan required | Optional (auto-created) | Required (must be explicit) |
| OS | Linux | Linux only |
| Configuration | App settings | `functionAppConfig` section |
| Storage | `WEBSITE_CONTENTSHARE` setting | `deployment.storage` in `functionAppConfig` |

## Deprecated Settings (Do NOT Migrate)

These app settings are NOT supported in Flex Consumption and should be filtered out:

- `WEBSITE_USE_PLACEHOLDER_DOTNETISOLATED`
- `AzureWebJobsStorage*` (replaced by identity-based config)
- `WEBSITE_MOUNT_ENABLED`
- `ENABLE_ORYX_BUILD`
- `FUNCTIONS_EXTENSION_VERSION` (set via `functionAppConfig`)
- `FUNCTIONS_WORKER_RUNTIME` (set via `functionAppConfig`)
- `FUNCTIONS_WORKER_RUNTIME_VERSION`
- `FUNCTIONS_MAX_HTTP_CONCURRENCY`
- `FUNCTIONS_WORKER_PROCESS_COUNT`
- `FUNCTIONS_WORKER_DYNAMIC_CONCURRENCY_ENABLED`
- `SCM_DO_BUILD_DURING_DEPLOYMENT`
- `WEBSITE_CONTENTAZUREFILECONNECTIONSTRING`
- `WEBSITE_CONTENTOVERVNET`
- `WEBSITE_CONTENTSHARE`
- `WEBSITE_DNS_SERVER`
- `WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT`
- `WEBSITE_NODE_DEFAULT_VERSION`
- `WEBSITE_RUN_FROM_PACKAGE`
- `WEBSITE_SKIP_CONTENTSHARE_VALIDATION`
- `WEBSITE_VNET_ROUTE_ALL`
- `APPLICATIONINSIGHTS_CONNECTION_STRING` (already created in new app)

## Troubleshooting

| Issue | Remediation |
|-------|-------------|
| Cold start performance issues | Review concurrency settings; check for missing dependencies |
| Missing bindings | Verify extension bundles; update binding configurations |
| Permission errors | Check identity assignments and role permissions |
| Network connectivity | Validate access restrictions and networking settings |
| Missing App Insights | Recreate the Application Insights connection |
| App fails to start | Check portal Diagnose & Solve; review App Insights Failures blade |
| Triggers not processing | Verify binding configs, connection strings, consumer groups |

## Rollback

1. Obtain immediate confirmation, then restart the source app if it was stopped: `az functionapp start --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP>`
2. Redirect clients back to original resources (queues/topics/containers)
3. Revert DNS or custom domain changes
4. Obtain separate confirmation before deleting the new Flex Consumption app if needed

## References

- [Flex Consumption plan overview](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-plan)
- [How to use the Flex Consumption plan](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to)
- [Azure CLI flex-migration commands](https://learn.microsoft.com/en-us/cli/azure/functionapp/flex-migration) (Linux only)
- [Flex Consumption IaC samples](https://github.com/Azure-Samples/azure-functions-flex-consumption-samples/tree/main/IaC)
- [Flex Consumption plan deprecations](https://learn.microsoft.com/en-us/azure/azure-functions/functions-app-settings#flex-consumption-plan-deprecations)
