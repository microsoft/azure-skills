# Database Post-Deploy Verification

Run schema migrations on AppOnboard-created databases (listed in `prepare-plan.json.services[]`) before health checks. The app must be running first — if it's crashing, fix that before attempting migrations.

## Create App Database (if needed)

> ⛔ **Azure PostgreSQL/MySQL Flexible Server only creates the system `postgres`/`mysql` database by default.** If the app's config references a named database (e.g., `car_sale_db`, `myapp_production`), create it BEFORE the container starts:
>
> ```powershell
> az postgres flexible-server db create -g {rg} -s {serverName} -d {dbName}
> ```
>
> Detect the database name from: (1) `prereq-output.json.initCommands[]` with `type: "db-migrate"`, (2) app config files (`config-docker.yml`, `.env`, `database.yml`), (3) compose `POSTGRES_DB` env var. If the container crashes with `database "X" does not exist`, this step was missed.

**Discover the migration command** from the codebase (check in order):

| Signal | Command | Working directory |
|--------|---------|-------------------|
| `alembic.ini` exists | `alembic upgrade head` | Directory containing `alembic.ini` |
| Django `manage.py` exists | `python manage.py migrate` | Directory containing `manage.py` |
| `prisma/schema.prisma` exists | `npx prisma migrate deploy` | Project root |
| EF `Migrations/` directory | `dotnet ef database update` | Project root |
| Rails `db/migrate/` directory | `rails db:migrate` | Project root |
| Sequelize `migrations/` + `.sequelizerc` | `npx sequelize-cli db:migrate` | Project root |

## Execute via the Deployed Environment

### App Service (Linux only)

```powershell
az webapp ssh -n {app} -g {rg} --subscription {sub}
# Then run the migration command interactively
```

### Container Apps

```powershell
az containerapp exec -n {ca} -g {rg} --subscription {sub} --command "{migration_command}"

# If the app's WORKDIR differs from migration tool location:
az containerapp exec -n {ca} -g {rg} --subscription {sub} --command "cd /app/backend && alembic upgrade head"
```

## Error Handling

If the migration command fails, classify as `IAC_ERROR` and check based on the database type:
- DB unreachable → check firewall rules (PostgreSQL: `AllowAllAzureServicesAndResourcesWithinAzureIps`, SQL: server firewall, MySQL: similar)
- Extension/feature missing → check DB-specific config (PostgreSQL: `azure.extensions`, SQL: compatibility level, MySQL: `require_secure_transport`)
- Module not found → verify the runtime includes the migration tool

> ⛔ **`{pass}` MUST be the same password passed to `az deployment sub create --parameters pgAdminPassword={value}`.** See deploy-safety.md § Deploy Checklist — generate each secret ONCE, persist to `deploy-secrets.env`, reuse everywhere. Mismatched passwords cause silent auth failures on migrations and connectivity checks.

## PostgreSQL-Specific Checks

Run BEFORE migrations when `services[]` includes PostgreSQL Flexible Server:

1. **Firewall connectivity:** `az postgres flexible-server execute -n {pg} -g {rg} -u {admin} -p {pass} -d postgres --querytext "SELECT 1"` — if this fails, the firewall rule is missing or RBAC propagation hasn't completed. Check `AllowAllAzureServicesAndResourcesWithinAzureIps` exists, wait 60s, retry
2. **Extension availability:** `az postgres flexible-server parameter show -g {rg} -n {pg} --name azure.extensions --query value -o tsv` — verify the extensions the app needs (e.g., `uuid-ossp` for Alembic/Django UUID fields) are in the allow-list. If missing, the Bicep module should have set them — check `infra/modules/postgresql.bicep`

## MySQL Flexible Server Checks

Run BEFORE migrations when `services[]` includes MySQL Flexible Server:

1. **Firewall connectivity:** `az mysql flexible-server execute -n {mysql} -u {admin} -p {pass} -d mysql -q "SELECT 1"` — if this fails, check the firewall rule and RBAC propagation. Note: `execute` resolves by server name (no `-g` needed)
2. **SSL enforcement:** `az mysql flexible-server parameter show -g {rg} -n {mysql} --name require_secure_transport --query value -o tsv` — verify matches the app's connection string SSL mode

## Azure SQL Checks

Run BEFORE migrations when `services[]` includes Azure SQL:

1. **Firewall connectivity:** `az sql db show -g {rg} -s {sqlServer} -n {dbName} --query status -o tsv` — verify the database is `Online`
2. **Server firewall:** `az sql server firewall-rule list -g {rg} -s {sqlServer} -o table` — verify `AllowAllWindowsAzureIps` (0.0.0.0 → 0.0.0.0) exists for Azure-internal access
