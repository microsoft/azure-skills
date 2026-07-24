# Environment Variables & Secrets — Cross-Cutting Rules

Applies to ALL compute targets (App Service, Container Apps, Functions). For Container Apps-specific Bicep patterns (secretRef, identity), see [bicep-container-apps.md](bicep-container-apps.md).

## Environment Variable Value Derivation

> ⛔ **Never invent env var values — derive from the app's config class.** Cross-reference `.env.example`, `.env.sample`, `docker-compose.yml`, and the app's config module. Verify each value:
> 1. **Type validation:** URL-typed fields need valid URLs — not `*` or placeholders
> 2. **Defaults:** Use app defaults unless overriding with deployed URL
> 3. **Required:** Fields without defaults must be provided
>
> **Pitfalls:** `CORS_ORIGINS=["*"]` → invalid for strict validators (use actual URLs). `DATABASE_URL=changethis` → use KV ref. JSON array env vars need Bicep variable escaping:
> ```bicep
> var corsOrigins = '["https://${containerApp.properties.configuration.ingress.fqdn}"]'
> { name: 'CORS_ORIGINS', value: corsOrigins }
> ```

## Key Vault Secret Dependency Chain

> ⛔ **Chicken-and-egg:** CA references KV secrets that don't exist yet at deploy time. KV secret values (DB connection strings, passwords) are only known AFTER IaC creates the database.

**Correct ordering:**
1. **IaC Phase 1:** Key Vault → RBAC → Database → Container App with `secrets: []` (placeholder image, no KV refs yet)
2. **Deploy phase seeds KV:** `az keyvault secret set --vault-name {kv} --name db-connection-string --value {value}`
3. **IaC Phase 2:** Redeploy Bicep with `isPlaceholder=false` → activates KV `secretRef` entries + real image + ACR registries

**IaC pattern — reference secrets by name, gated by `isPlaceholder`:**

> ⛔ **Container Apps:** KV `secretRef` entries MUST be gated behind `isPlaceholder` (see [bicep-container-apps.md](bicep-container-apps.md) § Two-Phase Wiring). Phase 1 deploys with `secrets: []` because the CA's managed identity has no RBAC yet. Phase 2 activates KV refs after RBAC propagates.

```bicep
// Phase 1: secrets: [] (isPlaceholder == true)
// Phase 2: KV secretRef entries activated after RBAC propagates
secrets: isPlaceholder ? [] : [
  {
    name: 'db-connection-string'
    keyVaultUrl: 'https://${keyVault.name}.vault.azure.net/secrets/db-connection-string'
    identity: 'system'
  }
]
```

> ⛔ **Do NOT hardcode secrets in committed files** — not in `main.parameters.json`, `terraform.tfvars`, env vars, or any generated file. (`@secure()` Bicep params ARE the correct way to pass a secret at deploy time — the ban is on committing the value, not on the parameter.) The deploy phase seeds secrets into Key Vault via `az keyvault secret set` after database provisioning — see [code-deployment-appservice.md](../../deploy/references/code-deployment-appservice.md) or [code-deployment-container-apps.md](../../deploy/references/code-deployment-container-apps.md) § Database Post-Deploy.

## Azure Managed Service SSL/TLS Requirements

> ⛔ **Azure managed databases and caches enforce TLS. Local docker-compose configs typically don't.** This mismatch causes container crashes post-deploy.

Check `prereq-output.json.warnings[]` for warnings with `fixPhase: "scaffold"`. Each warning's `fix` field describes the required IaC change. Read the app's config loader for the actual env var name.

> ⛔ **Prefer env var override over code change.** Only modify source if no env override path exists AND user approves.
> ⛔ **Self-review:** If any `fixPhase: "scaffold"` warning exists and IaC lacks the fix → flag as FLAGGED.

## Key Vault Secret Naming

> ⛔ **KV secret names allow only alphanumeric characters and hyphens.** Map env var names: `SECRET_KEY` → `secret-key`, `DATABASE_URL` → `database-url`. Do NOT use underscores — Azure rejects them with `SecretNameInvalid`.

## Compose → Azure PaaS Credential Mapping

> ⛔ **Azure managed databases only create the `administratorLogin` user.** Docker-compose `POSTGRES_USER` / `MYSQL_USER` auto-creates a database user — Azure PostgreSQL/MySQL Flexible Server does NOT. Map compose user env vars to the `administratorLogin` value from your Bicep, not the compose username.
