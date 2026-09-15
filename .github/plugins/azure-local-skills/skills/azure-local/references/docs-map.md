# Azure Local Documentation Map

Use Microsoft Learn as the authoritative source for Azure Local procedures. Use latest-version URLs by default; add a version-aware view parameter only when the user asks about a specific Azure Local release, and fetch current docs before giving detailed commands.

## Core entry points

| Area | Microsoft Learn path |
| --- | --- |
| Azure Local landing page | `https://learn.microsoft.com/azure/azure-local/` |
| What is Azure Local | `https://learn.microsoft.com/azure/azure-local/overview` |
| Scalability and deployments (choose a scale) | `https://learn.microsoft.com/azure/azure-local/scalability-deployments` |
| Release information | `https://learn.microsoft.com/azure/azure-local/release-information-23h2` |
| Known issues | `https://learn.microsoft.com/azure/azure-local/known-issues` |

## Planning and deployment

| Need | Microsoft Learn path |
| --- | --- |
| System requirements | `https://learn.microsoft.com/azure/azure-local/concepts/system-requirements-23h2` |
| Physical network requirements | `https://learn.microsoft.com/azure/azure-local/concepts/physical-network-requirements` |
| Host network requirements | `https://learn.microsoft.com/azure/azure-local/concepts/host-network-requirements` |
| Firewall requirements | `https://learn.microsoft.com/azure/azure-local/concepts/firewall-requirements` |
| Network reference patterns | `https://learn.microsoft.com/azure/azure-local/plan/network-patterns-overview` |
| Choose network pattern | `https://learn.microsoft.com/azure/azure-local/plan/choose-network-pattern` |
| Deployment introduction | `https://learn.microsoft.com/azure/azure-local/deploy/deployment-introduction` |
| Deployment prerequisites | `https://learn.microsoft.com/azure/azure-local/deploy/deployment-prerequisites` |
| Prepare Active Directory | `https://learn.microsoft.com/azure/azure-local/deploy/deployment-prep-active-directory` |
| Install OS | `https://learn.microsoft.com/azure/azure-local/deploy/deployment-install-os` |
| Simplified machine provisioning | `https://learn.microsoft.com/azure/azure-local/deploy/simplified-machine-provisioning` |
| Subscription permissions | `https://learn.microsoft.com/azure/azure-local/deploy/deployment-arc-register-server-permissions` |
| Register without Arc gateway | `https://learn.microsoft.com/azure/azure-local/deploy/deployment-without-azure-arc-gateway` |
| Register with Arc gateway | `https://learn.microsoft.com/azure/azure-local/deploy/deployment-with-azure-arc-gateway` |
| Deploy via portal | `https://learn.microsoft.com/azure/azure-local/deploy/deploy-via-portal` |
| Deploy via ARM template | `https://learn.microsoft.com/azure/azure-local/deploy/deployment-azure-resource-manager-template` |

## Rack-aware clusters

Rack-aware clustering spreads a single cluster across two racks as availability zones with synchronous replication. It is a standard-scale topology, not multi-rack. For multi-rack (rack scale), use the `azure-local-multi-rack` skill.

| Need | Microsoft Learn path |
| --- | --- |
| Rack aware cluster overview | `https://learn.microsoft.com/azure/azure-local/concepts/rack-aware-cluster-overview` |
| Requirements and supported configurations | `https://learn.microsoft.com/azure/azure-local/concepts/rack-aware-cluster-requirements` |
| Network reference patterns | `https://learn.microsoft.com/azure/azure-local/concepts/rack-aware-cluster-reference-architecture` |
| Prepare deployment | `https://learn.microsoft.com/azure/azure-local/deploy/rack-aware-cluster-deploy-prep` |
| Deploy via portal | `https://learn.microsoft.com/azure/azure-local/deploy/rack-aware-cluster-deploy-portal` |
| Deploy via ARM template | `https://learn.microsoft.com/azure/azure-local/deploy/rack-aware-cluster-deployment-via-template` |

## Operations, updates, and upgrades

| Need | Microsoft Learn path |
| --- | --- |
| About updates | `https://learn.microsoft.com/azure/azure-local/update/about-updates-23h2` |
| Update phases | `https://learn.microsoft.com/azure/azure-local/update/update-phases-23h2` |
| Update via PowerShell | `https://learn.microsoft.com/azure/azure-local/update/update-via-powershell-23h2` |
| Limited connectivity updates | `https://learn.microsoft.com/azure/azure-local/update/import-discover-updates-offline-23h2` |
| Update via Azure portal | `https://learn.microsoft.com/azure/azure-local/update/azure-update-manager-23h2` |
| Update best practices | `https://learn.microsoft.com/azure/azure-local/update/update-best-practices` |
| Troubleshoot updates | `https://learn.microsoft.com/azure/azure-local/update/update-troubleshooting-23h2` |
| About upgrades | `https://learn.microsoft.com/azure/azure-local/upgrade/about-upgrades-23h2` |
| Upgrade troubleshooting | `https://learn.microsoft.com/azure/azure-local/upgrade/troubleshoot-upgrade-to-23h2` |

## Workloads

| Need | Microsoft Learn path |
| --- | --- |
| Azure Local VM management overview | `https://learn.microsoft.com/azure/azure-local/manage/azure-arc-vm-management-overview` |
| VM management prerequisites | `https://learn.microsoft.com/azure/azure-local/manage/azure-arc-vm-management-prerequisites` |
| Assign VM RBAC roles | `https://learn.microsoft.com/azure/azure-local/manage/assign-vm-rbac-roles` |
| Create storage path | `https://learn.microsoft.com/azure/azure-local/manage/create-storage-path` |
| Create logical networks | `https://learn.microsoft.com/azure/azure-local/manage/create-logical-networks` |
| Create network interfaces | `https://learn.microsoft.com/azure/azure-local/manage/create-network-interfaces` |
| Create Arc VMs | `https://learn.microsoft.com/azure/azure-local/manage/create-arc-virtual-machines` |
| Manage Arc VMs | `https://learn.microsoft.com/azure/azure-local/manage/manage-arc-virtual-machines` |
| Troubleshoot Arc VMs | `https://learn.microsoft.com/azure/azure-local/manage/troubleshoot-arc-enabled-vms` |
| AKS on Azure Local | `https://learn.microsoft.com/azure/aks/hybrid/aks-create-clusters-portal?toc=/azure/azure-local/toc.json&bc=/azure/azure-local/breadcrumb/toc.json` |
| SQL Server on Azure Local | `https://learn.microsoft.com/azure/azure-local/deploy/sql-server-23h2` |
| Disaster recovery overview | `https://learn.microsoft.com/azure/azure-local/manage/disaster-recovery-overview` |

## Networking and security

| Need | Microsoft Learn path |
| --- | --- |
| Security features | `https://learn.microsoft.com/azure/azure-local/concepts/security-features` |
| Security book | `https://learn.microsoft.com/azure/azure-local/security-book/overview` |
| Private endpoints | `https://learn.microsoft.com/azure/azure-local/deploy/about-private-endpoints` |
| SDN overview | `https://learn.microsoft.com/azure/azure-local/concepts/sdn-overview` |
| Enable SDN integration | `https://learn.microsoft.com/azure/azure-local/deploy/enable-sdn-integration` |
| Network security groups | `https://learn.microsoft.com/azure/azure-local/manage/create-network-security-groups` |
| Manage NSGs | `https://learn.microsoft.com/azure/azure-local/manage/manage-network-security-groups` |
| SDN troubleshooting | `https://learn.microsoft.com/azure/azure-local/manage/sdn-troubleshooting` |
| External storage | `https://learn.microsoft.com/azure/azure-local/deploy/enable-external-storage` |

## Documentation usage rules

1. Fetch current docs for detailed procedures, command syntax, or supported topology decisions.
2. If a URL redirects or 404s, search Microsoft Learn for the article title and keep the user's requested Azure Local version in the query.
3. Do not copy long procedural content into responses; summarize the decision and link or cite the authoritative doc.
4. When documentation differs by version, ask for the Azure Local version or use the version provided by the user.
