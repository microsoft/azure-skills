# Full-Stack Web App Template — REFERENCE ONLY

Template for server-side rendered web applications on Azure App Service. Use for MVC, Razor Pages, Next.js SSR, Django, or React+API patterns.

## Templates by Pattern

| Pattern | AZD Template | Framework |
|---------|-------------|-----------|
| React + C# API | `azd init -t todo-csharp` | React SPA + ASP.NET Core API |
| React + Node.js API | `azd init -t todo-nodejs-mongo` | React SPA + Express API |
| React + Python API | `azd init -t todo-python-mongo` | React SPA + FastAPI |
| React + Java API | `azd init -t todo-java-mongo` | React SPA + Spring Boot |

**Browse all:** [Awesome AZD](https://azure.github.io/awesome-azd/?tags=appservice)

> 💡 **Tip:** For static frontends with API backends, consider Azure Static Web Apps instead. Use App Service when you need full server-side rendering.

## Architecture Patterns

### Pattern A: Single App Service (API + static files)

```
App Service (Linux)
├── /api/*    → Backend routes
└── /*        → Static files (React/Vue build output)
```

Best for: Simple apps, MVPs, Razor Pages, Django with templates.

### Pattern B: Separate frontend + backend

```
App Service (frontend) ← React/Next.js SSR
      │
      └──► App Service (backend) ← REST API
```

Best for: Independent scaling, team separation, microservices.

## Project Structure (Single App)

```
project-root/
├── azure.yaml
├── infra/
│   ├── main.bicep
│   └── app/
│       └── web.bicep
└── src/
    ├── api/              # Backend
    │   ├── Program.cs    # or app.py / index.js
    │   └── ...
    └── web/              # Frontend (built output served as static)
        ├── package.json
        └── src/
```

## azure.yaml (multi-service)

```yaml
name: my-web-app
services:
  web:
    project: ./src/web
    host: appservice
    language: js
    dist: build
  api:
    project: ./src/api
    host: appservice
    language: csharp
```

## Server-Side Rendering Examples

### ASP.NET Core MVC / Razor Pages

```csharp
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddControllersWithViews();
var app = builder.Build();
app.UseStaticFiles();
app.MapControllerRoute(name: "default", pattern: "{controller=Home}/{action=Index}/{id?}");
app.MapGet("/health", () => Results.Ok(new { status = "healthy" }));
app.Run();
```

### Next.js (SSR on App Service)

```javascript
// next.config.js
module.exports = {
  output: 'standalone',  // Required for App Service deployment
};
```

Startup command in App Service:
```bash
node server.js
```

### Django

```python
# settings.py
ALLOWED_HOSTS = ['.azurewebsites.net', 'localhost']
STATIC_ROOT = BASE_DIR / 'staticfiles'
CSRF_TRUSTED_ORIGINS = ['https://*.azurewebsites.net']
```

### Express + React (served from build)

```javascript
const express = require('express');
const path = require('path');
const app = express();

app.use(express.json());
app.use('/api', apiRouter);
app.use(express.static(path.join(__dirname, '../web/build')));
app.get('/health', (req, res) => res.json({ status: 'healthy' }));
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '../web/build/index.html'));
});

app.listen(process.env.PORT || 3000);
```

## App Service Configuration

```bicep
resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  properties: {
    siteConfig: {
      linuxFxVersion: 'NODE|24-lts'  // or DOTNETCORE|10.0, PYTHON|3.14
      healthCheckPath: '/health'
      appCommandLine: ''              // Custom startup command if needed
      appSettings: [
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'WEBSITE_NODE_DEFAULT_VERSION', value: '~24' }
      ]
    }
  }
  tags: {
    'azd-service-name': 'web'
  }
}
```

## Startup Commands by Runtime

| Runtime | Startup Command | Notes |
|---------|----------------|-------|
| ASP.NET Core | (auto-detected) | No command needed |
| Node.js | `node server.js` or `npm start` | Set via `appCommandLine` |
| Python (Django) | `gunicorn myapp.wsgi` | Use gunicorn for production |
| Python (FastAPI) | `uvicorn main:app --host 0.0.0.0` | Use uvicorn for ASGI |
| Next.js SSR | `node server.js` | Use `output: 'standalone'` |

## Deployment

```bash
ENV_NAME="$(basename "$PWD" | tr '[:upper:]' '[:lower:]' | tr ' _' '-')-dev"
azd init -t <template> -e "$ENV_NAME" --no-prompt
azd env set AZURE_LOCATION eastus2
azd up --no-prompt
```

**PowerShell:**
```powershell
$ENV_NAME = "$(Split-Path -Leaf (Get-Location) | ForEach-Object { $_.ToLower() -replace '[ _]','-' })-dev"
azd init -t <template> -e $ENV_NAME --no-prompt
azd env set AZURE_LOCATION eastus2
azd up --no-prompt
```

## References

- [Deploy to App Service](https://learn.microsoft.com/en-us/azure/app-service/quickstart-dotnetcore)
- [Node.js on App Service](https://learn.microsoft.com/en-us/azure/app-service/quickstart-nodejs)
- [Python on App Service](https://learn.microsoft.com/en-us/azure/app-service/quickstart-python)
