# Networking and Security for Azure Local

Use this workflow for Azure Local physical networking, validated topology selection, SDN, NSGs, software load balancer, gateways, datacenter firewall, private endpoints, security baseline, governance, and compliance.

## Networking flow

1. **Identify layer** - Physical host/storage network, cloud deployment connectivity, SDN fabric, tenant/workload networking, or VM/AKS workload networking.
2. **Load current docs** - Use [docs-map](../../references/docs-map.md) for physical network requirements, network reference patterns, SDN overview, private endpoints, and firewall/proxy guidance.
3. **Collect topology** - Node count, storage switchless/switched design, converged/non-converged adapters, VLANs, IP ranges, DNS, gateways, proxy, and firewall requirements.
4. **Validate support** - Confirm the selected topology is supported for portal or ARM deployment.
5. **Plan changes** - For SDN/NSG/load balancer/gateway changes, map dependent workloads and rollback requirements before making changes.
6. **Apply with confirmation** - Network changes can interrupt management or workloads. Ask before applying changes.
7. **Validate reachability** - Check Arc connectivity, management endpoints, workload IPs, NSG behavior, load balancer/gateway health, DNS, and monitoring.

## Security flow

1. **Start from secure defaults** - Azure Local is secure by default with a baseline of security settings. Do not disable baseline controls without an explicit reason.
2. **Map governance** - Confirm Azure Policy, Defender for Cloud, Azure Monitor, RBAC, identity, and compliance requirements.
3. **Check secrets and certificates** - For private endpoints, SDN, and local identity scenarios, verify certificate and Key Vault requirements from docs.
4. **Apply least privilege** - Use Azure RBAC and Azure Local-specific roles for VM/workload administration.
5. **Document exceptions** - Any security exception must include reason, scope, owner, and validation plan.

## SDN routing

| Signal | Area |
| --- | --- |
| Network Controller, SDN infrastructure, SDN Express, SDN wizard | SDN deployment/management docs |
| NSG, default network access policy, tags | Network security group docs |
| Software load balancer, public IP assignment | Load balancer docs |
| Gateway connections, multisite, route reflector | Gateway and multisite docs |
| Datacenter firewall | Datacenter firewall docs |
| SDN certificate, Kerberos SPN, Network Controller security | SDN security docs |

## Guardrails

- Confirm topology and current state before changing IP ranges, VLANs, gateways, DNS, NSGs, load balancers, or firewall policy.
- Do not recommend unsupported network patterns for the user's node count/storage design.
- Do not disable security baseline controls or Defender/Policy protections as a workaround without explicit confirmation and risk disclosure.
- Use [safety-rules](../../references/safety-rules.md) for any change that can disrupt management, storage, or workloads.

## Handoff

- Deployment topology and initial Arc/private endpoint setup -> [Plan and Deploy](../plan-and-deploy/plan-and-deploy.md).
- Workload logical networks, NICs, VM connectivity, and AKS networking -> [Workload Management](../workload-management/workload-management.md).
- SDN or connectivity failure -> [Troubleshooting](../troubleshooting/troubleshooting.md).

## Related references

- [Azure Local docs map](../../references/docs-map.md)
- [MCP and CLI tools](../../references/mcp-and-cli-tools.md)
- [Safety rules](../../references/safety-rules.md)
