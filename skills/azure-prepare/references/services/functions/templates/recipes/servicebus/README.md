# Service Bus Recipe

Service Bus queue/topic trigger with managed identity authentication.

## Template Selection

Resource filter: `servicebus`  
Discover templates via MCP tool or CDN manifest where `resource == "servicebus"` and `language` matches user request.

## Troubleshooting

### 500 Error on First Request

**Cause:** RBAC role assignment hasn't propagated to Service Bus data plane.  
**Solution:** Wait 30-60 seconds after provisioning, or restart the function app.

### "Unauthorized" or "Forbidden" Errors

**Cause:** Missing UAMI credential settings.  
**Solution:** Ensure all three settings are present in app configuration:

- `ServiceBusConnection__fullyQualifiedNamespace`
- `ServiceBusConnection__credential` (value: `managedidentity`)
- `ServiceBusConnection__clientId`

See [Service Bus trigger connections](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-service-bus-trigger#connections) for identity-based config — refer to the **"Connections"** section on that page for managed identity app settings.

## Eval

| Path | Description |
|------|-------------|
| [eval/summary.md](eval/summary.md) | Evaluation summary |
| [eval/python.md](eval/python.md) | Python evaluation results |
| [eval/typescript.md](eval/typescript.md) | TypeScript evaluation results |
