# AWS Elastic Beanstalk to Azure App Service Migration

Detailed guidance for migrating AWS Elastic Beanstalk applications to Azure App Service.

## Service Mapping

| AWS Service | Azure Equivalent |
|-------------|------------------|
| Elastic Beanstalk | Azure App Service |
| Elastic Beanstalk Environment | App Service + App Service Plan |
| Platform Presets | Runtime Stacks |
| `.ebextensions/` | Bicep + App Settings |
| `Procfile` | Startup Command |
| RDS (PostgreSQL) | Azure Database for PostgreSQL Flexible Server |
| RDS (MySQL) | Azure Database for MySQL Flexible Server |
| RDS (SQL Server) | Azure SQL Database |
| ElastiCache (Redis) | Azure Cache for Redis |
| ElastiCache (Memcached) | Azure Cache for Redis |
| S3 | Azure Blob Storage |
| ALB / ELB | App Service built-in LB / Azure Front Door |
| Route 53 | Azure DNS |
| ACM (Certificate Manager) | App Service Managed Certificate |
| CloudWatch | Application Insights / Azure Monitor |
| CloudWatch Alarms | Azure Monitor Alerts |
| X-Ray | Application Insights (distributed tracing) |
| IAM Roles | Managed Identity + Azure RBAC |
| CodePipeline / CodeBuild | GitHub Actions / Azure DevOps |
| CloudFormation | Bicep / ARM Templates |
| Parameter Store | Azure App Configuration |
| Secrets Manager | Azure Key Vault |
| SQS | Azure Service Bus / Storage Queue |
| SNS | Azure Event Grid |
| Auto Scaling Group | App Service Autoscale |
| VPC | Azure VNet Integration |
| Security Groups | NSG + App Service Access Restrictions |

## Platform Preset → Runtime Stack Mapping

| Beanstalk Platform | App Service Runtime Stack |
|--------------------|---------------------------|
| Node.js 22 | Node 22 LTS |
| Node.js 24 | Node 24 LTS |
| Python 3.13 | Python 3.13 |
| Python 3.14 | Python 3.14 |
| Java 21 (Corretto) | Java 21 (Microsoft Build of OpenJDK) |
| Java 24 (Corretto) | Java 24 (Microsoft Build of OpenJDK) |
| .NET 10 on Linux | .NET 10 |
| Go (Docker) | Custom Container (Go) |
| Ruby | Custom Container (Ruby) |
| PHP 8.x | PHP 8.x |
| Docker | Azure App Service (Custom Container) |

## `.ebextensions/` Migration

Beanstalk `.ebextensions/` YAML configs map to Bicep and App Settings:

| `.ebextensions/` Feature | Azure Equivalent | Implementation |
|--------------------------|------------------|----------------|
| `option_settings` (env vars) | App Settings | Bicep `siteConfig.appSettings` |
| `packages` (yum/apt) | Startup script or Dockerfile | Custom container or startup command |
| `files` (config files) | Deployment package or Blob Storage | Include in app deployment |
| `commands` / `container_commands` | Startup command or deployment script | `az webapp config set --startup-file` |
| `Resources` (CloudFormation) | Bicep modules | Equivalent Azure resources |
| `services` (sysvinit) | WebJobs (continuous) or Azure Functions | Background processing — App Service "Always On" only prevents idle unload; it is NOT a replacement for sysvinit-style background services |

### Example: `.ebextensions/` → Bicep

```yaml
# .ebextensions/environment.config (AWS)
option_settings:
  aws:elasticbeanstalk:application:environment:
    NODE_ENV: production
    DB_HOST: mydb.xxx.rds.amazonaws.com
```

```bicep
// Bicep equivalent
resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  properties: {
    siteConfig: {
      appSettings: [
        { name: 'NODE_ENV', value: 'production' }
        { name: 'PGHOST', value: postgresServer.properties.fullyQualifiedDomainName }
      ]
    }
  }
}
```

## RDS → Azure Database Migration

| RDS Feature | Azure Equivalent |
|-------------|------------------|
| Multi-AZ deployment | Zone-redundant HA |
| Read replicas | Read replicas |
| Automated backups | Automated backups (up to 35 days) |
| Parameter groups | Server parameters |
| Subnet groups | VNet integration + private endpoints |
| IAM authentication | Microsoft Entra authentication |
| RDS Proxy | Azure Database for PostgreSQL Flexible Server (built-in PgBouncer) |

> 💡 **Tip:** Use Azure Database Migration Service (DMS) for data migration from RDS.

## Auto Scaling Migration

| Beanstalk Scaling | App Service Autoscale |
|-------------------|----------------------|
| `MinSize` / `MaxSize` | Min/Max instance count |
| `Trigger` metric (CPU, Network) | Autoscale rules (CPU, Memory, HTTP queue) |
| `BreachDuration` | Time window + cool-down period |
| `ScalingAdjustment` | Scale-out/in increment |
| Time-based scaling | Schedule-based autoscale rules |

```bicep
resource autoscale 'Microsoft.Insights/autoscalesettings@2022-10-01' = {
  properties: {
    targetResourceUri: appServicePlan.id
    profiles: [{
      capacity: { minimum: '2', maximum: '10', default: '2' }
      rules: [{
        metricTrigger: {
          metricName: 'CpuPercentage'
          operator: 'GreaterThan'
          threshold: 70
          timeAggregation: 'Average'
          timeWindow: 'PT5M'
        }
        scaleAction: {
          direction: 'Increase'
          type: 'ChangeCount'
          value: '1'
          cooldown: 'PT5M'
        }
      }]
    }]
  }
}
```

## ALB → App Service Load Balancing

| ALB Feature | Azure Equivalent |
|-------------|------------------|
| Path-based routing | App Service path mappings or Front Door rules |
| Host-based routing | Custom domains + Front Door |
| Health checks | App Service Health Check feature |
| SSL termination | Built-in TLS / Front Door |
| WAF | Azure Front Door WAF or App Gateway WAF |
| Sticky sessions | ARR Affinity (App Service) |

> For global load balancing with WAF, use **Azure Front Door** instead of App Service built-in LB.

## Environment Variables Migration

| Source | Target | Notes |
|--------|--------|-------|
| `option_settings` (env vars) | App Settings | Non-sensitive config |
| `option_settings` (secrets) | Key Vault references | `@Microsoft.KeyVault(SecretUri=...)` |
| Parameter Store refs | App Configuration | Shared config across environments |
| Secrets Manager refs | Key Vault | Secrets with rotation |
| `.env` file | App Settings + Key Vault | Split by sensitivity |

## Reference Links

- [AWS to Azure services comparison](https://learn.microsoft.com/en-us/azure/architecture/aws-professional/)
- [App Service overview](https://learn.microsoft.com/en-us/azure/app-service/overview)
- [App Service autoscale](https://learn.microsoft.com/en-us/azure/azure-monitor/autoscale/autoscale-get-started)
- [Azure Database Migration Service](https://learn.microsoft.com/en-us/azure/dms/dms-overview)
