# Multi-Rack Safety Rules

Multi-rack instances host large-scale production workloads across shared racks, a shared SAN, and a managed network fabric. A single change can affect hundreds of machines.

## Always read-only first

Start every investigation with `show`/`list` commands and ARG queries. Establish the current state before proposing any change.

## Confirm before acting

Ask for explicit user confirmation before anything in this table.

| Action | Why it is risky |
| --- | --- |
| Network fabric changes | Fabric config is instance-wide; errors can isolate racks or break east-west traffic. |
| Isolation domain create/update/delete | Alters L2/L3 segmentation for running workloads. |
| Route policy changes | Can withdraw or import routes affecting north-south connectivity. |
| Bare metal machine power, restart, reimage, replace | Removes capacity and can move or destroy workloads. |
| Rack-level operations | Affects every machine in the rack. |
| Storage appliance / SAN operations | Shared by all compute racks; risk of data loss. |
| Cluster Manager or NFC changes | Control plane for the whole instance and, for NFC, potentially multiple instances. |
| VM power, delete, or disk operations | Direct workload impact. |
| Custom location or extension changes | Breaks the workload control path. |

## Preview caveat

Multi-rack is in preview. Do not assert that an operation is supported, reversible, or GA-backed without confirming in current documentation. Tell the user when guidance depends on preview behavior.

## Scale-confirmation rule

Before giving any procedure, confirm the deployment is multi-rack. Applying standard Azure Local procedures to a multi-rack instance — or the reverse — produces commands that fail or, worse, act on the wrong control plane.

## Evidence before diagnosis

Collect subscription, resource group, region, cluster name, Cluster Manager, NFC, rack identifiers, and affected machine or VM IDs before drawing conclusions. Never infer fabric or SAN health from Azure Resource Health alone.

## Boundaries

- Do not generate destructive commands as "examples"; the user may run them.
- Do not work around a missing permission by proposing a broader role assignment without flagging it.
- Do not recommend decommissioning, rack removal, or redeployment as a first troubleshooting step.
