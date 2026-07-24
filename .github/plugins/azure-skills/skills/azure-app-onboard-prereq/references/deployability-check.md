# Deployability Check

> ⛔ **No build/install/test commands — `npm install`, `npm test`, `dotnet build`, `dotnet restore`, `dotnet test`, `pip install`, `pytest`, `go mod download`, `cargo build`. Use static analysis only during this check.**

Assess whether the repository can feasibly be deployed to Azure and whether a preparation plan can be created.

> ⛔ **You MUST read the following in order. Skip items marked conditional if the condition is not met:**
>
> 1. [component-mapping.md](component-mapping.md) — Steps 1–2: Component→Azure mapping, existing infrastructure detection, Terraform provider classification, compose service extraction. **Conditional: monorepo only (>1 project manifest found).** For single-component repos, skip to Step 3.
> 2. [dependency-compatibility.md](dependency-compatibility.md) — Step 3: EOL runtimes/frameworks, archived repos, vulnerable apps, platform deps, Dockerfile analysis, native module detection
> 3. Steps 4–5 below

## Step 4: Recipe Feasibility

Assess whether at least one deployment recipe is viable.

| Check | Question |
|-------|----------|
| AZD feasible? | Standard web app stack? No exotic build requirements? |
| Container feasible? | Can be Dockerized? Or already has Dockerfile? |
| Functions feasible? | Event-driven or HTTP-triggered stateless handlers? |
| Terraform feasible? | User has TF experience or existing TF files? |

| Outcome | Verdict |
|---------|---------|
| At least one recipe clearly viable | ✅ PASS |
| Viable with modifications (config change, Dockerfile tweak) | 🔧 Recommended Fix — note required changes |
| Viable but requires significant rework (>5 files, architecture change) | 🔶 Major Migration — warn about scope |
| Minor platform concerns (ephemeral storage, missing .dockerignore) | ⚠️ WARN — informational |
| No viable recipe identified | ❌ FAIL |

## Step 5: Specialized Skill Detection

Check if the repo's stack requires a specialized deployment skill. If a match is found, set `context.json.routeToSkill` and `routeReason` so Step 8 routes directly.

> **Non-Azure cloud SDK deps** (AWS/GCP SDKs, Firebase, etc.) — evaluated and carried as 🔶 blockers (no `routeToSkill`); prereq stops at Step 8. See [dependency-compatibility.md § Non-Azure Cloud SDK Dependencies](dependency-compatibility.md).

| Dependency / Pattern | `routeToSkill` | `routeReason` |
|---------------------|----------------|---------------|
| `@github/copilot-sdk`, `github-copilot-sdk`, `GitHub.CopilotSdk` | `azure-hosted-copilot-sdk` | `copilot-sdk-detected` |
| `azure_ai_projects`, `azure-ai-agents`, `foundry-agents` | `microsoft-foundry` | `foundry-agents-detected` |

## f1Viable Aggregation

After the deployability check completes, cross-check `buildRequirements.f1Viable`. The build axis may have set an initial value — the deployability check MUST override it to `false` if ANY blocker was found during [dependency-compatibility.md § Native Module Detection](dependency-compatibility.md) or [§ F1 Viability — Beyond Native Modules](dependency-compatibility.md). Verify `f1BlockReason` is populated when `f1Viable: false`.
