# Tool — Browser Automation (`type: browser_automation_preview`) — preview

Browser automation backed by an **Azure Playwright workspace**. Auth is `ProjectManagedIdentity`; the connection kind is `PlaywrightWorkspace`. For the toolbox concept, versions, and endpoint, see [toolbox.md](../toolbox.md).

The tool uses the **nested** shape: a `browser_automation_preview: { connection: { project_connection_id: ... } }` object under the tool entry (not a top-level `connections:` array).

> 🚦 Before creating a toolbox/connection either way, read [create-hosted.md → Toolbox creation boundary](../../create/create-hosted.md#toolbox-creation-boundary).

---

## Prerequisite — an Azure Playwright workspace + connection

An **Azure Playwright workspace** must exist first (create it in the Azure portal / via the `Microsoft.AzurePlaywrightService` resource provider — workspace creation may be gated in some subscriptions). Then create a `PlaywrightWorkspace` connection on the project that points at it; the tool references that connection by `project_connection_id`.

---

# A. Imperative CLI

Steps 1–3 of [toolbox.md § The flow](../toolbox.md#the-flow). Write the toolbox spec to a **file** — `azd ai toolbox create --from-file` takes a **path** (stdin `-` is not supported).

```bash
# 0. Install the CLI extension (once)
azd extension install azure.ai.toolboxes

# Write the toolbox spec to a file
cat > ba.yaml <<'EOF'
description: browser automation toolbox
tools:
  - type: browser_automation_preview
    name: browser
    browser_automation_preview:
      connection:
        project_connection_id: my-playwright-conn   # the PlaywrightWorkspace connection
EOF
```

**Create a new toolbox** (first version auto-promoted):

```bash
azd ai toolbox create agent-tools --from-file ba.yaml --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"
```

> The CLI also accepts a `connections: [{ name: my-playwright-conn }]` alias, which it expands into the nested tool above — but the raw toolbox API accepts only the `tools:` shape.

---

# B. Declarative `azure.yaml`

Declare the toolbox as a `host: azure.ai.toolbox` service in `azure.yaml`; `azd deploy` upserts it (and auto-promotes the new version). Needs only an **existing** Foundry project (via `FOUNDRY_PROJECT_ENDPOINT` + `AZURE_SUBSCRIPTION_ID` in the azd env) — **no `azd provision`**, no `infra:` block. The `PlaywrightWorkspace` connection must already exist (see prerequisite).

```yaml
name: my-agent-project
services:
  agent-tools:
    host: azure.ai.toolbox
    tools:
      - type: browser_automation_preview
        name: browser
        browser_automation_preview:
          connection:
            project_connection_id: my-playwright-conn

  # A hosted agent in the same project consumes the toolbox by name
  my-agent:
    host: azure.ai.agent
    uses:
      - agent-tools
    environmentVariables:
      - name: TOOLBOX_NAME
        value: agent-tools
```

```bash
azd deploy agent-tools
```

---

## Verify & deploy

After creating the toolbox either way, verify its MCP endpoint end-to-end — see [test-endpoint.md](test-endpoint.md). Browser automation surfaces as MCP sub-tools under your `name` prefix (e.g. `browser___create_session`, joined by three underscores). Calling them needs a working Playwright workspace + connection.

---

## References

- [Browser automation tool documentation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/browser-automation)
- [toolbox.md § Supported tool types](../toolbox.md#supported-tool-types)
