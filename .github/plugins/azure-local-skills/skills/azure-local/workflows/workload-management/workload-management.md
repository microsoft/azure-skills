# Workload Management on Azure Local

Use this workflow for Azure Local VMs enabled by Azure Arc, AKS on Azure Local, SQL Server on Azure Local, workload storage/network resources, RBAC, GPU assignment, and disaster recovery.

## Routing

| User intent | Guidance |
| --- | --- |
| Create, manage, update, delete, or connect to Azure Local VMs | Follow Azure Local VM management docs and use Arc VM resource patterns. |
| Create VM images, disks, storage paths, logical networks, NICs, or NSGs | Confirm custom location and dependency order before mutation. |
| Manage AKS on Azure Local / AKS hybrid | Use AKS hybrid docs under the Azure Local table of contents, not standard AKS-only assumptions. |
| Run SQL Server on Azure Local | Fetch SQL Server on Azure Local deployment docs for current prerequisites. |
| Configure backup, ASR, or workload resiliency | Use disaster recovery docs and confirm RPO/RTO before changes. |
| Assign workload access | Use Azure Local built-in RBAC roles and least privilege. |

## Azure Local VM workflow

1. **Confirm context** - Identify Azure Local instance, custom location, resource group, logical network, image source, storage path, and user permissions.
2. **Confirm prerequisites** - Verify Arc resource bridge, custom location, infrastructure logical network, and VM management extension are healthy.
3. **Build dependencies in order** - Storage paths/images/logical networks/NICs/disks before VM creation.
4. **Apply least privilege** - Assign built-in Azure Local VM roles only as needed.
5. **Create or change VM** - Use portal, Azure CLI, PowerShell, ARM/Bicep, or Terraform paths documented for Azure Local VMs.
6. **Validate** - Confirm provisioning state, power state, network reachability, guest management/extension status, and monitoring/backup configuration where required.

## AKS on Azure Local workflow

1. Confirm the request is AKS on Azure Local, AKS hybrid, or AKS Arc rather than AKS in public Azure.
2. Fetch current AKS hybrid docs from [docs-map](../../references/docs-map.md).
3. Check Azure Local instance health, Arc resource bridge/custom location, logical networks, IP capacity, and identity/RBAC prerequisites.
4. Use documented create/upgrade/scale/delete flows for AKS on Azure Local.
5. Validate cluster state, node pools, Kubernetes access, workload networking, storage classes, and Azure Arc connection.

## Safety checks

- Ask before deleting VMs, disks, NICs, images, storage paths, logical networks, AKS clusters, NSGs, or custom locations.
- Do not remove Arc resource bridge or custom location to fix workload issues unless following a confirmed decommission/reimage path.
- Warn that changes made locally inside VMs or through local tools may not be reflected in Azure for Azure Local VM management.
- Confirm IPv4 requirements for Azure Local VM logical networks where relevant.

## Handoff

- Public Azure VM sizing/pricing/capacity reservations -> `azure-compute`.
- Public Azure AKS optimization -> `azure-kubernetes`.
- Azure Local SDN/NSG/load balancer/gateway configuration -> [Networking and Security](../networking-and-security/networking-and-security.md).
- Azure Local workload failures -> [Troubleshooting](../troubleshooting/troubleshooting.md).

## Related references

- [Resource types and ARG patterns](../../references/resource-types.md)
- [MCP and CLI tools](../../references/mcp-and-cli-tools.md)
- [Safety rules](../../references/safety-rules.md)
- [Azure Local docs map](../../references/docs-map.md)
