# Deploy Strategy

Determine how application code will be deployed to Azure based on prereq scan results. The prepare phase writes `deployStrategy` to `prepare-plan.json`; scaffold encodes it in Bicep; deploy executes it.

## Deployment Patterns

Three patterns — select based on `prereq-output.json.components[].buildRequirements`:

> ⛔ **Dockerfile ≠ Container Apps.** A Dockerfile that only serves static files (nginx, httpd, `COPY . /usr/share/nginx/html`) is NOT a backend app. Route static-only Dockerfiles as static sites per `service-mapping.md § Static Dockerfile sites`, not Pattern C.

| Pattern | When | `deployStrategy` needed? |
|---------|------|--------------------------|
| **A: Oryx auto-build** | No native modules, no Dockerfile | Yes — startup command + app settings go in Bicep at scaffold time |
| **B: Startup-install** | Native modules detected (`hasNativeModules: true`) | Yes — startup command + fallback install + app settings in Bicep |
| **C: Container-only** | Has Dockerfile that runs a server process (Express, Flask, uvicorn, etc.) | No — route to Container Apps (Dockerfile IS the deploy strategy) |

**Additional routing:**

| Condition | Action |
|-----------|--------|
| Jib build plugin (Java + `com.google.cloud.tools.jib`) | Container-only via Jib push to ACR — no Dockerfile needed |

---

## Pattern A: Oryx Auto-Build (Default)

**Languages:** Node.js, Python, .NET, Go, Java, PHP, Ruby

Oryx detects the stack from project manifests, installs dependencies, and builds automatically during zip deploy.

**Still write `deployStrategy` to `prepare-plan.json`** — even though Oryx auto-detects, the startup command and app settings MUST be in Bicep at scaffold time (not generated at deploy time). This eliminates imperative CLI commands during deploy.

```json
"deployStrategy": {
  "codeDeployPattern": "oryx-auto",
  "requiredAppSettings": {
    "SCM_DO_BUILD_DURING_DEPLOYMENT": "true",
    "ENABLE_ORYX_BUILD": "true",
    "ORYX_DISABLE_COMPRESSION": "true"
  },
  "reason": "Standard Oryx build — no native modules, no Dockerfile. Compression disabled to avoid startup extraction delays. No custom appCommandLine — Oryx launcher handles decompression + start."
}
```

 Read `prereq-output.json.entryPoint` for the app's start file — do NOT re-read manifests. Build the startup command from `package.json` `start` script (Node.js) or framework convention (Python gunicorn, .NET/Go/Java Oryx-native).

> ⛔ **Do NOT set a custom `appCommandLine` for Pattern A.** Let Oryx use `package.json` `start` script or framework defaults natively. A custom `appCommandLine` (`cd /home/site/wwwroot && node {entryPoint}`) replaces the Oryx launcher entirely — the launcher handles `node_modules.tar.gz` decompression, and bypassing it causes `MODULE_NOT_FOUND` crashes. Only set `appCommandLine` when `initCommands[]` has `required: true` entries (migrations).
>
> ⛔ **TypeScript projects:** Verify `typescript` + `@types/*` are in `dependencies` (not `devDependencies`) — Oryx production mode skips devDeps, causing `tsc` build failures.
>
> ⛔ **When `initCommands[]` has `required: true` entries:** Set `startupCommand` to prepend migrations: `"cd /home/site/wwwroot && {initCommand} && {framework-default-start}"`. Migrations are idempotent — safe on every cold start. Otherwise, omit `startupCommand` entirely (let Oryx handle it).

Scaffold encodes `startupCommand` → Bicep `appCommandLine`, and `requiredAppSettings` → Bicep `siteConfig.appSettings`. Deploy only does: wait → zip → health check.

---

## Pattern B: Startup-Install (Native Modules)

When native modules are detected, Oryx may fail to compile them. The startup-install pattern provides a two-layer safety net.

### Two-Layer Strategy

1. **Primary — Oryx zip build:** `SCM_DO_BUILD_DURING_DEPLOYMENT=true` + `ENABLE_ORYX_BUILD=true` tells Oryx to run dependency installation during the Kudu-side zip deploy. The Kudu build environment on App Service Linux has `gcc`, `make`, and build tools available, so native compilation CAN succeed here.

2. **Fallback — startup-install command:** `appCommandLine` runs dependency installation on first container boot IF the dependency directory doesn't exist. The existence guard ensures it only runs when needed — subsequent restarts skip it because `/home` is persistent storage.

Both layers are set in Bicep at scaffold time. The startup command is insurance — not the primary mechanism.

> **Why two layers?** `az webapp deploy --type zip` uses the OneDeploy API, which may not trigger Oryx even with `SCM_DO_BUILD_DURING_DEPLOYMENT=true`. The startup command catches this case. If Oryx DID build successfully, the guard skips the redundant install.

### Deploy Strategy Schema

Write to `prepare-plan.json.deployStrategy`:

```json
"deployStrategy": {
  "codeDeployPattern": "startup-install",
  "startupCommand": "cd /home/site/wwwroot && if [ ! -d node_modules ]; then npm install --production; fi && node index.js",
  "requiredAppSettings": {
    "WEBSITES_CONTAINER_START_TIME_LIMIT": "1800",
    "SCM_DO_BUILD_DURING_DEPLOYMENT": "true",
    "ENABLE_ORYX_BUILD": "true",
    "ORYX_DISABLE_COMPRESSION": "true"
  },
  "reason": "Native module (better-sqlite3 via node-gyp) requires server-side npm install."
}
```

Replace `startupCommand` and `reason` with language-specific values from the entry point table below.

### Entry Point & Startup Commands

Same as Pattern A, but Node.js adds a dependency guard: `if [ ! -d node_modules ]; then npm install --production; fi` before the start command.

> ⛔ **Inline commands only.** Never generate a `.sh` startup script file — CRLF causes `bash` exit code 2.
> ⛔ **Python: do NOT use `venv` in startup commands.**

### SKU Implications

When `f1Viable: false` (any of: native modules, TypeScript build, large deps, WSGI/ASGI server), F1 is not viable — use B1 (~$13/mo) minimum. Surface at approval gate: "⚠️ {f1BlockReason}. B1 minimum required."

### Container Timeout

`WEBSITES_CONTAINER_START_TIME_LIMIT` controls how long Azure waits for the container to start responding.

| Value | Use case |
|-------|----------|
| 230 (default) | Standard apps, no native compilation |
| 1800 (max) | Startup-install — native compilation takes 2-5 min. Python with scipy/scikit-learn can take longer |

Always set to `1800` when `codeDeployPattern == "startup-install"`.

---

## Pattern C: Container-Only

When the component has a Dockerfile with backend logic, route to **Container Apps**. The Dockerfile IS the deploy strategy — no `deployStrategy` needed in `prepare-plan.json`.

The deploy phase handles: ACR build → image push → Bicep redeploy with real image. See [code-deployment-container-apps.md](../../deploy/references/code-deployment-container-apps.md).

For Java apps using Jib (`build.gradle` + `com.google.cloud.tools.jib`), the build produces a container image without a Dockerfile — push to ACR via `jib` task.
