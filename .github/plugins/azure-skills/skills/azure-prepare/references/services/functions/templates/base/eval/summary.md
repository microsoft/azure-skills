# Base HTTP Template - Eval Summary

## Coverage Status

| Language | Manifest Templates | Eval | Status |
|----------|-------------------|------|--------|
| Python | 5 (Bicep + TF) | [✅](python.md) | ✅ Verified |
| TypeScript | 2 (Bicep) | [✅](typescript.md) | ✅ Verified |
| JavaScript | 2 (Bicep) | — | 📋 AZD template exists |
| C# (.NET) | 4 (Bicep + TF) | — | 📋 AZD template exists |
| Java | 2 (Bicep) | — | 📋 AZD template exists |
| PowerShell | 1 (Bicep) | — | 📋 AZD template exists |

> ⚠️ **Eval cost note:** Each language × trigger eval requires ~5 min of agent runtime. Full matrix (6 languages × 9 triggers) = ~4.5 hours of CI. Python is verified end-to-end; other languages are confirmed available in the [functions template manifest](https://cdn.functions.azure.com/public/templates-manifest/manifest.json) (70 templates, 6 languages). Multi-language eval expansion tracked as follow-up.

## MCP Tool Validation

| Test | Status | Details |
|------|--------|---------|
| `functions_template_get` | ✅ PASS | 2 calls via `azure-functions` MCP tool |
| Template Discovery | ✅ PASS | HTTP templates found for all languages |
| IaC Included | ✅ PASS | Bicep/Terraform infra/ included in projectFiles |
| E2E Agent Test | ✅ PASS | 2 `azure-functions` calls per language, templates retrieved and applied |

## Results

| Test | Python | TypeScript |
|------|--------|------------|
| Syntax Valid | ✅ | ✅ |
| Health Endpoint | ✅ | ✅ |
| HTTP Trigger | ✅ | ✅ |
| Code Indicator | ✅ `app.route` | ✅ `app.http` |
| Template Scaffolded | `http-trigger-python-azd` | `http-trigger-typescript-azd` |

## Notes

- Templates retrieved via `functions_template_get(language: "<language>", template: "<template-name>")` MCP tool
- Base HTTP template provides the foundation for all recipes
- All recipes compose on top of this base

## Test Date

2026-04-22
