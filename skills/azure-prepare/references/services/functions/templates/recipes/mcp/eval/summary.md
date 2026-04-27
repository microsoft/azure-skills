# Eval Summary

## Coverage Status

| Language | Manifest Templates | Eval | Status |
|----------|-------------------|------|--------|
| Python | 3 (Bicep) | ✅ | ✅ Verified |
| TypeScript | 2 (Bicep) | — | 📋 AZD template exists |
| C# (.NET) | 2 (Bicep) | — | 📋 AZD template exists |
| Java | 2 (Bicep) | — | 📋 AZD template exists |
| JavaScript | — | — | ⚠️ No AZD template |
| PowerShell | — | — | ⚠️ No AZD template |

> ⚠️ **Eval cost note:** Each language eval requires ~5 min of agent runtime. Python is verified end-to-end; other languages confirmed in [manifest](https://cdn.functions.azure.com/public/templates-manifest/manifest.json). JavaScript and PowerShell have no MCP AZD template. Multi-language eval expansion tracked as follow-up.

## MCP Tool Validation

| Test | Status | Details |
|------|--------|---------|
| `functions_template_get` | ✅ PASS | 2 calls via `azure-functions` MCP tool |
| Template Discovery | ✅ PASS | Templates found via resource filter |
| IaC Included | ✅ PASS | Storage queue config in projectFiles |
| E2E Agent Test | ✅ PASS | 2 `azure-functions` calls, template `mcp-server-remote-python` retrieved and applied |

## Results

| Test | Python |
|------|--------|
| Health | ✅ |
| tools/list | ✅ |
| tools/call | ✅ |

## Notes

- Templates retrieved via `functions_template_get(language: "<language>", template: "<template-name>")` MCP tool
- Requires `enableQueue: true` for MCP state management
- Uses JSON-RPC 2.0 protocol over HTTP

## Test Date

2026-04-22
