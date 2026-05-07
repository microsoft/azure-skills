# Azure App Service

Hosting patterns and best practices for Azure App Service.

## When to Use

- Traditional web applications
- REST APIs without containerization
- .NET, Node.js, Python, Java, PHP applications
- When Docker is not required/desired
- When built-in deployment slots are needed

## Service Type in azure.yaml

```yaml
services:
  my-web:
    host: appservice
    project: ./src/my-web
```

## Required Supporting Resources

| Resource | Purpose |
|----------|---------|
| App Service Plan | Compute hosting |
| Application Insights | Monitoring |
| Key Vault | Secrets (optional) |

## Runtime Stacks

> 💡 **Tip:** Prefer Linux App Service Plans for Node.js, Python, and Java. Use Windows only when explicitly required (e.g. .NET Framework). See [Bicep Patterns](bicep.md) for Linux vs Windows configuration.

### Linux (recommended)

| Language | linuxFxVersion |
|----------|----------------|
| Node.js 18 | `NODE\|18-lts` |
| Node.js 20 | `NODE\|20-lts` |
| Python 3.11 | `PYTHON\|3.11` |
| .NET 8 | `DOTNETCORE\|8.0` |
| Java 17 | `JAVA\|17-java17` |

### Windows

| Language | Setting |
|----------|---------|
| Node.js | `WEBSITE_NODE_DEFAULT_VERSION: '~20'` (app setting) |
| .NET 8 | Built-in (no extra config) |

## SKU Selection

| SKU | Use Case |
|-----|----------|
| F1/D1 | Development/testing (free/shared) |
| B1-B3 | Small production, basic features |
| S1-S3 | Production with auto-scale, slots |
| P1v3-P3v3 | High-performance production |

## Health Checks

Always configure health check path:

```bicep
siteConfig: {
  healthCheckPath: '/health'
}
```

Endpoint should return 200 OK when healthy.

## Templates

For App Service templates with composable recipes (SQL, Cosmos DB, Auth, Redis), see [Template Selection](templates/selection.md).

## Common Data Backends

When pairing App Service with a data layer, load the corresponding service references:

| Data Service | Reference                                 |
| ------------ | ----------------------------------------- |
| Azure SQL    | [SQL Database](../sql-database/README.md) |
| Cosmos DB    | [Cosmos DB](../cosmos-db/README.md)       |

## References

- [Bicep Patterns](bicep.md)
- [Deployment Slots](deployment-slots.md)
- [Auto-Scaling](scaling.md)
- [Networking](networking.md)
- [SKU Selection](sku-selection.md)
- [Custom Domains](custom-domains.md)
