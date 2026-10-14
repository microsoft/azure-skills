# Managed Harness Agent Authoring

A Microsoft Foundry Managed Harness Agent is a Prompt Agent configured with the Foundry-managed GitHub Copilot harness. This skill uses azd to author and deploy it:

```yaml
services:
  assistant:
    host: azure.ai.agent
    kind: prompt
    name: assistant
    model: gpt-5-mini
    instructions: Help the user.
    harness:
      type: github_copilot_preview
```

Use REST field names, normally `snake_case`, inside `tools[]`. azd strictly validates the harness and Copilot toolset; most other nested tool fields pass through to Foundry.

## Direct tools

Prefer direct tool definitions unless the user explicitly requests a Toolbox:

```yaml
tools:
  - type: web_search
  - type: code_interpreter
```

Read [Managed Harness Agent Tools](tools/managed-harness-agent/agent-tools.md) for the supported tools, required fields, connections, and per-tool authoring references.

## Toolbox attachment

A Managed Harness Agent prefers direct tools. When the user explicitly requests an existing Toolbox, create or update it separately with `azd ai toolbox`, then attach its versioned MCP endpoint as a direct tool:

```yaml
tools:
  - type: mcp
    server_label: research-tools
    server_url: https://<account>.services.ai.azure.com/api/projects/<project>/toolboxes/<toolbox>/versions/<version>/mcp?api-version=v1
    require_approval: never
```

Resolve the endpoint from the separately managed Toolbox:

```bash
azd ai toolbox show <toolbox-name> \
  --version <version> \
  --project-endpoint "<project-endpoint>" \
  --output json
```

Do not declare `host: azure.ai.toolbox` in this phase: that would make `azd deploy` create or update the Toolbox. Do not use the Agent's singular `toolbox` field, which expects an azd-managed sibling Toolbox service.

If the Toolbox endpoint requires a project connection, add its connection ID:

```yaml
tools:
  - type: mcp
    server_label: research-tools
    server_url: <versioned-toolbox-mcp-endpoint>
    project_connection_id: <toolbox-connection>
    require_approval: never
```

Do not use Hosted Agent `TOOLBOX_ENDPOINT` code wiring for a Managed Harness Agent.

## Skill attachment

Create and version Skills separately with `azd ai skill`. Reference an existing Foundry Skill by name and immutable version:

```yaml
skills:
  - name: issue-triage
    version: "3"
```

For a local Skill, upload it first:

```bash
azd ai skill create issue-triage \
  --file ./skills/issue-triage/ \
  --project-endpoint "<project-endpoint>" \
  --output json
```

Use the returned version in `azure.yaml`. For updates, run `azd ai skill update` and replace the pinned version.

Do not declare `host: azure.ai.skill` in this phase: that would make `azd deploy` manage the Skill lifecycle.

## Validation

After deploy, read the published definition and verify:

- `kind` remains `prompt`.
- `harness.type` remains `github_copilot_preview`.
- Direct tools retain their authored fields.
- The versioned Toolbox MCP endpoint remains in the direct `mcp` tool.
- Skill references retain both `name` and `version`.

Managed Harness Agents, ordinary Prompt Agents, and Hosted Agents are not converted in place.
