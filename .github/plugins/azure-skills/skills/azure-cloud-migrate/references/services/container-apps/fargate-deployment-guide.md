# Deployment: Fargate to Container Apps

## Prerequisites

Azure CLI 2.53+ with `containerapp` extension, AWS CLI v2, Docker, ACR, Key Vault, Log Analytics

## Phase 1: Container Registry Migration

```bash
set -euo pipefail
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
az acr login --name "$ACR_NAME"
docker pull "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${IMAGE}"
docker tag "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${IMAGE}" "${ACR_NAME}.azurecr.io/${IMAGE}"
docker push "${ACR_NAME}.azurecr.io/${IMAGE}"
```

```powershell
$ErrorActionPreference = 'Stop'
$ecrPassword = aws ecr get-login-password --region $env:AWS_REGION
$ecrPassword | docker login --username AWS --password-stdin "$($env:AWS_ACCOUNT_ID).dkr.ecr.$($env:AWS_REGION).amazonaws.com"
az acr login --name $env:ACR_NAME
docker pull "$($env:AWS_ACCOUNT_ID).dkr.ecr.$($env:AWS_REGION).amazonaws.com/$($env:IMAGE)"
docker tag "$($env:AWS_ACCOUNT_ID).dkr.ecr.$($env:AWS_REGION).amazonaws.com/$($env:IMAGE)" "$($env:ACR_NAME).azurecr.io/$($env:IMAGE)"
docker push "$($env:ACR_NAME).azurecr.io/$($env:IMAGE)"
```

## Phase 2: Infrastructure

> Choose ONE path: basic (without VNet) OR VNet-integrated.

### Basic (no VNet)

```bash
set -euo pipefail
az group create --name "$RG" --location "$LOCATION"
az monitor log-analytics workspace create -g "$RG" -n "${RG}-logs" -l "$LOCATION"
LOG_ID=$(az monitor log-analytics workspace show -g "$RG" -n "${RG}-logs" --query customerId -o tsv)
# Keyless (recommended): avoids handling the shared key entirely
az containerapp env create -n "${RG}-env" -g "$RG" -l "$LOCATION" \
  --logs-destination azure-monitor --logs-workspace-id "$LOG_ID"
# Fallback: use shared key if azure-monitor destination is not available
# LOG_KEY=$(az monitor log-analytics workspace get-shared-keys -g "$RG" -n "${RG}-logs" --query primarySharedKey -o tsv)
# az containerapp env create -n "${RG}-env" -g "$RG" -l "$LOCATION" \
#   --logs-workspace-id "$LOG_ID" --logs-workspace-key "$LOG_KEY"
```

```powershell
$ErrorActionPreference = 'Stop'
az group create --name $env:RG --location $env:LOCATION
az monitor log-analytics workspace create -g $env:RG -n "$($env:RG)-logs" -l $env:LOCATION
$logId = az monitor log-analytics workspace show -g $env:RG -n "$($env:RG)-logs" --query customerId -o tsv
# Keyless (recommended): avoids handling the shared key entirely
az containerapp env create -n "$($env:RG)-env" -g $env:RG -l $env:LOCATION `
  --logs-destination azure-monitor --logs-workspace-id $logId
# Fallback: use shared key if azure-monitor destination is not available
# $logKey = az monitor log-analytics workspace get-shared-keys -g $env:RG -n "$($env:RG)-logs" --query primarySharedKey -o tsv
# az containerapp env create -n "$($env:RG)-env" -g $env:RG -l $env:LOCATION `
#   --logs-workspace-id $logId --logs-workspace-key $logKey
```

### VNet-Integrated

```bash
set -euo pipefail
az group create --name "$RG" --location "$LOCATION"
az monitor log-analytics workspace create -g "$RG" -n "${RG}-logs" -l "$LOCATION"
LOG_ID=$(az monitor log-analytics workspace show -g "$RG" -n "${RG}-logs" --query customerId -o tsv)
az network vnet create -g "$RG" -n "${RG}-vnet" \
  --address-prefix 10.0.0.0/16 --subnet-name aca-subnet --subnet-prefix 10.0.0.0/23
SUBNET_ID=$(az network vnet subnet show -g "$RG" --vnet-name "${RG}-vnet" -n aca-subnet --query id -o tsv)
az containerapp env create -n "${RG}-env" -g "$RG" -l "$LOCATION" \
  --logs-destination azure-monitor --logs-workspace-id "$LOG_ID" \
  --infrastructure-subnet-resource-id "$SUBNET_ID"
```

```powershell
$ErrorActionPreference = 'Stop'
az group create --name $env:RG --location $env:LOCATION
az monitor log-analytics workspace create -g $env:RG -n "$($env:RG)-logs" -l $env:LOCATION
$logId = az monitor log-analytics workspace show -g $env:RG -n "$($env:RG)-logs" --query customerId -o tsv
az network vnet create -g $env:RG -n "$($env:RG)-vnet" `
  --address-prefix 10.0.0.0/16 --subnet-name aca-subnet --subnet-prefix 10.0.0.0/23
$subnet = az network vnet subnet show -g $env:RG --vnet-name "$($env:RG)-vnet" -n aca-subnet | ConvertFrom-Json
az containerapp env create -n "$($env:RG)-env" -g $env:RG -l $env:LOCATION `
  --logs-destination azure-monitor --logs-workspace-id $logId `
  --infrastructure-subnet-resource-id $subnet.id
```

## Phase 3: Secrets & Identity

```bash
set -euo pipefail
az keyvault create --name "$KEY_VAULT" -g "$RG" -l "$LOCATION" \
  --enable-rbac-authorization true
IDENTITY_ID=$(az identity create -n "${RG}-id" -g "$RG" -l "$LOCATION" --query id -o tsv)
PRINCIPAL_ID=$(az identity show --ids "$IDENTITY_ID" --query principalId -o tsv)

# Grant Key Vault access — use RBAC (recommended) or access policies
# Option A: RBAC (enabled on the vault created above)
KV_ID=$(az keyvault show --name "$KEY_VAULT" --query id -o tsv)
az role assignment create --assignee "$PRINCIPAL_ID" \
  --role "Key Vault Secrets User" --scope "$KV_ID"
# Option B: Access policies (if vault uses access policy mode)
# az keyvault set-policy --name "$KEY_VAULT" --object-id "$PRINCIPAL_ID" --secret-permissions get list

# Migrate secrets more safely: avoid passing the secret as a CLI argument.
# Use a locked-down temporary file, import with --file, and remove it immediately.
# Do not run this in shared, monitored, or recorded environments.
umask 077
secret_file="$(mktemp)"
trap 'rm -f "$secret_file"' EXIT
aws secretsmanager get-secret-value --secret-id <secret-id> --region <region> \
  --query SecretString --output text > "$secret_file"
az keyvault secret set --vault-name "$KEY_VAULT" --name <secret-name> \
  --file "$secret_file"
rm -f "$secret_file"
trap - EXIT

# ACR pull access
ACR_ID=$(az acr show --name "$ACR_NAME" --query id -o tsv)
az role assignment create --assignee "$PRINCIPAL_ID" --role AcrPull --scope "$ACR_ID"
```

```powershell
$ErrorActionPreference = 'Stop'
az keyvault create --name $env:KEY_VAULT -g $env:RG -l $env:LOCATION --enable-rbac-authorization true
$identityId = az identity create -n "$($env:RG)-id" -g $env:RG -l $env:LOCATION --query id -o tsv
$principalId = az identity show --ids $identityId --query principalId -o tsv

# Grant Key Vault access — use RBAC (recommended) or access policies
# Option A: RBAC (enabled on the vault created above)
$kvId = az keyvault show --name $env:KEY_VAULT --query id -o tsv
az role assignment create --assignee $principalId `
  --role "Key Vault Secrets User" --scope $kvId
# Option B: Access policies (if vault uses access policy mode)
# az keyvault set-policy --name $env:KEY_VAULT --object-id $principalId --secret-permissions get list

# Migrate secrets more safely: use a temp file instead of passing as CLI argument.
# Do not run this in shared, monitored, or recorded environments.
$secretFile = [System.IO.Path]::GetTempFileName()
try {
    aws secretsmanager get-secret-value --secret-id <secret-id> --region <region> `
      --query SecretString --output text | Set-Content -Path $secretFile -NoNewline
    az keyvault secret set --vault-name $env:KEY_VAULT --name <secret-name> `
      --file $secretFile
} finally {
    Remove-Item -Path $secretFile -Force -ErrorAction SilentlyContinue
}

# ACR pull access
$acrId = az acr show --name $env:ACR_NAME --query id -o tsv
az role assignment create --assignee $principalId --role AcrPull --scope $acrId
```

## Phase 4: Deploy

```bash
set -euo pipefail
SECRET_URI=$(az keyvault secret show --vault-name "$KEY_VAULT" --name db-password --query id -o tsv)
az containerapp create --name <app-name> -g "$RG" --environment "${RG}-env" \
  --image "${ACR_NAME}.azurecr.io/<image>:<tag>" --target-port 8080 --ingress external \
  --cpu 0.5 --memory 1Gi --min-replicas 1 --max-replicas 10 \
  --user-assigned "$IDENTITY_ID" --registry-identity "$IDENTITY_ID" \
  --registry-server "${ACR_NAME}.azurecr.io" \
  --secrets db-pass=keyvaultref:"${SECRET_URI}",identityref:"${IDENTITY_ID}" \
  --env-vars ENV=production DB_PASSWORD=secretref:db-pass
```

```powershell
$ErrorActionPreference = 'Stop'
$secretUri = az keyvault secret show --vault-name $env:KEY_VAULT --name db-password --query id -o tsv
az containerapp create --name <app-name> -g $env:RG --environment "$($env:RG)-env" `
  --image "$($env:ACR_NAME).azurecr.io/<image>:<tag>" --target-port 8080 --ingress external `
  --cpu 0.5 --memory 1Gi --min-replicas 1 --max-replicas 10 `
  --user-assigned $identityId --registry-identity $identityId `
  --registry-server "$($env:ACR_NAME).azurecr.io" `
  --secrets "db-pass=keyvaultref:$($secretUri),identityref:$($identityId)" `
  --env-vars ENV=production DB_PASSWORD=secretref:db-pass
```

### Configuration Mapping

| ECS Task Definition | Container Apps CLI |
|---------------------|--------------------|
| `cpu: "512"` (0.5 vCPU) | `--cpu 0.5` |
| `memory: "1024"` (1 GB) | `--memory 1Gi` |
| `containerPort: 8080` | `--target-port 8080` |
| `desiredCount: 2` | `--min-replicas 2` |
| `secrets` (Secrets Manager ARN) | `--secrets name=keyvaultref:URI,identityref:ID` |
| `environment` (env vars) | `--env-vars KEY=value` |

## Phase 5: Validate

```bash
set -euo pipefail
FQDN=$(az containerapp show --name <app-name> -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)
curl -f -I "https://$FQDN/health" || { echo "Health check failed"; exit 1; }
az containerapp logs show --name <app-name> -g "$RG" --tail 100
```

```powershell
$ErrorActionPreference = 'Stop'
$fqdn = az containerapp show --name <app-name> -g $env:RG --query properties.configuration.ingress.fqdn -o tsv
Invoke-WebRequest -Uri "https://$fqdn/health" -Method Head
az containerapp logs show --name <app-name> -g $env:RG --tail 100
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Image pull fails | Verify ACR role: `az role assignment list --assignee $(az identity show --ids <identity-resource-id> --query principalId -o tsv) --scope $(az acr show -n <acr-name> --query id -o tsv)` |
| App won't start | Check logs: `az containerapp logs show --name <app-name> -g <resource-group> --tail 100` |
| Secret not accessible | Verify RBAC: `az role assignment list --assignee $(az identity show --ids <identity-resource-id> --query principalId -o tsv) --scope $(az keyvault show -n <vault-name> --query id -o tsv)` |
