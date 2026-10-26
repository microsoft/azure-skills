#!/usr/bin/env bash
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
#
# EXIT CODES: 0 = success, 1 = validation or command failure (no arguments accepted).

set -e

# Safely load azd environment variables without eval
if ! AZD_ENV=$(azd env get-values); then
  echo "ERROR: Failed to read azd environment values." >&2
  exit 1
fi

while IFS= read -r line; do
  line=${line%$'\r'}
  [ -n "$line" ] || continue
  key=${line%%=*}
  value=${line#*=}
  case "$value" in
    \"*\") value=${value#\"}; value=${value%\"} ;;
    \'*\') value=${value#\'}; value=${value%\'} ;;
  esac
  export "$key=$value"
done <<< "$AZD_ENV"

# Determine app identity name (App Service uses SERVICE_WEB_NAME, APIs use SERVICE_API_NAME)
APP_NAME=${SERVICE_WEB_NAME:-${SERVICE_API_NAME:-}}

if [ -z "$APP_NAME" ]; then
  echo "ERROR: Neither SERVICE_WEB_NAME nor SERVICE_API_NAME is set in azd environment." >&2
  exit 1
fi

if [[ ${#APP_NAME} -lt 2 || ${#APP_NAME} -gt 60 ||
      "$APP_NAME" == *[!abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-]* ||
      "$APP_NAME" == -* || "$APP_NAME" == *- ]]; then
  echo "ERROR: App name must be 2-60 ASCII letters, digits or hyphens, starting and ending with a letter or digit." >&2
  exit 1
fi

APP_SQL_LITERAL=${APP_NAME//\'/\'\'}
APP_SQL_IDENTIFIER=${APP_NAME//\]/\]\]}

echo "Granting SQL data-plane access to managed identity: $APP_NAME"

# Build idempotent SQL grant queries (reader + writer, required for all apps)
SQL_QUERIES="
  IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = N'$APP_SQL_LITERAL')
    CREATE USER [$APP_SQL_IDENTIFIER] FROM EXTERNAL PROVIDER;

  IF NOT EXISTS (
    SELECT 1 FROM sys.database_role_members drm
    JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
    JOIN sys.database_principals m ON drm.member_principal_id = m.principal_id
    WHERE r.name = 'db_datareader' AND m.name = N'$APP_SQL_LITERAL'
  )
    ALTER ROLE db_datareader ADD MEMBER [$APP_SQL_IDENTIFIER];

  IF NOT EXISTS (
    SELECT 1 FROM sys.database_role_members drm
    JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
    JOIN sys.database_principals m ON drm.member_principal_id = m.principal_id
    WHERE r.name = 'db_datawriter' AND m.name = N'$APP_SQL_LITERAL'
  )
    ALTER ROLE db_datawriter ADD MEMBER [$APP_SQL_IDENTIFIER];
"

# Optionally grant db_ddladmin (needed when EF Core migrations run at startup or via hook)
SQL_GRANT_DDLADMIN="${SQL_GRANT_DDLADMIN:-false}"
if [ "$SQL_GRANT_DDLADMIN" = "true" ]; then
  SQL_QUERIES="$SQL_QUERIES
  IF NOT EXISTS (
    SELECT 1 FROM sys.database_role_members drm
    JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
    JOIN sys.database_principals m ON drm.member_principal_id = m.principal_id
    WHERE r.name = 'db_ddladmin' AND m.name = N'$APP_SQL_LITERAL'
  )
    ALTER ROLE db_ddladmin ADD MEMBER [$APP_SQL_IDENTIFIER];
"
fi

# Ensure sqlcmd is available to execute the query
if ! command -v sqlcmd >/dev/null 2>&1; then
  echo "ERROR: 'sqlcmd' is not installed or not on PATH." >&2
  echo "Install the modern go-sqlcmd from https://github.com/microsoft/go-sqlcmd and retry." >&2
  exit 1
fi

if ! sqlcmd \
  -S "${SQL_SERVER}.database.windows.net" \
  -d "$SQL_DATABASE" \
  --authentication-method ActiveDirectoryDefault \
  -x -b \
  -Q "$SQL_QUERIES"; then
  echo "ERROR: sqlcmd failed. SQL access was not granted." >&2
  exit 1
fi

echo "SQL access granted successfully."
