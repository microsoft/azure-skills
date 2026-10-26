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
#
# EXIT CODES: 0 = success, 1 = validation or command failure (no arguments accepted).

# Load azd environment variables
$AzdEnvironment = azd env get-values
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to read azd environment values."
    exit 1
}

foreach ($line in $AzdEnvironment) {
    if ([string]::IsNullOrEmpty($line)) { continue }
    $name, $value = $line.Split('=', 2)
    if ($null -eq $value) {
        Write-Error "Invalid azd environment entry."
        exit 1
    }
    if ($value.Length -ge 2 -and
        (($value.StartsWith('"') -and $value.EndsWith('"')) -or
         ($value.StartsWith("'") -and $value.EndsWith("'")))) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    try {
        Set-Item "env:$name" $value -ErrorAction Stop
    }
    catch {
        Write-Error "Failed to load azd environment entry: $_"
        exit 1
    }
}

# Determine app identity name (App Service uses SERVICE_WEB_NAME, APIs use SERVICE_API_NAME)
$AppName = if ($env:SERVICE_WEB_NAME) { $env:SERVICE_WEB_NAME } else { $env:SERVICE_API_NAME }

if (-not $AppName) {
    Write-Error "Neither SERVICE_WEB_NAME nor SERVICE_API_NAME is set in azd environment."
    exit 1
}

if ($AppName -cnotmatch '\A[a-zA-Z0-9][a-zA-Z0-9-]{0,58}[a-zA-Z0-9]\z') {
    Write-Error "App name must be 2-60 ASCII letters, digits or hyphens, starting and ending with a letter or digit."
    exit 1
}

$AppSqlLiteral = $AppName.Replace("'", "''")
$AppSqlIdentifier = $AppName.Replace(']', ']]')

Write-Host "Granting SQL data-plane access to managed identity: $AppName"

# Build idempotent SQL grant queries (reader + writer, required for all apps)
$SqlQuery = @"
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = N'$AppSqlLiteral')
  CREATE USER [$AppSqlIdentifier] FROM EXTERNAL PROVIDER;

IF NOT EXISTS (
  SELECT 1 FROM sys.database_role_members drm
  JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
  JOIN sys.database_principals m ON drm.member_principal_id = m.principal_id
  WHERE r.name = 'db_datareader' AND m.name = N'$AppSqlLiteral'
)
  ALTER ROLE db_datareader ADD MEMBER [$AppSqlIdentifier];

IF NOT EXISTS (
  SELECT 1 FROM sys.database_role_members drm
  JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
  JOIN sys.database_principals m ON drm.member_principal_id = m.principal_id
  WHERE r.name = 'db_datawriter' AND m.name = N'$AppSqlLiteral'
)
  ALTER ROLE db_datawriter ADD MEMBER [$AppSqlIdentifier];
"@

# Optionally grant db_ddladmin (needed when EF Core migrations run at startup or via hook)
$GrantDdlAdmin = $env:SQL_GRANT_DDLADMIN -eq 'true'
if ($GrantDdlAdmin) {
    $SqlQuery += @"

IF NOT EXISTS (
  SELECT 1 FROM sys.database_role_members drm
  JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
  JOIN sys.database_principals m ON drm.member_principal_id = m.principal_id
  WHERE r.name = 'db_ddladmin' AND m.name = N'$AppSqlLiteral'
)
  ALTER ROLE db_ddladmin ADD MEMBER [$AppSqlIdentifier];
"@
}

# Ensure sqlcmd is available to execute the query
if (-not (Get-Command sqlcmd -ErrorAction SilentlyContinue)) {
    Write-Error "'sqlcmd' is not installed or not on PATH."
    Write-Error "Install the modern go-sqlcmd from https://github.com/microsoft/go-sqlcmd and retry."
    exit 1
}

sqlcmd `
  -S "$($env:SQL_SERVER).database.windows.net" `
  -d $env:SQL_DATABASE `
  --authentication-method ActiveDirectoryDefault `
  -x -b `
  -Q $SqlQuery

if ($LASTEXITCODE -ne 0) {
    Write-Error "sqlcmd failed with exit code $LASTEXITCODE. SQL access was not granted."
    exit 1
}

Write-Host "SQL access granted successfully."
