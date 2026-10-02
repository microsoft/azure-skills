# Data (Relational) Resources

| Resource | ARM Type | API Version | CAF Prefix | Naming Scope | Region |
|----------|----------|-------------|------------|--------------|--------|
| SQL Server | `Microsoft.Sql/servers` | `2023-08-01` | `sql` | Global | Foundational |
| SQL Database | `Microsoft.Sql/servers/databases` | `2023-08-01` | `sqldb` | Parent server | Foundational |
| MySQL Flexible Server | `Microsoft.DBforMySQL/flexibleServers` | `2023-12-30` | `mysql` | Global | Mainstream |
| PostgreSQL Flexible Server | `Microsoft.DBforPostgreSQL/flexibleServers` | `2024-08-01` | `psql` | Global | Mainstream |

## Documentation

| Resource | Bicep Reference | Service Overview | Naming Rules | Additional |
|----------|----------------|------------------|--------------|------------|
| SQL Server | [2023-08-01](https://learn.microsoft.com/azure/templates/microsoft.sql/servers?pivots=deployment-language-bicep) | [SQL Server overview](https://learn.microsoft.com/azure/azure-sql/database/sql-database-paas-overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftsql) | [TDE with Key Vault](https://learn.microsoft.com/azure/azure-sql/database/transparent-data-encryption-byok-overview) |
| SQL Database | [2023-08-01](https://learn.microsoft.com/azure/templates/microsoft.sql/servers/databases?pivots=deployment-language-bicep) | [SQL Database overview](https://learn.microsoft.com/azure/azure-sql/database/sql-database-paas-overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftsql) | [DTU vs vCore](https://learn.microsoft.com/azure/azure-sql/database/purchasing-models) |
| MySQL Flexible Server | [2023-12-30](https://learn.microsoft.com/azure/templates/microsoft.dbformysql/flexibleservers?pivots=deployment-language-bicep) | [MySQL overview](https://learn.microsoft.com/azure/mysql/flexible-server/overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftdbformysql) | [Compute and storage](https://learn.microsoft.com/azure/mysql/flexible-server/concepts-compute-storage) |
| PostgreSQL Flexible Server | [2024-08-01](https://learn.microsoft.com/azure/templates/microsoft.dbforpostgresql/flexibleservers?pivots=deployment-language-bicep) | [PostgreSQL overview](https://learn.microsoft.com/azure/postgresql/flexible-server/overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftdbforpostgresql) | [Compute and storage](https://learn.microsoft.com/azure/postgresql/flexible-server/concepts-compute-storage) |
