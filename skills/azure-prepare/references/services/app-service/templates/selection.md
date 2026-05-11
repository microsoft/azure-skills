# Template Selection Decision Tree — REFERENCE ONLY

**CRITICAL**: Check for specific scenario indicators IN ORDER before defaulting to Web API.

**Architecture**: All deployments start from a base template per language/scenario. Integrations are applied as [composable recipes](recipes/README.md) on top of the base. See [composition.md](recipes/composition.md) for the merge algorithm.

Cross-reference with [App Service overview](https://learn.microsoft.com/en-us/azure/app-service/overview) and [official AZD gallery templates](https://azure.github.io/awesome-azd/?tags=appservice).

```
1. Is this a full-stack web app with server-side rendering?
   Indicators: Razor Pages, MVC views, Next.js SSR, Nuxt, Django templates,
               server-rendered HTML, .cshtml, EJS/Pug, Jinja2
   └─► YES → web-app base template (see [web-app.md](web-app.md))

2. Is this a background worker or WebJob?
   Indicators: WebJob, IHostedService, BackgroundService, worker,
               queue processor, scheduled task (no HTTP endpoints)
   └─► YES → Use Worker Service template (out of scope — see Functions or Container Apps)

3. Does it use Azure SQL or PostgreSQL?
   Indicators: DbContext, EF Core, Prisma, SQLAlchemy, connection string,
               Microsoft.EntityFrameworkCore, @prisma/client, psycopg2
   └─► YES → Web API base + sql recipe (IaC + RBAC + source)
   Recipe: recipes/sql/ ✅ Available

4. Does it use Cosmos DB?
   Indicators: CosmosClient, @azure/cosmos, azure-cosmos, CosmosDBConnection,
               Microsoft.Azure.Cosmos, container.read_item
   └─► YES → Web API base + cosmos recipe (IaC + RBAC + source)
   Recipe: recipes/cosmos/ ✅ Available

5. Does it require authentication?
   Indicators: [Authorize], Microsoft.Identity.Web, passport-azure-ad,
               msal, EasyAuth, /.auth/login, authsettingsV2
   └─► YES → base + auth recipe (Easy Auth or MSAL config)
   Recipe: recipes/auth/ ✅ Available

6. Does it use Redis caching?
   Indicators: IDistributedCache, StackExchange.Redis, ioredis, redis,
               azure-cache-redis, aioredis
   └─► YES → base + redis recipe (IaC + RBAC + source)
   Recipe: recipes/redis/ ✅ Available

7. DEFAULT → Web API base template by runtime (see [web-api.md](web-api.md))
```

## Base Templates

| Scenario | Template Reference |
|----------|-------------------|
| Full-stack web app with server-side rendering | [web-app.md](web-app.md) |
| REST API / headless backend (default) | [web-api.md](web-api.md) |

## Recipe Types

| Type | IaC Delta? | Examples |
|------|-----------|----------|
| **Full recipe** | Yes — Bicep module + RBAC + networking | sql, cosmos, redis, auth |
| **Source-only** | No — only application code patterns | health checks |

## Critical Rules

> See [Critical Rules](recipes/composition.md#critical-rules) in composition.md (canonical).
