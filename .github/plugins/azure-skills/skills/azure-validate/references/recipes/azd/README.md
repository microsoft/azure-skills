# AZD Validation

Validation steps for Azure Developer CLI projects.

## Prerequisites

- `azure.yaml` exists in project root
- Infrastructure files exist:
  - For Bicep: `./infra/` contains Bicep files
  - For Terraform: `./infra/` contains `.tf` files and `azure.yaml` has `infra.provider: terraform`

## Validation Steps

- [ ] 1. AZD Installation
- [ ] 2. Schema Validation
- [ ] 3. Environment Setup
- [ ] 4. Authentication Check
- [ ] 5. Subscription/Location Check
- [ ] 6. Aspire Pre-Provisioning Checks
- [ ] 7. Provision Preview
- [ ] 8. Build Verification
- [ ] 9. Docker Build Context Validation
- [ ] 10. Package Validation
- [ ] 11. Azure Policy Validation
- [ ] 12. Aspire Post-Provisioning Checks

## Validation Details

### 1. AZD Installation

Verify AZD is installed:

```bash
azd version
```

**If not installed:**
```
mcp_azure_mcp_extension_cli_install(cli-type: "azd")
```

### 2. Schema Validation

Validate azure.yaml against official schema:

```
mcp_azure_mcp_azd(command: "validate_azure_yaml", parameters: { path: "./azure.yaml" })
```

### 3. Environment Setup

Verify AZD environment exists and is configured. See [Environment Setup](environment.md) for detailed steps.

### 4. Authentication Check

```bash
azd auth login --check-status
```

**If not logged in:**
```bash
azd auth login
```

### 5. Subscription/Location Check

Check environment values:
```bash
azd env get-values
```

**If AZURE_SUBSCRIPTION_ID or AZURE_LOCATION not set:**

Use Azure MCP tools to list subscriptions:
```
mcp_azure_mcp_subscription_list
```

Use Azure MCP tools to list resource groups (check for conflicts):
```
mcp_azure_mcp_group_list
  subscription: <subscription-id>
```

Prompt user to confirm subscription and location before continuing.

Refer to the region availability reference to select a region supported by all services in this template:
- [Region availability](../../region-availability.md)

```bash
azd env set AZURE_SUBSCRIPTION_ID <subscription-id>
azd env set AZURE_LOCATION <location>
```

### 6. Aspire Pre-Provisioning Checks

**If this is a .NET Aspire project** (detected by `*.AppHost.csproj` or `Aspire.Hosting` package reference), run the **Pre-Provisioning** checks in [Aspire Validation](aspire.md) before continuing. **If not Aspire, skip this step.**

### 7. Provision Preview

Validate IaC is ready (must complete without error):

```bash
azd provision --preview --no-prompt
```

> 💡 **Note:** This works for both Bicep and Terraform. azd will automatically detect the provider from `azure.yaml` and run the appropriate validation (`bicep build` or `terraform plan`).

**If `azd provision --preview` fails with `unsupported resource type`:**

⛔ **Stop deployment immediately.** Do NOT attempt to fix or work around the error.

This error means the Aspire AppHost contains custom resource types that have no Azure deployment target (e.g., `HealthChecksUI`, custom child resources, or local-only integrations). These resources are intentionally designed for local development tooling and cannot be meaningfully deployed to Azure.

**Required actions:**
1. ⛔ **Do NOT modify source code** to suppress the error (e.g., do not add `.ExcludeFromManifest()`).
2. ⛔ **Do NOT proceed with `azd provision` or `azd deploy`.**
3. ✅ Inform the user: "This application contains custom Aspire resource types (`unsupported resource type: <type-name>`) that cannot be deployed to Azure. The application is designed for local development only."
4. ✅ Record a blocker: "Deployment blocked — AppHost contains unsupported resource types with no Azure deployment target."

> ⚠️ Adding `.ExcludeFromManifest()` to suppress the error may allow provisioning to proceed, but the resulting deployment will not represent the application's actual functionality and is not a valid deployment.

### 8. Build Verification

Build the project and verify there are no errors. If the build fails, fix the issues and re-build until it succeeds. Do NOT proceed to packaging or deployment with build errors.

### 9. Docker Build Context Validation

**If any service in `azure.yaml` uses a Dockerfile** (check the service's `project` path from `azure.yaml` for a `Dockerfile`), validate the build context before packaging:

1. Read each service's `Dockerfile`
2. If the Dockerfile contains `npm ci`, verify `package-lock.json` exists in the same directory
3. If `package-lock.json` is missing, generate it in the service's `project` path directory before proceeding:

```bash
cd <service-project-path>
npm install --package-lock-only
```

> ⚠️ **Warning:** `npm ci` will fail during Docker build if `package-lock.json` is missing. This check prevents Docker build failures during `azd package` and `azd up`.

### 10. Package Validation

Confirm all services package successfully:

```bash
azd package --no-prompt
```

### 11. Azure Policy Validation

See [Policy Validation Guide](../../policy-validation.md) for instructions on retrieving and validating Azure policies for your subscription.

### 12. Aspire Post-Provisioning Checks

**If this is a .NET Aspire project**, run the **Post-Provisioning** checks in [Aspire Validation](aspire.md) before proceeding to deployment. **If not Aspire, skip this step.**

## References

- [Environment Setup](environment.md)
- [Aspire Validation](aspire.md)
- [Error Handling](./errors.md)

## Next

All checks pass → **azure-deploy**
