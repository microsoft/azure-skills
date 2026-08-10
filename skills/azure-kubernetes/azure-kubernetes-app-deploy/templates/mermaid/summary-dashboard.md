# Deployment Summary Template

After successful deployment, render this summary in the terminal.

## Template

```
╔══════════════════════════════════════════════════════╗
║  DEPLOYMENT SUCCESSFUL                               ║
║  {{APP_NAME}} is live at {{APP_URL}}                 ║
║  Deployed: {{DEPLOY_TIMESTAMP}}                      ║
╚══════════════════════════════════════════════════════╝
```

### Azure Resources

| Resource | Type | Name | Portal Link |
|----------|------|------|-------------|
| Resource Group | resourceGroups | {{RG_NAME}} | `https://portal.azure.com/...` |
| AKS Cluster | managedClusters | {{AKS_NAME}} | `https://portal.azure.com/...` |
| Container Registry | registries | {{ACR_NAME}} | `https://portal.azure.com/...` |
| {{BACKING_SERVICE}} | {{TYPE}} | {{NAME}} | `https://portal.azure.com/...` |

Replace each portal link with the full URL using the subscription ID, resource group, and resource name.

### Files Created / Modified

List all files generated during the workflow with `+` for created and `~` for modified.

### Monthly Cost Estimate

List each Azure resource with its SKU/tier and approximate monthly cost.

### Next Steps

1. **Custom Domain** — Point DNS to external IP, update Gateway/Ingress
2. **TLS Certificate** — Enable HTTPS via cert-manager or Azure-managed TLS
3. **Monitoring Dashboard** — Set up Azure Monitor / Prometheus + Grafana
4. **Scaling** — Tune HPA min/max replicas and resource requests/limits
5. **CI/CD Trigger** — Push to default branch to trigger pipeline
