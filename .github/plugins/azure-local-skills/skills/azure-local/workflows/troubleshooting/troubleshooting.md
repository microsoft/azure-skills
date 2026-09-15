# Troubleshooting Azure Local

Use this workflow for Azure Local deployment failures, Arc registration/connectivity issues, Arc resource bridge/custom location problems, Azure Local VM or AKS Arc failures, SDN issues, update/upgrade failures, and evidence collection.

## Triage sequence

1. **Classify the failure** - Deployment, Arc registration, Arc gateway/private endpoint, Arc resource bridge, custom location, VM management, AKS on Azure Local, SDN, update/upgrade, monitoring, or workload.
2. **Collect context** - Subscription, resource group, Azure Local instance, version, custom location, resource bridge name, affected workload, connectivity model, recent changes, and exact error.
3. **Check Azure control plane** - Use Azure Resource Graph, resource health, activity logs, and extension/resource provisioning states.
4. **Check local prerequisites only when needed** - Some issues require direct access to an Azure Local machine. Use documented local commands only after confirming access and scope.
5. **Load scenario docs** - Use [docs-map](../../references/docs-map.md) to fetch the relevant troubleshooting article for the user's version.
6. **Prefer reversible remediation** - Retry, refresh status, fix permissions/connectivity, restore configuration, or complete documented repair steps before deletion/recreation.
7. **Validate and document** - Confirm resource state, Arc connectivity, workload health, and monitoring after remediation.

## Scenario routing

| Symptom | First checks |
| --- | --- |
| Deployment failed | Deployment operation details, prerequisites, topology, AD prep, Arc registration, permissions, portal/ARM errors |
| Arc registration failed | Network/proxy/firewall, Arc gateway/private endpoint, subscription permissions, Connected Machine agent state |
| Arc resource bridge unhealthy | Resource bridge resource state, VM state on local cluster, custom location, extension status, logs |
| Custom location unavailable | Resource bridge health, custom location resource state, namespace/extension mapping, RBAC |
| Azure Local VM create/update/delete failed | VM management extension, custom location, image/storage/logical network/NIC dependencies, IPv4/IP pool capacity |
| AKS on Azure Local failed | Azure Local health, Arc bridge/custom location, logical network/IP capacity, AKS Arc docs, cluster/node pool status |
| SDN issue | Network Controller, certificates, NSGs, load balancer, gateway, datacenter firewall, SDN logs |
| Update failed | Update phase, health checks, unsupported update path, solution extension content, offline import status |
| Upgrade failed | Upgrade readiness validation, post-upgrade steps, Network ATC, stretched cluster constraints |

## Evidence checklist

- Exact error text and operation ID/correlation ID.
- Azure resource IDs for Azure Local, Arc bridge, custom location, VM/AKS/SDN resources.
- Deployment/update/upgrade phase.
- Recent activity log entries.
- Extension provisioning states.
- Connectivity/proxy/private endpoint/Arc gateway configuration.
- Local logs only when Microsoft Learn requires them for the scenario.

## Critical safety rules

- Do not delete Arc resource bridge or custom location as a generic fix.
- Do not remove workload resources before confirming dependencies and recovery impact.
- Do not run unsupported update or upgrade repair paths.
- Ask before any remediation that can reboot hosts, interrupt storage/networking, delete resources, or break workload access.

## Related references

- [MCP and CLI tools](../../references/mcp-and-cli-tools.md)
- [Resource types and ARG patterns](../../references/resource-types.md)
- [Safety rules](../../references/safety-rules.md)
- [Azure Local docs map](../../references/docs-map.md)
