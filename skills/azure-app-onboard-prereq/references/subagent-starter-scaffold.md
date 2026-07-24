# Subagent Template — Starter App Scaffold (Zero-Code Path Step 4)

Generate a minimal, Azure-compatible starter project from scratch based on user requirements.

## Critical Rules

- ⛔ **Do NOT invoke ANY skills** — no `{"skill": "..."}` calls. You are a code generation sub-agent only.
- ⛔ **Do NOT generate Azure infrastructure** (Bicep, Terraform, `azure.yaml`). This creates application source code only — infrastructure is the prepare/scaffold phase's job.
- ⛔ **Do NOT install dependencies** — no `npm install`, `pip install`, or any package manager commands. The main agent handles the build-validation gate after you return.

## Input (provided by caller)

| Field | Source | Required |
|-------|--------|----------|
| App description | User's answer to "What kind of app?" or `context.json.intent.userPrompt` | YES |
| Chosen stack | Stack the user accepted or overrode (e.g., "Node.js/Express", "Python/FastAPI") | YES |
| Workspace root | Absolute path to write files | YES |
| Data needs | `true` if user described database/storage needs ("with a database", "stores tasks") | YES |
| Multi-page | `true` if user described multiple views/pages ("three tabs", "dashboard + settings") | YES |

## Workflow

### Step 1 — Apply starter patterns

Generate health endpoints, follow stack conventions, and avoid common mistakes:

**Health endpoints (MANDATORY):**
- `/healthz` — liveness: `200 { status: "ok" }`. Must return 2xx directly (no redirects), allow anonymous access.
- `/readyz` — readiness: check DB/cache/deps. `200` when ready, `503` when not.
- Container Apps: `httpGet.port` must match `targetPort` in ingress config.

**Stack conventions:**
- **Node.js/Express:** Listen on `process.env.PORT || 3000`. `"start"` script required. `"engines": { "node": ">=20" }`. Production deps in `dependencies`.
- **Python (Flask/FastAPI):** Production: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app`. Include `gunicorn` in `requirements.txt`. Bind `0.0.0.0`, not `127.0.0.1`.
- **Next.js/React:** Static export: `output: 'export'`. Hybrid SSR works on SWA.

**Project structure:** `src/` for app code (routes, entry, server). `.env.sample`, `.gitignore`, `package.json`/`requirements.txt`, `README.md`.

**Common mistakes to avoid:** hardcoded port, dev server in production, no health endpoint, missing `start` script, secrets in source, no CORS middleware, missing `engines.node`, Python missing `gunicorn`, Python using `passlib` (unmaintained, breaks on Python 3.12+ with bcrypt 5.x — use `bcrypt>=4.0` directly).

### Step 2 — Generate files

Scaffold a minimal starter project. Include:
- Entry point file with a working HTTP server, `/healthz` (liveness), and `/readyz` (readiness) endpoints
- Package manifest (`package.json`, `requirements.txt`, `*.csproj`, `go.mod`) with minimal production dependencies
- `.env.sample` listing required environment variables (at minimum: `PORT`)
- `.gitignore` appropriate for the stack
- README.md with project name, one-line description, and local run instructions
- If data needs is `true`: add a placeholder data model/schema file and an in-memory or file-based data layer (NOT a cloud database client — that's scaffold phase's job)
- If multi-page is `true`: scaffold route stubs or page components

### Step 3 — Return file list

Return the list of files written to the workspace so the main agent can verify and pass to build validation.

## Output

| Artifact | Location |
|----------|----------|
| Application source files | Workspace root (conventional layout per Step 1 patterns) |
| File list | Return to caller — array of relative paths written |

## Rules

- Scaffold dynamically based on app description — no hardcoded templates. Read the stack ecosystem's conventions (e.g., `npm init` patterns for Node, `dotnet new webapi` patterns for .NET).
- Code must be functional enough to start locally (e.g., `node src/server.js` serves HTTP on a port) so the 3-axis evaluation has something real to assess.
- Follow the project structure and common mistakes guidance from Step 1 exactly.
