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

> ⚠️ **Warning: hosted agent deployment has 8 steps, not 7.**
>
> The single most common failure of this skill is stopping after Step 7 (invocation smoke test) and emitting a "deployment complete" summary. **Step 8 (auto-generate evaluation suite) is mandatory and runs automatically after every deploy — including redeploys, version bumps, and `azd deploy` re-runs.**
>
> Before you write any final summary, Playground link, version table, or deployment success message, you MUST self-verify:
>
> 1. Did Step 8 run to completion (suite generated **or** documented fallback persisted)?
> 2. Was `.foundry/agent-metadata.yaml` updated for the selected environment?
> 3. Did you prompt the user to run an evaluation?
>
> If the answer to any of these is **no**, do not summarize — go run Step 8 now.

> ⚠️ **`azd deploy` ≠ deployment complete.** `azd deploy` (or any `azd up`/`az acr build`/`agent_update` shortcut) only covers Steps 1–6. You **MUST** still execute Step 7 (invocation test) and Step 8 (auto-generate evaluation suite) before reporting success to the user. A successful `azd deploy` exit code is **not** a stopping condition. A successful invocation in Step 7 is **not** a stopping condition either.

### Definition of Done — Hosted Agent Deployment

A hosted-agent deployment is complete only when **every** box below is checked. Do **not** produce a final "deployment successful" summary, table, or Playground link until all items are done. If you skip any item, your response is incomplete.

- [ ] Step 1 — Project scanned, type detected
- [ ] Step 2 — Environment variables confirmed with user
- [ ] Step 3 — Image built and pushed to ACR
- [ ] Step 4 — Agent configuration collected
- [ ] Step 5 — Agent definition schema retrieved
- [ ] Step 6 — `agent_update` called successfully
- [ ] Step 7 — RBAC checked **and** invocation smoke test passed (via the invoke skill)
- [ ] Step 8 — Auto-generated evaluation suite job reached `succeeded` (or documented fallback)
- [ ] Step 8 — Cache files written: `.foundry/suites/<suite>-v<ver>.json`, `.foundry/evaluators/<eval>-v<ver>.json` (FULL definition, not stub), `.foundry/datasets/<agent>-<dataset>-v<ver>.ref.json`, AND `.foundry/datasets/<dataset>-v<ver>/<blob>` (actual dataset rows via SAS-url download)
- [ ] Deployment context written to `.foundry/agent-metadata.yaml` for the selected environment
- [ ] User prompted to run an evaluation

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

> ⚠️ **Not done yet: invocation success is the midpoint, not the finish line.** The next action after a passing smoke test is **Step 8**, not a deployment summary. Do not write a summary, version table, or Playground link yet.

### Step 8: Auto-Generate Evaluation Suite (MANDATORY — RUNS AUTOMATICALLY)

> ⚠️ **Pre-summary gate.** If you are about to write a deployment summary, Playground link, or "deployment complete" message and Step 8 has not run, you are violating this skill. Run Step 8 first.
>
> This step **runs automatically** without waiting for the user to ask. The only user input required is the one-question prompt below in 8a.

This step is mandatory — not optional — for every hosted-agent deployment, including redeploys, version bumps, and `azd deploy` re-runs against an already-existing agent.

**8a. Ask the user (one question, required).** Before generating, ask the user to pick a generation source. Recommend (b) when the agent has recent traces, otherwise (a):

> *"Your agent is deployed. I'll now auto-generate an evaluation suite. Which source should I use?*
> *(a) **Current agent code/definition** — synthetic Q&A from `agent.yaml` / instructions. Best when there's little or no trace history.*
> *(b) **Historical traces** — last 3 days, ~50 traces. Best if the agent has recent invocations."*

**8b. Follow the full procedure.** Read and follow [After Deployment — Auto-Generate Evaluation Suite](#after-deployment--auto-generate-evaluation-suite) below for the generation, polling, persistence, and metadata-update steps. Required parameters and poll-to-terminal rules are non-negotiable.

**8c. Cache artifacts locally (MANDATORY after `succeeded`).** Once the suite-generation job is `succeeded`, perform the required cache calls described in [Evaluation Suite Generation → Cache Artifacts Locally](../observe/references/evaluation-suite-generation.md#cache-artifacts-locally):

- `evaluation_suite_get` → `.foundry/suites/<suite>-v<ver>.json` (full object)
- `evaluator_catalog_get` → `.foundry/evaluators/<eval>-v<ver>.json` (full definition, NOT a stub)
- `evaluation_dataset_get` + `evaluation_dataset_sas_url_get` → `.foundry/datasets/<agent>-<dataset>-v<ver>.ref.json` (metadata stub) AND `.foundry/datasets/<dataset>-v<ver>/<blob>` (actual JSONL rows). The SAS-url tool returns a container-scope SAS — list the container then `curl.exe` each blob. See the reference for the exact list+download steps. Set `contentDownloaded: true` in the stub once files are on disk.

Do not write the deployment summary until all cache files exist.

**8d. Skip-only-on-explicit-request.** If — and only if — the user explicitly says "skip eval suite generation," record that decision in your summary and still update `.foundry/agent-metadata.yaml` with the deployment context. "The user didn't ask for it" is **not** a valid reason to skip; this step is opt-out, not opt-in.

## Workflow: Prompt Agent Deployment

### Definition of Done — Prompt Agent Deployment

A prompt-agent deployment is complete only when **every** box below is checked. Do **not** produce a final "deployment successful" summary, table, or Playground link until all items are done.

- [ ] Step 1 — Agent configuration collected
- [ ] Step 2 — Agent definition schema retrieved
- [ ] Step 3 — `agent_update` called successfully
- [ ] Step 4 — Invocation smoke test passed (via the invoke skill)
- [ ] Step 5 — Auto-generated evaluation suite job reached `succeeded` (or documented fallback)
- [ ] Step 5 — Cache files written: `.foundry/suites/<suite>-v<ver>.json`, `.foundry/evaluators/<eval>-v<ver>.json` (FULL definition, not stub), `.foundry/datasets/<agent>-<dataset>-v<ver>.ref.json`, AND `.foundry/datasets/<dataset>-v<ver>/<blob>` (actual dataset rows via SAS-url download)
- [ ] Deployment context written to `.foundry/agent-metadata.yaml` for the selected environment
- [ ] User prompted to run an evaluation

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

> ⚠️ **Not done yet: invocation success is the midpoint, not the finish line.** The next action is **Step 5**, not a deployment summary. Do not write a summary or Playground link yet.

### Step 5: Auto-Generate Evaluation Suite (MANDATORY — RUNS AUTOMATICALLY)

> ⚠️ **Pre-summary gate.** If you are about to write a deployment summary or Playground link and Step 5 has not run, you are violating this skill. Run Step 5 first.
>
> This step **runs automatically** without waiting for the user to ask. The only user input required is the one-question prompt below.

**5a. Ask the user (one question, required).** Before generating, ask which generation source to use. Recommend (b) when the agent has recent traces, otherwise (a):

> *"Your agent is deployed. I'll now auto-generate an evaluation suite. Which source should I use? (a) Current agent code/definition (synthetic Q&A), or (b) Historical traces (last 3 days, ~50 traces)?"*

**5b. Follow the full procedure.** Read and follow [After Deployment — Auto-Generate Evaluation Suite](#after-deployment--auto-generate-evaluation-suite) below.

**5c. Cache artifacts locally (MANDATORY after `succeeded`).** Once the suite-generation job is `succeeded`, perform the required cache calls described in [Evaluation Suite Generation → Cache Artifacts Locally](../observe/references/evaluation-suite-generation.md#cache-artifacts-locally): suite JSON, evaluator full definition, dataset `.ref.json` PLUS the actual dataset blobs downloaded via `evaluation_dataset_sas_url_get` (container SAS → list → curl each blob). Do not write the deployment summary until those files exist.

**5d. Skip-only-on-explicit-request.** Skip only if the user explicitly says "skip eval suite generation." "The user didn't ask for it" is **not** a valid reason to skip.

## Display Agent Information

> ⚠️ **Gate:** Do not render the table or Playground link until the Definition of Done checklist for the selected workflow (Hosted or Prompt) is fully satisfied, including the invocation smoke test, the auto-generated evaluation suite (or documented skip), and the `.foundry/agent-metadata.yaml` update. The Playground link is the final artifact, not a mid-workflow checkpoint.

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

## After Deployment — Auto-Generate Evaluation Suite

> ⚠️ **This step is automatic.** After a successful deployment, immediately prepare the selected `.foundry` environment for evaluation without waiting for the user to request it. This matches the eval-driven optimization loop.

### 1. Read Agent Instructions

Use **`agent_get`** (or local `agent.yaml`) to understand the agent's purpose and capabilities.

### 2. Reuse or Refresh Suite Cache

Inspect the selected agent root before generating anything new:

- Reuse a selected environment `evaluationSuites[]` entry when it has `suiteName`, `suiteVersion`, matching `.foundry/datasets/`, and matching `.foundry/evaluators/` cache files.
- Call `evaluation_suite_get` to confirm the remote suite still exists before reusing it.
- Ask before refreshing cached files, replacing thresholds, or writing a new suite version.
- If cache or the remote suite is missing/stale, generate a new suite and update metadata for the active environment only.

### 3. Identify Generation Deployment

Use **`model_deployment_get`** to list the selected project's actual model deployments, then choose one that supports chat completions for quality evaluators. Do **not** assume `gpt-4o` exists in the project. If no deployment supports chat completions, stop the auto-setup flow and tell the user quality evaluators cannot run until a compatible judge deployment is available.

### 4. Generate Evaluation Suite

Read and follow [Evaluation Suite Generation](../observe/references/evaluation-suite-generation.md) for source selection, required parameters, polling, and cache writes. In the deploy flow, keep these guardrails:

- Ask the user which generation source to use before calling `evaluation_suite_generation_job_create`; recommend recent traces when available, otherwise the current agent code/definition.
- Use the chat-capable generation deployment selected above and honor the reference's service constraints, especially `maxSamples` (15-1000) and `agentSourceNames: [<agentName>]` for agent-sourced suites.
- Do not report deployment complete while the generation job is `in_progress`; poll with `evaluation_suite_generation_job_get` until `succeeded`, `failed`, or `canceled`, then inspect the suite with `evaluation_suite_get` and cache artifacts as described in the reference.

### 5. Fallback to Manual Suggestions

If `evaluation_suite_generation_job_create`, `evaluation_suite_generation_job_get`, or `evaluation_suite_get` fails, is unavailable, or returns incomplete artifacts, fall back to the previous manual flow:

1. Call `evaluator_catalog_get` and suggest relevant built-in/custom evaluators.
2. Read [Generate Seed Evaluation Dataset](../eval-datasets/references/generate-seed-dataset.md), generate valid local JSONL with `query` and `expected_behavior`, and register it with `evaluation_dataset_create`.
3. Persist the suite with `generationSource: manual-fallback` and include the fallback reason in the workflow summary.

Do **not** silently ignore generation failures; the user should know whether setup used the generated-suite path or the fallback path.

The local filename must start with the selected environment's Foundry agent name (`agentName` in the selected metadata file) before adding stage, environment, or version suffixes.

### 6. Persist Artifacts and Evaluation Suites

Save generated or fallback evaluator definitions, local datasets, and evaluation outputs under `.foundry/` using the cache paths defined in [Evaluation Suite Generation](../observe/references/evaluation-suite-generation.md), then register or update evaluation suites in the selected metadata file for the selected environment:

```text
.foundry/
  agent-metadata.yaml
  agent-metadata.prod.yaml
  suites/
    <suite-name>-v<version>.json
  evaluators/
    <evaluator-name>-v<version>.json
  datasets/
    <agent-name>-<dataset-name>-v<version>.ref.json
    <dataset-name>-v<version>/<blob>
  results/
```

Each evaluation suite should bundle the remote suite reference, local cache paths, thresholds, and a `tags` map (for example, `tier: smoke`, `purpose: baseline`, `stage: generated`). Persist `suiteName`, `suiteVersion`, `generationJobId`, `generationSource`, `datasetFile`, and `datasetUri` together. If the selected environment still uses older `testSuites[]` or legacy `testCases[]`, replace that list with `evaluationSuites[]` in the rewritten metadata and map legacy `priority` to `tags.tier` only when `tags.tier` is missing.

### 7. Prompt User

*"Your agent is deployed and running in the selected environment. The `.foundry` cache now contains generated evaluation-suite metadata, local dataset/evaluator references, and remote Foundry suite references. Would you like to run an evaluation to identify optimization opportunities?"*

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
