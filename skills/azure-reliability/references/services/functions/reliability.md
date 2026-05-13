# Azure Functions — Reliability Reference

## Supported Plans & Zone Redundancy

| Plan | Zone Redundancy | Min Instances | Health Check |
|------|----------------|---------------|--------------|
| Flex Consumption (FC1) | ✅ `zoneRedundant: true` | Auto-managed | ❌ Platform health check not supported |
| Premium (EP1/EP2/EP3) | ✅ `zoneRedundant: true` + `sku.capacity: 2` | `minimumElasticInstanceCount: 2` per app | ✅ `healthCheckPath` |
| Consumption (Y1) | ❌ Not supported | N/A | ❌ Not supported |
| Dedicated (P1v2+) | ✅ (treated as App Service) | `sku.capacity: 2` | ✅ `healthCheckPath` |

## Assessment Queries

### Zone Redundancy Check
```bash
az graph query -q "
resources
| where resourceGroup =~ '<rg>'
| where type =~ 'microsoft.web/serverfarms'
| where kind contains 'functionapp' or kind =~ 'linux' or kind =~ 'elastic'
| project name, sku=sku.name, zoneRedundant=properties.zoneRedundant, location
" --subscriptions <sub-id>
```

### Function App Instance Count (Premium)
```bash
az functionapp show --name <app> --resource-group <rg> \
  --query "{minInstances:siteConfig.minimumElasticInstanceCount}" -o table
```

## Configure: Zone Redundancy

### Flex Consumption (FC1)
```bash
# Enable zone redundancy on plan
az resource update \
  --resource-group <rg> \
  --name <plan-name> \
  --resource-type "Microsoft.Web/serverfarms" \
  --set properties.zoneRedundant=true
```

### Premium (EP1/EP2/EP3)
```bash
# Enable zone redundancy + set min capacity
az appservice plan update \
  --name <plan-name> \
  --resource-group <rg> \
  --number-of-workers 2

az resource update \
  --resource-group <rg> \
  --name <plan-name> \
  --resource-type "Microsoft.Web/serverfarms" \
  --set properties.zoneRedundant=true

# Set minimum elastic instances per app
az resource update \
  --resource-group <rg> \
  --name <app-name> \
  --resource-type "Microsoft.Web/sites" \
  --set properties.siteConfig.minimumElasticInstanceCount=2
```

### Consumption (Y1) — upgrade path required

Consumption (Y1) plans do **not** support zone redundancy. The user must upgrade the plan first:

- **Recommended:** Upgrade to **Flex Consumption** — similar serverless model, supports ZR, no per-app minimum cost.
- **Alternative:** Upgrade to **Premium (EP1+)** — more control, higher base cost (always-ready instances charged 24/7).

⚠️ Inform the user of cost implications **before** initiating any plan change.

## Configure: Health Endpoint

Flex Consumption does NOT support platform health check (`healthCheckPath`). Instead, add an HTTP endpoint in code:

### TypeScript (v4 programming model)
```typescript
import { app } from "@azure/functions";

app.http('health', {
  methods: ['GET'],
  authLevel: 'anonymous',
  route: 'health',
  handler: async () => ({ status: 200, body: 'OK' })
});
```

### Python (v2 programming model)
```python
import azure.functions as func

app = func.FunctionApp()

@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("OK", status_code=200)
```

### C# (isolated worker)
```csharp
[Function("Health")]
public IActionResult Health([HttpTrigger(AuthorizationLevel.Anonymous, "get", Route = "health")] HttpRequest req)
{
    return new OkObjectResult("OK");
}
```

### Premium Functions — Platform Health Check
```bash
az webapp config set \
  --name <app-name> \
  --resource-group <rg> \
  --generic-configurations '{"healthCheckPath": "/api/health"}'
```

⚠️ Enabling health check causes an app restart.

## IaC Patching: Bicep

### App Service Plan (AVM module)
```bicep
module appServicePlan 'br/public:avm/res/web/serverfarm:0.5.0' = {
  params: {
    skuName: 'FC1'
    reserved: true
    zoneRedundant: true  // ← ADD
  }
}
```

### Premium Plan — extra settings
```bicep
module appServicePlan 'br/public:avm/res/web/serverfarm:0.5.0' = {
  params: {
    skuName: 'EP1'
    reserved: true
    zoneRedundant: true      // ← ADD
    skuCapacity: 2           // ← ADD (min 2 for ZR)
  }
}

// On the function app resource:
resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  properties: {
    siteConfig: {
      minimumElasticInstanceCount: 2  // ← ADD
    }
  }
}
```

## IaC Patching: Terraform

```hcl
resource "azurerm_service_plan" "plan" {
  sku_name               = "FC1"
  os_type                = "Linux"
  zone_balancing_enabled = true  # ← ADD
}

# Premium plan:
resource "azurerm_service_plan" "plan" {
  sku_name               = "EP1"
  os_type                = "Linux"
  zone_balancing_enabled = true  # ← ADD
  worker_count           = 2     # ← ADD
}

resource "azurerm_linux_function_app" "func" {
  site_config {
    minimum_elastic_instance_count = 2  # ← ADD (Premium only)
  }
}
```

## Multi-Region Notes

- Flex Consumption standby costs ~$0 (pay-per-execution) — ideal for active-passive
- Code must be deployed to both regions separately
- Event Hub checkpoints are per-app — secondary starts from its own checkpoint on failover
- Consider Event Hubs Geo-DR for true event replication

## Reporting (for the assessment table)

When the parent skill builds the feature-pivoted assessment table, report each Functions resource on the relevant rows:

| Feature row | What to report |
|---|---|
| Zone redundancy — compute | `🟢 ON` if the **plan** has `zoneRedundant: true`. For Premium plans, also requires `sku.capacity ≥ 2` AND each Function App has `minimumElasticInstanceCount ≥ 2`. `🔴 OFF` if the plan tier doesn't support ZR (Consumption Y1) — annotate `(needs plan upgrade to Flex / Premium)`. |
| Health probes | For Premium / Dedicated: `🟢 ON` if `siteConfig.healthCheckPath` is set, `🔴 OFF` otherwise. For Flex Consumption (FC1) / Consumption (Y1): always annotate `🔴 OFF (code-only fix)` — `healthCheckPath` is not supported on these plans, so an HTTP-triggered `/api/health` function must be added in app code (gated by user consent — see [configure-health-probes.md](../../configure-health-probes.md)). |
| Multi-region failover | `🟢 ON` if the same Function App is deployed in ≥2 regions behind Front Door / Traffic Manager; otherwise `🔴 OFF`. |

## Additional References

- [Reliability in Azure Functions (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/reliability/reliability-functions)
