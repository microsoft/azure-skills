# Azure Database for MySQL Flexible Server

Use Flexible Server for applications that need MySQL compatibility, relational transactions, and a managed database. Do not substitute Azure SQL Database for an existing MySQL workload or generate new Single Server infrastructure.

Invoke **`azure-mysql`** for service-specific decisions, then return its findings to the current preparation plan. This reference does not replace `azure-prepare` -> `azure-validate` -> `azure-deploy` or start another plan.

## Plan the Supporting Stack

| Component | Decision to record |
| --- | --- |
| Engine and compute | Supported GA engine/driver combination, regional SKU, capacity/quota, and measured workload needs |
| Native MySQL driver | Existing application driver/ORM, bounded connection pool, timeouts, and safe reconnect behavior |
| Identity | Application managed identity where supported; separate server UAMI, Entra admin, approved tenant permissions, and least-privilege database user |
| Network | VNet integration with delegated subnet or supported Private Link configuration; app routes, private DNS, and verified TLS |
| Secrets | Key Vault/project secret store only when native credentials remain necessary; no credentials in outputs |
| Reliability | RPO/RTO, supported HA mode, backup retention/redundancy, storage growth, and restore/cutover procedure |
| Observability | Metrics/alerts, explicitly chosen logs and diagnostic destination, retention, and ingestion cost |

Use the selected recipe's current Bicep/provider schemas or an applicable Azure Verified Module. Keep the app's native MySQL driver for SQL data access; the Azure management SDK is not a SQL driver.

Expose nonsecret configuration such as the server-reported host, configured port, database, mapped user, and trust-bundle location. Do not assume ARM success proves connectivity: verify from the application network with its runtime identity after an approved deployment.

## Focused Guidance

- [MySQL skill](../../../../azure-mysql/SKILL.md)
- [Deployment and application stack](../../../../azure-mysql/references/deployment.md)
- [Identity, TLS, and networking](../../../../azure-mysql/references/connectivity.md)
- [HA, backups, replicas, and migration](../../../../azure-mysql/references/reliability.md)
- [Troubleshooting](../../../../azure-mysql/references/troubleshooting.md)

Source: [Azure MySQL architecture guidance](https://learn.microsoft.com/azure/well-architected/service-guides/azure-database-for-mysql).
