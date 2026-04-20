# Global Rules

These rules apply to ALL phases of the azure-upgrade skill.

## Destructive Action Policy

⛔ **NEVER** perform destructive actions without explicit user confirmation via `ask_user`:
- Deleting apps, services, or resource groups
- Stopping or disabling the original app/service
- Overwriting app settings or configuration in the new app
- Removing the original hosting plan or service tier
- Modifying DNS or custom domain bindings

## User Confirmation Required

Always use `ask_user` before:
- Selecting target Azure subscription
- Selecting target Azure region/location
- Creating new Azure resources
- Stopping or deleting the original app/service
- Modifying custom domains or network restrictions
- Any irreversible configuration change

## Best Practices

- Always use `mcp_azure_mcp_get_azure_bestpractices` tool before generating upgrade commands
- Prefer managed identity over connection strings — upgrades are a good time to improve security
- **Always target the latest supported runtime version** — check Azure docs for the newest GA version
- Keep the original app/service running until the upgraded one is fully validated
- Use the same resource group for the new resource to maintain access to existing dependencies
- Follow Azure naming conventions for all new resources

## Identity-First Authentication (Zero API Keys)

> Enterprise subscriptions commonly enforce policies that block local auth. Always design for identity-based access from the start.

- Prefer managed identity connections over connection strings/keys
- Use `DefaultAzureCredential` in code — works locally and in Azure
- When using User Assigned Managed Identity, always pass `managedIdentityClientId` explicitly
- See service-specific identity configuration in the scenario reference files

## Rollback Policy

- Always document rollback steps before executing upgrade
- Keep the original app intact and running until upgrade is validated
- If upgrade fails, guide the user to restart the original app
- Never delete the original app automatically — always require `ask_user`
