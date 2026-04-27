# Blob Storage with Event Grid Recipe

Blob trigger via Event Grid for high-scale, low-latency blob processing.

## Template Selection

Resource filter: `blob`  
Discover templates via MCP or CDN manifest where `resource == "blob"` and `language` matches user request.

## Why Event Grid?

| Aspect | Polling Trigger | Event Grid Source |
|--------|-----------------|-------------------|
| **Latency** | 10s-60s | Sub-second |
| **Scale** | Limited | High-scale |

## Troubleshooting

### "Unauthorized" or "Forbidden" Errors

**Cause:** Missing UAMI credential settings for Storage.  
**Solution:** Ensure these settings are present in app configuration (prefix must match the connection name used in your function code, default: `AzureWebJobsStorage`):

- `<ConnectionName>__blobServiceUri` (e.g., `https://<account>.blob.core.windows.net`)
- `<ConnectionName>__credential` (value: `managedidentity`)
- `<ConnectionName>__clientId`

See [Blob Storage trigger connections](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-storage-blob-trigger#connections) for identity-based config — refer to the **"Connections"** section on that page for managed identity app settings.

### Blob Events Not Triggering

**Cause:** Event Grid subscription not created or filtering incorrectly.  
**Solution:** Verify the Event Grid system topic and subscription exist. Check the blob container prefix filter matches the expected path.

## Eval

| Path | Description |
|------|-------------|
| [eval/summary.md](eval/summary.md) | Evaluation summary |
| [eval/python.md](eval/python.md) | Python evaluation results |
