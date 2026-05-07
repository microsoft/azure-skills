# Pre-Migration Assessment for Spring Boot to Azure Container Apps

## Local State Assessment

| Issue | Impact | Solution |
|-------|--------|----------|
| Singleton patterns | Multiple instances may run during updates | Refactor to stateless design |
| In-memory sessions | Lost during restarts/scaling | Migrate to Azure Cache for Redis |
| Local caching | Not shared across replicas | Use Azure Cache for Redis with Spring Data Redis |
| File-based state | Lost on restart | Migrate to Azure Cosmos DB, Azure SQL, or Azure Storage |

**State Migration Options:**
- **Azure Cache for Redis**: Session data, distributed caching
- **Azure Cosmos DB**: NoSQL data, document storage
- **Azure SQL/MySQL/PostgreSQL**: Relational data
- **Azure Storage Blobs**: Unstructured data, serialized objects

## File System Usage

| Pattern | Container Apps Solution |
|---------|------------------------|
| Temporary files | Ephemeral storage (automatic, deleted on restart) |
| Shared persistent data | Azure Files storage mounts |
| Static content serving | Azure Blob Storage + Azure CDN |
| User uploads | Azure Blob Storage with Azure Function triggers |

## Platform Compatibility

### Supported Java Versions
- **For Spring Boot 2.x source apps**: Java 8 or 11 supported for assessment
- **For Spring Boot 3.x target apps**: Java 17 or 21 required (verify with `java -version`)

### Spring Boot Version Requirements
- **Recommended target**: Spring Boot 3.x (requires Java 17+)
- **Supported source**: Spring Boot 2.x on Java 8/11 → plan upgrade to Java 17+ and follow [Spring Boot 3.0 Migration Guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-3.0-Migration-Guide)

### Spring Cloud Compatibility
- Verify Spring Cloud version matches Spring Boot 3.x requirements
- See [Spring Cloud versions](https://spring.io/projects/spring-cloud#overview)

## External Resources Inventory

Inventory all external dependencies. See [spring-dependency-patterns.md](spring-dependency-patterns.md) for configuration examples (databases, message brokers, caches).

### Identity Providers

| Provider | Configuration |
|----------|---------------|
| OAuth2 | Spring Security reference docs |
| Auth0 | Auth0 Spring Security documentation |
| PingFederate | Spring Security SAML 2.0/OIDC docs, PingIdentity docs |
| Microsoft Entra ID | Update redirect URIs to new Container Apps FQDN |

## Scheduled Jobs Assessment

| Job Type | Container Apps Solution |
|----------|------------------------|
| Unix cron jobs | Azure Container Apps Jobs (ephemeral) |
| Spring Batch tasks | Azure Container Apps Jobs |
| Quartz scheduler | Long-running app (handle scale-out race conditions) |
| Scheduled @Scheduled methods | Long-running app (handle multiple instances) |

## Configuration & Secrets

### Port Configuration
- Default: 8080
- Change via `server.port` or `SERVER_PORT` environment variable
- Configure in Container Apps ingress settings

### Secrets Checklist
1. Inventory all secrets in application.properties/application.yml
2. Document database passwords, API keys, connection strings
3. Plan migration to Azure Key Vault
4. Update app to use Key Vault references or environment variables

### Certificates
- Run `keytool -list -v -keystore <path>` to document SSL certificates
- Plan migration to Azure Key Vault or Container Apps managed certificates

## Deployment Architecture

**Document current state:**
- Number of instances
- CPU per instance (vCPU)
- RAM per instance (GiB)
- Regional distribution
- Uptime requirements/SLA

**Container Apps Limits:**
- Max 4 vCPU per container
- Max 8 GiB RAM per container
- Max 300 replicas per revision

## Assessment Checklist

- [ ] Identified all local state and planned migration to external storage
- [ ] Reviewed file system usage and selected storage solution
- [ ] Verified Java version compatibility (17+ for Spring Boot 3.x target; 8/11 for source assessment only)
- [ ] Confirmed Spring Boot 3.x or planned upgrade
- [ ] Inventoried databases (MySQL, PostgreSQL, MongoDB, Cosmos DB)
- [ ] Inventoried message brokers (ActiveMQ, IBM MQ, Azure Service Bus)
- [ ] Inventoried external caches (Redis)
- [ ] Documented identity providers (OAuth2, SAML, Entra ID)
- [ ] Identified scheduled jobs and selected execution model
- [ ] Listed all configuration secrets for Key Vault migration
- [ ] Documented SSL certificates
- [ ] Recorded current deployment architecture (instances, CPU, RAM)
- [ ] Reviewed logging configuration (console vs. file)
- [ ] Identified APM tools (Application Insights, custom agents)

## Complexity Guidelines

**Low Complexity:**
- Stateless Spring Boot app with external database
- No scheduled jobs or simple @Scheduled tasks
- Standard Java version (11, 17, 21)
- OAuth2/SAML authentication

**Medium Complexity:**
- In-memory session state requiring Redis migration
- File system writes requiring Azure Files or Blob Storage
- Spring Boot 2.x requiring upgrade to 3.x
- Message broker integration (ActiveMQ, Service Bus)
- Scheduled jobs requiring Jobs configuration

**High Complexity:**
- Multiple stateful components (local cache, sessions, file storage)
- Custom JVM agents or APM integrations
- Java 8 requiring upgrade to 11+
- Complex scheduled jobs with coordination requirements
- Multi-region deployment with traffic distribution
- Custom identity provider federation
