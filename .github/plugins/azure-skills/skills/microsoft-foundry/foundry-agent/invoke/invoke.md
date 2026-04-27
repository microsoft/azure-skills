# Invoke Foundry Agent

Invoke and test deployed agents in Azure AI Foundry with single-turn and multi-turn conversations.

## Quick Reference

| Property | Value |
|----------|-------|
| Agent types | Prompt (LLM-based), Hosted |
| MCP server | `azure` |
| Key Foundry MCP tools | `agent_invoke`, `agent_get` |
| Conversation support | Single-turn and multi-turn (via `conversationId`) |
| Session support | Sticky sessions for hosted agents (via client-generated `sessionId`) |

## When to Use This Skill

- Send a test message to a deployed agent
- Have multi-turn conversations with an agent
- Test a prompt agent immediately after creation
- Test a hosted agent after deployment
- Verify an agent responds correctly to specific inputs

## MCP Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `agent_invoke` | Send a message to an agent and get a response | `projectEndpoint`, `agentName`, `inputText` (required); `agentVersion`, `conversationId`, `sessionId` |
| `agent_get` | Get agent details to verify existence and type | `projectEndpoint` (required), `agentName` (optional) |

## Workflow

### Step 1: Verify Agent Readiness

Delegate the readiness check to a sub-agent. Provide the project endpoint and agent name, and instruct it to:

**Prompt agents** → Use `agent_get` to verify the agent exists.

**Hosted agents** → Use `agent_get` to verify the agent exists and that the targeted version is available for invocation. If a specific version is supplied, verify that version is `active` before continuing.

### Step 2: Invoke Agent

Use the project endpoint and agent name from the project context (see Common: Project Context Resolution). Ask the user only for values not already resolved.

Use `agent_invoke` to send a message:
- `projectEndpoint` — AI Foundry project endpoint
- `agentName` — Name of the agent to invoke
- `inputText` — The message to send

**Optional parameters:**
- `agentVersion` — Target a specific agent version
- `conversationId` — Continue an existing conversation
- `sessionId` — MANDATORY for hosted agents; include the session ID to maintain sticky sessions with the same compute resource

#### Session Support for Hosted Agents

Hosted agents accept a 25 character alphanumeric `sessionId` parameter. Sessions are **sticky**: they route the request to the same underlying compute resource, so the agent can reuse state stored on that compute across multiple turns.

Rules:
1. You MUST generate a unique `sessionId` before making the first `agent_invoke` call.
2. If you have a session ID, you MUST include it in every subsequent `agent_invoke` call for that conversation.
3. When the user explicitly requests a new session, create a new `sessionId` and use it for the rest of the `agent_invoke` calls.

This is different from `conversationId`, which tracks conversation history. `sessionId` controls which compute instance handles the request.

If hosted-agent invocation fails with a permission-related error, read and follow the [troubleshoot skill](../troubleshoot/troubleshoot.md). Verify that `Azure AI User` is assigned to the per-agent identity and the project-level agent identity at the Cognitive Services account scope.

#### Fallback for Hosted Agents Using `invocations` Protocol Only

Use this fallback only when the target hosted agent is deployed with the `invocations` protocol and `agent_invoke` does not work correctly for that agent. Do not use this fallback for prompt agents or hosted agents using the `responses` protocol.

Use `az rest` for this fallback. Azure CLI injects the Entra bearer token automatically after `az login`.

1. Call the hosted agent runtime endpoint directly:

```text
POST {projectEndpoint}/agents/{agentName}/endpoint/protocols/invocations?api-version=v1&session_id={sessionId}
```

- `projectEndpoint` — For example, `https://<resource>.services.ai.azure.com/api/projects/<project>`
- `agentName` — The deployed hosted agent name
- `sessionId` — A 25 character alphanumeric session ID. This enables sticky routing to the same compute instance and should be reused across turns in the same session.

2. Send these required headers:

| Header | Value | Notes |
|--------|-------|-------|
| `Authorization` | `Bearer {token}` | Required. When using `az rest`, Azure CLI adds this automatically if you pass `--resource https://ai.azure.com` |
| `Content-Type` | `application/json` | Required |
| `Foundry-Features` | `HostedAgents=V1Preview` | Required for this endpoint; requests can return `403` without it |

3. Send a JSON body that matches what the agent code expects to parse on the `invocations` endpoint. The payload shape is defined by the agent implementation, not by a fixed protocol-level request schema.

Example if the agent expects a `message` field:

```bash
az rest \
  --method post \
  --url "https://<resource>.services.ai.azure.com/api/projects/<project>/agents/<agentName>/endpoint/protocols/invocations?api-version=v1&session_id=<sessionId>" \
  --resource "https://ai.azure.com" \
  --headers "Foundry-Features=HostedAgents=V1Preview" "Content-Type=application/json" \
  --body '{"message":"Hello"}'
```

Key notes:

- This fallback applies only to hosted agents that implement the `invocations` protocol.
- `api-version` must be `v1`, not a date-based API version.
- The runtime path is `.../endpoint/protocols/invocations`, not `.../agents/{name}:invoke`.
- The `Foundry-Features: HostedAgents=V1Preview` header is mandatory for this endpoint.
- The JSON body must match the shape that the hosted agent implementation actually parses.
- When using `az rest`, include `--resource https://ai.azure.com` so Azure CLI requests the correct token audience for Foundry.
- Reuse the same `session_id` for multi-turn calls that must stay on the same compute instance.

### Step 3: Multi-Turn Conversations

For follow-up messages, pass the `conversationId` from the previous response to `agent_invoke`. This maintains conversation context across turns.

Each invocation with the same `conversationId` continues the existing conversation thread.

## Agent Type Differences

| Behavior | Prompt Agent | Hosted Agent |
|----------|--------------|--------------|
| Readiness | Immediate after creation | Ready after deployment once the target version is active |
| Pre-check | `agent_get` to verify existence | `agent_get` to verify existence and active version |
| Routing | Automatic | Sticky routing via required `sessionId` |
| Multi-turn | ✅ via `conversationId` | ✅ via `conversationId` plus sticky `sessionId` |

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| Agent not found | Invalid agent name or project endpoint | Use `agent_get` to list available agents and verify name |
| Hosted agent not active | The requested hosted agent version is still provisioning or failed | Use `agent_get` to inspect version status, then follow the troubleshoot skill if it does not become `active` |
| Invocation failed | Model error, timeout, or invalid input | Check agent logs, verify model deployment is active, retry with simpler input |
| `agent_invoke` fails for an `invocations` protocol hosted agent | Current MCP tool path does not work correctly for that protocol | Use the direct REST fallback in Step 2 against `.../endpoint/protocols/invocations` with `api-version=v1`, a sticky `session_id`, and `Foundry-Features: HostedAgents=V1Preview` |
| Invocation failed with permission error | Missing or incorrect invocation RBAC for the per-agent identity or project-level agent identity | Read and follow the troubleshoot skill, verify `Azure AI User` on the per-agent identity and project-level agent identity at the Cognitive Services account scope, then retry invocation |
| Conversation ID invalid | Stale or non-existent conversation | Start a new conversation without `conversationId` |
| Rate limit exceeded | Too many requests | Implement backoff and retry, or wait before sending next message |

## Additional Resources

- [Foundry Hosted Agents](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/concepts/hosted-agents?view=foundry)
- [Foundry Agent Runtime Components](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/concepts/runtime-components?view=foundry)
- [Foundry Samples](https://github.com/azure-ai-foundry/foundry-samples)
