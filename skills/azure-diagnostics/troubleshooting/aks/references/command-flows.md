# AKS Command Flows

## Cluster Baseline Flow

```text
Resolve subscription -> resolve resource group -> resolve cluster -> inspect cluster state -> inspect node pools -> inspect resource health -> inspect recent operations
```

CLI fallback when AKS-MCP cannot perform the cluster baseline read — run the **[`aks-baseline`](../../../scripts/aks-baseline.sh)** script, which gathers cluster state, node pools, and recent operations as one read-only digest:

```bash
# bash
./scripts/aks-baseline.sh -g <resource-group> -n <cluster-name>
```

```powershell
# PowerShell
.\scripts\aks-baseline.ps1 -ResourceGroup <resource-group> -Cluster <cluster-name>
```

## Kubernetes Baseline Flow

```text
Check API reachability -> inspect nodes -> inspect kube-system -> inspect events -> inspect affected namespace -> inspect pod details and logs
```

CLI fallback when AKS-MCP cannot perform the Kubernetes baseline read — the same **[`aks-baseline`](../../../scripts/aks-baseline.sh)** script also covers node readiness, unhealthy pods, kube-system health, and recent warning events. Pass `--namespace` to include an affected namespace, then deep-dive on a specific pod:

```bash
# bash
./scripts/aks-baseline.sh -g <resource-group> -n <cluster-name> --namespace <namespace>
kubectl describe pod <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --previous
```

```powershell
# PowerShell
.\scripts\aks-baseline.ps1 -ResourceGroup <resource-group> -Cluster <cluster-name> -Namespace <namespace>
```

## Connectivity Flow

```text
pod -> service -> endpoints -> ingress or load balancer -> DNS -> network controls
```

CLI fallback when AKS-MCP cannot perform the connectivity read:

```bash
kubectl get pods -n <namespace> -o wide
kubectl get svc -n <namespace>
kubectl get endpoints -n <namespace>
kubectl get ingress -n <namespace>
kubectl describe ingress <ingress-name> -n <namespace>
```

## Detector Flow

```text
resolve cluster resource ID -> list detectors or choose category -> select a focused time window -> run the detector or category -> rank critical findings above warnings -> ignore emerging issues when choosing the primary root cause
```

## Monitoring Flow

```text
check resource health -> inspect metrics -> verify diagnostics settings -> inspect control plane logs if available -> correlate with Application Insights or namespace symptoms
```

## Scheduling Flow

```text
pod events -> node capacity -> taints and tolerations -> affinity rules -> PVC state -> quotas
```

CLI fallback when AKS-MCP cannot perform the scheduling read:

```bash
kubectl describe pod <pod-name> -n <namespace>
kubectl get nodes -o wide
kubectl describe node <node-name>
kubectl get pvc -n <namespace>
kubectl describe quota -n <namespace>
```

## Deep Diagnostics Flow (Inspektor Gadget)

```text
Standard diagnostics inconclusive -> resolve target node -> select gadget from symptom-to-gadget map -> run IG command with namespace/pod filters -> interpret output -> correlate with prior evidence
```

Use when steps 1–3 of the evidence order (Azure-side, Kubernetes-side, and detector evidence) do not reveal root cause. See [inspektor-gadget.md](inspektor-gadget.md) for the full gadget catalog and command patterns.

## Safety Boundary

Treat the following as change operations and avoid them unless the user explicitly asks for remediation:

- deleting or restarting pods
- cordon and drain operations
- scaling workloads or node pools
- cluster upgrade operations
- DNS, route, NSG, or firewall changes
