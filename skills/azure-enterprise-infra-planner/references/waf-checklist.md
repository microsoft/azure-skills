# WAF Cross-Cutting Checklist

Walk through every row and decide if resources or properties are needed.

| Concern | Question | Resources / Properties to Add |
|---------|----------|-------------------------------|
| Identity | How do services authenticate to each other? | Managed identity (`Microsoft.ManagedIdentity/userAssignedIdentities`), RBAC role assignments |
| Secrets | Are there connection strings, API keys, credentials? | Key Vault (`Microsoft.KeyVault/vaults`) with `enableRbacAuthorization: true`, `enableSoftDelete: true`, `enablePurgeProtection: true` |
| Monitoring | How will operators observe the system? | Application Insights for compute resources, Log Analytics workspace, diagnostic settings per data resource |
| Network | Should resources have public endpoints? | Production → VNet + private endpoints, `publicNetworkAccess: "Disabled"`. Cost-optimized → document omission as tradeoff. |
| Encryption | Is data encrypted at rest and in transit? | `httpsOnly: true`, `minTlsVersion: "1.2"`, Key Vault for CMK |
| Resilience | Single points of failure? | `zoneRedundant: true` on supported SKUs. Cost-optimized → document as tradeoff. |
| Auth hardening | Can local/key-based auth be disabled? | `disableLocalAuth: true` on Event Grid, Service Bus, Storage |
| Tagging | Resources tagged for cost tracking? | Tags on every resource |

## Common Additions

Most workloads should include these unless sub-goals justify omission:

- Key Vault — secrets, certificates, CMK
- Managed Identity — prefer over keys for service-to-service auth
- Application Insights — for App Service, Functions, Container Apps, AKS
- Log Analytics — centralized log aggregation
- Diagnostic Settings — wire Cosmos DB, SQL, Storage to Log Analytics

If you intentionally skip a concern (e.g., no VNet for cost reasons), document it in `overallReasoning.tradeoffs` and `inputs.subGoals`.
