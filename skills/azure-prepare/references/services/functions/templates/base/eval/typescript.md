# Base HTTP Template - TypeScript Eval

## MCP Template Validation

| Criteria | Expected | Status |
|----------|----------|--------|
| Template discovery | `functions_template_get(language: "typescript")` returns list | ✅ PASS |
| Template scaffolded | `http-trigger-typescript-azd` | ✅ PASS |
| Has trigger code | `app.http` trigger in output | ✅ PASS |
| Has IaC | `projectFiles[]` includes Bicep | ✅ PASS |

## Agent Behavior Validation

```text
1. Agent calls: functions_template_get(language: "typescript")
2. Agent scans templateList for HTTP trigger templates
3. Agent selects: http-trigger-typescript-azd
4. Agent calls: functions_template_get(language: "typescript", template: "http-trigger-typescript-azd")
5. Agent writes: functionFiles[] + projectFiles[]
```

## Code Indicators Verified

- `app.http` trigger pattern (V4 model)
- TypeScript compilation successful (`npm install` + `tsc`)
- HTTP trigger with request/response handling

## Test Date

2026-04-22

## Verdict

**PASS** - MCP template provides complete TypeScript HTTP trigger with IaC and V4 programming model.
