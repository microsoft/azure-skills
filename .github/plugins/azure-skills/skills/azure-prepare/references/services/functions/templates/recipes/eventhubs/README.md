# Event Hubs Recipe

Event Hubs streaming trigger with managed identity authentication.

## Template Selection

Resource filter: `eventhub`  
Discover templates via MCP or CDN manifest where `resource == "eventhub"` and `language` matches user request.

## Troubleshooting

### "Unauthorized" or "Forbidden" Errors

**Cause:** Missing UAMI credential settings for Event Hubs.  
**Solution:** Ensure all three settings are present in app configuration:

- `EventHubConnection__fullyQualifiedNamespace`
- `EventHubConnection__credential` (value: `managedidentity`)
- `EventHubConnection__clientId`

See [Event Hubs trigger connections](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-event-hubs-trigger#connections) for identity-based config — refer to the **"Connections"** section on that page for managed identity app settings.

### Events Not Arriving

**Cause:** Consumer group or checkpoint storage misconfigured.  
**Solution:** Verify the Event Hubs consumer group exists and the function has `Azure Event Hubs Data Receiver` role on the namespace.

## Eval

| Path | Description |
|------|-------------|
| [eval/summary.md](eval/summary.md) | Evaluation summary |
| [eval/python.md](eval/python.md) | Python evaluation results |
