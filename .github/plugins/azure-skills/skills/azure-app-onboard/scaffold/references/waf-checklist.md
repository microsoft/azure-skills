# WAF Checklist

Per-pillar Well-Architected Framework alignment for AppOnboard-generated infrastructure. Use during scaffold self-review (Layer 4) and prepare validation (WAF Alignment dimension).

> **Reference:** [Azure Well-Architected Framework](https://learn.microsoft.com/en-us/azure/well-architected/) — link, don't duplicate. See [WAF Service Guides](https://learn.microsoft.com/en-us/azure/well-architected/service-guides/) for per-service checklists.

## Reliability

- Zone redundancy enabled for production SKUs (App Service P1v3+, SQL Premium, Redis Premium)
- Health probes configured (Container Apps liveness/readiness, App Service `/health`)
- GRS storage for production data (Standard_GRS or RA-GRS)
- Retry policies in application code for transient failures
- Min replicas ≥ 1 for production Container Apps (no cold-start)

## Security

- System-assigned managed identity on all services
- Key Vault for all secrets (no inline connection strings)
- HTTPS-only + TLS 1.2+ on all endpoints
- No public blob access on storage accounts
- Private endpoints where budget allows (balanced/performance tiers)
- No `administratorLogin` for SQL (Entra-only auth)

## Cost Optimization

- SKU matches `prepare-plan.json` budget tier — no over-provisioning
- Scale-to-zero enabled for dev/test Container Apps
- Free tier grants applied in cost estimate (see [pricing-guide.md](../../prepare/references/pricing-guide.md) § Free Grants Summary)
- Reserved instances noted as option for production (don't auto-apply)

## Operational Excellence

- `diagnostic-settings` is not scaffolded; if the generator added one it MUST be gated behind `enableDiagnostics` (default `false`) or absent — never wired unconditionally (that blocks the first deploy).
- Application Insights connected for APM
- Resource tagging: `app-onboard-skill`, `app-onboard-session-id`, `created-at` (see `bicep-patterns.md` § Service Tagging or `terraform-patterns.md` § Resource Tags)
- All configurable values parameterized (no hardcoded regions, names, SKUs)

## Performance Efficiency

- Autoscale rules for production SKUs (Container Apps max replicas, App Service auto-scale)
- CDN for static assets when SPA frontend detected
- Connection pooling for database access
- Appropriate cache tier (Redis) when session/cache pattern detected
