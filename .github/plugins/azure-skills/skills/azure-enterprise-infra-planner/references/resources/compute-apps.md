# Compute (PaaS) Resources

| Resource | ARM Type | API Version | CAF Prefix | Naming Scope | Region |
|----------|----------|-------------|------------|--------------|--------|
| App Service | `Microsoft.Web/sites` | `2024-11-01` | `app` | Global | Mainstream |
| App Service Plan | `Microsoft.Web/serverfarms` | `2024-11-01` | `asp` | Resource group | Mainstream |
| Container App | `Microsoft.App/containerApps` | `2025-01-01` | `ca` | Environment | Strategic |
| Container Apps Environment | `Microsoft.App/managedEnvironments` | `2025-01-01` | `cae` | Resource group | Strategic |
| Container Registry | `Microsoft.ContainerRegistry/registries` | `2025-04-01` | `cr` | Global | Mainstream |
| Function App | `Microsoft.Web/sites` | `2024-11-01` | `func` | Global | Mainstream |
| Static Web App | `Microsoft.Web/staticSites` | `2024-11-01` | `stapp` | Resource group | Mainstream |

## Documentation

| Resource | Bicep Reference | Service Overview | Naming Rules | Additional |
|----------|----------------|------------------|--------------|------------|
| App Service | [2024-11-01](https://learn.microsoft.com/azure/templates/microsoft.web/sites?pivots=deployment-language-bicep) | [App Service overview](https://learn.microsoft.com/azure/app-service/overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftweb) | [Hosting plans](https://learn.microsoft.com/azure/app-service/overview-hosting-plans) |
| App Service Plan | [2024-11-01](https://learn.microsoft.com/azure/templates/microsoft.web/serverfarms?pivots=deployment-language-bicep) | [Plan overview](https://learn.microsoft.com/azure/app-service/overview-hosting-plans) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftweb) | [Pricing](https://azure.microsoft.com/en-us/pricing/details/app-service/linux) |
| Container App | [2025-01-01](https://learn.microsoft.com/azure/templates/microsoft.app/containerapps?pivots=deployment-language-bicep) | [Container Apps overview](https://learn.microsoft.com/azure/container-apps/overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftapp) | [Environments](https://learn.microsoft.com/azure/container-apps/environment) |
| Container Apps Environment | [2025-01-01](https://learn.microsoft.com/azure/templates/microsoft.app/managedenvironments?pivots=deployment-language-bicep) | [Environments overview](https://learn.microsoft.com/azure/container-apps/environment) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftapp) | [Workload profiles](https://learn.microsoft.com/azure/container-apps/workload-profiles-overview) |
| Container Registry | [2025-04-01](https://learn.microsoft.com/azure/templates/microsoft.containerregistry/registries?pivots=deployment-language-bicep) | [ACR overview](https://learn.microsoft.com/azure/container-registry/container-registry-intro) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftcontainerregistry) | [SKU tiers](https://learn.microsoft.com/azure/container-registry/container-registry-skus) |
| Function App | [2024-11-01](https://learn.microsoft.com/azure/templates/microsoft.web/sites?pivots=deployment-language-bicep) | [Functions overview](https://learn.microsoft.com/azure/azure-functions/functions-overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftweb) | [Hosting plans](https://learn.microsoft.com/azure/azure-functions/functions-scale) |
| Static Web App | [2024-11-01](https://learn.microsoft.com/azure/templates/microsoft.web/staticsites?pivots=deployment-language-bicep) | [Static Web Apps overview](https://learn.microsoft.com/azure/static-web-apps/overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftweb) | [Hosting plans](https://learn.microsoft.com/azure/static-web-apps/plans) |
