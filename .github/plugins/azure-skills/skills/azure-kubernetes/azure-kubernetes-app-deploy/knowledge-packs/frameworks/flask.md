# Flask Knowledge Pack

> **Applies to:** Projects detected with `requirements.txt`, `pyproject.toml`, or `Pipfile` containing `flask`

## Quick Reference

| Property | Value |
|----------|-------|
| Signal files | `requirements.txt`/`pyproject.toml`/`Pipfile` containing `flask` |
| Default port | `8000` prod (`5000` dev — never in prod) |
| Health path | `/health` + `/ready` |
| Base template | `templates/dockerfiles/python.Dockerfile` (+ `references/base-images.md`) |

---

## Health Endpoints

Flask does not include health check endpoints — they must be defined explicitly in application code:

### Minimal health route

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify(status="ok"), 200
```

### Readiness route with database check

```python
from flask import jsonify
from sqlalchemy import text

@app.route("/ready")
def ready():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify(status="ready"), 200
    except Exception:
        return jsonify(status="not ready"), 503
```

### Probe configuration in Deployment manifest

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 15
  timeoutSeconds: 3
  failureThreshold: 3
readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3
```

**Note:** Flask apps behind gunicorn start quickly (typically <3s), so `initialDelaySeconds: 5` is sufficient — much lower than JVM-based frameworks.

---

## Database Profiles

Flask does not have a built-in profile system. Database configuration is typically driven by environment variables:

| ORM / Driver | Package(s) | Connection String Env Var |
|-------------|-----------|--------------------------|
| Flask-SQLAlchemy | `flask-sqlalchemy`, `psycopg2-binary` | `SQLALCHEMY_DATABASE_URI` |
| SQLAlchemy direct | `sqlalchemy`, `psycopg2-binary` | `DATABASE_URL` |
| psycopg2 direct | `psycopg2-binary` | `DATABASE_URL` |

**Important:** Flask-SQLAlchemy reads the connection string from `app.config["SQLALCHEMY_DATABASE_URI"]`, which is typically set via `os.environ.get("SQLALCHEMY_DATABASE_URI")` or `os.environ.get("DATABASE_URL")`. Ensure the env var name matches what the app expects.

### Environment variables for PostgreSQL on AKS

```yaml
env:
  - name: SQLALCHEMY_DATABASE_URI
    value: "postgresql://{{IDENTITY_NAME}}@{{PG_SERVER_NAME}}.postgres.database.azure.com:5432/{{DB_NAME}}?sslmode=require"
  - name: SECRET_KEY
    valueFrom:
      secretKeyRef:
        name: {{APP_NAME}}-secrets
        key: secret-key
```

### Secret for SECRET_KEY

Flask requires `SECRET_KEY` for session signing, CSRF tokens, and any use of `flask.session`. Never hardcode it — store it in a Kubernetes Secret:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: {{APP_NAME}}-secrets
type: Opaque
stringData:
  secret-key: "<generate-a-random-string>"
```

### ConfigMap pattern

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{APP_NAME}}-config
data:
  SQLALCHEMY_DATABASE_URI: "postgresql://{{IDENTITY_NAME}}@{{PG_SERVER_NAME}}.postgres.database.azure.com:5432/{{DB_NAME}}?sslmode=require"
```

### Workload Identity with azure-identity

See `references/workload-identity.md` for connection patterns. Requires `azure-identity` package.

---

## Writable Paths (DS012 Compliance)

When `readOnlyRootFilesystem: true` is set, Flask apps typically only need `/tmp` writable:

- **Uploaded files** use `/tmp` as the default staging directory for `request.files`
- **Temporary processing** may write intermediate results to `/tmp`

### Required volume mount

```yaml
volumes:
  - name: tmp
    emptyDir: {}
containers:
  - name: app
    volumeMounts:
      - name: tmp
        mountPath: /tmp
```

No other writable paths are typically needed for production Flask apps.

---

## Resource Sizing

Flask with Gunicorn runs multiple worker processes. Size for the number of workers (default: 2-4).

| Resource | Request | Limit |
|----------|---------|-------|
| CPU | 150m | 500m |
| Memory | 128Mi | 256Mi |

---

## Port Configuration

- **Development port:** 5000 (`flask run` default — do not use in production)
- **Production port:** 8000 (gunicorn convention)
- **CLI flag:** `--bind 0.0.0.0:8000` passed to `gunicorn`
- **Env var override:** `PORT` (read via `gunicorn --bind 0.0.0.0:$PORT` or in app code `int(os.environ.get("PORT", 8000))`)
- **Workers formula:** `2 * CPU_CORES + 1` — override at runtime via `WEB_CONCURRENCY` env var
- **Entry point variants:** `gunicorn "app:app"` (module-level) or `gunicorn "myapp:create_app()"` (application factory)

Gunicorn logs the port on startup: `Listening at: http://0.0.0.0:8000`

---

## Build Commands

| Tool | Install Command |
|------|----------------|
| pip | `pip install --no-cache-dir -r requirements.txt` |
| Poetry | `poetry install --only main --no-interaction` |

Ensure `gunicorn` is listed in `requirements.txt` or `pyproject.toml` production dependencies.

---

## Common Issues on AKS

| Issue | Symptom | Fix |
|-------|---------|-----|
| Running dev server in production | Single-threaded, poor performance, `WARNING: This is a development server` in logs | Use `gunicorn` as the ENTRYPOINT — never use `flask run` or `app.run()` in production containers |
| `SECRET_KEY` not set | `RuntimeError: The session is unavailable because no secret key was set`, CSRF failures | Set `SECRET_KEY` via a Kubernetes Secret and reference it as an env var in the Deployment manifest |
| Flask binds to localhost | Connection refused from Kubernetes probes | Pass `--bind 0.0.0.0:8000` to gunicorn — the Flask dev server defaults to `127.0.0.1` which is unreachable from outside the container |
| Gunicorn not installed | `ModuleNotFoundError: No module named 'gunicorn'` | Ensure `gunicorn` is in `requirements.txt` or `pyproject.toml` main dependencies — it is often only in dev dependencies or missing entirely |
| DB connections not closed | `sqlalchemy.exc.TimeoutError: QueuePool limit`, PostgreSQL `max_connections` exhaustion | Configure pool size with `SQLALCHEMY_ENGINE_OPTIONS = {"pool_size": 5, "max_overflow": 10, "pool_recycle": 300}` and match PostgreSQL `max_connections` |
