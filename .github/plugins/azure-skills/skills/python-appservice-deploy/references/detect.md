# Framework Detection (Advisory)

Framework detection is **advisory only**. The deployment never blocks because of an unknown framework.

## What to check

1. **Confirm Python project** — at least one of:
   - `requirements.txt`
   - `pyproject.toml`
   - `*.py` files in workspace root
2. **Scan dependencies** in `requirements.txt` or `pyproject.toml`:

| Token (case-insensitive) | Detected framework |
|---|---|
| `flask`, `Flask` | **flask** |
| `django`, `Django` | **django** |
| `fastapi` | **fastapi** |
| `gunicorn` (alone, no flask) | **wsgi-generic** |
| `uvicorn` (alone, no fastapi) | **asgi-generic** |
| None of the above | **unknown** |

3. **Locate the WSGI / ASGI entry point** (best-effort):
   - Flask common: `app.py` exporting `app`, `application.py`, `wsgi.py`
   - Django common: `<project>/wsgi.py`
   - FastAPI common: `main.py` exporting `app`
4. **Record findings** in your working memory so Step 5 (startup) can use them.

## Outcomes

| Detection | Step 5 behavior |
|---|---|
| `flask` | Skip startup auto-config. Oryx auto-detects Flask and starts it. |
| `django` | Skip startup auto-config. Oryx auto-detects Django via `wsgi.py` and starts it. |
| `fastapi` (any Python version) | **Always auto-set** startup: `python -m uvicorn main:app --host 0.0.0.0` (replace `main:app` with the discovered entry point if different — e.g., `app.main:app`). The skill does not rely on Oryx FastAPI auto-detection. |
| `wsgi-generic`, `asgi-generic`, `unknown` | Skip startup auto-config. Emit warning: *"Could not auto-detect a supported framework (only Flask, Django, and FastAPI are auto-configured today). The app will deploy, but you may need to set the startup command manually: `az webapp config set --startup-file '<your-command>'`"* |

> Priority rule when both `flask` and `fastapi` appear in `requirements.txt` (or `pyproject.toml`): **always treat as FastAPI** — set the explicit uvicorn startup command. This is deterministic and avoids relying on import-order or token-order heuristics. Rationale: Flask is happily auto-detected by Oryx with no startup command, but FastAPI requires the explicit uvicorn command to run reliably; if the project actually uses Flask as the served app, the user can override the startup command later, but if it uses FastAPI and we silently picked Flask, the container ping fails.

## Important rules

- ⛔ **Do not** abort deployment when framework is unknown.
- ⛔ **Do not** try to install Flask, Django, or any framework into the user's project.
- ✅ Always report what was detected so the user has full context.
- ✅ When detection is `wsgi-generic`, `asgi-generic`, or `unknown`, **remember this fact for Step 8** — the post-deploy message must use the **unknown-framework template** in [post-deploy-message.md](post-deploy-message.md), which adds an explicit "set a startup command" instruction. The Step 5 warning alone is not enough; the user needs the reminder at the end of the run too.

## Example output to surface to the user

```
Detected: Flask (Python 3.14)
Entry point: app.py
Startup command will be auto-detected by Oryx — no startup command needed.
```

or

```
Detected: Django (Python 3.14)
Entry point: <project>/wsgi.py
Startup command will be auto-detected by Oryx — no startup command needed.
```

or

```
Detected: FastAPI (Python 3.14)
Entry point: main.py → app
Setting startup command (always set for FastAPI):
  python -m uvicorn main:app --host 0.0.0.0
```

or

```
Detected: Python project, framework unknown.
The app will deploy, but App Service may not start it correctly until
you set a startup command:
  az webapp config set -n <app> -g <rg> --startup-file '<command>'
See startup-commands.md for examples.
```
