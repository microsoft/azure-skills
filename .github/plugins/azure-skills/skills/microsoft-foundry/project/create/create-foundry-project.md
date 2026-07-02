---
name: foundry-create-project
description: |
  Create a new Azure AI Foundry project using Azure Developer CLI (azd) to provision infrastructure for hosting AI agents and models.
  USE FOR: create Foundry project, new AI Foundry project, set up Foundry, azd init Foundry, provision Foundry infrastructure, onboard to Foundry, create Azure AI project, set up AI project.
  DO NOT USE FOR: deploying agents to existing projects (use agent/deploy), creating agent code (use agent/create), deploying AI models from catalog (use microsoft-foundry main skill), Azure Functions (use azure-functions).
allowed-tools: Read, Write, Bash, AskUserQuestion
---

# Create Azure AI Foundry Project

Create a new Azure AI Foundry project using azd. Provisions: Foundry account, project, Application Insights, managed identity, and RBAC permissions. Optionally enables hosted-agent deployment (adds an Azure Container Registry, and — only when the **Standard Setup** capability-host flag is also enabled — a `capabilityHosts/agents` resource).

**Table of Contents:** [Prerequisites](#prerequisites) · [Workflow](#workflow) · [Best Practices](#best-practices) · [Troubleshooting](#troubleshooting) · [Related Skills](#related-skills) · [Resources](#resources)

## Prerequisites

Run checks in order. STOP on any failure and resolve before proceeding.

**1. Azure CLI** — `az version` → expects version output. If missing: https://aka.ms/installazurecli

**2. Azure login & subscription:**

```bash
az account show --query "{Name:name, SubscriptionId:id, State:state}" -o table
```

If not logged in, run `az login`. If no active subscription: https://azure.microsoft.com/free/ — STOP.

If multiple subscriptions, ask which to use, then `az account set --subscription "<id>"`.

**3. Role permissions:**

```bash
az role assignment list --assignee "$(az ad signed-in-user show --query id -o tsv)" --query "[?contains(roleDefinitionName, 'Owner') || contains(roleDefinitionName, 'Contributor') || contains(roleDefinitionName, 'Foundry')].{Role:roleDefinitionName, Scope:scope}" -o table
```

Requires Owner, Contributor, or Foundry Owner. If insufficient — STOP, request elevated access from admin.

**4. Azure Developer CLI** — `azd version`. If missing: https://aka.ms/azure-dev/install

## Workflow

### Step 1: Verify azd login

```bash
azd auth login --check-status
```

If not logged in, run `azd auth login` and complete browser auth.

### Step 2: Resolve Project Details

Collect only values the user has not already provided. For values not specified, use defaults:

1. **Project name** — used as azd environment name and resource group (`rg-<name>`). Must contain only alphanumeric characters and hyphens.
   - If the user provided a name, use it as-is.
   - If the user did NOT provide a name, **auto-generate a unique name** using the pattern `ai-project-<random>` where `<random>` is a short random suffix (6-8 lowercase alphanumeric characters). Generate the suffix with a platform-appropriate method:
     ```bash
     # bash/zsh
     echo "ai-project-$(openssl rand -hex 4)"
     ```
     ```powershell
     # PowerShell
     "ai-project-$(-join ((48..57)+(97..122) | Get-Random -Count 8 | ForEach-Object {[char]$_}))"
     ```
   - Show the generated name to the user before proceeding, but do not block on confirmation — proceed unless the user objects.
   - Examples: `ai-project-3f8a1b2c`, `my-ai-project`, `dev-agents`
2. **Azure location** (optional) — defaults to North Central US (required for hosted agents preview)
3. **Enable hosted agents?** (yes/no) — enables hosted-agent deployment and provisions an Azure Container Registry. A capability host (`capabilityHosts/agents`, used by Foundry's **Standard Agent Setup** for bring-your-own storage) is also created only when `ENABLE_CAPABILITY_HOST=true`. Defaults to no. See [Step 3](#step-3-create-directory-and-initialize) for how the two flags interact.

### Step 3: Create Directory and Initialize

```bash
mkdir "<project-name>" && cd "<project-name>"
azd init -t https://github.com/Azure-Samples/azd-ai-starter-basic -e <project-name> --no-prompt
```

- `-t` — Azure AI starter template (Foundry infrastructure)
- `-e` — environment name
- `--no-prompt` — non-interactive, use defaults
- **IMPORTANT:** `azd init` requires an empty directory

If user specified a non-default location:

```bash
azd config set defaults.location <location>
```

If user chose to enable hosted agents:

```bash
azd env set ENABLE_HOSTED_AGENTS true
azd env set ENABLE_CAPABILITY_HOST false
```

`ENABLE_HOSTED_AGENTS=true` enables hosted-agent deployment and creates an Azure Container Registry for the container image. A capability host (`capabilityHosts/agents`, used by Foundry's **Standard Agent Setup** for bring-your-own storage) is **also** created only when `ENABLE_CAPABILITY_HOST=true`. The default `azd ai agent` flow targets **Basic Agent Setup**, so it sets `ENABLE_CAPABILITY_HOST=false` automatically. The two flags are independent.

> ⚠️ **Warning:** The Bicep template parameter `enableCapabilityHost` defaults to `true`. If you set `ENABLE_HOSTED_AGENTS` by hand without also setting `ENABLE_CAPABILITY_HOST=false`, you will accidentally provision Standard Setup (with the capability host). Use `azd ai agent init` to set both flags correctly.

See the canonical env-var docs: [azure-dev/cli/azd/docs/environment-variables.md](https://github.com/Azure/azure-dev/blob/main/cli/azd/docs/environment-variables.md).

### Step 4: Provision Infrastructure

```bash
azd provision --no-prompt
```

Takes 5–10 minutes. Creates resource group, Foundry account/project, Application Insights, managed identity, and RBAC roles. If `ENABLE_HOSTED_AGENTS=true`, also creates an Azure Container Registry. A `capabilityHosts/agents` resource is created **only** when `ENABLE_CAPABILITY_HOST=true` (Standard Setup); the default Basic Setup uses `ENABLE_CAPABILITY_HOST=false` and no capability host is provisioned — its absence is correct.

### Step 5: Retrieve Project Details

```bash
azd env get-values
```

Capture `AZURE_AI_PROJECT_ID`, `AZURE_AI_PROJECT_ENDPOINT`, and `AZURE_RESOURCE_GROUP`. Direct user to verify at https://ai.azure.com.

### Step 6: Next Steps

> **Next — azd Golden Path:** create a hosted agent with [foundry-agent/create/create-hosted.md](../../foundry-agent/create/create-hosted.md). For headless / scripted flows, **pre-bootstrap the workspace with core `azd init`** so subscription + location are populated before model resolution runs:
>
> ```bash
> azd init -t Azure-Samples/azd-ai-starter-basic . -e <env-name> --subscription <id> -l <region>
> azd ai agent init -m <manifest-url> --no-prompt --deploy-mode code --runtime python_3_13 --entry-point main.py
> ```
>
> Core `azd init` accepts `--subscription` and `-l/--location`; `azd ai agent init` does not. `azd ai agent init` then resolves the model from the chosen sample's manifest and writes it into `azure.yaml services.ai-project.deployments[]`; the next `azd provision` creates the deployment through Bicep. **You do not need to deploy a model separately for this path** — no `az cognitiveservices` calls, no `azd env set AI_PROJECT_DEPLOYMENTS`.
>
> Use [models/deploy-model](../../models/deploy-model/SKILL.md) **only** for out-of-band scenarios: adding models to a Foundry project that is not managed by this azd project, or ad-hoc deployments outside the azd lifecycle.

- Deploy an existing agent → [foundry-agent/deploy/deploy.md](../../foundry-agent/deploy/deploy.md)
- Browse model catalog → `foundry_models_list` MCP tool
- Manage project → https://ai.azure.com

## Best Practices

- Use North Central US for hosted agents (preview requirement)
- Name must be alphanumeric + hyphens only — no spaces, underscores, or special characters
- Delete unused projects with `azd down` to avoid ongoing costs
- `azd down` deletes ALL resources — Foundry account, agents, models, Container Registry, and Application Insights data
- `azd provision` is safe to re-run on failure

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `azd: command not found` | Install from https://aka.ms/azure-dev/install |
| `ERROR: Failed to authenticate` | Run `azd auth login`; verify subscription with `az account list` |
| `environment name '' is invalid` | Name must be alphanumeric + hyphens only |
| `ERROR: Insufficient permissions` | Request Contributor or Foundry Owner role from admin |
| Region not supported for hosted agents | Use `azd config set defaults.location northcentralus` |
| Provisioning timeout | Check region availability, verify connectivity, retry `azd provision` |

## Related Skills

- **agent/deploy** — Deploy agents to the created project
- **agent/create** — Create a new agent for deployment

## Resources

- [Azure Developer CLI](https://aka.ms/azure-dev/install) · [AI Foundry Portal](https://ai.azure.com) · [Foundry Docs](https://learn.microsoft.com/azure/ai-foundry/) · [azd-ai-starter-basic template](https://github.com/Azure-Samples/azd-ai-starter-basic)
