# azd ai CLI Reference

Core mental model for the `azd ai agent` extension. Use this when you need to understand command surface, file layout, or where a given setting lives.

## CLI surface

```bash
azd ai project show                  # which Foundry project endpoint is active
azd ai agent show                    # is the agent deployed? what version?
azd ai agent doctor                  # full health check, suggests fixes

azd ai agent sample list             # curated catalog -- pick a manifestUrl
azd ai agent init -m <manifestUrl>   # scaffold from a sample
azd ai agent init --from-code        # scaffold from existing source

azd ai agent run                     # start the agent on localhost:8088
azd ai agent invoke "<msg>"          # remote invoke (billed; gated)
azd ai agent invoke --local "<msg>"  # local invoke (no billing)

azd provision                        # core azd; creates Foundry project + infra
azd deploy                           # core azd; packages + registers new agent version
azd ai agent endpoint update         # patch agentEndpoint / agentCard in place

azd ai agent connection list / show / create / update / delete
azd ai toolbox list / show / create / update / delete
azd ai toolbox connection add / remove / list
azd ai toolbox version list

azd ai agent files list / show / upload / download / delete / stat / mkdir
azd ai agent sessions list / show / create / update / delete
azd ai agent monitor                 # per-session log stream (SSE)

azd ai agent eval generate / run / show / update / list
azd ai agent optimize / optimize status / optimize apply / optimize deploy / optimize cancel
```

Read-only commands accept `--output json` and never require `--force`. Write commands are gated by a confirmation envelope (see "Confirmation envelope" below).

## Two files, two schemas

After `azd ai agent init`, every hosted agent is defined by **two** files plus the active azd env. Putting a field in the wrong file is the most common scaffolding failure.

| File | What it holds |
|------|---------------|
| `<service-dir>/agent.yaml` | The flat `ContainerAgent`: `kind`, `name`, `protocols`, `environment_variables`, `agentEndpoint`, `agentCard`, `code_configuration` / `image`, container `resources` (cpu, memory). |
| `azure.yaml services.<name>.config` | Model deployments, project connections, toolboxes, tool resources, container settings, `startupCommand`. |
| `.azure/<env>/.env` (`azd env set`) | Secrets and `PARAM_<CONN>_<KEY>` credential values referenced from `azure.yaml`. |

`azd deploy` reads `agent.yaml` and creates a new immutable agent version. `azd provision` reads `config.deployments[]` and `config.connections[]` and applies them via Bicep.

`agent.manifest.yaml` (the file passed to `-m`) is the seed format -- it is NOT on disk after init. Init splits its `parameters:` / `resources:` blocks across the three files above. Don't reintroduce the `template:` wrapper into `agent.yaml`.

### Minimal `agent.yaml` (hosted)

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/microsoft/AgentSchema/refs/heads/main/schemas/v1.0/ContainerAgent.yaml
kind: hosted
name: my-agent
protocols:
  - protocol: responses
    version: "1.0.0"
resources:
  cpu: "0.25"
  memory: "0.5Gi"
environment_variables:
  - name: AZURE_AI_MODEL_DEPLOYMENT_NAME
    value: ${AZURE_AI_MODEL_DEPLOYMENT_NAME}
code_configuration:
  runtime: python_3_13
  entry_point: app.py
  dependency_resolution: remote_build   # or "bundled"
```

- `protocols` -- `responses` (OpenAI), `invocations` (A2A). Editing requires `azd deploy`.
- `resources` -- valid tiers: `0.25/0.5Gi`, `1/2Gi`, `2/4Gi`.
- `environment_variables` -- `${VAR}` resolves from the active azd env. Not for secrets.
- `code_configuration` present -> direct code deploy (ZIP, Foundry builds). Absent -> container/ACR deploy (Dockerfile + `docker:` in `azure.yaml`). `image:` skips the Dockerfile build.
- In non-interactive mode, `azd ai agent init` defaults to container deploy. Pass `--deploy-mode code --runtime <runtime> --entry-point <file>` during init to get `code_configuration`.
- `agentEndpoint` / `agentCard` -- patch in place with `azd ai agent endpoint update` (no new version).

### Minimal `azure.yaml` service config

```yaml
services:
  my-agent:
    project: ./src/my-agent
    host: azure.ai.agent
    language: python
    config:
      startupCommand: "python -m main"
      container:
        resources:
          cpu: "0.5"
          memory: "1Gi"
      deployments:
        - name: AZURE_AI_MODEL_DEPLOYMENT_NAME
          model:
            name: gpt-4.1-mini
            format: OpenAI
            version: "2024-04-09"
          sku:
            name: GlobalStandard
            capacity: 50
      connections: [...]        # see tools.md
      toolboxes: [...]          # see tools.md
```

- `startupCommand` -- what `azd ai agent run` executes locally. Auto-detected at init.
- `config.container.resources` -- deployment-time CPU/memory. Keep this aligned with `agent.yaml resources`; this value can override the agent file.
- `deployments[]` -- model deployments provisioned via Bicep. `name` is the env var the agent reads.
- `connections[]` -- project connections provisioned via Bicep. Use `PARAM_<CONN>_<KEY>` env-var references for secrets.
- `toolboxes[]` -- declarative record of intent; today you still drive the toolbox CLI to materialize them on Foundry. See [tools](tools.md).

## State (azd env vars)

| Variable | Read by | Where to set |
|----------|---------|--------------|
| `AZURE_AI_PROJECT_ENDPOINT` | Every `azd ai agent` command | `azd env set` or `azd ai project show` |
| `AZURE_AI_PROJECT_ID` | `azd ai agent show` (playground URL) | `azd env set` |
| `AZURE_SUBSCRIPTION_ID`, `AZURE_LOCATION` | `azd provision` | `azd config get defaults` |
| `AGENT_<SVC>_NAME` / `_VERSION` / `_<PROTO>_ENDPOINT` | Auto-written by deploy | Auto |
| `PARAM_<CONN>_<KEY>` | Connection credentials in `azure.yaml` | `azd env set` |

Manage with `azd env get-values`, `azd env set`, `azd env list`, `azd env new`, `azd env select`.

The platform also injects `FOUNDRY_*` and `AGENT_*` into the running container at runtime. **Never** put these in the agent.yaml environment_variables section.

## Resolving subscription / location

`azd ai project show` returns only the Foundry project endpoint. For subscription / location, try in order:

1. `azd config get defaults`
2. `azd env get-values`
3. Ask the user.
4. Last resort, with explicit consent: `az account list --output json`.

For the Foundry project ARM ID (`--project-id`), ask the user: "New project, or use an existing one?" If existing, ask for the ID and hint where to find it (https://ai.azure.com -> Operate -> Admin). Do NOT shell out to `az cognitiveservices` -- it returns the wrong resource shape.

## Common error codes

- `not_logged_in` / `login_expired` -- ask the user to run `azd auth login`.
- `missing_project_endpoint` -- run `azd provision`, or `azd env set AZURE_AI_PROJECT_ENDPOINT <url>`.
- `project_not_found` -- cwd has no `azure.yaml`. Move to project root or run init.
- `invalid_agent_manifest` -- `agent.yaml` is malformed. Run `azd ai agent doctor` and read the named field.
- `invalid_connection` -- inspect with `azd ai agent connection show <name>`.
- `eval_config_invalid` -- `eval.yaml` failed validation. Run `azd ai agent doctor`.
- `agent_definition_not_found` -- deployed name doesn't match `azure.yaml`. Re-deploy from project root.

Any unfamiliar `code` value is safe to surface verbatim to the user.
