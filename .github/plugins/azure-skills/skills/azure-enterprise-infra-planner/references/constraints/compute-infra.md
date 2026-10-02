# Compute (IaaS) Pairing Constraints

### AKS Cluster

| Paired With | Constraint |
|-------------|------------|
| **VNet / Subnet** | With Azure CNI, subnet must have enough IPs for nodes + pods (30 pods/node default × node count). Subnet cannot have other delegations. Reserved CIDR ranges cannot be used: `169.254.0.0/16`, `172.30.0.0/16`, `172.31.0.0/16`, `192.0.2.0/24`. |
| **Pod CIDR** | Pod CIDR must not overlap with cluster subnet, peered VNets, ExpressRoute, or VPN address spaces. Overlapping causes SNAT/routing issues. |
| **kubenet** | Kubenet uses NAT — subnet only needs IPs for nodes. Less IP pressure but no direct pod-to-VNet connectivity. Kubenet is retiring March 2028 — migrate to CNI Overlay. Not supported by Application Gateway for Containers. |
| **CNI Overlay** | CNI Overlay does not support VM availability sets (must use VMSS-based node pools), virtual nodes, or DCsv2-series VMs (use DCasv5/DCadsv5 instead). |
| **Dual-stack CNI Overlay** | IPv4+IPv6 dual-stack disables Azure/Calico network policies, NAT gateway, and virtual nodes. |
| **Key Vault** | Enable `azureKeyvaultSecretsProvider` addon. Use `enableRbacAuthorization: true` on Key Vault with managed identity. |
| **Container Registry** | Attach ACR via `acrPull` role assignment on cluster identity, or use `imagePullSecrets`. |
| **Log Analytics** | Enable `omsagent` addon with `config.logAnalyticsWorkspaceResourceID` pointing to workspace. |
| **Load Balancer** | AKS creates a managed Standard LB by default (`loadBalancerSku: 'standard'`). |
| **System Pool** | At least one agent pool must have `mode: 'System'`. System pools run critical pods (CoreDNS, tunnelfront). |

### Availability Set

| Paired With | Constraint |
|-------------|------------|
| **Virtual Machine** | VMs must be in the same resource group. Set `vm.properties.availabilitySet.id`. |
| **Availability Zones** | Cannot combine with zones — availability zones supersede availability sets for zone-redundant architectures. |
| **Managed Disks** | `sku.name` must be `Aligned` when VMs use managed disks. |
| **VM Scale Set** | A VM cannot be in both an availability set and a VMSS. |

### Managed Disk

| Paired With | Constraint |
|-------------|------------|
| **Virtual Machine** | Attach via `storageProfile.osDisk` or `storageProfile.dataDisks`. Disk must be in same region. |
| **Availability Zone** | `PremiumV2_LRS` and `UltraSSD_LRS` require zone specification. |
| **Premium SSD v2** | Cannot be used as OS disk (data disks only). Does not support host caching (`ReadOnly`/`ReadWrite` unavailable). Requires zonal VM deployment. Cannot mix with other storage types on SQL Server VMs. |
| **Key Vault (CMK)** | Requires a Disk Encryption Set pointing to Key Vault key. Key Vault must have purge protection enabled. |

### Virtual Machine

| Paired With | Constraint |
|-------------|------------|
| **NIC** | At least one NIC required via `networkProfile.networkInterfaces`. NIC must be in the same region. |
| **Availability Set** | Cannot combine with `virtualMachineScaleSet` or availability zones. Set `availabilitySet.id`. |
| **Availability Zone** | Cannot combine with availability sets. Set `zones: ['1']` (string array). |
| **Managed Disk (Premium SSD)** | Not all VM sizes support Premium storage — check size docs for compatibility. |
| **Managed Disk (UltraSSD)** | Requires `additionalCapabilities.ultraSSDEnabled: true`. Cannot enable on a running VM — requires stop/deallocate first. |
| **Managed Disk (Premium SSD v2)** | Premium SSD v2 cannot be used as OS disk (data disks only). Does not support host caching (ReadOnly/ReadWrite unavailable). Requires zonal VM deployment. Cannot mix Premium SSD v2 with other storage types on SQL Server VMs. |
| **Dedicated Host** | Cannot specify both `host` and `hostGroup`. |
| **Boot Diagnostics Storage** | Cannot use Premium or ZRS storage. Use `Standard_LRS` or `Standard_GRS`. |
| **CNI Overlay (AKS)** | DCsv2-series VMs are not supported with Azure CNI Overlay. Use DCasv5/DCadsv5 for confidential computing. |

### VM Scale Set

| Paired With | Constraint |
|-------------|------------|
| **Subnet** | Network interfaces defined inline in `virtualMachineProfile.networkProfile`. Subnet must be in same region. |
| **Load Balancer** | Reference backend pool ID in NIC IP configuration. |
| **Orchestration Mode** | `Flexible` is the modern default. `Uniform` requires `upgradePolicy`. |
| **Availability Zone** | Set `zones: ['1', '2', '3']` for zone distribution. Cannot combine with availability sets. |
