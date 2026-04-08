# Grant Azure SQL data-plane access to the App Service / Container App managed identity.
#
# USAGE: Copy this file to scripts/grant-sql-access.ps1 in your project root and add
#        a postprovision hook in azure.yaml:
#
#   hooks:
#     postprovision:
#       posix:
#         shell: sh
#         run: ./scripts/grant-sql-access.sh
#       windows:
#         shell: pwsh
#         run: ./scripts/grant-sql-access.ps1
#
# ENVIRONMENT VARIABLES (sourced from azd env):
#   SQL_SERVER           - SQL server name (without .database.windows.net)
#   SQL_DATABASE         - Database name
#   AZURE_RESOURCE_GROUP - Resource group name
#   SERVICE_WEB_NAME     - App Service name (used when set, takes priority)
#   SERVICE_API_NAME     - API service name (fallback when SERVICE_WEB_NAME is not set)
#   SQL_GRANT_DDLADMIN   - Set to "true" to also grant db_ddladmin (needed for EF migrations)

$ErrorActionPreference = 'Stop'

# Load azd environment variables
azd env get-values | ForEach-Object {
    $name, $value = $_.Split('=', 2)
    Set-Item "env:$name" $value.Trim('"')
}

# Determine app identity name (App Service uses SERVICE_WEB_NAME, APIs use SERVICE_API_NAME)
$AppName = if ($env:SERVICE_WEB_NAME) { $env:SERVICE_WEB_NAME } else { $env:SERVICE_API_NAME }

if (-not $AppName) {
    throw "ERROR: Neither SERVICE_WEB_NAME nor SERVICE_API_NAME is set in azd environment."
}

Write-Host "Granting SQL data-plane access to managed identity: $AppName"

# Build idempotent SQL grant queries (reader + writer, required for all apps)
$SqlQuery = @"
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = '$AppName')
  CREATE USER [$AppName] FROM EXTERNAL PROVIDER;

IF NOT EXISTS (
  SELECT 1 FROM sys.database_role_members drm
  JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
  JOIN sys.database_principals m ON drm.member_principal_id = m.principal_id
  WHERE r.name = 'db_datareader' AND m.name = '$AppName'
)
  ALTER ROLE db_datareader ADD MEMBER [$AppName];

IF NOT EXISTS (
  SELECT 1 FROM sys.database_role_members drm
  JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
  JOIN sys.database_principals m ON drm.member_principal_id = m.principal_id
  WHERE r.name = 'db_datawriter' AND m.name = '$AppName'
)
  ALTER ROLE db_datawriter ADD MEMBER [$AppName];
"@

# Optionally grant db_ddladmin (needed when EF Core migrations run at startup or via hook)
$GrantDdlAdmin = $env:SQL_GRANT_DDLADMIN -eq 'true'
if ($GrantDdlAdmin) {
    $SqlQuery += @"

IF NOT EXISTS (
  SELECT 1 FROM sys.database_role_members drm
  JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
  JOIN sys.database_principals m ON drm.member_principal_id = m.principal_id
  WHERE r.name = 'db_ddladmin' AND m.name = '$AppName'
)
  ALTER ROLE db_ddladmin ADD MEMBER [$AppName];
"@
}

az sql db query `
  --server $env:SQL_SERVER `
  --database $env:SQL_DATABASE `
  --resource-group $env:AZURE_RESOURCE_GROUP `
  --auth-mode ActiveDirectoryDefault `
  --queries $SqlQuery

Write-Host "SQL access granted successfully."
