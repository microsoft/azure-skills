# Bicep — Container Apps Patterns

Container Apps-specific Bicep patterns. For shared patterns (skeleton, naming, tags, security defaults, data modules), see [bicep-patterns.md](bicep-patterns.md).

## Two-Phase Wiring

Container Apps + ACR requires two-phase deployment (circular dependency: CA needs ACR image, ACR needs CA identity for AcrPull):

1. **Phase 1:** Deploy Container App with placeholder image (`mcr.microsoft.com/azuredocs/containerapps-helloworld:latest`). ⛔ **No `registries` block, no KV `secretRef`.** The placeholder image is pulled from MCR (public). Use `registries: []` and `secrets: []`. **RBAC role assignments (AcrPull, KV Secrets User) ARE created in Phase 1** — they don't affect the placeholder deployment and need 1–2 minutes to propagate before Phase 2.
2. **Phase 2:** Build + push app image to ACR, redeploy with real image + `registries` + KV `secretRef` entries. RBAC is already propagated from Phase 1.

> ⛔ **Placeholder image listens on port 80, not your app's port.** Set `targetPort` conditionally: `var effectivePort = containerImage == 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest' ? 80 : appPort`. Mismatched ports cause "Operation expired" (health probe can't reach container).

> ⛔ **`containerImage` param must exist in BOTH `main.bicep` AND the container app module.** Phase 2 passes `--parameters containerImage='...'` via CLI — if `main.bicep` lacks the param, the override is silently ignored and the placeholder persists.

```bicep
// In main.bicep: thread containerImage to module
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
module containerApp './modules/containerapp.bicep' = {
  params: { containerImage: containerImage /* ...other params... */ }
}

// In containerapp.bicep:
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
var isPlaceholder = containerImage == 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  identity: { type: 'SystemAssigned' }
  properties: {
    configuration: {
      ingress: {
        external: true
        targetPort: isPlaceholder ? 80 : appPort
        allowInsecure: false  // ⛔ MANDATORY
      }
      registries: isPlaceholder ? [] : [{ server: acr.properties.loginServer, identity: 'system' }]
      secrets: isPlaceholder ? [] : [ /* KV secretRefs here */ ]
    }
    template: {
      containers: [{
        image: containerImage
        env: [{ name: 'PORT', value: string(isPlaceholder ? 80 : appPort) }]
      }]
    }
  }
}
```

> ⛔ **Do NOT set `revisionSuffix`.** Omit it entirely — ARM auto-generates unique revision names. Hardcoding `revisionSuffix: 'v1'` causes Phase 2 redeploy to fail with "revision with suffix v1 already exists."

### AcrPull Role Assignment

> ⛔ **AcrPull role GUID: `7f951dda-4ed3-4680-a7ca-43fe172d538d`.** Copy verbatim — wrong GUIDs cause `RoleDefinitionDoesNotExist`.

```bicep
resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, containerApp.id, '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: containerApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}
```

## Log Analytics Workspace Key

> ⛔ **Use `resource.listKeys()`, NOT `reference()`.** `reference()` does not expose `primarySharedKey`.

```bicep
// ✅ Correct
var laKey = logAnalyticsWorkspace.listKeys().primarySharedKey

// ❌ Wrong
var laKey = reference(logAnalyticsWorkspace.id, '2023-09-01').primarySharedKey
```

### Log Analytics customerId vs resource ID

> ⛔ **Output BOTH `id` and `customerId` from the log-analytics module.** Container Apps Environment needs the GUID `customerId`. App Insights needs the ARM resource ID. Do NOT use `split(workspaceId, '/')[8]` — that extracts the workspace name, not the GUID.

```bicep
// log-analytics.bicep outputs:
output id string = logAnalyticsWorkspace.id                            // ARM resource ID
output customerId string = logAnalyticsWorkspace.properties.customerId // GUID
output sharedKey string = logAnalyticsWorkspace.listKeys().primarySharedKey

// container-app-environment.bicep:
param workspaceCustomerId string  // GUID, NOT resource ID
// ⛔ MUST nest under appLogsConfiguration.destination='log-analytics' — a bare top-level logAnalyticsConfiguration fails deploy (ManagedEnvironmentInvalidSchema). This nesting is the ONLY valid location at EVERY API version (the flat shape was never valid — NOT version drift, so do not chase API-version pins). This is the CA's only log path (no diagnostic-settings module).
properties: {
  appLogsConfiguration: {
    destination: 'log-analytics'
    logAnalyticsConfiguration: {
      customerId: workspaceCustomerId
      sharedKey: workspaceSharedKey
    }
  }
}
// ❌ WRONG: customerId: split(workspaceId, '/')[8]
```

## Ingress & Port Mapping

> ⛔ **Container resource limits:** Use decimal format for memory: `'0.5Gi'`, `'1Gi'`, `'2Gi'` — NOT Kubernetes-style `'512Mi'`. CPU must be type `string`: `'0.25'`, `'0.5'`, `'1'`. Valid combos: `0.25/0.5Gi`, `0.5/1Gi`, `0.75/1.5Gi`, `1/2Gi`, `1.25/2.5Gi`, `1.5/3Gi`, `1.75/3.5Gi`, `2/4Gi`.

> ⛔ **ACR module:** `retentionPolicy` is **Premium-only**. For Basic/Standard ACR, omit `retentionPolicy` entirely — ARM rejects it.

## Key Vault Secret References

> ⛔ **Container Apps does NOT support `@Microsoft.KeyVault(SecretUri=...)` syntax.** That is App Service-only. Container Apps uses `secretRef` with managed identity.

**Correct pattern — Container Apps secrets from Key Vault:**

> ❌ **WRONG — `environment().suffixes.keyvaultDns` produces double-dot URL:**
> `keyVaultUrl: 'https://${kvName}${environment().suffixes.keyvaultDns}/secrets/...'`
> That function returns `.vault.azure.net` (WITH leading dot) → `kv-name..vault.azure.net` → `ContainerAppSecretKeyVaultUrlInvalid`.
> ✅ Use `keyVault.name` + `.vault.azure.net` (hardcoded domain) or `keyVaultModule.outputs.vaultUri`.

> ⛔ **Every `secrets[].keyVaultUrl` in a Container App MUST have a matching `Microsoft.KeyVault/vaults/secrets` child resource in the KV module.** If the CA references `sshpass` via secretRef, the KV module must create that secret. Missing secrets → `SecretNotFound` at Phase 2 deploy.

```bicep
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    configuration: {
      secrets: [
        {
          name: 'db-connection-string'
          // ⛔ Do NOT replace vault.azure.net with environment().suffixes.keyvaultDns — it adds a leading dot → double-dot URL
          #disable-next-line no-hardcoded-env-urls
          keyVaultUrl: 'https://${keyVault.name}.vault.azure.net/secrets/db-connection-string'
          identity: 'system'  // Uses the CA's system-assigned managed identity
        }
      ]
    }
    template: {
      containers: [{
        env: [
          {
            name: 'DATABASE_URL'
            secretRef: 'db-connection-string'  // References the secret defined above
          }
        ]
      }]
    }
  }
}
```

> ⛔ **Never use conditional logic (`??`, ternary, `empty()`, `union()`) to mix plain and secret env vars in a single Bicep loop or array.** ARM evaluates ALL property paths in conditional expressions — `envVar.secretRef` errors on items that don't have that property, producing `InvalidTemplate`. Instead, define plain and secret env vars as separate arrays and concatenate:
>
> ```bicep
> env: concat(
>   [
>     { name: 'PORT', value: '8000' }
>     { name: 'NODE_ENV', value: 'production' }
>   ],
>   [
>     { name: 'DATABASE_URL', secretRef: 'db-connection-string' }
>     { name: 'REDIS_URL', secretRef: 'redis-connection-string' }
>   ]
> )
> ```

> ⛔ **KV Secrets User role scoped to Key Vault resource — NOT `resourceGroup()`.** Scoping to `resourceGroup()` causes 403.

```bicep
resource kvRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: keyVault                    // ⛔ scope to KV resource, not RG
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6') // Key Vault Secrets User
    principalId: containerApp.identity.principalId  // ⛔ object ID, NOT clientId
    principalType: 'ServicePrincipal'
  }
}
```

> ❌ **WRONG:** `principalId: .clientId` (not the object ID) or `identity: containerApp.id` in secrets[] (use `'system'` for system-assigned MI).

> For KV secret seeding and dependency chain, see [env-var-secrets.md](env-var-secrets.md).

## Multi-Container Internal DNS

Container Apps in the same environment communicate via internal DNS: `http://{container-app-name}`. Set via env vars:

```bicep
env: [
  { name: 'API_URL', value: 'http://${apiContainerApp.name}' }
  { name: 'WORKER_URL', value: 'http://${workerContainerApp.name}' }
]
```

No ingress needed for internal-only services — set `ingress.external: false` or omit ingress entirely.

## Networking

> ⛔ **Subnets MUST be defined inline** in VNet `properties.subnets[]`, NOT as separate `Microsoft.Network/virtualNetworks/subnets` child resources. Separate child resources cause `InUseSubnetCannotBeDeleted` on redeploy when NICs are attached.
