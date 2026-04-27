# Service Bus Recipe - Python Eval

## MCP Template Validation

| Criteria | Expected | Status |
|----------|----------|--------|
| Template discovery | `functions_template_get(language: "python")` returns list | ✅ PASS |
| Filter by resource | `resource == "servicebus"` finds matches | ✅ PASS |
| Template scaffolded | `servicebus-trigger-python-azd` | ✅ PASS |
| Has trigger code | `@app.service_bus_queue_trigger` decorator in output | ✅ PASS |
| Has IaC | `projectFiles[]` includes Bicep | ✅ PASS |
| Has RBAC | Service Bus Data Receiver/Sender role | ✅ PASS |

## Agent Behavior Validation

```text
1. Agent calls: functions_template_get(language: "python")
2. Agent scans templateList.triggers[] descriptions and resource field
3. Agent selects: template where resource == "servicebus" → servicebus-trigger-python-azd
4. Agent calls: functions_template_get(language: "python", template: "servicebus-trigger-python-azd")
5. Agent writes: functionFiles[] + projectFiles[]
```

## Code Indicators Verified

- `@app.service_bus_queue_trigger` with queue_name
- `connection="ServiceBusConnection"` (UAMI pattern)
- `ServiceBusConnection__fullyQualifiedNamespace` binding
- Extension bundle v4

## Test Date

2026-04-22

## Verdict

**PASS** - MCP template provides complete Service Bus trigger with IaC, RBAC, and UAMI binding.
