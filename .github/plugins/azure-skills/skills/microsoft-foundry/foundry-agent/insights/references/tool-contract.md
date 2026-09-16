# Agent Insights MCP Contract

Discover `agent_insights_get` through the Azure MCP `foundry` tool. It resolves the named agent's **existing** monitor and returns one unchanged page of generated insights. It does not generate fresh findings.

## Inputs

| Parameter | Required | Meaning |
|-----------|----------|---------|
| `projectEndpoint` | Yes | Foundry project URL: `https://<account>.services.ai.azure.com/api/projects/<project>`; use the actual endpoint for the target cloud, not a portal URL |
| `agentName` | Yes | Exact agent name, not a monitor ID or `name:version` |
| `category` | No | Supported category filter; omit unless requested |
| `severity` | No | Supported severity filter, for example `low`, `medium`, `high` |
| `status` | No | `active`, `resolved`, or `ignored`; `open` is invalid |
| `includeDetails` | No | Expanded evidence/remediation; service default `false`, workflow default `true` |
| `order` | No | Creation-time order: `asc` or `desc`; default `desc` |
| `after` | No | Previous page's `last_id` when `has_more` is true |
| `limit` | No | Page size 1-100; service default 20, workflow default 100 |

Use only schema-supported parameters. Do not translate a request for fresh analysis into this retrieval call.

```javascript
// Azure MCP router; use the host's discovered name for the foundry tool.
foundry({
  intent: "Read generated agent insights with evidence",
  command: "agent_insights_get",
  parameters: {
    projectEndpoint: "https://<account>.services.ai.azure.com/api/projects/<project>",
    agentName: "<agent-name>",
    includeDetails: true,
    order: "desc",
    limit: 100
  }
});
```

For a directly exposed `agent_insights_get` tool, pass the inputs without the router wrapper. For subsequent pages, add `after` and retain the other inputs. Honor requested filters and total-result limits as described in the [workflow](../insights.md).

## Output

Pagination fields are **snake_case**:

```json
{
  "data": [
    {
      "id": "insight_example",
      "agent_name": "example-agent",
      "agent_version": "1",
      "title": "Handle tool failures",
      "category": "quality",
      "severity": "high",
      "status": "active",
      "description": "A generated finding."
    }
  ],
  "first_id": "insight_example",
  "last_id": "insight_example",
  "has_more": true
}
```

This abbreviated example omits `details`. With `includeDetails: true`, inspect available `details.highlighted_traces`, `details.linked_traces`, and `details.recommended_actions.proposed_fix`. Preserve returned trace IDs and evidence; do not manufacture missing fields. Proposed fixes are recommendations, not permission to modify code or prompts.

## Errors

| Result | Required handling |
|--------|-------------------|
| Successful empty `data`, `has_more: false` | Report no matching generated insights; do not infer health |
| No monitor found | Explain that an existing monitor is required; do not create one |
| Tool unavailable | Stop and report MCP availability/discovery failure |
| Invalid argument/filter | Show the actionable error and correct only supported inputs; do not silently drop filters |
| Authentication/authorization failure | Report the failure; do not change permissions |
| Backend/network failure | Report failure, or explicitly partial results if earlier pages succeeded |
| Malformed page or missing/repeated continuation cursor | Stop; mark retrieval incomplete rather than looping or returning false success |
