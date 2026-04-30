# Foundry Agent Deploy

Create and manage agent deployments in Azure AI Foundry. For hosted agents, this includes the full workflow from containerizing the project to verifying the deployed agent.

## Quick Reference

| Property | Value |
|----------|-------|
| Agent types | Prompt (LLM-based), Hosted |
| MCP server | `azure` |
| Key Foundry MCP tools | `agent_definition_schema_get`, `agent_update`, `agent_get` |
| CLI tools | `docker`, `az acr` (hosted agents only) |
| Container protocols | `a2a`, `responses`, `invocations`, `mcp` |
| Supported languages | .NET, Node.js, Python, Go, Java |

## When to Use This Skill

USE FOR: deploy agent to foundry, push agent to foundry, ship my agent, build and deploy container agent, deploy hosted agent, create hosted agent, deploy prompt agent, ACR build, container image for agent, docker build for foundry, redeploy agent, update agent deployment, clone agent, delete agent, azd deploy hosted agent, azd ai agent, azd up for agent, deploy agent with azd.

> ⚠️ **DO NOT manually run** `azd up`, `azd deploy`, `az acr build`, `docker build`, or `agent_update` **without reading this skill first.** This skill orchestrates the full deployment pipeline: project scan → env var collection → Dockerfile generation → image build → agent creation → verification. Running CLI commands or calling MCP tools individually skips critical steps (env var confirmation, schema validation, RBAC setup, invocation verification).

## MCP Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `agent_definition_schema_get` | Get JSON schema for agent definitions | `projectEndpoint` (required), `schemaType` (`prompt`, `hosted`, `tools`, `all`) |
| `agent_update` | Create, update, or clone an agent | `projectEndpoint`, `agentName` (required); `agentDefinition` (JSON), `isCloneRequest`, `cloneTargetAgentName`, `modelName` |
| `agent_get` | List all agents or get a specific agent | `projectEndpoint` (required), `agentName` (optional) |
| `agent_delete` | Delete an agent and clean up hosted-agent runtime resources | `projectEndpoint`, `agentName` (required) |

## Workflow: Hosted Agent Deployment


### Step 1: Detect and Scan Project

Get the project path from the selected agent root in the project context (see Common: Project Context Resolution). Detect the project type by checking for these files. Do **not** scan sibling agent folders.

| Project Type | Detection Files |
|--------------|-----------------|
| .NET | `*.csproj`, `*.fsproj` |
| Node.js | `package.json` |
| Python | `requirements.txt`, `pyproject.toml`, `setup.py` |
| Go | `go.mod` |
| Java (Maven) | `pom.xml` |
| Java (Gradle) | `build.gradle` |

Delegate an environment variable scan to a sub-agent. Provide the selected agent root path and project type. Search source files inside that folder only for these patterns:

| Project Type | Patterns to Search |
|--------------|--------------------|
| .NET (`*.cs`) | `Environment.GetEnvironmentVariable("...")`, `configuration["..."]`, `configuration.GetValue<T>("...")` |
| Node.js (`*.js`, `*.ts`, `*.mjs`) | `process.env.VAR_NAME`, `process.env["..."]` |
| Python (`*.py`) | `os.environ["..."]`, `os.environ.get("...")`, `os.getenv("...")` |
| Go (`*.go`) | `os.Getenv("...")`, `os.LookupEnv("...")` |
| Java (`*.java`) | `System.getenv("...")`, `@Value("${...}")` |

Classification: if followed by a throw/error → required; if followed by a fallback value → optional with default; otherwise → assume required, ask user.

### Step 2: Collect and Confirm Environment Variables

> ⚠️ **Warning:** Environment variables are included in the agent payload and are difficult to change after deployment.

Use azd environment values from the project context to pre-fill discovered variables. Merge with any user-provided values. Present all variables to the user for confirmation with variable name, value, and source (`azd`, `project default`, or `user`). Mask sensitive values.

Loop until the user confirms or cancels:
- `yes` → Proceed
- `VAR_NAME=new_value` → Update the value, show updated table, ask again
- `cancel` → Abort deployment

### Step 3: Generate Dockerfile and Build Image

Delegate Dockerfile creation to a sub-agent. Guidelines:
- Use official base image for the detected language and runtime version
- Use multi-stage builds for compiled languages
- Use Alpine or slim variants for smaller images
- Always target `linux/amd64` platform
- Expose the correct port (usually 8088)

> 💡 **Tip:** Reference [Hosted Agents Foundry Samples](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents) for containerized agent examples.

Also generate `docker-compose.yml` and `.env` files for local development.

**IMPORTANT**: You MUST always generate image tag as current timestamp (e.g., `myagent:202401011230`) to ensure uniqueness and avoid conflicts with existing images in ACR. DO NOT use static tags like `latest` or `v1`.

Collect ACR details from project context.

- If an ACR already exists, use it, then verify that the Foundry project managed identity has pull permissions (for example, `Container Registry Repository Reader` or equivalent) on the target repository/registry. If the role assignment is missing, add it.
- If no ACR exists, create a new one with ABAC repository permissions mode, and assign `Container Registry Repository Reader` to the Foundry project managed identity. Foundry hosted agents use ABAC mode that requires repository-scoped roles, not the registry-level `AcrPull` role.

Let the user choose the build method:

**Cloud Build (ACR Tasks) (Recommended)** — no local Docker required:
```bash
az acr build --registry <acr-name> --image <repository>:<tag> --platform linux/amd64 --source-acr-auth-id "[caller]" --file Dockerfile .
```

> ⚠️ **Mandatory:** The `--source-acr-auth-id "[caller]"` parameter is required. Do NOT omit it — without this flag the build will fail due to missing authentication context.

**Local Docker Build:**
```bash
docker build --platform linux/amd64 -t <image>:<tag> -f Dockerfile .
az acr login --name <acr-name>
docker tag <image>:<tag> <acr-name>.azurecr.io/<repository>:<tag>
docker push <acr-name>.azurecr.io/<repository>:<tag>
```

> 💡 **Tip:** Prefer Cloud Build if Docker is not available locally. On Windows with WSL, prefix Docker commands with `wsl -e` if `docker info` fails but `wsl -e docker info` succeeds.

### Step 4: Collect Agent Configuration

Use the project endpoint and ACR name from the project context. Ask the user only for values not already resolved:
- **Agent name** — Unique name for the agent
- **Model deployment** — Model deployment name (e.g., `gpt-4o`)

### Step 5: Get Agent Definition Schema

Use `agent_definition_schema_get` with `schemaType: hosted` to retrieve the current schema and validate required fields.

### Step 6: Create the Agent

Use `agent_update` with the agent definition:

> ⚠️ **Protocol version source of truth:** Do NOT copy the protocol version from `agent_definition_schema_get` examples. Use the protocol version declared by the agent source itself (for example, `agent.yaml` or `agent.manifest.yaml`).

```json
{
  "command": "agent_update",
  "intent": "Update a hosted agent with a new docker image",
  "parameters": {
    "projectEndpoint": "<project-endpoint>",
    "agentName": "<agent-name>",
    "agentDefinition": {
      "kind": "hosted",
      "image": "<acr-name>.azurecr.io/<repository>:<tag>",
      "cpu": "<cpu-cores>",
      "memory": "<memory>",
      "container_protocol_versions": [
        { "protocol": "<protocol>", "version": "<version>" }
      ],
      "environment_variables": { "<var>": "<value>" }
    }
  }
}
```

Capture the per-agent identity from the agent creation response, then retrieve the project-level agent identity from the project resource after creation. You will need both identities to assign the minimum RBAC required for invocation before running invoke tests.

### Step 7: Test the Agent

For a newly deployed hosted agent, before invocation testing, first check whether the per-agent identity and project-level agent identity already have the minimum RBAC required for invocation.

Required role assignment:
- `Azure AI User`

Required scope: the Cognitive Services account, not the project.

Check existing assignments before creating any new assignment. If the required role assignment is missing for either identity, assign it before invocation testing.

If the current user account does not have permission to create a missing role assignment, stop the deployment workflow here. Explain to the user that hosted-agent invocation requires `Azure AI User` on the per-agent identity and project-level agent identity at the Cognitive Services account scope, and the deployment cannot be treated as complete until someone with RBAC assignment permission grants the missing role.

After this RBAC check is complete, read and follow the [invoke skill](../invoke/invoke.md) to send a test message and verify the agent responds correctly. DO NOT SKIP reading the invoke skill — it contains important information about required hosted-agent session handling.

If invocation testing still fails after this RBAC check, immediately read and follow the [troubleshoot skill](../troubleshoot/troubleshoot.md). Do not treat the deployment as fully successful until invocation succeeds.

> ⚠️ **DO NOT stop here.** Continue to Step 8 (Auto-Create Evaluators & Dataset). This step is mandatory after every successful deployment.

### Step 8: Auto-Create Evaluators & Dataset

Follow [After Deployment — Auto-Create Evaluators & Dataset](#after-deployment--auto-create-evaluators--dataset) below.

## Workflow: Prompt Agent Deployment

### Step 1: Collect Agent Configuration

Use the project endpoint from the project context (see Common: Project Context Resolution). Ask the user only for values not already resolved:
- **Agent name** — Unique name for the agent
- **Model deployment** — Model deployment name (e.g., `gpt-4o`)
- **Instructions** — System prompt (optional)
- **Temperature** — Response randomness 0-2 (optional, default varies by model)
- **Tools** — Tool configurations (optional)

### Step 2: Get Agent Definition Schema

Use `agent_definition_schema_get` with `schemaType: prompt` to retrieve the current schema.

### Step 3: Create the Agent

Use `agent_update` with the agent definition:

```json
{
  "kind": "prompt",
  "model": "<model-deployment>",
  "instructions": "<system-prompt>",
  "temperature": 0.7
}
```

### Step 4: Test the Agent

Read and follow the [invoke skill](../invoke/invoke.md) to send a test message and verify the agent responds correctly.

> ⚠️ **DO NOT stop here.** Continue to Step 5 (Auto-Create Evaluators & Dataset). This step is mandatory after every successful deployment.

### Step 5: Auto-Create Evaluators & Dataset

Follow [After Deployment — Auto-Create Evaluators & Dataset](#after-deployment--auto-create-evaluators--dataset) below.

## Display Agent Information
Once deployment is done for either hosted or prompt agent, display the agent's details in a nicely formatted table.

Below the table you MUST also display a Playground link for direct access to the agent in Azure AI Foundry:

[Open in Playground](https://ai.azure.com/nextgen/r/{encodedSubId},{resourceGroup},,{accountName},{projectName}/build/agents/{agentName}/build?version={agentVersion})

To calculate the encodedSubId, you need to take subscription id and convert it into its 16-byte GUID, then encode it as URL-safe base64 without padding (= characters trimmed). You can use the following Python code to do this conversion:

```
python -c "import base64,uuid;print(base64.urlsafe_b64encode(uuid.UUID('<SUBSCRIPTION_ID>').bytes).rstrip(b'=').decode())"
```

## Document Deployment Context

After a successful deployment, persist the deployment context to the selected metadata file under `<agent-root>/.foundry/` so future conversations (evaluation, trace analysis, monitoring) can reuse it automatically. Local/dev flows should default to `agent-metadata.yaml`; prod or CI-targeted flows can point at `agent-metadata.prod.yaml` or another explicit sidecar file. See [Agent Metadata Contract](../../references/agent-metadata-contract.md) for the canonical schema.

| Metadata Field | Purpose | Example |
|----------------|---------|---------|
| `environments.<env>.projectEndpoint` | Foundry project endpoint | `https://<account>.services.ai.azure.com/api/projects/<project>` |
| `environments.<env>.agentName` | Deployed agent name | `my-support-agent` |
| `environments.<env>.azureContainerRegistry` | ACR resource (hosted agents) | `myregistry.azurecr.io` |
| `environments.<env>.evaluationSuites[]` | Evaluation bundles for datasets, evaluators, tags, and thresholds | `smoke-core`, `trace-regression-suite` |
| `environments.<env>.evaluationSuites[].datasetUri` | Remote Foundry dataset URI for shared eval workflows | `azureml://datastores/.../paths/...` |

If the selected metadata file is a preferred single-environment file, update only that one environment block and leave sibling metadata files untouched. If the selected metadata file is a legacy multi-environment file, merge the selected environment instead of overwriting other environments or cached evaluation suites without confirmation. If the selected environment still uses older `testSuites[]` or legacy `testCases[]`, rewrite that environment to `evaluationSuites[]` when you persist deployment metadata.

## After Deployment — Auto-Create Evaluators & Dataset

> ⚠️ **This step is automatic.** After a successful deployment, immediately prepare the selected `.foundry` environment for evaluation without waiting for the user to request it. This matches the eval-driven optimization loop.

### 1. Read Agent Instructions

Use **`agent_get`** (or local `agent.yaml`) to understand the agent's purpose and capabilities.

### 2. Reuse or Refresh Local Cache

Inspect the selected agent root before generating anything new:

- Reuse `.foundry/evaluators/` and `.foundry/datasets/` when they already contain the right assets for the selected environment.
- Ask before refreshing cached files or replacing thresholds.
- If cache is missing or stale, regenerate the dataset/evaluators and update metadata for the active environment only.

### 2.5 Discover Existing Evaluators

Use **`evaluator_catalog_get`** with the selected environment's project endpoint to list all evaluators already registered in the project. Display them to the user grouped by type (`custom` vs `built-in`) with name, category, and version. During Phase 1, catalog any promising custom evaluators for later reuse, but keep the first run on the built-in baseline. Only propose creating a new evaluator in Phase 2 when no existing evaluator covers the required dimension.

### 3. Select Default Evaluators

Follow the [observe skill's Two-Phase Evaluator Strategy](../observe/observe.md). Phase 1 is built-in only, so do not create a new custom evaluator during the initial setup pass.

Start with <=5 built-in evaluators for the initial eval run so the first pass stays fast:

| Category | Evaluators |
|----------|-----------|
| **Quality (built-in)** | relevance, task_adherence, intent_resolution |
| **Safety (built-in)** | indirect_attack |
| **Tool use (built-in, conditional)** | tool_call_accuracy (use when the agent calls tools; some catalogs label it as `builtin.tool_call_accuracy`) |

After analyzing initial results, suggest additional evaluators (custom or built-in) targeted at specific failure patterns instead of front-loading a larger default set.

If Phase 2 is needed, call `evaluator_catalog_get` again to reuse an existing custom evaluator first. Only create a new custom evaluator when the catalog still lacks the required signal, and prefer prompt templates that consume `expected_behavior` for per-query behavioral scoring.

### 4. Identify LLM-Judge Deployment

Use **`model_deployment_get`** to list the selected project's actual model deployments, then choose one that supports chat completions for quality evaluators. Do **not** assume `gpt-4o` exists in the project. If no deployment supports chat completions, stop the auto-setup flow and tell the user quality evaluators cannot run until a compatible judge deployment is available.

### 5. Generate Seed Dataset

> ⚠️ **MANDATORY: Read the full generation workflow before proceeding.**

Read and follow [Generate Seed Evaluation Dataset](../eval-datasets/references/generate-seed-dataset.md). That reference contains:
- The required JSONL row schema (`query` + `expected_behavior` are both mandatory)
- Coverage distribution targets and generation rules
- Generation requirements that keep rows valid by construction (valid JSON, required fields, coverage targets, and minimum row count)
- Foundry registration steps (blob upload + `evaluation_dataset_create`)
- Metadata updates for the selected metadata file and `manifest.json`

Do NOT skip the `expected_behavior` field. The generation reference handles the complete flow from query generation through Foundry registration.

The local filename must start with the selected environment's Foundry agent name (`agentName` in the selected metadata file) before adding stage, environment, or version suffixes.

Use [Generate Seed Evaluation Dataset](../eval-datasets/references/generate-seed-dataset.md) as the single source of truth for seed dataset registration. It covers `project_connection_list` with `AzureStorageAccount`, key-based versus AAD upload, `evaluation_dataset_create` with `connectionName`, and saving the returned `datasetUri`.

### 6. Persist Artifacts and Evaluation Suites

Save evaluator definitions, local datasets, and evaluation outputs under `.foundry/`, then register or update evaluation suites in the selected metadata file for the selected environment:

```text
.foundry/
  agent-metadata.yaml
  agent-metadata.prod.yaml
  evaluators/
    <name>.yaml
  datasets/
    <agent-name>-eval-seed-v1.jsonl
  results/
```

Each evaluation suite should bundle one dataset with the evaluator list, thresholds, and a `tags` map (for example, `tier: smoke`, `purpose: baseline`, `stage: seed`). Persist the local `datasetFile` and remote `datasetUri` together, and seed exactly one smoke suite after deployment. If the selected environment still uses older `testSuites[]` or legacy `testCases[]`, replace that list with `evaluationSuites[]` in the rewritten metadata and map legacy `priority` to `tags.tier` only when `tags.tier` is missing.

### 7. Prompt User

*"Your agent is deployed and running in the selected environment. The `.foundry` cache now contains evaluators, a local seed dataset, the Foundry dataset registration metadata, and evaluation-suite metadata. Would you like to run an evaluation to identify optimization opportunities?"*

- **Yes** → follow the [observe skill](../observe/observe.md) starting at **Step 2 (Evaluate)** — cache and metadata are already prepared.
- **No** → stop. The user can return later.
- **Production trace analysis** → follow the [trace skill](../trace/trace.md) to search conversations, diagnose failures, and analyze latency using App Insights.

## Agent Definition Schemas

### Prompt Agent

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `kind` | string | ✅ | Must be `"prompt"` |
| `model` | string | ✅ | Model deployment name (e.g., `gpt-4o`) |
| `instructions` | string | | System message for the model |
| `temperature` | number | | Response randomness (0-2) |
| `top_p` | number | | Nucleus sampling (0-1) |
| `tools` | array | | Tools the model may call |
| `tool_choice` | string/object | | Tool selection strategy |
| `rai_config` | object | | Responsible AI configuration |

### Hosted Agent

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `kind` | string | ✅ | Must be `"hosted"` |
| `image` | string | ✅ | Container image URL |
| `cpu` | string | ✅ | CPU allocation (e.g., `"0.5"`, `"1"`, `"2"`) |
| `memory` | string | ✅ | Memory allocation (e.g., `"1Gi"`, `"2Gi"`) |
| `container_protocol_versions` | array | ✅ | Protocol and version pairs |
| `environment_variables` | object | | Key-value pairs for container env vars |
| `tools` | array | | Tool configurations |
| `rai_config` | object | | Responsible AI configuration |

### Container Protocols

| Protocol | Description |
|----------|-------------|
| `a2a` | Agent-to-Agent protocol |
| `responses` | OpenAI Responses API |
| `invocations` | Invocation payload protocol for arbitrary request bodies and custom SSE behavior |
| `mcp` | Model Context Protocol |

## Agent Management Operations

### Clone an Agent

Use `agent_update` with `isCloneRequest: true` and `cloneTargetAgentName` to create a copy. For prompt agents, optionally override the model with `modelName`.

### Delete an Agent

Use `agent_delete` — automatically cleans up hosted-agent runtime resources.

### List Agents

Use `agent_get` without `agentName` to list all agents, or with `agentName` to get a specific agent's details.

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| Project type not detected | No known project files found | Ask user to specify project type manually |
| Docker not running | Docker Desktop not started or not installed | Start Docker Desktop, or use Cloud Build (ACR Tasks) instead |
| ACR login failed | Not authenticated to Azure | Run `az login` first, then `az acr login --name <acr-name>` |
| Build/push failed | Dockerfile errors or insufficient ACR permissions | Check Dockerfile syntax, verify Contributor or AcrPush role on registry |
| ACR build log crash | `UnicodeEncodeError` when `az acr build` streams remote logs | The remote build continues independently — do not assume failure. Get the `<run-id>` from the earlier `az acr build` output and check status with `az acr task show-run -r <acr-name> --run-id <run-id> --query status`. |
| Agent creation failed | Invalid definition or missing required fields | Use `agent_definition_schema_get` to verify schema, check all required fields |
| Hosted agent not running after creation | Provisioning failed or the image is not usable | Verify ACR image path, check cpu/memory values, confirm ACR permissions, then inspect hosted-agent logs with the troubleshoot skill |
| Role assignment failed | The required invocation RBAC was not granted | Stop the deployment workflow and explain that hosted-agent invocation requires `Azure AI User` on the per-agent identity and project-level agent identity at the Cognitive Services account scope |
| Invocation test failed after deployment | Missing or incorrect invocation RBAC for the per-agent identity or project-level agent identity | Check whether `Azure AI User` is assigned to the per-agent identity and project-level agent identity at the Cognitive Services account scope; assign missing role assignments, then retry invocation |
| Permission denied | Insufficient Foundry project permissions | Verify Azure AI Owner or Contributor role on the project |
| Schema fetch failed | Invalid project endpoint | Verify project endpoint URL format: `https://<resource>.services.ai.azure.com/api/projects/<project>` |

## Non-Interactive / YOLO Mode

When running in non-interactive mode (e.g., `nonInteractive: true` or YOLO mode), the skill skips user confirmation prompts and uses sensible defaults:

- **Environment variables** — Uses values resolved from `azd env get-values` and project defaults without prompting for confirmation
- **Agent name** — Must be provided in the initial user message or derived sensibly from the project context; if missing, the skill fails with an error instead of prompting
- **Hosted agent verification** — Automatically continues into RBAC and invocation verification without additional prompts once deployment succeeds

> ⚠️ **Warning:** In non-interactive mode, ensure all required values (project endpoint, agent name, ACR image) are provided upfront in the user message or available via `azd env get-values`. Missing values will cause the deployment to fail rather than prompt.

## Additional Resources

- [Foundry Hosted Agents](https://learn.microsoft.com/azure/ai-foundry/agents/concepts/hosted-agents?view=foundry)
- [Foundry Agent Runtime Components](https://learn.microsoft.com/azure/ai-foundry/agents/concepts/runtime-components?view=foundry)
- [Foundry Samples](https://github.com/microsoft-foundry/foundry-samples/)
