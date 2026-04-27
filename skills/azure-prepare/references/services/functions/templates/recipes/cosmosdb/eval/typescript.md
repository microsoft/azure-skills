# Cosmos DB Recipe - TypeScript Eval

## MCP Template Validation

| Criteria | Expected | Status |
|----------|----------|--------|
| Template discovery | `functions_template_get(language: "typescript")` returns list | ✅ PASS |
| Filter by resource | `resource == "cosmos"` finds matches | ✅ PASS |
| Template scaffolded | `cosmos-trigger-typescript-azd` | ✅ PASS |
| Has trigger code | `app.cosmosDB` trigger binding in output | ✅ PASS |
| Has IaC | `projectFiles[]` includes Bicep | ✅ PASS |
| Has RBAC | Cosmos DB Data Contributor role | ✅ PASS |

## Agent Behavior Validation

```text
1. Agent calls: functions_template_get(language: "typescript")
2. Agent scans templateList.triggers[] descriptions and resource field
3. Agent selects: template where resource == "cosmos" → cosmos-trigger-typescript-azd
4. Agent calls: functions_template_get(language: "typescript", template: "cosmos-trigger-typescript-azd")
5. Agent writes: functionFiles[] + projectFiles[]
```

## Code Indicators Verified

- `app.cosmosDB` trigger binding (V4 model)
- TypeScript compilation successful (`npm install` + `tsc`)
- Cosmos DB with managed identity and proper RBAC assignments
- Infrastructure uses `Microsoft.DocumentDB`

## Test Date

2026-04-22

## Verdict

**PASS** - MCP template provides complete TypeScript Cosmos DB trigger with IaC, RBAC, and UAMI binding.
