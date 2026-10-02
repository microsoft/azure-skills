# Compute (PaaS) Pairing Constraints

### App Service

| Paired With | Constraint |
|-------------|------------|
| **App Service Plan** | Must be in the same region. Linux apps need Linux plan (`reserved: true`). Windows apps need Windows plan. |
| **Deployment Slots** | Only available on Standard or higher plan tiers. Free and Basic do not support slots. |
| **VNet Integration** | Requires Basic or higher plan tier. Subnet must be delegated to `Microsoft.Web/serverFarms`. VNet integration subnet must be a different subnet than any Private Endpoint subnet. |
| **Private Endpoints** | Requires Basic or higher plan tier. Not available on Free or Shared tiers. |
| **Custom Domain** | Requires Shared (D1) or higher tier for custom domains. Free tier only supports `*.azurewebsites.net`. Managed certificates require Basic or higher. |
| **Application Insights** | Set `APPLICATIONINSIGHTS_CONNECTION_STRING` in app settings. |
| **Key Vault References** | Use `@Microsoft.KeyVault(SecretUri=...)` in app settings. Requires managed identity with Key Vault access. |
| **Managed Identity** | Enable `identity.type: 'SystemAssigned'` or `'UserAssigned'` for passwordless auth to other Azure resources. |

### App Service Plan

| Paired With | Constraint |
|-------------|------------|
| **Function App** | Consumption (`Y1`) and Flex (`FC1`) plans cannot be shared with web apps. EP plans can host both functions and web apps. |
| **Linux Apps** | Linux plan (`reserved: true`) cannot host Windows apps and vice versa. |
| **Zone Redundancy** | Requires Premium v3 (`P1v3`+) or Isolated v2. Minimum 3 instances. |
| **Deployment Slots** | Slots share plan capacity. Standard+ tier required. Slots are not available on Free/Basic. |
| **Auto-scale** | Not available on Free/Shared/Basic. Standard+ required for manual scale, auto-scale. |
| **VNet Integration** | Requires Basic or higher. Subnet must be delegated to `Microsoft.Web/serverFarms`. Minimum subnet size /28 (or /26 for multi-plan subnet join). VNet integration subnet must be a different subnet than any Private Endpoint subnet. |
| **Private Endpoints** | Requires Basic tier or higher. Not available on Free or Shared tiers. |
| **Isolated Compute** | Dedicated single-tenant compute requires IsolatedV2 (`I1v2`+) tier. |
| **Free/Shared Tiers** | Free (`F1`) and Shared (`D1`) use shared compute with no VNet integration, no private endpoints, no deployment slots, no Always On, and no auto-scale. Managed Identity is available but limited. |

### Container App

| Paired With | Constraint |
|-------------|------------|
| **Container Apps Environment** | Must reference `environmentId`. Environment must exist in the same region. |
| **VNet** | VNet integration is configured on the **Environment**, not the individual app. Environment needs a dedicated subnet with minimum /23 prefix for Consumption-only environments or /27 for workload profiles environments. |
| **Container Registry** | Requires registry credentials in `configuration.registries[]` or managed identity-based pull. |
| **Dapr** | Enable via `configuration.dapr.enabled: true`. Dapr components are configured on the Environment. |
| **CPU/Memory** | CPU and memory must follow valid combinations: 0.25 cores/0.5Gi, 0.5/1Gi, 1/2Gi, 2/4Gi, 4/8Gi (consumption). |
| **Scale Rules** | KEDA-based scale rules reference secrets by name — secrets must be defined in `configuration.secrets[]`. |

### Container Apps Environment

| Paired With | Constraint |
|-------------|------------|
| **Container App** | Container Apps reference the environment via `properties.environmentId`. Apps and environment must be in the same region. |
| **Log Analytics Workspace** | Provide `customerId` and `sharedKey` in `appLogsConfiguration`. Workspace must exist before the environment. |
| **VNet / Subnet** | Subnet must have a minimum /23 prefix for Consumption-only environments or /27 for workload profiles environments. Subnet must be dedicated to the Container Apps Environment (no other resources). Workload Profiles: subnet must be delegated to `Microsoft.App/environments`. Consumption-only: subnet MUST NOT be delegated to any service. |
| **Zone Redundancy** | Requires VNet integration. Zone-redundant environments need a /23 subnet in a region with availability zones. |
| **Internal Environment** | When `internal: true`, no public endpoint is created. Requires custom DNS or Private DNS Zone and a VNet with connectivity to clients. |
| **Workload Profiles** | At least one `Consumption` profile must be defined when using workload profiles. Dedicated profiles require `minimumCount` and `maximumCount`. |
| **Workload Profiles vs Consumption-only** | UDR support, NAT Gateway egress, private endpoints, and remote gateway peering are only available with Workload Profiles environments — not Consumption-only. |
| **Network Immutability** | Network type (Workload Profiles vs Consumption-only) is immutable after creation. Cannot change between environment types. |
| **IPv6** | IPv6 is not supported for either Workload Profiles or Consumption-only environments. |
| **VNet Move** | VNet-integrated environments cannot be moved to a different resource group or subscription while in use. |

### Container Registry

| Paired With | Constraint |
|-------------|------------|
| **AKS** | AKS needs `acrPull` role assignment on the registry. Use managed identity (attach via `az aks update --attach-acr`). |
| **Container App** | Reference in `configuration.registries[]`. Use managed identity or admin credentials. |
| **ML Workspace** | Referenced as `containerRegistry` property. Used for custom training/inference images. |
| **Private Endpoint** | Premium SKU required. Set `publicNetworkAccess: 'Disabled'`. |
| **Geo-Replication** | Premium SKU required. Configure via child `replications` resource. |
| **CMK** | Premium SKU required. Needs user-assigned identity with Key Vault access. |

### Function App

| Paired With | Constraint |
|-------------|------------|
| **Storage Account** | Must use `StorageV2` or `Storage` kind. `BlobStorage`, `BlockBlobStorage`, `FileStorage` not supported (need Queue + Table). |
| **Storage (Consumption)** | Consumption plan cannot use VNet-secured storage. Only Premium/Dedicated support VNet-restricted storage. |
| **Storage (ZRS)** | Zone-redundant functions require `Standard_ZRS` storage SKU. |
| **App Service Plan** | Plan must be in the same region. Linux functions need Linux plan (`reserved: true`). |
| **VNet Integration** | Requires Premium (EP) or Dedicated plan. Consumption does not support VNet integration (use Flex Consumption). |
| **Application Insights** | Set `APPINSIGHTS_INSTRUMENTATIONKEY` or `APPLICATIONINSIGHTS_CONNECTION_STRING` in app settings. |
| **Key Vault References** | App settings can use `@Microsoft.KeyVault(SecretUri=...)` syntax. Requires managed identity with Key Vault access. |

### Static Web App

| Paired With | Constraint |
|-------------|------------|
| **GitHub Repository** | Provide `repositoryUrl`, `branch`, and `repositoryToken`. A GitHub Actions workflow is auto-created in the repo. |
| **Azure DevOps** | Set `provider: 'DevOps'`. Provide `repositoryUrl` and `branch`. Pipeline is configured separately. |
| **Azure Functions (managed)** | API location in `buildProperties.apiLocation` deploys a managed Functions backend. Limited to HTTP triggers, C#, JavaScript, Python, Java. |
| **Linked Backend** | Use `linkedBackends` child resource to connect an existing Function App, Container App, or App Service as the API backend. Standard SKU required. |
| **Private Endpoint** | Only available with `Standard` SKU. Set up a Private Endpoint to restrict access to the static web app. |
| **Custom Domain** | Custom domains are child resources. Require DNS CNAME or TXT validation. Free SSL certificates are auto-provisioned. |
| **Enterprise-Grade CDN** | `Standard` SKU only. Enables Azure Front Door integration for advanced caching and edge capabilities. |
