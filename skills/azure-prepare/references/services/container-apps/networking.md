# Container Apps Networking

VNet integration, ingress configuration, custom domains, and TLS for Container Apps.

## Ingress Modes

| Mode | Visibility | Use Case |
|------|-----------|----------|
| External | Internet-accessible | Public APIs, web apps |
| Internal | Not internet-accessible; reachable within the environment and VNet (if VNet-injected) | Microservices, back-end APIs |
| Disabled | No HTTP ingress | Background workers, queue processors |

### Bicep — External Ingress

```bicep
configuration: {
  ingress: {
    external: true
    targetPort: 8080
    transport: 'auto'
    allowInsecure: false
  }
}
```

### Bicep — Internal Ingress

```bicep
configuration: {
  ingress: {
    external: false
    targetPort: 8080
  }
}
```

> 💡 **Tip:** Internal apps get a `*.internal.<env-default-domain>` FQDN. This is accessible from within the Container Apps environment and, when the environment is VNet-injected, also from the VNet.

## VNet Integration

Container Apps run inside an environment that can be injected into a VNet subnet.

### Subnet Requirements

| Requirement | Workload Profiles (default) | Consumption-only (legacy) |
|------------|---------------------------|--------------------------|
| Minimum subnet size | `/27` (32 addresses) | `/23` (512 addresses) |
| Delegation | `Microsoft.App/environments` | `Microsoft.App/environments` |
| Dedicated | Subnet must be exclusive to the Container Apps environment | Same |

### Bicep — VNet-Integrated Environment

```bicep
resource subnet 'Microsoft.Network/virtualNetworks/subnets@2023-11-01' = {
  parent: vnet
  name: 'container-apps-subnet'
  properties: {
    addressPrefix: '10.0.16.0/27'
    delegations: [
      {
        name: 'Microsoft.App.environments'
        properties: { serviceName: 'Microsoft.App/environments' }
      }
    ]
  }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  properties: {
    vnetConfiguration: {
      infrastructureSubnetId: subnet.id
      internal: false // true for internal-only environment
    }
  }
}
```

> ⚠️ **Warning:** VNet configuration is set at environment creation and cannot be changed afterward. Plan your network topology before creating the environment.

## Custom Domains

### Steps

1. Add a CNAME or A record pointing to the Container App's FQDN or static IP
2. Bind the custom domain to the Container App
3. Configure a managed or custom TLS certificate

```bash
# Register custom domain (hostname only — no cert provisioned yet)
az containerapp hostname add -n $APP -g $RG --hostname app.contoso.com

# Bind managed certificate (provisions and attaches TLS cert)
az containerapp hostname bind -n $APP -g $RG \
  --hostname app.contoso.com \
  --environment $ENV_NAME \
  --validation-method CNAME
```

### DNS Configuration

| Record Type | Name | Value |
|------------|------|-------|
| CNAME | `app.contoso.com` | `<app-name>.<region>.azurecontainerapps.io` |
| TXT (verification) | `asuid.app.contoso.com` | `<verification-id>` |
| A (apex domain) | `contoso.com` | Environment static IP |

> 💡 **Tip:** Use `az containerapp show -n $APP -g $RG --query properties.configuration.ingress.fqdn` to get the target FQDN for DNS records.

## TLS Configuration

### Managed Certificates

Azure automatically provisions and renews TLS certificates for custom domains — no manual cert management required.

> ⚠️ **Prerequisites:** Managed certificates require the app to be externally reachable with valid **public** DNS (CNAME or HTTP validation). They do **not** work for internal environments or apps behind private DNS. For private/internal scenarios, bring your own certificate via `az containerapp ssl upload`.

## IP Restrictions

> ⚠️ **Warning:** IP restriction rules are evaluated in **array order** (first match wins). The `priority` field does not exist in the Container Apps API — order your rules carefully in the array.

Allow-only rules implicitly deny all traffic not matching any rule. Deny-only rules implicitly allow all other traffic.

```bicep
configuration: {
  ingress: {
    external: true
    targetPort: 8080
    ipSecurityRestrictions: [
      {
        name: 'allow-office'
        action: 'Allow'
        ipAddressRange: '203.0.113.0/24'
        description: 'Office network'
      }
      {
        name: 'allow-vpn'
        action: 'Allow'
        ipAddressRange: '198.51.100.0/24'
        description: 'VPN gateway'
      }
    ]
  }
}
```

## Network Topology Summary

| Topology | Environment `internal` | Ingress `external` | Access |
|----------|----------------------|-------------------|--------|
| Public app | `false` | `true` | Internet + VNet |
| Internal microservice | `false` | `false` | Same environment; VNet if environment is VNet-injected |
| Fully private (VNet-wide) | `true` | `true` | VNet only (no public IP); accessible from anywhere in the VNet |
| Fully private (env-only) | `true` | `false` | VNet only (no public IP); accessible only within the Container Apps environment |

> ⚠️ **Warning:** An internal environment has no public IP. You need VPN, ExpressRoute, or a jump box to reach apps in an internal environment.
