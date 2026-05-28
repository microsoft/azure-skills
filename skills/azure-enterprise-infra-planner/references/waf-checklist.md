# WAF Cross-Cutting Checklist

Walk through every row and decide if resources or properties are needed.

| Concern | Question | Resources / Properties to Add |
|---------|----------|-------------------------------|
| Identity | How do services authenticate to each other? | Managed identity, RBAC role assignments |
| Secrets | Are there connection strings, API keys, credentials? | Key Vault with RBAC authorization, soft-delete, and purge protection enabled |
| Monitoring | How will operators observe the system? | Application Insights for compute, Log Analytics workspace, diagnostic settings on data resources |
| Network | Should resources have public endpoints? | Prefer private connectivity (VNet integration, private endpoints, `publicNetworkAccess: "Disabled"`). Only expose endpoints publicly when the workload requires it, and document the decision as a tradeoff. |
| Encryption | Is data encrypted at rest and in transit? | HTTPS-only, modern minimum TLS, Key Vault for customer-managed keys |
| Resilience | Single points of failure? | Zone-redundant SKUs where supported; compute distributed across ≥2 zones for production. Document deviations as tradeoffs. |
| Auth hardening | Can local/key-based auth be disabled? | Disable local auth on services that support it (e.g. Event Grid, Service Bus, Storage) |
| Tagging | Resources tagged for cost tracking? | Tags on every resource |

## Common Additions

Most workloads should include these unless sub-goals justify omission:

- Key Vault — secrets, certificates, customer-managed keys
- Managed Identity — prefer over keys for service-to-service auth
- Application Insights — for App Service, Functions, Container Apps, AKS
- Log Analytics — centralized log aggregation
- Diagnostic Settings — wire data resources to Log Analytics

If you intentionally skip a concern (e.g., no VNet for cost reasons), document it in `overallReasoning.tradeoffs` and `inputs.subGoals`.
