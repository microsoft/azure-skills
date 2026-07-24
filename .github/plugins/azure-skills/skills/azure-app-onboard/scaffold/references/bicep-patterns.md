# Bicep Patterns

Bicep default-path patterns for AppOnboard scaffold. Used as the primary IaC format. For the alternative Terraform path (existing `.tf` files or user override), scaffold uses `mcp_azure_mcp_azureterraformbestpractices` output patterns.

> **Source:** Adapted from Azure Bicep best practices. See [Bicep best practices](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/best-practices) for updates.

## File Structure

> ⛔ **Always use `targetScope = 'subscription'`.** Subscription-scope Bicep creates the resource group in IaC with all 5 AppOnboard tags (including `created-at`). Resource-group scope requires `az group create` via CLI, which consistently misses `created-at` because CLI-created resource groups don't receive IaC-managed tags. There are zero benefits to resource-group scope for AppOnboard.

```
infra/
├── main.bicep              # Entry point (subscription scope)
├── main.parameters.json    # ARM JSON parameter values (NOT .bicepparam)
└── modules/
    ├── container-app.bicep
    ├── app-service.bicep
    ├── sql-database.bicep
    ├── key-vault.bicep
    ├── log-analytics.bicep
    └── ...
```

Each service gets its own module. `main.bicep` orchestrates resource group creation + module calls.

## main.bicep Skeleton

```bicep
targetScope = 'subscription'

@minLength(1)
@maxLength(64)
param environmentName string

@minLength(1)
param location string

param sessionId string

param deployedBy string   // resolved via: az ad signed-in-user show --query displayName -o tsv

// ⛔ createdAt: passed in parameters.json, NOT utcNow() default (crashes Portal blade)
param createdAt string

var tags = {
  'app-onboard-skill': 'true'
  'app-onboard-session-id': sessionId
  'created-at': createdAt
  environment: environmentName
  'deployed-by': deployedBy
}

resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

// ⛔ scope: rg (symbolic) — creates implicit dependsOn. Do NOT use resourceGroup(name) — it races against RG creation.
module resources './modules/resources.bicep' = {
  name: 'resources'
  scope: rg
  params: {
    location: location
    environmentName: environmentName
    tags: tags
  }
}
```

## main.parameters.json

> ⛔ **ARM JSON only.** Do NOT use `.bicepparam` syntax (`using`, `param`, `readEnvironmentVariable()`). AppOnboard deploys via `az deployment sub create` (subscription-scope default) — not `azd` — and `.bicepparam` requires azd or newer tooling. If the user lacks subscription-level permissions, the deploy phase falls back to `az deployment group create` automatically.

```json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "environmentName": { "value": "{project}-{env}" },
    "location": { "value": "{region}" },
    "sessionId": { "value": "{context.json.sessionId}" },
    "deployedBy": { "value": "{context.json.azure.userDisplayName}" }
  }
}
```

## Naming Convention (Bicep)

The prepare phase generates a logical resource prefix in `prepare-plan.json.naming.resourcePrefix` (e.g., `myapp-dev`). Scaffold MUST add a globally unique suffix using Bicep's `uniqueString()` function to prevent cross-deployment name collisions on globally unique Azure resources (App Service, Key Vault, Storage Account, ACR).

```bicep
// main.bicep — derive unique suffix from resource group
var nameSuffix = uniqueString(resourceGroup().id)

// Pass unique names to modules
param kvName string = 'kv-${resourcePrefix}-${take(nameSuffix, 4)}'
param appName string = 'app-${resourcePrefix}-${take(nameSuffix, 4)}'
param storName string = 'st${replace(resourcePrefix, '-', '')}${take(nameSuffix, 4)}'
param acrName string = 'cr${replace(resourcePrefix, '-', '')}${take(nameSuffix, 4)}'
```

> ⛔ **Do NOT use `uniqueString()` for secrets** — it is deterministic and predictable. See [bicep-patterns-security.md](bicep-patterns-security.md) § Secrets for correct secret patterns.

If `prepare-plan.json.naming.resources[]` provides pre-computed names with suffixes, prefer those — but ALWAYS ensure globally unique resources include a `uniqueString()` or equivalent hash in main.bicep as a safety net.

## Log Analytics Module Output

> ⛔ **Output the resource ID (`.id`), NOT `.properties.customerId`.** Container Apps Environment requires `workspaceResourceId` (the full ARM resource ID). `.properties.customerId` is the GUID used for queries — passing it as `workspaceResourceId` causes an ARM deploy failure (`BadRequest`). Separate the two outputs:
> ```bicep
> output workspaceId string = logAnalyticsWorkspace.id                          // ARM resource ID — for CAE, App Insights
> output workspaceCustomerId string = logAnalyticsWorkspace.properties.customerId // GUID — for Log Analytics queries only
> ```

## Compute-Target Patterns

Read the file(s) matching the service mapping — load only what's needed:
- **App Service / Functions:** [bicep-app-service.md](bicep-app-service.md) — module template, SCM/FTP auth, native module deploy strategy
- **Container Apps:** [bicep-container-apps.md](bicep-container-apps.md) — two-phase ACR wiring, ingress, secretRef, image parameter, multi-container DNS
- **Static Web Apps:** [bicep-swa.md](bicep-swa.md) — module template, detached deploy rule

Load multiple only if the plan includes multiple compute targets.

> ⛔ **F1/D1 SKU: do NOT generate a Dockerfile.** If `prepare-plan.json` specifies F1 or D1 (free/shared tier), use the platform's built-in runtime stack (e.g., `NODE|20-lts` for Node.js, `PYTHON|3.12` for Python). Dockerfiles are for B1+ or Container Apps only.

> ⛔ **Native module deploy strategy.** If `prepare-plan.json.deployStrategy` exists, read [bicep-app-service.md § Native Module Deploy Strategy](bicep-app-service.md) and apply the startup command + app settings. `deployStrategy.startupCommand` → `appCommandLine`, `deployStrategy.requiredAppSettings` → `appSettings[]`. When no `deployStrategy` exists, do NOT set `appCommandLine`.

## Service Tagging

> ⛔ **You MUST read [iac-generation-rules.md § Session Tags](iac-generation-rules.md).** All resources MUST include the 5 AppOnboard session tags. Pass `tags` object from `main.bicep` into every module.

## API Version Policy

Use the latest stable API version for each resource type. Never use preview APIs unless required for a feature with no GA alternative. Validate via `bicep build` — stale API versions produce warnings.

## Key Vault Reference Syntax

Syntax differs by service — never mix. See [bicep-container-apps.md](bicep-container-apps.md) for Container Apps `secretRef` and [bicep-patterns-security.md](bicep-patterns-security.md) for App Service `@Microsoft.KeyVault()`. For Terraform, see [terraform-patterns.md](terraform-patterns.md).
