# NestJS Knowledge Pack

> **Applies to:** Projects detected with `package.json` containing `@nestjs/core` as a dependency

## Quick Reference

| Property | Value |
|----------|-------|
| Signal files | `package.json` containing `@nestjs/core` |
| Default port | `3000` |
| Health path | `/health` |
| Base template | `templates/dockerfiles/node.Dockerfile` (+ `references/base-images.md`) |

---

## Signal Handling

NestJS lifecycle events (`OnModuleDestroy`, `BeforeApplicationShutdown`) fire only when shutdown hooks are enabled. Call `app.enableShutdownHooks()` in `main.ts` so `SIGTERM` from Kubernetes triggers graceful teardown of HTTP connections, database pools, and message queue consumers:

```typescript
const app = await NestFactory.create(AppModule);
app.enableShutdownHooks();
await app.listen(process.env.PORT || 3000);
```

The base template uses `dumb-init` as the entrypoint to forward `SIGTERM` to the Node process when running as PID 1. Both are required: `dumb-init` routes the signal, `enableShutdownHooks()` handles it.

---

## Health Endpoints

NestJS provides health checks via the `@nestjs/terminus` package.

### Installation

```bash
npm install @nestjs/terminus
```

### HealthModule

```typescript
import { Module } from '@nestjs/common';
import { TerminusModule } from '@nestjs/terminus';
import { HealthController } from './health.controller';

@Module({
  imports: [TerminusModule],
  controllers: [HealthController],
})
export class HealthModule {}
```

Register `HealthModule` in `AppModule` imports.

### HealthController with database check

```typescript
import { Controller, Get } from '@nestjs/common';
import { HealthCheck, HealthCheckService, TypeOrmHealthIndicator } from '@nestjs/terminus';

@Controller('health')
export class HealthController {
  constructor(private health: HealthCheckService, private db: TypeOrmHealthIndicator) {}
  @Get()
  @HealthCheck()
  check() {
    return this.health.check([() => this.db.pingCheck('database')]);
  }
}
```

For Prisma, use `PrismaHealthIndicator`; for MikroORM, use `MikroOrmHealthIndicator`. If no database is used, omit the indicator and return a simple status check.

### Probe configuration in Deployment manifest

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 3000
  initialDelaySeconds: 5
  periodSeconds: 15
  timeoutSeconds: 3
  failureThreshold: 3
readinessProbe:
  httpGet:
    path: /health
    port: 3000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3
```

**Note:** NestJS apps start quickly (typically under 2 seconds), so `initialDelaySeconds: 5` is sufficient. If the app performs heavy initialization (e.g., loading large config, running migrations), increase to 10–15s or add a `startupProbe`.

---

## Database Profiles

NestJS supports multiple ORM libraries. The standard pattern is a connection string or individual env vars injected via environment variables:

| ORM | Connection Pattern | Config Property |
|-----|-------------------|-----------------|
| TypeORM | `TypeOrmModule.forRoot({ url: process.env.DATABASE_URL })` | `DATABASE_URL` |
| Prisma | `datasource db { url = env("DATABASE_URL") }` in `schema.prisma` | `DATABASE_URL` |
| MikroORM | `MikroOrmModule.forRoot({ clientUrl: process.env.DATABASE_URL })` | `DATABASE_URL` |
| Sequelize | `SequelizeModule.forRoot({ uri: process.env.DATABASE_URL })` | `DATABASE_URL` |

### Environment variables for PostgreSQL on AKS

```yaml
env:
  - name: DATABASE_URL
    value: "postgresql://{{IDENTITY_NAME}}@{{PG_SERVER_NAME}}.postgres.database.azure.com:5432/{{DB_NAME}}?sslmode=require"
```

For Workload Identity, see `references/workload-identity.md`.

---

## Writable Paths (DS012 Compliance)

When `readOnlyRootFilesystem: true` is set, NestJS apps need only `/tmp` writable:

- **Multipart uploads** (e.g., `@nestjs/platform-express` with `multer`) stage files to `/tmp`
- **Logging libraries** that buffer to disk use `/tmp`
- **`node_modules` and `dist/`** are read-only at runtime

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

NestJS is Node.js-based and single-threaded. Similar to Express/Fastify.

| Resource | Request | Limit |
|----------|---------|-------|
| CPU | 100m | 500m |
| Memory | 128Mi | 256Mi |

---

## Port Configuration

- **Default port:** 3000
- **Env var override:** `PORT=3000`
- **Code pattern:** `await app.listen(process.env.PORT || 3000)` in `main.ts`

NestJS (via Express adapter) binds to `0.0.0.0` by default. For Fastify adapter, pass `'0.0.0.0'` explicitly: `await app.listen(process.env.PORT || 3000, '0.0.0.0')`.

---

## Build Commands

| Scenario | Build Command | Output | Entrypoint |
|----------|---------------|--------|------------|
| Standard | `npm run build` (invokes `nest build`) | `dist/` | `node dist/main.js` |
| Monorepo | `npx nest build <app-name>` | `dist/apps/<app-name>/` | `node dist/apps/<app-name>/main.js` |
| SWC compiler | `nest build --builder swc` | `dist/` | `node dist/main.js` |

The **SWC compiler** is ~20x faster than the default TypeScript compiler for large projects. Enable it by installing `@swc/cli @swc/core` and passing `--builder swc` or setting `"builder": "swc"` in `nest-cli.json`. SWC does not perform type checking — run `tsc --noEmit` separately in CI if type safety is required.

---

## Common Issues on AKS

| Issue | Symptom | Fix |
|-------|---------|-----|
| SIGTERM not handled | Pod takes 30s to terminate (killed by `SIGKILL` after grace period) | Call `app.enableShutdownHooks()` in `main.ts` so NestJS lifecycle events (`OnModuleDestroy`, `BeforeApplicationShutdown`) fire on `SIGTERM`; also use `dumb-init` as the container entrypoint |
| TypeORM connection pool exhaustion | `Error: Connection pool exhausted` or `ETIMEDOUT` under load | Set `extra: { max: 10 }` in TypeORM config to limit pool size; Azure PG Flexible Server has a connection limit based on SKU — monitor with `pg_stat_activity` |
| Circular dependency | `Error: Nest cannot create the ... instance` at startup | Use `forwardRef(() => Module)` in module imports; refactor shared logic into a dedicated module to break the cycle |
| dist/ not included in image | `Error: Cannot find module '/app/dist/main.js'` at container start | Ensure `COPY --from=build /app/dist ./dist` is present in the Dockerfile runtime stage; verify `nest build` runs successfully in the build stage |
| Global prefix breaks probes | Health probes return `404` after setting `app.setGlobalPrefix('api')` | The health endpoint moves to `/api/health` — update probe paths in the Deployment manifest, or exclude the health controller from the global prefix using `app.setGlobalPrefix('api', { exclude: ['health'] })` |
