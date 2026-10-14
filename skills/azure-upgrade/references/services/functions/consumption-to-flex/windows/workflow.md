# Windows Consumption Plan to Flex Consumption Plan Upgrade

> **Source**: Azure Functions Consumption Plan (Y1/Dynamic) on Windows
> **Target**: Azure Functions Flex Consumption Plan (FC1/FlexConsumption)
> **Platform**: Windows → Linux (Flex Consumption is Linux-based)
> **Docs**: [Windows migration guide](https://learn.microsoft.com/en-us/azure/azure-functions/migration/migrate-plan-consumption-to-flex?pivots=platform-windows)

> ⚠️ **This is a Windows-to-Linux migration**, not just a plan change. Flex Consumption is Linux-based. Apps with Windows-specific dependencies, in-process .NET, .NET Framework targeting, or Windows-RID deployment packages must be prepared before migration. See [Known Limitations and Migration Blockers](#known-limitations-and-migration-blockers).

## Before You Begin

Before running any discovery or Azure command, read the ordered `### Phase` headings in this workflow and the ordered workflow-unit table in [automation.md](automation.md). Present a concise user-facing summary in that order, combining implementation units under their corresponding phases. Do not maintain or infer a separate hard-coded step list.

State that the source app remains read-only during assessment and replication. Every source-changing cutover, rollback, or cleanup action requires a separate, immediate approval. After presenting the plan, confirm the source app and Flex Consumption target plan with the user before continuing.

## Why Upgrade?

- **Faster cold starts** — always-ready instances mean functions respond more quickly
- **Better scaling** — per-function scaling and concurrency controls
- **Virtual network support** — connect to private networks and use private endpoints
- **Active investment** — Flex Consumption is where new features land first

## What to Expect

1. **Your code may need changes** — unlike the Linux Consumption → Flex migration, this is a Windows-to-Linux OS change. Apps with Windows-only NuGet packages, P/Invoke, COM interop, .NET Framework dependencies, Windows-RID deployment packages, or Windows-specific PowerShell modules require preparation.
2. **Create a new Flex app alongside the existing one** — test thoroughly on the new app before cutting over. This 2-app approach lets you discover Linux compatibility issues safely before committing.
3. The new app runs in the **same resource group** with access to the same dependencies.
4. **Deployment model changes** — Windows Consumption stores code on Azure Files (SMB); Flex uses immutable blob packages via One Deploy. Existing MSDeploy, FTP, and Kudu git push pipelines will not work after migration.
5. You **control the timing** — the original Windows app stays running until you are confident in the migrated app.

### Source-App Safety

The source app is read-only throughout assessment and replication. Before any cutover, rollback, or cleanup command that changes the source app's settings, triggers, state, deployment, bindings, or existence, the skill must use `ask_user` to describe the exact action and obtain explicit approval. Approval is specific to that action and cannot be reused for later source changes.

## Platform Notes

- **Recommended plan**: Flex Consumption is the recommended serverless hosting plan for Azure Functions. Do not assume or state a Windows Consumption retirement date unless current Microsoft documentation publishes one.
- **OS change**: Flex Consumption is **Linux-based**. Windows-compiled binaries, Windows-only NuGet packages, COM interop, P/Invoke to Windows APIs, and Windows PowerShell modules will not run without modification.
- **Deployment model**: Windows Consumption uses Azure Files (SMB share via `WEBSITE_CONTENTAZUREFILECONNECTIONSTRING`/`WEBSITE_CONTENTSHARE`); Flex uses blob-based One Deploy (immutable zip packages in Azure Blob Storage).
- **`az functionapp flex-migration` does not support Windows** — all migration steps use raw CLI commands (see [automation.md](automation.md)).
- **Elastic Premium alternative**: Apps with hard Windows dependencies that cannot be removed can migrate to [Elastic Premium on Windows](https://learn.microsoft.com/en-us/azure/azure-functions/functions-premium-plan) instead of Flex Consumption. This is more expensive but changes the hosting plan without requiring an OS migration.

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
| `dotnet-isolated` (.NET 8+) | .NET isolated worker, .NET 8+ | ✅ Yes — if no Windows-only dependencies and not published with a Windows RID |
| `dotnet-isolated` (.NET Framework) | .NET isolated worker targeting `net4x` | ❌ No — .NET Framework runtime not present on Linux; must retarget to .NET 8+ |
| `dotnet` | .NET in-process model | ❌ No — not supported on Flex; must migrate to isolated worker model first |
| `node` | JavaScript/TypeScript | ✅ Yes |
| `java` | Java | ✅ Yes |
| `python` | Python | ✅ Yes |
| `powershell` | PowerShell | ⚠️ Review — Windows-only modules (WMI, registry, COM interop) will not work on Linux |
| `go` | Go (Preview) | ✅ Yes — if the handler and native dependencies are built for Linux |
| `custom` | Custom handlers | ⚠️ Review — handler binary must be Linux-compatible |

### Known Limitations and Migration Blockers

#### Flex Consumption Platform Limits (shared with Linux migration)

| Feature | Status | Action Required |
|---------|--------|-----------------|
| Deployment slots | ❌ Not supported | Consolidate to production slot or rearchitect to separate apps |
| TLS/SSL certificates | ⚠️ Site-scoped certificates in preview | Re-add used certificates after migration, verify the per-app limits, and update code to use Linux certificate file paths |
| Blob trigger (polling) | ❌ EventGrid source only | Convert `LogsAndContainerScan` → `EventGrid`; create event subscription |
| Disable setting for function names containing `-` | ❌ Not supported on Linux | Isolate the target dependency, rename/repackage the function, use a source-first deployment cutover, or explicitly accept active-trigger risk |
| Azure Government | ❌ Not available | Cannot migrate yet |
| MSDeploy / FTP / Kudu git deploy | ❌ Not supported | Switch to `az functionapp deploy` or `func azure functionapp publish` |

#### Windows-to-Linux Specific Blockers

| Issue | How to Detect | Action Required |
|-------|---------------|-----------------|
| .NET in-process model | `FUNCTIONS_WORKER_RUNTIME=dotnet` app setting | Migrate to isolated worker model — requires code changes (different NuGet packages, `Program.cs` startup) |
| .NET Framework targeting (`net4x`) | `.csproj` target framework | Retarget to .NET 8+ — may require replacing Framework-only APIs and NuGet packages |
| Windows-only NuGet packages (GDI+, COM, P/Invoke) | Assembly/package scan (heuristic) | Replace with cross-platform alternatives, or migrate to Elastic Premium on Windows |
| Windows RID deployment package | `runtimes/win-x64/` present without `linux-x64` in package | Republish without a RID (framework-dependent) or with `-r linux-x64` |
| Path separator / case sensitivity | Code review | Replace `\` path construction with `Path.Combine()`; fix case-sensitive file references |
| PowerShell Windows-only modules (WMI, registry, COM) | `requirements.psd1` module imports | Replace with cross-platform alternatives or remove |
| Windows certificate store access | Code review | Migrate to file-based certificate loading |
| Unsupported language runtime version | Site config | Upgrade to a [supported version](https://learn.microsoft.com/en-us/azure/azure-functions/supported-languages) |
| App region not supported by Flex | Region vs. Flex availability list | Wait for regional availability, or relocate the app |

> 💡 **Elastic Premium escape hatch**: Apps with hard Windows dependencies that cannot be removed can migrate to [Elastic Premium on Windows](https://learn.microsoft.com/en-us/azure/azure-functions/functions-premium-plan) as an alternative. This changes the hosting plan without requiring an OS migration.

## New App Name

The new Flex Consumption app needs a globally unique name. The skill defaults to **`<source>-flex`** — e.g. if your source app is `test-app`, the new app will be `test-app-flex`. This is short, self-documenting, and signals the SKU change.

Two modes are supported. State your preference in your initial migration request:

| Mode | How to invoke | Resulting name |
|------|---------------|----------------|
| **Default suffix** *(default)* | Just say "migrate my function app" | `<source>-flex` |
| **Custom name** | "migrate my function app **as `<name>`**" or "… **named `<name>`**" | The name you provide |

> ⚠️ **Skill instruction**: Before executing Step 4b in [automation.md](automation.md), **announce the proposed name to the user**, e.g. *"I'll create the new Flex app as `test-app-flex` in resource group `test-app_group` (region `westus2`). Say so if you'd prefer a different name."* This gives the user a chance to course-correct without a blocking prompt.

> 💡 Constraints (from the underlying [MS Learn create flow](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to?tabs=azure-cli%2Cazure-cli-publish&pivots=programming-language-csharp#create-a-flex-consumption-app)): globally unique in Azure (becomes `<APP_NAME>.azurewebsites.net`), 2–60 characters, alphanumerics + hyphens, must start with a letter, no consecutive hyphens. If the default `<source>-flex` would exceed 60 chars or collides with an existing app, fall back to a shortened suffix (e.g. `<source>-fc`) and announce that to the user.

## Storage Account Options

The new Flex Consumption app needs a storage account bound at creation time. The skill defaults to **reusing the source app's existing storage account** — the same default as `az functionapp flex-migration` on Linux. This is the lowest-friction option because there is no new storage resource to manage. Flex configures deployment storage on the target rather than reusing the source app's Windows content-share settings.

Three modes are supported. State your preference in your initial migration request — the skill will detect it and set the binding accordingly. Think of these as CLI-style flags:

| Mode | How to invoke | When to use |
|------|---------------|-------------|
| **Reuse source storage** *(default)* | Just say "migrate my function app" | Most migrations. No isolation needed between source and target. |
| **Create new storage** | "migrate my function app **with a new storage account**" or "… **and create a new storage account**" | You want isolated storage for blast-radius, compliance, or test/prod separation. |
| **Use a specific existing account** | "migrate my function app **using storage account `<name>`**" | You already have a target account provisioned (e.g. via IaC or central platform team). |

> ⚠️ **Skill instruction**: Before executing Step 4a/4b in [automation.md](automation.md), **announce the storage choice to the user**, e.g. *"I'll reuse your existing storage account `foo` for the new Flex app. Say so if you'd prefer a new isolated account or a different existing one."* This gives the user a chance to course-correct without a blocking prompt.

## Upgrade Phases

Initialize and maintain `<UPGRADE_DIR>/upgrade-status.md` using [Migration Progress](progress-tracking.md). Derive its workflow snapshot from the current scenario and automation headings, and show the current phase, substep, description, and state in chat at every transition; do not use a percentage.

### Phase 1: Assessment

Run all checks from [assessment.md](assessment.md). Since `az functionapp flex-migration` does not support Windows, eligibility is determined manually — use Step 1 and Step 2 in [automation.md](automation.md) to identify candidate apps and run compatibility checks.

- **Source code dependency scan** ([Step 2g](automation/discovery-and-assessment.md#2g-source-code-windows-dependency-scan) / [dependency-scan.md](dependency-scan.md)) — recommended for every Windows → Flex migration. Prefer a local source directory or checked-out repository; use the deployed package only when source is unavailable. The scan checks for Win32/COM/WMI/registry/cert-store usage, Windows-only packages, Windows-RID targeting, and shell-outs to Windows tools. Skippable — when skipped, the user owns the risk. Findings populate §11 of the assessment report and advisorily affect §1 `Upgrade Readiness`.

### Phase 2: Pre-migration (Collect Everything)

Collect all settings and configurations from the existing app before creating the new one. See **Step-by-step scripts** in [automation.md](automation.md):

1. Collect app settings
2. Collect application configurations (CORS, custom domains, HTTP version, TLS, client certs, etc.)
3. Inventory TLS/SSL certificates that must be re-added with the site-scoped certificate process
4. Identify managed identities and RBAC role assignments
5. Identify built-in authentication settings
6. Review inbound access restrictions
7. Get the code deployment package (if source code not in version control)

### Phase 3: Create Flex Consumption App

Execute Steps 4a–4l from [automation.md](automation.md). Each sub-step handles a discrete part of the migration:

- **4a** — *(optional)* Create a new storage account — only run if the user explicitly asked for new or different storage; see [Storage Account Options](#storage-account-options)
- **4b** — Create the Flex Consumption app (binds storage — source account by default; conn-string-based per the [MS Learn create flow](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to?tabs=azure-cli%2Cazure-cli-publish&pivots=programming-language-csharp#create-a-flex-consumption-app))
- **4b.opt** — *(optional, security hardening)* Identity-based storage — only run if the source app was already identity-based or the user explicitly requested it; re-derives `AzureWebJobsStorage__*` settings against the new app's chosen storage account
- **4c** — Review app-setting names, then ask whether to copy filtered source settings or defer them until target-specific dependencies are configured
- **4d** — Apply site configurations (HTTP/2, TLS, HTTPS-only, client certs, SCM basic auth)
- **4e** — Migrate system-assigned managed identity and role assignments
- **4f** — Migrate user-assigned managed identities
- **4f.auth** — If the source uses built-in authentication, configure and validate each provider before code deployment or defer the migration
- **4g** — Migrate CORS settings
- **4h** — Migrate custom domains
- **4i** — Migrate access restrictions
- **4j** — Skip disablement when settings and every trigger dependency are proven isolated from production and no autonomous function can affect production; otherwise separate hyphenated non-HTTP function names, which Linux cannot disable through app settings, and obtain the applicable safety decisions — [decision guidance](automation/trigger-safety-and-monitoring.md#4j-choose-the-pre-deployment-state-of-non-http-functions)
- **4k** — Verify the Application Insights configuration created with the target app; preserve AAD ingestion only when the source used it
- **4l** — Inventory access-key names and choose target-generated keys or opt in to preserving source host and HTTP-function key values

> 💡 Use Microsoft Entra ID + managed identities instead of connection strings when creating the new app.

### Identity-First Configuration (Functions)

Enterprise subscriptions commonly enforce policies blocking local auth. Configure identity-based access:

- **Storage accounts**: Step 4b creates the new app with a connection-string `AzureWebJobsStorage` binding (matching the [MS Learn create flow](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to?tabs=azure-cli%2Cazure-cli-publish&pivots=programming-language-csharp#create-a-flex-consumption-app)). To preserve or upgrade to identity-based storage, run optional [4b.opt](automation/app-creation.md#4bopt-identity-based-storage-optional-security-hardening), which assigns the storage data-plane roles to the new app's identity and writes `AzureWebJobsStorage__credential`, `__clientId` (UMI only), `__blobServiceUri`, `__queueServiceUri`, `__tableServiceUri` against the **new** app's storage account. Source-app `AzureWebJobsStorage__*` settings are intentionally dropped by 4c — carrying them over verbatim would silently point the new app's runtime at the source storage account.
- **Application Insights**: Preserve `Authorization=AAD` when the source already uses it; otherwise treat conversion as optional post-migration hardening
- When using User Assigned Managed Identity, pass `managedIdentityClientId` explicitly

### Phase 4: Verify and Configure the New App

Steps 4a–4i migrate application configuration; Step 4f.auth handles built-in authentication; Steps 4j–4k establish trigger safety and verify monitoring; Step 4l records the access-key strategy. Verify the results and manually configure anything not covered by those steps (see [automation.md](automation.md)):

1. **Verify** the chosen app-setting mode, identities, and custom domains
2. **Re-add** used TLS/SSL certificates with the site-scoped certificate process and update code that used the Windows certificate store
3. **Configure** the source app's custom scale limit, if one was set
4. **Verify** Application Insights monitoring

### Phase 5: Deploy Code

> ⚠️ **Code is NOT automatically migrated.** The new app is created with config only — you must deploy code separately.
>
> ⚠️ If source app settings were deferred in Step 4c, deployment is blocked until the user confirms all required application-specific target settings are configured. The skill may inspect names, but never setting values.
>
> ⚠️ If built-in authentication was deferred in Step 4f.auth, deployment is blocked. The source authentication boundary must be recreated and verified before application code is placed on the target.

**Use `ask_user` to present these options:**

> Your new Flex Consumption app `<NEW_APP_NAME>` has been created and configured. Now we need to deploy your function code. How would you like to proceed?
>
> 1. **Update CI/CD pipeline** — I'll help you update your Azure Pipelines or GitHub Actions workflow to target the new app
> 2. **Deploy from local project** — I'll run `func azure functionapp publish <NEW_APP_NAME>` from your project directory
> 3. **Deploy existing package** — I'll deploy the package we downloaded earlier from the original app

After user selects an option, execute the corresponding deployment method from [automation.md](automation.md) — Step 5.

After deployment synchronizes all functions, execute Step 5a. When preservation was selected, copy and verify source host and HTTP-function keys before any HTTP validation. System and master keys remain target-generated.

> ✅ If Step 4j disablement was approved and no risky hyphenated non-HTTP function was approved for active deployment, only HTTP endpoints will be live after deployment and per-function cutover happens in Phase 6.
>
> ✅ If Step 4j was skipped because the target is fully isolated, deploy without per-function disable settings and validate only against those isolated dependencies.
>
> ⚠️ If the user declined disablement, warn again and obtain explicit approval immediately before deployment because non-HTTP functions may begin processing or running schedules as soon as deployment completes.

**After successful deployment, inform the user:**

> Code deployed! Next steps to consider:
>
> - The original app is still running — keep it as rollback for a few days
> - If target-generated access keys were selected, update key-dependent clients and workflows before directing them to the new URL
> - Enable HTTPS-only and managed identity on the new app for better security
> - Source deletion is available only after all applicable production traffic and triggers are cut over and validated

### Phase 6: Post-Upgrade Validation

1. **Smoke test** — Get the app's default hostname via `az functionapp show --query defaultHostName -o tsv`, then hit that URL and confirm it returns a non-error response (HTTP 2xx/4xx, not connection refused or 503). If an intentional access restriction returns `403 Ip Forbidden`, verify deployment and function synchronization through ARM and record functional smoke testing as deferred until it can run from an already allowed client; do not relax access rules automatically.
2. Verify the app is running on Flex Consumption (`az functionapp show --query sku`)
3. Test HTTP trigger endpoints (e.g. `curl https://<DEFAULT_HOST>/api/<FUNCTION_NAME>`)
4. **Per-function validation and cutover for event-driven triggers** — either validate the target against isolated test resources without changing the source, or use a production cutover transaction. For production, obtain function-specific approval first, disable and verify the source, then enable the target; the same approval must explicitly authorize rollback if target validation fails. Never enable a production-connected target while source-disable approval is pending. See [Per-Function Cutover](automation/validation-and-cutover.md#per-function-cutover-event-driven-triggers) for the full procedure.
5. Capture and compare performance benchmarks
6. Set up monitoring dashboards
7. Refine scale/concurrency settings
8. Update IaC (Bicep/Terraform) to reflect new plan

### Phase 7: Cleanup (Optional)

- Keep the original app for a few days/weeks as rollback
- Consumption plan charges only for actual usage — low cost to keep idle
- A validation-only success is not eligible for source deletion
- The skill may offer deletion only when the recorded outcome is `production cutover complete`, no production-readiness work remains deferred, and the source no longer processes production workloads
- Immediately before deletion, use `ask_user` as specified in [automation.md](automation.md) — Step 7

## Trigger Migration Risks

> ✅ **Recommended safety net**: When the user approves [Step 4j](automation/trigger-safety-and-monitoring.md#4j-choose-the-pre-deployment-state-of-non-http-functions), non-HTTP functions are disabled before deployment. Phase 6 then uses isolated target resources or a source-first, pre-approved production transaction so the target is never enabled while source-disable approval is pending. If the user declines Step 4j, record that dual processing or duplicate schedules may begin immediately after deployment. Apply the relevant mitigations below before enabling or deploying each function.

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
| OS | Windows | Linux |
| Configuration | App settings | `functionAppConfig` section |
| Storage | `WEBSITE_CONTENTSHARE` setting | `deployment.storage` in `functionAppConfig` |

If the source app is managed through Bicep, ARM, or Terraform:

1. Define the Flex app and plan as new resources; a Consumption app cannot be converted to Flex Consumption in place.
2. Update the deployment definitions to use the new resource names and the Flex configuration above.
3. Reconcile resources created during migration instead of allowing IaC to recreate or overwrite them. For Terraform, import the new resources when appropriate.
4. Review the proposed changes with `az deployment group what-if` or `terraform plan` before applying them.
5. Update CI/CD pipelines to deploy to the new Flex app.

Do not mix ongoing manual configuration with resource-based deployments. If the app is not managed through IaC, skip this section.

## Deprecated Settings (Do NOT Migrate)

These app settings must be filtered out before applying to the new Flex app (Step 4c). The skill handles this automatically — Step 4c streams source settings through `jq`, deleting these keys in memory before PATCHing the new app's ARM endpoint.

### Azure Files content settings (always present on Windows Consumption — never migrate)

Every Windows Consumption app has these because the platform requires them for the Azure Files SMB share. Flex uses blob-based deployment instead — these have no equivalent.

These platform content settings are distinct from explicit Azure Files mount metadata returned by `az webapp config storage-account list`. Windows Consumption doesn't support explicit storage mounts, so catalog any returned metadata but don't migrate it.

- `WEBSITE_CONTENTAZUREFILECONNECTIONSTRING`
- `WEBSITE_CONTENTSHARE`
- `WEBSITE_CONTENTOVERVNET`
- `WEBSITE_SKIP_CONTENTSHARE_VALIDATION`

### Deployment settings (Flex uses `deployment.storage` in `functionAppConfig`, not app settings)

Windows Consumption has three historical aliases for run-from-package — all must be removed:

- `WEBSITE_RUN_FROM_PACKAGE`
- `WEBSITE_RUN_FROM_ZIP` (legacy alias — same semantics as `WEBSITE_RUN_FROM_PACKAGE`)
- `WEBSITE_USE_ZIP` (original name — same semantics)

### Runtime / scale settings (configured via `functionAppConfig` in Flex, not app settings)

- `FUNCTIONS_EXTENSION_VERSION`
- `FUNCTIONS_WORKER_RUNTIME`
- `FUNCTIONS_WORKER_RUNTIME_VERSION`
- `FUNCTIONS_MAX_HTTP_CONCURRENCY`
- `FUNCTIONS_WORKER_PROCESS_COUNT`
- `FUNCTIONS_WORKER_DYNAMIC_CONCURRENCY_ENABLED`
- `WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT`

### Other unsupported settings

- `WEBSITE_USE_PLACEHOLDER_DOTNETISOLATED`
- `WEBSITE_LOAD_CERTIFICATES` (unused in Flex; use the site-scoped certificate process and make certificates accessible to app code)
- `AzureWebJobsDashboard` (legacy v1 setting — not used by the v4 runtime)
- `WEBSITE_MOUNT_ENABLED`
- `ENABLE_ORYX_BUILD`
- `SCM_DO_BUILD_DURING_DEPLOYMENT`
- `WEBSITE_DNS_SERVER`
- `WEBSITE_NODE_DEFAULT_VERSION`
- `WEBSITE_VNET_ROUTE_ALL`

### Application Insights (preserved from Step 4b and verified by Step 4k)

- `APPLICATIONINSIGHTS_CONNECTION_STRING` — Step 4c preserves the target-specific value normally created by `az functionapp create`; Step 4k verifies it without displaying the value. `APPLICATIONINSIGHTS_AUTHENTICATION_STRING=Authorization=AAD` is preserved only when the source already used AAD ingestion.

### Storage (replaced by Step 4b / 4b.opt)

Every setting whose name starts with `AzureWebJobsStorage` is dropped by the 4c filter — storage is owned end-to-end by Step 4b (default conn-string binding for `<STORAGE_NAME>`, matching the [MS Learn create flow](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to?tabs=azure-cli%2Cazure-cli-publish&pivots=programming-language-csharp#create-a-flex-consumption-app)) or by optional [Step 4b.opt](automation/app-creation.md#4bopt-identity-based-storage-optional-security-hardening) (identity-based binding against the new app's storage account):

- `AzureWebJobsStorage` — the raw connection string is dropped because `--storage-account` in 4b binds storage at the platform level. The platform sets a fresh value pointing at `<STORAGE_NAME>`.
- All `AzureWebJobsStorage__*` variants are dropped because carrying them over verbatim could silently point the new app's runtime at the **source** storage account regardless of which account 4b bound. If you need identity-based storage on the new app, [4b.opt](automation/app-creation.md#4bopt-identity-based-storage-optional-security-hardening) re-derives the required settings against `<STORAGE_NAME>` after assigning the data-plane roles.
