# Container Apps Bicep Patterns

> **⚠️ Container Registry Naming:** If using Azure Container Registry, names must be alphanumeric only (5-50 characters). Use `replace()` to remove hyphens: `replace('cr${environmentName}${resourceSuffix}', '-', '')`

> **⚠️ Two-Phase Deployment (Mandatory):** To avoid a circular dependency when scoping the AcrPull role assignment to a Bicep module, use the two-phase pattern below:
> - **Phase 1:** Deploy ACR and Container App with a public placeholder image and **no** `registries` block.
> - **Phase 2:** Deploy the AcrPull role assignment as a **separate module** using outputs from Phase 1.
>
> The Bicep template does **not** need a `registries` block. `azd deploy` handles the registry/identity link by calling `az containerapp registry set --server <acr-server> --identity system` via the Azure API before updating the container image. If you are not using AZD, you must run this command manually before switching the image to an ACR-hosted image; otherwise the app will hit image pull failures.

## Phase 1: Container App Module (No Registry Link)

```bicep
// Placeholder image allows provisioning before app image exists in ACR.
// No registries block in Bicep — azd deploy configures the registry/identity link
// (az containerapp registry set --identity system) and updates the image via the Azure API.
// If not using AZD, run that command manually before switching to an ACR-hosted image.
param containerImageName string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        transport: 'auto'
      }
      // No registries block in Bicep. azd deploy sets the registry/identity link via
      // 'az containerapp registry set --identity system' before pushing the real image.
      // Without this step (or its manual equivalent), the app will fail to pull from ACR.
    }
    template: {
      containers: [
        {
          name: serviceName
          image: containerImageName
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
    }
  }
}

output systemAssignedMIPrincipalId string = containerApp.identity.principalId
```

## Phase 2: AcrPull Role Assignment Module (acr-pull-role.bicep)

Place this in a **separate module file** so neither the ACR module nor the Container App module depends on it, eliminating the circular dependency.

```bicep
// acr-pull-role.bicep
param acrName string
param principalId string

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, principalId, 'acrpull')
  scope: containerRegistry
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '7f951dda-4ed3-4680-a7ca-43fe172d538d'
    )
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}
```

> 💡 **Tip:** Always set `principalType: 'ServicePrincipal'` for managed identities. This avoids a Graph API lookup and speeds up role assignment propagation.

## Wiring Phase 1 and Phase 2 in main.bicep

```bicep
// Phase 1: ACR and Container App — neither module depends on the role assignment
module containerRegistry './modules/container-registry.bicep' = {
  name: 'containerRegistry'
  scope: rg
  params: { /* ... */ }
}

module api './modules/container-app.bicep' = {
  name: 'api'
  scope: rg
  params: {
    containerImageName: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
    // No registries param in Bicep — azd deploy configures the registry/identity link
    // and updates the image via the Azure API after provisioning.
    /* ... */
  }
}

// Phase 2: Role assignment depends on outputs of both Phase 1 modules,
// but neither Phase 1 module depends on this — no circular dependency.
module acrPullRole './modules/acr-pull-role.bicep' = {
  name: 'acrPullRole'
  scope: rg
  params: {
    acrName: containerRegistry.outputs.name
    principalId: api.outputs.systemAssignedMIPrincipalId
  }
}
```

## Container Apps Environment

```bicep
resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: '${resourcePrefix}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
  }
}
```
