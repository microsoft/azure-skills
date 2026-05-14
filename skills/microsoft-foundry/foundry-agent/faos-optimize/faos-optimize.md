# FAOS (Foundry Agent Optimization Service) Optimize Python Agent

Convert existing Python agent code into a FAOS optimization-ready version by wiring runtime configuration knobs to the FAOS config contract. This workflow prepares source code for optimization, asks the user to review the changes, and then routes to Foundry deployment only after explicit user approval.

## When to Use This Skill

USE FOR: make my Python agent FAOS optimizable, add FAOS_Config, add `load_config`, enable optimization config, make this agent optimization-ready, convert Python agent for FAOS optimization, wire evaluator-driven optimization knobs, expose prompt/model/temperature for FAOS.

DO NOT USE FOR: non-Python agents, deploying an agent directly, running batch evaluations, prompt optimization of an already deployed agent without source-code changes, or general Foundry deployment. For deployment, use [deploy](../deploy/deploy.md). For evaluator runs and prompt optimization loops, use [observe](../observe/observe.md).

## Scope

- Python only for now.
- Works across Python frameworks and runtimes when there are identifiable instructions/model/options surfaces.
- The FAOS config contract is framework-neutral. Framework-specific work is limited to finding the correct insertion points and preserving the existing runtime.
- Do not switch frameworks, hosting adapters, protocols, or entrypoints unless the user explicitly asks.
- Do not deploy automatically. Always stop for review first, then suggest Foundry deployment.

## Quick Reference

| Property | Value |
| -------- | ----- |
| Supported language | Python |
| Required pattern | `from agent_optimization import load_config` |
| Required knobs | instructions, model |
| Optional knobs | temperature, skills directory, learned skills, tool/retrieval options when safe |
| Review gate | Mandatory before deploy |
| Next workflow | [deploy](../deploy/deploy.md) after user approval |

## Workflow

### Step 1: Resolve Target Agent Root

Use the parent Microsoft Foundry project context resolution rules. If the user provides a path, use that path directly. Otherwise discover `.foundry/agent-metadata*.yaml` or agent source indicators in the workspace.

After selecting an agent root, stay inside that root. Do not scan sibling agent folders unless the user explicitly switches target roots.

### Step 2: Confirm Python Eligibility

Detect Python using one or more of:

- `requirements.txt`
- `pyproject.toml`
- `setup.py`
- `*.py` entrypoints

If the target is not Python, stop and explain that FAOS source-code conversion is Python-only for now. If the target contains multiple languages, modify only the Python agent entrypoint unless the user approves a broader change.

### Step 3: Resolve Evaluator Objective

FAOS optimizes behavior against evaluator signals, so first identify what the code should become optimizable for.

Inspect these sources, in order, when available:

1. User-stated evaluator objective, for example `tool_call_accuracy`, `intent_resolution`, or `relevance`
2. Selected `.foundry/agent-metadata*.yaml` `evaluationSuites[]`, legacy `testSuites[]`, or legacy `testCases[]`
3. `.foundry/evaluators/*.yaml`
4. `.foundry/results/**` summaries or recent failure analysis files
5. Existing code comments, README guidance, or test names describing target behavior

If evaluator context is unknown, continue with a conservative base conversion and tell the user that evaluator-specific targeting may produce better FAOS results.

### Step 4: Build Python Knob Inventory

Scan the selected agent root for configurable behavior surfaces. Prefer semantic reads of source files over broad string replacement.

Look for:

- Instructions: `instructions=`, `system_prompt`, `SYSTEM_PROMPT`, `prompt=`, `system_message`, `developer_message`
- Model selection: `model=`, `deployment=`, `MODEL_DEPLOYMENT_NAME`, `AZURE_OPENAI_DEPLOYMENT`, framework-specific model fields
- Generation options: `temperature`, `top_p`, `max_tokens`, `response_format`, `tool_choice`, `parallel_tool_calls`
- Agent topology: `Agent(`, `agents=[...]`, `handoffs`, `supervisor`, `router`, `planner`, `executor`, `critic`, `synthesizer`, `WorkflowBuilder`, `StateGraph`
- Tool/retrieval surfaces: tool decorators, tool descriptions, argument schemas, retriever settings, index names, search limits
- Hosting entrypoint: FastAPI/Flask apps, `ResponsesHostServer`, uvicorn, custom response loops, LangGraph servers

Create an internal inventory with file path, symbol/name, role, current default, and whether it is safe to expose through FAOS config.

### Step 5: Classify Agent Topology

Classify the architecture before editing:

| Topology | Default FAOS targeting |
| -------- | ---------------------- |
| Single agent | Wire config directly to the agent's instructions/model/options |
| Multi-agent with obvious orchestrator/supervisor | Target the orchestrator by default, unless evaluator context points elsewhere |
| Multi-agent with specialist tool agent | Target the specialist/tool path when evaluators focus on tool or task behavior |
| Multi-agent peer architecture with no orchestrator | Present a plan and ask before editing |
| Unknown Python runtime | Add only the minimal config loader and propose exact manual wiring points |

Do not collapse multiple role-specific prompts into a single global `SYSTEM_PROMPT`. Preserve specialist prompts as defaults unless the user asks to optimize them together.

### Step 6: Map Evaluators to Candidate Knobs

Use evaluator context to select the smallest meaningful optimization scope.

| Evaluator signal | Prefer these knobs first |
| ---------------- | ------------------------ |
| `relevance` | final response instructions, answer synthesis prompt, model choice |
| `task_adherence` | primary task instructions, specialist instructions, response constraints |
| `intent_resolution` | router/orchestrator prompt, classifier prompt, planner prompt, handoff descriptions |
| `builtin.tool_call_accuracy` | tool-calling agent instructions, tool descriptions, argument schema descriptions, tool-choice/planner settings, low-temperature planning behavior |
| `indirect_attack` | safety instructions, instruction hierarchy, tool input handling, retrieved/tool-content treatment rules |
| groundedness/citation quality | retrieval instructions, answer synthesis prompt, citation formatting, retrieval parameters when exposed safely |
| latency/cost | model selection, max tokens, number of agent hops, tool/retrieval limits |

If evaluators point to different subsystems, prefer a targeted set of named config hooks over one global config. Flag any knob whose change would affect all agents, such as a shared model client.

### Step 7: Present Proposed FAOS Targets

Before editing, summarize:

- Selected agent root
- Python entrypoint(s)
- Detected topology
- Known evaluator objectives
- Proposed FAOS targets and why
- Knobs that will remain unchanged
- Files that will be modified or added

If there is exactly one safe target, proceed unless the user asked for an approval checkpoint. If there are multiple plausible targets, ask the user which scope to optimize before editing.

Example review summary:

```text
Detected evaluator targets:
- builtin.tool_call_accuracy
- intent_resolution

Detected topology:
- router_agent routes user requests
- weather_agent owns get_weather tool
- final_answer_agent synthesizes output

Proposed FAOS targets:
- router_agent instructions: improves intent resolution
- weather_agent instructions/tool schema: improves tool-call accuracy
- preserve final_answer_agent for now
```

### Step 8: Apply the Python FAOS Config Contract

Use the generic Python contract from [Python Patterns](references/python-patterns.md). At minimum, add or reuse:

```python
import os

from agent_optimization import load_config

SYSTEM_PROMPT = """...existing default instructions..."""
EXISTING_MODEL_FALLBACK = os.getenv("<existing-model-env-var>", "gpt-4.1")

config = load_config(
    default_instructions=SYSTEM_PROMPT,
    default_model=EXISTING_MODEL_FALLBACK,
    default_skills_dir="skills",
)
```

Then map the selected target knobs:

- Existing default instructions -> `config.compose_instructions()`
- Existing model default -> `config.model or <existing fallback>`. Reuse the app's current model-selection environment variable(s) and fallback chain instead of hard-coding `MODEL_DEPLOYMENT_NAME` unless that is already what the app uses.
- Existing temperature/default options -> `config.temperature` only when the runtime supports it
- Skills directory -> `config.skills_dir` only when the runtime has a skill/tool loading mechanism or one is explicitly added

For multi-agent code, prefer named config variables such as `orchestrator_config`, `tool_agent_config`, or `synthesizer_config` over a misleading global `config` when more than one agent can be optimized.

### Step 9: Add or Reuse `agent_optimization`

If the agent already has an `agent_optimization` package, reuse it and avoid overwriting user changes.

If missing, add the canonical local package structure:

```text
agent_optimization/
    __init__.py
    _config.py
    _resolver.py
```

The package must expose the public API from `__init__.py`:

```python
"""Agent optimization config loader for hosted agents."""

from agent_optimization._config import OptimizationConfig, Skill, load_config

__all__ = ["OptimizationConfig", "Skill", "load_config"]
__version__ = "0.1.0"
```

Implement `_config.py` and `_resolver.py` with the reference contract:

- `load_config(...)`
- `OptimizationConfig`
- `Skill`
- graceful fallback to defaults when no optimization config is present
- environment-variable fallback support for `AGENT_OPTIMIZATION_CONFIG` and `OPTIMIZATION_CONFIG`
- optional candidate resolver support for `AGENT_OPTIMIZATION_CANDIDATE_ID` and `AGENT_OPTIMIZATION_RESOLVE_ENDPOINT`
- candidate config resolution from `{endpoint}/candidates/{candidate_id}/config`
- optional candidate skill-file download from `{endpoint}/candidates/{candidate_id}` and `{endpoint}/candidates/{candidate_id}/files?path=...`
- resolver token acquisition with `DefaultAzureCredential().get_token("https://ml.azure.com/.default")`

Do not collapse the package into a single source file when creating new conversions. The split files make the config loader and resolver easier to compare, test, and update.

Do not introduce alternate `FAOS_OPTIMIZATION_*` environment variable names in the generated package unless the user explicitly asks for a compatibility adapter. The base FAOS contract uses `AGENT_OPTIMIZATION_*` and `OPTIMIZATION_CONFIG`.

Do not assume a public PyPI package exists. Keep the local package self-contained unless the repository already uses a shared internal package.

### Step 10: Update Dependencies and Runtime Config

Update Python dependency files only as needed:

- Add `python-dotenv` if the code imports it or already uses `.env` files
- Add `azure-identity` only if resolver token support is included or already imported

Use `load_dotenv(override=False)` so Foundry runtime environment variables win over local `.env` values.

Do not automatically add optimization env vars to `agent.yaml`. Hosted agent vNext reserves platform-owned `AGENT_*` variables in deployment payloads, so `AGENT_OPTIMIZATION_*` values should come from the optimization/runtime path or local development environment, not from user-authored `agent.yaml` container variables. If the user wants env var placeholders, add only non-reserved variables required for their workflow and keep optional optimization vars documented rather than injected by default.

### Step 11: Verify

Run these checks where possible:

1. Python syntax check for changed files
2. Import smoke test for `agent_optimization.load_config`
3. Default config smoke test with no optimization env vars
4. Pylance or workspace diagnostics for changed files
5. Existing project tests if they are cheap and relevant

If Azure credentials or model endpoints are missing, do not treat live invocation failures as conversion failures. The required proof is that defaults load and the original runtime can still start or import as far as local configuration allows.

### Step 12: Stop for Review, Then Suggest Deploy

End the workflow with a review checkpoint. Summarize:

- Changed files
- FAOS knobs exposed
- Evaluator objectives considered
- Any global side effects, such as shared model clients
- Verification results

Ask the user to review the diff. Do not deploy automatically.

When the user approves deployment, route to [deploy](../deploy/deploy.md), then [invoke](../invoke/invoke.md). If the user wants to evaluate the deployed version, route to [observe](../observe/observe.md).

## Guardrails

- Python only for now.
- The config contract is framework-neutral; insertion points are runtime-specific.
- Preserve existing frameworks, tools, hosting adapters, protocols, and entrypoints.
- Do not use one global config across all agents in a multi-agent system unless the existing architecture already uses one global prompt/model and the user approves.
- Do not wire temperature where unsupported or semantically risky.
- Prefer low-temperature planning/tool-calling defaults unless an evaluator objective suggests otherwise.
- Treat evaluator context as a targeting signal, not proof that every related knob should be changed.
- Keep all edits scoped to the selected agent root.
- Stop for review before deployment.
