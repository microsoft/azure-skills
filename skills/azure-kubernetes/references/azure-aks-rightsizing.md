# AKS Pod Rightsizing

Identify pods requesting far more CPU/memory than they use and recommend reduced resource requests.

## Prerequisites — Check Monitoring State First

Before collecting usage data, determine what monitoring is available on the cluster:

```bash
# 1. Check if Azure Managed Prometheus is enabled
az aks show \
  --name "<CLUSTER_NAME>" --resource-group "<RESOURCE_GROUP>" \
  --query "azureMonitorProfile.metrics.enabled" -o tsv

# 2. Check if Container Insights (Log Analytics) is enabled
az aks show \
  --name "<CLUSTER_NAME>" --resource-group "<RESOURCE_GROUP>" \
  --query "addonProfiles.omsagent.enabled" -o tsv

# 3. Check if Metrics Server is running (pre-installed on AKS, but may be unhealthy)
kubectl get deployment metrics-server -n kube-system
```

Based on the result, follow the appropriate path:

| State | Rightsizing Possible? | Data Source | Accuracy |
|-------|-----------------------|-------------|----------|
| Azure Managed Prometheus enabled |  Yes | Prometheus metrics via Azure Monitor | Best — full P95/7-day history |
| Container Insights (Log Analytics) enabled |  Yes | KQL queries on `Perf` / `KubePodInventory` | Good — 7-day trends |
| Only Metrics Server (no Azure Monitor) |  Limited | `kubectl top pods` — live data only | Low — no historical trends |

> If nothing is enabled, Metrics Server is pre-installed on AKS — confirm it is healthy and use it for live rightsizing data:
> ```bash
> kubectl get deployment metrics-server -n kube-system
> kubectl top pods --all-namespaces --sort-by=cpu
> ```
> For historical P95 trends (more accurate rightsizing), recommend enabling Azure Managed Prometheus. Warn user this incurs cost and wait for confirmation before proceeding.

---

## Detection

```bash
# Authenticate to cluster
az aks get-credentials --name "<CLUSTER_NAME>" --resource-group "<RESOURCE_GROUP>"

# List requests/limits for ALL containers per pod (includes sidecars)
# Using [*] ensures multi-container pods are not misrepresented
kubectl get pods --all-namespaces \
  -o custom-columns="NAMESPACE:.metadata.namespace,POD:.metadata.name,CONTAINERS:.spec.containers[*].name,CPU_REQ:.spec.containers[*].resources.requests.cpu,MEM_REQ:.spec.containers[*].resources.requests.memory,CPU_LIM:.spec.containers[*].resources.limits.cpu,MEM_LIM:.spec.containers[*].resources.limits.memory"

# Live per-container usage (shows each container individually, including sidecars)
kubectl top pods --all-namespaces --containers --sort-by=cpu
```

## Historical Metrics (Azure Monitor — use when Prometheus or Container Insights is enabled)

First discover available metric names, then query:

```bash
az monitor metrics list-definitions \
  --resource "<AKS_RESOURCE_ID>" \
  --query "[].name.value" -o tsv
```

```bash
az monitor metrics list \
  --resource "<AKS_RESOURCE_ID>" \
  --metric "<METRIC_NAME_FROM_ABOVE>" \
  --interval PT1H --aggregation Average \
  --start-time "<YYYY-MM-DDTHH:mm:ssZ>" \
  --end-time "<YYYY-MM-DDTHH:mm:ssZ>"
```

## Optimization Rules

| Condition | Recommendation | Risk |
|-----------|----------------|------|
| CPU request >5x P95 actual | Reduce to `P95 * 1.2` | Medium |
| Memory request >3x P95 actual | Reduce to `P95 * 1.2` | Medium |
| CPU request >2x P95 actual | Recommend rightsizing with 20% buffer | Low |
| No resource limits set | Add limits to prevent noisy-neighbor waste | Low |
| No VPA/HPA configured | Suggest enabling Vertical Pod Autoscaler | Low |

> For VPA setup and configuration, see [azure-aks-vpa.md](./azure-aks-vpa.md).

## YAML Patch Format
```yaml
# Rightsizing patch for <NAMESPACE>/<DEPLOYMENT_NAME>
# Current: CPU request=<CURRENT>, P95 actual=<ACTUAL>
# Recommended: CPU request=<NEW> (P95 * 1.2 buffer)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <DEPLOYMENT_NAME>
  namespace: <NAMESPACE>
spec:
  template:
    spec:
      containers:
      - name: <CONTAINER_NAME>
        resources:
          requests:
            cpu: "<NEW_CPU>"
            memory: "<NEW_MEM>"
          limits:
            cpu: "<NEW_CPU_LIMIT>"     # e.g. CPU limit = 1.5x CPU request, or preserve existing limit-to-request ratio
            memory: "<NEW_MEM_LIMIT>"  # e.g. memory limit = 1.25x memory request, or preserve existing limit-to-request ratio
```

> Risk: Medium-High. Always review patches before applying. Test in non-production first. Get explicit user confirmation before applying to production.
