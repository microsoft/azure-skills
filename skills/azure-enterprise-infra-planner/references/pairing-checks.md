# Property & Pairing Checks

Cross-check each new resource's properties against **every already-written resource** it connects to. Only run the checks relevant to this resource's type. Consult the resource file's **Pairing Constraints** section for type-specific rules.

## SKU Compatibility

| # | Check | Fix |
|---|-------|-----|
| 1 | Public IP SKU matches Load Balancer SKU (both Standard or both Basic) | Align to Standard (Basic retiring Sep 2025) |
| 2 | Application Gateway v1/v2 on separate subnets; v2 if zone redundancy, autoscaling, or Key Vault integration needed | Upgrade to v2 or split subnets |
| 3 | VPN Gateway SKU supports required features (BGP, IPv6, coexistence) — not Basic if any advanced feature is needed | Upgrade SKU |
| 4 | App Service Plan SKU meets feature requirements (VNet integration ≥ Basic, slots ≥ Standard, isolation ≥ IsolatedV2) | Upgrade plan SKU |
| 5 | Redis Cache tier supports required features (VNet injection = Premium, clustering = Premium/Enterprise) | Upgrade tier |

## Subnet & Network Conflicts

| # | Check | Fix |
|---|-------|-----|
| 1 | No already-written service with exclusive subnet requirements shares the same subnet as this resource | Assign a separate subnet |
| 2 | Subnet delegation matches service requirement — delegated for App Service/Container Apps Workload Profiles; NOT delegated for AKS, Consumption-only Container Apps | Fix delegation setting |
| 3 | App Service VNet Integration subnet ≠ App Service Private Endpoint subnet | Split into two subnets |
| 4 | Subnet CIDR size meets minimum (/26 for Firewall/Bastion, /27 for Gateway/Container Apps WP, /23 for Container Apps Consumption) | Expand CIDR |
| 5 | GatewaySubnet has no NSG; AzureBastionSubnet has an NSG | Add or remove NSG resource |

## Storage Pairing

| # | Check | Fix |
|---|-------|-----|
| 1 | Functions storage account uses `StorageV2` or `Storage` kind (not BlobStorage/BlockBlob/FileStorage) | Change `kind` to `StorageV2` |
| 2 | Functions on Consumption plan do not reference network-secured storage | Remove network rules or upgrade to Premium plan |
| 3 | Zone-redundant Functions use ZRS storage (not LRS/GRS) | Change storage SKU to `Standard_ZRS` |
| 4 | VM boot diagnostics storage is not Premium or ZRS | Use `Standard_LRS` or `Standard_GRS` |

## Cosmos DB

| # | Check | Fix |
|---|-------|-----|
| 1 | Multi-region writes + Strong consistency not configured together | Switch to Session consistency or single-region writes |
| 2 | Serverless accounts are single-region only, no shared-throughput databases | Remove multi-region config or switch to provisioned throughput |

## Key Vault & CMK

| # | Check | Fix |
|---|-------|-----|
| 1 | Any service using CMK has its Key Vault with `enableSoftDelete: true` and `enablePurgeProtection: true` | Add properties to Key Vault (or fix the already-written Key Vault entry) |
| 2 | CMK at storage creation uses user-assigned managed identity (not system-assigned) | Add a user-assigned identity resource before this resource |

## SQL Database

| # | Check | Fix |
|---|-------|-----|
| 1 | Zone redundancy not configured on Basic/Standard DTU tiers | Upgrade to Premium, Business Critical, or GP vCore |
| 2 | Hyperscale zone-redundant elastic pools use ZRS/GZRS backup storage | Set backup storage redundancy |

## AKS Networking

| # | Check | Fix |
|---|-------|-----|
| 1 | Pod CIDR does not overlap with cluster subnet, peered VNets, or gateway ranges already in the plan | Adjust CIDR |
| 2 | Reserved CIDR ranges (169.254.0.0/16, 172.30.0.0/16, 172.31.0.0/16, 192.0.2.0/24) not used | Change to allowed range |
| 3 | CNI Overlay not combined with VM availability sets, virtual nodes, or DCsv2 VMs | Switch CNI plugin or VM series |
