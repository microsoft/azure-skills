# Composition Algorithm

Combine multiple templates into a single deployable project.

## Azure MCP Path

```
INPUT: language, user_requirements
OUTPUT: Complete project ready for `azd up`

1. DISCOVER
   functions_template_get(language) → template list with descriptions

2. CHECK SINGLE-TEMPLATE MATCH
   If one template's description covers ALL requirements → use it alone

3. SELECT TEMPLATES
   - Trigger template (REQUIRED) — base project with IaC
   - Binding templates (OPTIONAL) — extract patterns only

4. FETCH TEMPLATES
   - Single match: 1 call
   - Multiple: parallel calls

5. COMPOSE
   - Use trigger template as BASE (functionFiles + projectFiles)
   - EXTRACT binding patterns from binding templates
   - MERGE IaC resources and RBAC roles
   - ADD user's custom business logic

6. TRIM unused demo code (keep AzureWebJobsStorage)

7. WRITE files — for each entry { path, content } in functionFiles[] AND projectFiles[]:
      a. Create parent directories from path
      b. Write content to path
      NEVER hand-write Bicep/Terraform and use azd init -t/func init/func new as fallback when composing multiple recipes and required templates are not found

8. DEPLOY: azd up --no-prompt
```

## Fallback Path (Azure MCP Unavailable)

```
INPUT: language, user_requirements
OUTPUT: Complete project ready for `azd up`

1. FETCH MANIFEST
   GET https://cdn.functions.azure.com/public/templates-manifest/manifest.json
   If fetch fails → fall back to: https://github.com/Azure/azure-functions-templates/blob/dev/Functions.Templates/Template-Manifest/manifest.json
   If both fail → fall back to known-good Azure-Samples/functions-quickstart-* repos by language+resource
   If all fail → report error and ask user to retry later

2. FILTER TEMPLATES
   Filter by: language, resource (from selection.md), iac

3. CHECK SINGLE-TEMPLATE MATCH
   If one template covers ALL requirements → use it alone

4. SELECT TEMPLATES
   - Trigger template (REQUIRED) — base project
   - Binding templates (OPTIONAL) — extract patterns only

5. DOWNLOAD TEMPLATES
   For each template:
   - If folderPath == "." → ZIP download + unzip
   - If folderPath != "." → fetch tree + raw github url file downloads
   - Fallback: git clone --depth 1

6. COMPOSE
   - Use trigger template as BASE
   - EXTRACT binding patterns from binding templates
   - MERGE IaC resources, RBAC roles and settings, README and other files.
   - ADD user's custom business logic

7. TRIM unused demo code (keep AzureWebJobsStorage)

8. WRITE all files

9. DEPLOY: azd up --no-prompt
```

## Example (MCP)

**User:** "HTTP function that writes to Cosmos DB"

```
1. Discover: functions_template_get(language: "python") → returns template list
2. Check: No single template description mentions BOTH HTTP trigger AND Cosmos output
3. Select from discovered list:
   - Template with resource: "http" (trigger, base)
   - Template with resource: "cosmos" and description mentioning "output" (binding)
4. Fetch both templates by templateName from discovery results
5. Compose:
   - Base: HTTP template (has IaC, azure.yaml)
   - Extract: Cosmos output binding + RBAC from cosmos template
   - Merge: Add Cosmos module to infra/main.bicep
6. Trim: Remove HTTP demo response code
7. Write files
8. Deploy
```

## Example (Fallback)

**User:** "HTTP function that writes to Cosmos DB"

```
1. Fetch: GET manifest.json from CDN
2. Filter: language=Python, resource=http OR resource=cosmos, iac=bicep
3. Check: No single template covers both
4. Select:
   - http-trigger-python-azd (trigger, base) → repositoryUrl + folderPath
   - cosmos-trigger-python-azd (binding) → repositoryUrl + folderPath
5. Download: ZIP download both repos (folderPath = ".")
6. Compose:
   - Base: HTTP template (has infra/, azure.yaml)
   - Extract: Cosmos IaC module + RBAC from cosmos template
   - Merge: Add cosmos.bicep to infra/app/, wire into main.bicep
7. Trim: Remove demo code
8. Write files
9. Deploy
```

## Critical Rules

1. **NEVER hardcode template names** — always discover/fetch manifest first
2. **PRESERVE generated IaC patterns** — keep RBAC roles, managed identity config, and security settings intact when merging
3. **ALWAYS keep AzureWebJobsStorage** — runtime requires it
4. **ALWAYS use `--no-prompt`** — the agent must never elicit user input during azd commands
5. **ALWAYS include ALL THREE UAMI settings for every binding** — see UAMI Configuration below
6. **ALWAYS wait for RBAC propagation** — use two-phase deploy if 403 errors occur
7. **NEVER enable `allowSharedKeyAccess: true`** — correct solution is waiting for RBAC, not disabling security

## IaC Merge Guidelines

When composing multiple templates:

| Action | Allowed | Not Allowed |
|--------|---------|-------------|
| Add resource modules from binding templates | ✅ | |
| Add RBAC role assignments from binding templates | ✅ | |
| Merge environment variables | ✅ | |
| Remove RBAC roles | | ❌ |
| Change managed identity to connection strings | | ❌ |
| Remove security configurations | | ❌ |
| Modify resource SKUs without user request | | ❌ |

**Merge = additive combination, not modification of security patterns.**

## UAMI Configuration (CRITICAL)

Templates use User Assigned Managed Identity (UAMI). ALL service bindings require explicit `credential` and `clientId` app settings. Missing these causes 500/401/403 errors at runtime.

**Required pattern for EVERY service binding:**

```bicep
appSettings: {
  // Endpoint (varies by service)
  EventHubConnection__fullyQualifiedNamespace: eventhubs.outputs.fullyQualifiedNamespace
  // UAMI credentials - REQUIRED, prefix vary by example
  EventHubConnection__credential: 'managedidentity'
  EventHubConnection__clientId: apiUserAssignedIdentity.outputs.clientId
}
```

**Validation Checklist (MANDATORY before deploy):**

| Setting Pattern | Required | Example |
|-----------------|:--------:|---------|
| `{Connection}__fullyQualifiedNamespace` or `{Connection}__accountEndpoint` | ✅ | `EventHubConnection__fullyQualifiedNamespace` |
| `{Connection}__credential` | ✅ | `'managedidentity'` (exact case) |
| `{Connection}__clientId` | ✅ | `apiUserAssignedIdentity.outputs.clientId` |

> ⛔ **STOP if any check fails.** The function WILL fail at runtime with 500/Unauthorized errors.

## Language-Specific Entry Points

### Node.js (JavaScript/TypeScript)

> ⛔ **Do NOT delete `src/index.js` (JS) or `src/index.ts` (TS).**
> This file contains `app.setup()` which initializes the Functions runtime.
> Without it, functions deploy but return 404 on all endpoints.

> ⛔ **Glob pattern REQUIRED in package.json:**
>
> ```json
> { "main": "src/{index.js,functions/*.js}" }
> ```
>
> Using `"main": "src/index.js"` alone results in 404 on ALL endpoints.

> ⛔ **package.json must be at project ROOT** (same level as `azure.yaml`), NOT inside `src/`.

> 📦 **TypeScript:** Run `npm run build` before deployment.
> Use: `"main": "dist/src/{index.js,functions/*.js}"`

### C# (.NET)

> ⛔ **Do NOT replace `Program.cs` from the base template.**
> The base template uses `ConfigureFunctionsWebApplication()` with App Insights integration.
> Recipes only ADD trigger function files (`.cs`) and package references (`.csproj`).

## Deployment Strategy

**Option A: Single command** (fast, may fail on first deploy due to RBAC propagation)

```bash
azd up --no-prompt
```

**Option B: Two-phase** (recommended for reliability)

```bash
azd provision --no-prompt     # Create resources + RBAC assignments
sleep 60                       # Wait for RBAC propagation (Azure AD needs 30-60s)
azd deploy --no-prompt        # Deploy code (RBAC now active)
```

## Terraform-Specific Requirements

> ⚠️ **CRITICAL**: All Terraform must use `sku_name = "FC1"` (Flex Consumption). **NEVER use Y1/Dynamic.**

### Runtime Versions

> ⚠️ **ALWAYS QUERY OFFICIAL DOCUMENTATION** — Do NOT use hardcoded versions.
>
> **Primary Source:** [Azure Functions Supported Languages](https://learn.microsoft.com/en-us/azure/azure-functions/supported-languages)
>
> Query for latest GA/LTS versions before generating IaC.

| Language | `function_runtime` | Version Source |
|----------|-------------------|----------------|
| C# (.NET) | `dotnet-isolated` | Latest LTS from docs |
| TypeScript/JS | `node` | Latest LTS from docs |
| Python | `python` | Latest GA from docs |
| Java | `java` | Latest LTS from docs |
| PowerShell | `powershell` | Latest GA from docs |

### Flex Consumption (FC1) Requires azapi

> ⚠️ Use `azapi_resource` instead of `azurerm_linux_function_app` for FC1.
> The AzureRM provider doesn't support FC1's `functionAppConfig` block.

```hcl
resource "azapi_resource" "function_app" {
  type      = "Microsoft.Web/sites@2023-12-01"
  name      = "func-${local.name}"
  location  = azurerm_resource_group.rg.location
  parent_id = azurerm_resource_group.rg.id

  body = {
    kind = "functionapp,linux"
    properties = {
      serverFarmId = azapi_resource.plan.id
      functionAppConfig = {
        runtime = { name = "node", version = "22" }
        scaleAndConcurrency = { maximumInstanceCount = 100, instanceMemoryMB = 2048 }
        deployment = {
          storage = {
            type  = "blobContainer"
            value = "${azurerm_storage_account.storage.primary_blob_endpoint}deploymentpackage"
            authentication = {
              type                           = "UserAssignedIdentity"
              userAssignedIdentityResourceId = azurerm_user_assigned_identity.api.id
            }
          }
        }
      }
    }
  }
  depends_on = [time_sleep.rbac_propagation]
}
```

### RBAC Propagation Delay

Azure RBAC takes 30-60s to propagate. Terraform's `depends_on` only waits for resource creation, not RBAC propagation.

**Solution 1: Add `time_sleep` resource**

```hcl
resource "time_sleep" "rbac_propagation" {
  depends_on      = [azurerm_role_assignment.storage_blob_owner]
  create_duration = "60s"
}

resource "azapi_resource" "function_app" {
  depends_on = [time_sleep.rbac_propagation]
  # ...
}
```

**Solution 2: Create deployment container explicitly**

```hcl
resource "azurerm_storage_container" "deployment" {
  name                  = "deploymentpackage"
  storage_account_id    = azurerm_storage_account.storage.id
  container_access_type = "private"
  depends_on            = [azurerm_role_assignment.storage_blob_owner]
}
```

> ⚠️ **Common Failures Without These Fixes:**
>
> - `403 Forbidden` — RBAC not yet propagated
> - `404 Container Not Found` — deployment container not created
> - `Tag Not Found: azd-service-name` — Azure resource tags take time to be queryable

### Required: azd-service-name Tag

```hcl
tags = {
  "azd-service-name" = "api"   # MUST match service name in azure.yaml
}
```

> ⚠️ **Without this tag, `azd deploy` fails with:**
> `resource not found: unable to find a resource tagged with 'azd-service-name: api'`

### Disabled Local Auth (Policy Required)

Azure Policy often enforces RBAC-only authentication. Always disable local auth (connection strings, SAS keys) and use managed identity instead.

```hcl
# Storage
shared_access_key_enabled = false

# Service Bus
local_auth_enabled = false

# Event Hubs
local_authentication_enabled = false

# Cosmos DB
local_authentication_disabled = true
```
