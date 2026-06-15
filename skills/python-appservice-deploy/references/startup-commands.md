# Startup Commands by Framework

Linux App Service (Oryx) auto-detects **Flask** and **Django** — no startup command is needed for these. **FastAPI does NOT rely on Oryx auto-detection** in this skill: we always set an explicit uvicorn startup command so the behavior is identical on every supported Python runtime (3.12, 3.13, 3.14, …). This skill also sets a startup command (or emits a manual hint) for non-Flask/Django/FastAPI frameworks.

## Flask — no startup command needed

Azure App Service (Oryx) auto-detects Flask and starts it correctly. **Do not run `az webapp config set --startup-file` for Flask apps.**

## Django — no startup command needed

Azure App Service (Oryx) auto-detects Django by finding `wsgi.py` and starts gunicorn against `<project>.wsgi:application` automatically. **Do not run `az webapp config set --startup-file` for Django apps.**

Make sure the project has:
- `requirements.txt` containing `django` (and ideally `gunicorn`; Oryx provides one if missing)
- `<project>/wsgi.py` at a path Oryx can discover (the default Django layout works out of the box)
- `ALLOWED_HOSTS` includes `<app>.azurewebsites.net` (or `*` for first-deploy validation — tighten later)

## FastAPI — always set the uvicorn startup command

The skill sets the startup command unconditionally for FastAPI, regardless of the Python runtime version. Oryx FastAPI auto-detection is **not** relied on — an explicit startup command always works and avoids version-dependent surprises:

```bash
az webapp config set -n <app> -g <rg> \
  --startup-file "python -m uvicorn main:app --host 0.0.0.0"
```
```powershell
az webapp config set -n <app> -g <rg> `
  --startup-file "python -m uvicorn main:app --host 0.0.0.0"
```

Replace `main:app` with the discovered entry point if different (e.g., `app.main:app`, `src.api:app`). The `--host 0.0.0.0` flag is mandatory — uvicorn defaults to 127.0.0.1, which causes App Service container-ping timeouts.

Make sure `requirements.txt` contains both `fastapi` and `uvicorn` (or `uvicorn[standard]`).

## Not auto-configured — warn & deploy anyway

When the detected framework is `wsgi-generic`, `asgi-generic`, or `unknown`, **deploy the code without setting a startup command** and surface this message to the user:

> ⚠️ This skill auto-configures Flask, Django, and FastAPI only. The app has been deployed, but App Service may not start it until you set a startup command. Choose the matching example below and run it:

### Generic WSGI

```bash
az webapp config set -n <app> -g <rg> \
  --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 <module>:<callable>"
```
```powershell
az webapp config set -n <app> -g <rg> `
  --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 <module>:<callable>"
```

### Generic ASGI

```bash
az webapp config set -n <app> -g <rg> \
  --startup-file "python -m uvicorn <module>:<callable> --host 0.0.0.0 --port 8000"
```
```powershell
az webapp config set -n <app> -g <rg> `
  --startup-file "python -m uvicorn <module>:<callable> --host 0.0.0.0 --port 8000"
```

### Django override (only if auto-detection fails)

Oryx auto-detection covers the standard Django layout. Set this manually **only** if the project uses a non-standard layout and the auto-detected startup doesn't find your WSGI app:

```bash
az webapp config set -n <app> -g <rg> \
  --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 <project>.wsgi"
```
```powershell
az webapp config set -n <app> -g <rg> `
  --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 <project>.wsgi"
```

## Diagnosing a wrong startup command

```bash
# Current value
az webapp config show -n <app> -g <rg> --query linuxFxVersion -o tsv
az webapp config show -n <app> -g <rg> --query appCommandLine -o tsv

# Live logs
az webapp log tail -n <app> -g <rg>
```

Look for:
- `Container <app>_<...> didn't respond to HTTP pings on port: 8000` → app didn't bind to 0.0.0.0 (or 0.0.0.0:8000)
- `ModuleNotFoundError` → wrong `<module>:<callable>` in startup command, or build didn't install deps
- `gunicorn: command not found` / `uvicorn: command not found` → add `gunicorn` / `uvicorn` to `requirements.txt`

## Why `--host 0.0.0.0` matters

App Service forwards traffic to the container on the port the runtime listens on (8000 by default). The startup command must bind to `0.0.0.0` so the platform's ping reaches it — binding to `127.0.0.1` causes ping timeouts.
