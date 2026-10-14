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

## Artifact Output Policy

> All migration artifacts (assessment reports, status files, downloaded packages, transient JSON used to transfer settings) must be written under a single, scoped directory — **never** loose in the workspace root.

### Placeholder

| Placeholder | Resolves to |
|---|---|
| `<UPGRADE_DIR>` | `<workspace-root>/.azure-upgrade/<scenario-id>/` (override: `$env:AZURE_UPGRADE_DIR` on PowerShell, `$AZURE_UPGRADE_DIR` on bash) |

`<scenario-id>` is defined by each scenario reference:

| Scenario | `<scenario-id>` |
|---|---|
| Functions Consumption → Flex (Linux or Windows) | source function-app name (e.g. `mathewc-test-isolated`) |
| Java SDK modernization | uses its own location: `.github/java-upgrade/{RUN_ID}/` *(historical — TODO: converge to `<UPGRADE_DIR>` in a future pass)* |
| Redis (ACR/ACRE) → AMR | n/a — routes to external skills, this policy does not apply |

### Rules

1. **Resolve `<UPGRADE_DIR>` once at session start.** Honor `$AZURE_UPGRADE_DIR` if set; otherwise use `.azure-upgrade/<scenario-id>/` under the current workspace root. Create the directory if missing.
2. **Announce the chosen directory to the user before the first write**, e.g. *"I'll save migration artifacts under `.azure-upgrade/<scenario-id>/`. Say so if you'd prefer a different location."* — non-blocking, same pattern as naming/storage choices in the scenario references.
3. **Add `.azure-upgrade/` to `.gitignore`** if the workspace is a git repo and the entry is missing. Append once; never modify other entries.
4. **Pass explicit paths to all download/write commands** (`--file <UPGRADE_DIR>/...`, `--dest <UPGRADE_DIR>`, `> <UPGRADE_DIR>/...`). Do not rely on the current working directory — terminal sessions reset cwd between calls.
5. **Clean up transient artifacts after the operation that produced them succeeds.** Generated files and downloaded packages may contain user code or interim state — delete them once they have been applied. If the operation fails, leave retryable non-secret artifacts in place so the user does not need to recreate or re-fetch them.
6. **Never persist raw secret values to disk — anywhere, including `<UPGRADE_DIR>`.** Connection strings, keys, passwords, and secret-bearing app settings must stay in scoped process memory only. Suppress command output and clear variables immediately after use. `<UPGRADE_DIR>` is for migration artifacts users already handle as part of normal app development — not raw secrets.
