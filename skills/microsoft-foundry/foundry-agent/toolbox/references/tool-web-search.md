# Tool — Web Search (`type: web_search`)

Basic Bing web search (Grounding with Bing Search) is a **connectionless built-in** — declared under a `tools:` block; **no project connection required**. This is the supported path today. For the toolbox concept, versions, and endpoint, see [toolbox.md](../toolbox.md).

> 🚦 Before creating a toolbox/connection either way, read [create-hosted.md → Toolbox creation boundary](../../create/create-hosted.md#toolbox-creation-boundary).

---

# A. Imperative CLI

## Full flow — basic web search (no connection)

Steps 1–3 of [toolbox.md § The flow](../toolbox.md#the-flow) — basic Bing needs no connection, so it goes under a `tools:` block. Write the toolbox spec to a **file** — `azd ai toolbox create --from-file` takes a **path** (stdin `-` is not supported).

```bash
# 0. Install the CLI extension (once)
azd extension install azure.ai.toolboxes

# Write the toolbox spec to a file
cat > ws.yaml <<'EOF'
description: web-search toolbox
tools:
  - type: web_search
EOF
```

**Create a new toolbox** (first version auto-promoted):

```bash
azd ai toolbox create agent-tools --from-file ws.yaml --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

> **Add to an existing toolbox:** the current `azd` CLI does **not** support adding a connectionless built-in to an existing toolbox — you can only create a new toolbox (`azd ai toolbox create`) with the full tool set.

`--from-file` entry (`name` optional; add one only for multiple `web_search` instances):

```yaml
tools:
  - type: web_search           # basic Bing — connectionless
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
      - type: web_search
        name: web_search

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

## Verify & deploy

After creating the toolbox either way, verify its MCP endpoint end-to-end (bearer token + raw `tools/list` / `tools/call`) — see [test-endpoint.md](test-endpoint.md).

---

## References

- [Web Search tool documentation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/web-search)
- [Web Search vs Grounding with Bing Search](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/web-overview)
- [toolbox.md § Supported tool types](../toolbox.md#supported-tool-types)
