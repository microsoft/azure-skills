# Eval Summary

## Coverage Status

| Language | Manifest Templates | Eval | Status |
|----------|-------------------|------|--------|
| Python | 1 (Bicep) | [✅](python.md) | ✅ Verified |
| TypeScript | 1 (Bicep) | [✅](typescript.md) | ✅ Verified |
| JavaScript | 1 (Bicep) | — | 📋 AZD template exists |
| C# (.NET) | 1 (Bicep) | — | 📋 AZD template exists |
| Java | 1 (Bicep) | — | 📋 AZD template exists |
| PowerShell | 1 (Bicep) | — | 📋 AZD template exists |

> ⚠️ **Eval cost note:** Each language eval requires ~5 min of agent runtime. Python is verified end-to-end; other languages confirmed in [manifest](https://cdn.functions.azure.com/public/templates-manifest/manifest.json). Multi-language eval expansion tracked as follow-up.

## MCP Tool Validation

| Test | Status | Details |
|------|--------|---------|
| `functions_template_get` | ✅ PASS | 2 calls via `azure-functions` MCP tool |
| Template Discovery | ✅ PASS | Templates found via resource filter |
| IaC Included | ✅ PASS | Service Bus Bicep + RBAC in projectFiles |
| E2E Agent Test | ✅ PASS | 2 `azure-functions` calls per language, templates retrieved and applied |

## Results

| Test | Python | TypeScript |
|------|--------|------------|
| Health | ✅ | ✅ |
| Queue message | ✅ | ✅ |
| Output binding | ✅ | ✅ |
| Code Indicator | ✅ `service_bus_queue_trigger` | ✅ `app.serviceBusQueue` |
| Extra Indicator (IaC) | ✅ `Microsoft.ServiceBus` | ✅ `Microsoft.ServiceBus` |
| Template Scaffolded | `servicebus-trigger-python-azd` | `servicebus-trigger-typescript-azd` |

## Notes

- Templates retrieved via `functions_template_get(language: "<language>", template: "<template-name>")` MCP tool
- See README for UAMI troubleshooting (500 error, Unauthorized)

## Test Date

2026-04-22
