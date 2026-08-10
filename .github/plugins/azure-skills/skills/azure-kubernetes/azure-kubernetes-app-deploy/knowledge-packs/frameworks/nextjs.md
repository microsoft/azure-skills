# Next.js Knowledge Pack

> **Applies to:** Projects detected with `package.json` containing `next` as a dependency

## Quick Reference

| Property | Value |
|----------|-------|
| Signal files | `package.json` containing `next` |
| Default port | `3000` |
| Health path | `/api/health` |
| Base template | `templates/dockerfiles/node.Dockerfile` (+ `references/base-images.md`) |

---

## Standalone Output (Required)

Next.js standalone output mode is critical for containerized deployments — it reduces the image from ~1GB to ~100MB by bundling only the files needed to run the server. Without it, the build copies all of `node_modules` into the image.

Enable it in `next.config.js` (or `next.config.mjs` / `next.config.ts`):

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
};

module.exports = nextConfig;
```

The build then produces `.next/standalone/server.js`, a self-contained HTTP server that does not require the `next` CLI at runtime.

### Three required COPY targets

The Dockerfile runtime stage needs exactly three items from the build stage:

1. `public/` — static assets served directly
2. `.next/standalone/` — the standalone server and its bundled dependencies
3. `.next/static/` — client-side JS/CSS bundles (must be copied into `.next/static` inside the standalone directory, not alongside it)

### Hostname binding

Set `HOSTNAME="0.0.0.0"` as a runtime environment variable (required for Next.js 14+). The standalone `server.js` reads this variable on startup to listen on all interfaces. Without it, the server binds to `127.0.0.1` and Kubernetes probes fail.

Set `NEXT_TELEMETRY_DISABLED=1` in both the build stage and the runtime stage to prevent outbound telemetry calls to `telemetry.nextjs.org` from the container.

---

## Health Endpoints

Next.js does not provide health endpoints out of the box. Add a custom API route — the implementation depends on whether the project uses App Router or Pages Router.

### App Router (Next.js 13.4+)

Create `app/api/health/route.ts`:

```ts
import { NextResponse } from 'next/server';

export async function GET() {
  return NextResponse.json({ status: 'UP' });
}

export const dynamic = 'force-dynamic';
```

The `force-dynamic` export prevents Next.js from statically caching the health response at build time.

### Pages Router

Create `pages/api/health.ts`:

```ts
import type { NextApiRequest, NextApiResponse } from 'next';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  res.status(200).json({ status: 'UP' });
}
```

### Probe configuration in Deployment manifest

```yaml
livenessProbe:
  httpGet:
    path: /api/health
    port: 3000
  initialDelaySeconds: 10
  periodSeconds: 15
  timeoutSeconds: 3
  failureThreshold: 3
readinessProbe:
  httpGet:
    path: /api/health
    port: 3000
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3
```

**Note:** Next.js standalone server starts in 1–3 seconds, but `initialDelaySeconds: 10` provides a safe margin for cold starts and environment variable resolution. No `startupProbe` is needed unless the app performs heavy server-side initialization.

---

## Database Profiles

Next.js apps commonly use Prisma, Drizzle, or `pg` (node-postgres) for database access. All follow the `DATABASE_URL` connection string pattern:

| Library | Connection Pattern | Config Property |
|---------|-------------------|-----------------|
| Prisma | `datasource db { url = env("DATABASE_URL") }` in `schema.prisma` | `DATABASE_URL` |
| Drizzle | `postgres(process.env.DATABASE_URL!)` or `drizzle(process.env.DATABASE_URL!)` | `DATABASE_URL` |
| `pg` (node-postgres) | `new Pool({ connectionString: process.env.DATABASE_URL })` | `DATABASE_URL` |

### Environment variables for PostgreSQL on AKS

```yaml
env:
  - name: DATABASE_URL
    value: "postgresql://{{IDENTITY_NAME}}@{{PG_SERVER_NAME}}.postgres.database.azure.com:5432/{{DB_NAME}}?sslmode=require"
```

For Workload Identity, see `references/workload-identity.md`.

---

## Writable Paths (DS012 Compliance)

When `readOnlyRootFilesystem: true` is set, Next.js needs **two** writable paths:

- **`/tmp`** — general-purpose temporary file storage
- **`/app/.next/cache`** — ISR (Incremental Static Regeneration) page cache and `next/image` optimization cache; without this, ISR and image optimization fail with `EROFS: read-only file system` errors

### Required volume mounts

```yaml
volumes:
  - name: tmp
    emptyDir: {}
  - name: next-cache
    emptyDir: {}
containers:
  - name: app
    volumeMounts:
      - name: tmp
        mountPath: /tmp
      - name: next-cache
        mountPath: /app/.next/cache
```

Both mounts are required. Missing the cache mount is the most common cause of ISR failures on AKS.

---

## Resource Sizing

Next.js SSR needs more memory than a plain API due to React rendering. Static-only exports can use lower limits.

| Resource | Request | Limit |
|----------|---------|-------|
| CPU | 200m | 1000m |
| Memory | 256Mi | 512Mi |

---

## Port Configuration

- **Default port:** 3000
- **Env var override:** `PORT=3000`
- **Hostname binding:** `HOSTNAME="0.0.0.0"` (Next.js 14+)

The standalone `server.js` reads the `PORT` and `HOSTNAME` environment variables automatically. No code changes are needed to customize the port.

---

## Build Commands

| Scenario | Build Command | Output | Entrypoint |
|----------|---------------|--------|------------|
| Standalone build (required) | `npm run build` with `output: 'standalone'` | `.next/standalone/server.js` | `node server.js` |
| Standard build (not for containers) | `npm run build` | `.next/` (full) | `next start` |

Always use the standalone build for container deployments. The standard build requires the full `node_modules` directory at runtime, resulting in images 5–10x larger.

### sharp for next/image

If the app uses `next/image`, install `sharp` explicitly in the runtime stage. Without it, Next.js falls back to the slower `squoosh` library and image optimization may fail under load.

---

## Common Issues on AKS

| Issue | Symptom | Fix |
|-------|---------|-----|
| Image too large without standalone | Image > 1GB, slow pulls from ACR | Set `output: 'standalone'` in `next.config.js` — reduces image to ~100MB |
| Static assets 404 | CSS/JS files return 404 after deployment | Ensure `.next/static` is copied to `.next/static` in the runtime stage (not into `standalone/.next/static`) |
| ISR fails with read-only filesystem | `EROFS: read-only file system` when revalidating pages | Mount `emptyDir` volume at `/app/.next/cache` — ISR writes regenerated pages to the cache directory |
| next/image optimization fails | Images return 500 or timeout under load | Install `sharp` explicitly; the standalone build may not include it automatically |
| Env vars undefined (`NEXT_PUBLIC_` prefix) | Client-side code sees `undefined` for environment variables | `NEXT_PUBLIC_` vars are inlined at **build time**, not runtime; set them as build args in the Dockerfile or use runtime config via `publicRuntimeConfig` |
| Telemetry calls from container | Unexpected outbound network requests to `telemetry.nextjs.org` | Set `NEXT_TELEMETRY_DISABLED=1` in both the build stage and runtime stage of the Dockerfile |
