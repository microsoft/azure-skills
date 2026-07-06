# Declarative Routines

The routines extension registers a service target so routines can live in source control and be upserted by `azd up` / `azd deploy`. Declare each routine as a service with `host: azure.ai.routine`: the **service key is the routine name**, and the keys under it bind directly to the routine model.

```yaml
# azure.yaml
services:
  my-agent:
    host: azure.ai.agent
    # ... agent service block ...

  daily-digest:                 # service key = routine name
    host: azure.ai.routine
    uses:
      - my-agent                # order the agent ahead of the routine that invokes it
    description: Daily 8am digest
    enabled: true
    triggers:
      default:
        type: schedule          # recurring cron; see type table below
        cron_expression: "0 8 * * *"
        time_zone: America/New_York
    action:
      type: invoke_agent_responses_api   # see type table below
      agent_name: my-agent      # target agent (distinct from the routine name)
      input: "Summarize activity for ${AZURE_ENV_NAME}"
```

Then:

```bash
azd deploy daily-digest --no-prompt
azd up
```

## Trigger and action `type` values

`azure.yaml` (like a `--file` manifest) uses the raw wire `type:` value, **not** the CLI alias:

- Trigger `type`: `schedule` (recurring cron), `timer` (one-shot), `github_issue`, or `custom`.
- Action `type`: `invoke_agent_responses_api` (resume with `conversation`) or `invoke_agent_invocations_api` (resume with `session_id`).

The `azd ai routine` CLI accepts friendlier aliases (`recurring`, `github-issue`, `agent-response`, `agent-invoke`) for the same values. See the full alias-to-wire mapping and per-trigger key fields in [CLI CRUD and Operations](cli-crud.md#vocabulary-cli-aliases-vs-manifest-values).

## `action.input`

Put the prompt or payload sent to the agent in `action.input`:

- `invoke_agent_responses_api` (`agent-response`): a string prompt.
- `invoke_agent_invocations_api` (`agent-invoke`): an object/array/scalar matching the target agent's expected input.

## Behavior notes

- `azd deploy` PUTs the routine idempotently; package and publish are no-ops (a routine has no build artifact).
- The routine name always comes from the service key; any `name:` inside the block is ignored.
- Put the target agent service in `uses:` so azd orders the agent before the routine that invokes it.
- String values resolve `${VAR}` against the active azd env at deploy time; Foundry server-side `${{...}}` expressions are left untouched.
- Removing the service block stops azd managing the routine but does **not** delete it from Foundry. Delete explicitly with `azd ai routine delete <name>`.
