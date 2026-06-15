# Create Hosted Agent (azd ai)

Scaffold a hosted Foundry agent project with the Azure Developer CLI (`azd`) and the `azure.ai.agents` extension. The same flow covers greenfield (from a curated sample) and brownfield (lift existing code), then drops you into a local inner-loop so you can iterate before deploying.

> **Creating a new agent end-to-end from scratch?** Use [quick-start-hosted.md](quick-start-hosted.md) instead -- an opinionated happy-path with safe defaults. Stay here for anything not covered by the quickstart.

> **Scope:** `azd ai` is the preferred *code-first* path -- use it when the intent is agent code on disk, in a repo, with infrastructure-as-code and a local inner-loop. If the intent is only to create a remote agent resource (no code on disk), other approaches may apply -- for prompt agents see [create-prompt.md](create-prompt.md), or use the Foundry MCP tools / portal.

## Quick Reference

| Property | Value |
|----------|-------|
| Agent type | Hosted (container or code) |
| Primary CLI | `azd ai agent` (from extension `azure.ai.agents`) |
| Scaffold command | `azd ai agent init -m <manifestUrl> --deploy-mode code --runtime python_3_13 --entry-point main.py`, pass `--runtime dotnet_10 --entry-point MyAgent.dll` for .NET project (or `--from-code` for brownfield) |
| Local run | `azd ai agent run` + `azd ai agent invoke --local "..."` |
| Deploy handoff | [deploy/deploy.md](../deploy/deploy.md) |
| Sample catalog | `azd ai agent sample list --featured-only --output json` |
| Reference docs | [azd-ai-cli](references/azd-ai-cli.md), [local-run](references/local-run.md), [tools](references/tools.md) |

## When to Use This Skill

- Create a new hosted agent from a curated Foundry sample.
- Lift an existing agent project (Python, .NET, Node.js) into a hosted Foundry agent.
- Add tools (web search, AI Search, MCP, A2A) to a hosted agent.
- Run and iterate on a hosted agent locally before deploying.

For prompt agents (LLM + instructions, no container), use [create-prompt.md](create-prompt.md). For deploy, use [deploy.md](../deploy/deploy.md).

## Hosted vs Prompt

| | Hosted | Prompt |
|--|--------|--------|
| Custom Python / .NET / Node code? | Yes -> this skill | No -> [create-prompt.md](create-prompt.md) |
| Tools / RAG / MCP / A2A | Toolbox + connections | Built-in tool configs |
| Local debugging | `azd ai agent run` | Limited |
| Output | New immutable agent version per `azd deploy` | `agent_update` via MCP / SDK |

## Workflow

### Step 1 -- Verify the environment

> **Preflight: get `AZURE_SUBSCRIPTION_ID` + `AZURE_LOCATION` into the azd env *before* the first `azd ai agent init`.** Without both, init defers model resolution → `azure.yaml services.<name>.config.deployments[]` ends up empty → `AI_PROJECT_DEPLOYMENTS=[]` → `azd provision` creates zero model deployments → `agent.yaml` keeps the literal `{{AZURE_AI_MODEL_DEPLOYMENT_NAME}}` placeholder. `azd ai agent init` itself has **no** `--subscription` / `--location` flags (those live on core `azd init`). Pick the **first** option that fits, ranked best-first:
>
> 1. **Pre-bootstrap with core `azd init`** — per-project, no global state. **Recommended default for scripted / MCP / agent-driven flows.** Run in the target empty directory:
>    ```bash
>    azd init -t Azure-Samples/azd-ai-starter-basic . -e <env-name> --subscription <id> -l <region>
>    azd ai agent init -m <manifest-url> --no-prompt --deploy-mode code --runtime python_3_13 --entry-point main.py
>    ```
>    Core `azd init` creates `azure.yaml` + the azd env with `AZURE_SUBSCRIPTION_ID` / `AZURE_LOCATION` already populated; the extension's `ensureProject` sees the existing project and the model resolver reads the values core just wrote. (Use this even though `azd ai agent init` can scaffold from scratch — it's the only headless path that avoids deferral without mutating global config.)
> 2. **`azd ai agent init --project-id <arm-id>`** — only when the Foundry project already exists in Azure. Init extracts the subscription from the ARM ID and uses the project's own location. Skip Option 1.
> 3. **Interactive mode** — omit `--no-prompt`. Init prompts for subscription + location. Only when a human is at a terminal.
> 4. **Global config (last resort, mutates `~/.azure/config.json` for every azd project on the machine):**
>    ```bash
>    azd config set defaults.subscription <id>
>    azd config set defaults.location <region>
>    ```
>    Avoid in per-project / scripted flows. Use only when no per-project option fits and the machine is single-tenant.
>
> **If you only discover the need to set sub + location *after* init has already scaffolded `src/<name>/`, do *not* naively re-run `azd ai agent init`.** It is not idempotent: under `--no-prompt` it silently creates `<service>-2`; in interactive mode the collision prompt's **default selection is "Use a different service name"** (you must actively arrow-up to "Overwrite existing"). See the [recovery paths](#step-4a----greenfield-scaffold-from-a-sample) in Step 4a.
>
> Never `azd env set AI_PROJECT_DEPLOYMENTS '[...]'` and never `az cognitiveservices account deployment create ...` for the azd Golden Path — both break the lifecycle.

Run the bundled verification script to check that the local environment is set up correctly:

```bash
./scripts/verify-environment.sh     # macOS / Linux
./scripts/verify-environment.ps1    # Windows (pwsh)
```

Act on the summary prefixes: `[OK]` nothing to do; `[WARN]` non-blocking (continue); `[ACTION]` resolve first (missing extension -> `azd extension install azure.ai.agents`; failed auth -> ask the user to run `azd auth login`, never run it yourself).

Branch on the reported agent status:

- `not_deployed` -> Step 2.
- `active` / `deployed` -> already deployed. Skip to [deploy/deploy.md](../deploy/deploy.md) for redeploy or [tools](references/tools.md) to add a tool.

### Step 2 -- New or existing Foundry project?

Ask: "Do you want to create a new Foundry project, or use an existing one?" Skip the question when the prompt already says to use an existing project or supplies a Foundry project endpoint / project ARM resource ID.

- **New project** -- do NOT pass `--project-id`. `azd provision` (in deploy) will create it.
- **Existing project with ARM resource ID** -- pass that exact ID to `azd ai agent init --project-id`.
- **Existing project with Foundry project endpoint only** -- resolve the project ARM resource ID with the bundled script, then pass the returned `id` to `azd ai agent init --project-id`:
  ```bash
  ./scripts/resolve-project-id.sh --endpoint "<foundry-project-endpoint>"     # macOS / Linux
  ./scripts/resolve-project-id.ps1 -Endpoint "<foundry-project-endpoint>"     # Windows (pwsh)
  ```
- **Existing project with neither endpoint nor ARM ID** -- ask for the ARM resource ID.

Do not guess, derive, or construct the project ID from the endpoint. For `--project-id`, pass either the user-supplied project ARM resource ID or the `id` returned by Azure lookup / the bundled resolve script.

### Step 3 -- Pick the scaffolding source

| User has ... | Use |
|--------------|-----|
| Empty workspace, or wants a starter | **Greenfield** -- Step 4a |
| Hand-written agent code already in cwd | **Brownfield** -- Step 4b |

If unsure, default to greenfield. Never guess a manifest URL by hand.

### Step 4a -- Greenfield: scaffold from a sample

List the curated catalog (filter by language if known):

```bash
azd ai agent sample list --featured-only --language python --output json
```

Each entry has a `manifestUrl` and an `initCommand`. Prefer direct code deploy at init time. `--no-prompt` defaults to container deploy unless you pass `--deploy-mode code`, so include the code flags up front.

For a generic new hosted agent request, start from the basic sample. Use tool/function-calling samples only when the user explicitly asks for external actions, APIs, tools, connectors, or data lookup.

> **Before running init**, make sure subscription + location are resolvable via one of the four options in [Step 1 preflight](#step-1----verify-the-environment). For headless / scripted flows the recommended path is to **pre-bootstrap with core `azd init`**:
>
> ```bash
> azd init -t Azure-Samples/azd-ai-starter-basic . -e <env-name> --subscription <id> -l <region>
> ```
>
> Then run `azd ai agent init` inside the bootstrapped directory. `azd ai agent init` itself has **no** `--subscription` / `--location` flags (passing them fails with `unknown flag`); core `azd init` does. If init still defers resolution (empty `config.deployments[]` / `{{...}}` placeholder), see the recovery paths after the init example below — do **not** blindly re-run init.

Python Example (add `--project-id "<resourceId>"` for an existing Foundry project; add `--agent-name <name>` if the user wants a custom name -- omit otherwise to keep the sample default):

```bash
azd ai agent init --no-prompt \
  -m "<manifestUrl>" \
  --deploy-mode code \
  --runtime python_3_13 \
  --entry-point main.py
```

> `--agent-name` at init names both `agent.yaml name:` and `azure.yaml services:<key>:` in one shot; renaming after init requires editing both files.

Do not run `azd env new`, `azd env select`, or `azd env set` before `azd ai agent init` in a new temp/workspace; there is no azd project yet, so those commands fail and waste time. For an existing project, `--project-id` is enough during init. Set endpoint/model values immediately after init, once `azure.yaml` and the azd env exist.

> Tip: if the manifest declares a `parameters:` block (check by `curl <manifestUrl>`), collect required values before init when an azd project already exists. In a new empty workspace, prefer a sample without required secrets; there is no azd env to set until init creates the project files.

`init` writes `azure.yaml` (or appends to it), `<service-dir>/agent.yaml`, and `<service-dir>/.agentignore` (code-deploy only). A successful direct-code init produces `<service-dir>/agent.yaml` with `code_configuration:`. For file shapes, see [azd-ai-cli](references/azd-ai-cli.md).

#### Model deployments (azd Golden Path)

`azure.yaml services.<name>.config.deployments[]` is the **single source of truth** for model deployments in azd-managed Foundry projects. The flow is:

```
manifest → azd ai agent init → azure.yaml config.deployments[] → AI_PROJECT_DEPLOYMENTS env (internal) → Bicep → Microsoft.CognitiveServices/accounts/deployments
```

Rules:

- **`azd ai agent init` writes `config.deployments[]` from the sample's manifest** and also sets `AZURE_AI_MODEL_DEPLOYMENT_NAME` to the first deployment's `name`. `azd provision` then creates the deployment through Bicep. No `az` calls are needed in the Golden Path.
- **`deployments[].name` is the literal Azure deployment resource name** — not a label, not a placeholder. Use a human-readable model name (e.g. `gpt-4o-mini`, `gpt-4.1-mini`). **Never** use the literal string `AZURE_AI_MODEL_DEPLOYMENT_NAME` as the `name` value; doing so creates a deployment literally named `AZURE_AI_MODEL_DEPLOYMENT_NAME` and the agent will 404 on its first invoke.
- **Adding a *second* model (or any change to `config.deployments[]`) to an existing project:** edit `azure.yaml services.<name>.config.deployments[]` directly (and update `agent.yaml model_deployment_name:` / `${AZURE_AI_MODEL_DEPLOYMENT_NAME}` if the new entry should become the default), then run `azd provision`. The extension's `preprovision` hook calls `envUpdate` automatically, which re-marshals `azure.yaml deployments[]` and re-writes `AI_PROJECT_DEPLOYMENTS` with the correct double-escaping before Bicep runs. **Do not re-run `azd ai agent init`** for this case — it triggers the non-idempotent collision flow (see anti-patterns) and at best (with explicit "Overwrite existing") re-resolves models from the original manifest rather than merging your edit.
- **`agent.yaml`: prefer `${AZURE_AI_MODEL_DEPLOYMENT_NAME}` over a hardcoded model name.** The `${VAR}` form is resolved from the active azd env at run / deploy time, so a single `azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME <name>` (or env switch dev → prod) updates `agent.yaml` without touching the file. Init writes this form by default (`init_from_code.go`); only the literal `{{AZURE_AI_MODEL_DEPLOYMENT_NAME}}` (double braces) is a failure marker that means model resolution deferred.
- **Recovery: `config.deployments[]` is empty or `agent.yaml` has the literal `{{AZURE_AI_MODEL_DEPLOYMENT_NAME}}` placeholder.** First get sub + location into the env (see [Step 1 preflight](#step-1----verify-the-environment) options). Then pick **one** of these three paths — init is **not** idempotent:
  1. **Clean re-init (preferred when no user code has been added to `src/<name>/` yet):** delete `src/<name>/`, remove the `services.<name>:` block from `azure.yaml`, then re-run `azd ai agent init`. No collision, scaffolds cleanly with the resolved model.
  2. **Interactive overwrite:** re-run `azd ai agent init` **without `--no-prompt`**. When the collision prompt appears, **actively arrow-up and select "Overwrite existing"** — the default selection is *not* overwrite (it's "Use a different service name", which produces `<name>-2`).
  3. **Hand-fix in place (preserves any user code in `src/<name>/`):** edit `azure.yaml services.<name>.config.deployments[]` to add the model block (`name`, `model.{name, format, version}`, `sku.{name, capacity}`), replace the literal `{{AZURE_AI_MODEL_DEPLOYMENT_NAME}}` in `agent.yaml` with `${AZURE_AI_MODEL_DEPLOYMENT_NAME}`, then `azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME <deployment-name>`. Run `azd provision`; the `preprovision` hook auto-syncs `AI_PROJECT_DEPLOYMENTS`.
- **Anti-patterns — do not do these:**
  - **Blindly re-running `azd ai agent init` against an existing project.** Under `--no-prompt` init silently auto-suffixes (`<service>-2`, then `-3`, ...) via `nextAvailableName`; in interactive mode the collision prompt's default is "Use a different service name". There is **no flag** (`--force` does not apply here) to make `--no-prompt` overwrite. Use one of the three recovery paths above.
  - **Reaching for `azd config set defaults.subscription` / `defaults.location` as the *first* fix for the deferral.** This mutates `~/.azure/config.json` for every azd project on the machine. Prefer pre-bootstrap with `azd init -t ... --subscription -l` (per-project) or `--project-id` (existing project) first — see the [Step 1 preflight options](#step-1----verify-the-environment).
  - `azd env set AI_PROJECT_DEPLOYMENTS '[...]'` — `AI_PROJECT_DEPLOYMENTS` is internal extension state. The extension writes it with double-escaped JSON (`\\` and `\"`) required by Bicep parameter substitution; `azd env set` only single-escapes and breaks the parse with `invalid character 'n' after object key:value pair`.
  - `az cognitiveservices account deployment create ...` against the azd-managed Foundry account — creates the deployment outside the azd lifecycle, so `azd provision` won't manage it and `azd down` won't clean it up. Use `az cognitiveservices` (or [models/deploy-model](../../models/deploy-model/SKILL.md)) **only** for shared/pre-existing Foundry projects that are not managed by this azd project.
  - Hand-patching the `{{AZURE_AI_MODEL_DEPLOYMENT_NAME}}` placeholder in `agent.yaml` *without also* adding the matching entry to `azure.yaml services.<name>.config.deployments[]` — the agent will reference a deployment name that Bicep never created. Use the [hand-fix recovery path](#step-4a----greenfield-scaffold-from-a-sample) above (path #3) which fixes both files together.

Check the scaffold before local run:

1. **Verify `azure.yaml services.<name>.config.deployments[]` is non-empty** and that `<service-dir>/agent.yaml` has either a literal `model_deployment_name:` value or the `${AZURE_AI_MODEL_DEPLOYMENT_NAME}` substitution form — **not** the double-brace literal `{{AZURE_AI_MODEL_DEPLOYMENT_NAME}}` (that placeholder is the marker that init deferred model resolution). Also confirm `azure.yaml` has only **one** service entry for your agent — a duplicate `<name>-2` means a previous init re-ran against the existing project (collision prompt default + `--no-prompt` silent auto-suffix; see anti-patterns above). If either condition fails, use one of the three [recovery paths in the anti-patterns section](#model-deployments-azd-golden-path) (clean re-init / interactive overwrite / hand-fix). Do **not** `azd env set AI_PROJECT_DEPLOYMENTS`.
2. If the user supplied an existing project endpoint, project ARM ID, or model deployment name, set them in the active azd env and verify the values. `azd ai agent run` injects azd env values before `.env`, so a stale `AZURE_AI_MODEL_DEPLOYMENT_NAME` can override a correct `.env` file.
   ```bash
   azd env set AZURE_AI_PROJECT_ENDPOINT "<project-endpoint>"
   azd env set AZURE_AI_PROJECT_ID "<project-arm-id>"
   azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME "<model-deployment-name>"
   azd env get-values
   ```
3. Create the agent source `.env` with the same endpoint and model deployment values:
   ```env
   FOUNDRY_PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
   AZURE_AI_MODEL_DEPLOYMENT_NAME=<model-deployment-name>
   ```
4. Prefer direct code deployment. Inspect `<service-dir>/agent.yaml`; if `code_configuration:` is missing and the agent does not need a custom Dockerfile or system packages, add it before deployment.
5. Prefer `--agent-name` at init time (above). Fallback only: if init already ran without it, rename the agent in `<service-dir>/agent.yaml` AND the matching key under `azure.yaml services:` to the same value, preserving its `project:` path.
6. If you change CPU or memory, keep `<service-dir>/agent.yaml` and `azure.yaml services.<name>.config.container.resources` aligned because the `azure.yaml` service config can override the agent file.

### Step 4b -- Brownfield: lift existing code

Use ONLY when the workspace already contains hand-written agent source.

```bash
azd ai agent init --no-prompt \
  --src ./src/my-agent \
  --agent-name my-agent \
  --deploy-mode code \
  --runtime python_3_13 \
  --entry-point app.py
```

`--runtime` and `--entry-point` are required with `--deploy-mode code --no-prompt`. Runtimes: `python_3_13`, `python_3_14`, `dotnet_10`, `node_22`. `--deploy-mode container` builds from `Dockerfile`. For an existing Foundry project, add `--project-id "<resourceId>"`.

### Step 5 -- Run locally and iterate

Read and follow [local-run](references/local-run.md). Complete one representative local invocation before deploying.

### Step 6 -- Add tools (optional)

Tools attach through **toolboxes** -- bundled MCP-compatible endpoints. Flow:

1. Create the **connection** (`azd ai agent connection create ...`).
2. Create or update the **toolbox** (`azd ai toolbox create` / `connection add`).
3. Set the agent env var (`azd env set TOOLBOX_<NAME>_MCP_ENDPOINT ...`).
4. Reference it in `agent.yaml` `environment_variables[]`.
5. `azd deploy`.

Full recipes (GitHub MCP, Azure AI Search, A2A, Bing Custom) in [tools](references/tools.md).

### Step 7 -- Hand off to deploy

Once local invocation succeeds, tell the user the agent is ready and ask if they want to deploy. Read [deploy/deploy.md](../deploy/deploy.md).

## Expected env-var fingerprint (post-provision)

After `azd provision` completes for an `azd ai agent`-scaffolded project (default Basic Agent Setup), `azd env get-values` should show this canonical state. Verify before debugging deployment or runtime issues.

| Variable | Expected value | Notes |
|----------|----------------|-------|
| `ENABLE_HOSTED_AGENTS` | `true` | Set automatically by `azd ai agent init`. |
| `ENABLE_CAPABILITY_HOST` | `false` | Set automatically by `azd ai agent init`. Leave as-is unless you are intentionally targeting Standard Agent Setup. |
| `FOUNDRY_PROJECT_ENDPOINT` | `https://<account>.services.ai.azure.com/api/projects/<project>` | Populated by provision (or pre-set if reusing an existing project). |
| `AZURE_AI_PROJECT_ID` | Full ARM resource ID of the Foundry project | Populated by provision; required for deploy. |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | Model deployment name (e.g. `gpt-4o`) | Set automatically by `azd ai agent init` from the first entry in `azure.yaml services.<name>.config.deployments[]`. Required for local run and deploy. |
| `AI_PROJECT_DEPLOYMENTS` | escaped JSON array, e.g. `[{\"name\":\"gpt-4o\",...}]` | **Internal extension state.** Managed by `azd ai agent init` from `azure.yaml services.<name>.config.deployments[]`. Carries deployments into the Bicep parameter `aiProjectDeploymentsJson`. **Never** set with `azd env set` — manual edits single-escape the JSON and break Bicep `json()` parsing. |
| `AI_AGENT_PENDING_PROVISION` | *(empty / unset)* | Non-empty means provision is still mid-flight; do not deploy. |

`Microsoft.CognitiveServices/accounts/capabilityHosts/agents` is **not** provisioned by `azd ai agent init` (Basic Agent Setup). Its absence is expected. The resource only appears under Standard Agent Setup, which is documented separately in [references/standard-agent-setup.md](../../references/standard-agent-setup.md).

Both `ENABLE_HOSTED_AGENTS` and `ENABLE_CAPABILITY_HOST` are set automatically by `azd ai agent init` — you do not need to manage them. If you ever set them manually outside this flow, see [project/create/create-foundry-project.md](../../project/create/create-foundry-project.md#step-3-create-directory-and-initialize) for the manual-flag procedure.

See the canonical env-var registry: [azure-dev/cli/azd/docs/environment-variables.md](https://github.com/Azure/azure-dev/blob/main/cli/azd/docs/environment-variables.md).

## Common Guidelines

1. **Sample-first** -- always get `manifestUrl` from `azd ai agent sample list`.
2. **Prefer azd over az** -- fall back to `az` only as a last resort, with explicit consent.
3. **Don't auto-login** -- `azd auth login` opens a browser; ask the user.
4. **JSON output** -- add `--output json` only to read-only `azd ai agent` commands such as `show`. Do not add it to `azd ai agent invoke`; invoke supports `default` and `raw`, not `json`.
5. **Two files** -- `agent.yaml` is the agent; `azure.yaml services.<name>.config` is service config. See [azd-ai-cli](references/azd-ai-cli.md).
6. **Reserved env vars** -- `FOUNDRY_*` and `AGENT_*` are platform-injected at runtime; `AI_PROJECT_DEPLOYMENTS`, `AI_PROJECT_RESOURCES`, and `AI_PROJECT_TOOL_CONNECTIONS` are extension-managed transport for Bicep. Never set any of these with `azd env set` — edit `azure.yaml services.<name>.config` and re-run `azd ai agent init`.

## Non-Interactive / YOLO Mode

Defaults when unspecified: greenfield + Python + `azd ai agent sample list --featured-only --language python`, choose the simplest recommended sample that matches the request, plus `--no-prompt` on every write. If creating a new project and the user did not provide a project name, auto-generate one using the pattern `ai-project-<random>` (6-8 lowercase alphanumeric characters). Show the generated name to the user but do not block on confirmation. If using an existing project, ensure `azd ai agent init` receives `--project-id`: use the supplied ARM ID, or run the Step 2 resolve script for the supplied Foundry project endpoint and pass the returned `id`. Stop and ask only when neither an ARM ID nor a resolvable endpoint is available. If the manifest declares secret parameters, collect them with `ask_user` and set them via `azd env set PARAM_...` before init -- keep `--no-prompt` (do not fall into azd's interactive prompts).

## Error Handling

| Error | Fix |
|-------|-----|
| `extension not installed` | `azd extension install azure.ai.agents` |
| `not_logged_in` / `login_expired` | Ask user to run `azd auth login` |
| `unknown flag: --subscription` / `--location` on `azd ai agent init` | Wrong command — those flags live on **core** `azd init`. See [Step 1 preflight](#step-1----verify-the-environment) for the four options. |
| `no project exists; to create a new project, run azd init` on `azd env set` | The azd env does not exist yet — `azd env set` cannot create it. See [Step 1 preflight](#step-1----verify-the-environment). |
| `agent.yaml` contains literal `{{AZURE_AI_MODEL_DEPLOYMENT_NAME}}` placeholder after init | Init deferred model resolution. **Do not blindly re-run init** (default prompt = `<name>-2`; `--no-prompt` silently auto-suffixes). Pick one of the three [recovery paths](#model-deployments-azd-golden-path): clean re-init after deleting `src/<name>/`, interactive overwrite, or hand-fix `azure.yaml` + replace `{{...}}` with `${AZURE_AI_MODEL_DEPLOYMENT_NAME}` and `azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME <name>`, then `azd provision`. |
| `azure.yaml` has duplicate `<service>-2` entry after re-running init | Init is not idempotent: interactive default is "Use a different service name" and `--no-prompt` silently appends `-2`. To recover, merge the resolved `deployments:` block from `<service>-2` into the original service, delete the `<service>-2` entry from `azure.yaml`, remove `src/<service>-2/`, then `azd provision`. |
| `invalid character 'n' after object key:value pair` during `azd provision` | You used `azd env set AI_PROJECT_DEPLOYMENTS '[...]'` (single-escaped JSON breaks Bicep `json()`). Clear it (`azd env set AI_PROJECT_DEPLOYMENTS ""`), declare the deployment in `azure.yaml services.<name>.config.deployments[]` instead, then re-run `azd provision` (its `preprovision` hook re-syncs `AI_PROJECT_DEPLOYMENTS` with the correct double-escaping). |
| `missing_project_endpoint` | Run `azd provision`, or `azd env set AZURE_AI_PROJECT_ENDPOINT <url>` |
| `project_not_found` | cwd has no `azure.yaml`; move to project root or run init |
| Secret parameter prompt under `--no-prompt` | In an empty workspace, choose a simpler sample without secret parameters. In an existing azd project, set `PARAM_<CONN>_<KEY>` with `azd env set` before init; keep `--no-prompt`. |
| `cannot use --version with --local` | Drop `--version`, or drop `--local` to hit the deployed agent |
| `could not detect project type` | Set `startupCommand` in `azure.yaml` or pass `--start-command` |
| Local run issue | Follow [local-run](references/local-run.md) common failures |

Run `azd ai agent doctor --output json` to surface failing checks with `suggestion` fields.

## Next Steps

- Deploy to Foundry -> [deploy/deploy.md](../deploy/deploy.md)
- Add tools -> [tools](references/tools.md)
- Invoke the deployed agent -> [invoke/invoke.md](../invoke/invoke.md)
- Evaluate / optimize -> [observe/observe.md](../observe/observe.md)
- Diagnose failures -> [troubleshoot/troubleshoot.md](../troubleshoot/troubleshoot.md)
