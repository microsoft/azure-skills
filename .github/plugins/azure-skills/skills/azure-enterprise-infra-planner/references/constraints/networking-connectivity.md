# Networking (Connectivity) Pairing Constraints

### Azure Bastion

| Paired With | Constraint |
|-------------|------------|
| **VNet** | Requires a subnet named exactly `AzureBastionSubnet` with minimum /26 prefix. |
| **Developer SKU** | Does NOT require `AzureBastionSubnet` or public IP. Deploys as shared infrastructure. Only connects to VMs in the same VNet. |
| **Public IP** | Requires Standard SKU public IP with Static allocation. |
| **NSG** | NSG on `AzureBastionSubnet` requires mandatory inbound (HTTPS 443 from Internet, GatewayManager 443) and outbound rules (see [Bastion NSG docs](https://learn.microsoft.com/azure/bastion/bastion-nsg)). |
| **VMs** | Target VMs must be in the same VNet as Bastion (or peered VNets with Standard/Premium SKU). |

### Azure Firewall

| Paired With | Constraint |
|-------------|------------|
| **VNet** | Requires a subnet named exactly `AzureFirewallSubnet` with minimum /26 prefix. |
| **Basic Tier** | Additionally requires `AzureFirewallManagementSubnet` with /26 minimum and its own public IP. |
| **Public IP** | Requires Standard SKU public IP with Static allocation. |
| **Firewall Policy** | Cannot use both `firewallPolicy.id` and classic rule collections simultaneously. Policy tier must match or exceed firewall tier. |
| **Zones** | In zone-redundant mode, all associated public IPs must also be zone-redundant (Standard SKU). |
| **Virtual WAN** | `AZFW_Hub` SKU name must reference `virtualHub.id` instead of `ipConfigurations`. |

### VPN Gateway

| Paired With | Constraint |
|-------------|------------|
| **VNet** | Requires a subnet named exactly `GatewaySubnet` with minimum /27 prefix. Use /26+ for 16 ExpressRoute circuits or for ExpressRoute/VPN coexistence. |
| **Public IP** | Basic VPN SKU requires Basic public IP. VpnGw1+ requires Standard public IP. |
| **Active-Active** | Requires 2 public IPs and 2 IP configurations. Only supported with VpnGw1+. |
| **Zone-Redundant** | Must use `AZ` SKU variant (e.g., `VpnGw1AZ`). Requires Standard SKU public IPs. AZ SKU cannot be downgraded to non-AZ (one-way migration only). |
| **ExpressRoute** | Can coexist with VPN gateway on the same `GatewaySubnet` (requires /27 or larger). Not supported with Basic SKU. Route-based VPN required. |
| **PolicyBased** | Limited to 1 S2S tunnel, no P2S, no VNet-to-VNet. Use `RouteBased` for most scenarios. |
| **Basic SKU** | Basic VPN Gateway does not support BGP, IPv6, RADIUS authentication, IKEv2 P2S, or ExpressRoute coexistence. Max 10 S2S tunnels. |
| **GatewaySubnet UDR** | Do not apply UDR with `0.0.0.0/0` next hop on GatewaySubnet. ExpressRoute gateways require management controller access — this route breaks it. |
| **GatewaySubnet BGP** | BGP route propagation must remain enabled on GatewaySubnet. Disabling causes the gateway to become non-functional. |
| **DNS Private Resolver** | DNS Private Resolver in a VNet with an ExpressRoute gateway and wildcard forwarding rules can cause management connectivity problems. |

### DNS Zone

| Paired With | Constraint |
|-------------|------------|
| **Domain Registrar** | NS records from `properties.nameServers` must be configured at your domain registrar to delegate the domain to Azure DNS. |
| **App Service** | Create a CNAME record pointing to `{app-name}.azurewebsites.net` for custom domains. Add a TXT verification record. |
| **Front Door** | Create a CNAME record pointing to the Front Door endpoint. Add a `_dnsauth` TXT record for domain validation. |
| **Application Gateway** | Create an A record pointing to the Application Gateway public IP, or a CNAME to the public IP DNS name. |
| **Traffic Manager** | Create a CNAME record pointing to the Traffic Manager profile `{name}.trafficmanager.net`. |
| **Child Zones** | Delegate subdomains by creating NS records in the parent zone pointing to the child zone's Azure name servers. |

### Private DNS Zone

| Paired With | Constraint |
|-------------|------------|
| **Virtual Network** | Must create a `virtualNetworkLinks` child resource to link the DNS zone to each VNet that needs resolution. |
| **Private Endpoint** | Use a `privateDnsZoneGroups` child on the Private Endpoint to auto-register A records, or manually create A record sets. One DNS record per DNS name — multiple private endpoints in different regions need separate Private DNS Zones. |
| **VNet Link (auto-registration)** | Only one Private DNS Zone with `registrationEnabled: true` can be linked per VNet. Auto-registration creates DNS records for VMs in the VNet. |
| **Hub-Spoke VNet** | Link the Private DNS Zone to the hub VNet. Spoke VNets resolve via hub DNS forwarder or VNet link. |
| **PostgreSQL Flexible Server** | For Private Endpoint access, zone name is `privatelink.postgres.database.azure.com`. For VNet-integrated (private access) servers, the zone name is `{name}.postgres.database.azure.com` (not `privatelink.*`). Referenced via `properties.network.privateDnsZoneArmResourceId`. |
| **MySQL Flexible Server** | For Private Endpoint access, zone name is `privatelink.mysql.database.azure.com`. For VNet-integrated (private access) servers, the zone name is `{name}.mysql.database.azure.com` (not `privatelink.*`). Referenced via `properties.network.privateDnsZoneResourceId`. |

### Private Endpoint

| Paired With | Constraint |
|-------------|------------|
| **Subnet** | The subnet must not have NSG rules that block private endpoint traffic. Subnet must have `privateEndpointNetworkPolicies` set to `Disabled` (default) for network policies to be bypassed. |
| **Private DNS Zone** | Create a `Microsoft.Network/privateDnsZones/virtualNetworkLinks` to link the DNS zone to the VNet. Create an A record or use a private DNS zone group to auto-register DNS. |
| **Private DNS Zone Group** | Use `privateEndpoint/privateDnsZoneGroups` child resource to auto-register DNS records in the Private DNS Zone. |
| **Key Vault** | Group ID: `vault`. DNS zone: `privatelink.vaultcore.azure.net`. |
| **Storage Account** | Group IDs: `blob`, `file`, `queue`, `table`, `web`, `dfs`. Each requires its own PE and DNS zone. |
| **SQL Server** | Group ID: `sqlServer`. DNS zone: `privatelink.database.windows.net`. |
| **Container Registry** | Group ID: `registry`. DNS zone: `privatelink.azurecr.io`. |
