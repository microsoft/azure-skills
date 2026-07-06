# CLI CRUD and Operations

Use `azd ai routine` for imperative routine CRUD and operations. Every verb accepts `--output json` or `--output table` (default), and `-p <endpoint>` to override the resolved project endpoint.

## Vocabulary: CLI aliases vs. manifest values

A routine is a **trigger** (when it fires) plus an **action** (what it does). There are two spellings for each type: the CLI flags accept a short **alias**, while a `--file` manifest (and `azure.yaml`) use the raw **wire `type:` value**. They mean the same thing.

**Triggers**

| Fires on | `--trigger` alias | manifest `type:` | Key fields |
|----------|-------------------|------------------|------------|
| A single moment (one-shot) | `timer` | `timer` | `at` (ISO 8601 UTC) |
| A recurring cron schedule | `recurring` | `schedule` | `cron_expression`, `time_zone` |
| A GitHub issue event | `github-issue` | `github_issue` | `connection_id`, `owner`, `repository`, `issue_event` |
| A custom external event | `custom` | `custom` | `provider`, `event_name`, `parameters` |

**Actions** — both invoke the target agent; they differ only in which agent protocol is called and which field resumes prior context.

| Invokes the agent using | `--action` alias | manifest `type:` | Resume field |
|-------------------------|------------------|------------------|--------------|
| the agent `responses` protocol | `agent-response` (default) | `invoke_agent_responses_api` | `conversation` |
| the agent `invocations` protocol | `agent-invoke` | `invoke_agent_invocations_api` | `session_id` |

## Create

Put the prompt or payload the routine sends to the agent in `action.input`. What it should contain depends on the action type you chose (the `--action` alias / action `type:` from the table above): when the action is `agent-response` (`invoke_agent_responses_api`), `action.input` is the natural-language prompt; when the action is `agent-invoke` (`invoke_agent_invocations_api`), it is the hosted agent's expected request payload. `azd ai routine create` has **no `--input` flag**, so any routine that needs `action.input` must be created from a manifest:

```yaml
# routine.yaml — the type: fields take the manifest value from the table above
triggers:
  default:
    type: schedule
    cron_expression: "0 * * * *"
action:
  type: invoke_agent_responses_api
  agent_name: my-agent
  input: "Say hi."
```

```bash
azd ai routine create hourly-hello --file routine.yaml
```

Flag-only create works only when the target agent needs no stored input. `--file` and `--trigger` are mutually exclusive.

```bash
# One-shot timer -> agent
azd ai routine create nightly-report \
  --trigger timer --at <YYYY-MM-DDTHH:MM:SSZ> \
  --action agent-response --agent-name my-agent

# Recurring cron schedule
azd ai routine create daily-digest \
  --trigger recurring --cron "0 8 * * *" --time-zone America/New_York \
  --action agent-response --agent-name my-agent \
  --description "Daily 8am digest"

# GitHub issue event -> agent
azd ai routine create triage-on-open \
  --trigger github-issue \
  --connection-id <workspace-connection-id> --owner Azure --repository azure-dev \
  --issue-event opened \
  --action agent-invoke --agent-name triage-agent

# Custom event -> agent
azd ai routine create on-custom-event \
  --trigger custom --provider <provider-id> --event-name <event> \
  --parameters '{"key":"value"}' \
  --action agent-response --agent-name my-agent
```

## Create Flags

| Flag | Applies to | Notes |
|------|------------|-------|
| `--trigger` | all | `timer` \| `recurring` \| `github-issue` \| `custom` (required unless `--file`) |
| `--at` | timer | ISO 8601 UTC datetime, e.g. `<YYYY-MM-DDTHH:MM:SSZ>` |
| `--cron` | recurring | 5-field cron; minimum interval 5 minutes |
| `--time-zone` | recurring | IANA zone, e.g. `America/New_York` (default `UTC`; not valid for timer) |
| `--connection-id`, `--owner`, `--repository`, `--issue-event` | github-issue | all four required; `--issue-event` is `opened` or `closed` |
| `--provider`, `--event-name`, `--parameters` | custom | `--provider` and JSON-object `--parameters` required |
| `--action` | all | `agent-response` (default) \| `agent-invoke` |
| `--agent-name` \| `--agent-endpoint-id` | action | exactly one; identifies the target agent |
| `--conversation-id` | agent-response | continue an existing conversation (preview) |
| `--session-id` | agent-invoke | continue an existing hosted-agent session |
| `--description` | all | free-text description |
| `--enabled` | all | enabled by default; pass `--enabled=false` to create disabled |
| `--force` | all | overwrite an existing routine of the same name (upsert) |

## Read

```bash
azd ai routine list
azd ai routine list --output json

azd ai routine show nightly-report
azd ai routine show nightly-report --output json
```

## Update

`update` changes only the fields you pass; everything else is preserved. Supply named flags and/or a `--file` manifest.

```bash
azd ai routine update daily-digest --cron "30 9 * * *"
azd ai routine update daily-digest --agent-name another-agent --description "New owner"
azd ai routine update daily-digest --file routine.yaml
```

The trigger and action **types** are immutable: `--trigger` / `--action` are rejected on `update`. To change a type, delete the routine and recreate it.

## Delete

```bash
azd ai routine delete daily-digest
azd ai routine delete daily-digest --force
```

Use `--force` for non-interactive deletes, including under `--no-prompt`.

## Routine Operations

```bash
azd ai routine enable daily-digest
azd ai routine disable daily-digest

# Fire a routine once, now
azd ai routine dispatch daily-digest
azd ai routine dispatch daily-digest --input '{"foo":"bar"}'
azd ai routine dispatch daily-digest --async

# Inspect past runs
azd ai routine run list daily-digest
azd ai routine run list daily-digest --top 20 --filter "<odata-filter>"
```

`dispatch --input` is a one-time override for that manual run only; it does not change the routine's stored `action.input`. `dispatch` prints a Dispatch ID and Action Correlation ID — use `run list` to see the resulting status and phase.
