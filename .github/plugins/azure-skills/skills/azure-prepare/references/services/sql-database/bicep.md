# SQL Database - Bicep Patterns

> ⛔ **CRITICAL — SQL Server Bicep MUST use Entra-only authentication. NEVER include `administratorLogin` or `administratorLoginPassword` anywhere in a Bicep file — not even inside a conditional (`condition ? { ... } : { administratorLoginPassword: ... }`) branch. If either property name appears anywhere in the file, the deployment will be rejected. Always use the pattern below.**

## Basic Setup (Entra-Only Authentication)

**Required approach** — Uses Microsoft Entra ID authentication only. Required for subscriptions with Entra-only policies; SQL admin authentication is disabled by policy in those environments.

```bicep
param principalId string
param principalName string
@allowed(['User', 'Group', 'Application'])
param principalType string = 'User'

resource sqlServer 'Microsoft.Sql/servers@2022-05-01-preview' = {
  name: '${resourcePrefix}-sql-${uniqueHash}'
  location: location
  properties: {
    administrators: {
      administratorType: 'ActiveDirectory'
      principalType: principalType
      login: principalName
      sid: principalId
      tenantId: subscription().tenantId
      azureADOnlyAuthentication: true
    }
    minimalTlsVersion: '1.2'
  }
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2022-05-01-preview' = {
  parent: sqlServer
  name: 'appdb'
  location: location
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    maxSizeBytes: 2147483648  // 2 GB
  }
}

resource sqlFirewallAzure 'Microsoft.Sql/servers/firewallRules@2022-05-01-preview' = {
  parent: sqlServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}
```

**Set Entra admin parameters:**

1. Get current user info:
```bash
az ad signed-in-user show --query "{id:id, name:displayName}" -o json
```

> ⚠️ **Warning:** If deploying from CI/CD with a service principal, set `principalType` to `'Application'`. The default `'User'` only works for interactive (human) deployments. Mismatched `principalType` causes `UnmatchedPrincipalType` errors during provisioning.

2. Set as azd environment variables:
```bash
PRINCIPAL_INFO=$(az ad signed-in-user show --query "{id:id, name:displayName}" -o json)
azd env set AZURE_PRINCIPAL_ID $(echo $PRINCIPAL_INFO | jq -r '.id')
azd env set AZURE_PRINCIPAL_NAME $(echo $PRINCIPAL_INFO | jq -r '.name')
```

> 💡 **Tip:** Set these variables immediately after `azd init` to avoid deployment failures. The Bicep `principalId` and `principalName` parameters will automatically use these environment variables.

## Serverless Configuration

```bicep
resource sqlDatabase 'Microsoft.Sql/servers/databases@2022-05-01-preview' = {
  parent: sqlServer
  name: 'appdb'
  location: location
  sku: {
    name: 'GP_S_Gen5'
    tier: 'GeneralPurpose'
    family: 'Gen5'
    capacity: 2
  }
  properties: {
    autoPauseDelay: 60  // minutes
    minCapacity: json('0.5')
  }
}
```

## Private Endpoint

```bicep
resource sqlPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-05-01' = {
  name: '${sqlServer.name}-pe'
  location: location
  properties: {
    subnet: {
      id: subnet.id
    }
    privateLinkServiceConnections: [
      {
        name: '${sqlServer.name}-connection'
        properties: {
          privateLinkServiceId: sqlServer.id
          groupIds: ['sqlServer']
        }
      }
    ]
  }
}
```

## ⛔ MANDATORY: SQL Data-Plane Access via postprovision Hook

> **CRITICAL:** ARM/Bicep role assignments (`SQL DB Contributor`) only grant **control-plane** access. They do **not** grant the app **data-plane** access to the database. Without the T-SQL grant below, apps using `Authentication=Active Directory Default` will crash on startup with a login failure.
>
> **When you generate SQL + Managed Identity infrastructure you MUST also:**
> 1. Add a `postprovision` hook to `azure.yaml` that runs the SQL grant script
> 2. Copy the pre-built scripts from [scripts/grant-sql-access.sh](scripts/grant-sql-access.sh) and [scripts/grant-sql-access.ps1](scripts/grant-sql-access.ps1) to `scripts/` in the user's project root

**azure.yaml hooks section (add or merge):**

```yaml
hooks:
  postprovision:
    posix:
      shell: sh
      run: ./scripts/grant-sql-access.sh
    windows:
      shell: pwsh
      run: ./scripts/grant-sql-access.ps1
```

**Copy the pre-built scripts** — Read [scripts/grant-sql-access.sh](scripts/grant-sql-access.sh) and [scripts/grant-sql-access.ps1](scripts/grant-sql-access.ps1) and write them verbatim to the project's `scripts/` folder. Do not regenerate them from scratch.

Key behaviours of the scripts:
- Installs the `rdbms-connect` Azure CLI extension if not already present (required for `az sql db query`)
- Loads `azd env get-values` safely (no `eval`)
- Grants `db_datareader` + `db_datawriter` by default (idempotent)
- Set `SQL_GRANT_DDLADMIN=true` in the azd env to also grant `db_ddladmin` (needed for EF Core migrations)
- `SERVICE_WEB_NAME` takes priority over `SERVICE_API_NAME` when resolving the app identity

> 💡 Make executable: `chmod +x scripts/*.sh`

> 💡 If the app also uses EF Core migrations, combine this with the migration hook — see the `azure-deploy` skill's `references/recipes/azd/sql-managed-identity.md`.

## Legacy SQL Authentication (⛔ DO NOT USE - EVER)

> ❌ **PROHIBITED — NEVER generate `administratorLogin` or `administratorLoginPassword` properties.**
> This applies unconditionally: do NOT include them in direct assignments, conditional expressions, ternary branches, parameter defaults, or any other construct. The **text** of these property names must not appear anywhere in a generated `.bicep` file.
> SQL admin authentication is disabled in all subscriptions with Entra-only policies and violates Azure security best practices.
> Always use the Entra-only authentication pattern at the top of this file.
>
> ❌ **DO NOT generate conditional patterns like:**
> ```bicep
> properties: useEntraAuth ? {
>   administrators: {
>     azureADOnlyAuthentication: true
>     // ...
>   }
> } : {
>   administratorLogin: sqlAdminLogin          // ❌ PROHIBITED
>   administratorLoginPassword: sqlAdminPassword  // ❌ PROHIBITED
> }
> ```
> Use only the unconditional Entra-only pattern. No fallback. No toggle. No conditional.
