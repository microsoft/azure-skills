# Django Knowledge Pack

> **Applies to:** Projects detected with `requirements.txt`, `pyproject.toml`, or `Pipfile` containing `django`, or presence of `manage.py`

## Quick Reference

| Property | Value |
|----------|-------|
| Signal files | `requirements.txt`/`pyproject.toml`/`Pipfile` containing `django`, or `manage.py` |
| Default port | `8000` (gunicorn) |
| Health path | `/health/` (django-health-check) |
| Base template | `templates/dockerfiles/python.Dockerfile` (+ `references/base-images.md`) |

---

## Health Endpoints

Django does not provide health endpoints out of the box. Use the `django-health-check` package:

### Installation

```bash
pip install django-health-check
```

### Configuration in `settings.py`

```python
INSTALLED_APPS = [
    # ...existing apps...
    "health_check",
    "health_check.db",
    "health_check.cache",
    "health_check.storage",
    "health_check.contrib.migrations",
]
```

### URL configuration in `urls.py`

```python
from django.urls import include, path

urlpatterns = [
    # ...existing urls...
    path("health/", include("health_check.urls")),
]
```

The `/health/` endpoint returns HTTP 200 when all checks pass and HTTP 500 with details when any check fails.

### Probe configuration in Deployment manifest

```yaml
livenessProbe:
  httpGet:
    path: /health/
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 15
  timeoutSeconds: 3
  failureThreshold: 3
readinessProbe:
  httpGet:
    path: /health/
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3
```

**Note:** `initialDelaySeconds: 10` is sufficient for most Django apps.

---

## Database Profiles

Django does not have a built-in profile system like Spring Boot. Database configuration is driven by `settings.py` with environment variables:

| Pattern | How it works |
|---------|-------------|
| `dj-database-url` | Parse `DATABASE_URL` env var (recommended for 12-factor apps)

### Environment variables for PostgreSQL on AKS

```yaml
env:
  - name: DATABASE_URL
    value: "postgres://{{IDENTITY_NAME}}@{{PG_SERVER_NAME}}.postgres.database.azure.com:5432/{{DB_NAME}}?sslmode=require"
  - name: SECRET_KEY
    valueFrom:
      secretKeyRef:
        name: {{APP_NAME}}-secrets
        key: secret-key
```

**Important:** `SECRET_KEY` must never be in a ConfigMap or hardcoded. Always store it in a Kubernetes Secret (or Key Vault via Workload Identity).

### ConfigMap pattern

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{APP_NAME}}-config
data:
  DJANGO_SETTINGS_MODULE: "config.settings.production"
  DJANGO_ALLOWED_HOSTS: "{{INGRESS_HOSTNAME}}"
  DATABASE_URL: "postgres://{{IDENTITY_NAME}}@{{PG_SERVER_NAME}}.postgres.database.azure.com:5432/{{DB_NAME}}?sslmode=require"
```

---

## Writable Paths (DS012 Compliance)

When `readOnlyRootFilesystem: true` is set, Django apps need `/tmp` writable and optionally `/app/staticfiles`:

- **`/tmp`** — required for file uploads (`FILE_UPLOAD_TEMP_DIR` defaults to `/tmp`), session data when using file-based sessions, and temporary processing
- **`/app/staticfiles`** — optional, only needed if serving collected static files at runtime from the local filesystem (when not using WhiteNoise or a CDN)

### Volume mount configuration

```yaml
volumes:
  - name: tmp
    emptyDir: {}
  - name: staticfiles
    emptyDir: {}
containers:
  - name: app
    volumeMounts:
      - name: tmp
        mountPath: /tmp
      - name: staticfiles
        mountPath: /app/staticfiles
```

If static files are baked into the image at build time via `collectstatic` and served by WhiteNoise, the `staticfiles` volume can be omitted — only `/tmp` is required.

---

## Resource Sizing

Django with Gunicorn runs multiple worker processes. Size for the number of workers (default: 2-4).

| Resource | Request | Limit |
|----------|---------|-------|
| CPU | 200m | 500m |
| Memory | 256Mi | 512Mi |

---

## Port Configuration

- **Default port:** 8000
- **CLI flag:** `--bind 0.0.0.0:8000` passed to `gunicorn`
- **Env var override:** `PORT` (read via `gunicorn --bind 0.0.0.0:$PORT` or `int(os.environ.get("PORT", 8000))`)
- **Workers formula:** `2 * CPU_CORES + 1` (e.g. `--workers 3` for a 1-vCPU container)
- **WSGI module path** varies by project scaffold: `config.wsgi:application`, `myproject.wsgi:application`, or `app.wsgi:application` — check `wsgi.py` location

Gunicorn logs the port on startup: `Listening at: http://0.0.0.0:8000`

---

## Build Commands

| Command | Purpose | When to run |
|---------|---------|-------------|
| `python manage.py collectstatic --noinput` | Gathers static files into `STATIC_ROOT` | In Dockerfile build stage (with `SECRET_KEY=build-placeholder`) |
| `python manage.py migrate --noinput` | Applies database migrations | As a Kubernetes init container — **never in the Dockerfile** |

**Important:** Database migrations must run as an init container, not during the Docker build. The build stage has no access to the production database, and running migrations in the entrypoint creates race conditions when multiple replicas start simultaneously.

### Init container for migrations

```yaml
initContainers:
  - name: migrate
    image: {{ACR_NAME}}.azurecr.io/{{APP_NAME}}:{{TAG}}
    command: ["python", "manage.py", "migrate", "--noinput"]
    envFrom:
      - configMapRef:
          name: {{APP_NAME}}-config
      - secretRef:
          name: {{APP_NAME}}-secrets
```

---

## Common Issues on AKS

| Issue | Symptom | Fix |
|-------|---------|-----|
| `collectstatic` not run | Static files 404 | Run `python manage.py collectstatic --noinput` in Dockerfile build stage |
| `ALLOWED_HOSTS` not set | `DisallowedHost` error | Set `DJANGO_ALLOWED_HOSTS` env var |
| Dev server in production | Single-threaded, no security | Use `gunicorn` in ENTRYPOINT |
| Migrations not applied | `relation "..." does not exist` | Run `manage.py migrate` as init container |
| `SECRET_KEY` not set | `ImproperlyConfigured` error | Store in Kubernetes Secret |
| Static files 404 in production | CSS/JS/images not loading | Use WhiteNoise or CDN for static files
