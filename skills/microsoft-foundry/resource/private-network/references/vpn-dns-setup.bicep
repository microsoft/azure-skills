/*
  VPN Gateway + DNS Private Resolver
  ------------------------------------
  Post-deployment add-on for private network templates (T10, T15–T19).
  Creates a P2S VPN Gateway (AAD auth, OpenVPN) and a DNS Private Resolver
  so the user can connect from their dev machine and resolve private DNS zones.

  Note: VPN Gateway deployment takes 30-45 minutes.
*/

@description('Name of the existing VNet from the Foundry deployment')
param vnetName string

@description('Resource group of the existing VNet. Defaults to the deployment resource group.')
param vnetResourceGroup string = resourceGroup().name

// ── Existing VNet ──
resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' existing = {
  name: vnetName
  scope: resourceGroup(vnetResourceGroup)
}

var location = vnet.location

@description('CIDR for GatewaySubnet — agent must compute from available VNet space')
param gatewaySubnetCidr string

@description('CIDR for DNS resolver inbound subnet — agent must compute from available VNet space')
param dnsResolverSubnetCidr string

@description('VPN client address pool — must not overlap with VNet')
param vpnClientAddressPool string = '172.16.201.0/24'

@description('Azure AD tenant ID for VPN authentication')
param aadTenantId string

@description('Unique suffix for resource naming')
param suffix string

// AAD constants for Azure Public cloud only.
// Sovereign clouds (AzureUSGovernment, AzureChinaCloud) require different audience/issuer values.
// The intake step (az cloud show) warns users before reaching this template.
var aadAudience = 'c632b3df-fb67-4d84-bdcf-b95ad541b5c8'
var aadIssuer = 'https://sts.windows.net/${aadTenantId}/'
var aadTenant = 'https://login.microsoftonline.com/${aadTenantId}/'

// ── Add subnets ──
resource gatewaySubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' = {
  parent: vnet
  name: 'GatewaySubnet'
  properties: {
    addressPrefix: gatewaySubnetCidr
    defaultOutboundAccess: false
  }
}

// NOTE: NRMS policy may auto-deploy an NSG on this subnet.
// Ensure the NSG allows inbound UDP/TCP port 53 (DNS) from the VPN client address pool.
resource dnsResolverSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' = {
  parent: vnet
  name: 'dns-resolver-inbound'
  properties: {
    addressPrefix: dnsResolverSubnetCidr
    defaultOutboundAccess: false
    delegations: [
      {
        name: 'dns-resolver-delegation'
        properties: {
          serviceName: 'Microsoft.Network/dnsResolvers'
        }
      }
    ]
  }
  dependsOn: [gatewaySubnet] // serialize subnet updates
}

// ── Public IP for VPN Gateway ──
resource vpnGatewayPip 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: 'vpn-gateway-pip-${suffix}'
  location: location
  sku: {
    name: 'Standard'
  }
  zones: ['1', '2', '3']
  properties: {
    publicIPAllocationMethod: 'Static'
  }
}

// ── VPN Gateway ──
resource vpnGateway 'Microsoft.Network/virtualNetworkGateways@2024-05-01' = {
  name: 'vpn-gateway-${suffix}'
  location: location
  properties: {
    gatewayType: 'Vpn'
    vpnType: 'RouteBased'
    sku: {
      name: 'VpnGw1AZ'
      tier: 'VpnGw1AZ'
    }
    ipConfigurations: [
      {
        name: 'default'
        properties: {
          publicIPAddress: {
            id: vpnGatewayPip.id
          }
          subnet: {
            id: gatewaySubnet.id
          }
        }
      }
    ]
    vpnClientConfiguration: {
      vpnClientAddressPool: {
        addressPrefixes: [vpnClientAddressPool]
      }
      vpnClientProtocols: ['OpenVPN']
      vpnAuthenticationTypes: ['AAD']
      aadTenant: aadTenant
      aadAudience: aadAudience
      aadIssuer: aadIssuer
    }
  }
}

// ── DNS Private Resolver ──
resource dnsResolver 'Microsoft.Network/dnsResolvers@2022-07-01' = {
  name: 'dns-resolver-${suffix}'
  location: location
  properties: {
    virtualNetwork: {
      id: vnet.id
    }
  }
}

resource dnsInboundEndpoint 'Microsoft.Network/dnsResolvers/inboundEndpoints@2022-07-01' = {
  parent: dnsResolver
  name: 'inbound'
  location: location
  properties: {
    ipConfigurations: [
      {
        privateIpAllocationMethod: 'Dynamic'
        subnet: {
          id: dnsResolverSubnet.id
        }
      }
    ]
  }
}

// ── Outputs ──
output vpnGatewayName string = vpnGateway.name
output vpnGatewayId string = vpnGateway.id
output vpnPublicIpAddress string = vpnGatewayPip.properties.ipAddress
output dnsResolverInboundIp string = dnsInboundEndpoint.properties.ipConfigurations[0].privateIpAddress
