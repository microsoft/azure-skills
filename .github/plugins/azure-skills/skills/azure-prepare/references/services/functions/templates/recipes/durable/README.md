# Durable Functions Recipe

Orchestration workflows with Durable Task Scheduler as the backend.

## Template Selection

Resource filter: `durable`  
Discover templates via MCP or CDN manifest where `resource == "durable"` and `language` matches user request.

## Key Concept

Uses **Durable Task Scheduler** (DTS) — a fully managed backend for state persistence. Do NOT use Azure Storage queues/tables.

See [Durable Task Scheduler reference](../../../../durable-task-scheduler/README.md) for backend configuration details.

## Troubleshooting

### Orchestration Fails to Start

**Cause:** Durable Task Scheduler (DTS) backend not provisioned or connection misconfigured.  
**Solution:** Verify the DTS resource exists and the function app has the `Durable Task Scheduler Worker` role. Do NOT use Azure Storage queues/tables as backend.

### UAMI Connection Issues

**Cause:** Missing or incorrect Durable Task Scheduler connection string.  
**Solution:** DTS uses a connection string format (not the `__` suffix pattern). Set these app settings:

- `DURABLE_TASK_SCHEDULER_CONNECTION_STRING`: `Endpoint=<scheduler-endpoint>;Authentication=ManagedIdentity;ClientID=<client-id>`
- `TASKHUB_NAME`: name of the task hub

For system-assigned identity, omit `ClientID`:
`Endpoint=<scheduler-endpoint>;Authentication=ManagedIdentity`

The identity must have the **Durable Task Data Contributor** role on the scheduler or task hub resource. See [DTS identity auth](https://learn.microsoft.com/en-us/azure/durable-task/scheduler/durable-task-scheduler-identity) for identity-based config — refer to the **"Configure managed identity"** section for connection string and role assignment details.

## Eval

| Path | Description |
|------|-------------|
| [eval/summary.md](eval/summary.md) | Evaluation summary |
| [eval/python.md](eval/python.md) | Python evaluation results |
