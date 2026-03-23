# Compute (IaaS) Resources

| Resource | ARM Type | API Version | CAF Prefix | Naming Scope | Region |
|----------|----------|-------------|------------|--------------|--------|
| AKS Cluster | `Microsoft.ContainerService/managedClusters` | `2025-05-01` | `aks` | Resource group | Foundational |
| Availability Set | `Microsoft.Compute/availabilitySets` | `2024-11-01` | `avail` | Resource group | Foundational |
| Managed Disk | `Microsoft.Compute/disks` | `2025-01-02` | `osdisk`/`disk` | Resource group | Foundational |
| Virtual Machine | `Microsoft.Compute/virtualMachines` | `2024-11-01` | `vm` | Resource group | Foundational |
| VM Scale Set | `Microsoft.Compute/virtualMachineScaleSets` | `2024-11-01` | `vmss` | Resource group | Foundational |

## Documentation

| Resource | Bicep Reference | Service Overview | Naming Rules | Additional |
|----------|----------------|------------------|--------------|------------|
| AKS Cluster | [2025-05-01](https://learn.microsoft.com/azure/templates/microsoft.containerservice/managedclusters?pivots=deployment-language-bicep) | [AKS overview](https://learn.microsoft.com/azure/aks/intro-kubernetes) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftcontainerservice) | [Networking concepts](https://learn.microsoft.com/azure/aks/concepts-network) |
| Availability Set | [2024-11-01](https://learn.microsoft.com/azure/templates/microsoft.compute/availabilitysets?pivots=deployment-language-bicep) | [Overview](https://learn.microsoft.com/azure/virtual-machines/availability-set-overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftcompute) | — |
| Managed Disk | [2025-01-02](https://learn.microsoft.com/azure/templates/microsoft.compute/disks?pivots=deployment-language-bicep) | [Managed disks overview](https://learn.microsoft.com/azure/virtual-machines/managed-disks-overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftcompute) | — |
| Virtual Machine | [2024-11-01](https://learn.microsoft.com/azure/templates/microsoft.compute/virtualmachines?pivots=deployment-language-bicep) | [VMs overview](https://learn.microsoft.com/azure/virtual-machines/overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftcompute) | [VM sizes](https://learn.microsoft.com/azure/virtual-machines/sizes/overview) |
| VM Scale Set | [2024-11-01](https://learn.microsoft.com/azure/templates/microsoft.compute/virtualmachinescalesets?pivots=deployment-language-bicep) | [VMSS overview](https://learn.microsoft.com/azure/virtual-machine-scale-sets/overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftcompute) | — |
