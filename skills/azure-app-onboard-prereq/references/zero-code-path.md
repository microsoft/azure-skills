# Zero-Code Path

When the workspace is empty (no project files, no Dockerfile), prereq scaffolds a starter project before evaluating.

## Step 0: Check Existing Context

⛔ **Before asking anything, check `context.json.intent.userPrompt`.** The orchestrator (or the user's original message on direct entry) already captured what the user wants. If `userPrompt` contains an app description (e.g., "build me a todo app", "REST API with auth", "a notes app with three tabs"), treat it as the answer to "what are you building?" and skip directly to Step 2 (recommend stack). Only ask Step 1's question if `userPrompt` is vague ("help me get started", "deploy to Azure") or empty.

## Flow

1. **Ask what they want to build** (skip if Step 0 resolved it): *"What kind of app are you building?"* (e.g., "a todo app", "REST API"). Users know what they want, not what stack to use.
2. **Recommend a stack** based on the app description (from `userPrompt` or Step 1): *"For a REST API with a database, I'd suggest Node.js with a framework like Express or Fastify. Sound good?"* User can accept or override.
3. ⛔ **Confirm before scaffolding** via `ask_user`.
4. **Scaffold minimal starter project** — ⛔ **You MUST read [subagent-starter-scaffold.md](subagent-starter-scaffold.md).** Your NEXT action MUST be a `task` call with the FULL template text (verbatim) + app description + chosen stack + workspace path + data needs flag + multi-page flag. Do NOT generate code inline — the sub-agent applies starter patterns internally and writes files to the workspace. After the sub-agent returns, verify the file list is non-empty and proceed to Step 5.
5. **Validate generated code** — ⛔ **When the agent has WRITTEN code from scratch, offer to run build validation before evaluation.** The generated code has never been tested. Present: **"I've scaffolded your app. Want me to install dependencies, build, and run tests? (Yes / Skip)"** ⛔ **General prior consent** (e.g., "yes", "go ahead", "fix it") **does NOT constitute consent** — the user must answer THIS specific question. If they say Skip, run nothing.
   - If **Yes**: run `npm install` → `npm run build` → `npm test` (or stack equivalent). If any step fails, fix the issue and retry (max 2 attempts). This is allowed because the agent WROTE the code — it's not an existing repo.
   - If **Skip**: proceed to Step 6. The deploy phase will handle builds via Oryx/ACR.
   - ⛔ **This gate applies ONLY to code the agent generated from scratch.** It does NOT apply to existing repos — those follow the deploy-as-is principle with the ABSOLUTE PROHIBITION on `npm install` during prereq.
6. Run the full 3-axis evaluation (from prereq Step 3) on the scaffolded code.
7. Continue to prereq Step 4 (write artifacts + readiness gate).

## Rules

- Max 3 interactions before scaffolding begins (counting from Step 1 — Step 0's `userPrompt` check doesn't count as an interaction).
- Scaffold dynamically based on app description — no hardcoded templates. Read the stack ecosystem's conventions (e.g., `npm init` patterns for Node, `dotnet new webapi` patterns for .NET).
- If user gives no app description after 2 attempts AND `userPrompt` was also vague: *"I can't evaluate an empty workspace without knowing what you want to build. Try: 'I want to build a REST API' or 'Help me scaffold a Node.js API.'"*
- ⛔ **Do NOT generate Azure infrastructure (Bicep/Terraform/azure.yaml) here.** This path creates application source code only. Infrastructure is the scaffold phase's job.
- The generated code should be functional enough to start locally (e.g., `node index.js` serves HTTP on a port) so prereq's evaluation has something real to assess.
