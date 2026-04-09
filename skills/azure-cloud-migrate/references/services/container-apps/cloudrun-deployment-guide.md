# Deployment: Cloud Run to Container Apps

## Prerequisites

Azure CLI 2.53+, gcloud CLI, Docker, ACR, Key Vault, Log Analytics

## Phase 1: Image Migration

### Bash

```bash
set -euo pipefail
GCP_PROJECT="${GCP_PROJECT:-<project>}"
GCP_REGION="${GCP_REGION:-<region>}"
ACR_NAME="${ACR_NAME:-<acr>}"

gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev"
az acr login --name "$ACR_NAME"
for img in "app:v1" "worker:v1"; do
  docker pull "${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT}/<repo>/$img"
  docker tag "${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT}/<repo>/$img" "${ACR_NAME}.azurecr.io/$img"
  docker push "${ACR_NAME}.azurecr.io/$img"
done
```

### PowerShell

```powershell
$GCP_PROJECT = if ($env:GCP_PROJECT) { $env:GCP_PROJECT } else { "<project>" }
$GCP_REGION = if ($env:GCP_REGION) { $env:GCP_REGION } else { "<region>" }
$ACR_NAME = if ($env:ACR_NAME) { $env:ACR_NAME } else { "<acr>" }

gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev"
az acr login --name $ACR_NAME
@("app:v1", "worker:v1") | ForEach-Object {
  docker pull "${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT}/<repo>/$_"
  docker tag "${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT}/<repo>/$_" "${ACR_NAME}.azurecr.io/$_"
  docker push "${ACR_NAME}.azurecr.io/$_"
}
```

## Phase 2: Infrastructure

> Choose ONE path: basic (without VNet) OR VNet-integrated.

### Basic (no VNet)

#### Bash

```bash
set -euo pipefail
az group create --name "$RG" --location "$LOCATION"
az monitor log-analytics workspace create -g "$RG" -n "${RG}-logs" -l "$LOCATION"
LOG_ID=$(az monitor log-analytics workspace show -g "$RG" -n "${RG}-logs" --query customerId -o tsv)
LOG_KEY=$(az monitor log-analytics workspace get-shared-keys -g "$RG" -n "${RG}-logs" --query primarySharedKey -o tsv)
az containerapp env create -n "${RG}-env" -g "$RG" -l "$LOCATION" \
  --logs-workspace-id "$LOG_ID" --logs-workspace-key "$LOG_KEY"
```

#### PowerShell

```powershell
az group create --name $RG --location $LOCATION
az monitor log-analytics workspace create -g $RG -n "${RG}-logs" -l $LOCATION
$workspace = az monitor log-analytics workspace show -g $RG -n "${RG}-logs" | ConvertFrom-Json
$keys = az monitor log-analytics workspace get-shared-keys -g $RG -n "${RG}-logs" | ConvertFrom-Json
az containerapp env create -n "${RG}-env" -g $RG -l $LOCATION `
  --logs-workspace-id $workspace.customerId --logs-workspace-key $keys.primarySharedKey
```

### VNet-Integrated

#### Bash

```bash
set -euo pipefail
az network vnet create -g "$RG" -n "${RG}-vnet" \
  --address-prefix 10.0.0.0/16 --subnet-name aca-subnet --subnet-prefix 10.0.0.0/23
SUBNET_ID=$(az network vnet subnet show -g "$RG" --vnet-name "${RG}-vnet" -n aca-subnet --query id -o tsv)
az containerapp env create -n "${RG}-env" -g "$RG" -l "$LOCATION" \
  --logs-workspace-id "$LOG_ID" --logs-workspace-key "$LOG_KEY" \
  --infrastructure-subnet-resource-id "$SUBNET_ID"
```

#### PowerShell

```powershell
az network vnet create -g $RG -n "${RG}-vnet" `
  --address-prefix 10.0.0.0/16 --subnet-name aca-subnet --subnet-prefix 10.0.0.0/23
$subnet = az network vnet subnet show -g $RG --vnet-name "${RG}-vnet" -n aca-subnet | ConvertFrom-Json
az containerapp env create -n "${RG}-env" -g $RG -l $LOCATION `
  --logs-workspace-id $workspace.customerId --logs-workspace-key $keys.primarySharedKey `
  --infrastructure-subnet-resource-id $subnet.id
```

## Phase 3: Secrets & Identity

### Bash

```bash
set -euo pipefail
az keyvault create --name "$KEY_VAULT" -g "$RG" -l "$LOCATION"
IDENTITY_ID=$(az identity create -n "${RG}-id" -g "$RG" -l "$LOCATION" --query id -o tsv)
PRINCIPAL_ID=$(az identity show --ids "$IDENTITY_ID" --query principalId -o tsv)

# Grant Key Vault access — use RBAC (recommended) or access policies
# Option A: RBAC (default for new vaults)
KV_ID=$(az keyvault show --name "$KEY_VAULT" --query id -o tsv)
az role assignment create --assignee "$PRINCIPAL_ID" \
  --role "Key Vault Secrets User" --scope "$KV_ID"
# Option B: Access policies (if vault uses access-policy mode)
# az keyvault set-policy --name "$KEY_VAULT" --object-id "$PRINCIPAL_ID" --secret-permissions get list

# Migrate secrets without writing them to disk
az keyvault secret set --vault-name "$KEY_VAULT" --name <secret-name> \
  --value "$(gcloud secrets versions access latest --secret=<secret-id> --project="$GCP_PROJECT")"

# ACR pull access
ACR_ID=$(az acr show --name "$ACR_NAME" --query id -o tsv)
az role assignment create --assignee "$PRINCIPAL_ID" --role AcrPull --scope "$ACR_ID"
```

### PowerShell

```powershell
az keyvault create --name $KEY_VAULT -g $RG -l $LOCATION
$identity = az identity create -n "${RG}-id" -g $RG -l $LOCATION | ConvertFrom-Json
$principalId = (az identity show --ids $identity.id | ConvertFrom-Json).principalId

# Grant Key Vault access — RBAC (recommended)
$kvId = (az keyvault show --name $KEY_VAULT | ConvertFrom-Json).id
az role assignment create --assignee $principalId `
  --role "Key Vault Secrets User" --scope $kvId

# Migrate secrets without writing them to disk
$secretValue = gcloud secrets versions access latest --secret=<secret-id> --project=$GCP_PROJECT
az keyvault secret set --vault-name $KEY_VAULT --name <secret-name> --value $secretValue
Remove-Variable secretValue

# ACR pull access
$acrId = (az acr show --name $ACR_NAME | ConvertFrom-Json).id
az role assignment create --assignee $principalId --role AcrPull --scope $acrId
```

## Phase 4: Deploy Container App

### Bash

```bash
set -euo pipefail
SECRET_URI=$(az keyvault secret show --vault-name "$KEY_VAULT" --name db-pw --query id -o tsv)
az containerapp create \
  --name <app-name> -g "$RG" --environment "${RG}-env" \
  --image "${ACR_NAME}.azurecr.io/app:v1" --target-port 8080 --ingress external \
  --cpu 1.0 --memory 1Gi --min-replicas 0 --max-replicas 10 \
  --user-assigned "$IDENTITY_ID" --registry-identity "$IDENTITY_ID" \
  --registry-server "${ACR_NAME}.azurecr.io" \
  --secrets db-pw=keyvaultref:"${SECRET_URI}",identityref:"${IDENTITY_ID}" \
  --env-vars ENV=prod DB_PASSWORD=secretref:db-pw \
  --scale-rule-name http --scale-rule-type http --scale-rule-http-concurrency 80
```

### PowerShell

```powershell
$secret = az keyvault secret show --vault-name $KEY_VAULT --name db-pw | ConvertFrom-Json
az containerapp create `
  --name <app-name> -g $RG --environment "${RG}-env" `
  --image "${ACR_NAME}.azurecr.io/app:v1" --target-port 8080 --ingress external `
  --cpu 1.0 --memory 1Gi --min-replicas 0 --max-replicas 10 `
  --user-assigned $identity.id --registry-identity $identity.id `
  --registry-server "${ACR_NAME}.azurecr.io" `
  --secrets "db-pw=keyvaultref:$($secret.id),identityref:$($identity.id)" `
  --env-vars "ENV=prod" "DB_PASSWORD=secretref:db-pw" `
  --scale-rule-name http --scale-rule-type http --scale-rule-http-concurrency 80
```

### Configuration Mapping

| Cloud Run | Container Apps |
|-----------|----------------|
| `--min-instances 0` | `--min-replicas 0` |
| `--max-instances 10` | `--max-replicas 10` |
| `--concurrency 80` | `--scale-rule-http-concurrency 80` |
| `--cpu 1` | `--cpu 1.0` |
| `--memory 512Mi` | `--memory 1Gi` |

## Phase 5: Validation

### Bash

```bash
FQDN=$(az containerapp show --name <app-name> -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)
curl -I "https://$FQDN/health"
az containerapp logs show --name <app-name> -g "$RG" --tail 100
```

### PowerShell

```powershell
$app = az containerapp show --name <app-name> -g $RG | ConvertFrom-Json
Invoke-WebRequest -Uri "https://$($app.properties.configuration.ingress.fqdn)/health"
az containerapp logs show --name <app-name> -g $RG --tail 100
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Image pull fails | Verify ACR role: `az role assignment list --assignee $PRINCIPAL_ID --scope $ACR_ID -o table` |
| App won't start | Check logs: `az containerapp logs show --name <app> -g $RG --tail 100` |
| Secret not accessible | Verify RBAC: `az role assignment list --assignee $PRINCIPAL_ID --scope $KV_ID -o table` |
| Scaling not working | Check config: `az containerapp show --name <app> --query properties.template.scale` |
