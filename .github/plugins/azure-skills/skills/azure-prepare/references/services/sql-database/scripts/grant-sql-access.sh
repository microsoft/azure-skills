#!/bin/bash
# Grant Azure SQL data-plane access to the App Service / Container App managed identity.
#
# USAGE: Copy this file to scripts/grant-sql-access.sh in your project root and add
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

set -e

# Safely load azd environment variables without eval
while IFS= read -r line; do
  [ -n "$line" ] || continue
  key=${line%%=*}
  value=${line#*=}
  case "$value" in
    \"*\") value=${value#\"}; value=${value%\"} ;;
    \'*\') value=${value#\'}; value=${value%\'} ;;
  esac
  export "$key=$value"
done < <(azd env get-values)

# Determine app identity name (App Service uses SERVICE_WEB_NAME, APIs use SERVICE_API_NAME)
APP_NAME=${SERVICE_WEB_NAME:-$SERVICE_API_NAME}

if [ -z "$APP_NAME" ]; then
  echo "ERROR: Neither SERVICE_WEB_NAME nor SERVICE_API_NAME is set in azd environment." >&2
  exit 1
fi

echo "Granting SQL data-plane access to managed identity: $APP_NAME"

# Build idempotent SQL grant queries (reader + writer, required for all apps)
SQL_QUERIES="
  IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = '$APP_NAME')
    CREATE USER [$APP_NAME] FROM EXTERNAL PROVIDER;

  IF NOT EXISTS (
    SELECT 1 FROM sys.database_role_members drm
    JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
    JOIN sys.database_principals m ON drm.member_principal_id = m.principal_id
    WHERE r.name = 'db_datareader' AND m.name = '$APP_NAME'
  )
    ALTER ROLE db_datareader ADD MEMBER [$APP_NAME];

  IF NOT EXISTS (
    SELECT 1 FROM sys.database_role_members drm
    JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
    JOIN sys.database_principals m ON drm.member_principal_id = m.principal_id
    WHERE r.name = 'db_datawriter' AND m.name = '$APP_NAME'
  )
    ALTER ROLE db_datawriter ADD MEMBER [$APP_NAME];
"

# Optionally grant db_ddladmin (needed when EF Core migrations run at startup or via hook)
SQL_GRANT_DDLADMIN="${SQL_GRANT_DDLADMIN:-false}"
if [ "$SQL_GRANT_DDLADMIN" = "true" ]; then
  SQL_QUERIES="$SQL_QUERIES
  IF NOT EXISTS (
    SELECT 1 FROM sys.database_role_members drm
    JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
    JOIN sys.database_principals m ON drm.member_principal_id = m.principal_id
    WHERE r.name = 'db_ddladmin' AND m.name = '$APP_NAME'
  )
    ALTER ROLE db_ddladmin ADD MEMBER [$APP_NAME];
"
fi

# Ensure the rdbms-connect extension is installed (provides 'az sql db query')
if ! az extension show --name rdbms-connect >/dev/null 2>&1; then
  echo "Azure CLI extension 'rdbms-connect' is not installed. Installing..."
  if ! az extension add --name rdbms-connect --yes; then
    echo "ERROR: Failed to install Azure CLI extension 'rdbms-connect'. Ensure Azure CLI has network access and retry." >&2
    exit 1
  fi
fi

az sql db query \
  --server "$SQL_SERVER" \
  --database "$SQL_DATABASE" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --auth-mode ActiveDirectoryDefault \
  --queries "$SQL_QUERIES"

echo "SQL access granted successfully."
