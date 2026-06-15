# Troubleshooting

## Quick diagnosis flow

```
Deploy failed?
  ├─ Check `az webapp log tail` first
  ├─ Then `az webapp log deployment list` for build-time errors
  ├─ Then `az webapp config show` to verify runtime + startup
  └─ For `Connection reset` / `429` / `502-504` on create commands,
      see [transient-retry.md](transient-retry.md)
```

## Symptom → Cause → Fix

| Symptom | Likely cause | Fix |
|---|---|---|
| `Container ... didn't respond to HTTP pings on port: 8000` | Wrong/missing startup command, or app bound to 127.0.0.1 | Set startup to bind `0.0.0.0:8000` ([startup-commands.md](startup-commands.md)) |
| `ModuleNotFoundError: No module named 'flask'` (or any dep) | Build skipped, deps not installed | `az webapp config appsettings set --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true` then redeploy |
| `gunicorn: command not found` | `gunicorn` missing from `requirements.txt` | Add `gunicorn>=21` to requirements, redeploy |
| Deploy returns 202 but site still shows default page | Async deploy not finished | Wait, or re-run with `--track-status true` to make the CLI block until completion; check `az webapp log deployment list` |
| `OperationNotAllowed: ... requires the plan to be Linux` | Plan was created as Windows | Recreate plan with `--is-linux` ([create-app.md](create-app.md)) |
| `Resource group '<rg>' could not be found` | RG missing | `az group create -n <rg> -l <region>` |
| `An app with name '<app>' already exists` | Global name collision | Pick a different name (App Service host names are globally unique) |
| `az webapp up` shown in user's notes | Deprecated command | Replace with `az webapp create` + `az webapp deploy --type zip` |
| `azd up` provisions Container Apps instead of App Service | azure.yaml host isn't `appservice` | Either fix the template's `host:` or fall back to az CLI path |
| Deployment hangs in "Building..." | Oryx pip install failing on native deps | Run `az webapp log deployment list -n <app> -g <rg>` to find the deployment ID, then `az webapp log deployment show -n <app> -g <rg> --deployment-id <id>`; pin known-good versions in requirements |
| 401 / unauthorized on deploy | `az login` expired or wrong subscription | `az login` + `az account set -s <sub>` |
| `LinuxFxVersion` shows `DOCKER\|...` | Web app was created as custom container | Recreate with `--runtime "PYTHON:3.14"` (colon form is shell-safe) |

## Where logs live

> ⚠️ **Prereq for `az webapp log tail` on a fresh app**: filesystem logging must be enabled, otherwise the stream stays empty. Run **once** after the app is created:
>
> ```bash
> az webapp log config -n <app> -g <rg> \
>   --application-logging filesystem \
>   --web-server-logging filesystem \
>   --level information
> ```
> ```powershell
> az webapp log config -n <app> -g <rg> `
>   --application-logging filesystem `
>   --web-server-logging filesystem `
>   --level information
> ```
>
> `az webapp log deployment list/show` and `az webapp log download` do **not** require this — they read from a different store.

| Log | Command |
|---|---|
| Live stream | `az webapp log tail -n <app> -g <rg>` |
| Deployment history | `az webapp log deployment list -n <app> -g <rg>` |
| Deployment details | `az webapp log deployment show -n <app> -g <rg> --deployment-id <id>` |
| Full log download | `az webapp log download -n <app> -g <rg>` |

## When to hand off to `azure-prepare`

Hand off (and stop) if the user needs:

- VNet integration, private endpoints, or Front Door
- Key Vault references for app settings
- A database (Cosmos DB, PostgreSQL, MySQL, SQL)
- Multiple environments with Bicep/Terraform-managed infra
- A non-App-Service target (Container Apps, Functions, AKS)

Tell the user clearly: *"This deployment goes beyond a code push — `azure-prepare` will build the full infrastructure plan."*
