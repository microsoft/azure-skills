# Plan and Deploy Multi-Rack Azure Local

Use this workflow when planning, preparing, or deploying a multi-rack instance. Fetch current procedures through [docs-map](../../references/docs-map.md) before giving step-by-step commands.

> Multi-rack is in preview. Confirm regional availability and supported configurations before committing to a design.

## Intake

| Question | Why it matters |
| --- | --- |
| Is this multi-rack or standard Azure Local? | Determines which skill and procedure set applies. Standard deployments use the `azure-local` skill. |
| Target Azure region | NFC and Cluster Manager must exist in the target region. |
| Existing NFC/CM pair? | Reused across deployments until cluster quota is reached. |
| Rack count and layout | Minimum four racks: one aggregation rack plus three or more compute racks. |
| Hardware BOM status | Multi-rack uses a prescriptive BOM from a Microsoft hardware partner. |
| Connectivity and identity model | Affects provider registration, permissions, and fabric design. |
| Workload profile | VMs, AKS, GPU needs drive capacity and network design. |

## Sequence

1. **Confirm scale** — Verify multi-rack via the resource providers in use or the customer's hardware. See [resource-types](../../references/resource-types.md). If standard Azure Local, stop and hand off to the `azure-local` skill.
2. **Load authoritative docs** — Fetch `multi-rack-overview` and `multi-rack-prerequisites` via [docs-map](../../references/docs-map.md).
3. **Install CLI extensions** — `networkcloud`, `managednetworkfabric`, `stack-hci-vm` and supporting extensions per [cli-and-prereqs](../../references/cli-and-prereqs.md).
4. **Register resource providers** — Use the complete list from the prerequisites article, not a remembered subset.
5. **Create the control plane** — Network Fabric Controller, then the paired Cluster Manager in the same region and subscription.
6. **Validate hardware and cabling** — Aggregation rack, compute racks, terminal server connections, and SAN must match the BOM before cluster creation.
7. **Deploy the cluster** — Follow the documented cluster creation flow; do not improvise ARM payloads.
8. **Provision the fabric** — Network fabric bootstrapping and workload network configuration per [networking](../networking/networking.md).
9. **Validate** — Confirm cluster, racks, bare metal machines, storage appliances, fabric, custom location, and expected extensions all exist and are healthy.
10. **Hand off** — [workload-management](../workload-management/workload-management.md) for workloads, [operate-and-monitor](../operate-and-monitor/operate-and-monitor.md) for day-2.

## Guardrails

- Do not propose cluster creation before the NFC/CM pair exists and is healthy.
- Do not generate fabric or isolation domain changes without user confirmation.
- Do not substitute standard Azure Local deployment articles; the procedures differ.
- Do not treat a partially registered provider set as ready.
- Follow [safety-rules](../../references/safety-rules.md) for anything destructive.

## Evidence to collect

- Subscription, tenant, region, resource groups.
- NFC and Cluster Manager resource IDs and provisioning state.
- Cluster name, rack count and roles, bare metal machine inventory.
- Storage appliance status.
- Fabric resource state and isolation domain configuration.
- CLI extension versions.

## Related references

- [Docs map](../../references/docs-map.md)
- [CLI and prerequisites](../../references/cli-and-prereqs.md)
- [Resource types](../../references/resource-types.md)
- [Safety rules](../../references/safety-rules.md)
