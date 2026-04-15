# Terraform Validation

Validation steps for Terraform deployments.

## Prerequisites

- `./infra/main.tf` exists
- State backend accessible

## Validation Steps

- [ ] 1. Terraform Installation
- [ ] 2. Azure CLI Installation
- [ ] 3. Authentication
- [ ] 4. Initialize
- [ ] 5. Format Check
- [ ] 6. Validate Syntax
- [ ] 7. Plan Preview
- [ ] 8. State Backend
- [ ] 9. Azure Policy Validation
- [ ] 10. Template Variable Resolution Check (AZD+Terraform)

## Validation Details

### 1. Terraform Installation

Verify Terraform is installed:

```bash
terraform version
```

**If not installed:** See https://developer.hashicorp.com/terraform/install

### 2. Azure CLI Installation

Verify Azure CLI is installed:

```bash
az version
```

**If not installed:**
```
mcp_azure_mcp_extension_cli_install(cli-type: "az")
```

### 3. Authentication

```bash
az account show
```

**If not logged in:**
```bash
az login
az account set --subscription <subscription-id>
```

### 4. Initialize

```bash
cd infra
terraform init
```

### 5. Format Check

```bash
terraform fmt -check -recursive
```

**Fix if needed:**
```bash
terraform fmt -recursive
```

### 6. Validate Syntax

```bash
terraform validate
```

### 7. Plan Preview

```bash
terraform plan -out=tfplan
```

### 8. State Backend

Verify state is accessible:

```bash
terraform state list
```

### 9. Azure Policy Validation

See [Policy Validation Guide](../../policy-validation.md) for instructions on retrieving and validating Azure policies for your subscription.

### 10. Template Variable Resolution Check (AZD+Terraform)

> ⚠️ **CRITICAL for azd+Terraform projects.** azd substitutes `${VAR}` references in
> `main.tfvars.json` via envsubst, but does NOT interpolate Go-style template variables
> (`{{ .Env.* }}`). Unresolved Go-style template strings passed to Terraform cause
> cascading deployment failures, state conflicts, and timeouts.

**Check for Go-style template variables:**

```bash
# Check for Go-style template variables in Terraform files
grep -rn '{{ *\.Env\.' infra/ --include='*.tf' --include='*.tfvars.json' || echo "OK: No Go-style template variables found"

# Check main.tfvars.json uses correct ${VAR} syntax
if test -f infra/main.tfvars.json; then
  grep -n '{{ *\.Env\.' infra/main.tfvars.json && echo "WARNING: Use \${VAR} syntax instead of {{ .Env.* }}" || echo "OK: main.tfvars.json syntax is correct"
fi
```

**If Go-style template variables are found:**
1. **Fix the syntax** in `main.tfvars.json` — replace `{{ .Env.VAR }}` with `${VAR}`:
   ```json
   {
       "environment_name": "${AZURE_ENV_NAME}",
       "location": "${AZURE_LOCATION}"
   }
   ```
2. For additional variables, use **`TF_VAR_*` environment variables**:
   ```bash
   azd env set TF_VAR_environment_name "$(azd env get-value AZURE_ENV_NAME)"
   ```
3. **Verify** that `variables.tf` declares all required variables
4. **Re-run** `terraform validate` and `terraform plan` to confirm

**If `.tfvars.json` uses wrong syntax:**
- Replace Go-style `{{ .Env.* }}` with `${VAR}` (azd's envsubst format)
- Prefer putting static defaults in `variables.tf` `default` values. Using `terraform.tfvars` (HCL) for static defaults is acceptable if your team prefers it; this restriction is specifically about avoiding Go-style template expressions in `.tfvars.json` files.

## References

- [Error handling](./errors.md)

## Next

All checks pass → **azure-deploy**
