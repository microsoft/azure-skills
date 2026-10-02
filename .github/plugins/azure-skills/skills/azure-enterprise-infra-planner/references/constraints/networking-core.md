# Networking (Core) Pairing Constraints

### Virtual Network

| Paired With | Constraint |
|-------------|------------|
| **Subnets** | Address prefixes of all subnets must fall within the VNet address space. Subnet CIDRs cannot overlap. |
| **VNet Peering** | Peered VNets cannot have overlapping address spaces. |
| **Azure Firewall** | Requires a subnet named exactly `AzureFirewallSubnet` with minimum /26 prefix. |
| **Azure Bastion** | Requires a subnet named exactly `AzureBastionSubnet` with minimum /26 prefix (recommended /26). |
| **VPN Gateway** | Requires a subnet named exactly `GatewaySubnet` with minimum /27 prefix (recommended /27). |
| **Application Gateway** | Requires a dedicated subnet (no mandatory name, but must not contain other resource types). |
| **AKS** | AKS subnet must have enough IP addresses for nodes + pods. With Azure CNI, each node reserves IPs for max pods. |

### Subnet

| Paired With | Constraint |
|-------------|------------|
| **NSG** | Cannot attach NSG to `GatewaySubnet` — NSGs are not supported for either VPN or ExpressRoute gateways. NSG on `AzureBastionSubnet` requires specific required rules. |
| **Delegations** | A subnet can only be delegated to one service. Delegated subnets cannot host other resource types. |
| **Service Endpoints** | Must match the service being accessed (e.g., `Microsoft.Sql` for SQL Server VNet rules). |
| **Private Endpoints** | Set `privateEndpointNetworkPolicies: 'Enabled'` to apply NSG/route table to private endpoints (default is `Disabled`). |
| **AKS** | AKS subnet needs enough IPs for all nodes + pods. Cannot be delegated or have conflicting service endpoints. |
| **Application Gateway** | Dedicated subnet required — cannot coexist with other resources except other App Gateways. Cannot mix v1 and v2 App Gateway SKUs on the same subnet. |
| **Azure Firewall** | Subnet must be named `AzureFirewallSubnet`, minimum /26. Cannot have other resources. |
| **App Service VNet Integration** | Subnet must be delegated to `Microsoft.Web/serverFarms`. Minimum size /28 (or /26 for multi-plan subnet join). This subnet must be different from any subnet used for App Service Private Endpoints. |
| **GatewaySubnet UDR** | Do not apply UDR with `0.0.0.0/0` next hop on `GatewaySubnet`. ExpressRoute gateways require management controller access. BGP route propagation must remain enabled on `GatewaySubnet`. |

### NSG

| Paired With | Constraint |
|-------------|------------|
| **GatewaySubnet** | NSGs are not supported on `GatewaySubnet`. Associating an NSG may cause VPN and ExpressRoute gateways to stop functioning. |
| **AzureBastionSubnet** | NSG on Bastion subnet requires specific inbound/outbound rules (see [Azure Bastion NSG](https://learn.microsoft.com/azure/bastion/bastion-nsg)). |
| **Application Gateway** | NSG on App Gateway subnet must allow `GatewayManager` service tag on ports `65200–65535` (v2) and health probe traffic. |
| **Load Balancer** | Must allow `AzureLoadBalancer` service tag for health probes. Standard LB requires NSG — it is secure by default and blocks inbound traffic without an NSG. |
| **Virtual Network** | NSG is associated to subnets, not directly to VNets. Each subnet can have at most one NSG. |

### Route Table

| Paired With | Constraint |
|-------------|------------|
| **Subnet** | Route table is associated on the subnet side: set `subnet.properties.routeTable.id` to the route table resource ID. Each subnet can have at most one route table. |
| **Azure Firewall** | For forced tunneling, create a default route (`0.0.0.0/0`) with `nextHopType: 'VirtualAppliance'` pointing to the firewall private IP. |
| **VPN Gateway** | Set `disableBgpRoutePropagation: true` to prevent BGP routes from overriding UDRs on the subnet. |
| **GatewaySubnet** | UDRs on `GatewaySubnet` have restrictions — cannot use `0.0.0.0/0` route pointing to a virtual appliance. |
| **AKS** | AKS subnets with UDRs require careful route design. Must allow traffic to Azure management APIs. `kubenet` and `Azure CNI` have different routing requirements. |
| **Virtual Appliance** | `nextHopIpAddress` must be a reachable private IP in the same VNet or a peered VNet. The appliance NIC must have `enableIPForwarding: true`. |

### Network Interface

| Paired With | Constraint |
|-------------|------------|
| **Virtual Machine** | Each VM requires at least one NIC. NIC must be in the same region and subscription as the VM. |
| **Subnet** | NIC must reference a subnet. The subnet determines the VNet, NSG, and route table that apply. |
| **NSG** | NSG can be associated at the NIC level or at the subnet level (or both). NIC-level NSG is evaluated after subnet-level NSG. |
| **Public IP** | Public IP and NIC must be in the same region. When associated with a Load Balancer, Public IP SKU must match the LB SKU (Basic with Basic, Standard with Standard). |
| **Load Balancer** | NIC IP configuration can reference `loadBalancerBackendAddressPools` and `loadBalancerInboundNatRules`. Load balancer and NIC must be in the same VNet. |
| **Accelerated Networking** | Not all VM sizes support accelerated networking. Must verify VM size compatibility. |
| **VM Scale Set** | NICs for VMSS instances are managed by the scale set — do not create standalone NICs for VMSS. |
| **Application Gateway** | NIC IP configuration can reference `applicationGatewayBackendAddressPools`. |

### Public IP

| Paired With | Constraint |
|-------------|------------|
| **Standard SKU** | Must use `Static` allocation method. `Dynamic` only works with Basic SKU. |
| **Load Balancer** | Public IP SKU must match Load Balancer SKU (Standard ↔ Standard, Basic ↔ Basic). |
| **Application Gateway** | Standard_v2 App Gateway requires Standard SKU public IP with Static allocation. |
| **Azure Bastion** | Requires Standard SKU with Static allocation. |
| **VPN Gateway** | Basic VPN Gateway SKU requires Basic public IP. Standard+ gateway SKUs require Standard public IP. |
| **Azure Firewall** | Requires Standard SKU with Static allocation. |
| **Zones** | Standard SKU is zone-redundant by default. Specify `zones` only to pin to specific zone(s). |

### NAT Gateway

| Paired With | Constraint |
|-------------|------------|
| **Subnet** | NAT Gateway is associated on the subnet side: set `subnet.properties.natGateway.id` to the NAT Gateway resource ID. A subnet can have at most one NAT Gateway. |
| **Public IP** | Public IP must use `Standard` SKU and `Static` allocation. Public IP and NAT Gateway must be in the same region. |
| **Public IP Prefix** | Public IP prefix must use `Standard` SKU. Provides contiguous outbound IPs. |
| **Availability Zones** | NAT Gateway can be zonal (pinned to one zone) or non-zonal. Public IPs must match the same zone or be zone-redundant. |
| **Load Balancer** | NAT Gateway takes precedence over outbound rules of a Standard Load Balancer when both are on the same subnet. |
| **VPN Gateway / ExpressRoute** | `GatewaySubnet` does not support NAT Gateway association. |
| **Azure Firewall** | NAT Gateway can be associated with the `AzureFirewallSubnet` for deterministic outbound IPs in SNAT scenarios. |
