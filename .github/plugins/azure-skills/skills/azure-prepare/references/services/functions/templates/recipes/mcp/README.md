# MCP (Model Context Protocol) Recipe

MCP tool endpoints for AI agent integration via the JSON-RPC 2.0 protocol.

## Template Selection

Resource filter: `mcp`  
Discover templates via MCP or CDN manifest where `resource == "mcp"` and `language` matches user request.

## Protocol

MCP uses the **JSON-RPC 2.0** protocol. Two template types with different transport support:

- **Extension-based** (`mcp-server-remote-*`) supports both Streamable HTTP and SSE transports
- **Self-hosted** (`mcp-sdk-hosting-*`) — supports Streamable HTTP only

See [MCP Specification](https://modelcontextprotocol.io/) for protocol details.

## Troubleshooting

### Transport Mismatch

**Cause:** Client and server using different transports — SSE client gets `404`/`405`, HTTP client gets unexpected `text/event-stream`.  
**Solution:** Extension-based templates support both Streamable HTTP and SSE. Self-hosted templates support Streamable HTTP only. In VS Code `mcp.json`, set `"type": "sse"` or `"type": "http"` to match the server.

### Missing App Settings After Deploy

**Cause:** Required app settings not configured on the function app.  
**Solution:** Ensure protected resource metadata settings are present. For C# self-hosted servers, verify `host.json` `arguments` points to the compiled DLL path.

See [MCP extension trigger and bindings](https://learn.microsoft.com/azure/azure-functions/functions-bindings-mcp) for extension-based servers, [Self-hosted MCP servers](https://learn.microsoft.com/en-us/azure/azure-functions/self-hosted-mcp-servers) for self-hosted architecture, and [MCP tutorial troubleshooting](https://learn.microsoft.com/en-us/azure/azure-functions/functions-mcp-tutorial?tabs=self-hosted#troubleshooting) for self-hosted deployment issues.

## Eval

| Path | Description |
|------|-------------|
| [eval/summary.md](eval/summary.md) | Evaluation summary |
| [eval/python.md](eval/python.md) | Python evaluation results |
