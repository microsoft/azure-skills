# Tool — Agent-to-Agent (A2A) connection

Create the `remote-a2a` connection that lets your agent call another A2A-compatible agent as a tool. The peer can be another Foundry agent or any external service that implements the A2A protocol.

## Create the connection

```bash
azd ai connection create <conn-name> \
  --kind remote-a2a \
  --target <A2A_BASE_URL> \
  --auth-type <auth-type> \
  [--audience <token-audience>] \
  [--key <api-key>] \
  [--metadata KEY=VALUE ...]
```

### Foundry peer

`$TARGET_AGENT_A2A_ENDPOINT` is `https://<account>.services.ai.azure.com/api/projects/<project>/agents/<peer>/endpoint/protocols/a2a`.

> 🚦 **Prerequisite: the target Foundry agent must have incoming A2A enabled** and return 200 on `$TARGET_AGENT_A2A_ENDPOINT/agentCard/v1.0`. If that URL 404s, follow [enable-incoming-a2a.md](enable-incoming-a2a.md) on the peer first.

Grant the **calling** agent's identity the **Foundry Agent Consumer** role (least privilege) on the peer project.

```bash
azd ai connection create $CONNECTION_NAME \
  --project-endpoint $PROJECT_ENDPOINT \
  --kind remote-a2a \
  --target $TARGET_AGENT_A2A_ENDPOINT \
  --auth-type AgenticIdentityToken \
  --audience "https://ai.azure.com" \
  --metadata "ApiType=Azure" \
  --metadata "type=custom_A2A" \
  --metadata "AgentCardPath=/agentCard/v1.0"
```

## References

- [A2A tool documentation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/agent-to-agent)
