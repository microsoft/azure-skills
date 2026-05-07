# App Service Networking

VNet integration, Private Endpoints, Access Restrictions, and Hybrid Connections.

## Feature Availability by SKU

| Feature | Free | Basic | Standard | Premium | Isolated |
|---------|:-:|:-:|:-:|:-:|:-:|
| VNet integration (outbound) | ❌ | ✅ | ✅ | ✅ | ✅ (native) |
| Private Endpoints (inbound) | ❌ | ✅ | ✅ | ✅ | ✅ |
| Access Restrictions | ✅ | ✅ | ✅ | ✅ | ✅ |
| Hybrid Connections | ❌ | 5 | 25 | 200 | 200 |
| Access to service-endpoint-protected resources | ❌ | ✅ | ✅ | ✅ | ✅ |
> Note: Service endpoints are configured on VNets/subnets and downstream services (e.g., Storage, SQL). App Service accesses them via VNet integration rather than enabling service endpoints directly on the app.

## VNet Integration (Outbound)

Routes outbound traffic from the app through a VNet subnet, enabling access to private resources (databases, storage, VMs).

### Subnet Requirements

| Requirement | Value |
|------------|-------|
| Minimum subnet size | `/26` (64 addresses) recommended |
| Delegation | `Microsoft.Web/serverFarms` |
| Dedicated | One subnet per App Service plan |

### Bicep — VNet Integration

```bicep
resource subnet 'Microsoft.Network/virtualNetworks/subnets@2023-11-01' = {
  parent: vnet
  name: 'app-service-subnet'
  properties: {
    addressPrefix: '10.0.1.0/26'
    delegations: [
      {
        name: 'Microsoft.Web.serverFarms'
        properties: { serviceName: 'Microsoft.Web/serverFarms' }
      }
    ]
  }
}

resource webApp 'Microsoft.Web/sites@2024-11-01' = {
  name: appName
  location: location
  properties: {
    serverFarmId: appServicePlan.id
    virtualNetworkSubnetId: subnet.id
    outboundVnetRouting: {
      allTraffic: true // route all outbound through VNet
    }
  }
}
```

### CLI - VNet Integration

```bash
# Configure virtual network integration 
az webapp vnet-integration add --resource-group RG --name APP --vnet VNET --subnet SUBNET

# Update app configuration to route all outbound traffic through the virtual network integration
az resource update --resource-group RG --name APP --resource-type "Microsoft.Web/sites" --set properties.outboundVnetRouting.allTraffic=true
```


> 💡 **Tip:** Set `outboundVnetRouting.allTraffic: true` to route ALL outbound traffic through the VNet. Without this, only RFC1918 traffic is routed through the VNet.

## Private Endpoints (Inbound)

Expose the app on a private IP address within your VNet. Public access can be disabled entirely.

### Bicep — Private Endpoint

```bicep
resource privateEndpoint 'Microsoft.Network/privateEndpoints@2023-11-01' = {
  name: '${appName}-pe'
  location: location
  properties: {
    subnet: { id: privateEndpointSubnet.id }
    privateLinkServiceConnections: [
      {
        name: '${appName}-connection'
        properties: {
          privateLinkServiceId: webApp.id
          groupIds: ['sites']
        }
      }
    ]
  }
}

resource privateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.azurewebsites.net'
  location: 'global'
}

resource dnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: privateDnsZone
  name: '${vnet.name}-link'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

resource privateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = {
  parent: privateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'webapp-dns-zone'
        properties: {
          privateDnsZoneId: privateDnsZone.id
        }
      }
    ]
  }
}
```

### CLI - Private Endpoint

```bash
# Retrieve web app resource id
id=$(az webapp show --name APP --resource-group RG --query id --output tsv)

# Create Private Endpoint
az network private-endpoint create --connection-name CONNECTIONNAME --name private-endpoint --private-connection-resource-id $id --resource-group RG --subnet SUBNET --group-id sites --vnet-name VNET

# Create Private DNS Zone
az network private-dns zone create --resource-group RG --name "privatelink.azurewebsites.net"

# Link the DNS Zone to virtual network
az network private-dns link vnet create --resource-group RG --zone-name "privatelink.azurewebsites.net" --name dns-link --virtual-network VNET --registration-enabled false

```

> ⚠️ **Warning:** Private Endpoints require Basic (B1+) or higher tier. The private DNS zone `privatelink.azurewebsites.net` must be linked to the VNet for name resolution.

## Access Restrictions

Control inbound access with IP-based or service-tag rules. Available on all SKUs.

### Bicep — Access Restrictions

```bicep
siteConfig: {
  ipSecurityRestrictions: [
    {
      name: 'allow-office'
      priority: 100
      action: 'Allow'
      ipAddress: '203.0.113.0/24'
    }
    {
      name: 'deny-all'
      priority: 2147483647
      action: 'Deny'
      ipAddress: 'Any'
    }
  ]
  scmIpSecurityRestrictionsUseMain: true
}
```

### CLI - Access Restrictions

```bash
# Add restriction to allow traffic from set range used by the office
az webapp config access-restriction add --resource-group RG --name APP --rule-name 'allow-office' --action Allow --ip-address 203.0.113.0/24 --priority 100

# Add restriction to deny access from any other address range
az webapp config access-restriction add --resource-group RG --name APP --rule-name 'deny-all' --action Deny --ip-address Any --priority 2147483647

# Set SCM Site (Kudu) to use same access restrictions as main site
az webapp config access-restriction set -g RG -n APP --use-same-restrictions-for-scm-site true
```

> 💡 **Tip:** Always restrict the SCM/Kudu site too. Use `scmIpSecurityRestrictionsUseMain: true` to inherit main site rules, or define separate SCM rules.

## Hybrid Connections

Connect to on-premises resources without VPN. Requires Basic tier or higher. Uses Hybrid Connection Manager (HCM) agent on-premises relaying through Azure Relay.

> ⚠️ **Warning:** Each Hybrid Connection maps to a single host:port endpoint. Basic tier supports 5; Standard tier supports 25; Premium/Isolated support 200.

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Cannot reach private DB | VNet integration not enabled | Enable VNet integration; check `outboundVnetRouting.allTraffic` |
| DNS resolution fails | Private DNS zone not linked | Link `privatelink.*` DNS zone to VNet |
| Access restriction not working | Priority ordering wrong | Lower numbers = higher priority; check rule order |
| Hybrid Connection timeout | HCM not running | Verify HCM service status on-premises |
| Outbound traffic blocked | NSG rules on subnet | Allow outbound to required services in NSG |
