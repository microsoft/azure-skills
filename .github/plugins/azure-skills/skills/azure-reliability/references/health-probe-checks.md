# Health Probe & Monitoring — Platform-Level Checks

## Overview

Health probes enable automated failover and recovery. Without them, load balancers and platform services cannot detect failures automatically.

This file covers **global / platform-level** probe checks (Azure Front Door, Traffic Manager, Application Insights connectivity). For service-specific health-probe checks, configuration commands, and IaC patches, see:

| Service | Reference |
|---|---|
| Azure Functions | [services/functions/reliability.md](services/functions/reliability.md) |

> Azure App Service and Azure Container Apps per-service references are planned but not yet shipped in this skill version.

> **⚠️ Output format:** Use `--query "data[]" -o json` for `az graph query`. Standard `az afd` / `az network traffic-manager` commands work fine with `-o table`.

## Check Front Door Health Probe Configuration

```bash
az afd origin-group list \
  --profile-name <front-door-name> \
  --resource-group <rg> \
  --query "[].{name:name, probePath:healthProbeSettings.probePath, probeProtocol:healthProbeSettings.probeProtocol, intervalSeconds:healthProbeSettings.probeIntervalInSeconds}" -o table
```

**Interpretation:**
- `probePath` empty / null → ❌ No active health probing → no automatic failover
- `probePath = /api/health` (or similar) → ✅ Probe configured

## Check Traffic Manager Endpoint Monitoring

```bash
az graph query -q "
Resources
| where type =~ 'microsoft.network/trafficmanagerprofiles'
| extend monitorPath = tostring(properties.monitorConfig.path)
| extend monitorProtocol = tostring(properties.monitorConfig.protocol)
| extend monitorPort = tostring(properties.monitorConfig.port)
| project name, resourceGroup, monitorProtocol, monitorPort, monitorPath
" --query "data[]" -o json
```

## Check Application Insights Connectivity

App settings are not reliably queryable via Resource Graph. Use Azure CLI directly:

```bash
az webapp config appsettings list \
  --name <app-name> \
  --resource-group <rg> \
  --query "[?contains(name, 'APPINSIGHTS') || contains(name, 'APPLICATIONINSIGHTS')].{name:name}" -o table
```

For Function Apps:
```bash
az functionapp config appsettings list \
  --name <app-name> \
  --resource-group <rg> \
  --query "[?contains(name, 'APPINSIGHTS') || contains(name, 'APPLICATIONINSIGHTS')].{name:name}" -o table
```

## Best Practices for Health Endpoints

These apply across all services:

1. **Keep health endpoints lightweight** — return 200 quickly, no heavy DB/dependency queries on every probe.
2. **Use anonymous auth** — health probes can't pass auth tokens.
3. **Two endpoints, not one** — fast `/health` for the load balancer, optional `/health/deep` for on-call diagnostics.
4. **For Container Apps, both liveness AND readiness** — liveness alone restarts the container without taking it out of rotation.
5. **Test the endpoint** before relying on it: `curl https://<app-url>/api/health`.

## Reporting (for the Multi-Region row)

For the `Multi-region failover` row of the assessment table:
- ✅ — Front Door (or Traffic Manager) exists AND has a non-empty `probePath` / `monitorConfig.path`
- ⚠️ Partial — global load balancer exists but has no health probe configured (manual failover only)
- ❌ — no global load balancer

Per-service `Health probes` row reporting for Azure Functions is documented in [services/functions/reliability.md](services/functions/reliability.md). App Service and Container Apps per-service reporting is planned but not yet available.
