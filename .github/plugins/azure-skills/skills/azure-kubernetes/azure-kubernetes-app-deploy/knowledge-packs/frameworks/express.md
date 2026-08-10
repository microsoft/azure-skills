# Express / Fastify Knowledge Pack

> **Applies to:** Projects detected with `package.json` containing `express` or `fastify` as a dependency

## Quick Reference

| Property | Value |
|----------|-------|
| Signal files | `package.json` containing `express` or `fastify` |
| Default port | `3000` |
| Health path | `/healthz` |
| Base template | `templates/dockerfiles/node.Dockerfile` (+ `references/base-images.md`) |

---

## Signal Handling

Node.js does not handle `SIGTERM` correctly when running as PID 1. The base template includes `dumb-init` as the entrypoint to forward signals properly; no application-level changes are needed unless the app registers explicit cleanup handlers.

### Fastify listen caveat

Fastify defaults to listening on `127.0.0.1`, which is unreachable from outside the container. Bind to `0.0.0.0` explicitly:

```js
await fastify.listen({ port: 3000, host: '0.0.0.0' });
```

If the pod starts but health probes fail with `connection refused`, this is almost always the cause. Express already binds to `0.0.0.0` by default — no change needed for Express apps.

### Package manager variants

| Package Manager | Install (all) | Install (prod only) | Lock File |
|----------------|---------------|---------------------|-----------|
| npm | `npm ci` | `npm ci --omit=dev` | `package-lock.json` |
| yarn | `yarn install --frozen-lockfile` | `yarn install --frozen-lockfile --production` | `yarn.lock` |
| pnpm | `pnpm install --frozen-lockfile` | `pnpm install --frozen-lockfile --prod` | `pnpm-lock.yaml` |

Copy the correct lock file in the Dockerfile `COPY` step to match the project's package manager.

---

## Health Endpoints

Node.js frameworks do not provide health endpoints out of the box. Add a `/healthz` route manually.

### Express

```js
app.get('/healthz', (req, res) => {
  res.status(200).json({ status: 'UP' });
});
```

### Fastify

```js
fastify.get('/healthz', async () => {
  return { status: 'UP' };
});
```

For richer checks (database connectivity, downstream services), extend the handler to verify dependencies and return `503` when unhealthy.

### Probe configuration in Deployment manifest

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 3000
  initialDelaySeconds: 5
  periodSeconds: 15
  timeoutSeconds: 3
  failureThreshold: 3
readinessProbe:
  httpGet:
    path: /healthz
    port: 3000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3
```

**Note:** Node.js apps start in under a second, so `initialDelaySeconds: 5` is sufficient. No `startupProbe` is needed unless the app performs heavy initialization (e.g., loading ML models).

---

## Database Profiles

Node.js projects use a variety of database libraries. The standard pattern is a `DATABASE_URL` connection string injected via environment variable:

| Library | Connection Pattern | Config Property |
|---------|-------------------|-----------------|
| `pg` (node-postgres) | `new Pool({ connectionString: process.env.DATABASE_URL })` | `DATABASE_URL` |
| Prisma | `datasource db { url = env("DATABASE_URL") }` in `schema.prisma` | `DATABASE_URL` |
| Sequelize | `new Sequelize(process.env.DATABASE_URL)` | `DATABASE_URL` |
| Knex | `connection: process.env.DATABASE_URL` in `knexfile.js` | `DATABASE_URL` |

### Environment variables for PostgreSQL on AKS

```yaml
env:
  - name: DATABASE_URL
    value: "postgresql://{{IDENTITY_NAME}}@{{PG_SERVER_NAME}}.postgres.database.azure.com:5432/{{DB_NAME}}?sslmode=require"
  - name: PGHOST
    value: "{{PG_SERVER_NAME}}.postgres.database.azure.com"
  - name: PGDATABASE
    value: "{{DB_NAME}}"
  - name: PGUSER
    value: "{{IDENTITY_NAME}}"
  - name: PGPORT
    value: "5432"
  - name: PGSSLMODE
    value: "require"
```

For Workload Identity with passwordless authentication, use the `@azure/identity` package with `pg` to obtain Azure AD tokens instead of passwords.

---

## Writable Paths (DS012 Compliance)

When `readOnlyRootFilesystem: true` is set, Node.js apps need only `/tmp` writable:

- **Multipart uploads** (e.g., `multer`, `@fastify/multipart`) stage files to `/tmp`
- **Logging libraries** that buffer to disk use `/tmp`

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

---

## Resource Sizing

Node.js is single-threaded and relatively lightweight. These are starting-point defaults — tune based on observed usage.

| Resource | Request | Limit |
|----------|---------|-------|
| CPU | 100m | 500m |
| Memory | 128Mi | 256Mi |

For memory-intensive workloads (large payloads, SSR), increase the memory limit and set `--max-old-space-size` to ~75% of the limit.

---

## Port Configuration

- **Default port:** 3000
- **Env var override:** `PORT=3000`
- **Code pattern:** `app.listen(process.env.PORT || 3000)`

Express binds to `0.0.0.0` by default, so it is reachable from outside the container without additional configuration.

Fastify binds to `127.0.0.1` by default — **you must pass `host: '0.0.0.0'`** in the `listen()` call or the pod will start but all probes and traffic will fail with `connection refused`.

---

## Build Commands

| Scenario | Build Command | Output | Entrypoint |
|----------|---------------|--------|------------|
| TypeScript | `npm run build` (invokes `tsc`) | `dist/` | `node dist/index.js` |
| JavaScript (no build) | None | `src/` | `node src/index.js` |
| Bundler (esbuild/webpack) | `npm run build` | `dist/bundle.js` | `node dist/bundle.js` |

For TypeScript projects, ensure `tsconfig.json` has `"outDir": "dist"` and the Dockerfile copies the `dist/` folder to the runtime stage. Do **not** install `typescript` or `ts-node` in the production image.

---

## Common Issues on AKS

| Issue | Symptom | Fix |
|-------|---------|-----|
| No SIGTERM handling | Pod takes 30s to terminate (killed by `SIGKILL` after grace period) | Use `dumb-init` as entrypoint, or add explicit `process.on('SIGTERM', ...)` handler to close the server gracefully |
| ECONNRESET on PostgreSQL | `Error: Connection terminated unexpectedly` | Configure pool `idleTimeoutMillis` and `connectionTimeoutMillis`; Azure PG Flexible Server closes idle connections after ~5 min |
| Fastify localhost binding | Health probes fail with `connection refused` despite app running | Pass `host: '0.0.0.0'` to `fastify.listen()` — Fastify defaults to `127.0.0.1` |
| node_modules bloat | Image > 500MB, slow pulls from ACR | Run `npm ci --omit=dev` in a separate stage; consider esbuild bundling for single-file output |
| Memory leak under load | Pod `OOMKilled` after hours of traffic | Set `--max-old-space-size` to ~75% of container memory limit (e.g., `--max-old-space-size=384` for 512Mi limit); profile with `--inspect` locally |
