# Azure Local Safety Rules

Azure Local changes can affect physical hosts, storage networks, Azure Arc connectivity, and local workloads. Default to assessment and reversible actions.

## Always ask before

- Installing, scheduling, importing, or retrying updates that can reboot hosts or affect workloads.
- Upgrading Azure Local or changing feature releases.
- Deleting, recreating, or repairing Azure Arc resource bridge.
- Deleting custom locations.
- Decommissioning, reimaging, or unregistering Azure Local machines.
- Changing physical network settings, VLANs, IP pools, DNS, gateways, proxy, Arc gateway, private endpoints, SDN infrastructure, NSGs, load balancers, gateways, or firewall policy.
- Creating, deleting, resizing, stopping, restarting, or migrating Azure Local VMs.
- Deleting disks, NICs, VM images, logical networks, storage paths, AKS clusters, SQL deployments, or backup/disaster-recovery resources.
- Disabling security baseline controls, Defender, Policy, monitoring, or auditing.

## Critical components

| Component | Rule |
| --- | --- |
| Azure Arc resource bridge | Do not delete unless following confirmed reimage/decommission guidance after dependent workload resources are removed. |
| Custom location | Do not delete until dependent workloads are removed and resource bridge decommission guidance allows it. |
| Infrastructure logical network | Treat as required infrastructure for Azure Local VM management. |
| VM management extension | Check health before VM remediation; do not remove as a generic fix. |
| SDN infrastructure | Treat certificate, controller, load balancer, and gateway changes as high risk. |

## Safe default sequence

1. Read-only inventory.
2. Health and activity log review.
3. Documentation lookup for the user's version.
4. Impact analysis and rollback plan.
5. User confirmation.
6. Scoped change.
7. Post-change validation.

## Response requirements

When recommending a risky change, include:

- The specific resource(s) affected.
- Why the change is needed.
- Expected workload/control-plane impact.
- Validation steps.
- Rollback or recovery notes when available.
