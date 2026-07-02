# Guardrails (RAI Content-Filter Policies)

Guardrails are Responsible AI (RAI) content-filter policies that control what content is allowed through model deployments and agents in Microsoft Foundry.

## When to Use

- Create or manage a guardrail (content-filter policy) for a Foundry project
- Attach a guardrail to a hosted agent, model deployment, or toolbox → [guardrail-attach.md](guardrail-attach.md)
- Create a guardrail via REST API → [guardrail-api-create.md](guardrail-api-create.md)

## Default Path: Portal

By default, guide the user to the Foundry portal to create guardrails interactively.

**Construct and show this URL to the user:**

```
https://ai.azure.com/nextgen/r/{encodedSubId},{resourceGroup},,{accountName},{projectName}/build/guardrails
```

Where:
- `{encodedSubId}` — subscription GUID as URL-safe base64 (no `=` padding):
  ```bash
  python -c "import base64,uuid;print(base64.urlsafe_b64encode(uuid.UUID('<SUBSCRIPTION_ID>').bytes).rstrip(b'=').decode())"
  ```
- `{resourceGroup}` — resource group name
- `{accountName}` — AI Services account name
- `{projectName}` — Foundry project name

If resource details are unknown, use the generic URL and instruct the user to navigate manually:

```
https://ai.azure.com
```

Then navigate: select your project → **Build** → **Guardrails** → **Create Guardrail**.

> Use the API path ([guardrail-api-create.md](guardrail-api-create.md)) only when the user explicitly asks for programmatic/CLI/CI/CD creation.

## Intervention Points

| Intervention Point | Models | Agents (Preview) | Toolbox |
|---|---|---|---|
| User input | Yes | Yes | No |
| Tool call | No | Yes | Yes |
| Tool response | No | Yes | Yes |
| Output | Yes | Yes | No |

Tool call and tool response are agent-only (and toolbox). An agent's guardrail fully overrides its model deployment's guardrail at all intervention points.

## Default Guardrails

| Policy Name | Description | Editable |
|-------------|-------------|----------|
| `Microsoft.Default` | Base default policy (4 categories) | No |
| `Microsoft.DefaultV2` | Updated default with jailbreak + protected material | No |
| Custom policies | User-created policies | Yes |

