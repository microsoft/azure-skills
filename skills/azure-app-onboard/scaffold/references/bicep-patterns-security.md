# Bicep Patterns — Security Defaults

Mandatory security configuration for all AppOnboard-generated Bicep. Read during IaC generation before writing resource definitions. Apply during scaffold — never defer to deploy.

For core patterns (file structure, skeleton, naming, tagging), see [bicep-patterns.md](bicep-patterns.md). For data module templates (PostgreSQL, Redis), see [subagent-iac-gen.md](subagent-iac-gen.md) Step 6.

## Key Vault Deployer RBAC

The deploying user/principal needs RBAC to write secrets (scaffold seeds initial values) and read them (verify wiring):

- **Key Vault Secrets Officer** (`b86a8fe4-44ce-4948-aee5-eccb2c155cd7`) — write secrets
- **Key Vault Secrets User** (`4633458b-17de-408a-b874-0445c86b69e6`) — read secrets (also needed by app MI)

If the app seeds data using a generated secret (admin password, API key), either display it to the user at deploy time OR ensure the deployer has read RBAC on the Key Vault.

> ⛔ **Include a role assignment for the deploying user** (`context.json.azure.userObjectId`) with Key Vault Secrets Officer scoped to the Key Vault resource. Without this, `az keyvault secret set` fails with 403 during deploy secret seeding.

## Security Defaults

> **Source:** Adapted from Azure security best practices. See [Azure security baseline](https://learn.microsoft.com/en-us/security/benchmark/azure/overview) for updates.

### Identity — Managed Identity Everywhere

> ⛔ **Managed identity decision — evaluate top to bottom, first match wins.**
>
> | Condition | Include MI? |
> |-----------|-------------|
> | F1 or D1 SKU on Linux | **NO** (MI sidecar causes OOM — use `@secure()` param + KV deployer RBAC instead) |
> | Any Key Vault, database, storage, queue, or ACR access | **YES** |
> | None of the above | **YES** (default secure) |

- **System-assigned managed identity** for all services (default). User-assigned only when shared identity is explicitly needed.
- ⛔ **Never generate `administratorLogin` or `administratorLoginPassword`** for SQL — including inside conditional branches. Use Entra-only auth (see SQL Server pattern below).
- App-to-service auth: managed identity + RBAC role assignments. Zero secrets in code or config.

```bicep
identity: {
  type: 'SystemAssigned'
}
```

### SQL Server — Entra-Only Authentication

> For full SQL auth reference (connection strings, managed identity SQL grants, CI/CD principal types), see `azure-prepare/references/services/sql-database/auth.md`.

```bicep
param principalId string
param principalName string
@allowed(['User', 'Group', 'Application'])
param principalType string = 'User'

// Preview API required — azureADOnlyAuthentication via administrators block
// is not available in GA API versions (GA path uses a separate child resource).
resource sqlServer 'Microsoft.Sql/servers@2024-05-01-preview' = {
  name: '${resourcePrefix}-sql-${uniqueHash}'
  location: location
  properties: {
    administrators: {
      administratorType: 'ActiveDirectory'
      principalType: principalType
      login: principalName
      sid: principalId
      tenantId: subscription().tenantId
      azureADOnlyAuthentication: true
    }
    minimalTlsVersion: '1.2'
  }
}
```

> ⚠️ If deploying from CI/CD with a service principal, set `principalType` to `'Application'`. The default `'User'` only works for interactive deployments.

### Secrets — Key Vault References

Store secrets in Key Vault. Reference via app settings — never inline.

> ⛔ **No plaintext secrets in Bicep `appSettings`.** Values like `SECRET_KEY`, `JWT_SECRET`, `API_KEY`, session secrets, and database passwords MUST NOT be hardcoded — not even as placeholders. Never use `uniqueString()` for secrets (deterministic/predictable). These appear in ARM deployment history and persist in source control.
>
> **Container Apps exception:** Phase 1 of two-phase deployment uses `secrets: []` — NO secrets at all (not plaintext, not KV). KV `secretRef` entries are activated in Phase 2 after RBAC propagates. See [bicep-container-apps.md](../../scaffold/references/bicep-container-apps.md) § Two-Phase Wiring.
>
> ⛔ **Container Apps KV URL — do NOT use `environment().suffixes.keyvaultDns`.** That function returns `.vault.azure.net` (WITH leading dot) → double-dot URL → `ContainerAppSecretKeyVaultUrlInvalid`. Use `'https://${kvName}.vault.azure.net/secrets/...'` with `#disable-next-line no-hardcoded-env-urls` to suppress the linter.
>
> **Correct patterns:**
> 1. **Key Vault reference (preferred):** `'@Microsoft.KeyVault(VaultName=${kvName};SecretName=secret-key)'`
> 2. **Deploy-time seeding (free-tier):** Omit from Bicep; run `az webapp config appsettings set --settings SECRET_KEY=$(openssl rand -base64 32)` post-deploy
> 3. **Bicep `@secure()` parameter:** Pass via CLI `--parameters secretKey=$(openssl rand -base64 32)` — never committed to parameters.json
>
> ❌ **NEVER:** `{ name: 'SECRET_KEY', value: 'hard-to-guess-string' }` or `value: 'change-me'` in Bicep

```bicep
// App Service / Functions — Key Vault reference pattern
appSettings: [
  {
    name: 'DB_CONNECTION_STRING'
    value: '@Microsoft.KeyVault(VaultName=${kvName};SecretName=db-connection-string)'
  }
]
```

Key Vault module — emit this resource EXACTLY; add no other properties. `enablePurgeProtection` is deliberately absent (ARM rejects `false`; `true` blocks cleanup).

```bicep
resource kv 'Microsoft.KeyVault/vaults@{apiVersion}' = {
  name: kvName
  location: location
  tags: tags
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true          // RBAC, not access policies
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    networkAcls: { defaultAction: 'Allow', bypass: 'AzureServices' }
  }
}
```

### Transport — HTTPS Only

All web-facing resources:

```bicep
// App Service
httpsOnly: true
siteConfig: {
  minTlsVersion: '1.2'
}

// Storage
supportsHttpsTrafficOnly: true
allowBlobPublicAccess: false
minimumTlsVersion: 'TLS1_2'
```

### App Service / Functions — Publishing Credential Lockdown

> ⛔ **Every App Service and Functions app MUST include both `basicPublishingCredentialsPolicies` child resources.** Missing these means deploy cannot toggle SCM auth post-deployment — the REST API call targets a resource that doesn't exist in ARM.

```bicep
// SCM — allow: true for deploy phase (deploy re-disables via REST API after code upload)
resource scmAuth 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2023-12-01' = {
  parent: appService
  name: 'scm'
  properties: {
    allow: true
  }
}

// FTP — always disabled
resource ftpAuth 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2023-12-01' = {
  parent: appService
  name: 'ftp'
  properties: {
    allow: false
  }
}
```

> **Deploy lifecycle:** Scaffold sets `scm.allow: true` so `az webapp deploy` works. After code upload + health check, deploy phase runs `az rest --method put .../basicPublishingCredentialsPolicies/scm` with `allow: false` to re-harden. If scaffold omits these resources, deploy's Step 7 SCM re-disable REST API call fails silently.

### Cosmos DB — Data Plane RBAC

⛔ Cosmos DB uses its own role system — see [rbac-roles.md](rbac-roles.md) § Cosmos DB for role IDs and behavioral rules. Do NOT use `Microsoft.Authorization/roleAssignments` for Cosmos data access.

### RBAC — Deterministic Role Assignments

For the common roles GUID table, see [rbac-roles.md](rbac-roles.md).

```bicep
resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(scopeResourceId, principalId, roleDefinitionId)
  scope: targetResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitionId)
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'  // REQUIRED — prevents AAD graph lookup delays
  }
}
