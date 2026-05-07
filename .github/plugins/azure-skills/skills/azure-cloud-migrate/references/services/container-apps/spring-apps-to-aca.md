# Spring Boot to Azure Container Apps Migration

> Migrate Spring Boot applications from Azure Spring Apps, VMs, or other platforms to Azure Container Apps with containerization, deployment, and Spring Cloud integration.

## Overview

This migration enables you to move existing Spring Boot applications from Azure Spring Apps (or any platform) to Azure Container Apps with minimal code changes.

## Migration Scenarios

| Source Platform | Target Platform | Migration Path |
|----------------|-----------------|----------------|
| Azure Spring Apps | Azure Container Apps | Assess → Containerize → Deploy → Spring Cloud components |
| Spring Boot on VMs | Azure Container Apps | Assess → Containerize → Deploy |
| Spring Boot (other cloud) | Azure Container Apps | Assess → Containerize → Deploy |

## Service Mapping

| Spring Apps Feature | Container Apps Equivalent |
|-------------------|---------------------------|
| App Deployment | Container App |
| Service Registry (Eureka) | Managed Eureka for Spring (`eureka-server-for-spring`); alt: Dapr service invocation + internal DNS |
| Config Server | Managed Config Server for Spring (`config-server-for-spring`); alt: Azure App Configuration + Key Vault |
| Spring Cloud Gateway | Managed Gateway for Spring; alt: Azure API Management / Container Apps ingress |
| Distributed Tracing | Application Insights |
| Log Streaming | Log Analytics Workspace |

## Pre-Migration Assessment

Assess your Spring Boot application for migration readiness:

- **Local State**: Check for in-memory sessions, singletons, file-based state → [spring-assessment-guide.md](spring-assessment-guide.md#local-state-assessment)
- **File System**: Identify file writes, temp files, shared storage needs → [spring-assessment-guide.md](spring-assessment-guide.md#file-system-usage)
- **Platform Compatibility**: Verify Java 17+, Spring Boot 3.x support → [spring-assessment-guide.md](spring-assessment-guide.md#platform-compatibility)
- **External Resources**: Inventory databases, message brokers, caches → [spring-assessment-guide.md](spring-assessment-guide.md#external-resources-inventory)

## Migration Workflow

1. **Assess** — Analyze application for migration readiness
   > Present findings and complexity rating to user. Ask: "Assessment complete — proceed with containerization?"
2. **Containerize** — Create Dockerfile, build image, push to ACR
3. **Provision** — Create Container Apps environment, configure logging
4. **Deploy** — Deploy container to Azure Container Apps
5. **Optimize** — Add Spring Cloud components (Config, Eureka, Gateway)

See [spring-deployment-guide.md](spring-deployment-guide.md) for detailed phase-by-phase instructions.

## Key Differences from Azure Spring Apps

| Aspect | Azure Spring Apps | Container Apps |
|--------|-------------------|----------------|
| Deployment Unit | JAR/WAR | Container Image |
| Service Discovery | Built-in Eureka | Managed Eureka component (or Dapr / DNS) |
| Configuration Management | Built-in Config Server | Managed Config Server component (or App Configuration) |
| Scaling | Auto-scaling | HTTP/CPU/Memory/Custom metrics |
| Networking | VNet injection | VNet integration + Internal ingress |

## Best Practices

- Use managed identity for Azure resource access (no connection strings)
- Store secrets in Azure Key Vault, reference via environment variables
- Use Application Insights for observability
- Enable Log Analytics for centralized logging
- Use Azure Files for persistent storage if needed

## Next Steps After Migration

After successful migration:
1. Configure Spring Cloud components (optional)
2. Set up CI/CD pipeline with GitHub Actions / Azure DevOps
3. Configure custom domains and SSL certificates
4. Implement autoscaling rules
5. Hand off to `azure-prepare` for infrastructure optimization
