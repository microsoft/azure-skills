# Google App Engine to Azure App Service Migration

Detailed guidance for migrating Google App Engine applications to Azure App Service.

## Service Mapping

| GCP Service | Azure Equivalent |
|-------------|------------------|
| App Engine (Standard) | Azure App Service (Standard/Premium plan) |
| App Engine (Flex) | Azure App Service (Premium v3) or Container Apps |
| App Engine Services | App Service apps (one per service) |
| `app.yaml` | `azure.yaml` + Bicep |
| Datastore / Firestore | Azure Cosmos DB |
| Cloud SQL (PostgreSQL) | Azure Database for PostgreSQL Flexible Server |
| Cloud SQL (MySQL) | Azure Database for MySQL Flexible Server |
| Cloud Storage | Azure Blob Storage |
| Cloud Tasks | Azure Service Bus / Durable Functions |
| Cloud Pub/Sub | Azure Service Bus / Event Grid |
| Memcache / Memorystore | Azure Cache for Redis |
| Cloud Scheduler | Azure Functions Timer trigger |
| Cloud CDN | Azure Front Door / Azure CDN |
| Cloud DNS | Azure DNS |
| Cloud Logging | Application Insights / Azure Monitor |
| Cloud Monitoring | Azure Monitor Metrics |
| Cloud Trace | Application Insights (distributed tracing) |
| Cloud IAM | Managed Identity + Azure RBAC |
| Cloud Build | GitHub Actions / Azure DevOps |
| Traffic Splitting | Deployment Slots (weighted routing) |
| Service Versions | Deployment Slots |
| Cloud KMS | Azure Key Vault |
| Secret Manager | Azure Key Vault |
| Cloud Endpoints | Azure API Management |
| Identity-Aware Proxy | Azure Front Door + Entra ID auth |
| VPC Connector | VNet Integration |

## Standard vs Flex → App Service Plan Mapping

| App Engine Tier | App Service Equivalent | Notes |
|-----------------|------------------------|-------|
| Standard (F1 instance) | Free (F1) | Dev/test only |
| Standard (B1/B2) | Basic (B1/B2) | Low-traffic apps |
| Standard (auto-scaling) | Standard (S1-S3) | Auto-scale, slots |
| Flex (custom runtime) | Premium v3 (P1v3-P3v3) | Custom containers |
| Flex (high-memory) | Premium v3 (P3v3) | Up to 32 GB RAM |

## `app.yaml` → `azure.yaml` + Bicep

### App Engine Configuration Mapping

| `app.yaml` Field | Azure Equivalent | Implementation |
|-------------------|------------------|----------------|
| `runtime: python314` | Runtime stack: Python 3.14 | Bicep `siteConfig.linuxFxVersion` |
| `instance_class: F2` | App Service Plan SKU | Bicep `sku.name` |
| `automatic_scaling` | Autoscale settings | Bicep `Microsoft.Insights/autoscalesettings` |
| `env_variables` | App Settings | Bicep `siteConfig.appSettings` |
| `handlers` (URL routing) | App Service path mappings / Front Door | Route rules |
| `entrypoint` | Startup command | `az webapp config set --startup-file` |
| `vpc_access_connector` | VNet Integration | Bicep `virtualNetworkSubnetId` |
| `inbound_services: [warmup]` | Always On | Bicep `siteConfig.alwaysOn: true` |

### Example: `app.yaml` → Bicep

```yaml
# app.yaml (GCP)
runtime: python312
instance_class: F2
automatic_scaling:
  min_instances: 1
  max_instances: 10
env_variables:
  DATABASE_URL: "postgres://..."
```

```bicep
// Bicep equivalent
resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  sku: { name: 'S2', capacity: 1 }
  properties: { reserved: true }
}

resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  properties: {
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.14'
      alwaysOn: true
      appSettings: [
        { name: 'PGHOST', value: postgresServer.properties.fullyQualifiedDomainName }
      ]
    }
  }
}
```

## Datastore / Firestore → Cosmos DB

| Datastore Feature | Cosmos DB Equivalent |
|-------------------|----------------------|
| Entity / Document | Item |
| Kind / Collection | Container |
| Namespace | Database |
| Key / ID | Partition key + ID |
| Ancestor queries | Hierarchical partition keys |
| Eventual consistency | Session or Eventual consistency |
| Strong consistency | Strong consistency |
| `ndb` / `google.cloud.datastore` | `@azure/cosmos` SDK |

> 💡 **Tip:** Use Cosmos DB for NoSQL API for the closest mapping from Datastore. Use Cosmos DB for MongoDB API if the app already uses MongoDB-compatible patterns.

## Cloud Tasks → Service Bus / Durable Functions

| Cloud Tasks Feature | Azure Equivalent |
|--------------------|------------------|
| HTTP target tasks | Service Bus + Azure Functions |
| App Engine target tasks | Service Bus + WebJobs |
| Task scheduling (delayed) | Service Bus scheduled messages |
| Task retry / dead-letter | Service Bus retry + dead-letter queue |
| Rate limiting | Service Bus message throttling |
| Task orchestration | Durable Functions (fan-out/fan-in) |

## Traffic Splitting → Deployment Slots

| App Engine Feature | Azure Equivalent |
|--------------------|------------------|
| Version traffic splitting (%) | Slot traffic routing (%) |
| Canary deployment | Slot with low traffic % |
| A/B testing | Slot traffic routing |
| Version rollback | Slot swap (revert) |
| Gradual rollout | Increase slot traffic % incrementally |
| Warmup requests | Slot warm-up (pre-swap) |

```bicep
// Configure traffic routing: 90% production, 10% staging
resource siteConfig 'Microsoft.Web/sites/config@2023-12-01' = {
  name: 'web'
  properties: {
    experiments: {
      rampUpRules: [{
        actionHostName: '${webApp.name}-staging.azurewebsites.net'
        reroutePercentage: 10
        name: 'staging'
      }]
    }
  }
}
```

## Memcache → Azure Cache for Redis

| Memcache Feature | Azure Cache for Redis |
|------------------|----------------------|
| `memcache.get()` / `set()` | `redis.get()` / `redis.set()` |
| Shared memcache | Azure Cache for Redis (Basic) |
| Dedicated memcache | Azure Cache for Redis (Standard/Premium) |
| Session store | Redis session store |
| Cache expiry | Redis TTL |

## Environment Variables Migration

| Source | Target | Notes |
|--------|--------|-------|
| `app.yaml` env_variables | App Settings | Non-sensitive config |
| Secret Manager refs | Key Vault references | `@Microsoft.KeyVault(SecretUri=...)` |
| Runtime env (auto-injected) | App Settings | Map GAE-specific vars |
| `GAE_APPLICATION` | `WEBSITE_SITE_NAME` | Auto-injected by App Service |
| `PORT` | `PORT` | Auto-injected by App Service |
| `GOOGLE_CLOUD_PROJECT` | (no equivalent) | GCP project IDs identify a runtime environment; Azure subscription IDs are a tooling/billing context, not a runtime equivalent. Use App Service `WEBSITE_RESOURCE_GROUP` or rely on `DefaultAzureCredential` to discover the subscription at runtime if needed. |

## CI/CD Migration

| Cloud Build / gcloud | Azure Equivalent |
|---------------------|------------------|
| `gcloud app deploy` | `az webapp deploy` or `azd deploy` |
| `cloudbuild.yaml` | `.github/workflows/deploy.yml` |
| Cloud Build triggers | GitHub Actions triggers |
| Artifact Registry | Azure Container Registry |
| `gcloud app versions` | Deployment slots |

## Reference Links

- [GCP to Azure services comparison](https://learn.microsoft.com/en-us/azure/architecture/gcp-professional/)
- [App Service overview](https://learn.microsoft.com/en-us/azure/app-service/overview)
- [Cosmos DB migration options](https://learn.microsoft.com/en-us/azure/cosmos-db/migration-choices)
- [App Service deployment slots](https://learn.microsoft.com/en-us/azure/app-service/deploy-staging-slots)
