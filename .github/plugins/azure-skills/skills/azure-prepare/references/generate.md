# Artifact Generation

Generate infrastructure and configuration files based on selected recipe.

## CRITICAL: Check for Special Patterns First

**Before manual generation, check if the project uses patterns that require `azd init --from-code -e <environment-name>`:**

| Pattern | Detection | Action |
|---------|-----------|--------|
| **.NET Aspire** | `*.AppHost.csproj` or `Aspire.Hosting` package | Use `azd init --from-code -e <environment-name>` → [aspire.md](aspire.md) |
| **Complex existing codebase** | Multiple services, existing structure | Consider `azd init --from-code -e <environment-name>` |

> ⚠️ **For .NET Aspire projects:** Do NOT manually create azure.yaml. Use `azd init --from-code -e <environment-name>` instead to auto-detect the AppHost. **The `-e` flag is required for non-interactive environments.** See [aspire.md](aspire.md) for details.
>
> **CRITICAL:** After running `azd init --from-code`, you **MUST** immediately set the user-confirmed subscription with `azd env set AZURE_SUBSCRIPTION_ID <id>`. Do NOT skip this step. See [aspire.md](aspire.md) Step 3 for the complete sequence.

## CRITICAL: Research Must Be Complete

**DO NOT generate any files without first completing the [Research Components](research.md) step.**

The research step loads service-specific references and invokes related skills to gather best practices. Apply all research findings to generated artifacts.

## Research Checklist

1. ✅ Completed [Research Components](research.md) step
2. ✅ Loaded all relevant `services/*.md` references
3. ✅ Invoked related skills for specialized guidance
4. ✅ Documented findings in `.azure/plan.md`

## Generation Order

| Order | Artifact | Notes |
|-------|----------|-------|
| 1 | Application config (azure.yaml) | AZD only—defines services and hosting |
| 2 | Application code scaffolding | Entry points, health endpoints, config |
| 3 | Dockerfiles | If containerized |
| 4 | Infrastructure (Bicep/Terraform) | IaC templates in `./infra/` |
| 5 | CI/CD pipelines | If requested |

## Recipe-Specific Generation

Load the appropriate recipe for detailed generation steps:

| Recipe | Guide |
|--------|-------|
| AZD | [AZD Recipe](recipes/azd/README.md) |
| AZCLI | [AZCLI Recipe](recipes/azcli/README.md) |
| Bicep | [Bicep Recipe](recipes/bicep/README.md) |
| Terraform | [Terraform Recipe](recipes/terraform/README.md) |

## Common Standards

### File Structure

```
project-root/
├── .azure/
│   └── plan.md
├── infra/
│   ├── main.bicep (or main.tf)
│   └── modules/
├── src/
│   └── <component>/
│       └── Dockerfile
└── azure.yaml (AZD only)
```

### Security Requirements

- No hardcoded secrets
- Use Key Vault for sensitive values
- Managed Identity for service auth
- HTTPS only, TLS 1.2+

### Runtime Configuration

Apply language-specific production settings for containerized apps:

| Runtime | Reference |
|---------|-----------|
| Node.js/Express | [runtimes/nodejs.md](runtimes/nodejs.md) |

## After Generation

1. Update `.azure/plan.md` with generated file list
2. Run validation checks
3. Proceed to **azure-validate** skill
