# MCP Server Recipe - Python Eval

## MCP Template Validation

| Criteria | Expected | Status |
|----------|----------|--------|
| Template discovery | `functions_template_get(language: "python")` returns list | ✅ PASS |
| Filter by resource | `resource == "mcp"` finds matches | ✅ PASS |
| Template scaffolded | `mcp-server-remote-python` | ✅ PASS |
| Has trigger code | HTTP trigger with JSON-RPC handler in output | ✅ PASS |
| Has IaC | `projectFiles[]` includes Bicep | ✅ PASS |

## Agent Behavior Validation

```text
1. Agent calls: functions_template_get(language: "python")
2. Agent scans templateList.triggers[] descriptions and resource field
3. Agent selects: template where resource == "mcp" → mcp-server-remote-python
4. Agent calls: functions_template_get(language: "python", template: "mcp-server-remote-python")
5. Agent writes: functionFiles[] + projectFiles[]
```

## Code Indicators Verified

- HTTP trigger endpoint for JSON-RPC 2.0 protocol
- `tools/list` returns tool definitions with schemas
- `tools/call` executes tools and returns results
- Ready for AI agent integration (Copilot, Claude, etc.)

## Test Date

2026-04-22

## Verdict

**PASS** - MCP template provides complete remote MCP server with JSON-RPC endpoint and IaC.
