# Site and Identity Configuration

### 4d. Apply Site Configurations

Apply the site-level settings collected in Step 3a. Each command below corresponds to one field from the `az functionapp config show` output (and one from the SCM basic publishing query). **Run only the commands whose source value was non-null** — skipping a command leaves the new app at its Flex default for that field.

> 💡 Source-of-truth mapping: every value below comes directly from Step 3a. Do not re-query the source app — use the values you already captured.

HTTP/2 (`http20Enabled`):

```bash
az functionapp config set --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --http20-enabled <true|false>
```

Minimum TLS version (`minTlsVersion`, e.g. `1.2` or `1.3`):

```bash
az functionapp config set --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --min-tls-version <MIN_TLS_VERSION>
```

Minimum TLS cipher suite (`minTlsCipherSuite`):

```bash
az functionapp update --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --set siteConfig.minTlsCipherSuite=<MIN_TLS_CIPHER_SUITE>
```

HTTPS-only (`httpsOnly`):

```bash
az functionapp update --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --set httpsOnly=<true|false>
```

Client certificate enabled (`clientCertEnabled`):

```bash
az functionapp update --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --set clientCertEnabled=<true|false>
```

Client certificate mode (`clientCertMode`, one of `Required`, `Optional`, `OptionalInteractiveUser`):

```bash
az functionapp update --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --set clientCertMode=<CLIENT_CERT_MODE>
```

Client certificate exclusion paths (`clientCertExclusionPaths`):

```bash
az functionapp update --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --set clientCertExclusionPaths=<CLIENT_CERT_EXCLUSION_PATHS>
```

SCM basic publishing credentials policy (the `allow` value from Step 3a's `basicPublishingCredentialsPolicies` query):

```bash
az resource update --resource-group <RESOURCE_GROUP> --name scm --namespace Microsoft.Web --resource-type basicPublishingCredentialsPolicies --parent sites/<NEW_APP_NAME> --set properties.allow=<true|false>
```

> ⚠️ **Skill instruction**: For each command above, look at the corresponding field from Step 3a's output. If the value was `null` or the field was absent, **skip that command** — do not pass `null` or an empty string. If all Step 3a site-config values were already at Flex defaults (typically `httpsOnly=true`, `minTlsVersion=1.2`, all others null/false), this entire sub-step is a no-op and may be skipped.

### 4e. Migrate System-Assigned Managed Identity

Check if the source app has a system-assigned identity:

```bash
az functionapp identity show --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP> --query principalId -o tsv
```

> Only proceed with the rest of this step if the principal ID above is non-empty. Save it as `<SOURCE_PRINCIPAL_ID>`.

Enable system identity on the new app:

```bash
az functionapp identity assign --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP>
```

Get the new app's system identity principal ID (save it as `<NEW_PRINCIPAL_ID>`):

```bash
az functionapp identity show --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --query principalId -o tsv
```

List the source app's role assignments — project just the fields needed to recreate them:

```bash
az role assignment list --assignee <SOURCE_PRINCIPAL_ID> --all --query "[].{role:roleDefinitionName, scope:scope}" -o tsv
```

> ⚠️ **Skill instruction**: For **each row** above, run the command below — substitute the row's first column into `<ROLE_NAME>` and the row's second column into `<RESOURCE_ID>`. The new SMI is a different principal than the source, so every assignment must be recreated explicitly; nothing carries over automatically. If 4b.opt already ran, the three storage data-plane roles on `<STORAGE_NAME>` are already assigned — skip those rows to avoid duplicates.
>
> Before recreating a role, determine whether its scope is a retained dependency or a resource replaced by the migration. Recreate retained dependency scopes directly. Do **not** grant the new identity access to the source Application Insights component; if the source uses AAD ingestion, Step [4k](trigger-safety-and-monitoring.md#4k-verify-application-insights-monitoring) grants `Monitoring Metrics Publisher` on the target component instead.
>
> ```bash
> az role assignment create --assignee-object-id <NEW_PRINCIPAL_ID> --assignee-principal-type ServicePrincipal --role "<ROLE_NAME>" --scope "<RESOURCE_ID>"
> ```

### 4f. Migrate User-Assigned Managed Identities

List user-assigned identities on the source app:

```bash
az functionapp identity show --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP> --query userAssignedIdentities -o json
```

Assign each identity to the new app (repeat per identity resource ID):

```bash
az functionapp identity assign --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --identities <IDENTITY_RESOURCE_ID>
```
