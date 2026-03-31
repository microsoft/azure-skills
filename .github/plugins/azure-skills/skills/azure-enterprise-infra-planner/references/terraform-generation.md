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
