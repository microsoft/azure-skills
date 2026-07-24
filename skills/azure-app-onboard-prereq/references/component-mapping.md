Component-to-Azure mapping and existing infrastructure detection. Part of the [deployability check](deployability-check.md).

## Step 1: Component Mapping Feasibility

Determine if each detected component maps to a known Azure service.

| Component Type | Mappable Azure Services |
|----------------|------------------------|
| SPA / Static Site | Static Web Apps, Blob + CDN |
| SSR Web App | Container Apps, App Service |
| REST / GraphQL API | Container Apps, App Service, Functions |
| Background Worker | Container Apps, Functions |
| Scheduled Task | Functions (Timer Trigger) |
| Event Processor | Functions, Container Apps |
| CLI Tool | Not directly deployable — flag |

| Outcome | Verdict |
|---------|---------|
| All components map to Azure services | ✅ PASS |
| Some components need clarification | ⚠️ WARN |
| Unknown component type, can't map | ⚠️ WARN — ask user for context |
| Component is fundamentally incompatible | ❌ FAIL |

## Step 2: Existing Infrastructure Check

Check if the repo already has Azure infrastructure or deployment config.

| Found | Implication |
|-------|-------------|
| `azure.yaml` | AZD project — may only need update |
| `infra/*.bicep` | Bicep IaC exists |
| `infra/*.tf` or `*.tf` | Terraform IaC exists — classify provider (see below) |
| `Dockerfile` | Containerization ready |
| `.github/workflows/` | CI/CD configured |
| `azure-pipelines.yml` | Azure DevOps CI/CD |
| `docker-compose.yml` | Multi-container setup — parse for service dependencies |
| None of the above | Greenfield — full prep needed |

Record what exists; this feeds into recipe selection during azure-prepare.

### Terraform Provider Classification

When `.tf` files are detected, read `versions.tf`, `provider.tf`, or `main.tf` to identify `required_providers`. Classify and write to `context.json.detectedInfraProvider.terraform`:

| `required_providers` contains | Classification | Scaffold behavior |
|-------------------------------|---------------|-------------------|
| `hashicorp/azurerm` only | `"azure"` | Halt — existing Azure IaC |
| `hashicorp/google` or `hashicorp/google-beta` (no `azurerm`) | `"gcp"` | Generate Azure TF alongside |
| `hashicorp/aws` (no `azurerm`) | `"aws"` | Generate Azure TF alongside |
| Multiple cloud providers including `azurerm` | `"multi"` | Halt — Azure IaC already present |
| Multiple cloud providers without `azurerm` | `"multi"` | Generate Azure TF alongside |
| No provider block found or only non-cloud providers | `"unknown"` | Halt — ask user to clarify |

Also check for `azure.yaml` coexistence: if BOTH `azure.yaml` AND non-Azure `.tf` exist → `azure.yaml` takes priority → route to `azure-deploy`, not AppOnboard scaffold.

### Compose Service Dependency Extraction

When `docker-compose.yml` or `compose.yml` is found, parse `services:` for infrastructure dependencies. Map known images to `detectedServices[]` entries (`DetectedService` in `session-schemas.ts`):

| Image pattern | `type` | Version source |
|--------------|--------|----------------|
| `postgres:*` | `postgresql` | Image tag (e.g., `postgres:16` → `"16"`) |
| `redis:*` / `redis/redis-stack:*` | `redis` | Image tag |
| `*kafka*` (bitnami, confluent, etc.) | `kafka` | Image tag |
| `elasticsearch:*` / `opensearchproject/*` | `elasticsearch` | Image tag |
| `mariadb:*` | `mariadb` | Image tag |
| `mongo:*` | `mongodb` | Image tag |
| `rabbitmq:*` | `rabbitmq` | Image tag |
| `minio/*` | `minio` | Image tag |
| `mysql:*` | `mysql` | Image tag |

Set `source: "compose"` on each. If no tag or `latest`, omit `version`. Skip the app's own service entries (services with `build:` context pointing to the repo).

### Compose Hostname Detection

After extracting compose services, grep app source code and config files for compose service names used as hostnames. Compose DNS names (e.g., `postgres`, `redis`, `api`) resolve inside Docker networks but NOT on Azure PaaS.

**Detection:** For each extracted service name, search app config files (`.env`, `config.*`, `application.*`, `settings.*`) and source code for patterns like `host=<service_name>`, `<service_name>:<port>`, `://<service_name>:`, or `<service_name>.` used as a hostname. Common examples: `host=postgres`, `redis://redis:6379`, `PGHOST=db`.

**Verdict:** ⚠️ WARN — `id: W-COMPOSE-HOSTNAME`. "App references Docker Compose service name `{name}` as a hostname. On Azure, use the managed service endpoint (set via environment variable) instead." Include in `postDeployRecommendations[]`: `{ "title": "Replace compose hostnames with Azure endpoints", "reason": "Compose DNS names don't resolve on Azure PaaS", "effort": "low", "services": ["{mapped Azure service}"] }`.
