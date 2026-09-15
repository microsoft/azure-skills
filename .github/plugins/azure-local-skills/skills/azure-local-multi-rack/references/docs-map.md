# Multi-Rack Documentation Map

Microsoft Learn is authoritative for multi-rack procedures. All paths below are relative to the base:

`https://learn.microsoft.com/azure/azure-local/multi-rack/`

Use latest-version URLs by default; add a version-aware view parameter only when the user asks about a specific release.

> Multi-rack is in preview. Confirm current capability and regional availability from `multi-rack-overview` before committing to a design.

## Core

| Need | Page |
| --- | --- |
| What multi-rack is, BOM, rack structure | `multi-rack-overview` |
| Latest capability changes | `multi-rack-whats-new` |
| Prerequisites: NFC, Cluster Manager, RP registration | `multi-rack-prerequisites` |
| Required Azure CLI extensions | `multi-rack-cli-extensions` |
| Compute concepts | `multi-rack-concepts-compute` |
| Security model | `multi-rack-security` |

## Networking

| Need | Page |
| --- | --- |
| Network fabric overview | `multi-rack-network-fabric-overview` |
| Layer 3 isolation domains | `multi-rack-configure-layer-3-isolation-domain` |
| Create logical networks | `multi-rack-create-logical-networks` |
| Manage logical networks | `multi-rack-manage-logical-networks` |
| Create network interfaces | `multi-rack-create-network-interfaces` |
| Create virtual networks | `multi-rack-create-virtual-networks` |
| Create network security groups | `multi-rack-create-network-security-groups` |
| Manage network security groups | `multi-rack-manage-network-security-groups` |
| Load balancer overview | `multi-rack-load-balancer-overview` |
| Load balancer logical network | `multi-rack-create-load-balancer-logical-network` |
| Internal load balancer | `multi-rack-create-internal-load-balancer-virtual-networks` |
| Public load balancer | `multi-rack-create-public-load-balancer-virtual-networks` |
| Public IP | `multi-rack-create-public-ip` |
| NAT gateway | `multi-rack-nat-gateway-overview` |

## Workloads

| Need | Page |
| --- | --- |
| Arc VM management overview | `multi-rack-azure-arc-vm-management-overview` |
| VM management prerequisites | `multi-rack-vm-management-prerequisites` |
| Create Arc VMs | `multi-rack-create-arc-virtual-machines` |
| Manage Arc VMs | `multi-rack-manage-arc-virtual-machines` |
| Manage VM resources | `multi-rack-manage-arc-virtual-machine-resources` |
| VM operations | `multi-rack-virtual-machine-operations` |
| Manage VM images | `multi-rack-virtual-machine-manage-image` |
| Image storage account | `multi-rack-virtual-machine-image-storage-account` |
| Manage VM extensions | `multi-rack-virtual-machine-manage-extension` |
| Manage data disks | `multi-rack-manage-data-disks` |
| Disk snapshots | `multi-rack-disk-snapshot` |
| Assign VM RBAC roles | `multi-rack-assign-vm-rbac-roles` |
| Connect to a VM over SSH | `multi-rack-connect-arc-vm-using-ssh` |
| GPU preparation | `multi-rack-gpu-preparation` |
| GPU device management | `multi-rack-gpu-manage-via-device` |

## Operations and troubleshooting

| Need | Page |
| --- | --- |
| Monitoring overview | `multi-rack-monitor-overview` |
| Cluster metrics | `multi-rack-monitor-cluster-with-metrics` |
| Serial console | `multi-rack-serial-console` |
| Troubleshoot Arc VMs | `multi-rack-troubleshoot-arc-enabled-vms` |
| Storage appliance error messages | `multi-rack-storage-appliance-error-messages` |

## Outside the multi-rack base path

| Need | Full path |
| --- | --- |
| AKS on multi-rack architecture | `https://learn.microsoft.com/azure/aks/aksarc/multi-rack/cluster-architecture` |
| Choosing a deployment scale | `https://learn.microsoft.com/azure/azure-local/scalability-deployments` |

## Usage rules

1. Never substitute a standard Azure Local article for a multi-rack one. The same task (logical networks, VM creation, NSGs) has separate, non-interchangeable procedures.
2. Fetch current docs before giving command syntax; preview content changes.
3. If a URL redirects or 404s, search Learn for the title scoped to multi-rack deployments of Azure Local.
4. Summarize and cite rather than copying long procedures.
