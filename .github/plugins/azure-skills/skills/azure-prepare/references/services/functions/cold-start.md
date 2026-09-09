# Azure Functions Cold Start Mitigation

Cold starts occur when a function app must allocate infrastructure, load the runtime, and initialize your code before handling a request. Impact and mitigation options differ significantly by hosting plan.

## Cold Start Behavior by Plan

Cold-start duration depends on the runtime, dependencies, package size, and initialization work. Measure the latency of the deployed app instead of relying on a fixed estimate.

| Plan | Platform behavior | Primary mitigation |
|------|-------------------|--------------------|
| Consumption (Y1) | Scales to zero; cold starts are expected | Reduce dependencies and startup work, or move to another plan |
| Flex Consumption (FC1) | Improved scale-from-zero behavior | Configure always-ready instances per function or trigger group |
| Premium (EP1-EP3) | Keeps app-level always-ready instances and an HTTP prewarmed buffer | Configure the app's always-ready instance count |
| Dedicated | Host runs continuously when `Always On` is enabled | Enable `Always On` |
| Container Apps (Functions-on-ACA) | Scales to zero when `minReplicas` is `0` | Set `minReplicas` to `1` or higher |

## Mitigation Strategies

### Consumption Plan

Consumption has no built-in always-ready setting. Reduce the work required to specialize a new instance:

| Strategy | How | Trade-off |
|----------|-----|-----------|
| Reduce package size | Trim unused dependencies; use tree-shaking/bundling | Development effort |
| Optimize startup code | Lazy-load heavy modules; defer non-critical connections | Code changes required |

> 💡 **Tip:** A timer-based keep-alive isn't a cold-start guarantee and creates extra executions. If cold starts are a consistent problem, move to Flex Consumption or Premium. See [hosting-plans.md](hosting-plans.md) for the comparison.

### Flex Consumption Plan

Configure always-ready instances for a function group with the dedicated CLI command (do not hand-edit the `functionAppConfig` ARM array — indexing into it by position can silently overwrite other always-ready groups):

```bash
# Set 1 always-ready instance for the "http" function group
az functionapp scale config always-ready set \
  -g $RG -n $APP \
  --settings http=1
```

#### Bicep — Always-Ready Configuration

```bicep
resource functionApp 'Microsoft.Web/sites@2024-04-01' = {
  name: appName
  location: location
  kind: 'functionapp,linux'
  properties: {
    serverFarmId: flexPlan.id
    functionAppConfig: {
      runtime: {
        name: 'node'
        version: '<supported-major-version>'
      }
      scaleAndConcurrency: {
        alwaysReady: [
          { name: 'http', instanceCount: 1 }
        ]
        instanceMemoryMB: 2048
        maximumInstanceCount: 100
      }
    }
  }
}
```

> ⚠️ **Warning:** Always-ready instances are billed continuously, separate from and in addition to on-demand instances (they don't count toward `maximumInstanceCount`). Start with 1 instance per group and scale based on observed traffic.

### Premium Plan

Set the app-level always-ready count so this function app stays loaded. The HTTP prewarmed buffer defaults to one instance and usually shouldn't be changed:

```bash
az functionapp update -g $RG -n $APP \
  --set siteConfig.minimumElasticInstanceCount=2
```

If you need to reserve plan capacity ahead of scale-out or change its burst ceiling, configure the plan separately:

```bash
az functionapp plan update -g $RG -n $PLAN --min-instances 2
az functionapp plan update -g $RG -n $PLAN --max-burst 20
```

> `--min-instances` reserves plan capacity. It doesn't replace the app-level `minimumElasticInstanceCount` setting that keeps a specific app always ready. `--min-elastic-worker-count` isn't a valid parameter for `az functionapp plan update`.

### Dedicated Plan

Enable `Always On` so the app is never unloaded due to idle timeout:

```bash
az functionapp config set -g $RG -n $APP --always-on true
```

### Functions on Container Apps

For new deployments, use the native `Microsoft.App/containerApps` integration and set `kind: 'functionapp'`. A generic container app without this kind doesn't enable the Functions integration. The older `Microsoft.Web/sites` integration is legacy and planned for future deprecation.

```bicep
resource functionApp 'Microsoft.App/containerApps@2024-10-02-preview' = {
  name: appName
  location: location
  kind: 'functionapp'
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 80
      }
    }
    template: {
      containers: [
        {
          name: appName
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
      }
    }
  }
}
```

> ⚠️ **Warning:** `minReplicas: 0` allows scale-to-zero; set it to `1` or higher to keep at least one replica running. Configure required Functions settings such as `AzureWebJobsStorage` through secrets or managed identity.

## Language-Specific Optimization

| Language | Cold Start Tip |
|----------|---------------|
| .NET | Use ReadyToRun (or Native AOT where supported) compilation; avoid heavy DI registration in startup |
| Node.js | Minimize `node_modules`; bundle with esbuild/webpack; use the latest LTS version supported by Azure Functions |
| Python | Reduce package count; avoid importing unused modules at the top of the file |
| Java | Prefer the latest supported Java version on Functions v4; minimize static initialization and classpath size |
| PowerShell | Minimize modules declared in `requirements.psd1` |

## Recommendation Summary

| Scenario | Recommended Plan | Cold Start Strategy |
|----------|-----------------|----------------------|
| Cost-sensitive, tolerates latency | Consumption | Small deployment package + minimal startup work |
| Low latency, Linux, bursty | Flex Consumption | 1-2 always-ready instances via `az functionapp scale config always-ready set` |
| Enterprise, strict SLA, Windows or slots needed | Premium | App-level `minimumElasticInstanceCount` + default prewarmed buffer |
| Shared App Service plan, always running | Dedicated | `Always On = true` |
| Containerized Functions | Container Apps (Functions-on-ACA) | `minReplicas` set to `1` or higher on a `Microsoft.App/containerApps` resource with `kind: 'functionapp'` |
