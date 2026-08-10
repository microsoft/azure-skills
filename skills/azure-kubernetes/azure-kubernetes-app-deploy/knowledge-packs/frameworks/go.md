# Go Knowledge Pack

> **Applies to:** Projects detected with `go.mod` containing `github.com/gin-gonic/gin`, `github.com/labstack/echo`, `github.com/gofiber/fiber`, or any Go project using the standard library `net/http` for HTTP serving

## Quick Reference

| Property | Value |
|----------|-------|
| Signal files | `go.mod` (gin/echo/fiber or stdlib `net/http`) |
| Default port | `8080` |
| Health path | `/healthz` + `/ready` |
| Base template | `templates/dockerfiles/go.Dockerfile` (+ `references/base-images.md`) |

---

## Build Flags

Two flags are required for a correct production build:

- **`CGO_ENABLED=0`** produces a fully static binary with no libc dependency — required when targeting the distroless static image. If CGO is needed (e.g., for sqlite3 or cgo bindings), use the distroless cc image instead.
- **`-ldflags="-s -w"`** strips debug symbols and DWARF info, reducing binary size by ~30%.

---

## Health Endpoints

Go does not provide health check endpoints out of the box — you must implement them manually. Example using standard library:

```go
http.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(http.StatusOK)
    w.Write([]byte(`{"status":"ok"}`))
})
http.HandleFunc("/ready", func(w http.ResponseWriter, r *http.Request) {
    if err := db.Ping(); err != nil {
        w.WriteHeader(http.StatusServiceUnavailable)
        w.Write([]byte(`{"status":"not ready"}`))
        return
    }
    w.WriteHeader(http.StatusOK)
    w.Write([]byte(`{"status":"ready"}`))
})
```

### Probe configuration in Deployment manifest

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 3
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 3
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3
```

**Note:** Go binaries start in milliseconds — `initialDelaySeconds: 3` is generous. No JVM warmup or interpreter startup to wait for.

---

## Graceful Shutdown

Implement `signal.NotifyContext` with `srv.Shutdown(ctx)` to allow in-flight requests to complete before the pod exits during a rolling update. Without this, connections are dropped and callers receive 502 errors.

---

## Database Profiles

Go does not have a built-in profile system. Database configuration is typically driven by environment variables:

| Library | Driver | Connection Env Var |
|---------|--------|--------------------|
| `database/sql` + `pgx` | `github.com/jackc/pgx/v5/stdlib` | `DATABASE_URL` |
| GORM | `gorm.io/driver/postgres` | `DATABASE_URL` |
| sqlx | `github.com/jmoiron/sqlx` + `pgx` | `DATABASE_URL` |
| pgx direct | `github.com/jackc/pgx/v5` | `DATABASE_URL` |

### Environment variables for PostgreSQL on AKS

```yaml
env:
  - name: DATABASE_URL
    value: "host={{PG_SERVER_NAME}}.postgres.database.azure.com port=5432 dbname={{DB_NAME}} user={{IDENTITY_NAME}} sslmode=require"
```

### Workload Identity with pgx

Use `azidentity` to obtain Azure AD tokens and inject them via pgx's `BeforeConnect` hook — no password stored:

```go
import (
    "github.com/Azure/azure-sdk-for-go/sdk/azidentity"
    "github.com/jackc/pgx/v5"
)

cred, _ := azidentity.NewDefaultAzureCredential(nil)

config, _ := pgx.ParseConfig(os.Getenv("DATABASE_URL"))
config.BeforeConnect = func(ctx context.Context, cfg *pgx.ConnConfig) error {
    token, err := cred.GetToken(ctx, policy.TokenRequestOptions{
        Scopes: []string{"https://ossrdbms-aad.database.windows.net/.default"},
    })
    if err != nil {
        return err
    }
    cfg.Password = token.Token
    return nil
}
```

### ConfigMap pattern

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{APP_NAME}}-config
data:
  DATABASE_URL: "host={{PG_SERVER_NAME}}.postgres.database.azure.com port=5432 dbname={{DB_NAME}} user={{IDENTITY_NAME}} sslmode=require"
```

---

## Writable Paths (DS012 Compliance)

When `readOnlyRootFilesystem: true` is set, Go apps typically need **no writable paths**:

- Go compiles to a static binary — no temp files, no interpreted bytecode, no session storage
- The distroless static base image has no shell or package manager that writes to disk

### Optional `/tmp` mount

If your application explicitly writes temporary files (e.g., file uploads, report generation):

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

Most Go web APIs do not need this.

---

## Resource Sizing

Go compiles to a static binary with no runtime — it is the most resource-efficient option.

| Resource | Request | Limit |
|----------|---------|-------|
| CPU | 50m | 200m |
| Memory | 64Mi | 128Mi |

---

## Port Configuration

- **Default port:** 8080 (Go convention, not enforced by any framework)
- **Env var override:** `PORT` (commonly used pattern)
- **Bind port >= 1024** — lower ports require elevated privileges; running as non-root (uid 65534) means port 80 or 443 will fail with `permission denied`.

### Code pattern

```go
port := os.Getenv("PORT")
if port == "" {
    port = "8080"
}
log.Printf("Listening on :%s", port)
log.Fatal(http.ListenAndServe(":"+port, router))
```

All major Go frameworks (Gin, Echo, Fiber) accept the listen address as a string — no special configuration property needed.

---

## Build Commands

| Variant | Command | Notes |
|---------|---------|-------|
| Standard | `CGO_ENABLED=0 go build -ldflags="-s -w" -o server ./cmd/server` | Production binary, stripped |
| Race detector (test only) | `go build -race -o server ./cmd/server` | Do **not** use in production — 10x overhead |
| Multiple binaries | `CGO_ENABLED=0 go build -ldflags="-s -w" -o migrate ./cmd/migrate` | Build each binary target separately |

The `./cmd/server` path is conventional for Go projects using the [Standard Go Project Layout](https://github.com/golang-standards/project-layout). Adjust to match the actual `main` package location.

---

## Common Issues on AKS

| Issue | Symptom | Fix |
|-------|---------|-----|
| Binary not statically linked | `exec format error` or `not found` in distroless | Ensure `CGO_ENABLED=0` is set during build; if CGO is required, use the distroless cc image instead of the distroless static image |
| DNS resolution issues during build | `dial tcp: lookup ... no such host` | Add `ca-certificates` to the build stage or use a Debian-based build image |
| Graceful shutdown not implemented | Connections dropped during rolling update, 502 errors | Implement `signal.NotifyContext` with `srv.Shutdown(ctx)` — give in-flight requests time to complete before exit |
| Binary name mismatch | `exec /server: no such file or directory` | Verify the `-o` flag in `go build` matches the `ENTRYPOINT` path in the Dockerfile |
| Port < 1024 with non-root user | `bind: permission denied` | Use port 8080 (or any port >= 1024); never bind to 80 or 443 inside the container |
