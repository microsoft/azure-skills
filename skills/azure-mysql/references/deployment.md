# Deployment and Application Stack

## Establish Requirements

Record the existing application language, MySQL driver/version, ORM and migration tool, engine version, data size/growth, read/write pattern, peak connections, latency needs, budget, residency, and RPO/RTO. Preserve MySQL compatibility for an existing MySQL application; Azure SQL Database is a different engine, not a drop-in replacement.

| Decision | Recommended starting point | Verify before selecting |
| --- | --- | --- |
| Engine | A currently supported GA LTS release | [Version policy](https://learn.microsoft.com/azure/mysql/concepts-version-policy), driver/ORM compatibility, region availability; no preview default |
| Compute | Burstable for intermittent development; General Purpose for sustained production; evaluate memory-focused tiers for measured memory pressure | Current SKU names, capacity, CPU credits, memory and I/O requirements |
| Storage | Size for measured data and growth; evaluate autogrow | Provisioned storage cannot shrink; increases and autogrow affect cost |
| Network | Private connectivity for production | Choose VNet integration or Private Link deliberately; include application routing and DNS |
| Identity | Entra authentication with an application managed identity where supported | Server identity, Entra admin, tenant consent, driver token support, and SQL grants are separate requirements |
| Availability | Zone-redundant HA when required and supported | Region/tier support, creation-time constraints, standby cost, and recovery objectives |
| Recovery | Automated backups with policy-appropriate retention; geo protection when required | Available restore points, residency, backup redundancy constraints, and a tested restore procedure |
| Monitoring | Azure Monitor metrics and deliberate slow/audit-log collection | Log categories, diagnostic destination, retention, sensitive SQL exposure, and ingestion cost |

Inspect actual regional choices instead of copying an example SKU:

```azurecli
az mysql flexible-server list-skus --subscription SUBSCRIPTION_ID --location LOCATION --output table
```

SKU availability does not prove subscription quota or immediate capacity. Validate those separately before provisioning.

## Reuse the Project's Deployment Workflow

- For an existing `azure.yaml` or an explicit azd request, provide these MySQL decisions to **`azure-prepare`** and retain its plan/approval requirements. Continue through **`azure-validate`** and **`azure-deploy`**, not directly to `azd up`. If preparation invoked this skill, return findings to its current plan rather than start a second preparation workflow.
- For a requested Bicep, Terraform, or other non-azd workflow, keep that choice. Use its validation and preview/what-if/plan before asking to execute changes. Do not generate `azure.yaml` solely to force the request through azd.
- If no workflow exists, recommend the established plugin preparation path and confirm the deployment method before generating infrastructure.

## Generate Infrastructure from Current Schemas

Use `Microsoft.DBforMySQL/flexibleServers` and the current [Bicep resource reference](https://learn.microsoft.com/azure/templates/microsoft.dbformysql/flexibleservers), or the project's pinned provider and [Terraform resource reference](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/mysql_flexible_server). Prefer an applicable Azure Verified Module after checking its current contract. Do not paste a fixed API version, provider version, SKU, or untested template from memory.

Include the chosen network model and DNS links, necessary identities and explicitly approved grants, database configuration, tags, backup/HA choices, and diagnostic settings. Private endpoint networking and delegated-subnet integration are alternatives, not resources to combine blindly. Plan tenant permissions and SQL principal provisioning separately from ARM resources. Store unavoidable native credentials in the project's secret store/Key Vault; use secure parameters and never output secrets.

## Application Integration

Keep the application's existing maintained **native MySQL driver** and migration tool. Azure management SDKs manage the server; they do not replace a SQL driver. Use Azure Identity or a supported authentication integration when the driver needs an Entra token provider; verify the installed versions' documented API.

Export only nonsecret connection configuration: the server-reported FQDN, configured port, database, mapped database user, trusted CA bundle location, and an application UAMI client ID if required. Do not construct a public-cloud hostname for a sovereign-cloud server or confuse the server's UAMI with the app's.

Configure verified TLS, bounded pooling, connection/command timeouts, and token refresh for new physical connections. Handle transient failover with bounded backoff; retry whole transactions only when safe. An unknown commit outcome is not permission to replay a write.

## Verify the Complete Path

Validate infrastructure and inspect its preview before provisioning approval. After an approved deployment, verify readiness, private DNS/TCP connectivity, TLS, and a minimal read using the **application identity from its network**. An ARM deployment succeeding does not prove SQL connectivity. Validate migrations separately with their approved permissions; the app must not use the server administrator as its normal runtime identity.

Sources: [Architecture recommendations](https://learn.microsoft.com/azure/well-architected/service-guides/azure-database-for-mysql), [CLI SKU discovery](https://learn.microsoft.com/cli/azure/mysql/flexible-server#az-mysql-flexible-server-list-skus), [connectivity and authentication](connectivity.md), [recovery and lifecycle](reliability.md).
