# Kubernetes to Azure Container Apps Migration

Detailed guidance for migrating containerized workloads from Kubernetes (GKE, EKS, self-hosted) to Azure Container Apps.

## Overview

| Kubernetes Source | Azure Equivalent |
|-------------------|------------------|
| GKE / EKS / Self-hosted Kubernetes | Azure Container Apps |
| Docker Registry / GCR / ECR | Azure Container Registry (ACR) |
| ConfigMap | Container Apps Environment Variables / Secrets |
| Secret | Azure Key Vault + Key Vault references |
| Ingress | Container Apps Ingress |
| Service (LoadBalancer/ClusterIP) | Container Apps Ingress (external/internal) |
| HPA (Horizontal Pod Autoscaler) | Container Apps Scaling Rules |
| Namespace | Container Apps Environment |
| Persistent Volume | Azure Files / Blob Storage (via volume mounts) |

## Resource Mapping

| Kubernetes Resource | Container Apps Equivalent | Notes |
|--------------|---------------------------|-------|
| Deployment | Container App | One deployment → one Container App |
| Service (type: LoadBalancer) | Ingress (external: true) | Public endpoint |
| Service (type: ClusterIP) | Ingress (external: false) | Internal only |
| ConfigMap | `env` with plaintext values | Use Key Vault for sensitive data |
| Secret | `secretRef` + Key Vault | Managed identity for access |
| HPA | `scale` rules (http, cpu, memory, custom) | HTTP concurrency, queue depth, etc. |
| Ingress | Ingress configuration | Automatic HTTPS, custom domains |
| Liveness/Readiness Probe | Health probes | HTTP, TCP, or startup probes |

## Configuration Mapping

| Kubernetes Manifest | Container Apps CLI/Bicep | Example |
|--------------|--------------------------|---------|
| `replicas: 3` | `--min-replicas 3 --max-replicas 3` | Static scaling |
| `resources.requests.cpu` | `--cpu 0.5` | CPU cores (0.25-4.0) |
| `resources.requests.memory` | `--memory 1Gi` | Memory (0.5Gi-8Gi) |
| `image: gcr.io/my-registry/app:v1` | `--image myacr.azurecr.io/app:v1` | After ACR import |
| `env: - name: KEY, value: val` | `--env-vars KEY=val` | Environment variables |
| `env: - name: SECRET, valueFrom: secretKeyRef` | `--secrets SECRET=keyvaultref:...` | Key Vault reference |
| `ports: - containerPort: 8080` | `--target-port 8080` | Container port |
| `livenessProbe.httpGet.path: /health` | YAML/Bicep `probes` config | Health probes not configurable via CLI |

## Migration Workflow

Follow these phases sequentially:

### Phase 1: Export Kubernetes Resources
- Use `kubectl get deployment,service,configmap,secret -o yaml` to export manifests
- Document current configuration (replicas, resources, env vars)
- Identify external dependencies (databases, message queues, storage)

### Phase 2: Assess Compatibility
- Verify workloads are stateless (Container Apps doesn't support StatefulSets)
- Check for unsupported features (DaemonSets, custom CRDs, Operators)
- Plan Jobs/CronJobs migration to Container Apps Jobs
- Identify ConfigMaps/Secrets requiring Key Vault migration
- Review persistent storage needs (migrate to Azure Files/Blob)

See [assessment-guide.md](assessment-guide.md) for detailed checklist.

### Phase 3: Migrate Container Images
- Create Azure Container Registry: `az acr create`
- Import images from GCR/ECR/Docker Hub: `az acr import`
- Or rebuild and push: `docker build` → `docker push`
- Enable managed identity access: `az containerapp registry set`

### Phase 4: Deploy to Container Apps
- Create Container Apps Environment
- Deploy Container Apps with converted configuration
- Configure ingress, scaling rules, and health probes
- Set up Key Vault references for secrets

See [deployment-guide.md](deployment-guide.md) for step-by-step deployment.

### Phase 5: Verify and Test
- Test external endpoints (HTTP/HTTPS ingress)
- Test internal service-to-service communication
- Verify environment variables and secrets
- Validate scaling behavior
- Check health probes and logs

## Unsupported Features

Container Apps **does NOT support**:
- StatefulSets (use Azure Database services instead)
- DaemonSets (not applicable in serverless model)
- Kubernetes PV/PVC objects (use Azure Files/Blob Storage via Container Apps volume mounts instead)
- Custom CNI networking
- Node affinity / pod affinity

For batch and scheduled workloads, migrate Kubernetes **Jobs / CronJobs** to **Azure Container Apps Jobs** instead of long-running Container Apps.

For unsupported Kubernetes platform features, consider **Azure Kubernetes Service (AKS)** instead.

## Best Practices

1. **Use Managed Identity** for ACR and Key Vault access (no passwords)
2. **Store secrets in Key Vault**, reference them in Container Apps
3. **Use Container Apps Environments** to group related microservices
4. **Enable Dapr** for service-to-service communication, state management, pub/sub
5. **Configure health probes** to ensure reliability
6. **Use scaling rules** based on HTTP concurrency or custom metrics
7. **Never modify source Kubernetes cluster** during migration
