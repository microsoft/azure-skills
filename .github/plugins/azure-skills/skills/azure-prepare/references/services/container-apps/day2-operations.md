# Container Apps Day-2 Operations

Operational tasks for running Container Apps in production: restart, exec, logs, environment updates, and secret rotation.

## Restart and Lifecycle

| Action | Command |
|--------|---------|
| Restart active revision | `az containerapp revision restart -n $APP -g $RG --revision $REV` |
| Scale to zero (stop) | `az containerapp update -n $APP -g $RG --min-replicas 0 --max-replicas <current-max>` |
| Resume (restore scaling) | `az containerapp update -n $APP -g $RG --min-replicas <previous-min> --max-replicas <current-max>` |
| List replicas | `az containerapp replica list -n $APP -g $RG --revision $REV` |

> 💡 **Tip:** Restarting a revision replaces all running replicas gracefully. No new revision is created.

## Exec into a Container

Open a shell inside a running replica for debugging:

```bash
# Interactive shell
az containerapp exec -n $APP -g $RG --command /bin/sh

# Target a specific replica and container
az containerapp exec -n $APP -g $RG \
  --replica $REPLICA_NAME \
  --container $CONTAINER_NAME \
  --command /bin/sh
```

> ⚠️ **Warning:** Exec sessions are for debugging only. Changes to the container filesystem are lost on restart.

## Log Streaming

### Real-time Logs

```bash
# Stream system logs
az containerapp logs show -n $APP -g $RG --type system --follow

# Stream application (console) logs
az containerapp logs show -n $APP -g $RG --type console --follow

# Filter to a specific revision or replica
az containerapp logs show -n $APP -g $RG \
  --type console --revision $REV --follow
```

### Log Analytics (KQL)

Query historical logs via the Container Apps environment's Log Analytics workspace:

```kql
// Azure Monitor destination (new environments — default)
ContainerAppConsoleLogs
| where ContainerAppName == "my-app"
| where TimeGenerated > ago(1h)
| project TimeGenerated, Log, RevisionName
| order by TimeGenerated desc

// Log Analytics destination (legacy environments)
// ContainerAppConsoleLogs_CL
// | where ContainerAppName_s == "my-app"
// | project TimeGenerated, Log_s, RevisionName_s
```

## Environment Variable Updates

Updating environment variables creates a new revision:

```bash
# Set or update env vars
az containerapp update -n $APP -g $RG \
  --set-env-vars "DB_HOST=newhost.postgres.database.azure.com" \
                 "CACHE_TTL=300"

# Remove an env var
az containerapp update -n $APP -g $RG \
  --remove-env-vars "OLD_SETTING"
```

### Bicep — Env Vars with Secret References

```bicep
configuration: {
  secrets: [
    { name: 'db-password', value: dbPassword }  // or use keyVaultUrl + identity
  ]
}
template: {
  containers: [
    {
      name: 'api'
      image: '${acrName}.azurecr.io/api:latest'
      env: [
        { name: 'DB_HOST', value: dbHost }
        { name: 'DB_PASSWORD', secretRef: 'db-password' }
      ]
    }
  ]
}
```

## Secret Management

### Create and Update Secrets

```bash
# Add a secret (use Key Vault references in production — avoid plaintext secrets)
az containerapp secret set -n $APP -g $RG \
  --secrets "db-password=<secret-value>"

# Reference a Key Vault secret (managed identity required)
az containerapp secret set -n $APP -g $RG \
  --secrets "db-password=keyvaultref:https://myvault.vault.azure.net/secrets/db-pwd,identityref:/subscriptions/.../userAssignedIdentities/my-id"
```

> ⚠️ **Warning:** Avoid passing plaintext secrets on the command line — they may appear in shell history and process listings. Prefer Key Vault references. If you must use plaintext, use shell substitution like `--secrets "key=$(cat secret.txt)"` to avoid literals on the command line.

> 💡 **Tip:** Use Key Vault references instead of plain-text secrets. The Container App pulls the latest value on each new revision or replica start.

### Secret Rotation Workflow

1. Update the secret value in Key Vault
2. Create a new revision to pick up the updated value:
   ```bash
   az containerapp revision copy -n $APP -g $RG
   ```
3. Verify the new revision is healthy
4. Shift traffic to the new revision

> ⚠️ **Warning:** Existing replicas do NOT hot-reload Key Vault references. A new revision or replica restart is required.

## Health Monitoring

| Check | How |
|-------|-----|
| Revision health | `az containerapp revision list -n $APP -g $RG -o table` |
| Replica status | `az containerapp replica list -n $APP -g $RG --revision $REV` |
| System logs | `az containerapp logs show -n $APP -g $RG --type system` |
| Metrics | Azure Monitor → Container Apps → Requests, Replicas, CPU, Memory |

## Common Troubleshooting

| Symptom | Likely Cause | Remediation |
|---------|-------------|-------------|
| Replica crash loop | App startup failure | Check console logs; exec into container |
| 0 replicas running | Scale-to-zero + no traffic | Set `minReplicas: 1` or send a request |
| Env var not updating | Old revision still serving traffic | Verify the latest revision exists, then update ingress traffic weights or route to `latestRevision` |
| Secret value stale | Key Vault ref not refreshed | Create or verify the refreshed revision, then shift traffic to that revision |
| High memory/CPU | Resource limits too low | Update `resources.cpu` / `resources.memory` |
