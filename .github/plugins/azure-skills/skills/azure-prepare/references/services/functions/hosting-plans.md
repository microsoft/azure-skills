# Azure Functions Hosting Plans

## Plan Comparison Matrix

| Feature | Consumption (Y1) | Flex Consumption (FC1) | Premium (EP1-EP3) | Dedicated (App Service) | Container Apps |
|---------|:-:|:-:|:-:|:-:|:-:|
| **Max scale-out (instances)** | 200 | 1,000 | Plan-dependent (up to ~100) | Manual, per plan SKU | Up to 1,000 |
| **Per-function scaling** | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Always-ready / min instances** | ❌ | ✅ (always-ready groups) | ✅ (min instances) | ✅ (Always On) | ✅ (min replicas) |
| **Scale to zero** | ✅ | ✅ | ❌ (min 1 instance) | ❌ | ✅ (`minReplicas: 0`) |
| **VNet integration (outbound)** | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Private endpoints (inbound)** | ❌ | ✅ | ✅ | ✅ | ✅ (environment-level) |
| **Deployment slots (incl. production)** | 2 | ❌ Not supported | 3 | 1-20 (tier-dependent) | Via [revisions](https://learn.microsoft.com/azure/container-apps/revisions) |
| **Function timeout — default / max** | 5 min / 10 min | 30 min / unbounded | 30 min / unbounded | 30 min / unbounded (requires Always On) | 30 min / unbounded |
| **OS support** | Windows + Linux | Linux only | Windows + Linux | Windows + Linux | Linux only |

> ⚠️ **"Unbounded" timeout caveat:** Flex Consumption, Premium, Dedicated, and Container Apps allow `functionTimeout` in `host.json` to be set unbounded, but the platform can still recycle a worker: a 60-minute idle timer, up to a 60-minute scale-in grace period, and a 10-minute grace period during platform upgrades. Design long-running work to be resumable (e.g., Durable Functions) rather than relying on a single uninterrupted execution.

## Instance Sizing

| Plan | SKU | vCPU | Memory |
|------|-----|------|--------|
| Consumption | Y1 | Shared/dynamic | 1.5 GB |
| Flex Consumption | FC1 | 0.25 / 1 / 2 (selectable) | 512 MB / 2,048 MB / 4,096 MB (selectable) |
| Premium | EP1 | 1 | 3.5 GB |
| Premium | EP2 | 2 | 7 GB |
| Premium | EP3 | 4 | 14 GB |
| Dedicated | B1/S1 | 1 | 1.75 GB |
| Dedicated | P1v3 | 2 | 8 GB |

> 💡 Flex Consumption instance memory is user-selectable per app (512 MB, 2,048 MB, or 4,096 MB), each mapping to a fixed vCPU allocation. Use 2,048 MB as the default; go smaller for high fan-out/low-per-invocation-cost workloads, larger for CPU- or memory-intensive functions. Each region has a default 250-core (512,000 MB) Flex quota shared across all Flex apps in that subscription/region — request an increase for large-scale deployments.

## Cost Models

| Plan | Pricing Model | Notes |
|------|--------------|-------|
| Consumption | Per-execution + GB-s; free monthly grant | Lowest cost for spiky, low-volume workloads; no charge while idle |
| Flex Consumption | Per-execution + GB-s; optional always-ready instances billed continuously | Scale-to-zero like Consumption, with opt-in always-ready base cost for latency-sensitive paths |
| Premium (EP1) | Per-instance-hour; at least 1 instance always allocated | Fixed minimum cost even at zero traffic (no scale-to-zero) |
| Dedicated (B1) | Per-instance-hour; plan runs continuously | Cost-effective when Functions co-locate with existing App Service Plan capacity |
| Container Apps | Per-vCPU-second + per-GiB-second; can scale to zero | Pay only while replicas run when `minReplicas: 0` |

## Decision Criteria

```
Need per-function scaling, Linux, and fast/large scale-out?
├─ Yes → Flex Consumption
└─ No
   Need VNet integration or private endpoints?
   ├─ No → Consumption (lowest cost, simplest)
   └─ Yes
      Already running other apps on an App Service Plan, or need Windows + slots + long history of App Service features?
      ├─ Yes → Dedicated (App Service Plan)
      └─ No
         Budget-sensitive with bursty traffic?
         ├─ Yes + Linux → Flex Consumption
         ├─ Yes + Windows → Premium (EP1, cheapest always-on with VNet)
         └─ No → Premium (predictable pre-warmed latency, deployment slots)
```

## Plan-Specific Considerations

### Consumption (Y1)

- Best for: low-traffic, event-driven workloads that tolerate occasional cold starts.
- Limits: 10-minute max execution, no VNet integration, no per-function scaling.
- Slots: 2 total (production + 1 staging) on Windows and Linux.

### Flex Consumption (FC1)

- **Recommended default for new Functions apps.** Best for Linux workloads needing fast/large scale-out, VNet, per-function scaling, and configurable instance memory.
- Limits: Linux only, **no deployment slots** (use [rolling/blue-green site update strategies](https://learn.microsoft.com/azure/azure-functions/flex-consumption-site-updates) instead for zero-downtime deploys).
- Always-ready instances bypass the max-instance-count ceiling and are billed continuously — start small and measure.

### Premium (EP1–EP3)

- Best for: latency-sensitive workloads, longer executions, VNet + private endpoints on Windows, or apps needing 3 deployment slots.
- Always allocates at least 1 instance (no scale-to-zero); minimum instance count and maximum burst are both configurable.
- Migrating an existing app between Consumption and Premium **on Windows** is supported in place via CLI/PowerShell (no new app required). This migration path is **not supported on Linux** — Linux apps require a new function app on the target plan.

### Dedicated (App Service Plan)

- Best for: consolidating Functions onto App Service Plan capacity you already run, or workloads needing the broadest App Service feature set (Hybrid Connections, custom domains, `Always On`).
- Slot count depends on the underlying App Service Plan tier (Basic = 1, Standard = 5, Premium = 20; see [App Service limits](https://learn.microsoft.com/azure/azure-resource-manager/management/azure-subscription-service-limits#azure-app-service-limits)).
- No automatic scale-to-zero; the plan runs (and is billed) continuously unless you scale it down manually.

### Container Apps (Functions-on-ACA)

- Best for: teams standardizing on Container Apps/Dapr/microservices, or needing a custom container image for Functions.
- For new deployments, use the native `Microsoft.App/containerApps` integration with `kind: 'functionapp'`. The older `Microsoft.Web/sites` integration is legacy and planned for future deprecation. See [cold-start.md](cold-start.md#functions-on-container-apps) for the current Bicep shape.
- Scale-to-zero via `minReplicas: 0`; revisions replace deployment slots for staged rollout.

## Migration Notes

Switching hosting plans generally requires creating a new function app, **except**: Consumption ↔ Premium migration **on Windows** is supported in place via `az functionapp update` (see [Plan migration](https://learn.microsoft.com/azure/azure-functions/functions-how-to-use-azure-function-app-settings#plan-migration)). All Linux plan changes, and any move to/from Flex Consumption, require redeploying to a new app on the target plan. See `azure-upgrade` skill for Consumption→Flex migration guidance.
