# Durable Functions

Long-running orchestrations with checkpointing and state management.

## Storage Backend

Durable Functions requires a storage backend to persist orchestration state, queues, and history.

| Backend | Recommendation | Notes |
|---------|---------------|-------|
| **Durable Task Scheduler** | **✅ Required** | Fully managed Azure service. Best performance, lowest latency, built-in monitoring. Supports all languages (.NET, Python, Java, JavaScript). |
| Azure Storage (default) | ⛔ Do not use | Legacy backend. Higher latency, harder to monitor, no built-in RBAC. Not permitted for new projects. |
| MSSQL | Specialized | SQL Server backend. Only when SQL infrastructure already exists and user explicitly requests it. |

> **⛔ MANDATORY**: You **MUST** use **Durable Task Scheduler** as the storage backend for ALL new Durable Functions projects. Do NOT use Azure Storage as the backend — it is legacy and not permitted. Generate the DTS Bicep module (`Microsoft.DurableTask/schedulers` + `taskHubs`), RBAC role assignment (Durable Task Data Contributor), and `DURABLE_TASK_SCHEDULER_CONNECTION_STRING` app setting. See the [Durable Task Scheduler reference](../durable-task-scheduler/README.md) for setup, language-specific guidance, and Bicep templates.

## When to Use

- Multi-step workflows
- Fan-out/fan-in patterns
- Human interaction workflows
- Long-running processes

## Get Durable Templates

Use the [Azure Functions Templates workflow](templates/README.md) to discover and fetch durable samples:

**MCP Tool:** `functions_template_get(language)` → filter `resource == "durable"`

**Fallback:** CDN manifest → filter `resource == "durable"`

Available patterns: Fan-out/Fan-in, Order Processing (with Bicep), Distributed Tracing, Large Payload, Saga, AI Travel Planner, PDF Summarizer, .NET Aspire integration.
