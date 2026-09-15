# Azure Local Resource Types and ARG Patterns

Use Azure Resource Graph for cross-resource inventory. Resource providers and API coverage can evolve; verify against live resources and current Microsoft Learn docs.

## Common resource types

| Area | Resource type pattern |
| --- | --- |
| Azure Local instance / cluster | `microsoft.azurestackhci/clusters` |
| Arc machines | `microsoft.hybridcompute/machines` |
| Arc resource bridge | `microsoft.resourceconnector/appliances` |
| Custom locations | `microsoft.extendedlocation/customlocations` |
| Kubernetes/Arc extensions | `microsoft.kubernetesconfiguration/extensions` |
| AKS Arc / connected Kubernetes | `microsoft.kubernetes/connectedclusters` |
| Azure Local Arc VMs | `microsoft.azurestackhci/virtualmachineinstances`, `microsoft.hybridcompute/machines` |
| Azure Local logical networks | `microsoft.azurestackhci/logicalnetworks` |
| Azure Local network interfaces | `microsoft.azurestackhci/networkinterfaces` |
| Azure Local virtual hard disks | `microsoft.azurestackhci/virtualharddisks` |
| Azure Local gallery/images | `microsoft.azurestackhci/galleryimages`, `microsoft.azurestackhci/marketplacegalleryimages` |
| Azure Local storage paths | `microsoft.azurestackhci/storagecontainers` |
| Network security groups | `microsoft.azurestackhci/networksecuritygroups`, `microsoft.network/networksecuritygroups` |

## Inventory queries

List Azure Local instances:

```kql
Resources
| where type =~ 'microsoft.azurestackhci/clusters'
| project name, resourceGroup, location, id, properties
```

List Arc resource bridges and custom locations:

```kql
Resources
| where type in~ ('microsoft.resourceconnector/appliances', 'microsoft.extendedlocation/customlocations')
| project name, type, resourceGroup, location, id, properties
```

List Azure Local workload resources:

```kql
Resources
| where type startswith 'microsoft.azurestackhci/'
| project name, type, resourceGroup, location, id, properties
```

Find Arc machines associated with Azure Local:

```kql
Resources
| where type =~ 'microsoft.hybridcompute/machines'
| project name, resourceGroup, location, id, properties
```

## Query rules

- Use `=~`, `in~`, or lower-case type comparisons because resource types are case-insensitive but commonly stored lower-case.
- Project only needed fields for large tenants.
- Use `--subscriptions` or resource group filters when possible.
- Do not mutate through ARG; it is read-only.
- Validate resource-type names against live inventory because Azure Local resource providers evolve.
