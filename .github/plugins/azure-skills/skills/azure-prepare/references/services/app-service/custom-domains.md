# App Service Custom Domains and Managed TLS

## Prerequisites

| Requirement | Details |
|------------|---------|
| SKU tier | Basic (B1) or higher |
| DNS access | Ability to create CNAME, A, and TXT records |
| Domain ownership | Verified via TXT record |

## DNS Configuration

### Subdomain (CNAME)

| Record Type | Name | Value |
|------------|------|-------|
| CNAME | `www` | `<app-name>.azurewebsites.net` |
| TXT | `asuid.www` | `<verification-id>` |

### Apex / Root Domain (A Record)

| Record Type | Name | Value |
|------------|------|-------|
| A | `@` | `<app-ip-address>` |
| TXT | `asuid` | `<verification-id>` |

Get the verification ID and IP address:

```bash
# Get verification ID
az webapp show -n $APP -g $RG --query "customDomainVerificationId" -o tsv

# Get IP address (for A records)
az webapp show -n $APP -g $RG --query "inboundIpAddress" -o tsv
```

> 💡 **Tip:** Prefer CNAME records for subdomains. For apex domains, consider using an Azure DNS alias record to avoid hardcoding IP addresses that may change.

## Bind Custom Domain via CLI

```bash
# Add custom domain
az webapp config hostname add -n $APP -g $RG --hostname www.contoso.com

# Create managed certificate (free)
az webapp config ssl create -n $APP -g $RG --hostname www.contoso.com

# Capture certificate thumbprint
THUMBPRINT=$(az webapp config ssl list -n $APP -g $RG \
  --query "[?contains(hostNames, 'www.contoso.com')].thumbprint | [0]" -o tsv)

# Bind the certificate
az webapp config ssl bind -n $APP -g $RG \
  --certificate-thumbprint $THUMBPRINT --ssl-type SNI
```

## Bicep — Custom Domain with Managed Certificate

```bicep
resource customDomain 'Microsoft.Web/sites/hostNameBindings@2022-09-01' = {
  parent: webApp
  name: 'www.contoso.com'
  properties: {
    siteName: webApp.name
    hostNameType: 'Verified'
    sslState: 'Disabled' // enable after cert is created
  }
}

resource managedCert 'Microsoft.Web/certificates@2022-09-01' = {
  name: 'www.contoso.com'
  location: location
  properties: {
    serverFarmId: appServicePlan.id
    canonicalName: 'www.contoso.com'
  }
  dependsOn: [customDomain]
}
```

Then run a follow-up Bicep deployment to enable SNI and bind the managed certificate to the hostname:

```bicep
resource managedCert 'Microsoft.Web/certificates@2022-09-01' existing = {
  name: 'www.contoso.com'
}

resource customDomainTlsBinding 'Microsoft.Web/sites/hostNameBindings@2022-09-01' = {
  parent: webApp
  name: 'www.contoso.com'
  properties: {
    siteName: webApp.name
    hostNameType: 'Verified'
    sslState: 'SniEnabled'
    thumbprint: managedCert.properties.thumbprint
  }
}
```

> ⚠️ **Warning:** Managed certificate creation requires the DNS records to be in place first. The hostname binding must exist before requesting the certificate.

## Terraform — Custom Domain with Managed Certificate

```hcl
resource "azurerm_app_service_custom_hostname_binding" "domain" {
  hostname            = "www.contoso.com"
  app_service_name    = azurerm_linux_web_app.app.name
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_app_service_managed_certificate" "cert" {
  custom_hostname_binding_id = azurerm_app_service_custom_hostname_binding.domain.id
}

resource "azurerm_app_service_certificate_binding" "binding" {
  hostname_binding_id = azurerm_app_service_custom_hostname_binding.domain.id
  certificate_id      = azurerm_app_service_managed_certificate.cert.id
  ssl_state           = "SniEnabled"
}
```

## TLS Options

| Option | Cost | Renewal | Use Case |
|--------|------|---------|----------|
| App Service Managed Certificate | Free | Auto-renewed | Standard custom domains |
| App Service Certificate (purchased) | ~$70/yr | Auto-renewed | Extended validation, wildcard |
| Bring your own certificate | Varies | Manual | Enterprise PKI, specific CA |

### Enforce HTTPS Only

```bicep
resource webApp 'Microsoft.Web/sites@2022-09-01' = {
  name: appName
  location: location
  properties: {
    httpsOnly: true
    // ...
  }
}
```

```hcl
resource "azurerm_linux_web_app" "app" {
  name                = var.app_name
  # ...
  https_only          = true
}
```

## Minimum TLS Version

```bash
# Set minimum TLS version to 1.2
az webapp config set -n $APP -g $RG --min-tls-version 1.2
```

```bicep
siteConfig: {
  minTlsVersion: '1.2'
}
```

> ⚠️ **Warning:** TLS 1.0 and 1.1 are deprecated. Always set minimum TLS version to 1.2 for production workloads.

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Domain verification fails | Missing TXT record | Add `asuid` TXT record and wait for DNS propagation |
| Certificate creation fails | DNS not yet propagated | Wait 5-15 min for propagation; verify with `nslookup` |
| SSL binding error | SKU too low | Upgrade to Basic (B1) or higher |
| Managed cert not renewing | DNS record changed | Verify CNAME/A record still points to the app |
