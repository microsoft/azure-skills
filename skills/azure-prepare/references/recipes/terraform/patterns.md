# Terraform Patterns

Common patterns for Terraform Azure deployments.

## File Structure

```
infra/
├── main.tf             # Main resources
├── variables.tf        # Variable definitions
├── outputs.tf          # Output values
├── terraform.tfvars    # Variable values
├── backend.tf          # State backend
└── modules/
    └── ...
```

## Provider Configuration

```hcl
# backend.tf
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    azurecaf = {
      source  = "aztfmod/azurecaf"
      version = "~> 1.2"
    }
  }

  backend "azurerm" {
    resource_group_name  = "rg-terraform-state"
    storage_account_name = "tfstate<unique>"
    container_name       = "tfstate"
    key                  = "app.terraform.tfstate"
  }
}

provider "azurerm" {
  features {}
}
```

## Variables

```hcl
# variables.tf
variable "environment" {
  type        = string
  description = "Environment name"
}

variable "location" {
  type        = string
  description = "Azure region"
  default     = "eastus2"
}
```

## Main Configuration

```hcl
# main.tf
resource "azurerm_resource_group" "main" {
  name     = "rg-${var.environment}"
  location = var.location
  tags     = { environment = var.environment }
}

module "app" {
  source              = "./modules/app"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  environment         = var.environment
}
```

## Outputs

```hcl
# outputs.tf
output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "app_url" {
  value = module.app.url
}
```

## Naming with Azure CAF

```hcl
resource "azurecaf_name" "storage" {
  name          = var.environment
  resource_type = "azurerm_storage_account"
  random_length = 5
}

resource "azurerm_storage_account" "main" {
  name = azurecaf_name.storage.result
  # ...
}
```

## State Backend Setup

```bash
# Create state storage
az group create --name rg-terraform-state --location eastus2

az storage account create \
  --name tfstate<unique> \
  --resource-group rg-terraform-state \
  --sku Standard_LRS

az storage container create \
  --name tfstate \
  --account-name tfstate<unique>
```

## Security Requirements

| Requirement | Pattern |
|-------------|---------|
| No hardcoded secrets | Use Key Vault data sources |
| Managed Identity | `identity { type = "UserAssigned" }` |
| State encryption | Azure Storage encryption |
| State locking | Azure Blob lease |

## Container Apps with ACR

> **⚠️ Two-Phase Deployment Required.** See [Container Apps Terraform Patterns](../../services/container-apps/terraform.md) for full details.

Use a **public placeholder image** during initial provisioning. Never reference an ACR image that hasn't been built yet. Do **not** use `admin_enabled` on the ACR or add a `registry` block with `username`/`password_secret_name` — use managed identity instead.

```hcl
resource "azurerm_container_app" "api" {
  # ...
  template {
    container {
      name   = "api"
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      # ...
    }
  }

  # Prevent Terraform from reverting post-apply image and registry updates
  lifecycle {
    ignore_changes = [
      template[0].container[0].image,
      registry,
    ]
  }
}
```

After `terraform apply`, build the real image and update the Container App via CLI — see the **azure-deploy** skill's `references/recipes/terraform/README.md` (Container Apps Two-Phase Deployment section).
