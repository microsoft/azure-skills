# Eval Summary

## Coverage Status

| Language | Manifest Templates | Eval | Status |
|----------|-------------------|------|--------|
| Python | 1 (Bicep) | ✅ | ✅ Verified |
| TypeScript | 1 (Bicep) | — | 📋 AZD template exists |
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
| IaC Included | ✅ PASS | EventGrid + Storage Bicep in projectFiles |
| E2E Agent Test | ✅ PASS | 2 `azure-functions` calls, template `blob-eventgrid-trigger-python-azd` retrieved and applied |

## IaC Validation

| IaC Type | File | Syntax | Policy Compliant | Status |
|----------|------|--------|------------------|--------|
| Bicep | blob.bicep | ✅ | ✅ | PASS |
| Terraform | blob.tf | ✅ | ✅ | PASS |

## Deployment Validation

| Test | Status | Details |
|------|--------|---------|
| AZD Template Init | ✅ PASS | `functions-quickstart-python-azd-eventgrid-blob` |
| AZD Provision | ✅ PASS | Resources created in `rg-blob-eval` |
| AZD Deploy | ✅ PASS | Function deployed to `func-mtgqcoepn4p3w` |
| HTTP Response | ✅ PASS | HTTP 200 from function endpoint |
| Event Grid Topic | ✅ PASS | `eventgridpdftopic` created |
| Storage Account | ✅ PASS | RBAC-only storage provisioned |

## Results

| Test | Python |
|------|--------|
| Health | ✅ |
| Blob trigger | ✅ |
| EventGrid event | ✅ |
| Copy to processed | ✅ |

## Notes

- Templates retrieved via `functions_template_get(language: "<language>", template: "<template-name>")` MCP tool
- Dedicated AZD templates available for all 6 languages
- Uses Event Grid for reliable blob event delivery

## IaC Features

| Feature | Bicep | Terraform |
|---------|-------|-----------|
| Storage Account (RBAC-only) | ✅ | ✅ |
| Event Grid System Topic | ✅ | ✅ |
| Event Grid Subscription | ✅ | ✅ |
| RBAC Assignment | ✅ | ✅ |
| Private Endpoint (VNet) | ✅ | ✅ |
| Azure Policy Compliance | ✅ | ✅ |

## Test Date

2026-04-22
