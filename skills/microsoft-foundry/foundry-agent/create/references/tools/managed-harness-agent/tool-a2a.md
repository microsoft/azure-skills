# Agent-to-Agent

Use `a2a_preview` to call another A2A-compatible Agent as a tool.

```yaml
tools:
  - type: a2a_preview
    name: specialist
    description: Handles specialist requests.
    base_url: https://<peer-endpoint>
    agent_card_path: /.well-known/agent-card.json
    project_connection_id: <optional-connection>
```

Same-project or public peers may not need a connection. For an authenticated peer, use a connection supplied by the user or already referenced by the Agent.

Create a remote A2A connection only when explicitly requested:

```bash
azd ai connection create <connection-name> \
  --kind remote-a2a \
  --target "<peer-a2a-endpoint>" \
  --auth-type <user-entra-token-or-agentic-identity> \
  --audience "https://ai.azure.com" \
  --metadata "ApiType=Azure" \
  --metadata "type=custom_A2A" \
  --metadata "AgentCardPath=/agentCard/v1.0" \
  --project-endpoint "<project-endpoint>"
```

Grant the invoking user or Agent identity the **Foundry Agent Consumer** role on the peer project.

The target must already expose an A2A endpoint and Agent Card. For a Foundry peer that does not, follow [Enable Incoming A2A](../../enable-incoming-a2a.md).
