# Networking (Traffic) Pairing Constraints

### Application Gateway

| Paired With | Constraint |
|-------------|------------|
| **Subnet** | Requires a dedicated subnet — no other resources allowed in the subnet (except other App Gateways). Cannot mix v1 and v2 SKUs on the same subnet — separate subnets required for each. |
| **Public IP** | v2 SKU requires Standard SKU public IP with Static allocation. |
| **NSG** | NSG on App Gateway subnet must allow `GatewayManager` service tag on ports `65200–65535` (v2) or `65503–65534` (v1). |
| **WAF** | WAF configuration only available with `WAF_v2` or `WAF_Large`/`WAF_Medium` SKUs. WAF v2 cannot disable request buffering — chunked file transfer requires path-rule workaround. |
| **Zones** | v2 supports availability zones. Specify `zones: ['1','2','3']` for zone-redundant deployment. |
| **Key Vault** | For SSL certificates, use `sslCertificates[].properties.keyVaultSecretId` to reference Key Vault certificates. User-assigned managed identity required. |
| **v1 Limitations** | v1 does not support: autoscaling, zone redundancy, Key Vault integration, mTLS, Private Link, WAF custom rules, or header rewrite. Must use v2 for these features. v1 SKUs are being retired April 2026. |
| **Private-only (no public IP)** | Requires `EnableApplicationGatewayNetworkIsolation` feature registration. Only available with `Standard_v2` or `WAF_v2`. |
| **Global VNet Peering** | Backend via private endpoint across global VNet peering causes traffic to be dropped — results in unhealthy backend status. |
| **kubenet (AKS)** | Kubenet is not supported by Application Gateway for Containers. Must use CNI or CNI Overlay. |

### Front Door

| Paired With | Constraint |
|-------------|------------|
| **Origins (backends)** | Origins are defined in child `originGroups/origins`. Supported origin types: App Service, Storage, Application Gateway, Public IP, custom hostname. |
| **Private Link Origins** | Only available with `Premium_AzureFrontDoor` SKU. Enable private origin connections to App Service, Storage, Internal Load Balancer, etc. |
| **WAF Policy** | WAF policies are separate `Microsoft.Network/FrontDoorWebApplicationFirewallPolicies` resources. Linked via security policy child resource on the profile. |
| **Custom Domains** | Custom domains are child resources of the profile. Require DNS CNAME/TXT validation and certificate (managed or custom). |
| **Application Gateway** | Front Door in front of App Gateway: use App Gateway public IP as origin. Set `X-Azure-FDID` header restriction on App Gateway to accept only Front Door traffic. |
| **App Service** | Restrict App Service to Front Door traffic using access restrictions with `AzureFrontDoor.Backend` service tag and `X-Azure-FDID` header check. |

### Load Balancer

| Paired With | Constraint |
|-------------|------------|
| **Public IP** | Public IP SKU must match LB SKU. Basic LB requires Basic public IP; Standard LB requires Standard public IP. No cross-SKU mixing. |
| **Standard SKU** | Backend pool VMs must be in the same VNet. No VMs from different VNets. Standard LB blocks outbound traffic by default — requires explicit outbound rules, NAT gateway, or instance-level public IPs. Standard LB requires an NSG (secure by default; inbound traffic blocked without NSG). |
| **Basic SKU** | Backend pool VMs must be in the same availability set or VMSS. |
| **Availability Zones** | Standard SKU is zone-redundant by default. Frontend IPs inherit zone from public IP. |
| **VMs / VMSS** | VMs in backend pool cannot have both Basic and Standard LBs simultaneously. |
| **Outbound Rules** | Only Standard SKU supports outbound rules. Basic SKU has implicit outbound. |

### API Management

| Paired With | Constraint |
|-------------|------------|
| **VNet (External)** | Only available with `Developer`, `Premium`, or `Isolated` SKU. Subnet must be dedicated with an NSG allowing APIM management traffic. |
| **VNet (Internal)** | Same as External but no public gateway endpoint. Requires Private DNS or custom DNS for resolution. |
| **Application Gateway** | Common pattern: App Gateway in front of Internal-mode APIM. App Gateway uses the APIM private IP as backend. |
| **Key Vault** | Named values and certificates can reference Key Vault secrets. Requires managed identity with `Key Vault Secrets User` role. |
| **Application Insights** | Set `properties.customProperties` with `Microsoft.WindowsAzure.ApiManagement.Gateway.Protocols.Server.Http2` and logger resource for diagnostics. |
| **NSG (VNet mode)** | Subnet NSG must allow: inbound on ports 3443 (management), 80/443 (client); outbound to Azure Storage, SQL, Event Hub, and other dependencies. |
