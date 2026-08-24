# Terraform Generation

Generate Terraform IaC files from the approved infrastructure plan.

## File Structure

Generate files under `<project-root>/infra/`:

```
infra/
├── main.tf                 # Root module — calls child modules
├── variables.tf            # Input variable declarations
├── outputs.tf              # Output values
├── terraform.tfvars        # Default variable values
├── providers.tf            # Provider configuration
├── backend.tf              # State backend configuration
└── modules/
    ├── storage/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── compute/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    └── networking/
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

## Generation Steps

1. Create `infra/` directory — create `<project-root>/infra/` and `<project-root>/infra/modules/` directories. All files in subsequent steps go here.
2. Read plan — load `<project-root>/.azure/infrastructure-plan.json`, verify `meta.status === "approved"`
3. Generate providers.tf — write `infra/providers.tf` to configure `azurerm` provider with required features
4. Generate modules — group resources by category; one module per group under `infra/modules/`
5. Generate root main.tf — write `infra/main.tf` that calls all modules, wire outputs to inputs
6. Generate variables.tf — write `infra/variables.tf` with all configurable parameters
7. Generate terraform.tfvars — write `infra/terraform.tfvars` with default values from the plan
8. Generate backend.tf — write `infra/backend.tf` for Azure Storage backend remote state

## Terraform Conventions

- Use `azurerm` provider (latest stable version)
- Set `features {}` block in provider configuration
- Use `variable` blocks with `description`, `type`, and `default` where appropriate
- Use `locals` for computed values and naming patterns
- Use `depends_on` only when implicit dependencies are insufficient
- Tag all resources with `environment`, `workload`, and `managed-by = "terraform"`

## Provider Configuration

```hcl
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}
```

## Multi-Environment

For multi-environment plans, generate one `.tfvars` file per environment:

```
infra/
├── main.tf
├── variables.tf
├── dev.tfvars
├── staging.tfvars
└── prod.tfvars
```

Deploy with: `terraform apply -var-file=prod.tfvars`

## Validation Before Deployment

Run `terraform validate` and `terraform plan` to verify before applying.

## Correctness Checklist (must pass `terraform validate` with zero errors)

Generate against these rules, then run `terraform init -backend=false` + `terraform validate` and fix
in-place until clean. These are the failures that most often break validation:

1. **Every referenced value is declared.** Each `var.X` has a `variable "X"` block; each `local.X` is
   defined; each `module.X`/`azurerm_*.X` reference exists. No references to undeclared symbols.
2. **Module wiring is complete.** Values passed into a child module map to declared `variable` blocks in
   that module; values read as `module.X.Y` map to declared `output "Y"` in that child module.
3. **Existing resources use `data`/`import`, not new `resource`.** Reference pre-existing infra via
   `data` sources (or `import`), and wire new resources to them — never recreate them.
4. **Valid provider + required attributes.** `required_providers` pins `azurerm` (`~> 4.0`), the
   `provider "azurerm"` block has `features {}`, and every resource sets its required arguments with
   valid enum values and correctly-typed attributes.
5. **Correct block vs. attribute syntax.** Nested blocks (e.g. `identity`, `site_config`,
   `ip_configuration`) use block syntax; scalars use `=`. No unsupported/renamed arguments for the
   pinned provider version.
6. **`tfvars` match variables.** Every value in `terraform.tfvars`/`*.tfvars` corresponds to a declared
   `variable`; every variable without a default is supplied.
7. **No secrets in code.** Secrets come from variables (`sensitive = true`) or Key Vault data sources,
   never hardcoded literals.

If `terraform` is unavailable, self-review every item above before presenting.
