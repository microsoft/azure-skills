# Foundry Toolbox — Tool Integration for Hosted Agents

Hosted agents access Foundry-managed tools through a **Toolbox MCP endpoint**. Unlike prompt agents that wire tools directly, hosted agents connect to a single MCP-compatible endpoint that exposes all configured tools. The platform handles credential injection, token refresh, and policy enforcement.

## Quick Reference

| Property | Value |
|----------|-------|
| **Toolbox Docs** | https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox |
| **Default Sample (Python)** | https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/toolbox/maf |
| **Python Hosted Agent — `responses`** | https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/bring-your-own/responses |
| **Python Hosted Agent — `invocations`** | https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/bring-your-own/invocations |
| **C# (.NET) Samples** | https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/csharp/toolbox |
| **Supported Tool Types & Auth** | https://github.com/microsoft-foundry/foundry-samples/blob/main/samples/python/toolbox/SUPPORTED_TOOLBOX_TOOLS.md |

## Workflow

```
User wants tools in hosted agent
    │
    ▼
Step 1: Does user have a toolbox?
    │  ├─ Yes → Step 2
    │  └─ No → Ask, then Step 1b to create one
    │
    ▼
Step 2: Generate agent code with toolbox integration
```

After code generation, return to the parent skill's Step 6 (Verify Startup) to run the agent and send a test request. Toolbox auth/connection errors are expected without real Azure credentials — the key validation is that the HTTP server starts and the agent accepts requests.

### Step 1: Resolve Toolbox

If the user provides a toolbox name or endpoint URL, or the project already references a toolbox (e.g., in `.env` or `agent.manifest.yaml`) → proceed to Step 2.

Otherwise, ask: _"Do you have an existing Foundry Toolbox, or should I help create one?"_ Then proceed to Step 1b.

### Step 1b: Create a Toolbox (if needed)

**Available tool types:** Web Search, Azure AI Search, Code Interpreter, File Search, MCP Server, OpenAPI, Agent-to-Agent (A2A). For details, see [Configure tools](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox#configure-tools).

| Method | When to use | References |
|--------|-------------|------------|
| **azd** — preferred | AI can generate `agent.manifest.yaml` and run `azd provision` | [Toolbox docs — azd tab](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox), [`toolbox/azd/`](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/toolbox/azd) (multiple scenario manifests covering tool types + auth patterns) |
| **SDK (Python, .NET, JS)** | AI can generate code to create toolbox programmatically | [Toolbox docs](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox), Python: [`sample_toolboxes_crud.py`](https://github.com/microsoft-foundry/foundry-samples/blob/main/samples/python/toolbox/sample_toolboxes_crud.py), C#: [`csharp/toolbox/crud-sample/`](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/csharp/toolbox/crud-sample) |
| **REST API** | AI can generate HTTP calls | [Toolbox docs — REST API tab](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox) |
| **Foundry Toolkit (VS Code)** — manual | Direct user to create via VS Code extension | [Foundry Toolkit](https://aka.ms/foundrytk), [Tool Catalog](https://code.visualstudio.com/docs/intelligentapps/tool-catalog), [Toolbox docs — VS Code tab](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox) |
| **Foundry Portal** — manual | Direct user to create via portal UI | [Toolbox docs](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox) |

### Step 2: Generate Agent Code with Toolbox

The sample repo provides integration patterns for both Python and C#. Read the sample code and adapt it to the user's project.

**Python samples:**

| Sample | Framework | Protocol | When to use |
|--------|-----------|----------|-------------|
| [`toolbox/maf/`](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/toolbox/maf) — recommended | Agent Framework (MAF) | Responses | **Default choice** |
| [`bring-your-own/responses/langgraph-toolbox/`](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/bring-your-own/responses/langgraph-toolbox) | LangGraph (BYO) | Responses | LangGraph hosted agent with toolbox |
| [`toolbox/copilot-sdk/`](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/toolbox/copilot-sdk) | GitHub Copilot SDK | Responses | Copilot SDK with toolbox tools |
| [`bring-your-own/responses/bring-your-own-toolbox/`](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/bring-your-own/responses/bring-your-own-toolbox) | Generic MCP (BYO) | Responses | Raw `httpx` MCP client — works with any framework |
| [`bring-your-own/invocations/toolbox/`](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/bring-your-own/invocations/toolbox) | Generic MCP (BYO) | Invocations | Toolbox via Invocations protocol |

**C# (.NET) samples:**

| Sample | Description |
|--------|-------------|
| [`csharp/toolbox/maf/`](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/csharp/toolbox/maf) — recommended | Agent Framework agent with toolbox MCP (Responses protocol) |

**Notes:** (apply to all patterns, both Python and C#):
- Auth: Inject a bearer token with scope `https://ai.azure.com/.default` on every request (Python: `httpx.Auth` subclass; C#: `DefaultAzureCredential` + `BearerTokenAuthenticationPolicy`).
- Header: Always include `Foundry-Features: Toolboxes=V1Preview`.
- MCP client: Pass `load_prompts=False` — the toolbox endpoint does not support `prompts/list`.
- Endpoint: Construct from `{project_endpoint}/toolboxes/{toolbox_name}/mcp?api-version=v1`.

> 💡 **Tip:** If MCP tools have `require_approval: "always"` in `_meta.tool_configuration`, the agent runtime must ask the user for confirmation before invoking. The toolbox endpoint does not enforce this — your agent code is responsible.

## Toolbox Reference

### Endpoint Format

The toolbox MCP endpoint is constructed from the **project endpoint** + **toolbox name**:

| Endpoint | URL |
|----------|-----|
| Latest version (default) | `{project_endpoint}/toolboxes/{toolbox_name}/mcp?api-version=v1` |
| Specific version | `{project_endpoint}/toolboxes/{toolbox_name}/versions/{version}/mcp?api-version=v1` |

- **Project endpoint** format: `https://<account>.services.ai.azure.com/api/projects/<project>`
- The latest-version endpoint always serves the toolbox’s `default_version`.
- Use the specific-version endpoint to test a version before promoting it.
- **Required header** on every request: `Foundry-Features: Toolboxes=V1Preview`
- `?api-version=v1` query parameter is **required** — requests without it return HTTP 400.

### MCP Protocol

Toolboxes use **Model Context Protocol (MCP)** — JSON-RPC 2.0 over HTTP POST:

- **`initialize`** — Handshake to establish an MCP session. Returns a `mcp-session-id` header to include in subsequent requests.
- **`tools/list`** — Returns all available tools with names, descriptions, and input schemas.
- **`tools/call`** — Invokes a tool with arguments and returns structured results.

> `prompts/list` is **not supported** by the toolbox endpoint. Always pass `load_prompts=False` to MCP client constructors.

### Authentication

- **Agent → Toolbox:** Azure AD bearer token with scope `https://ai.azure.com/.default`, refreshed on every request.
- **Toolbox → External Services:** Managed by the platform via project connections (API keys, OAuth, managed identity).

### OAuth Consent Handling

When a toolbox includes an OAuth-based MCP connection (e.g., GitHub OAuth), the first call triggers a `CONSENT_REQUIRED` error (MCP error code `-32006`). The error message contains the consent URL.

**Agent code must handle this:**
1. Catch MCP error code `-32006` from `tools/call` or during MCP session initialization.
2. Extract the consent URL from the error message.
3. Log the URL and surface it to the user (e.g., print to stdout or return in the agent response).
4. After the user completes the OAuth flow in a browser, retry the call — subsequent calls succeed without re-prompting.

> This is a one-time flow per user per OAuth connection in a project. The agent should not silently swallow this error.

### Testing the Toolbox Endpoint

Before running the full agent, verify the toolbox MCP endpoint works end-to-end. Use `az login` for authentication, then test the three MCP operations in order:

**1. Get a bearer token:**
```bash
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)
TOOLBOX_URL="https://<account>.services.ai.azure.com/api/projects/<project>/toolboxes/<name>/mcp?api-version=v1"
```

**2. Initialize MCP session:**
```bash
curl -sS -X POST "$TOOLBOX_URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Foundry-Features: Toolboxes=V1Preview" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"debug","version":"1.0.0"}}}' \
  -D - | head -20
```
Save the `mcp-session-id` header from the response for subsequent calls.

**3. List tools:**
```bash
curl -sS -X POST "$TOOLBOX_URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Foundry-Features: Toolboxes=V1Preview" \
  -H "mcp-session-id: <session-id-from-step-2>" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | jq .
```

**Checklist:**
- Response contains `result.tools[]` with `len > 0`
- Each tool has `name`, `description`, and `inputSchema` with a `properties` field
- MCP tool names for remote servers are prefixed with `server_label` (e.g., `myserver.get_info`)

**4. Call a tool (optional):**
```bash
curl -sS -X POST "$TOOLBOX_URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Foundry-Features: Toolboxes=V1Preview" \
  -H "mcp-session-id: <session-id-from-step-2>" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"<tool_name>","arguments":{"query":"test"}}}' | jq .
```

> For a Python-based debug client, see the `_McpToolboxClient` class in the [BYO toolbox sample `main.py`](https://github.com/microsoft-foundry/foundry-samples/blob/main/samples/python/hosted-agents/bring-your-own/responses/bring-your-own-toolbox/main.py) — it implements `initialize`, `list_tools`, and `call_tool` using raw `httpx` calls.

## Troubleshooting

| Error | Cause | Resolution |
|-------|-------|------------|
| CONSENT_REQUIRED (code -32006) | OAuth MCP connection needs user consent | Open consent URL in browser, complete OAuth flow, retry |
| 401 on MCP calls | Expired token or wrong scope | Use scope `https://ai.azure.com/.default` and refresh token |
| 500 on `prompts/list` | Not supported by toolbox endpoint | Pass `load_prompts=False` to MCP client constructor |
| 500 with non-streaming `tools/call` | Non-streaming not supported | Always use `stream=True` for toolbox MCP tools |
