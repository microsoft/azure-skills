# Data (Relational) Pairing Constraints

### SQL Server

| Paired With | Constraint |
|-------------|------------|
| **SQL Database** | Databases are child resources — must reference this server as parent. |
| **Key Vault (TDE)** | Key Vault must have `enablePurgeProtection: true`. Must be in same Azure AD tenant. Server needs GET, WRAP KEY, UNWRAP KEY permissions on key. TDE protector setup fails if Key Vault soft-delete and purge-protection are not both enabled. |
| **Virtual Network** | Use `Microsoft.Sql/servers/virtualNetworkRules` to restrict access to specific subnets. Subnets need `Microsoft.Sql` service endpoint. |
| **Private Endpoint** | Set `publicNetworkAccess: 'Disabled'` when using private endpoints exclusively. |
| **Elastic Pool** | Databases using elastic pools reference `elasticPoolId` — server must host both pool and databases. Hyperscale elastic pools cannot be created from non-Hyperscale pools. |
| **Failover Group** | Both primary and secondary servers must exist. Databases to be replicated must belong to the primary server. Failover group from zone-redundant to non-zone-redundant Hyperscale elastic pool fails silently (geo-secondary shows "Seeding 0%"). |

### SQL Database

| Paired With | Constraint |
|-------------|------------|
| **SQL Server** | Must be deployed as child of the parent SQL Server. Location must match. |
| **Elastic Pool** | `elasticPoolId` must reference a pool on the same server. Cannot set `sku` when using elastic pool (it inherits pool SKU). |
| **Zone Redundancy** | Only available in `GeneralPurpose`, `BusinessCritical`, and `Hyperscale` tiers. Not available in DTU tiers. General Purpose zone redundancy is only available in selected regions. Hyperscale zone redundancy can only be set at creation — cannot modify after provisioning; must recreate via copy/restore/geo-replica. |
| **Serverless** | Only available in `GeneralPurpose` tier. SKU name uses `GP_S_Gen5_*` pattern. |
| **Hyperscale** | Reverse migration from Hyperscale to General Purpose is supported within 45 days of the original migration. Databases originally created as Hyperscale cannot reverse migrate. |
| **Hyperscale Elastic Pool** | Cannot be created from a non-Hyperscale pool. Cannot be converted to non-Hyperscale (one-way only). Named replicas cannot be added to Hyperscale elastic pools (`UnsupportedReplicationOperation`). Zone-redundant Hyperscale elastic pools require databases with ZRS/GZRS backup storage — cannot add LRS-backed databases. |
| **Failover Group** | Failover group from zone-redundant to non-zone-redundant Hyperscale elastic pool fails silently (geo-secondary shows "Seeding 0%"). |
| **Backup Redundancy** | `GeoZone` only available in select regions. `Local` not available in all regions. |

### MySQL Flexible Server

| Paired With | Constraint |
|-------------|------------|
| **VNet (private access)** | Requires a dedicated subnet delegated to `Microsoft.DBforMySQL/flexibleServers`. Subnet must have no other resources. |
| **Private DNS Zone** | For VNet-integrated (private access) servers, use the zone name `{name}.mysql.database.azure.com` (not `privatelink.*`). The `privatelink.mysql.database.azure.com` zone is used for Private Endpoint connectivity only. Provide `privateDnsZoneResourceId` and the DNS zone must be linked to the VNet. |
| **High Availability** | `ZoneRedundant` HA requires `GeneralPurpose` or `MemoryOptimized` tier. Not available with `Burstable`. |
| **Geo-Redundant Backup** | Must be enabled at server creation time. Cannot be changed after creation. Not available in all regions. |
| **Storage Auto-Grow** | Storage can only grow, never shrink. Enabled by default. |
| **Read Replicas** | Source server must have `backup.backupRetentionDays` > 1. Replica count limit: up to 10 replicas. |
| **Key Vault (CMK)** | Customer-managed keys require user-assigned managed identity and Key Vault with purge protection enabled. |

### PostgreSQL Flexible Server

| Paired With | Constraint |
|-------------|------------|
| **VNet (private access)** | Requires a dedicated subnet delegated to `Microsoft.DBforPostgreSQL/flexibleServers`. Subnet must have no other resources. |
| **Private DNS Zone** | For VNet-integrated (private access) servers, use the zone name `{name}.postgres.database.azure.com` (not `privatelink.*`). The `privatelink.postgres.database.azure.com` zone is used for Private Endpoint connectivity only. Provide `privateDnsZoneArmResourceId` and the DNS zone must be linked to the VNet. |
| **High Availability** | `ZoneRedundant` HA requires `GeneralPurpose` or `MemoryOptimized` tier. Not available with `Burstable`. |
| **Geo-Redundant Backup** | Not available in all regions. Cannot be enabled with VNet-integrated (private access) servers in some configurations. |
| **Storage Auto-Grow** | Storage can only grow, never shrink. Minimum increase is based on current size. |
| **Key Vault (CMK)** | Customer-managed keys require user-assigned managed identity and Key Vault with purge protection enabled. |
