# Multi-Rack Resource Types and ARG Patterns

Use Azure Resource Graph for read-only inventory. Multi-rack spans three providers; verify type names against live inventory because the offering is in preview.

## Common resource types

| Area | Resource type pattern |
| --- | --- |
| Cluster Manager | `microsoft.networkcloud/clustermanagers` |
| Multi-rack cluster | `microsoft.networkcloud/clusters` |
| Racks | `microsoft.networkcloud/racks` |
| Bare metal machines | `microsoft.networkcloud/baremetalmachines` |
| Storage appliances | `microsoft.networkcloud/storageappliances` |
| Network Fabric Controller | `microsoft.managednetworkfabric/networkfabriccontrollers` |
| Network fabric | `microsoft.managednetworkfabric/networkfabrics` |
| Network devices | `microsoft.managednetworkfabric/networkdevices` |
| L3 isolation domains | `microsoft.managednetworkfabric/l3isolationdomains` |
| L2 isolation domains | `microsoft.managednetworkfabric/l2isolationdomains` |
| Route policies | `microsoft.managednetworkfabric/routepolicies` |
| Access control lists | `microsoft.managednetworkfabric/accesscontrollists` |
| Network racks | `microsoft.managednetworkfabric/networkracks` |
| Arc VMs | `microsoft.azurestackhci/virtualmachineinstances` |
| Logical networks | `microsoft.azurestackhci/logicalnetworks` |
| Custom locations | `microsoft.extendedlocation/customlocations` |
| Arc machines | `microsoft.hybridcompute/machines` |

## Inventory queries

List multi-rack clusters and their managers:

```kql
Resources
| where type in~ ('microsoft.networkcloud/clusters', 'microsoft.networkcloud/clustermanagers')
| project name, type, resourceGroup, location, id, properties
```

List fabric resources:

```kql
Resources
| where type startswith 'microsoft.managednetworkfabric/'
| project name, type, resourceGroup, location, id, properties
```

List racks and bare metal machines:

```kql
Resources
| where type in~ ('microsoft.networkcloud/racks', 'microsoft.networkcloud/baremetalmachines')
| project name, type, resourceGroup, location, id, properties
```

## Distinguishing multi-rack from standard Azure Local

A tenant containing `microsoft.networkcloud/clusters` or `microsoft.managednetworkfabric/*` resources indicates multi-rack. A tenant with only `microsoft.azurestackhci/clusters` and no NetworkCloud resources indicates standard Azure Local — use the `azure-local` skill instead.

Note that `microsoft.azurestackhci/*` workload types appear in **both**, so they are not sufficient on their own to identify the deployment scale.

## Query rules

- Use `=~` or `in~`; resource types are case-insensitive.
- Project only needed fields.
- ARG is read-only; never attempt mutation through it.
- Validate type names against live inventory before relying on them in a procedure.
