# Toolbox MCP protocol, tool naming & testing

## Endpoint URL details
- **Consumer** — `{project_endpoint}/toolboxes/{toolbox_name}/mcp?api-version=v1`. Always serves the `default_version`. Connect agents here so promoting a version needs no redeploy.
- **Developer** — `{project_endpoint}/toolboxes/{toolbox_name}/versions/{version}/mcp?api-version=v1`. Test a specific version before promoting.
- `?api-version=v1` is **required** — requests without it return HTTP 400.
- Auth: bearer token with scope `https://ai.azure.com/.default`.

## MCP protocol

Toolboxes use **Model Context Protocol (MCP)** — JSON-RPC 2.0 over HTTP POST:

- **`initialize`** — optional handshake. `tools/list` / `tools/call` work without it. If you call it and the server returns an `mcp-session-id` header, resend it on subsequent calls.
- **`tools/list`** — returns all tools with names, descriptions, and input schemas.
- **`tools/call`** — invokes a tool and returns structured results. Plain POST works; SSE streaming is optional.

> `prompts/list` is **not supported**. If your MCP client calls it automatically (e.g. MAF's `MCPStreamableHTTPTool`), pass `load_prompts=False`.

## Tool naming

- **MCP-sourced tools** (`type: mcp`) are exposed as `{server_label}___{tool_name}` — **three underscores** (e.g. `myserver___get_info`).
- **All other tool types** use the entry's `name` field, or the default tool name if unset.
- **Tool Search** injects two meta-tools named `tool_search` and `call_tool`.

Each tool from `tools/list` includes a `_meta.tool_configuration` block with the `type` plus type-specific fields (e.g. `server_label`, `server_url`, `require_approval` for MCP).

## Testing the toolbox endpoint

Verify the MCP endpoint end-to-end with a bearer token + raw `tools/list` / `tools/call` — see [test-endpoint.md](test-endpoint.md).

## Troubleshooting (create / provision)

| Symptom | Likely cause |
|---------|--------------|
| `TOOLBOX_ENDPOINT` not set | Run `azd ai toolbox show` + `azd env set`. |
| Env var missing in deployed agent | Add to the agent service's `environmentVariables` in `azure.yaml`, `azd deploy`. |
| `403 Forbidden` (incl. `POST /toolboxes`, connection PUT) | Caller lacks `Foundry User` (or `Azure AI Developer`) on the project — grant at project scope. |
| 400 `Multiple tools without identifiers found` | Two unnamed tools (or duplicate `server_label`) — keep **at most one unnamed tool**; name each other. See [toolbox-azd.md § Multi-tool rule](toolbox-azd.md#multi-tool-rule). |
| `tools/list` returns zero | Version still provisioning, or tool type unavailable in region — wait ~10s, retry, or try another region. |
| `tools/list` zero for MCP/A2A only | Invalid/missing connection creds — verify `project_connection_id`; for MI auth, check RBAC on the target. |
| `tools/list` zero for OpenAPI only | Invalid OpenAPI spec — validate against 3.0/3.1; for MI auth, verify RBAC. |

For runtime/MCP-client errors (token scope, `prompts/list`, `require_approval`, tool-name prefixes), see [use-toolbox-in-hosted-agent.md § Troubleshooting](../../create/references/use-toolbox-in-hosted-agent.md#troubleshooting).
