# VPN Gateway & DNS Private Resolver Setup

Post-deployment add-on for private network templates (T10, T15–T19). Creates a point-to-site VPN Gateway and DNS Private Resolver so the user can connect from their dev machine and resolve private DNS zones.

## Assumptions

| Property | Value | Rationale |
|----------|-------|-----------|
| Auth | Microsoft Entra ID (AAD) only | No certificate management |
| Tunnel | OpenVPN | Cross-platform, Azure VPN Client |
| Gateway SKU | VpnGw1AZ | Zone-redundant, same cost as VpnGw1 |
| GatewaySubnet | /24 recommended | Agent computes from available VNet space |
| DNS resolver subnet | /28 minimum | Agent computes from available VNet space |
| Client address pool | `172.16.201.0/24` | Non-overlapping with VNet |

## Subnet Layout

Adds two subnets to the existing VNet. Uses the next available range after the agent and PE subnets.

| Subnet | CIDR (default) | Purpose | Delegation |
|--------|----------------|---------|------------|
| `GatewaySubnet` | Computed | VPN Gateway (name is required by Azure) | None |
| `dns-resolver-inbound` | Computed | DNS Private Resolver inbound endpoint | `Microsoft.Network/dnsResolvers` |

> ⚠️ **Warning:** `GatewaySubnet` is a reserved name — Azure requires this exact name for VPN Gateway.

## Pre-Deployment

### 1. Discover Available Subnets

List existing subnets to find free address space:

```bash
az network vnet subnet list \
  --resource-group <rg> --vnet-name <vnet-name> \
  --query "[].{name:name,cidr:addressPrefix}" -o table
```

Pick the next unused `/24` for `GatewaySubnet` and the next unused `/28` for `dns-resolver-inbound`. Both must not overlap with any existing subnet.

Example: if subnets `.0.0/24`, `.1.0/24`, `.2.0/24` are in use → use `192.168.3.0/24` for GatewaySubnet, `192.168.4.0/28` for dns-resolver-inbound.

### 2. Collect Remaining Inputs

| Parameter | Source |
|-----------|--------|
| `vnetName` | From main deployment |
| `vnetResourceGroup` | Resource group containing the VNet (omit if same as deployment RG) |
| `resourceGroupName` | Resource group for this deployment |
| `gatewaySubnetCidr` | Computed in step 1 |
| `dnsResolverSubnetCidr` | Computed in step 1 |
| `suffix` | From main deployment (or generate unique) |
| `aadTenantId` | From `az account show --query tenantId` |

### 3. Check VPN Gateway Quota

```bash
az network list-usages --location <location> \
  --query "[?name.value=='VirtualNetworkGateways'].{limit:limit,current:currentValue}" -o table
```

## Bicep Template

Template: [vpn-dns-setup.bicep](vpn-dns-setup.bicep)

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `vnetName` | Yes | — | Name of the existing VNet |
| `vnetResourceGroup` | No | Deployment RG | Resource group of the existing VNet (for BYO VNets in a different RG) |
| `aadTenantId` | Yes | — | Entra ID tenant ID for VPN auth |
| `suffix` | Yes | — | Unique suffix for resource naming |
| `gatewaySubnetCidr` | Yes | — | GatewaySubnet CIDR (computed from VNet) |
| `dnsResolverSubnetCidr` | Yes | — | DNS resolver inbound subnet CIDR (computed from VNet) |
| `vpnClientAddressPool` | No | `172.16.201.0/24` | VPN client address pool |

**Creates:** GatewaySubnet, dns-resolver-inbound subnet, Public IP (zonal), VPN Gateway (VpnGw1AZ, P2S AAD/OpenVPN), DNS Private Resolver with inbound endpoint.

## Deploy

```bash
az deployment group create \
  --resource-group <rg> \
  --template-file vpn-dns-setup.bicep \
  --parameters vnetName='<vnet-name>' aadTenantId='<tenant-id>' suffix='<suffix>' \
    gatewaySubnetCidr='<computed-cidr>' dnsResolverSubnetCidr='<computed-cidr>' \
  --name vpn-dns-setup
```

> ⚠️ **VPN Gateway provisioning takes 20–45 minutes.** This is normal. Do not cancel.

Monitor:

```bash
az deployment group show \
  --resource-group <rg> --name vpn-dns-setup \
  --query "{state:properties.provisioningState}" -o tsv
```

## Post-Deployment

### 1. Get DNS Resolver Inbound IP

```bash
az network dns-resolver inbound-endpoint show \
  --resource-group <rg> \
  --dns-resolver-name dns-resolver-<suffix> \
  --name inbound \
  --query "ipConfigurations[0].privateIpAddress" -o tsv
```

Save this IP — the VPN client needs it as custom DNS.

### 2. Connect via VPN

Provide the user with these instructions (substitute actual resource name and DNS IP):

1. Go to **Azure Portal** → `vpn-gateway-<suffix>` → **Point-to-site configuration** → **Download VPN client**
2. Extract the ZIP → edit `AzureVPN/azurevpnconfig.xml` — replace:
   ```xml
   <clientconfig i:nil="true" />
   ```
   with:
   ```xml
   <clientconfig>
     <dnsservers>
       <dnsserver><dns-resolver-inbound-ip></dnsserver>
     </dnsservers>
   </clientconfig>
   ```
3. Open [Azure VPN Client](https://aka.ms/azvpnclientdownload) → **Import** the modified `azurevpnconfig.xml` → **Connect**

Use `AskUserQuestion`: **"Let me know when you're connected so I can verify DNS resolution."**

> Do NOT proceed to verification until the user confirms they are connected.

### 3. Verify DNS Resolution

After connecting via VPN, verify private DNS zones resolve correctly:

```bash
nslookup <ai-account-name>.services.ai.azure.com
nslookup <cosmos-account>.documents.azure.com
nslookup <storage-account>.blob.core.windows.net
```

Each should resolve to a private IP (`192.168.x.x`), not a public IP.

### 4. VPN Setup Complete

DNS resolves to private IPs — VPN is working. Return to [post-deployment-validation.md](post-deployment-validation.md) **Step 5** to run the end-to-end tests.

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| VPN connects but DNS doesn't resolve | Custom DNS not set in VPN client profile | Add DNS resolver inbound IP as custom DNS server |
| `nslookup` returns public IP | Private DNS zones not linked to VNet | Verify DNS zone VNet links: `az network private-dns zone list -g <rg>` |
| VPN client auth fails | Wrong tenant or app not consented | Verify `tenantId`, ensure Azure VPN enterprise app is consented in the tenant |
| Gateway deployment times out | Normal — VPN GW takes 20-45 min | Wait and re-check with `az deployment group show` |
| Subnet conflict | CIDR overlaps with existing subnet | Use different CIDRs for `gatewaySubnetCidr` / `dnsResolverSubnetCidr` |
| DNS resolver queries blocked | NRMS auto-deployed NSG missing DNS rules | Add inbound allow rule for UDP/TCP port 53 from VPN client address pool to the `dns-resolver-inbound` subnet NSG |
