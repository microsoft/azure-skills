# Tool — Tool Search (preview) (`type: toolbox_search_preview`)

For toolboxes containing many tools, replace the full tool list passed to the model with two meta-tools — `tool_search` (natural-language discovery, returns matching tools per query) and `call_tool` (invoke any discovered tool by name) — so context cost stays flat regardless of toolbox size.

Tool Search is a **connectionless directive** — it's declared under a `tools:` block (like `web_search`); **no project connection required**. It is **not** a standalone toolbox: pair it with the tools it should index (see [Behavior](#behavior) and the [Multi-tool rule](toolbox-azd.md#multi-tool-rule)).

> 🚦 Before creating a toolbox/connection either way, read [create-hosted.md → Toolbox creation boundary](../../create/create-hosted.md#toolbox-creation-boundary).

## Toolbox shape

```json
{ "type": "toolbox_search_preview" }
```

---

# A. Imperative CLI

Steps 1–3 of [toolbox.md § The flow](../toolbox.md#the-flow). Tool Search needs no connection, so it goes under a `tools:` block. Write the toolbox spec to a **file** — `azd ai toolbox create --from-file` takes a **path** (stdin `-` is not supported). Because `toolbox_search_preview` **counts** as the one allowed unnamed tool, every other tool in the same spec must carry a `name` / `server_label`, or the create fails with `400 invalid_payload: Multiple tools without identifiers found`.

```bash
# 0. Install the CLI extension (once)
azd extension install azure.ai.toolboxes

# Write the toolbox spec to a file — Tool Search directive + the tools it indexes
cat > ts.yaml <<'EOF'
description: agent-tools with Tool Search
tools:
  - type: toolbox_search_preview       # the one allowed unnamed tool
  - type: web_search
    name: web_search                   # MUST be named once toolbox_search_preview is present
connections:
  - name: analytics-mcp                # any MCP connections to index (RemoteTool)
EOF
```

**Create a new toolbox** (first version auto-promoted):

```bash
azd ai toolbox create agent-tools --from-file ts.yaml --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

> **Add to an existing toolbox:** like other connectionless built-ins, the current `azd` CLI does **not** support adding `toolbox_search_preview` to an existing toolbox via `azd ai toolbox connection add` — recreate the toolbox (`azd ai toolbox create`) with the full tool set.

`--from-file` entry:

```yaml
tools:
  - type: toolbox_search_preview       # connectionless directive; unnamed (counts as the one unnamed tool)
```

---

# B. Declarative `azure.yaml`

Declare the toolbox as a `host: azure.ai.toolbox` service in `azure.yaml`; `azd deploy` upserts it (and auto-promotes the new version). Needs only an **existing** Foundry project (via `FOUNDRY_PROJECT_ENDPOINT` + `AZURE_SUBSCRIPTION_ID` in the azd env) — **no `azd provision`**, no `infra:` block.

```yaml
name: my-agent-project
services:
  agent-tools:
    host: azure.ai.toolbox
    tools:
      - type: toolbox_search_preview   # the one unnamed tool
      - type: web_search
        name: web_search               # named — required alongside toolbox_search_preview
      - type: mcp
        server_label: analytics        # server_label acts as its identifier
        project_connection_id: analytics-mcp

  # A hosted agent in the same project consumes the toolbox by name
  my-agent:
    host: azure.ai.agent
    uses:
      - agent-tools          # depend on the toolbox service
    environmentVariables:
      - name: TOOLBOX_NAME
        value: agent-tools    # agent resolves the MCP endpoint at runtime
```

```bash
azd deploy agent-tools
```

The agent references the toolbox **by name** (`TOOLBOX_NAME`), so the MCP endpoint resolves at runtime — no endpoint string is hard-coded. See [use-toolbox-in-hosted-agent.md](../../create/references/use-toolbox-in-hosted-agent.md).

---

## Behavior

- `toolbox_search_preview` is a **configuration directive** — it doesn't appear in `tools/list` itself, but it **counts** as the toolbox's one allowed unnamed tool. If you pair it with any other unnamed tool (e.g. a bare `web_search`), the create fails with `400 invalid_payload: Multiple tools without identifiers found` — give the other tools a `name` / `server_label`.
- All other toolbox tools are **hidden** from the initial `tools/list` and are returned only by `tool_search` calls (or by per-user auto-pinning of hot tools).
- Pin specific tools or add search-only keywords via `tool_configs.{tool_name}`:

  ```json
  {
    "type": "mcp",
    "server_label": "analytics",
    "server_url": "https://db-mcp.internal/sse",
    "tool_configs": {
      "execute_query": { "pin": true, "additional_search_text": "SQL analytics reporting dashboard" },
      "*":             { "additional_search_text": "data warehouse queries" }
    }
  }
  ```

  Use `"*"` as the key to apply settings to all tools in that entry.
- `additional_search_text` is used only for search ranking — it's never exposed to the model in the tool schema.
- Tool **descriptions drive match quality**: every MCP tool should have a clear `description`, or `tool_search` won't find it.
- Recommendation: add an instruction in the system prompt telling the model to call `tool_search` when a needed capability isn't in its current tool list.

## Verify & deploy

After creating the toolbox either way, verify its MCP endpoint end-to-end — with Tool Search enabled, `tools/list` returns only `tool_search` + `call_tool` (the indexed tools are hidden until a `tool_search` call surfaces them). See [test-endpoint.md](test-endpoint.md).

## References

For full fields, pinning recipes, the verify-with-`tool_search` flow, and best practices, see [Tool Search tool documentation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/tool-search).

- [agent-tools.md](../../create/references/tools/prompt-agent/agent-tools.md) — tool index
- [toolbox.md § Enable Tool Search](../toolbox.md#enable-tool-search)
