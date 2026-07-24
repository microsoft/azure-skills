# Bicep Patterns — Data Service Modules

Bicep module templates for database and cache services. Read when the prepare plan includes PostgreSQL, MySQL, or Redis.

For core patterns (file structure, skeleton, naming, tagging), see [bicep-patterns.md](bicep-patterns.md). For security defaults, see [bicep-patterns-security.md](bicep-patterns-security.md).

## PostgreSQL Flexible Server Module

```bicep
param pgName string
param location string
param tags object
param administratorLogin string
@secure()
param administratorLoginPassword string

// ⛔ @secure() — value generated ONCE at deploy time and reused on every redeploy (see deploy-checklist-template.md); never bake a value here.
param allowedExtensions string = 'uuid-ossp,pgcrypto,pg_trgm'

resource pg 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: pgName
  location: location
  tags: tags
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '16' // ⛔ use prepare-plan.json.services[].version (capabilities-verified) — do not guess
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorLoginPassword
    storage: { storageSizeGB: 32 }
  }
}

// 0.0.0.0 = all Azure services (intentional) — broad access consented at the Scaffold Gate.
resource pgFirewall 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: pg
  name: 'AllowAllAzureServicesAndResourcesWithinAzureIps'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
}

// Allow PG extensions (uuid-ossp, pgcrypto, pg_trgm)
resource pgExtensions 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2024-08-01' = {
  parent: pg
  name: 'azure.extensions'
  properties: { value: allowedExtensions, source: 'user-override' }
}
```

Wire connection string via Key Vault `secretRef` (Container Apps) or `@Microsoft.KeyVault()` (App Service).

## MySQL Flexible Server Module

```bicep
param mysqlName string
param location string
param tags object
param administratorLogin string
@secure()
param administratorLoginPassword string

// ⛔ @secure() — value generated ONCE at deploy time and reused on every redeploy (see deploy-checklist-template.md); never bake a value here.

resource mysql 'Microsoft.DBforMySQL/flexibleServers@2023-12-30' = {
  name: mysqlName
  location: location
  tags: tags
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '8.0.21' // ⛔ use prepare-plan.json.services[].version (capabilities-verified) — major-only '8.0' is rejected by ARM
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorLoginPassword
    storage: { storageSizeGB: 32 }
  }
}

// 0.0.0.0 = all Azure services (intentional) — broad access consented at the Scaffold Gate.
resource mysqlFirewall 'Microsoft.DBforMySQL/flexibleServers/firewallRules@2023-12-30' = {
  parent: mysql
  name: 'AllowAllAzureServicesAndResourcesWithinAzureIps'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
}

// Enforce TLS
resource mysqlTls 'Microsoft.DBforMySQL/flexibleServers/configurations@2023-12-30' = {
  parent: mysql
  name: 'require_secure_transport'
  properties: { value: 'ON', source: 'user-override' }
}

// App database from compose (e.g. MYSQLDB_DATABASE) — emit so it exists before first boot. Omit if only the default DB is used.
resource mysqlDb 'Microsoft.DBforMySQL/flexibleServers/databases@2023-12-30' = {
  parent: mysql
  name: appDbName
}
```

Wire connection string via Key Vault `secretRef` (Container Apps) or `@Microsoft.KeyVault()` (App Service).

## Redis Cache Module (Minimal)

```bicep
param redisName string
param location string
param tags object

resource redis 'Microsoft.Cache/redis@2024-03-01' = {
  name: redisName
  location: location
  tags: tags
  properties: { sku: { name: 'Basic', family: 'C', capacity: 0 }, enableNonSslPort: false, minimumTlsVersion: '1.2' }
}
```

Store `redis.properties.hostName` + access key in Key Vault. Wire via `secretRef`/`@Microsoft.KeyVault()`.
