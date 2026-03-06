// recipes/durable/bicep/durable-task-scheduler.bicep
// Durable Task Scheduler recipe module — adds DTS scheduler, task hub, and RBAC
// to an Azure Functions base template.
//
// USAGE: Add this as a module in your main.bicep:
//   module durableTaskScheduler './app/durable-task-scheduler.bicep' = {
//     name: 'durableTaskScheduler'
//     scope: rg
//     params: {
//       name: name
//       location: location
//       tags: tags
//       functionAppPrincipalId: app.outputs.SERVICE_API_IDENTITY_PRINCIPAL_ID
//       principalId: principalId
//       uamiClientId: apiUserAssignedIdentity.outputs.clientId
//     }
//   }
//
// Then add the connection string app setting to the function app:
//   appSettings: {
//     DURABLE_TASK_SCHEDULER_CONNECTION_STRING: durableTaskScheduler.outputs.connectionString
//   }

targetScope = 'resourceGroup'

@description('Base name for resources')
param name string

@description('Azure region')
param location string = resourceGroup().location

@description('Resource tags')
param tags object = {}

@description('Principal ID of the Function App managed identity (UAMI)')
param functionAppPrincipalId string

@description('Principal ID of the deploying user (for dashboard access). Set via AZURE_PRINCIPAL_ID.')
param principalId string = ''

@description('UAMI client ID from base template identity module - REQUIRED for UAMI auth')
param uamiClientId string

@allowed(['Consumption', 'Dedicated'])
@description('Use Consumption for quickstarts/variable workloads, Dedicated for high-demand/predictable throughput')
param skuName string = 'Consumption'

// ============================================================================
// Naming
// ============================================================================
var resourceSuffix = take(uniqueString(subscription().id, resourceGroup().name, name), 6)
var schedulerName = 'dts-${name}-${resourceSuffix}'

// ============================================================================
// Durable Task Scheduler
// ============================================================================
resource scheduler 'Microsoft.DurableTask/schedulers@2025-11-01' = {
  name: schedulerName
  location: location
  tags: tags
  properties: {
    sku: { name: skuName }
    ipAllowlist: ['0.0.0.0/0'] // Required: empty list denies all traffic
  }
}

// ============================================================================
// Task Hub
// ============================================================================
resource taskHub 'Microsoft.DurableTask/schedulers/taskHubs@2025-11-01' = {
  parent: scheduler
  name: 'default'
}

// ============================================================================
// RBAC — Durable Task Data Contributor for Function App
// ============================================================================
var durableTaskDataContributorRoleId = '0ad04412-c4d5-4796-b79c-f76d14c8d402'

resource functionAppRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(scheduler.id, functionAppPrincipalId, durableTaskDataContributorRoleId)
  scope: scheduler
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', durableTaskDataContributorRoleId)
    principalId: functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ============================================================================
// RBAC — Dashboard Access for Deploying User
// ============================================================================
resource dashboardRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(scheduler.id, principalId, durableTaskDataContributorRoleId)
  scope: scheduler
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', durableTaskDataContributorRoleId)
    principalId: principalId
    principalType: 'User'
  }
}

// ============================================================================
// Outputs
// ============================================================================
output schedulerName string = scheduler.name
output schedulerEndpoint string = scheduler.properties.endpoint
output taskHubName string = taskHub.name
output connectionString string = 'Endpoint=${scheduler.properties.endpoint};Authentication=ManagedIdentity;ClientID=${uamiClientId};TaskHub=${taskHub.name}'

// ============================================================================
// APP SETTINGS OUTPUT - Use this to ensure correct UAMI configuration
// ============================================================================
output appSettings object = {
  DURABLE_TASK_SCHEDULER_CONNECTION_STRING: 'Endpoint=${scheduler.properties.endpoint};Authentication=ManagedIdentity;ClientID=${uamiClientId};TaskHub=${taskHub.name}'
}
