# Networking (Core) Resources

| Resource | ARM Type | API Version | CAF Prefix | Naming Scope | Region |
|----------|----------|-------------|------------|--------------|--------|
| Virtual Network | `Microsoft.Network/virtualNetworks` | `2024-07-01` | `vnet` | Resource group | Foundational |
| Subnet | `Microsoft.Network/virtualNetworks/subnets` | `2024-07-01` | `snet` | Parent VNet | Foundational |
| NSG | `Microsoft.Network/networkSecurityGroups` | `2024-07-01` | `nsg` | Resource group | Foundational |
| Route Table | `Microsoft.Network/routeTables` | `2024-07-01` | `rt` | Resource group | Foundational |
| Network Interface | `Microsoft.Network/networkInterfaces` | `2024-07-01` | `nic` | Resource group | Foundational |
| Public IP | `Microsoft.Network/publicIPAddresses` | `2024-07-01` | `pip` | Resource group | Foundational |
| NAT Gateway | `Microsoft.Network/natGateways` | `2024-07-01` | `ng` | Resource group | Foundational |

## Documentation

| Resource | Bicep Reference | Service Overview | Naming Rules | Additional |
|----------|----------------|------------------|--------------|------------|
| Virtual Network | [2024-07-01](https://learn.microsoft.com/azure/templates/microsoft.network/virtualnetworks?pivots=deployment-language-bicep) | [VNet overview](https://learn.microsoft.com/azure/virtual-network/virtual-networks-overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftnetwork) | [VNet planning](https://learn.microsoft.com/azure/virtual-network/virtual-network-vnet-plan-design-arm) |
| Subnet | [2024-07-01](https://learn.microsoft.com/azure/templates/microsoft.network/virtualnetworks/subnets?pivots=deployment-language-bicep) | [Subnets](https://learn.microsoft.com/azure/virtual-network/virtual-network-manage-subnet) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftnetwork) | [Subnet delegation](https://learn.microsoft.com/azure/virtual-network/subnet-delegation-overview) |
| NSG | [2024-07-01](https://learn.microsoft.com/azure/templates/microsoft.network/networksecuritygroups?pivots=deployment-language-bicep) | [NSG overview](https://learn.microsoft.com/azure/virtual-network/network-security-groups-overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftnetwork) | [Security rules](https://learn.microsoft.com/azure/virtual-network/network-security-group-how-it-works) |
| Route Table | [2024-07-01](https://learn.microsoft.com/azure/templates/microsoft.network/routetables?pivots=deployment-language-bicep) | [Traffic routing](https://learn.microsoft.com/azure/virtual-network/virtual-networks-udr-overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftnetwork) | [Forced tunneling](https://learn.microsoft.com/azure/vpn-gateway/vpn-gateway-forced-tunneling-rm) |
| Network Interface | [2024-07-01](https://learn.microsoft.com/azure/templates/microsoft.network/networkinterfaces?pivots=deployment-language-bicep) | [NIC overview](https://learn.microsoft.com/azure/virtual-network/virtual-network-network-interface) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftnetwork) | [Accelerated networking](https://learn.microsoft.com/azure/virtual-network/accelerated-networking-overview) |
| Public IP | [2024-07-01](https://learn.microsoft.com/azure/templates/microsoft.network/publicipaddresses?pivots=deployment-language-bicep) | [Public IP overview](https://learn.microsoft.com/azure/virtual-network/ip-services/public-ip-addresses) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftnetwork) | [Basic SKU retirement](https://learn.microsoft.com/azure/virtual-network/ip-services/public-ip-basic-upgrade-guidance) |
| NAT Gateway | [2024-07-01](https://learn.microsoft.com/azure/templates/microsoft.network/natgateways?pivots=deployment-language-bicep) | [NAT Gateway overview](https://learn.microsoft.com/azure/nat-gateway/nat-overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftnetwork) | [Availability zones](https://learn.microsoft.com/azure/nat-gateway/nat-availability-zones) |
