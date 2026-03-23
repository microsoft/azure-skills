# Monitoring Resources

| Resource | ARM Type | API Version | CAF Prefix | Naming Scope | Region |
|----------|----------|-------------|------------|--------------|--------|
| Application Insights | `Microsoft.Insights/components` | `2020-02-02` | `appi` | Resource group | Mainstream |
| Log Analytics | `Microsoft.OperationalInsights/workspaces` | `2025-02-01` | `log` | Resource group | Mainstream |

## Documentation

| Resource | Bicep Reference | Service Overview | Naming Rules | Additional |
|----------|----------------|------------------|--------------|------------|
| Application Insights | [2020-02-02](https://learn.microsoft.com/azure/templates/microsoft.insights/components?pivots=deployment-language-bicep) | [App Insights overview](https://learn.microsoft.com/azure/azure-monitor/app/app-insights-overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftinsights) | [Workspace-based](https://learn.microsoft.com/azure/azure-monitor/app/convert-classic-resource) |
| Log Analytics | [2025-02-01](https://learn.microsoft.com/azure/templates/microsoft.operationalinsights/workspaces?pivots=deployment-language-bicep) | [Log Analytics overview](https://learn.microsoft.com/azure/azure-monitor/logs/log-analytics-overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftoperationalinsights) | [Pricing](https://learn.microsoft.com/azure/azure-monitor/logs/cost-logs) |
