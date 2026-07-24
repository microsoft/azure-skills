# Tool — Code Interpreter (`type: code_interpreter`)

Sandboxed Python execution — a **connectionless built-in** declared under a `tools:` block; **no project connection required**. Fully toolbox-compatible: the toolbox MCP endpoint (and a hosted agent) can invoke it directly. For the toolbox concept, versions, and endpoint, see [toolbox.md](../toolbox.md).

> 🚦 Before creating a toolbox/connection either way, read [create-hosted.md → Toolbox creation boundary](../../create/create-hosted.md#toolbox-creation-boundary).

---

# A. Imperative CLI

## Full flow

Steps 1–3 of [toolbox.md § The flow](../toolbox.md#the-flow) — connectionless, so it goes under a `tools:` block. Write the toolbox spec to a **file** — `azd ai toolbox create --from-file` takes a **path** (stdin `-` is not supported).

```bash
# 0. Install the CLI extension (once)
azd extension install azure.ai.toolboxes

# Write the toolbox spec to a file
cat > ci.yaml <<'EOF'
description: code-interpreter toolbox
tools:
  - type: code_interpreter
    container: { type: auto }
EOF
```

**Create a new toolbox** (first version auto-promoted):

```bash
azd ai toolbox create agent-tools --from-file ci.yaml --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

> **Add to an existing toolbox:** the current `azd` CLI does **not** support adding a connectionless built-in to an existing toolbox — you can only create a new toolbox (`azd ai toolbox create`) with the full tool set.

`--from-file` entry (`container: { type: auto }` for a fresh sandbox; supply `file_ids` to preload files):

```yaml
tools:
  - type: code_interpreter
    container: { type: auto }
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
      - type: code_interpreter
        container: { type: auto }

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

After creating the toolbox either way, verify its MCP endpoint end-to-end — see [test-endpoint.md](test-endpoint.md). A raw `tools/call` executes Python directly:

```bash
TOK=$(az account get-access-token --resource "https://ai.azure.com" --query accessToken -o tsv)
URL="$FOUNDRY_PROJECT_ENDPOINT/toolboxes/agent-tools/mcp?api-version=v1"
curl -s -X POST "$URL" -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"code_interpreter","arguments":{"code":"print(6*7)"}}}'
# -> content ... text='42\n' , isError: false
```

---

## References

- [Code Interpreter tool documentation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/code-interpreter)
- [toolbox.md § Supported tool types](../toolbox.md#supported-tool-types)
