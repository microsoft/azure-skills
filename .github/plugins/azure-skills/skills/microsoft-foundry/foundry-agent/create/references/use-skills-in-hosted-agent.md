# Use Skills in a Hosted Agent

How to consume Foundry **skills** (reusable behavioral guidelines) from hosted agent code. Two approaches:

1. **Direct download** — agent downloads skill ZIPs at startup via the Skills API, wires `SkillsProvider` (Python) or `AgentSkillsProvider` (C#).
2. **Via Toolbox MCP** — agent connects to a toolbox MCP endpoint that exposes skills as resources, wires `AgentSkillsProviderBuilder.UseMcpSkills` (C#) or `MCPStreamableHTTPTool` (Python).

> 📘 For skill resource CRUD (`azd ai skill create/update/list/download/delete`), see [skill-management.md](skill-management.md).
>
> 📘 For attaching skills to a toolbox (`azd ai toolbox skill add/remove/list`) and the raw MCP protocol, see [skill-toolbox.md](skill-toolbox.md).

## How progressive disclosure works

The Agent Framework SDK injects skill names/descriptions into the system prompt (~100 tokens each) and synthesizes a `load_skill` tool. When the model determines a skill is relevant, it calls `load_skill(name)` to retrieve the full body on demand — keeping context usage low.

## Choosing an approach

| | Direct Download | Via Toolbox MCP |
|--|---|---|
| How | Downloads ZIPs at startup, builds provider from local files | Connects to toolbox MCP; SDK reads `resources/list` → `load_skill` |
| Provider | `SkillsProvider.from_paths()` / `AgentSkillsProvider(dir)` | `MCPStreamableHTTPTool` / `AgentSkillsProviderBuilder.UseMcpSkills()` |
| Skill updates | Redeploy agent | Consumer endpoint picks up new version automatically |
| Header | `Foundry-Features: Skills=V1Preview` | `Foundry-Features: Toolboxes=V1Preview` |
| When to use | No toolbox; need explicit version control | Already have a toolbox; want dynamic updates |

---

## Approach 1: Direct Download

Downloads skill ZIPs at startup, extracts to disk, builds provider. The SDK synthesizes `load_skill` for the model.

### Env vars

| Variable | Purpose |
|----------|---------|
| `FOUNDRY_PROJECT_ENDPOINT` | Project endpoint for SDK calls |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | Model deployment for the agent |
| `SKILL_NAMES` | Comma-separated skill names to download |

### Python

The sample downloads each skill via `project.beta.skills.download()`, extracts the ZIP (with zip-slip guard), and attaches a `SkillsProvider` to the agent as a `context_providers` entry.

**Key classes:** `SkillsProvider.from_paths()`, `AIProjectClient` (with `allow_preview=True`).

Full working sample: [12-foundry-skills (Python)](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/agent-framework/responses/12-foundry-skills)

### C#

The sample uses `AgentAdministrationClient` (with `FoundryFeaturesPolicy` for the `Skills=V1Preview` header) to download skills via `ProjectAgentSkills.DownloadSkillAsync()`, extracts ZIPs, and attaches an `AgentSkillsProvider` via `AIContextProviders`.

**Key classes:** `AgentSkillsProvider`, `ProjectAgentSkills`, `AgentAdministrationClient`.

Full working sample: [agent-skills (C#)](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/csharp/hosted-agents/agent-framework/agent-skills)

---

## Approach 2: Via Toolbox MCP

Skills attached to a toolbox are discovered dynamically via `resources/list` and wrapped into `load_skill`. See [skill-toolbox.md](skill-toolbox.md) for MCP protocol details.

### Env vars

| Variable | Purpose |
|----------|---------|
| `FOUNDRY_PROJECT_ENDPOINT` | Project endpoint for SDK calls |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | Model deployment for the agent |
| `TOOLBOX_ENDPOINT` | Full toolbox MCP endpoint URL (Python preferred) |
| `TOOLBOX_NAME` | Toolbox name — SDK constructs endpoint (C# preferred) |

### C#

The sample creates an `McpClient` pointing at the toolbox endpoint, then builds a skills provider via `AgentSkillsProviderBuilder().UseMcpSkills(mcpClient).Build()`. The framework handles the advertise → load → read lifecycle automatically.

**Key classes:** `AgentSkillsProviderBuilder`, `McpClient`, `BearerTokenHandler`.

Full working sample: [foundry-toolbox-mcp-skills (C#)](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/csharp/hosted-agents/agent-framework/foundry-toolbox-mcp-skills)

---

## Deployment

### Provision skills

Skills must exist in the **same project** the deployed agent connects to:

```bash
azd ai skill create support-style --file ./skills/support-style/ --force
azd ai skill create escalation-policy --file ./skills/escalation-policy/ --force
```

### Direct download approach

```bash
azd env set SKILL_NAMES "support-style,escalation-policy"
```

`agent.yaml`:

```yaml
environment_variables:
  - name: SKILL_NAMES
    value: ${SKILL_NAMES}
```

### Toolbox approach

```bash
# Create toolbox with skills attached
cat > tools.yaml <<'EOF'
description: Agent toolbox with skills and tools
skills:
  - name: support-style
  - name: escalation-policy
tools:
  - type: web_search
    name: web
EOF
azd ai toolbox create agent-tools --from-file tools.yaml

# Wire endpoint env var
ENDPOINT=$(azd ai toolbox show agent-tools -o json | jq -r .endpoint)
azd env set TOOLBOX_ENDPOINT "$ENDPOINT"
```

`agent.yaml`:

```yaml
environment_variables:
  - name: TOOLBOX_ENDPOINT
    value: ${TOOLBOX_ENDPOINT}
```

Then `azd deploy`.

### RBAC

The deployed agent's managed identity needs **Foundry User** on the project:

```bash
az role assignment create \
  --assignee <managed-identity-object-id> \
  --role "Foundry User" \
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>
```

## Verify end-to-end

```bash
azd ai agent run
azd ai agent invoke --local "Hi, can I return my tent within 30 days?"
```

## Samples

| Language | Approach | Sample |
|----------|----------|--------|
| Python | Direct download | [12-foundry-skills](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/agent-framework/responses/12-foundry-skills) |
| Python | Via Toolbox | [04-foundry-toolbox](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/agent-framework/responses/04-foundry-toolbox) |
| C# | Direct download | [agent-skills](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/csharp/hosted-agents/agent-framework/agent-skills) |
| C# | Via Toolbox MCP | [foundry-toolbox-mcp-skills](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/csharp/hosted-agents/agent-framework/foundry-toolbox-mcp-skills) |

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|------------|-----|
| `SKILL.md not found` after download | ZIP doesn't contain `SKILL.md` at root | Create skill from directory with `SKILL.md` at root |
| `403` on skill download | Identity missing RBAC | Grant **Foundry User** on project scope |
| Agent ignores skills | Descriptions don't match user queries | Improve `description` in SKILL.md front matter |
| Skills load but agent doesn't follow | Instructions vague or conflicting | Refine skill body; add canary token to verify loading |
| `asyncio.TimeoutError` (Python) | Slow network or large packages | Increase bootstrap timeout (default 60s) |
| `allow_preview` error (Python) | SDK client missing preview flag | `AIProjectClient(allow_preview=True)` |
| HTTP 500 on skill download (C#) | Missing feature header | Add `FoundryFeaturesPolicy` for `Skills=V1Preview` |
| `SKILL_NAMES` not in deployed agent | Env var missing from `agent.yaml` | Add to `environment_variables[]`, redeploy |
| MCP timeout (Toolbox) | Auth token expired or wrong scope | Use `https://ai.azure.com/.default`; refresh per request |
| Skills not discovered from toolbox | New version not published | `azd ai toolbox publish <toolbox> <version>` |
| `Invalid skill name 'xxx:download'` | SDK bug in beta.2 | Use CLI or `agent-framework-foundry` wrapper |
