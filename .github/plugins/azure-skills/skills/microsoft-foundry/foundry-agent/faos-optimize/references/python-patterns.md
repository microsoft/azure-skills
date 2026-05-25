# Python FAOS (Foundry Agent Optimization Service) Optimization Patterns

These patterns are framework-neutral. Use them to expose Python agent behavior knobs to FAOS while preserving the app's current runtime.

## Base Contract

Use this when there is one clear instructions/model surface.

```python
import os

from agent_optimization import load_config

SYSTEM_PROMPT = """You are a helpful assistant."""

config = load_config(
    default_instructions=SYSTEM_PROMPT,
    default_model=os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4.1"),
    default_skills_dir="skills",
)
```

Then map the resolved values into the existing framework:

```python
instructions = config.compose_instructions()
model = config.model or os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4.1")
```

Only apply temperature if the framework supports it:

```python
options = {}
if config.temperature is not None:
    options["temperature"] = config.temperature
```

## Multi-Agent Named Targets

When a Python app has multiple agents, use names that match the architecture rather than one generic `config`.

```python
orchestrator_config = load_config(
    default_instructions=ORCHESTRATOR_PROMPT,
    default_model=os.getenv("ORCHESTRATOR_MODEL_DEPLOYMENT_NAME", os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4.1")),
    default_skills_dir="skills/orchestrator",
)

tool_agent_config = load_config(
    default_instructions=TOOL_AGENT_PROMPT,
    default_model=os.getenv("TOOL_AGENT_MODEL_DEPLOYMENT_NAME", os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4.1")),
    default_skills_dir="skills/tool-agent",
)
```

Use the evaluator objective to choose which named target to add first. For example, `intent_resolution` usually points to `orchestrator_config`, while `builtin.tool_call_accuracy` often points to `tool_agent_config`.

## Microsoft Agent Framework

Keep the current hosting adapter and agent construction. Replace only the selected knobs.

```python
agent = Agent(
    client=client,
    instructions=config.compose_instructions(),
    tools=existing_tools,
    default_options=default_options,
)
```

For model selection:

```python
client = FoundryChatClient(
    project_endpoint=project_endpoint,
    model=config.model or os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4.1"),
    credential=credential,
)
```

If the model client is shared by multiple agents, flag this as a global side effect in the review summary.

If the runtime should advertise local file-based skills, load `config.skills_dir` before composing instructions:

```python
from pathlib import Path

from agent_optimization._config import _load_skills_from_dir

if not config.skills and config.skills_dir:
    config.skills.extend(_load_skills_from_dir(Path(config.skills_dir)))
instructions = config.compose_instructions()
```

Patch optimized tool descriptions only on safe metadata surfaces:

```python
for tool_fn in existing_tools:
    overrides = config.tool_definitions.get(getattr(tool_fn, "__name__", ""))
    if overrides and "description" in overrides:
        tool_fn.__doc__ = overrides["description"]
```

## FastAPI or Custom Responses Runtime

Keep the existing HTTP contract. Use config values where the model call is created.

```python
instructions = body.get("instructions", config.compose_instructions())
model = body.get("model", config.model or os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4.1"))
```

When the app already supports request-level overrides, preserve them and use FAOS config as the default.

## LangGraph or Workflow Runtimes

Do not rewrite the graph. Identify node-level prompts and model clients.

- Router/planner nodes are good targets for `intent_resolution`.
- Tool nodes are good targets for `builtin.tool_call_accuracy`.
- Final synthesis nodes are good targets for `relevance`, style, and task adherence.

Prefer node-specific config names:

```python
router_config = load_config(
    default_instructions=ROUTER_PROMPT,
    default_model=default_model,
)
```

## Optional Skill Support

`default_skills_dir="skills"` records the default skill location. It does not automatically make the runtime load files or expose skill tools unless the app explicitly loads `config.skills_dir` as shown above.

Add file-based skill support only when the target framework has a safe tool-calling or plugin mechanism. If adding it, use progressive disclosure:

1. Startup prompt contains skill name and description only
2. Model calls a tool such as `load_skill` to load full skill instructions
3. Model calls a file-reading tool only for deep skill assets when needed

Do not append every `SKILL.md` body into every agent prompt by default, especially in multi-agent architectures.

## Dependency Guidance

Add dependencies only when needed:

```text
python-dotenv>=1.0.0
azure-identity>=1.19.0
```

Use `python-dotenv` when local `.env` support exists. Use `azure-identity` when the local resolver uses Entra tokens.

## Environment Variables

The canonical local `agent_optimization` package uses hosted-agent-safe `OPTIMIZATION_*` variables first:

| Variable | Purpose |
| -------- | ------- |
| `OPTIMIZATION_CONFIG` | Inline JSON config |
| `OPTIMIZATION_CANDIDATE_ID` | Candidate identifier |
| `OPTIMIZATION_RESOLVE_ENDPOINT` | Resolver API base URL |
| `OPTIMIZATION_LOCAL_DIR` | Local candidate directory |
| `AGENT_OPTIMIZATION_CONFIG` | Backward-compatible inline JSON |

Do not add all of these to `agent.yaml` by default. Hosted agent vNext reserves `AGENT_*` variables in user-authored deployment payloads. Add only non-reserved variables needed by the workflow, usually `OPTIMIZATION_LOCAL_DIR` or `OPTIMIZATION_CONFIG`.

## Local Candidate Directory

Use `OPTIMIZATION_LOCAL_DIR=.agent_optimization` for local or demo workflows without a resolver service. The local fallback expects this metadata layout. Resolver flows may persist `config.json`, but do not rely on it unless the package explicitly loads it.

```text
.agent_optimization/
  baseline/
    metadata.yaml
    instructions.md
    tools.json
  <candidate-id>/
    metadata.yaml
    instructions.md
    tools.json
    skills/<skill-name>/SKILL.md
```

Keep loader priority explicit: inline `OPTIMIZATION_CONFIG`, resolver candidate, local directory, then defaults.

## Canonical Local Package

When the target repository does not already provide an optimization package, add this split-file package rather than a single-file loader:

```text
agent_optimization/
    __init__.py
    _config.py
    _resolver.py
```

`__init__.py` should only re-export the public API:

```python
"""Agent optimization config loader for hosted agents."""

from agent_optimization._config import OptimizationConfig, Skill, load_config

__all__ = ["OptimizationConfig", "Skill", "load_config"]
__version__ = "0.1.0"
```

`_config.py` owns `Skill`, `OptimizationConfig`, `load_config`, default fallback behavior, inline config parsing, local directory loading, and candidate config handoff.

`_resolver.py` owns candidate resolution, using `OPTIMIZATION_RESOLVE_ENDPOINT`, `{endpoint}/candidates/{candidate_id}/config` for resolved config, optional skill-file download from the candidate manifest, and `DefaultAzureCredential` with the `https://ml.azure.com/.default` scope.

## Verification Checklist

- Changed Python files compile
- `from agent_optimization import load_config` succeeds from the agent root
- `load_config(default_instructions="x", default_model="m")` returns defaults when no optimization env vars are set
- Existing entrypoint, hosting adapter, and protocol remain unchanged
- Multi-agent targets are named and documented
- Evaluator objective influenced the target selection or was explicitly unavailable
- User is asked to review before deployment
