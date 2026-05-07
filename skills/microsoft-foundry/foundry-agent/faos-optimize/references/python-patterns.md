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

`default_skills_dir="skills"` records the default skill location. It does not automatically make the runtime load files or expose skill tools.

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

Supported optimization variables:

| Variable | Purpose |
|----------|---------|
| `AGENT_OPTIMIZATION_CONFIG` | Inline JSON config from the optimization service |
| `OPTIMIZATION_CONFIG` | Non-reserved inline JSON fallback |
| `AGENT_OPTIMIZATION_CANDIDATE_ID` | Candidate identifier to resolve from a service |
| `AGENT_OPTIMIZATION_RESOLVE_ENDPOINT` | Resolver API base URL |
| `AGENT_OPTIMIZATION_SKILLS_DIR` | Download location for candidate skill files |

Do not add all of these to `agent.yaml` by default. Add only the variables required for the user's intended optimization path.

## Verification Checklist

- Changed Python files compile
- `from agent_optimization import load_config` succeeds from the agent root
- `load_config(default_instructions="x", default_model="m")` returns defaults when no optimization env vars are set
- Existing entrypoint, hosting adapter, and protocol remain unchanged
- Multi-agent targets are named and documented
- Evaluator objective influenced the target selection or was explicitly unavailable
- User is asked to review before deployment
