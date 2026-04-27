# Azure SQL Recipe

SQL change tracking trigger with Entra ID managed identity authentication.

## Template Selection

Resource filter: `sql`  
Discover templates via MCP or CDN manifest where `resource == "sql"` and `language` matches user request.

## Troubleshooting

### SQL Trigger Not Firing

**Cause:** Change tracking not enabled on the target table.  
**Solution:** Run these T-SQL commands on your database:

```sql
ALTER DATABASE [YourDatabase] SET CHANGE_TRACKING = ON;
ALTER TABLE [dbo].[ToDo] ENABLE CHANGE_TRACKING;
```

### "Login failed" or "Unauthorized" Errors

**Cause:** Missing managed identity authentication or SQL access not granted.  
**Solution:** Set the SQL connection string with managed identity authentication:

```
Server=tcp:<server>.database.windows.net,1433;Database=<database>;Authentication=Active Directory Default;Encrypt=True;TrustServerCertificate=False;
```

For user-assigned managed identity, add `User Id=<ClientId>`:

```
Server=tcp:<server>.database.windows.net,1433;Database=<database>;Authentication=Active Directory Default;User Id=<ClientId>;Encrypt=True;TrustServerCertificate=False;
```

Also run post-deploy T-SQL to grant the function app data access:

```sql
CREATE USER [<function-app-name>] FROM EXTERNAL PROVIDER;
ALTER ROLE db_datareader ADD MEMBER [<function-app-name>];
ALTER ROLE db_datawriter ADD MEMBER [<function-app-name>];
```

See [SQL managed identity](https://learn.microsoft.com/en-us/azure/azure-functions/functions-identity-access-azure-sql-with-managed-identity) for identity-based config — refer to the **"Configure the function app"** section for connection string and identity settings.

## Eval

| Path | Description |
|------|-------------|
| [eval/summary.md](eval/summary.md) | Evaluation summary |
| [eval/python.md](eval/python.md) | Python evaluation results |
