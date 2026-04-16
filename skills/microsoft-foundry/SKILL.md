---
name: microsoft-foundry
description: "Deploy, evaluate, and manage Foundry agents end-to-end: Docker build, ACR push, hosted/prompt agent create, container start, batch eval, prompt optimization, prompt optimizer workflows, agent.yaml, dataset curation from traces. USE FOR: deploy agent to Foundry, hosted agent, create agent, invoke agent, evaluate agent, run batch eval, optimize prompt, improve prompt, prompt optimization, prompt optimizer, improve agent instructions, optimize agent instructions, optimize system prompt, deploy model, Foundry project, RBAC, role assignment, permissions, quota, capacity, region, troubleshoot agent, deployment failure, create dataset from traces, dataset versioning, eval trending, create AI Services, Cognitive Services, create Foundry resource, provision resource, knowledge index, agent monitoring, customize deployment, onboard, availability. DO NOT USE FOR: Azure Functions, App Service, general Azure deploy (use azure-deploy), general Azure prep (use azure-prepare)."
license: MIT
metadata:
  author: Microsoft
  version: "1.0.11"
---

# Microsoft Foundry Skill

This skill helps developers work with Microsoft Foundry resources, covering model discovery and deployment, complete dev lifecycle of AI agent, evaluation workflows, and troubleshooting.

## Sub-Skills

> **MANDATORY: Before executing ANY workflow, you MUST read the corresponding sub-skill document.** Do not call MCP tools for a workflow without reading its skill document. This applies even if you already know the MCP tool parameters — the skill document contains required workflow steps, pre-checks, and validation logic that must be followed. This rule applies on every new user message that triggers a different workflow, even if the skill is already loaded.

This skill includes specialized sub-skills for specific workflows. **Use these instead of the main skill when they match your task:**

| Sub-Skill | When to Use | Reference |
|-----------|-------------|-----------|
| **deploy** | Containerize, build, push to ACR, create/update/start/stop/clone agent deployments | [deploy](foundry-agent/deploy/deploy.md) |
| **invoke** | Send messages to an agent, single or multi-turn conversations | [invoke](foundry-agent/invoke/invoke.md) |
| **observe** | Evaluate agent quality, run batch evals, analyze failures, optimize prompts, improve agent instructions, compare versions, and set up CI/CD monitoring | [observe](foundry-agent/observe/observe.md) |
| **trace** | Query traces, analyze latency/failures, correlate eval results to specific responses via App Insights `customEvents` | [trace](foundry-agent/trace/trace.md) |
| **troubleshoot** | View container logs, query telemetry, diagnose failures | [troubleshoot](foundry-agent/troubleshoot/troubleshoot.md) |
| **create** | Create new hosted agent applications. Supports Microsoft Agent Framework, LangGraph, or custom frameworks in Python or C#. Downloads starter samples from foundry-samples repo. | [create](foundry-agent/create/create.md) |
| **eval-datasets** | Harvest production traces into evaluation datasets, manage dataset versions and splits, track evaluation metrics over time, detect regressions, and maintain full lineage from trace to deployment. Use for: create dataset from traces, dataset versioning, evaluation trending, regression detection, dataset comparison, eval lineage. | [eval-datasets](foundry-agent/eval-datasets/eval-datasets.md) |
| **project/create** | Creating a new Azure AI Foundry project for hosting agents and models. Use when onboarding to Foundry or setting up new infrastructure. | [project/create/create-foundry-project.md](project/create/create-foundry-project.md) |
| **resource/create** | Creating Azure AI Services multi-service resource (Foundry resource) using Azure CLI. Use when manually provisioning AI Services resources with granular control. | [resource/create/create-foundry-resource.md](resource/create/create-foundry-resource.md) |
| **models/deploy-model** | Unified model deployment with intelligent routing. Handles quick preset deployments, fully customized deployments (version/SKU/capacity/RAI), and capacity discovery across regions. Routes to sub-skills: `preset` (quick deploy), `customize` (full control), `capacity` (find availability). | [models/deploy-model/SKILL.md](models/deploy-model/SKILL.md) |
| **quota** | Managing quotas and capacity for Microsoft Foundry resources. Use when checking quota usage, troubleshooting deployment failures due to insufficient quota, requesting quota increases, or planning capacity. | [quota/quota.md](quota/quota.md) |
| **rbac** | Managing RBAC permissions, role assignments, managed identities, and service principals for Microsoft Foundry resources. Use for access control, auditing permissions, and CI/CD setup. | [rbac/rbac.md](rbac/rbac.md) |

> 💡 **Tip:** For a complete onboarding flow: `project/create` → agent workflows (`deploy` → `invoke`).

> 💡 **Model Deployment:** Use `models/deploy-model` for all deployment scenarios — it intelligently routes between quick preset deployment, customized deployment with full control, and capacity discovery across regions.

> 💡 **Prompt Optimization:** For requests like "optimize my prompt" or "improve my agent instructions," load [observe](foundry-agent/observe/observe.md) and use the `prompt_optimize` MCP tool through that eval-driven workflow.

## Agent Development Lifecycle

Match user intent to the correct workflow. Read each sub-skill in order before executing.

| User Intent | Workflow (read in order) |
|-------------|------------------------|
| Create a new agent from scratch | [create](foundry-agent/create/create.md) → [deploy](foundry-agent/deploy/deploy.md) → [invoke](foundry-agent/invoke/invoke.md) |
| Deploy an agent (code already exists) | deploy → invoke |
| Update/redeploy an agent after code changes | deploy → invoke |
| Invoke/test/chat with an agent | invoke |
| Optimize / improve agent prompt or instructions | observe (Step 4: Optimize) |
| Evaluate and optimize agent (full loop) | observe |
| Troubleshoot an agent issue | invoke → troubleshoot |
| Fix a broken agent (troubleshoot + redeploy) | invoke → troubleshoot → apply fixes → deploy → invoke |
| Start/stop agent container | deploy |

## Agent: .foundry Workspace Standard

Every agent source folder should keep Foundry-specific state under `.foundry/`:

```text
<agent-root>/
  .foundry/
    agent-metadata.yaml
    datasets/
    evaluators/
    results/
```

- `agent-metadata.yaml` is the required source of truth for environment-specific project settings, agent names, registry details, and evaluation test cases.
- `datasets/` and `evaluators/` are local cache folders. Reuse them when they are current, and ask before refreshing or overwriting them.
- See [Agent Metadata Contract](references/agent-metadata-contract.md) for the canonical schema and workflow rules.

## Agent: Setup References

- [Standard Agent Setup](references/standard-agent-setup.md) - Standard capability-host setup with customer-managed data, search, and AI Services resources.
- [Private Network Standard Agent Setup](references/private-network-standard-agent-setup.md) - Standard setup with VNet isolation and private endpoints.

## Agent: Project Context Resolution

Agent skills should run this step **only when they need configuration values they don't already have**. If a value (for example, agent root, environment, project endpoint, or agent name) is already known from the user's message or a previous skill in the same session, skip resolution for that value.

### Step 1: Discover Agent Roots

Search the workspace for `.foundry/agent-metadata.yaml`.

- **One match** → use that agent root.
- **Multiple matches** → require the user to choose the target agent folder.
- **No matches** → for create/deploy workflows, seed a new `.foundry/` folder during setup; for all other workflows, stop and ask the user which agent source folder to initialize.

### Step 2: Resolve Environment

Read `.foundry/agent-metadata.yaml` and resolve the environment in this order:
1. Environment explicitly named by the user
2. Environment already selected earlier in the session
3. `defaultEnvironment` from metadata

If the metadata contains multiple environments and none of the rules above selects one, prompt the user to choose. Keep the selected agent root and environment visible in every workflow summary.

### Step 3: Resolve Common Configuration

Use the selected environment in `agent-metadata.yaml` as the primary source:

| Metadata Field | Resolves To | Used By |
|----------------|-------------|---------|
| `environments.<env>.projectEndpoint` | Project endpoint | deploy, invoke, observe, trace, troubleshoot |
| `environments.<env>.agentName` | Agent name | invoke, observe, trace, troubleshoot |
| `environments.<env>.azureContainerRegistry` | ACR registry name / image URL prefix | deploy |
| `environments.<env>.testCases[]` | Dataset + evaluator + threshold bundles | observe, eval-datasets |

### Step 4: Bootstrap Missing Metadata (Create/Deploy Only)

If create/deploy is initializing a new `.foundry` workspace and metadata fields are still missing, check if `azure.yaml` exists in the project root. If found, run `azd env get-values` and use it to seed `agent-metadata.yaml` before continuing.

| azd Variable | Seeds |
|-------------|-------|
| `AZURE_AI_PROJECT_ENDPOINT` or `AZURE_AIPROJECT_ENDPOINT` | `environments.<env>.projectEndpoint` |
| `AZURE_CONTAINER_REGISTRY_NAME` or `AZURE_CONTAINER_REGISTRY_ENDPOINT` | `environments.<env>.azureContainerRegistry` |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription for trace/troubleshoot lookups |

### Step 5: Collect Missing Values

Use the `ask_user` or `askQuestions` tool **only for values not resolved** from the user's message, session context, metadata, or azd bootstrap. Common values skills may need:
- **Agent root** — Target folder containing `.foundry/agent-metadata.yaml`
- **Environment** — `dev`, `prod`, or another environment key from metadata
- **Project endpoint** — AI Foundry project endpoint URL
- **Agent name** — Name of the target agent

> 💡 **Tip:** If the user already provides the agent path, environment, project endpoint, or agent name, extract it directly — do not ask again.

## Agent: Agent Types

All agent skills support two agent types:

| Type | Kind | Description |
|------|------|-------------|
| **Prompt** | `"prompt"` | LLM-based agents backed by a model deployment |
| **Hosted** | `"hosted"` | Container-based agents running custom code |

Use `agent_get` MCP tool to determine an agent's type when needed.

## Tool Usage Conventions

- Use the `ask_user` or `askQuestions` tool whenever collecting information from the user
- Use the `task` or `runSubagent` tool to delegate long-running or independent sub-tasks (e.g., env var scanning, status polling, Dockerfile generation)
- Prefer Azure MCP tools over direct CLI commands when available
- Reference official Microsoft documentation URLs instead of embedding CLI command syntax

## Additional Resources

- [Foundry Hosted Agents](https://learn.microsoft.com/azure/ai-foundry/agents/concepts/hosted-agents?view=foundry)
- [Foundry Agent Runtime Components](https://learn.microsoft.com/azure/ai-foundry/agents/concepts/runtime-components?view=foundry)
- [Foundry Samples](https://github.com/azure-ai-foundry/foundry-samples)

## SDK Quick Reference

- [Python](references/sdk/foundry-sdk-py.md)
