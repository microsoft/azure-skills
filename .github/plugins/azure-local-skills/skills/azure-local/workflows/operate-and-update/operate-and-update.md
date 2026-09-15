# Operate and Update Azure Local

Use this workflow for Azure Local inventory, health, monitoring, lifecycle management, updates, and update troubleshooting.

## Intake

Identify:

- Azure Local version/release and support window.
- Subscription, resource group, Azure Local instance, and custom location.
- Connectivity model, including limited connectivity or disconnected operation.
- Monitoring configuration, Log Analytics workspace, Azure Monitor/Insights status, Defender/Policy onboarding, and alerting requirements.
- Update target: assessment only, import/discover, schedule, install, troubleshoot, or post-update validation.

## Operation flow

1. **Start read-only** - Inventory Azure Local, Arc, resource bridge, custom location, and workload resources with [resource-types](../../references/resource-types.md).
2. **Check health** - Review Azure resource status, Arc machine connectivity, Azure Local instance status, extension status, and recent activity logs.
3. **Check monitoring** - Verify Azure Monitor/Log Analytics or Insights configuration before querying logs.
4. **Assess lifecycle** - Compare current release to the Azure Local release information and support window. Fetch current release notes through [docs-map](../../references/docs-map.md).
5. **Plan updates** - Use the Azure Local update docs for prerequisites, phases, supported interfaces, expected reboots, maintenance windows, and workload impact.
6. **Apply updates only after confirmation** - Installing updates may reboot hosts or affect workloads. Ask for explicit confirmation before scheduling or installing.
7. **Validate after changes** - Confirm update state, cluster health, Arc connectivity, resource bridge health, workload health, and monitoring alerts.

## Supported update guidance

Azure Local updates are orchestrated as a solution update for the OS, agents/services, and solution extension content. Use documented Azure Local update paths:

| Need | Use |
| --- | --- |
| Learn update model and cadence | Azure Local update overview |
| Understand phases | Update phases docs |
| Command-line update | Azure Local PowerShell update docs |
| Portal update | Azure Update Manager for Azure Local docs |
| Limited connectivity | Import/discover updates offline docs |
| Failure investigation | Update troubleshooting docs |

## Avoid unsupported update paths

Do not recommend out-of-band updates for Azure Local components. Avoid unsupported interfaces such as manual Cluster-Aware Updating, Windows Admin Center update flows, SConfig, or update panes for individual Arc machines unless Microsoft Learn explicitly documents the scenario for the user's version.

## Monitoring and inventory patterns

Use Azure control-plane discovery first:

```kql
Resources
| where type =~ 'microsoft.azurestackhci/clusters'
| project name, resourceGroup, location, properties
```

Then expand to associated Arc resource bridge, custom locations, Arc machines, workload resources, extensions, and activity logs. See [resource-types](../../references/resource-types.md).

## Handoff

- For workload creation or VM/AKS operations, use [Workload Management](../workload-management/workload-management.md).
- For SDN, NSG, private endpoint, or security posture changes, use [Networking and Security](../networking-and-security/networking-and-security.md).
- For failures, use [Troubleshooting](../troubleshooting/troubleshooting.md).

## Related references

- [Azure Local docs map](../../references/docs-map.md)
- [MCP and CLI tools](../../references/mcp-and-cli-tools.md)
- [Resource types and ARG patterns](../../references/resource-types.md)
- [Safety rules](../../references/safety-rules.md)
