# Google Cloud Run → Azure Container Apps

Detailed guidance for migrating Cloud Run serverless containers to Azure Container Apps.

## Overview

| Cloud Run | Azure Container Apps |
|-----------|---------------------|
| Cloud Run Service | Container App |
| Artifact Registry / GCR | Azure Container Registry (ACR) |
| Secret Manager | Azure Key Vault |
| Cloud Logging | Azure Monitor / Log Analytics |
| VPC Connector | VNet Integration |

## Critical Differences

| Feature | Cloud Run | Container Apps | Impact |
|---------|-----------|----------------|--------|
| Max Timeout | 60 min | 30 min (1800s) | Redesign long-running tasks |
| CPU Allocation | Request-based or always | Always allocated | Cost model changes |
| Max Instances | 0–1000 | 0–300 per revision | Validate instance needs |
| Concurrency | 1–1000 | 1–300 | Adjust concurrency settings |
| Startup Time | 10 min max | 240s default | Validate startup time |

## Migration Workflow

1. **Assess** — Analyze Cloud Run config → [cloudrun-assessment-guide.md](cloudrun-assessment-guide.md)
2. **Images** — Migrate GCR/Artifact Registry → ACR
3. **Config** — Convert YAML, secrets → Key Vault, set up infrastructure
4. **Deploy** — Deploy to Container Apps → [cloudrun-deployment-guide.md](cloudrun-deployment-guide.md)
5. **Validate** — Health checks, logs, scaling verification

## Service Dependency Mappings

| GCP Service | Azure Equivalent | Notes |
|-------------|------------------|-------|
| Cloud SQL (PostgreSQL) | Azure Database for PostgreSQL | Connection string + managed identity |
| Cloud SQL (MySQL) | Azure Database for MySQL | Connection string + managed identity |
| Firestore | Azure Cosmos DB | SDK change required |
| Cloud Storage | Azure Blob Storage | SDK change required |
| Cloud Memorystore (Redis) | Azure Cache for Redis | Connection string update |
| Pub/Sub | Azure Service Bus / Event Grid | SDK change required |
| Cloud Tasks | Azure Queue Storage / Service Bus | SDK change required |
| Secret Manager | Azure Key Vault | Managed identity integration |
| Cloud Logging | Azure Monitor Logs | Auto-configured |
| Cloud Scheduler | Azure Logic Apps / Functions Timer | HTTP trigger to Container Apps |
