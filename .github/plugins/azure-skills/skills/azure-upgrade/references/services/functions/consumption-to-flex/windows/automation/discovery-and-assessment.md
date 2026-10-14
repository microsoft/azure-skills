# Discovery and Assessment

## Prerequisites

```bash
# Verify the Azure CLI version
az version --query '"azure-cli"' -o tsv

# Install required CLI extensions
az extension add --name resource-graph
az extension add --name application-insights

# Login and set subscription
az login
az account set --subscription <SUBSCRIPTION_ID>
```

If `az` is unavailable, stop and provide Azure CLI installation guidance. If the reported version is lower than `2.77.0`, stop and require an upgrade before running migration commands. When using the Bash path, also run `jq --version` before the first Bash block that uses `jq`; stop with installation guidance if it is unavailable. PowerShell 7 uses `ConvertFrom-Json` and does not require `jq`.

---

## Step 1: Identify Candidate Apps

Use a single Azure Resource Graph query to list all Windows function apps running on a Consumption (Y1/Dynamic) plan in the current subscription:

```bash
az graph query -q "resources | where subscriptionId == '$(az account show --query id -o tsv)' | where type == 'microsoft.web/sites' | where ['kind'] == 'functionapp' | where properties.sku == 'Dynamic' | project name, location, resourceGroup" --query data --output table
```

This returns app name, location, and resource group for every Windows Consumption (Y1) function app. The `kind == 'functionapp'` filter excludes Linux apps (`functionapp,linux`) and the `properties.sku == 'Dynamic'` filter excludes Premium / Dedicated / Isolated / Flex Consumption.

> 💡 The `$(az account show --query id -o tsv)` sub-expression works in both bash and PowerShell. The `--subscriptions` flag also accepts an explicit subscription ID if you want to target a different sub.

---

## Step 2: Assessment Checks

Run these checks against each candidate app from Step 1.

### 2a. Confirm Region Compatibility

```bash
# List all regions where Flex Consumption is available
az functionapp list-flexconsumption-locations --query "sort_by(@, &name)[].{Region:name}" -o table
```

### 2b. Verify Language Stack Compatibility

Read the runtime and Functions host generation from app settings:

```bash
az functionapp config appsettings list --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query "[?name=='FUNCTIONS_WORKER_RUNTIME' || name=='FUNCTIONS_EXTENSION_VERSION'].{N:name,V:value}" -o table
```

Pass criteria:

- `FUNCTIONS_WORKER_RUNTIME` is one of: `dotnet-isolated`, `node`, `java`, `python`, `powershell`, `go`, `custom`.
- `FUNCTIONS_EXTENSION_VERSION` is `~4`.

**Not supported**: `dotnet` (in-process) — must migrate to isolated first. Any `FUNCTIONS_EXTENSION_VERSION` other than `~4` is a blocker.

The CLI only returns the stored values; the supported-list comparison is yours to make. Capture the runtime as `<RUNTIME>` for Step 2c. `FUNCTIONS_EXTENSION_VERSION` is the Functions host generation, not the language runtime version used by `az functionapp create --runtime-version`.

### 2c. Verify Stack Version Compatibility

First collect source-version signals. These values can be empty or stale and are evidence only; `FUNCTIONS_WORKER_RUNTIME_VERSION` is not guaranteed to be present and must not be treated as authoritative:

```bash
az functionapp config appsettings list --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query "[?name=='FUNCTIONS_WORKER_RUNTIME_VERSION' || name=='WEBSITE_NODE_DEFAULT_VERSION'].{name:name,value:value}" -o table
az functionapp config show --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query "{netFrameworkVersion:netFrameworkVersion,javaVersion:javaVersion,nodeVersion:nodeVersion,powerShellVersion:powerShellVersion}" -o table
```

Check the versions supported for `<RUNTIME>` in the source app's region:

```bash
az functionapp list-flexconsumption-runtimes --location <REGION> --runtime <RUNTIME> --query "[].version" -o tsv
```

Resolve `<TARGET_RUNTIME_VERSION>` from the strongest available evidence: source project metadata, then deployed-package metadata, then the Azure configuration signals above. Examples include `.csproj` `TargetFramework`, `package.json` `engines.node`, `pom.xml` or Gradle Java toolchain, `pyproject.toml`/`runtime.txt`, and `go.mod`.

Require the resolved value to exactly match one of the supported versions returned by the command. If the evidence is missing, conflicting, or maps to multiple supported versions, use `ask_user` to show the evidence and supported values and have the user select the intended target version. Explain that selecting a different language version can require code or dependency changes. Record both `<RUNTIME>` and `<TARGET_RUNTIME_VERSION>` in the assessment report and upgrade status; do not guess or default to the newest version.

### 2d. Check Deployment Slots

```bash
az functionapp deployment slot list --name <APP_NAME> --resource-group <RESOURCE_GROUP> --output table
```

If this returns entries, the app has slots. Flex Consumption does NOT support slots — plan accordingly.

### 2e. Check TLS/SSL Certificates

List certificates available in the source app's resource group:

```bash
az webapp config ssl list --resource-group <RESOURCE_GROUP> --output table
```

If this returns output, determine which certificates the source app actually uses. Record whether each used certificate is private or public and confirm the target can fit within the Flex Consumption limit of three private and three public certificates per app. Plan to re-add them using the documented [site-scoped certificate process](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to#configure-site-scoped-certificates).

`WEBSITE_LOAD_CERTIFICATES` is not used by Flex Consumption. Code that accesses the Windows certificate store must instead load accessible certificates from `/var/ssl/certs` for public certificates or `/var/ssl/private` for private certificates.

### 2f. Check Blob Storage Triggers

Find blob triggers NOT using EventGrid source:

```bash
az functionapp function list --name <APP_NAME> --resource-group <RESOURCE_GROUP> --query "[?config.bindings[0].type=='blobTrigger' && config.bindings[0].source!='EventGrid'].{Function:name, TriggerType:config.bindings[0].type, Source:config.bindings[0].source}" --output table
```

If this returns rows, convert those blob triggers from `LogsAndContainerScan` to `EventGrid` before upgrading.

### 2g. Source Code Windows Dependency Scan

Recommended for every Windows → Flex migration. Prefer the local source directory or a checked-out repository because project manifests and API usage are directly inspectable. Use the deployed package retrieved in [Step 3e](deployment-package.md#3e-get-deployment-package-if-needed) only when source is unavailable; it confirms what is running but compiled artifacts may reduce scan coverage. The scan checks for Windows-only APIs, packages, registry/cert-store/COM/WMI usage, Windows-RID targeting, Windows-only PowerShell modules, and shell-outs to Windows tools.

Before concluding that source is unavailable, use `ask_user` to request a local source directory or checked-out repository path. Do not assume the current workspace contains the function app. If the user cannot provide source, offer to download the deployed package or skip the scan.

The agent dispatches per-language scanning automatically from the `FUNCTIONS_WORKER_RUNTIME` value captured in [Step 2b](#2b-verify-language-stack-compatibility) — no separate language input needed.

Follow the full procedure (inputs, pattern sets for all seven worker runtimes, severity rubric, output model, §11 report section) in [dependency-scan.md](../dependency-scan.md).

> ⚠️ **Skill instruction**: Announce the scan to the user before running it, **and tell them the scan is a heuristic aid only — it pattern-matches the most common Windows-only APIs, packages, and shell-outs but is not exhaustive. The user remains responsible for verifying their code has no Windows dependencies.** If they decline, write *"User declined the source code dependency scan"* to §11 of the assessment report and proceed — this scan is **never** a hard gate. Any `Blocker` findings advisorily flip §1 Upgrade Readiness to `Needs Attention`; the user always decides whether to proceed.

---
