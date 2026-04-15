# Static Web Apps — Terraform Patterns — REFERENCE ONLY

> ⛔ **DO NOT COPY THIS CODE DIRECTLY**
>
> This file contains **reference patterns** for understanding Azure Static Web Apps Terraform structure.
> Infrastructure for Static Web Apps must be composed using the Azure Prepare skill workflow, not copied directly from this reference.
>
> When composing infrastructure:
> - Start from an approved base template for Static Web Apps defined by your platform or template team.
> - Use `azurerm_static_web_app` — **NEVER** use Storage Account `static_website` for static web app hosting.
>
> Hand-writing Terraform from these patterns will result in missing tags, broken azd deploy, and policy violations.

> ⚠️ **WARNING: Do NOT use Storage Account static website hosting.**
> Storage Account `static_website` requires anonymous blob access, which violates
> enterprise Azure Policies (`RequestDisallowedByPolicy: "Anonymous blob access is not allowed"`).
> Always use `azurerm_static_web_app` instead — it is fully managed and policy-compliant.

## Basic Resource

```hcl
resource "azurerm_static_web_app" "web" {
  name                = "swa-${var.environment_name}-${var.service_name}-${var.unique_hash}"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location

  # sku_tier defaults to "Free"; set to "Standard" for production features
  sku_tier = "Standard"

  # Required for azd deploy to find this resource
  tags = merge(var.tags, {
    "azd-service-name" = var.service_name
  })
}
```

> ⚠️ **Region availability is limited.** Check [region-availability.md](region-availability.md) before selecting a region.

> 💡 **Key Points:**
> - No Storage Account, Service Plan, or other supporting resources required
> - Static Web Apps is a fully managed service — storage is built-in
> - The `azd-service-name` tag is **required** for `azd deploy` to locate the resource

## Custom Domain

```hcl
resource "azurerm_static_web_app_custom_domain" "example" {
  static_web_app_id = azurerm_static_web_app.web.id
  domain_name       = "www.example.com"
  validation_type   = "cname-delegation"
}
```

## Application Settings

For the integrated API backend:

```hcl
resource "azurerm_static_web_app_function_app_registration" "api" {
  static_web_app_id = azurerm_static_web_app.web.id
  function_app_id   = azurerm_linux_function_app.api.id
}
```

Environment variables for the SWA (available to both frontend and managed Functions API):

```hcl
resource "azurerm_static_web_app" "web" {
  # ... (base configuration from above)

  app_settings = {
    "DATABASE_URL" = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.kv.name};SecretName=db-url)"
  }
}
```

## Outputs

```hcl
output "WEB_URL" {
  value = azurerm_static_web_app.web.default_host_name
}

output "STATIC_WEB_APP_NAME" {
  value = azurerm_static_web_app.web.name
}
```

> 💡 **Tip:** Output names in UPPERCASE are automatically set as azd environment variables.

## Deployment Token

> ⚠️ **Security Warning:** Do NOT expose deployment tokens in Terraform outputs.

See [deployment.md](deployment.md) for secure token handling.

## azure.yaml Integration

```yaml
services:
  web:
    project: ./src/web
    language: js
    host: staticwebapp
    dist: dist
```

## References

- [AZD + Terraform](../../recipes/azd/terraform.md) — Full azd+Terraform project setup
- [Region Availability](region-availability.md) — SWA is NOT available in all regions
- [Routing and Auth](routing.md)
- [Deployment](deployment.md)
