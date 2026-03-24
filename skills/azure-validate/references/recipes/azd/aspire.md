# Aspire Validation

> ⚠️ **Only load this file when the project is a .NET Aspire application.**

Validation steps specific to .NET Aspire projects deployed via AZD.

## Detection

A project is Aspire-based if any of these are true:

| Indicator | Check |
|-----------|-------|
| AppHost project | `find . -name "*.AppHost.csproj"` |
| Aspire.Hosting package | `grep -r "Aspire.Hosting" . --include="*.csproj"` |

**If none found → skip this file entirely.**

---

## Pre-Provisioning: Functions Secret Storage

> ⚠️ **CRITICAL — Must run BEFORE `azd provision`.**

Check if the project uses Azure Functions within Aspire and ensure `AzureWebJobsSecretStorageType` is configured.
See [Aspire Functions Secrets Reference](../../aspire-functions-secrets.md) for detection commands, fix examples, and full details.

**If `AddAzureFunctionsProject` is NOT found**, skip this section.

---

## Post-Provisioning: Container Apps Environment Variables

> ⚠️ **CRITICAL — Run AFTER `azd provision` but BEFORE `azd deploy`.**

When using Aspire with Container Apps in "limited mode" (in-memory infrastructure generation), `azd provision` creates Azure resources but doesn't automatically populate environment variables that `azd deploy` needs.

**Check if environment variables are set:**

```bash
azd env get-values | grep -E "AZURE_CONTAINER_REGISTRY_ENDPOINT|AZURE_CONTAINER_REGISTRY_MANAGED_IDENTITY_ID|MANAGED_IDENTITY_CLIENT_ID"
```

**If any are missing, set them now BEFORE running `azd deploy`:**

```bash
# Get resource group name
RG_NAME=$(azd env get-values | grep AZURE_RESOURCE_GROUP | cut -d'=' -f2 | tr -d '"')

# Set required variables
azd env set AZURE_CONTAINER_REGISTRY_ENDPOINT $(az acr list --resource-group "$RG_NAME" --query "[0].loginServer" -o tsv)
azd env set AZURE_CONTAINER_REGISTRY_MANAGED_IDENTITY_ID $(az identity list --resource-group "$RG_NAME" --query "[0].id" -o tsv)
azd env set MANAGED_IDENTITY_CLIENT_ID $(az identity list --resource-group "$RG_NAME" --query "[0].clientId" -o tsv)
```

**PowerShell:**
```powershell
# Get resource group name
$rgName = (azd env get-values | Select-String 'AZURE_RESOURCE_GROUP').Line.Split('=')[1].Trim('"')

# Set required variables
azd env set AZURE_CONTAINER_REGISTRY_ENDPOINT (az acr list --resource-group $rgName --query "[0].loginServer" -o tsv)
azd env set AZURE_CONTAINER_REGISTRY_MANAGED_IDENTITY_ID (az identity list --resource-group $rgName --query "[0].id" -o tsv)
azd env set MANAGED_IDENTITY_CLIENT_ID (az identity list --resource-group $rgName --query "[0].clientId" -o tsv)
```

**Why this is needed:** Aspire's "limited mode" generates infrastructure in-memory. While `azd provision` creates all necessary Azure resources (Container Registry, Managed Identity, Container Apps Environment), it doesn't populate the environment variables that reference those resources. The `azd deploy` phase requires these variables to authenticate with the container registry and configure managed identity bindings.
