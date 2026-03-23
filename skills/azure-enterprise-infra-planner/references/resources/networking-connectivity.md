# Networking (Connectivity) Resources

| Resource | ARM Type | API Version | CAF Prefix | Naming Scope | Region |
|----------|----------|-------------|------------|--------------|--------|
| Azure Bastion | `Microsoft.Network/bastionHosts` | `2024-07-01` | `bas` | Resource group | Mainstream |
| Azure Firewall | `Microsoft.Network/azureFirewalls` | `2024-07-01` | `afw` | Resource group | Mainstream |
| DNS Zone | `Microsoft.Network/dnsZones` | `2018-05-01` | *(domain)* | Resource group | Foundational |
| VPN Gateway | `Microsoft.Network/virtualNetworkGateways` | `2024-07-01` | `vpng` | Resource group | Foundational |
| Private DNS Zone | `Microsoft.Network/privateDnsZones` | `2024-06-01` | *(domain)* | Resource group | Foundational |
| Private Endpoint | `Microsoft.Network/privateEndpoints` | `2024-07-01` | `pep` | Resource group | Foundational |

## Documentation

| Resource | Bicep Reference | Service Overview | Naming Rules | Additional |
|----------|----------------|------------------|--------------|------------|
| Azure Bastion | [2024-07-01](https://learn.microsoft.com/azure/templates/microsoft.network/bastionhosts?pivots=deployment-language-bicep) | [Bastion overview](https://learn.microsoft.com/azure/bastion/bastion-overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftnetwork) | [Configuration settings](https://learn.microsoft.com/azure/bastion/configuration-settings) |
| Azure Firewall | [2024-07-01](https://learn.microsoft.com/azure/templates/microsoft.network/azurefirewalls?pivots=deployment-language-bicep) | [Firewall overview](https://learn.microsoft.com/azure/firewall/overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftnetwork) | [SKU comparison](https://learn.microsoft.com/azure/firewall/choose-firewall-sku) |
| DNS Zone | [2018-05-01](https://learn.microsoft.com/azure/templates/microsoft.network/dnszones?pivots=deployment-language-bicep) | [Azure DNS overview](https://learn.microsoft.com/azure/dns/dns-overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftnetwork) | [Delegate a domain](https://learn.microsoft.com/azure/dns/dns-delegate-domain-azure-dns) |
| VPN Gateway | [2024-07-01](https://learn.microsoft.com/azure/templates/microsoft.network/virtualnetworkgateways?pivots=deployment-language-bicep) | [VPN Gateway overview](https://learn.microsoft.com/azure/vpn-gateway/vpn-gateway-about-vpngateways) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftnetwork) | [Gateway SKUs](https://learn.microsoft.com/azure/vpn-gateway/vpn-gateway-about-vpn-gateway-settings#gwsku) |
| Private DNS Zone | [2024-06-01](https://learn.microsoft.com/azure/templates/microsoft.network/privatednszones?pivots=deployment-language-bicep) | [Private DNS overview](https://learn.microsoft.com/azure/dns/private-dns-overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftnetwork) | [PE DNS config](https://learn.microsoft.com/azure/private-link/private-endpoint-dns) |
| Private Endpoint | [2024-07-01](https://learn.microsoft.com/azure/templates/microsoft.network/privateendpoints?pivots=deployment-language-bicep) | [PE overview](https://learn.microsoft.com/azure/private-link/private-endpoint-overview) | [Naming rules](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules#microsoftnetwork) | [DNS zone values](https://learn.microsoft.com/azure/private-link/private-endpoint-dns) |
