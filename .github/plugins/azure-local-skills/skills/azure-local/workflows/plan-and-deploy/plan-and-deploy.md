# Plan and Deploy Azure Local

Use this workflow when a user is planning, preparing, or deploying Azure Local. Keep the guidance version-aware and fetch current Microsoft Learn procedures through [docs-map](../../references/docs-map.md) before giving detailed step-by-step commands.

## Intake

Collect the minimum deployment context:

| Question | Why it matters |
| --- | --- |
| Deployment type and size | Azure Local supports single-node and multi-node hyperconverged deployments with topology-specific constraints. |
| Hardware/vendor/BOM status | Azure Local expects validated hardware and partner solution guidance. |
| Connectivity model | Direct Arc registration, Arc gateway, proxy, private endpoints, limited connectivity, and disconnected scenarios change prerequisites. |
| Network topology | The storage network pattern affects supported portal vs ARM deployment choices. |
| Identity model | Active Directory preparation and subscription permissions are prerequisites. |
| Deployment method | Portal, ARM template, and local identity with Key Vault have different inputs and validation points. |

## Sequence

1. **Confirm scope** - Determine whether the user is planning, preparing prerequisites, registering machines, deploying the instance, or validating a completed deployment.
2. **Load authoritative docs** - Use [docs-map](../../references/docs-map.md) to fetch the current Azure Local overview, prerequisites, deployment introduction, and topology guidance for the requested version.
3. **Check prerequisites** - Review hardware/BOM, OS, Active Directory, subscription permissions, Azure CLI/PowerShell requirements, firewall/proxy/private endpoint requirements, and Azure Arc requirements.
4. **Select topology** - Map the node count and storage connectivity to a validated network reference pattern before recommending IP/VLAN/switch settings.
5. **Prepare machines** - Follow docs for OS download/install or simplified machine provisioning. Do not invent installation steps.
6. **Register with Azure Arc** - Choose direct registration, Arc gateway, proxy, or private endpoint flow based on connectivity.
7. **Deploy the Azure Local instance** - Use portal for guided deployments when supported by the topology; use ARM templates for scenarios that require template support.
8. **Validate deployment** - Confirm Azure Local instance, Arc resource bridge, custom location, infrastructure logical network, and any expected extensions/resources exist.
9. **Document next operations** - Hand off to [Operate and Update](../operate-and-update/operate-and-update.md) for lifecycle and monitoring setup or [Workload Management](../workload-management/workload-management.md) for workload onboarding.

## Deployment method routing

| Scenario | Preferred path |
| --- | --- |
| User wants guided setup and topology is portal-supported | Azure portal deployment |
| User needs repeatable IaC or a topology not available in portal | ARM template deployment |
| Environment uses central Arc gateway | Arc gateway registration docs before deployment |
| Environment uses private endpoints | Private endpoint deployment docs before deployment |
| User is evaluating locally | Azure Local virtual/lab deployment guidance, with clear non-production caveat |

## Guardrails

- Do not proceed from planning to deployment commands without confirming the deployment method and target environment.
- Do not generate irreversible Active Directory, network, firewall, or private endpoint changes without user confirmation.
- Do not skip network topology validation; unsupported topology choices lead to deployment failures.
- Do not delete or recreate Arc resource bridge/custom locations during deployment troubleshooting unless the user confirms a decommission or reimage flow.
- Use [safety-rules](../../references/safety-rules.md) for all destructive or availability-impacting actions.

## Evidence to collect

- Azure subscription and tenant.
- Resource group and region.
- Azure Local instance name.
- Node count and hardware model.
- Network pattern and storage network configuration.
- Connectivity mode: direct, proxy, Arc gateway, private endpoint, limited, or disconnected.
- Deployment method and deployment status.

## Related references

- [Azure Local docs map](../../references/docs-map.md)
- [MCP and CLI tools](../../references/mcp-and-cli-tools.md)
- [Safety rules](../../references/safety-rules.md)
