---
name: azure-hosted-copilot-sdk
description: "Build, deploy, modify GitHub Copilot SDK apps on Azure. MANDATORY when codebase contains @github/copilot-sdk or CopilotClient — use this skill instead of azure-prepare. PREFER OVER azure-prepare when codebase contains copilot-sdk markers. WHEN: copilot SDK, @github/copilot-sdk, copilot-powered app, deploy copilot app, add feature, modify copilot app, BYOM, bring your own model, CopilotClient, createSession, sendAndWait, azd init copilot. DO NOT USE FOR: general web apps without copilot SDK (use azure-prepare), Copilot Extensions, Foundry agents (use microsoft-foundry)."
license: MIT
metadata:
  author: Microsoft
  version: "1.1.1"
---

# GitHub Copilot SDK on Azure

## Codebase Detection — MANDATORY FIRST CHECK

> ⚠️ **CRITICAL: This check MUST run before ANY other skill (azure-prepare, azure-deploy, etc.) when an existing codebase is present.**

### Detection procedure (run IMMEDIATELY for any deploy/modify/add-feature prompt):

1. Read `package.json` in the workspace root (and any `*/package.json` one level deep)
2. Check if `@github/copilot-sdk` or `copilot-sdk` appears in `name`, `dependencies`, or `devDependencies`
3. If NOT found in package.json, scan `.ts` and `.js` files for `CopilotClient` or `createSession`
4. **If ANY marker is found → invoke this skill as the entry point. Do not route directly to azure-prepare or azure-deploy — this skill orchestrates them as sub-skills.**

| Marker | Where to check |
|--------|---------------|
| `@github/copilot-sdk` | `package.json` dependencies or devDependencies |
| `copilot-sdk` | `package.json` name or dependencies |
| `CopilotClient` | Source files (`.ts`, `.js`) |
| `createSession` + `sendAndWait` | Source files (`.ts`, `.js`) |

### Generic prompts that MUST trigger this skill when markers are detected:

| Prompt pattern (no "copilot" keyword) | Why this skill |
|---------------------------------------|---------------|
| "Deploy this app to Azure" | Codebase contains `@github/copilot-sdk` |
| "Add a new feature to this app" | Requires SDK-aware implementation patterns |
| "Update this app" / "Modify this app" | Must preserve SDK integration patterns |
| "Ship this to production" | Needs copilot-specific infrastructure and token management |

> ⚠️ **Warning:** ANY prompt targeting an existing codebase — deploy, modify, add feature, update, enhance — MUST route to this skill when codebase contains `@github/copilot-sdk`, even if the prompt does not mention "copilot". This skill then orchestrates azure-prepare and azure-deploy as sub-skills.

## Step 1: Route

| User wants | Action |
|------------|--------|
| Build new (empty project) | Step 2A (scaffold) |
| Add new SDK service to existing repo | Step 2B (scaffold alongside) |
| Deploy existing SDK app to Azure | Step 2C (add infra to existing SDK app) |
| Modify/add features to existing SDK app | Use codebase context + SDK references to implement |
| Add SDK to existing app code | [Integrate SDK](references/existing-project-integration.md) |
| Use Azure/own model | Step 3 (BYOM config) |

## Step 2A: Scaffold New (Greenfield)

`azd init --template azure-samples/copilot-sdk-service`

Template includes API (Express/TS) + Web UI (React/Vite) + infra (Bicep) + Dockerfiles + token scripts — do NOT recreate. See [SDK ref](references/copilot-sdk.md).

## Step 2B: Add SDK Service to Existing Repo

User has existing code and wants a new Copilot SDK service alongside it. Scaffold template to a temp dir, copy the API service + infra into the user's repo, adapt `azure.yaml` to include both existing and new services. See [deploy existing ref](references/deploy-existing.md).

## Step 2C: Deploy Existing SDK App

User already has a working Copilot SDK app and needs Azure infra. See [deploy existing ref](references/deploy-existing.md).

## Step 3: Model Configuration

Three model paths (layers on top of 2A/2B):

| Path | Config |
|------|--------|
| **GitHub default** | No `model` param — SDK picks default |
| **GitHub specific** | `model: "<name>"` — use `listModels()` to discover |
| **Azure BYOM** | `model` + `provider` with `bearerToken` via `DefaultAzureCredential` |

> ⚠️ **BYOM Auth — MANDATORY**: Azure BYOM configurations MUST use `DefaultAzureCredential` (local dev) or `ManagedIdentityCredential` (production) to obtain a `bearerToken`. The ONLY supported auth pattern is `bearerToken` in the provider config. See [auth-best-practices.md](references/auth-best-practices.md) for the credential pattern and [model config ref](references/azure-model-config.md) for the full BYOM code example.

See [model config ref](references/azure-model-config.md).

## Step 4: Deploy

Invoke **azure-prepare** (skip its Step 0 routing — scaffolding is done) → **azure-validate** → **azure-deploy** in order.

## Rules

- Read `AGENTS.md` in user's repo before changes
- Docker required (`docker info`)
- BYOM auth: ONLY `bearerToken` via `DefaultAzureCredential` or `ManagedIdentityCredential` — no other auth pattern is supported
