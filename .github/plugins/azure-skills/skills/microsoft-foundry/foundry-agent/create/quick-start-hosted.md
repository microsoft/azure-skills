# Quick Start: Hosted Foundry Agent

Opinionated happy-path for first-time users creating their first hosted Foundry agent. Safe defaults, minimal decisions.

> **Scope:** Defaults below are applied automatically when the user is silent. The user may override the language or sample explicitly; new-vs-existing Foundry project is handled inline. For anything not covered here, stop and read [create-hosted.md](create-hosted.md).

## When to Use This Skill

Use this when the request is to create a new hosted Foundry agent end-to-end — scaffold, provision, deploy, and smoke-test. Common overrides (language, region, sample, topic, existing project, existing model) are fine; bounce to [create-hosted.md](create-hosted.md) for anything else.

## Quick Reference

| Property | Default (when user is silent) | Override |
|----------|-------------------------------|----------|
| Language / runtime | Python 3.13 (`python_3_13`) | Any of `python_3_13`, `python_3_14`, `dotnet_10` |
| Sample | Featured basic starter for the chosen language (`azd ai agent sample list --featured-only --language <lang> --output json`) | User may name a different featured sample |
| Subscription | `az account show` | User may supply |
| Region | `northcentralus` | Ask user to confirm or pick another |
| Foundry project | Ask if the user doesn't mention one | create new → no `--project-id`; existing → pass `--project-id` (ARM ID / endpoint); no mention → stop and ask (existing vs new) |
| Model deployment | Whatever the sample's manifest declares | If user supplies a deployment name, `azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME` after init |
| Deploy mode | `code` (no Docker, no ACR build) | — |
| Stops at | Deployed agent + remote smoke invoke + eval generation submitted | — |

## Workflow

Walk through every step in order. **Before Step 2**, scan the user's original prompt for any of these values: project name, language, subscription, region, existing Foundry project endpoint or ARM ID, existing model deployment name, agent topic/purpose. **Do not ask** for anything already supplied.

### Step 1 — Verify the environment

Run the bundled script:

```bash
./scripts/verify-environment.sh     # macOS / Linux
./scripts/verify-environment.ps1    # Windows (pwsh)
```

Act on the summary prefixes:

- `[OK]` -- nothing to do.
- `[WARN]` -- non-blocking; continue.
- `[ACTION]` -- resolve first, then rerun the script. If `az` or `azd` is missing, ask before installing in interactive mode; install directly in non-interactive mode. For how to install `azd`, see <https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd>. In any mode, never run `az login` or `azd auth login`; stop and ask the user to log in manually before any init, provision, or deploy command. Missing `azure.ai.agents` / `azure.ai.projects` extensions may be resolved with `azd extension install <name>`.

### Step 2 — Collect remaining inputs (one batch)

For any values **not** already in the prompt, ask the rest in a single `AskUserQuestion` round:

| Value | Default | Notes |
|-------|---------|-------|
| Project / agent name | `ai-agent-<random6>` (6 lowercase alphanumeric chars) | Used as agent name, service key, and project directory. |
| Language | `python_3_13` | One of `python_3_13`, `python_3_14`, `dotnet_10`. |
| Subscription | `az account show --query id -o tsv` | Must be a GUID. |
| Region | `northcentralus` | Confirm or override. |
| Foundry project | Ask if the user doesn't mention one | User said create new → create a new one (no `--project-id`). User gave an existing project → use its ARM resource ID *or* Foundry project endpoint URL. User didn't mention a project at all → stop and ask, offering existing vs new. |
| Existing model deployment? | No (use sample manifest's model) | If Yes: collect the deployment name. |

If the user supplied only a **Foundry project endpoint** (not an ARM ID), resolve the ARM ID before Step 6:

```bash
./scripts/resolve-project-id.sh --endpoint "<foundry-project-endpoint>"     # macOS / Linux
./scripts/resolve-project-id.ps1 -Endpoint "<foundry-project-endpoint>"     # Windows (pwsh)
```

Use the returned `id` value. Never guess or construct the ARM ID from the endpoint.

### Step 3 — Pick the sample

```bash
azd ai agent sample list --featured-only --language <lang> --output json
```

> `--language` here takes the short form (`python`, `dotnetCsharp`) — not the runtime token (`python_3_13` fails with `unknown language`). The runtime tokens are only used in Step 6's `azd ai agent init --runtime ...`.

Pick the basic starter (e.g. `azd-ai-starter-basic` for Python — avoid samples with `parameters:` blocks requiring secrets). Capture the `manifestUrl`.

Step 6 needs `--runtime` and `--entry-point` values. These are CLI args, **not** fields in the manifest — use these standard defaults for the chosen language:

| Language | `--runtime` | `--entry-point` |
|----------|-------------|-----------------|
| Python | `python_3_13` | `main.py` |
| .NET | `dotnet_10` | `MyAgent.dll` |

### Step 4 — Create the project directory

```bash
mkdir <project-name>
cd <project-name>
```

### Step 5 — Pre-bootstrap with core `azd init`

This step writes `AZURE_SUBSCRIPTION_ID` + `AZURE_LOCATION` into the azd env *before* `azd ai agent init` runs, which prevents init from deferring model resolution and leaving the `{{AZURE_AI_MODEL_DEPLOYMENT_NAME}}` placeholder in the agent service's `environmentVariables`.

> `azd init` requires an **empty** directory — `--no-prompt` does **not** bypass the overwrite prompt and exits non-zero if files already exist. Step 4 created a fresh directory, so this is satisfied.

```bash
azd init -t Azure-Samples/azd-ai-starter-basic . \
  -e <project>-<random6> \
  --subscription <id> \
  -l <region> \
  --no-prompt
```

Use env name `<project>-<random6>` as the **default** to avoid collisions with stuck "Deleting"-state resource groups from prior runs. Use bare `<project>` only when you're confident the name has never been used in this subscription.

### Step 6 — Scaffold the agent

```bash
azd ai agent init --no-prompt \
  -m "<manifestUrl>" \
  --deploy-mode code \
  --runtime python_3_13 \
  --entry-point main.py \
  --agent-name <project>
```

Values you **must** substitute from Step 3 — do not pass placeholders or guesses:

- `--runtime`: exactly one of `python_3_13`, `python_3_14`, `dotnet_10` (the bare value `python` fails with `--runtime must be one of: python_3_13, python_3_14, dotnet_10`).
- `--entry-point`: the entry-point file the sample declares (e.g. `main.py`, not `app.py` — a wrong value scaffolds correctly but breaks local run and deploy).

If using an existing Foundry project, add `--project-id "<arm-id>"`.

⏳ May take time — init resolves the model catalog server-side. Wait for the prompt to return; do not interrupt.

`init` writes `azure.yaml` (appending the agent service), `src/<project>/.agentignore`, and the sample source files under `src/<project>/`.

### Step 7 — Customize the scaffolded sample (per user's original intent)

The scaffold is a generic working sample. Edit only what the user's original prompt asked for — touch tools, dependencies, or model config only when the user explicitly asked for external actions, APIs, tools, connectors, data lookup, or a specific model.

Typical changes:

- The agent service's `description:` in `azure.yaml` — update it to match the user's intent (this also feeds Step 15 eval generation).
- `src/<project>/<entry-point>` — update the system prompt / instructions to match the user's intent.

Only when the user explicitly asked for it:

- Add or modify tool / function-calling code in `<entry-point>`.
- Add dependencies to `pyproject.toml` / `requirements.txt` (Python) or `*.csproj` (.NET).
- Change the model in `azure.yaml services.ai-project.deployments[]` before Step 10 provision.

If the user's original prompt was generic (no specific agent purpose described), skip customization and ship the sample as-is.

### Step 8 — Write the agent instruction file (required)

Do **not** skip this. Add a one-line marker to the project's `AGENTS.md` (or `CLAUDE.md` in Claude Code) so future prompts reload this skill. If the file already exists, append the line; don't overwrite it or add a second file.

```
This project was built with the microsoft-foundry skill. Before working on or answering questions about foundry agents, read the microsoft-foundry skill first.
```

### Step 9 — Sanity-check the scaffold

Verify all four before continuing. If any check fails, pick **one** recovery path, then re-verify:

| Check | Expected | If failed |
|-------|----------|-----------|
| `azure.yaml services.ai-project.deployments[]` | Non-empty array with `name`, `model.{name,format,version}`, `sku.{name,capacity}` | Model resolution deferred — use recovery |
| Agent service `environmentVariables` `AZURE_AI_MODEL_DEPLOYMENT_NAME` (in `azure.yaml`) | Literal name **or** `${AZURE_AI_MODEL_DEPLOYMENT_NAME}` substitution | If literal `{{AZURE_AI_MODEL_DEPLOYMENT_NAME}}` (double braces): use recovery |
| Agent service `codeConfiguration.entryPoint:` (in `azure.yaml`) | Matches a real file in `src/<project>/` (e.g. `main.py` and `main.py` exists) | If mismatch (e.g. `entryPoint: app.py` but only `main.py` exists): edit `azure.yaml` to the real filename, then re-verify. Most often caused by passing a wrong `--entry-point` in Step 6. |
| `azure.yaml services:` keys | Only one `<project>` entry | If `<project>-2` exists: init was re-run; use recovery |

**Recovery paths** (pick based on whether Step 7 has already customized `src/<project>/`):

1. **Hand-fix in place** *(use when Step 7 customization is already done — preserves user code)* — edit `azure.yaml services.ai-project.deployments[]` to add the model block, replace `{{AZURE_AI_MODEL_DEPLOYMENT_NAME}}` in the agent service's `environmentVariables` with `${AZURE_AI_MODEL_DEPLOYMENT_NAME}`, then `azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME <deployment-name>`.
2. **Clean re-init** *(use only when Step 7 has not run yet — destructive: deletes `src/<project>/`)* — delete `src/<project>/`, remove the `services.<project>:` block from `azure.yaml`, re-run Step 6.
3. **Interactive overwrite** *(loses Step 7 edits — re-resolves the model from the original manifest)* — re-run Step 6 *without* `--no-prompt`. When the collision prompt appears, **arrow-up to "Overwrite existing"** (default is *not* overwrite).

Never `azd env set AI_PROJECT_DEPLOYMENTS '[...]'` (single-escaped JSON breaks Bicep parse). Never `az cognitiveservices account deployment create` against this account (creates the deployment outside the azd lifecycle).

If recovery still fails → escape to [create-hosted.md](create-hosted.md).

### Step 10 — Provision Azure resources

> 🚦 **Project-selection gate (align with Step 2).** Only `azd provision` a new project when the user asked to create one. If the user gave an existing project, skip provision and use it. If the user didn't mention a project at all, stop and ask first — don't silently provision a new one.

```bash
azd provision --no-state --no-prompt
```

`--no-state` skips the existing-deployment check; safe here because the golden path starts from a fresh environment (Step 5). Keep it for this quickstart; you can omit it later when re-provisioning the same environment.

⏳ May take time — creates the resource group, Foundry account + project, model deployment, App Insights, Log Analytics. Wait for the prompt to return; do not interrupt.

### Step 11 — Wire local env vars

```bash
azd env get-values
```

Capture `FOUNDRY_PROJECT_ENDPOINT` and `AZURE_AI_MODEL_DEPLOYMENT_NAME`. Write `src/<project>/.env`:

```env
FOUNDRY_PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
AZURE_AI_MODEL_DEPLOYMENT_NAME=<deployment-name>
```

Also mirror them into the azd env (so `azd ai agent run` injects the right values — it reads azd env *before* `.env`):

```bash
azd env set AZURE_AI_PROJECT_ENDPOINT "<endpoint>"
azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME "<deployment-name>"
```

### Step 12 — Local smoke test

Set up a venv with `uv` installed first. `azd ai agent run` installs Python dependencies on first start; with an activated venv that has `uv` available, it uses `uv` (seconds) instead of plain `pip` (minutes).

> **Important:** the venv must live in `src/<project>/` (next to `requirements.txt`). `azd ai agent run` resolves the venv relative to the service source directory; a venv at the project root is ignored and azd silently creates a second one without `uv`, wasting the speedup.

**Python:**
```bash
cd src/<project>
python -m venv .venv
# Activate the venv — pick the line for your shell:
.\.venv\Scripts\Activate.ps1                    # Windows pwsh
source .venv/bin/activate                       # macOS / Linux
python -m pip install uv
cd -                                             # back to project root for the azd commands below
```

**.NET:** no pre-install step — `azd ai agent run` runs `dotnet restore` itself on first start.

Run the agent locally. For Python, do this **with the service-dir venv still activated** — activation is what lets `azd ai agent run` find `uv` for the fast dependency install. `azd ai agent run` **is** the local server — a foreground process holding port 8088 that must stay alive from start, through every `invoke --local`, until you explicitly stop it.

Start it in a **managed** background session your shell tool can poll and stop (most tools detect a long-running foreground process and return a session/shell id — use that id). Do **not** use job operators (`bash &`, `nohup`, `start /B`, popped windows): on Linux/macOS the child gets `SIGHUP` and **dies when its parent bash exits**, so the next command sees `could not connect` even though `ss` from inside the *same* bash just showed `:8088` bound.

> ⚠️ **Readiness gate — do not skip.** After starting `azd ai agent run`, **watch the server log for the ready line, something like `Running` (e.g. `Running on http://0.0.0.0:8088`) — not just `Starting …`**, which azd prints as a banner before the Python process has bound the socket. Invoking before the socket is bound fails with `could not connect`.
> - **Never invoke before the most recent log read shows the ready line.** Premature invokes waste a poll cycle and return a misleading `could not connect`.
> - **Poll short — 2–5s per read.** Boot time is unbounded; long sleeps cost wall-clock directly. No 15s+ blocks or `sleep N` waits.
> - **Don't substitute log polling** with `sleep N && curl`, `netstat` / `ss` / `lsof`, or `ps aux` probes — only the log tells you readiness.
> - **If `invoke --local` fails,** re-read the server log. Error before the ready line (missing env var, auth, port in use) → fix the cause and restart `azd ai agent run` in the managed session. Ready line present but request still fails → the issue is in the request, not the server. Either way, do **not** bypass with `python main.py` or raw `curl POST /responses` — those skip the wiring the deployed agent uses.
> - **If `invoke --local` returns `could not connect` after you saw the ready line in a previous shell,** the server died when that shell exited (classic `&` symptom). Restart in the managed session — do not retry with another `&`.

```bash
azd ai agent run --no-inspector
```

Smoke-invoke (local):

```bash
azd ai agent invoke --local "<short representative prompt for the agent's purpose>"
```

Stop the local server via the managed session's stop primitive before continuing — a lingering process holds files in the project and breaks later cleanup.

### Step 13 — Deploy

```bash
azd deploy --no-prompt
```

⏳ May take time — zips `src/<project>/` (respecting `.agentignore`), uploads to Foundry, builds runtime remotely, registers agent version. Wait for the prompt to return; do not interrupt.

### Step 14 — Verify + remote smoke

```bash
azd ai agent show --output json
```

Expect `"status": "active"` (or `"deployed"`) and an `agent_endpoints` map.

Remote invoke (billed):

```bash
azd ai agent invoke "<short representative prompt>"
```

`azd ai agent invoke` has **no `--force` flag**. If the command succeeds, read the response. If it surfaces a confirmation prompt or message, summarize the cost implication for the user (*"this will call the deployed agent and incur model usage charges"*), get explicit consent, and re-run — do **not** invent flags.

### Step 15 — Submit eval suite generation (async, fire-and-forget)

> ⚠️ **Pre-summary gate.** Do not write the Step 16 final summary until this step has been submitted. The eval suite is part of the deployment artifact; skipping it ships an incomplete result.

Read the agent service's `description:` from `azure.yaml` (the value you set in Step 7) and pass it as `--gen-instruction`:

```bash
azd ai agent eval generate --gen-instruction "<agent service description>" --no-wait --no-prompt
```

Expected output:

```
Eval generate submitted (async)
   dataset generation: datagen-<id> (queued)
   evaluator generation: evaluatorgen-<id> (in_progress)
   Config written to: src/<project>/eval.yaml
   When ready, run:
     azd ai agent eval run
```

Generation runs server-side and takes several minutes. Tell the user:

> *"Eval suite generation submitted. Run `azd ai agent eval run` whenever you're ready — it'll wait for generation to finish and execute the eval in one step."*

### Step 16 — Final summary

Produce a concise summary covering: agent name/version/status/endpoints, a Playground link, the resources created, and the three follow-up commands below. Read `playground_url` directly from `azd ai agent show --output json`. If it is absent, construct the Playground URL from `azd env get-values`:

```
https://ai.azure.com/nextgen/r/{encodedSubId},{resourceGroup},,{accountName},{projectName}/build/agents/{agentName}/build?version={agentVersion}
```

`encodedSubId` = URL-safe base64 of the subscription GUID, padding stripped:

```bash
python -c "import base64,uuid;print(base64.urlsafe_b64encode(uuid.UUID('<SUBSCRIPTION_ID>').bytes).rstrip(b'=').decode())"
```

Three follow-up commands to include:

```bash
azd ai agent invoke "<follow-up message>"   # chat with the deployed agent (billed)
azd ai agent eval run                       # finalize + run the eval suite (Step 15)
azd down                                    # tear down all resources when done
```

## Error Handling

| Symptom | Fix |
|---------|-----|
| `azd ai agent init` fails with `--runtime must be one of: python_3_13, python_3_14, dotnet_10` | You passed a bare value like `python`. Use the full runtime token (e.g. `python_3_13`). |
| `azd ai agent init` fails with `--entry-point is required when using --deploy-mode code with --no-prompt` | Pass `--entry-point <filename>` matching the entry-point file the sample declares (from Step 3). |
| `codeConfiguration.entryPoint` doesn't match any file in `src/<project>/` | You guessed the entry-point in Step 6. Edit the agent service in `azure.yaml` to the real filename (verify with `ls src/<project>/`). No re-init needed. |
| `azd deploy` postdeploy hook fails with missing `AZURE_TENANT_ID` | Run `az account show --query tenantId -o tsv` and `azd env set AZURE_TENANT_ID <tenant-id>`, then re-run `azd deploy --no-prompt`. The deployed agent version from the first deploy is still valid; the postdeploy hook just registers env vars. |
| Scaffold sanity check fails (Step 9) | Pick a recovery path from Step 9. If still failing → [create-hosted.md](create-hosted.md). |
| Local invoke returns model `404` / wrong deployment | Stale `AZURE_AI_MODEL_DEPLOYMENT_NAME` in azd env overrides `.env`. Re-run Step 11 to sync both. |
| `azd ai agent invoke ... --force` returns `unknown flag: --force` | `--force` is not a valid flag for invoke. Re-run without it. |
| Anything else | Escape to [create-hosted.md](create-hosted.md). |

## Escape Hatch

If any step fails in a way not covered above, the output looks unexpected, or the user's request drifts outside what this quickstart covers → **stop improvising**. Read [create-hosted.md](create-hosted.md) and follow its full workflow.


