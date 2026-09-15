# Multi-Rack Operations and Monitoring

Use for health, metrics, serial console access, and failure triage on a multi-rack instance.

## Intake

| Question | Why it matters |
| --- | --- |
| Confirmed multi-rack? | Standard Azure Local troubleshooting does not apply. |
| Scope of impact | Single VM, machine, rack, fabric, or SAN changes the approach. |
| When it started | Correlates with updates, fabric changes, or hardware events. |
| Monitoring configured? | Metrics and Log Analytics availability determines evidence sources. |
| Local or console access available? | Serial console may be required for machine-level issues. |

## Sequence

1. **Confirm scale** — See [resource-types](../../references/resource-types.md).
2. **Establish blast radius** — Read-only: cluster, racks, bare metal machines, storage appliances, fabric.
3. **Check control plane** — Cluster Manager and NFC provisioning state before blaming workloads.
4. **Use documented monitoring** — Fetch `multi-rack-monitor-overview` and cluster metrics guidance via [docs-map](../../references/docs-map.md).
5. **Narrow by layer** — Workload, then logical network, then fabric, then hardware. Do not skip layers.
6. **Targeted references** — Arc VM troubleshooting for VM-level faults; storage appliance error messages for SAN faults; serial console for machine-level access.
7. **Propose remediation** — Present the change, its blast radius, and its reversibility. Get confirmation before acting.

## Triage routing

| Symptom | Start at |
| --- | --- |
| Single VM unhealthy | Arc VM troubleshooting article |
| Multiple VMs on one machine | Bare metal machine state, then serial console |
| Whole rack affected | Rack and fabric state; check aggregation rack |
| East-west connectivity broken | Isolation domains and logical networks |
| North-south connectivity broken | Route policy, public IP, NAT gateway |
| Storage errors | Storage appliance error messages |
| Provisioning failures | Cluster Manager and NFC state, provider registration |

## Guardrails

- Never restart, reimage, or replace a machine without explicit confirmation.
- Never treat missing Resource Health data as a healthy fabric or SAN.
- Do not recommend redeployment or rack removal as an early step.
- Report partial evidence as partial; do not present absence of data as a clean result.
- Follow [safety-rules](../../references/safety-rules.md).

## Evidence to collect

- Cluster, Cluster Manager, NFC IDs and provisioning state.
- Affected rack, machine, and VM identifiers.
- Fabric and isolation domain state.
- Storage appliance status and error messages.
- Metrics and logs covering the incident window.
- Recent changes: updates, fabric edits, workload deployments.

## Related references

- [Docs map](../../references/docs-map.md)
- [CLI and prerequisites](../../references/cli-and-prereqs.md)
- [Resource types](../../references/resource-types.md)
- [Safety rules](../../references/safety-rules.md)
