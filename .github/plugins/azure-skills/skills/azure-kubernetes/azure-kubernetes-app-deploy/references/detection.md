# Detection Reference

Shared detection logic used by Section 1 (Detection) in Quick Deploy.

## Framework Detection

Scan for signal files at the project root (and one level deep for monorepos). Map each signal to a framework and, where possible, a sub-framework:

| Signal File | Framework | Sub-framework Detection |
|---|---|---|
| `package.json` | Node.js | Inspect `dependencies` for: **Express** (`express`), **Fastify** (`fastify`), **NestJS** (`@nestjs/core`), **Next.js** (`next`), **Remix** (`@remix-run/node`), **Hono** (`hono`), **Koa** (`koa`) |
| `requirements.txt` | Python | Scan for: **FastAPI** (`fastapi`), **Django** (`django`), **Flask** (`flask`), **Starlette** (`starlette`), **Gunicorn** (`gunicorn`) |
| `pyproject.toml` | Python | Parse `[project.dependencies]` or `[tool.poetry.dependencies]` for the same libraries as above |
| `Pipfile` | Python | Parse `[packages]` section for the same libraries as above |
| `pom.xml` | Java | Search for `<artifactId>spring-boot-starter-web</artifactId>` → **Spring Boot**; `<artifactId>quarkus-resteasy</artifactId>` → **Quarkus**; `<artifactId>micronaut-http-server-netty</artifactId>` → **Micronaut** |
| `build.gradle` / `build.gradle.kts` | Java / Kotlin | Search for `org.springframework.boot` → **Spring Boot**; `io.quarkus` → **Quarkus**; `io.micronaut` → **Micronaut** |
| `go.mod` | Go | Parse `require` block for: `github.com/gin-gonic/gin` → **Gin**; `github.com/labstack/echo` → **Echo**; `github.com/gofiber/fiber` → **Fiber**. For `net/http` (stdlib): search `.go` source files for `"net/http"` import — stdlib packages never appear in the `require` block |
| `*.csproj` | .NET | Search for `<PackageReference Include="Microsoft.AspNetCore.*"` → **ASP.NET Core**; check `<TargetFramework>` for version (e.g. `net8.0`) |
| `Cargo.toml` | Rust | Parse `[dependencies]` for: `actix-web` → **Actix**; `axum` → **Axum**; `rocket` → **Rocket**; `warp` → **Warp** |

**If multiple signal files are found** (e.g. both `package.json` and `requirements.txt`), record all of them — this may indicate a monorepo or polyglot project. Flag for clarification.

## Port Detection

Check these sources in priority order (first match wins):

| Source | What to Look For | Example |
|---|---|---|
| `Dockerfile` | `EXPOSE <port>` directive | `EXPOSE 3000` |
| `.env` / `.env.example` | `PORT=<number>` | `PORT=8080` |
| `package.json` (`scripts.start`) | `--port <number>` or `-p <number>` | `next start --port 3000` |
| Source code | `app.listen(<number>)`, `.listen(<number>)`, `server.port=<number>` | `app.listen(3000)` |
| `application.properties` / `application.yml` (Java) | `server.port=<number>` | `server.port=8080` |
| `appsettings.json` (.NET) | `"Urls": "http://*:<number>"` | `"Urls": "http://*:8080"` |
| Framework defaults | Use known defaults if nothing explicit found | Express: 3000, FastAPI: 8000, Spring Boot: 8080, ASP.NET: 8080, Gin: 8080 |

## Health Endpoint Detection

Grep the source tree for route registrations matching these patterns:

| Pattern | Endpoint Type |
|---|---|
| `/health` | Generic health check |
| `/healthz` | Kubernetes-style health check |
| `/ready`, `/readiness` | Readiness probe |
| `/liveness` | Liveness probe |
| `/startup` | Startup probe |
| `/ping` | Simple ping (sometimes used as health) |
| `/status` | Status endpoint |
| `/api/health`, `/api/healthz` | Prefixed health check |

Record the **HTTP method** (GET/HEAD) and **expected response code** (200) for each detected endpoint. If no health endpoints are found, flag it — probes will use `/health` as default.
