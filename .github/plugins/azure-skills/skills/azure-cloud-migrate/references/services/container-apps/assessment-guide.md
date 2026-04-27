# Kubernetes to Azure Container Apps - Assessment Guide

## Compatibility Matrix

### Kubernetes → Container Apps Resource Mapping

| Kubernetes Concept | Container Apps Equivalent | Supported | Notes |
|-------------------|--------------------------|-----------|-------|
| Deployment | Container App | ✅ Yes | One-to-one mapping for stateless workloads |
| Service (ClusterIP) | Internal ingress | ✅ Yes | Set `ingress.external: false` |
| Service (LoadBalancer) | External ingress | ✅ Yes | Set `ingress.external: true` |
| Ingress | Built-in ingress with custom domain | ✅ Yes | Supports TLS, traffic splitting |
| ConfigMap | Environment variables | ✅ Yes | Inline or from secrets |
| Secret | Secrets (Key Vault refs preferred) | ✅ Yes | Use managed identity for Key Vault |
| CronJob | Container Apps Job (scheduled) | ✅ Yes | Cron expression syntax |
| Job | Container Apps Job (manual/event) | ✅ Yes | One-time or event-triggered |
| HPA | Built-in scaling rules | ✅ Yes | HTTP, TCP, KEDA-compatible scalers |
| PersistentVolumeClaim | Azure Files mount | ⚠️ Limited | EmptyDir and Azure Files only; no block storage |
| DaemonSet | N/A | ❌ No | Consider sidecar containers or external agents |
| StatefulSet | N/A | ❌ No | Use external state (Cosmos DB, Redis, SQL) |
| Custom CRDs / Operators | N/A | ❌ No | Evaluate if Dapr components can replace |
| NetworkPolicy | VNet NSG rules | ⚠️ Limited | Configure at Environment subnet level |

### Resource Limits

| Resource | Kubernetes (typical) | Container Apps Maximum | Migration Impact |
|----------|---------------------|----------------------|------------------|
| CPU per container | Up to 64+ vCPU | 4 vCPU | Split large containers |
| Memory per container | Up to 256+ GiB | 8 GiB | Redesign memory-intensive workloads |
| Replicas per app | 1000+ | 300 per revision | Validate scale requirements |
| Request timeout | Configurable (hours+) | 240 seconds default | Redesign long-running requests |
| Startup probe timeout | Configurable | 240 seconds | Optimize startup time |
| Containers per pod/app | 10+ | Up to 10 sidecars | Init + sidecar containers supported |

## Unsupported Patterns

### Critical Blockers

1. **StatefulSets with persistent storage**
   - **Why**: Container Apps is designed for stateless workloads
   - **Alternative**: Migrate state to Azure Cosmos DB, Azure SQL, Redis, or Storage

2. **DaemonSets for node-level agents**
   - **Why**: No node-level access in managed environment
   - **Alternative**: Use Azure Monitor agents, Dapr components, or sidecar containers

3. **Privileged containers or host networking**
   - **Why**: Security isolation in managed platform
   - **Alternative**: Redesign to avoid host-level access

4. **Custom CRDs and Operators**
   - **Why**: No Kubernetes API server access
   - **Alternative**: Use Dapr state management, bindings, or Azure PaaS services

5. **Direct Kubernetes API calls from apps**
   - **Why**: Kubernetes API not exposed
   - **Alternative**: Use environment variables, service discovery via DNS, or Dapr

### Storage Considerations

- **EmptyDir**: Supported (ephemeral storage)
- **Azure Files**: Supported via volume mounts
- **Persistent Block Storage**: Not supported (migrate to Azure Blob, SQL, Cosmos DB)

## Assessment Checklist

### 1. Workload Inventory

- List all Deployments, StatefulSets, DaemonSets in target namespaces
- Identify workload types: API, background worker, CronJob, StatefulSet
- Document current resource requests/limits (CPU, memory)
- Note replica counts (min, max, typical)

### 2. Network Configuration

- **Service Types**: ClusterIP (internal) vs LoadBalancer (external)
- **Ingress**: Document hostnames, TLS certificates, path routing rules
- **Service Mesh**: Document if using Istio, Linkerd (consider migrating to Dapr)
- **NetworkPolicies**: List egress/ingress rules (map to NSG rules or VNet integration)

### 3. Storage and State

- **PersistentVolumeClaims**: List volumes, sizes, access modes (ReadWriteOnce, ReadWriteMany)
- **StatefulSets**: Document state storage patterns (candidates for external state migration)
- **EmptyDir/Temp Storage**: Note usage patterns (supported in Container Apps)
- **ConfigMaps/Secrets**: Count and categorize (migrate inline or to Key Vault)

### 4. Scaling and Performance

- **HPA**: Document scaling metrics (CPU, memory, custom metrics)
- **Min/Max Replicas**: Verify within Container Apps limits (0-300)
- **Startup Time**: Measure pod startup latency (must be <240s)
- **Request Patterns**: Long-running requests (>240s) need redesign

### 5. Dependencies

- **Internal Services**: List service-to-service calls (use internal DNS in Container Apps)
- **External Services**: Databases, APIs, message queues, storage
- **Authentication**: Service accounts, RBAC roles (map to managed identities)
- **Observability**: Logging, metrics, tracing (migrate to Azure Monitor, App Insights)

### 6. CI/CD and Deployment

- **Pipeline Tools**: kubectl, Helm, Kustomize, ArgoCD, Flux
- **Image Registries**: Docker Hub, GCR, ECR, private registries (migrate to ACR)
- **Deployment Strategy**: Rolling update, blue/green, canary (Container Apps supports traffic splitting)

## Complexity Assessment Guidelines

### Low Complexity
- Stateless Deployments with ClusterIP or LoadBalancer Services
- Simple environment variables (no complex ConfigMaps)
- No persistent storage or external state already in use
- Standard HTTP/gRPC ingress
- No service mesh dependencies

### Medium Complexity
- Multiple Deployments with inter-service communication
- ConfigMaps and Secrets requiring Key Vault migration
- HPA with custom metrics (need KEDA scaler mapping)
- CronJobs (map to Container Apps Jobs)
- Ingress with TLS and custom domains

### High Complexity
- StatefulSets requiring state migration to external services
- Service mesh (Istio/Linkerd) requiring Dapr migration
- Custom CRDs or Operators (need redesign)
- NetworkPolicies requiring VNet/NSG configuration
- Large-scale deployments (>100 replicas, need architecture review)
- Workloads exceeding Container Apps resource limits (>4 vCPU, >8 GiB)

## Assessment Report Structure

Generate `k8s-migration-assessment.md` with:

1. **Executive Summary**: Cluster name, namespace(s), workload count, complexity (Low/Medium/High), estimated timeline, Azure cost
2. **Current State**: Deployment inventory, resource usage, scaling config, storage usage, networking topology
3. **Compatibility Analysis**: Supported workloads, blockers, redesign requirements (StatefulSets, DaemonSets, CRDs)
4. **Azure Target**: Required resources (resource group, Container Apps Environment, ACR, Key Vault, Log Analytics, VNet if needed)
5. **Migration Plan**:
   - State migration strategy (databases, caches, storage)
   - Image migration approach (ACR import, rebuild)
   - IaC generation plan (Bicep templates per Deployment)
   - Deployment sequence (dependencies first, then consumers)
6. **Risk Assessment**: Blockers, feature gaps, performance considerations, downtime estimate
7. **Validation Tests**: Smoke tests, integration tests, performance benchmarks
