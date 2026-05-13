# Configure Multi-Region — Active-Passive with Azure Front Door

## When to Use

Use this reference when:
- Core single-region reliability is already in place (zone redundant compute, ZRS storage, health probes) and the user wants to go further
- User explicitly asks for "multi-region", "global reliability", or "region failover"
- User wants protection against a full Azure region outage

## Prerequisites

Before enabling multi-region:
1. App must already be zone-redundant in the primary region with ZRS/GZRS storage and health probes configured
2. App should have a health endpoint (`/api/health` or similar)
3. User must choose a secondary region (suggest paired region)

## Workflow

### Step 1: Gather Information

Ask the user:
```
To set up multi-region active-passive failover, I need:

1. Secondary region — Where should the standby deployment go?
   Suggested: [paired region for primary] (e.g., eastus2 → centralus, westus2 → westus3)

2. Pattern — Active-Passive (recommended, lower cost) or Active-Active?

3. Health endpoint — What path should Front Door probe?
   Default: /api/health
```

### Step 2: Choose Path (CLI vs IaC)

Same dual-path as zone redundancy:
- **Path A (Fix now):** Deploy secondary resources via CLI + create Front Door
- **Path B (Patch IaC):** Add secondary region module + Front Door to Bicep/Terraform

**Recommend Path B** for multi-region — it's complex enough that IaC is essential for maintainability.

### Step 3: What Gets Created

| Resource | Primary Region | Secondary Region |
|----------|---------------|-----------------|
| Resource Group | Existing | New (same name + `-secondary`) |
| App Service Plan | Existing (ZR) | New (ZR, same SKU) |
| Function App / Web App | Existing | New (same code, same config) |
| Storage Account | Existing (ZRS) | New (ZRS) |
| Event Hubs / other deps | Existing | Depends on service (some are global) |
| Azure Front Door | Global (new) | — |
| Managed Identity | Existing | New |

---

## Bicep: Full Multi-Region Module

### Add to `infra/main.bicep`:

```bicep
// ===== MULTI-REGION RELIABILITY =====

@description('Enable multi-region active-passive deployment')
param multiRegionEnabled bool = false

@description('Secondary region for failover deployment')
param secondaryLocation string = 'centralus'

@description('Health check path for Front Door probes')
param healthCheckPath string = '/api/health'

var secondaryResourceToken = toLower(uniqueString(subscription().id, environmentName, secondaryLocation))

// Secondary resource group
resource rgSecondary 'Microsoft.Resources/resourceGroups@2021-04-01' = if (multiRegionEnabled) {
  name: '${rg.name}-secondary'
  location: secondaryLocation
  tags: tags
}

// Secondary storage account
module storageSecondary 'br/public:avm/res/storage/storage-account:0.13.2' = if (multiRegionEnabled) {
  name: 'storage-secondary'
  scope: rgSecondary
  params: {
    name: 'st${secondaryResourceToken}'
    location: secondaryLocation
    tags: tags
    kind: 'StorageV2'
    skuName: 'Standard_ZRS'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    blobServices: {
      containers: [
        {
          name: deploymentStorageContainerName
        }
      ]
    }
  }
}

// Secondary managed identity
module apiUserAssignedIdentitySecondary 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.1' = if (multiRegionEnabled) {
  name: 'apiUserAssignedIdentity-secondary'
  scope: rgSecondary
  params: {
    name: '${abbrs.managedIdentityUserAssignedIdentities}api-${secondaryResourceToken}'
    location: secondaryLocation
    tags: tags
  }
}

// Secondary App Service Plan (zone redundant)
module appServicePlanSecondary 'br/public:avm/res/web/serverfarm:0.5.0' = if (multiRegionEnabled) {
  name: 'appserviceplan-secondary'
  scope: rgSecondary
  params: {
    name: '${abbrs.webServerFarms}${secondaryResourceToken}'
    location: secondaryLocation
    tags: tags
    skuName: 'FC1'
    reserved: true
    zoneRedundant: true
  }
}

// Secondary Function App
module apiSecondary './app/api.bicep' = if (multiRegionEnabled) {
  name: 'api-secondary'
  scope: rgSecondary
  params: {
    name: '${abbrs.webSitesFunctions}api-${secondaryResourceToken}'
    location: secondaryLocation
    tags: tags
    applicationInsightsName: monitoring.outputs.name
    appServicePlanId: appServicePlanSecondary.outputs.resourceId
    runtimeName: 'node'
    runtimeVersion: '22'
    storageAccountName: storageSecondary.outputs.name
    enableBlob: true
    enableQueue: false
    enableTable: true
    deploymentStorageContainerName: deploymentStorageContainerName
    identityId: apiUserAssignedIdentitySecondary.outputs.resourceId
    identityClientId: apiUserAssignedIdentitySecondary.outputs.clientId
    virtualNetworkSubnetId: ''
    eventHubNamespaceName: eventHubs.outputs.eventHubNamespaceName
    inputEventHubName: 'input-events'
    outputEventHubName: 'output-events'
    appSettings: []
  }
}

// Azure Front Door for global load balancing
module frontDoor './app/front-door.bicep' = if (multiRegionEnabled) {
  name: 'front-door'
  scope: rg
  params: {
    name: 'afd-${resourceToken}'
    tags: tags
    primaryAppHostName: '${api.outputs.SERVICE_API_NAME}.azurewebsites.net'
    secondaryAppHostName: multiRegionEnabled ? '${abbrs.webSitesFunctions}api-${secondaryResourceToken}.azurewebsites.net' : ''
    healthCheckPath: healthCheckPath
  }
}

// Outputs for multi-region
output FRONT_DOOR_ENDPOINT string = multiRegionEnabled ? frontDoor.outputs.endpoint : ''
output SECONDARY_REGION string = multiRegionEnabled ? secondaryLocation : ''
output SECONDARY_FUNCTION_APP string = multiRegionEnabled ? '${abbrs.webSitesFunctions}api-${secondaryResourceToken}' : ''
```

### Create `infra/app/front-door.bicep`:

```bicep
@description('Name of the Front Door profile')
param name string

@description('Tags for the resource')
param tags object = {}

@description('Primary app hostname')
param primaryAppHostName string

@description('Secondary app hostname')
param secondaryAppHostName string

@description('Health check path')
param healthCheckPath string = '/api/health'

resource frontDoor 'Microsoft.Cdn/profiles@2024-02-01' = {
  name: name
  location: 'global'
  tags: tags
  sku: {
    name: 'Standard_AzureFrontDoor'
  }
}

resource endpoint 'Microsoft.Cdn/profiles/afdEndpoints@2024-02-01' = {
  parent: frontDoor
  name: '${name}-endpoint'
  location: 'global'
  properties: {
    enabledState: 'Enabled'
  }
}

resource originGroup 'Microsoft.Cdn/profiles/originGroups@2024-02-01' = {
  parent: frontDoor
  name: 'app-origins'
  properties: {
    healthProbeSettings: {
      probePath: healthCheckPath
      probeProtocol: 'Https'
      probeRequestType: 'GET'
      probeIntervalInSeconds: 30
    }
    loadBalancingSettings: {
      sampleSize: 4
      successfulSamplesRequired: 3
      additionalLatencyInMilliseconds: 50
    }
  }
}

resource primaryOrigin 'Microsoft.Cdn/profiles/originGroups/origins@2024-02-01' = {
  parent: originGroup
  name: 'primary'
  properties: {
    hostName: primaryAppHostName
    originHostHeader: primaryAppHostName
    priority: 1
    weight: 1000
    httpPort: 80
    httpsPort: 443
    enabledState: 'Enabled'
  }
}

resource secondaryOrigin 'Microsoft.Cdn/profiles/originGroups/origins@2024-02-01' = {
  parent: originGroup
  name: 'secondary'
  properties: {
    hostName: secondaryAppHostName
    originHostHeader: secondaryAppHostName
    priority: 2
    weight: 1000
    httpPort: 80
    httpsPort: 443
    enabledState: 'Enabled'
  }
}

resource route 'Microsoft.Cdn/profiles/afdEndpoints/routes@2024-02-01' = {
  parent: endpoint
  name: 'default-route'
  properties: {
    originGroup: {
      id: originGroup.id
    }
    supportedProtocols: [
      'Http'
      'Https'
    ]
    patternsToMatch: [
      '/*'
    ]
    forwardingProtocol: 'HttpsOnly'
    httpsRedirect: 'Enabled'
    linkToDefaultDomain: 'Enabled'
  }
}

output endpoint string = 'https://${endpoint.properties.hostName}'
output frontDoorId string = frontDoor.id
```

---

## Terraform: Multi-Region Module

### Add to `infra/main.tf`:

```hcl
variable "multi_region_enabled" {
  description = "Enable multi-region active-passive deployment"
  type        = bool
  default     = false
}

variable "secondary_location" {
  description = "Secondary region for failover"
  type        = string
  default     = "centralus"
}

variable "health_check_path" {
  description = "Health check path for Front Door probes"
  type        = string
  default     = "/api/health"
}

# Secondary resource group
resource "azurerm_resource_group" "secondary" {
  count    = var.multi_region_enabled ? 1 : 0
  name     = "${azurerm_resource_group.rg.name}-secondary"
  location = var.secondary_location
  tags     = local.tags
}

# Secondary storage account
resource "azurerm_storage_account" "secondary" {
  count                    = var.multi_region_enabled ? 1 : 0
  name                     = "st${random_string.secondary_token.result}"
  resource_group_name      = azurerm_resource_group.secondary[0].name
  location                 = var.secondary_location
  account_tier             = "Standard"
  account_replication_type = "ZRS"
  tags                     = local.tags
}

# Secondary App Service Plan (zone redundant)
resource "azurerm_service_plan" "secondary" {
  count                  = var.multi_region_enabled ? 1 : 0
  name                   = "plan-${random_string.secondary_token.result}"
  location               = var.secondary_location
  resource_group_name    = azurerm_resource_group.secondary[0].name
  os_type                = "Linux"
  sku_name               = "FC1"
  zone_balancing_enabled = true
  tags                   = local.tags
}

# Secondary Function App
resource "azurerm_linux_function_app" "secondary" {
  count               = var.multi_region_enabled ? 1 : 0
  name                = "func-api-${random_string.secondary_token.result}"
  location            = var.secondary_location
  resource_group_name = azurerm_resource_group.secondary[0].name
  service_plan_id     = azurerm_service_plan.secondary[0].id
  storage_account_name = azurerm_storage_account.secondary[0].name
  tags                = local.tags

  site_config {
    application_stack {
      node_version = "22"
    }
  }
}

# Azure Front Door
resource "azurerm_cdn_frontdoor_profile" "main" {
  count               = var.multi_region_enabled ? 1 : 0
  name                = "afd-${random_string.token.result}"
  resource_group_name = azurerm_resource_group.rg.name
  sku_name            = "Standard_AzureFrontDoor"
  tags                = local.tags
}

resource "azurerm_cdn_frontdoor_endpoint" "main" {
  count                    = var.multi_region_enabled ? 1 : 0
  name                     = "afd-${random_string.token.result}-endpoint"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main[0].id
}

resource "azurerm_cdn_frontdoor_origin_group" "main" {
  count                    = var.multi_region_enabled ? 1 : 0
  name                     = "app-origins"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main[0].id

  health_probe {
    path                = var.health_check_path
    protocol            = "Https"
    request_type        = "GET"
    interval_in_seconds = 30
  }

  load_balancing {
    sample_size                 = 4
    successful_samples_required = 3
    additional_latency_in_milliseconds = 50
  }
}

resource "azurerm_cdn_frontdoor_origin" "primary" {
  count                          = var.multi_region_enabled ? 1 : 0
  name                           = "primary"
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.main[0].id
  host_name                      = "${azurerm_linux_function_app.main.default_hostname}"
  origin_host_header             = "${azurerm_linux_function_app.main.default_hostname}"
  priority                       = 1
  weight                         = 1000
  https_port                     = 443
  enabled                        = true
}

resource "azurerm_cdn_frontdoor_origin" "secondary" {
  count                          = var.multi_region_enabled ? 1 : 0
  name                           = "secondary"
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.main[0].id
  host_name                      = "${azurerm_linux_function_app.secondary[0].default_hostname}"
  origin_host_header             = "${azurerm_linux_function_app.secondary[0].default_hostname}"
  priority                       = 2
  weight                         = 1000
  https_port                     = 443
  enabled                        = true
}

resource "azurerm_cdn_frontdoor_route" "main" {
  count                          = var.multi_region_enabled ? 1 : 0
  name                           = "default-route"
  cdn_frontdoor_endpoint_id      = azurerm_cdn_frontdoor_endpoint.main[0].id
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.main[0].id
  cdn_frontdoor_origin_ids       = [
    azurerm_cdn_frontdoor_origin.primary[0].id,
    azurerm_cdn_frontdoor_origin.secondary[0].id
  ]
  supported_protocols            = ["Http", "Https"]
  patterns_to_match              = ["/*"]
  forwarding_protocol            = "HttpsOnly"
  https_redirect_enabled         = true
  link_to_default_domain         = true
}
```

---

## CLI: Quick Setup (Path A)

For users who want to deploy multi-region without IaC:

```bash
# Variables
PRIMARY_RG="rg-reliability-test"
SECONDARY_LOCATION="centralus"
SECONDARY_RG="${PRIMARY_RG}-secondary"
PRIMARY_APP="func-api-32mpw2gtw7lye"
RESOURCE_TOKEN=$(openssl rand -hex 6)
SECONDARY_APP="func-api-${RESOURCE_TOKEN}"
FRONT_DOOR_NAME="afd-${RESOURCE_TOKEN}"

# Step 1: Create secondary RG
az group create --name $SECONDARY_RG --location $SECONDARY_LOCATION

# Step 2: Create secondary storage (ZRS)
az storage account create \
  --name "st${RESOURCE_TOKEN}" \
  --resource-group $SECONDARY_RG \
  --location $SECONDARY_LOCATION \
  --sku Standard_ZRS \
  --kind StorageV2

# Step 3: Create secondary plan (zone redundant)
az functionapp plan create \
  --name "plan-${RESOURCE_TOKEN}" \
  --resource-group $SECONDARY_RG \
  --location $SECONDARY_LOCATION \
  --sku FC1 \
  --is-linux true

# Step 4: Create secondary function app
az functionapp create \
  --name $SECONDARY_APP \
  --resource-group $SECONDARY_RG \
  --plan "plan-${RESOURCE_TOKEN}" \
  --storage-account "st${RESOURCE_TOKEN}" \
  --runtime node \
  --runtime-version 22 \
  --functions-version 4

# Step 5: Deploy code to secondary (same zip as primary)
# az functionapp deployment source config-zip ...

# Step 6: Create Front Door
az afd profile create \
  --profile-name $FRONT_DOOR_NAME \
  --resource-group $PRIMARY_RG \
  --sku Standard_AzureFrontDoor

# Step 7: Create endpoint
az afd endpoint create \
  --endpoint-name "${FRONT_DOOR_NAME}-endpoint" \
  --profile-name $FRONT_DOOR_NAME \
  --resource-group $PRIMARY_RG

# Step 8: Create origin group with health probe
az afd origin-group create \
  --origin-group-name "app-origins" \
  --profile-name $FRONT_DOOR_NAME \
  --resource-group $PRIMARY_RG \
  --probe-path "/api/health" \
  --probe-protocol Https \
  --probe-request-type GET \
  --probe-interval-in-seconds 30 \
  --sample-size 4 \
  --successful-samples-required 3 \
  --additional-latency-in-milliseconds 50

# Step 9: Add primary origin (priority 1)
az afd origin create \
  --origin-name "primary" \
  --origin-group-name "app-origins" \
  --profile-name $FRONT_DOOR_NAME \
  --resource-group $PRIMARY_RG \
  --host-name "${PRIMARY_APP}.azurewebsites.net" \
  --origin-host-header "${PRIMARY_APP}.azurewebsites.net" \
  --priority 1 \
  --weight 1000 \
  --https-port 443 \
  --enabled-state Enabled

# Step 10: Add secondary origin (priority 2)
az afd origin create \
  --origin-name "secondary" \
  --origin-group-name "app-origins" \
  --profile-name $FRONT_DOOR_NAME \
  --resource-group $PRIMARY_RG \
  --host-name "${SECONDARY_APP}.azurewebsites.net" \
  --origin-host-header "${SECONDARY_APP}.azurewebsites.net" \
  --priority 2 \
  --weight 1000 \
  --https-port 443 \
  --enabled-state Enabled

# Step 11: Create route
az afd route create \
  --route-name "default-route" \
  --endpoint-name "${FRONT_DOOR_NAME}-endpoint" \
  --profile-name $FRONT_DOOR_NAME \
  --resource-group $PRIMARY_RG \
  --origin-group "app-origins" \
  --supported-protocols Http Https \
  --patterns-to-match "/*" \
  --forwarding-protocol HttpsOnly \
  --https-redirect Enabled \
  --link-to-default-domain Enabled
```

---

## Cost Implications

Present this to the user before proceeding:

| Component | Approximate Monthly Cost |
|-----------|-------------------------|
| Secondary Function App (FC1 Flex) | Pay-per-execution only (standby = ~$0 if idle) |
| Secondary Storage (ZRS) | ~$0.02/GB/month (minimal if just app package) |
| Azure Front Door (Standard) | ~$35/month base + $0.01/10K requests |
| **Total additional cost** | **~$35-40/month** for active-passive with idle standby |

> **Note for Flex Consumption:** The secondary app costs near-zero when idle since Flex Consumption is pay-per-execution. This makes active-passive very cost-effective for Functions.

---

## Verification After Setup

After multi-region is configured, verify:

```bash
# Check Front Door endpoint is responding
curl -I https://<front-door-name>-endpoint.z01.azurefd.net/api/health

# Check both origins are healthy
az afd origin-group show \
  --origin-group-name "app-origins" \
  --profile-name $FRONT_DOOR_NAME \
  --resource-group $PRIMARY_RG \
  --query "healthProbeSettings"

# List origins with their health status
az afd origin list \
  --origin-group-name "app-origins" \
  --profile-name $FRONT_DOOR_NAME \
  --resource-group $PRIMARY_RG \
  --query "[].{name:name, hostName:hostName, priority:priority, enabled:enabledState}"
```

---

## Reliability Checklist Impact

After multi-region is configured, the **Multi-Region** column flips to ✅ for:
- Each compute resource that now has a paired deployment in the secondary region
- The Front Door / Traffic Manager profile (with health probes enabled)

---

## Limitations & Gotchas

1. **Event Hubs:** The primary Event Hub namespace is in one region. For true region failover, consider Event Hubs Geo-DR pairing (separate setup).
2. **Code deployment:** Both apps need the same code. If using `azd deploy`, you'll need to deploy to both apps.
3. **App Settings:** Both apps must have matching configuration. Consider using a shared Key Vault for secrets.
4. **Cold start:** Secondary Flex Consumption app may have cold start on failover since it's idle. Consider periodic health pings.
5. **Front Door propagation:** DNS/config changes take 5-10 minutes to propagate globally.
6. **Storage independence:** Each region uses its own storage. Event Hub checkpoints are per-app, so the secondary will process from its own checkpoint on failover.
