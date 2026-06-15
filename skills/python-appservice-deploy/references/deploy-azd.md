# Deploy via `azd`

Use this path when the workspace already has an `azure.yaml` whose service host is `appservice`.

## When to use

| Condition | Use azd? |
|---|---|
| `azure.yaml` exists AND `services.<name>.host: appservice` | ✅ Yes |
| `azure.yaml` exists but targets Container Apps / Functions / etc. | ❌ Hand off to `azure-prepare` |
| No `azure.yaml` | ❌ Use [deploy-azcli.md](deploy-azcli.md) |

## Confirm host target

```bash
# Look for `host: appservice` under services in azure.yaml
grep -E "host:\s*appservice" azure.yaml
```
```powershell
# Look for `host: appservice` under services in azure.yaml
Select-String -Path azure.yaml -Pattern 'host:\s*appservice'
```

If no match → use the az CLI path.

## Authenticate

```bash
azd auth login --check-status || azd auth login
```
```powershell
azd auth login --check-status
if ($LASTEXITCODE -ne 0) { azd auth login }
```

## Provision (first time only)

If no `azd` environment exists in this folder:

```bash
azd env new <env-name>
azd env set AZURE_LOCATION <region>
# Optional: override default SKU via the template's parameters
azd env set APP_SERVICE_SKU P0v3
```

Then provision + deploy in one call:

```bash
azd up
```

## Deploy code only (subsequent deploys)

```bash
azd deploy
```

After `azd deploy` returns, **stop**. Do not run `azd monitor`, `az webapp log tail`, or any HTTP probe.

## Report endpoint to the user

> ⛔ **Do NOT probe the endpoint** (no `curl`, no `Invoke-WebRequest`) and **do NOT tail logs** as a verification step. App Service can take 2–3 minutes after deploy before the site responds.

Read the endpoint from azd without hitting the site:

```bash
# bash
azd env get-values | grep -E '^SERVICE_.*_URI='
```

```powershell
# PowerShell
azd env get-values | Select-String "SERVICE_.*_URI"
```

Present the URL with the `https://` prefix and the post-deploy message from [post-deploy-message.md](post-deploy-message.md), then end the turn.

## Notes

- ⛔ Do **not** run `azd init -t <template>` in an existing workspace — it can destroy user code. Only `azd init` (no template) is safe inside an existing project.
- If `azd up` provisions infra that doesn't match P0v3 Linux, the underlying template owns that decision — don't fight it. Note this to the user.
- If `azd deploy` fails because no environment exists, fall back to `azd env new` then re-run.
