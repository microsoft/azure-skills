# ASP.NET Core Knowledge Pack

> **Applies to:** Projects detected with `*.csproj` containing `Microsoft.NET.Sdk.Web` or referencing `Microsoft.AspNetCore.*` packages

## Quick Reference

| Property | Value |
|----------|-------|
| Signal files | `*.csproj` with `Microsoft.NET.Sdk.Web` or `Microsoft.AspNetCore.*` |
| Default port | `8080` (.NET 8+) |
| Health path | `/healthz` + `/ready` |
| Base template | `templates/dockerfiles/dotnet.Dockerfile` (+ `references/base-images.md`) |

---

## Health Endpoints

ASP.NET Core has built-in health check middleware via `Microsoft.Extensions.Diagnostics.HealthChecks`:

| Endpoint | Purpose | Probe Type |
|----------|---------|-----------|
| `/healthz` | Overall health | `livenessProbe` |
| `/ready` | Dependency readiness | `readinessProbe` |

### Required configuration

In `Program.cs`:

```csharp
var builder = WebApplication.CreateBuilder(args);

// Register health checks
builder.Services.AddHealthChecks()
    .AddNpgSql(builder.Configuration.GetConnectionString("DefaultConnection")!,
        name: "postgresql",
        tags: new[] { "ready" });

var app = builder.Build();

// Map health endpoints
app.MapHealthChecks("/healthz", new HealthCheckOptions
{
    Predicate = _ => false // No dependency checks for liveness
});

app.MapHealthChecks("/ready", new HealthCheckOptions
{
    Predicate = check => check.Tags.Contains("ready")
});
```

The `AspNetCore.HealthChecks.NpgSql` NuGet package provides the PostgreSQL health check. Install with:

```bash
dotnet add package AspNetCore.HealthChecks.NpgSql
```

### Probe configuration in Deployment manifest

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 15
  timeoutSeconds: 3
  failureThreshold: 3
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3
```

**Note:** ASP.NET Core apps start significantly faster than JVM-based frameworks — `initialDelaySeconds: 5` is typically sufficient.

---

## Database Profiles

ASP.NET Core uses configuration providers and Entity Framework Core for database access:

| Configuration Source | Activation | Typical Usage |
|---------------------|------------|---------------|
| `appsettings.json` | Default | Local dev with SQLite or LocalDB |
| `appsettings.Production.json` | `ASPNETCORE_ENVIRONMENT=Production` | Production connection strings |
| Environment variables | Always override file config | AKS deployments |

### Environment variables for PostgreSQL on AKS

```yaml
env:
  - name: ASPNETCORE_ENVIRONMENT
    value: Production
  - name: ConnectionStrings__DefaultConnection
    value: "Host={{PG_SERVER_NAME}}.postgres.database.azure.com;Database={{DB_NAME}};Username={{IDENTITY_NAME}};Ssl Mode=Require"
```

The double-underscore (`__`) in `ConnectionStrings__DefaultConnection` maps to the `:` separator in .NET configuration — `ConnectionStrings:DefaultConnection`.

### Workload Identity with Azure.Identity

See `references/workload-identity.md` for connection patterns. Requires `Azure.Identity` and `Npgsql.EntityFrameworkCore.PostgreSQL` packages.

### ConfigMap pattern

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{APP_NAME}}-config
data:
  ASPNETCORE_ENVIRONMENT: "Production"
  ConnectionStrings__DefaultConnection: "Host={{PG_SERVER_NAME}}.postgres.database.azure.com;Database={{DB_NAME}};Ssl Mode=Require"
  DOTNET_EnableDiagnostics: "0"
  DOTNET_RUNNING_IN_CONTAINER: "true"
```

---

## Writable Paths (DS012 Compliance)

When `readOnlyRootFilesystem: true` is set, ASP.NET Core needs `/tmp` writable:

- **Data Protection keys** are written to a local directory by default for key persistence
- **Temporary files** from multipart uploads and response buffering use `/tmp`
- **Entity Framework** compiled models may write to temp directories

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

### Data Protection key persistence

By default, ASP.NET Core Data Protection stores encryption keys in-memory when no persistent path is available, meaning keys are lost on pod restart. This breaks authentication cookies and anti-forgery tokens across pod restarts or in multi-replica deployments.

For production, persist keys to Azure Blob Storage:

```csharp
builder.Services.AddDataProtection()
    .PersistKeysToAzureBlobStorage("<connection-string>", "<container>", "<blob-name>")
    .ProtectKeysWithAzureKeyVault(new Uri("<key-vault-uri>"), new DefaultAzureCredential());
```

Alternatively, mount a PVC at a known path and configure:

```csharp
builder.Services.AddDataProtection()
    .PersistKeysToFileSystem(new DirectoryInfo("/keys"));
```

---

## Resource Sizing

ASP.NET Core on the .NET runtime is efficient but needs moderate memory for the CLR.

| Resource | Request | Limit |
|----------|---------|-------|
| CPU | 200m | 500m |
| Memory | 256Mi | 512Mi |

---

## Port Configuration

- **Default port:** 8080 (since .NET 8; previously 80 in .NET 7 and earlier)
- **Env var override:** `ASPNETCORE_URLS=http://+:8080` or `ASPNETCORE_HTTP_PORTS=8080`
- **Code override:** `builder.WebHost.UseUrls("http://+:8080")` in `Program.cs`

The port change from 80 to 8080 in .NET 8 aligns with non-root container best practices — port 80 requires elevated privileges. Set `DOTNET_EnableDiagnostics=0` to disable diagnostic pipes that require writable paths not available in read-only filesystems.

---

## Build Commands

| Variant | Build Command | Output |
|---------|---------------|--------|
| Framework-dependent | `dotnet publish -c Release -o ./publish` | `./publish/<app-name>.dll` — requires .NET runtime on target |
| Self-contained | `dotnet publish -c Release --self-contained -o ./publish` | `./publish/<app-name>` — includes .NET runtime |
| Single-file | `dotnet publish -c Release --self-contained -p:PublishSingleFile=true -o ./publish` | Single executable binary |

The `-c Release` flag enables compiler optimizations and disables debug symbols — always use it for production builds.

---

## EF Core Migrations

Run `dotnet ef database update` as an init container — never in the Dockerfile build stage (no database access) and never in the entrypoint (race condition when multiple replicas start simultaneously).

---

## Common Issues on AKS

| Issue | Symptom | Fix |
|-------|---------|-----|
| Kestrel bound to port 80 | `CrashLoopBackOff` — permission denied binding to port 80 as non-root | Set `ASPNETCORE_HTTP_PORTS=8080` or upgrade to .NET 8+ which defaults to 8080 |
| Data Protection keys lost on restart | Users logged out after pod restart, anti-forgery token validation failures | Persist keys to Azure Blob Storage or a PVC — do not rely on in-memory default |
| EF Core migrations not applied | `NpgsqlException: relation "..." does not exist` | Run `dotnet ef database update` as an init container or at startup with `Database.Migrate()` |
| Image too large (>500MB) | Slow pulls, high ACR storage | Use self-contained + trimmed publish with the runtime-deps Alpine base image |
| HTTPS redirect loop behind gateway | Infinite 307/308 redirects, `ERR_TOO_MANY_REDIRECTS` | Disable HTTPS redirection in `Program.cs` when behind a TLS-terminating gateway — configure `ForwardedHeaders` middleware instead |
