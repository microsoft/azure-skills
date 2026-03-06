# Durable Task Scheduler

Build reliable, fault-tolerant workflows using durable execution with Azure Durable Task Scheduler.

## When to Use

- Long-running workflows requiring state persistence
- Distributed transactions with compensating actions (saga pattern)
- Multi-step orchestrations with checkpointing
- Fan-out/fan-in parallel processing
- Workflows requiring human interaction or external events
- Stateful entities (aggregators, counters, state machines)
- Multi-agent AI orchestration
- Data processing pipelines

## Framework Selection

| Framework | Best For | Hosting |
|-----------|----------|---------|
| **Durable Functions** | Serverless event-driven apps | Azure Functions |
| **Durable Task SDKs** | Any compute (containers, VMs) | Azure Container Apps, Azure Kubernetes Service, App Service, VMs |

> **💡 TIP**: Use Durable Functions for serverless with built-in triggers. Use Durable Task SDKs for hosting flexibility.

## Quick Start - Local Emulator

```bash
# Start the emulator (see https://mcr.microsoft.com/v2/dts/dts-emulator/tags/list for available versions)
docker pull mcr.microsoft.com/dts/dts-emulator:latest
docker run -d -p 8080:8080 -p 8082:8082 --name dts-emulator mcr.microsoft.com/dts/dts-emulator:latest

# Dashboard available at http://localhost:8082
```

## Workflow Patterns

| Pattern | Use When |
|---------|----------|
| **Function Chaining** | Sequential steps, each depends on previous |
| **Fan-Out/Fan-In** | Parallel processing with aggregated results |
| **Async HTTP APIs** | Long-running operations with HTTP polling |
| **Monitor** | Periodic polling with configurable timeouts |
| **Human Interaction** | Workflow pauses for external input/approval |
| **Saga** | Distributed transactions with compensation |
| **Durable Entities** | Stateful objects (counters, accounts) |

## Connection & Authentication

| Environment | Connection String |
|-------------|-------------------|
| Local Development (Emulator) | `Endpoint=http://localhost:8080;Authentication=None;TaskHub=default` |
| Azure (System-Assigned MI) | `Endpoint=https://<scheduler>.durabletask.io;Authentication=ManagedIdentity;TaskHub=default` |
| Azure (User-Assigned MI) | `Endpoint=https://<scheduler>.durabletask.io;Authentication=ManagedIdentity;ClientID=<uami-client-id>;TaskHub=default` |

> **⚠️ NOTE**: Durable Task Scheduler uses identity-based authentication only — no connection strings with keys. When using a User-Assigned Managed Identity (UAMI), you must include the `ClientID` in the connection string.

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| **403 PermissionDenied** on gRPC call (e.g., `client.start_new()`) | Function App managed identity lacks RBAC on the Durable Task Scheduler resource, or IP allowlist blocks traffic | 1. Assign `Durable Task Data Contributor` role (`0ad04412-c4d5-4796-b79c-f76d14c8d402`) to the identity (SAMI or UAMI) scoped to the Durable Task Scheduler resource. For UAMI, also ensure the connection string includes `ClientID=<uami-client-id>`. 2. Ensure the scheduler's `ipAllowlist` includes `0.0.0.0/0` (an empty list denies all traffic). 3. RBAC propagation can take up to 10 minutes — restart the Function App after assigning roles. |
| **Connection refused** to emulator | Emulator container not running or wrong port | Verify container is running: `docker ps` and confirm port 8080 is mapped |
| **403 despite correct RBAC** | Scheduler IP allowlist is empty (denies all) | Set `ipAllowlist: ['0.0.0.0/0']` in Bicep or update via CLI: `az durabletask scheduler update --ip-allowlist '0.0.0.0/0'` |
| **TaskHub not found** | Task hub not provisioned or name mismatch | Ensure the `TaskHub` parameter in the `DURABLE_TASK_SCHEDULER_CONNECTION_STRING` matches the provisioned task hub name |
| **403 Forbidden** on DTS dashboard | Deploying user lacks RBAC on the scheduler | Assign `Durable Task Data Contributor` role to your own user identity (not just the Function App MI) scoped to the scheduler resource — see [Bicep Patterns](bicep.md) for the dashboard role assignment snippet |

## References

- [.NET](dotnet.md) — packages, setup, examples, determinism, retry, SDK
- [Python](python.md) — packages, setup, examples, determinism, retry, SDK
- [Java](java.md) — dependencies, setup, examples, determinism, retry, SDK
- [JavaScript](javascript.md) — packages, setup, examples, determinism, retry, SDK
- [Bicep Patterns](bicep.md) — scheduler, task hub, RBAC, CLI provisioning
- [Official Documentation](https://learn.microsoft.com/azure/azure-functions/durable/durable-task-scheduler/durable-task-scheduler)
- [Durable Functions Overview](https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-overview)
- [Sample Repository](https://github.com/Azure-Samples/Durable-Task-Scheduler)
- [Choosing an Orchestration Framework](https://learn.microsoft.com/azure/azure-functions/durable/durable-task-scheduler/choose-orchestration-framework)
