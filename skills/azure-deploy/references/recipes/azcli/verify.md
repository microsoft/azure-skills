# Azure CLI Verification

```bash
az resource list --resource-group <rg-name> --output table
```

## Health Check

```bash
curl -s https://<endpoint>/health | jq .
```

## Container Apps

```bash
az containerapp revision list \
  --name <app-name> \
  --resource-group <rg-name> \
  --query "[].{name:name, active:properties.active}" \
  --output table
```

## App Service

```bash
az webapp show \
  --name <app-name> \
  --resource-group <rg-name> \
  --query "{state:state, hostNames:hostNames}"
```

## Report Results to User

> ⛔ **MANDATORY** — You **MUST** present the deployed endpoint URLs to the user in your response.

Extract endpoints using the appropriate command for the service type:

```bash
# Container Apps
az containerapp show --name <app-name> --resource-group <rg-name> --query "properties.configuration.ingress.fqdn" -o tsv

# App Service
az webapp show --name <app-name> --resource-group <rg-name> --query "defaultHostName" -o tsv
```

Present a summary including all service URLs. Do NOT end your response without including them.
