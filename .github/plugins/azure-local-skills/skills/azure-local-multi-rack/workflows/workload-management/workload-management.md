# Multi-Rack Workload Management

Use for Arc VMs, images, disks, GPU, and AKS on a multi-rack instance. Multi-rack has its own VM management article set — do not substitute standard Azure Local VM procedures.

## Intake

| Question | Why it matters |
| --- | --- |
| Confirmed multi-rack? | Standard Azure Local VM procedures do not apply. |
| Cluster, custom location, resource group | Required scope for every workload command. |
| Workload type | VM, AKS, or GPU workloads have different prerequisites. |
| Network requirements | Logical network, virtual network, or load balancer must exist first. |
| Image source | Marketplace, custom image, or image storage account. |

## Sequence

1. **Confirm scale and scope** — Multi-rack, plus cluster and custom location. See [resource-types](../../references/resource-types.md).
2. **Check VM prerequisites** — Fetch `multi-rack-vm-management-prerequisites` via [docs-map](../../references/docs-map.md).
3. **Prepare networking first** — Logical networks and network interfaces must exist before VM creation. See [networking](../networking/networking.md).
4. **Prepare images** — Manage VM images or the image storage account per the multi-rack image articles.
5. **Create or manage VMs** — Use the multi-rack Arc VM articles for create, manage, and resource operations.
6. **Attach storage** — Data disks and snapshots per the multi-rack disk articles.
7. **GPU workloads** — Follow GPU preparation before device management.
8. **AKS** — Use the AKS multi-rack architecture doc; AKS on multi-rack differs from AKS on standard Azure Local.
9. **Access** — SSH connectivity and RBAC role assignment per the relevant articles.

## Guardrails

- Ask before VM power, delete, disk detach, or snapshot deletion.
- Do not create workloads before confirming the target logical network and custom location.
- Do not reuse standard Azure Local commands or article steps.
- Confirm required CLI extensions are installed — see [cli-and-prereqs](../../references/cli-and-prereqs.md).
- Follow [safety-rules](../../references/safety-rules.md).

## Evidence to collect

- Cluster, custom location, resource group, region.
- VM names and resource IDs, power state, provisioning state.
- Attached logical networks and network interfaces.
- Image source and version.
- Disk and snapshot inventory.
- Extension versions and CLI extension versions.

## Related references

- [Docs map](../../references/docs-map.md)
- [CLI and prerequisites](../../references/cli-and-prereqs.md)
- [Resource types](../../references/resource-types.md)
- [Safety rules](../../references/safety-rules.md)
