# Azure Skills Plugin

Azure work is not just a code problem. It is a decision problem: which service fits this app, what needs to be validated before deployment, which tools should run, and what guardrails matter. The Azure Skills Plugin packages Azure expertise and MCP-backed execution together so compatible coding agents can do real Azure work instead of giving generic cloud advice.

**[Install the plugin](#install-in-60-seconds)**

## One install, three layers of capability

### Azure skills: the brain

This plugin ships **20 curated Azure skills** that teach an agent how Azure work gets done. They provide workflows, decision trees, and guardrails for scenarios such as:

- **Build and deploy** with `azure-prepare`, `azure-validate`, and `azure-deploy`
- **Troubleshoot and operate** with `azure-diagnostics`, `azure-observability`, and `azure-compliance`
- **Optimize and design** with `azure-cost-optimization`, `azure-compute`, and `azure-resource-visualizer`
- **Work across data, AI, and platform services** with `azure-ai`, `azure-aigateway`, `azure-storage`, `azure-kusto`, `azure-rbac`, `azure-cloud-migrate`, `entra-app-registration`, and `microsoft-foundry`

### Azure MCP Server: the hands

The plugin wires in the **Azure MCP Server**, which gives your agent **200+ structured tools across 40+ Azure services**. That is the execution layer for listing resources, checking prices, querying logs, diagnosing issues, and driving real Azure workflows.

### Foundry MCP: the AI specialist

The plugin also includes **Foundry MCP** for Microsoft Foundry scenarios such as model discovery, model deployment, and agent workflows.

## Why this plugin is different

This is not a prompt pack. It is a packaged Azure capability layer:

- **Skills** teach the agent when to use Azure workflows and what to avoid.
- **MCP tools** let the agent act on live Azure and Foundry resources.
- **The plugin** keeps the guidance layer and execution layer aligned in one install.
- **Multi-host support** lets you use the same Azure capability across environments such as GitHub Copilot in VS Code, Copilot CLI, Claude Code, and other compatible hosts.

## What you get

| Component | What it adds | Examples |
| --- | --- | --- |
| **Azure skills** | Azure expertise, workflows, and guardrails | Prepare, validate, deploy, diagnostics, cost, AI, RBAC |
| **Azure MCP Server** | Live Azure tooling | Resource inventory, monitoring, pricing, storage, databases, messaging |
| **Foundry MCP** | Microsoft Foundry workflows | Model catalog, deployments, agents, evaluations |

The plugin payload lives in `.github/plugins/azure-skills/`, and the included MCP configuration shows how Azure and Foundry connectivity are wired for compatible hosts.

## Install in 60 seconds

### Prerequisites

Before you install, make sure you have:

- An Azure account or subscription
- **Node.js 18+** available on your PATH (`npx` is used to start the MCP servers)
- **Azure CLI** installed and authenticated with `az login`
- **Azure Developer CLI** installed and authenticated with `azd auth login` if you plan to use deployment workflows

### GitHub Copilot CLI

**Install the plugin**:

```
/plugin install azure@awesome-copilot
```

**Update the plugin**:

```
/plugin update azure@awesome-copilot
```

### VS Code

Install the **Azure MCP** extension from the Visual Studio Marketplace:

👉 [Azure MCP Extension](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-azure-mcp-server)

The Azure MCP extension will also install a companion extension that brings the Azure skills into VS Code. Together they configure the Azure MCP Server, Foundry MCP, and the full skills layer automatically.

### Claude Code

**Add the marketplace** (first time only):

```bash
claude plugin marketplace add microsoft/azure-skills
```

**Install the plugin**:

```bash
claude plugin install azure@azure-skills
```

**Update the plugin**:

```bash
claude plugin update azure
```

### What the install should add

A successful install gives you:

- The Azure skills under `.github/plugins/azure-skills/`
- MCP configuration for the Azure MCP Server and Foundry MCP
- A ready-to-use Azure workflow layer in your agent

## Verify the installation

After install, try three quick checks.

### 1. Verify the skills layer

Ask:

> What Azure services would I need to deploy this project?

You should get structured Azure guidance, not just a generic cloud answer.

### 2. Verify Azure MCP

Ask:

> List my Azure resource groups.

You should see a real tool-backed response from your Azure account.

### 3. Verify Foundry MCP

Ask:

> What AI models are available in Microsoft Foundry?

You should get a Foundry-backed response rather than a generic summary.

## Authentication

The recommended authentication path is Azure CLI:

```bash
az login
```

If you plan to deploy with `azd`, also run:

```bash
azd auth login
```

You can also authenticate with service principal credentials:

**Bash/Zsh**

```bash
export AZURE_TENANT_ID="your-tenant-id"
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-client-secret"
```

**PowerShell**

```powershell
$env:AZURE_TENANT_ID = "your-tenant-id"
$env:AZURE_CLIENT_ID = "your-client-id"
$env:AZURE_CLIENT_SECRET = "your-client-secret"
```

When the agent runs inside Azure, the Azure MCP Server can also use managed identity.

## Prompts to try

Once the plugin is installed, try prompts like these:

- `Prepare this app for Azure.`
- `Validate my Azure deployment files before I run azd up.`
- `Deploy this project to Azure Container Apps.`
- `List my Azure storage accounts.`
- `Find cost savings across my Azure subscription.`
- `Troubleshoot why my container app is failing health probes.`
- `What role should I assign to let this managed identity read blobs?`
- `What AI models are available in Microsoft Foundry?`

## Repository layout

If you are exploring or customizing the plugin source, the key pieces are:

- `.github/plugins/azure-skills/skills/` - the Azure skill definitions
- `.github/plugins/azure-skills/.mcp.json` - included MCP configuration for Azure and Foundry
- `README.md` - high-level overview and install guide for the plugin

## Troubleshooting

### The agent is not using Azure skills

- Make sure the plugin installed successfully in your host
- Confirm the Azure skills directory is present
- Reload or restart your host so it re-indexes plugins and MCP configuration

### MCP tools are not showing up

- Verify Node.js is installed and `npx` works
- Check that the Azure and Foundry MCP entries were added for your host
- Restart MCP servers or reload the host after configuration changes

### Azure commands fail with auth errors

- Re-run `az login`
- Re-run `azd auth login` for deployment scenarios
- Make sure the correct Azure subscription is selected

## Learn more

- [Azure MCP Server documentation](https://learn.microsoft.com/azure/developer/azure-mcp-server/)
- [Azure documentation](https://learn.microsoft.com/azure)
- [Azure CLI reference](https://learn.microsoft.com/cli/azure/)

## Telemetry

To disable Azure MCP telemetry collection, set:

```bash
export AZURE_MCP_COLLECT_TELEMETRY=false
```
