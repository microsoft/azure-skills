# Durable Functions Recipe

Adds Durable Functions orchestration patterns to an Azure Functions base template with **Durable Task Scheduler** as the backend.

## Overview

This recipe composes with any HTTP base template to create a Durable Functions app with:
- **Orchestrator** - Coordinates workflow execution
- **Activity** - Individual task units
- **HTTP Client** - Starts and queries orchestrations
- **Durable Task Scheduler** - Fully managed backend for state persistence, orchestration history, and task hub management

> **⚠️ IMPORTANT**: This recipe uses **Durable Task Scheduler** (DTS) as the storage backend — NOT Azure Storage queues/tables. DTS is the recommended, fully managed option with the best performance and developer experience. See [Durable Task Scheduler reference](../../../../durable-task-scheduler/README.md) for details.

## Integration Type

| Aspect | Value |
|--------|-------|
| **Trigger** | `OrchestrationTrigger` + `ActivityTrigger` |
| **Client** | `DurableClient` / `DurableOrchestrationClient` |
| **Auth** | UAMI (Managed Identity) → Durable Task Scheduler |
| **IaC** | Bicep module: scheduler + task hub + RBAC |

## Composition Steps

Apply these steps AFTER `azd init -t functions-quickstart-{lang}-azd`:

| # | Step | Details |
|---|------|---------|
| 1 | **Add IaC module** | Copy `bicep/durable-task-scheduler.bicep` → `infra/app/durable-task-scheduler.bicep` |
| 2 | **Wire into main** | Add module reference in `infra/main.bicep` |
| 3 | **Add app settings** | Add `DURABLE_TASK_SCHEDULER_CONNECTION_STRING` to function app configuration |
| 4 | **Add extension packages** | Add Durable Functions + DTS extension packages for the runtime |
| 5 | **Replace source code** | Add Orchestrator + Activity + Client from `source/{lang}.md` |
| 6 | **Configure host.json** | Set DTS storage provider (see [DTS language references](../../../../durable-task-scheduler/README.md)) |

## IaC Module

### Bicep

Copy `bicep/durable-task-scheduler.bicep` → `infra/app/durable-task-scheduler.bicep` and add to `main.bicep`:

```bicep
module durableTaskScheduler './app/durable-task-scheduler.bicep' = {
  name: 'durableTaskScheduler'
  scope: rg
  params: {
    name: name
    location: location
    tags: tags
    functionAppPrincipalId: app.outputs.SERVICE_API_IDENTITY_PRINCIPAL_ID
    principalId: principalId  // For dashboard access
    uamiClientId: apiUserAssignedIdentity.outputs.clientId  // REQUIRED for UAMI auth
  }
}
```

### App Settings

Add the DTS connection string to the function app's `appSettings`:

```bicep
appSettings: {
  DURABLE_TASK_SCHEDULER_CONNECTION_STRING: durableTaskScheduler.outputs.connectionString
}
```

> **💡 TIP**: The module output already includes `ClientID=<uami-client-id>` when you pass `uamiClientId` — no manual connection string construction needed.

> **⚠️ NOTE**: Do NOT set `enableQueue: true` or `enableTable: true` in the storage module — DTS replaces Azure Storage queues/tables for orchestration state.

## RBAC Roles Required

| Role | GUID | Scope | Purpose |
|------|------|-------|---------|
| **Durable Task Data Contributor** | `0ad04412-c4d5-4796-b79c-f76d14c8d402` | Durable Task Scheduler | Read/write orchestrations and entities |

## host.json Configuration

The `host.json` must configure DTS as the storage provider. The `type` value differs by language:

| Language | `storageProvider.type` | Reference |
|----------|----------------------|-----------|
| C# (.NET) | `azureManaged` | [dotnet.md](../../../../durable-task-scheduler/dotnet.md) |
| Python | `durabletask-scheduler` | [python.md](../../../../durable-task-scheduler/python.md) |
| JavaScript/TypeScript | `durabletask-scheduler` | [javascript.md](../../../../durable-task-scheduler/javascript.md) |
| Java | `durabletask-scheduler` | [java.md](../../../../durable-task-scheduler/java.md) |

**Example (Python / JavaScript / Java):**
```json
{
  "version": "2.0",
  "extensions": {
    "durableTask": {
      "hubName": "default",
      "storageProvider": {
        "type": "durabletask-scheduler",
        "connectionStringName": "DURABLE_TASK_SCHEDULER_CONNECTION_STRING"
      }
    }
  }
}
```

**Example (.NET isolated):**
```json
{
  "version": "2.0",
  "extensions": {
    "durableTask": {
      "hubName": "default",
      "storageProvider": {
        "type": "azureManaged",
        "connectionStringName": "DURABLE_TASK_SCHEDULER_CONNECTION_STRING"
      }
    }
  }
}
```

## Extension Packages

| Language | Durable Functions Package | DTS Extension Package |
|----------|--------------------------|----------------------|
| Python | `azure-functions-durable` | _(uses extension bundles)_ |
| TypeScript/JavaScript | `durable-functions` | _(uses extension bundles)_ |
| C# (.NET) | `Microsoft.Azure.Functions.Worker.Extensions.DurableTask` | `Microsoft.Azure.Functions.Worker.Extensions.DurableTask.AzureManaged` |
| Java | `com.microsoft:durabletask-azure-functions` | _(uses extension bundles)_ |
| PowerShell | Built-in (v2 bundles) | _(uses extension bundles)_ |

## Files

| Path | Description |
|------|-------------|
| [bicep/durable-task-scheduler.bicep](bicep/durable-task-scheduler.bicep) | DTS Bicep module (scheduler + task hub + RBAC) |
| [source/python.md](source/python.md) | Python Durable Functions source code |
| [source/typescript.md](source/typescript.md) | TypeScript Durable Functions source code |
| [source/javascript.md](source/javascript.md) | JavaScript Durable Functions source code |
| [source/dotnet.md](source/dotnet.md) | C# (.NET) Durable Functions source code |
| [source/java.md](source/java.md) | Java Durable Functions source code |
| [source/powershell.md](source/powershell.md) | PowerShell Durable Functions source code |
| [eval/summary.md](eval/summary.md) | Evaluation summary |
| [eval/python.md](eval/python.md) | Python evaluation results |

## Patterns Included

### Fan-out/Fan-in (Default)

```
HTTP Start → Orchestrator → [Activity1, Activity2, Activity3] → Aggregate → Return
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/orchestrators/{name}` | POST | Start new orchestration |
| `/api/status/{instanceId}` | GET | Check orchestration status |
| `/api/health` | GET | Health check |

## Common Issues

### 403 PermissionDenied on gRPC call

**Symptoms:** 403 on `client.start_new()` or orchestration calls.

**Cause:** Function App managed identity lacks RBAC on the DTS scheduler, or IP allowlist blocks traffic.

**Solution:**
1. Assign `Durable Task Data Contributor` role (`0ad04412-c4d5-4796-b79c-f76d14c8d402`) to the UAMI scoped to the scheduler.
2. Ensure the connection string includes `ClientID=<uami-client-id>`.
3. Ensure the scheduler's `ipAllowlist` includes `0.0.0.0/0` (empty list denies all traffic).
4. RBAC propagation can take up to 10 minutes — restart the Function App after assigning roles.

### TaskHub not found

**Cause:** Task hub not provisioned or name mismatch.

**Solution:** Ensure the `TaskHub` parameter in `DURABLE_TASK_SCHEDULER_CONNECTION_STRING` matches the provisioned task hub name (default: `default`).

### Orchestrator Replay Issues

**Cause:** Non-deterministic code in orchestrator (e.g., `DateTime.Now`, random values).

**Solution:** Use `context.current_utc_datetime` or `context.CurrentUtcDateTime` instead.
```
