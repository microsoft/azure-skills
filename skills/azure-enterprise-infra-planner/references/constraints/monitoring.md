# Monitoring Pairing Constraints

### Application Insights

| Paired With | Constraint |
|-------------|------------|
| **Log Analytics** | Workspace-based App Insights (recommended) requires `WorkspaceResourceId`. Classic (standalone) is being phased out. |
| **Function App** | Set `APPLICATIONINSIGHTS_CONNECTION_STRING` or `APPINSIGHTS_INSTRUMENTATIONKEY` in function app settings. |
| **App Service** | Set `APPLICATIONINSIGHTS_CONNECTION_STRING` in app settings. Enable auto-instrumentation for supported runtimes. |
| **AKS** | Use Container Insights (different from App Insights) for cluster-level monitoring. App Insights used for application-level telemetry. |
| **Private Link** | Use Azure Monitor Private Link Scope (AMPLS) to restrict ingestion/query to private networks. |
| **Retention** | If workspace-based, retention is governed by the Log Analytics workspace. Component-level retention acts as an override. |

### Log Analytics

| Paired With | Constraint |
|-------------|------------|
| **Application Insights** | App Insights `WorkspaceResourceId` must reference this workspace. Both should be in the same region for optimal performance. |
| **AKS (Container Insights)** | AKS `omsagent` addon references workspace via `logAnalyticsWorkspaceResourceID`. |
| **Diagnostic Settings** | Multiple resources can send diagnostics to the same workspace. Configure via `Microsoft.Insights/diagnosticSettings` on each resource. |
| **Retention** | Free tier is limited to 7-day retention. PerGB2018 supports 30–730 days. Archive tier available for longer retention. |
| **Private Link** | Use Azure Monitor Private Link Scope (AMPLS) for private ingestion/query. A workspace can be linked to up to 100 AMPLS resources (a VNet can connect to only one AMPLS). |
