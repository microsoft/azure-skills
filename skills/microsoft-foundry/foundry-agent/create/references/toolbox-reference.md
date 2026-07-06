# Toolbox Reference

Endpoint format, MCP protocol details, authentication, OAuth consent handling, endpoint testing, citation pattern, and troubleshooting for Foundry Toolboxes.

## Endpoint Format

The toolbox MCP endpoint is constructed from the **project endpoint** + **toolbox name**:

| Endpoint | URL |
|----------|-----|
| Latest version (default) | `{project_endpoint}/toolboxes/{toolbox_name}/mcp?api-version=v1` |
| Specific version | `{project_endpoint}/toolboxes/{toolbox_name}/versions/{version}/mcp?api-version=v1` |

- **Project endpoint** format: `https://<account>.services.ai.azure.com/api/projects/<project>`
- The latest-version endpoint always serves the toolbox's `default_version`.
- Use the specific-version endpoint to test a version before promoting it.
- `?api-version=v1` query parameter is **required** — requests without it return HTTP 400.

### Agent env contract

Hosted agents read the MCP endpoint from a single environment variable. The **canonical** name is **`TOOLBOX_ENDPOINT`** — use it in all new code and `.env` files:

```
# Latest version (recommended for prod):
TOOLBOX_ENDPOINT=https://{host}/api/projects/{project}/toolboxes/{toolbox_name}/mcp?api-version=v1

# Pinned to a specific version (recommended for testing a new version before promoting):
TOOLBOX_ENDPOINT=https://{host}/api/projects/{project}/toolboxes/{toolbox_name}/versions/{version}/mcp?api-version=v1
```

> ⚠️ **Don't use `FOUNDRY_TOOLBOX_ENDPOINT` in new code.** The Foundry platform **reserves** all environment variables prefixed `FOUNDRY_` and may silently overwrite user-defined values at runtime. Always use a name without the `FOUNDRY_` prefix (e.g. `TOOLBOX_ENDPOINT` or `TOOLBOX_MCP_ENDPOINT`). Some older samples still reference `FOUNDRY_TOOLBOX_ENDPOINT` — treat that as **deprecated/legacy** and only fall back to it when maintaining a sample that already wires it.

## MCP Protocol

Toolboxes use **Model Context Protocol (MCP)** — JSON-RPC 2.0 over HTTP POST:

- **`initialize`** — Optional MCP handshake. The toolbox endpoint is effectively **stateless**: it does **not** return an `mcp-session-id` header, and `tools/list` / `tools/call` work without first calling `initialize` or passing any session header.
- **`tools/list`** — Returns all available tools with names, descriptions, and input schemas.
- **`tools/call`** — Invokes a tool with arguments and returns structured results.

> `prompts/list` is **not supported** by the toolbox endpoint. Always pass `load_prompts=False` to MCP client constructors.

### Tool naming

- **MCP-sourced tools** (`type: mcp`) are exposed as `{server_label}___{tool_name}` — joined by **three underscores** (e.g. `myserver___get_info`). Call them with the prefixed name in `tools/call`.
- **All other tool types** (`web_search`, `file_search`, `azure_ai_search`, `code_interpreter`, `openapi`, `a2a_preview`, `work_iq_preview`, `fabric_iq_preview`, …) use the value of the entry's `name` field, or the default tool name if `name` is unset.
- **Tool Search** injects two platform meta-tools whose names are always `tool_search` and `call_tool`.

Each tool returned by `tools/list` includes a `_meta.tool_configuration` block with at least the `type`, plus type-specific fields (e.g. `server_label`, `server_url`, `require_approval` for MCP).

## Authentication

- **Agent → Toolbox:** Azure AD bearer token with scope `https://ai.azure.com/.default`, refreshed on every request.
- **Toolbox → External Services:** Managed by the platform via project connections (API keys, OAuth, managed identity). See [foundry-tool-catalog.md](foundry-tool-catalog.md) for the connection shapes that back each tool type.

> ⚠️ Do **not** use scope `https://cognitiveservices.azure.com/.default`. The toolbox MCP endpoint rejects it with HTTP 401.

> 💡 **If you're hitting OAuth errors (e.g. `CONSENT_REQUIRED`, ARA-style "authentication required" errors, or 401s) when calling an MCP server directly from your agent**, switch to wiring the same MCP server into a toolbox. The toolbox handles the full OAuth flow — bearer-token acquisition, refresh, consent discovery, and per-user token passthrough — so your agent only ever talks to the toolbox MCP endpoint with a standard `https://ai.azure.com/.default` token. This is the recommended path for any OAuth-based MCP server in a hosted agent.

## OAuth Consent Handling

When a toolbox includes an OAuth-based MCP connection (e.g., GitHub OAuth), the **first** call from a new user surfaces a consent requirement. The toolbox wraps per-source failures in a JSON-RPC error with outer **code `-32006`** (`tools/list failed for N tool source(s)…`); the failing source's nested error carries the **string** code `"CONSENT_REQUIRED"`, and its `message` is the consent URL. This can surface on `tools/list`, `initialize`, or `tools/call` depending on when the server discovers the missing grant.

**Agent code must handle this:**

1. On a `-32006` error, extract the embedded JSON from the outer `message`. **The message is not directly JSON-parseable** — it begins with a human-readable prefix (`tools/list failed for N tool source(s), succeeded for M tool source(s) `) followed by a `{"errors":[...]}` payload. Locate the first `{` and parse from there (do **not** call `JSON.parse` on the whole `message`):

   ```python
   msg = err["message"]
   payload = json.loads(msg[msg.index("{"):])   # slice off the prefix first
   ```

2. Detect the nested `"code":"CONSENT_REQUIRED"` in `payload["errors"][i]["error"]` and read the consent URL from that nested `message`.
3. Log the URL and surface it to the user (e.g., print to stdout or return in the agent response).
4. After the user completes the OAuth flow in a browser, retry the call — subsequent calls succeed without re-prompting.

Example error shape (as actually returned — note the prefix text before the JSON):

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32006,
    "message": "tools/list failed for 1 tool source(s), succeeded for 0 tool source(s) {\"errors\":[{\"name\":\"GitHub\",\"type\":\"mcp\",\"error\":{\"code\":\"CONSENT_REQUIRED\",\"message\":\"https://logic-apis-<region>.consent.azure-apim.net/login?data=...\"}}]}"
  }
}
```

> This is a one-time flow per user per OAuth connection in a project. The agent should not silently swallow this error.

## Multi-Tool Toolbox Constraint

A single toolbox can combine multiple tools, but **at most one tool per unnamed tool type**. Tools like `web_search`, `file_search`, `azure_ai_search`, and `code_interpreter` have no identifier; to include more than one instance of the same type, set a unique `name` on each instance. MCP tools must each have a unique `server_label`.

If you include two unnamed tools of the same type (or two MCP tools with the same `server_label`), the API returns:

```
400 invalid_payload: Multiple tools without identifiers found...
```

Valid combinations include:

- `file_search` + one or more `mcp` (each with unique `server_label`)
- `web_search` + one or more `mcp`
- `azure_ai_search` + one or more `mcp`
- `toolbox_search_preview` (the Tool Search directive — doesn't count toward the limit) + any other tools

## Azure AI Search Citation Pattern

When calling an `azure_ai_search` tool through the toolbox MCP endpoint, citation metadata is returned under `result.structuredContent.documents[]` — **not** in a separate `citations` array. Treat each document as one citation:

| Field | Meaning |
|-------|---------|
| `title` | Citation display text |
| `url` | Source link |
| `id` | Source identifier |
| `score` | Retrieval relevance score |
| `knowledgeSourceIndex` | Source grouping / index |

Verification checklist:

1. `tools/list` returns the tool name `azure_ai_search`.
2. `tools/call` succeeds with a `query` argument.
3. `result.structuredContent.documents` is present and non-empty.
4. At least one document has both `title` and `url`.

For File Search and Web Search citation patterns (under `result.content[].resource._meta` and `..._meta.annotations[]` respectively), see the public [Toolbox docs](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox).

## Testing the Toolbox Endpoint

Before running the full agent, verify the toolbox MCP endpoint works end-to-end. Use `az login` for authentication, then test the three MCP operations in order:

**1. Get a bearer token:**

```bash
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)
TOOLBOX_URL="https://<account>.services.ai.azure.com/api/projects/<project>/toolboxes/<name>/mcp?api-version=v1"
```

**2. (Optional) Initialize MCP session:**

The toolbox endpoint is stateless, so this step is not required — `tools/list` and `tools/call` work without it. Run it only to confirm the handshake:

```bash
curl -sS -X POST "$TOOLBOX_URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"debug","version":"1.0.0"}}}' \
  -D - | head -20
```

No `mcp-session-id` header is returned, and none is needed on later calls.

**3. List tools:**

```bash
curl -sS -X POST "$TOOLBOX_URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | jq .
```

Checklist:

- Response contains `result.tools[]` with `len > 0`
- Each tool has `name`, `description`, and `inputSchema` with a `properties` field
- MCP tool names for remote servers are prefixed with `server_label` joined by three underscores (e.g., `myserver___get_info`)
- All other tool types use the entry's `name` field value (or the default tool name)

**4. Call a tool (optional):**

```bash
curl -sS -X POST "$TOOLBOX_URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"<tool_name>","arguments":{"query":"test"}}}' | jq .
```

## Troubleshooting

| Error | Cause | Resolution |
|-------|-------|------------|
| `CONSENT_REQUIRED` (nested string code inside an outer `-32006` error) | OAuth MCP connection needs user consent | Parse the consent URL from the nested error `message`, open it in a browser, complete OAuth, retry |
| 401 on MCP calls | Expired token or wrong scope | Use scope `https://ai.azure.com/.default` (not `cognitiveservices`) and refresh token on every request |
| OAuth/ARA errors when calling MCP directly from agent | Direct MCP wiring without toolbox token passthrough | Wire the MCP server into a toolbox and call the toolbox endpoint instead — Foundry handles consent + refresh |
| 400 `invalid_payload: Multiple tools without identifiers found` | Two unnamed tools of the same type (or duplicate `server_label`) in one toolbox | Keep at most one unnamed tool per type; give each MCP tool a unique `server_label` |
| `tools/list` returns 0 tools | Toolbox version still provisioning, or tool type not yet available in the region | Wait ~10s and retry; try a different region |
| `tools/list` returns 0 tools for MCP/A2A only | Invalid or missing connection credentials | Verify `project_connection_id` exists and credentials are correct; for MI auth, check RBAC on the target service |
| `tools/list` returns 0 tools for OpenAPI only | Invalid OpenAPI spec (malformed paths, missing operationIds) | Validate the spec against OpenAPI 3.0/3.1; for MI auth, also verify RBAC |
| Tool not found on `tools/call` | Missing `server_label___` prefix for MCP-sourced tools | Call as `{server_label}___{tool_name}` (three underscores) |
| 500 on `prompts/list` | Not supported by toolbox endpoint | Pass `load_prompts=False` to MCP client constructor |
| 500 on `send_ping()` (MAF `MCPStreamableHTTPTool._ensure_connected`) | Toolbox MCP server doesn't implement `ping` | Disable the ping check or override with a no-op |
| 500 with non-streaming `tools/call` | Non-streaming not supported | Always use `stream=True` for toolbox MCP tools |
| 400 missing `api-version` | Query string dropped | Append `?api-version=v1` to every toolbox URL |
| Environment variable silently overwritten at runtime | Foundry reserves `FOUNDRY_`-prefixed env vars | Rename to a non-`FOUNDRY_` name (e.g. `TOOLBOX_ENDPOINT`) |
| 403 on `POST /toolboxes` or `PUT .../connections/...` | Caller lacks `Foundry User` (or `Azure AI Developer` / `Cognitive Services Contributor`) on the project | Grant the role at the project scope |
