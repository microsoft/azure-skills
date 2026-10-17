---
name: azure-mysql
description: "Manage and troubleshoot Azure Database for MySQL Flexible Server with public Azure MCP tools and Azure CLI. Covers service planning, secure application connections, Microsoft Entra authentication, configuration, SQL inspection, performance, high availability, backups, replicas, and migrations. USE FOR: Azure MySQL, MySQL Flexible Server, MySQL managed identity, passwordless MySQL, MySQL TLS or private networking, MySQL access denied, MySQL connection failures, MySQL high CPU, slow queries, MySQL server parameters, MySQL backup or restore, MySQL replication lag, MySQL version upgrades. DO NOT USE FOR: PostgreSQL, Azure SQL Database, SQL Server, Cosmos DB, self-managed MySQL on VMs or Kubernetes, or generic MySQL questions without Azure context."
license: MIT
metadata:
  author: Microsoft
  version: "1.0.0"
---

# Azure Database for MySQL

Guide developers and operators using **MySQL Flexible Server**. Reuse the plugin's existing Azure MCP server; no additional MCP server is required.

## Route the Request

Classify the task, then load only the matching reference.

| Intent | Reference | Outcome |
| --- | --- | --- |
| List servers/databases/tables, inspect schema, query data, read or change parameters | [Tools and safe execution](references/tools.md) | Scoped MCP operation or documented CLI fallback |
| Choose a tier, provision infrastructure, add MySQL to an app | [Deployment and application stack](references/deployment.md) | Service decisions and validated infrastructure plan |
| Connect an app, configure passwordless auth, investigate TLS/DNS/network access | [Connectivity and authentication](references/connectivity.md) | Verified identity, private connectivity, and encrypted connection |
| Connection errors, high CPU, slow queries, storage pressure, replication lag | [Troubleshooting](references/troubleshooting.md) | Evidence-backed diagnosis and bounded remediation |
| HA, read replicas, backups, restore, migration, or engine upgrade | [Reliability and lifecycle](references/reliability.md) | Recovery or change plan with verification and rollback |

## Workflow

1. **Establish scope.** Identify the task and production impact. Before live operations, confirm the tenant/cloud, subscription, resource group, server, and database where relevant. Do not enumerate unrelated subscriptions. For evidence-only requests, use supplied logs and configuration without live access.
2. **Inspect before changing.** Discover the installed tool version and schemas. Read server version, configuration, and relevant parameter values; distinguish Azure management permissions from SQL privileges and network reachability. Before any data-plane operation, apply the [data-plane preflight](references/tools.md#data-plane-preflight), including TLS verification and identity mapping.
3. **Choose the smallest action.** Prefer Azure MCP for management-plane operations and documented CLI management commands when unavailable. Use MCP data-plane commands only after the preflight passes; otherwise use an authorized verified native client. Never bypass an authorization refusal.
4. **Explain and approve changes.** Present the exact target, before/after state, downtime, cost/security effects, verification, and rollback. Obtain explicit approval before writes, permission/network changes, restart, scaling, failover, restore, replica promotion, or migration cutover.
5. **Verify the result.** Re-read changed state and check the original symptom from the application network and identity. Report evidence, remaining uncertainty, and any follow-up that still needs approval.

## Guardrails

- Default database inspection to a single, bounded, non-locking read-only `SELECT`. A query tool or a `SELECT` prefix is not a guarantee of safety. Never run user-supplied SQL without inspecting its effects.
- Prefer Microsoft Entra authentication and application managed identity when supported. Azure RBAC does not grant database privileges. Never request, display, persist, or place passwords/access tokens in command arguments.
- Require verified TLS with hostname validation, including connections made by tools. Encryption alone is insufficient: the MySQL data-plane implementation in `@azure/mcp` 3.0.0 does not validate certificates or hostnames and must not be used. Do not disable `require_secure_transport` or certificate checks to fix connectivity.
- Treat VNet integration and Private Link as different networking models. Never open all IPs or enable broad Azure-service access as a default fix.
- Check current engine support, regional SKUs, quota, and feature availability; do not default to an unsupported or preview engine version.
- Do not assume `SUPER`, host filesystem access, arbitrary plugins, or self-managed MySQL configuration techniques exist on the managed service.

## Coordinate with Other Skills

- **`azure-prepare`** owns application preparation when the project uses azd (`azure.yaml`) or the user explicitly chooses azd. Supply MySQL decisions, then retain `azure-prepare` -> `azure-validate` -> `azure-deploy`. If called from preparation, return findings instead of recursively starting preparation. Respect explicitly requested non-azd infrastructure workflows.
- **`azure-diagnostics`** supplies cross-service health and incident correlation; keep MySQL-specific diagnosis in this skill.
- **`azure-quotas`**, **`azure-rbac`**, and **`azure-kusto`** help with capacity, management-plane roles, and discovered log schemas when those skills are available. Their absence does not block the documented MySQL/CLI workflow.

Use the current [Azure MySQL architecture guidance](https://learn.microsoft.com/azure/well-architected/service-guides/azure-database-for-mysql) to ground recommendations; the references link to operation-specific sources.
