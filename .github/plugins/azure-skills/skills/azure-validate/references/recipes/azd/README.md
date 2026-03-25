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
- [ ] 9. Package Validation
- [ ] 10. Azure Policy Validation
- [ ] 11. Aspire Post-Provisioning Checks

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

### 8. Build Verification

Build the project and verify there are no errors. If the build fails, fix the issues and re-build until it succeeds. Do NOT proceed to packaging or deployment with build errors.

### 9. Package Validation

Confirm all services package successfully:

```bash
azd package --no-prompt
```

### 10. Azure Policy Validation

See [Policy Validation Guide](../../policy-validation.md) for instructions on retrieving and validating Azure policies for your subscription.

### 11. Aspire Post-Provisioning Checks

**If this is a .NET Aspire project**, run the **Post-Provisioning** checks in [Aspire Validation](aspire.md) before proceeding to deployment. **If not Aspire, skip this step.**

## References

- [Environment Setup](environment.md)
- [Aspire Validation](aspire.md)
- [Error Handling](./errors.md)

## Next

All checks pass → **azure-deploy**
