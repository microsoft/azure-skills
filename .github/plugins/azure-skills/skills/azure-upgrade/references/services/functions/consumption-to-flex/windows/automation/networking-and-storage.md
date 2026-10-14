# Networking and Storage

### 4g. Migrate CORS Settings

Get CORS origins from the source app:

```bash
az functionapp cors show --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP> --query allowedOrigins -o tsv
```

Add each origin to the new app (repeat per origin):

```bash
az functionapp cors add --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --allowed-origins <ORIGIN>
```

### 4h. Migrate Custom Domains

List custom domains on the source app (excluding the default `*.azurewebsites.net`):

```bash
az functionapp config hostname list --webapp-name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP> --query "[?!contains(name, 'azurewebsites.net')].name" -o tsv
```

Adding a hostname binding does not update its DNS record or move traffic to the target. Verify domain ownership as described in [Migrate an active DNS name](https://learn.microsoft.com/en-us/azure/app-service/manage-custom-dns-migrate-domain), then attempt to add each domain to the new app (repeat per domain):

```bash
az functionapp config hostname add --webapp-name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --hostname <CUSTOM_DOMAIN>
```

If Azure rejects the binding because the hostname cannot be assigned to both apps, stop and record custom-domain migration as deferred. Do not remove the source binding, change DNS, or alter its certificate during this replication phase.

### 4i. Migrate Access Restrictions

Get access restrictions from the source app:

```bash
az functionapp config access-restriction show --name <SOURCE_APP_NAME> --resource-group <SOURCE_RESOURCE_GROUP> -o json
```

Recreate every explicit main-site rule, preserving its name, action, priority, description, and selector. Skip platform-generated fallback rows with priority `2147483647` (`Allow all` or `Deny all`); default actions are applied separately below.

```bash
az functionapp config access-restriction add --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --rule-name <RULE_NAME> --action <Allow|Deny> --priority <PRIORITY> --description "<DESCRIPTION>" --ip-address <IP_CIDR>
```

Use exactly one selector matching the source rule:

- IP/CIDR: `--ip-address <IP_CIDR>`
- Service tag: `--service-tag <SERVICE_TAG>`
- Virtual-network subnet: `--subnet <SUBNET_RESOURCE_ID>`

If the source has explicit SCM rules and `scmIpSecurityRestrictionsUseMain` is `false`, recreate them with the same command plus `--scm-site true`.

After all explicit rules are present, apply the captured fallback behavior. Set default actions last so the target remains reachable while rules are being added:

```bash
az functionapp config access-restriction set --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> --default-action <MAIN_DEFAULT_ACTION> --scm-default-action <SCM_DEFAULT_ACTION> --use-same-restrictions-for-scm-site <true|false>
```

> ⚠️ **Skill instruction**: Before setting a default action to `Deny`, verify that an explicit allow rule covers the user's smoke-test client and that required deployment traffic can still reach SCM. Use `ask_user` to list the rules and fallback actions being applied. Do not migrate platform-generated fallback rows as ordinary rules.

Verify actions, priorities, selectors, descriptions, default actions, and SCM behavior:

```bash
az functionapp config access-restriction show --name <NEW_APP_NAME> --resource-group <RESOURCE_GROUP> -o json
```
