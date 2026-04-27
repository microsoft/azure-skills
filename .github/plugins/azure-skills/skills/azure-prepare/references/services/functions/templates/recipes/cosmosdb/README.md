# Cosmos DB Recipe

Cosmos DB change feed trigger with managed identity authentication.

## Template Selection

Resource filter: `cosmos`  
Discover templates via MCP or CDN manifest where `resource == "cosmos"` and `language` matches user request.

## Troubleshooting

### "Forbidden" on Data Operations

**Cause:** Cosmos DB uses **two separate RBAC systems** — Azure RBAC (control plane) and Cosmos SQL RBAC via `sqlRoleAssignments` (data plane). The MCP template configures both, but if the SQL role assignment is missing, data reads/writes will fail even if Azure RBAC is correctly assigned.

**Solution:** Verify the `sqlRoleAssignments` resource exists in the Bicep/Terraform output. Check the function app has the `Cosmos DB Built-in Data Contributor` SQL role.

### UAMI Connection Issues

**Cause:** Missing managed identity credential settings.  
**Solution:** Ensure all three settings are present in app configuration:

- `COSMOS_CONNECTION__accountEndpoint`
- `COSMOS_CONNECTION__credential` (value: `managedidentity`)
- `COSMOS_CONNECTION__clientId`

See [Cosmos DB trigger connections](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-cosmosdb-v2-trigger#connections) for identity-based config — refer to the **"Connections"** section on that page for managed identity app settings.

## Eval

| Path | Description |
|------|-------------|
| [eval/summary.md](eval/summary.md) | Evaluation summary |
| [eval/python.md](eval/python.md) | Python evaluation results |
| [eval/typescript.md](eval/typescript.md) | TypeScript evaluation results |
