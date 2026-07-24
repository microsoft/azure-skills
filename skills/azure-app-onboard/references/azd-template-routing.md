# azd Template Routing

When prereq detects an existing azd template, AppOnboard routes to `azure-prepare` instead of continuing the greenfield pipeline. AppOnboard is a greenfield deployment skill — repos with existing Azure IaC belong to the prepare → validate → deploy pipeline.

## Detection

Before the scope triage question (Step 2), do a quick file-system check (workspace root + `infra/` only — never scan `.copilot-azure/`). Route if ALL of these are true:

| Condition | Where to check |
|-----------|----------------|
| `azure.yaml` exists in workspace root | File system scan |
| `*.bicep` or `*.tf` files exist in `infra/` | File system scan |
| `azure.yaml` has `services:` with at least 1 entry | Read `azure.yaml` in workspace root |

If only `azure.yaml` is present without IaC files (partial azd setup), continue AppOnboard pipeline — the repo needs IaC generated.

## Gate — presented as the scope triage question

When an azd template is detected, the scope triage question is replaced with an azd-aware version (see [intent-gathering.md § Scope triage](intent-gathering.md)). Present:

```
📦 **Existing Azure deployment setup detected**

Your repo already has:
- `azure.yaml` — Azure Developer CLI configuration
- `infra/` — {Bicep|Terraform} infrastructure templates
{list any other detected infra: Dockerfiles, CI/CD workflows}

This is a complete azd template — it already defines how to build and deploy your app.

**How would you like to proceed?**

1. **Deploy with existing setup** — I'll hand off to `azure-prepare`, which works with azd templates natively. It will analyze your IaC, plan the deployment, and walk you through `azd up`.

2. **Start fresh** — Ignore the existing IaC and build new infrastructure from scratch using AppOnboard's greenfield pipeline. Your existing files won't be modified.

3. **Just scan for readiness** — Keep the prereq results (your app is {ready|needs fixes}) and stop here.
```

## Routing protocol

**Option 1 — Deploy with existing setup:**

1. Write routing state to `context.json`:
   ```json
   {
     "routeToSkill": "azure-prepare",
     "routeReason": "existing-azd-template",
     "completedPhases": [],
     "currentPhase": null,
     "statusSummary": "Routed to azure-prepare — existing azd template detected, prereq scan skipped (not needed for existing IaC)"
   }
   ```
2. Tell the user:
   ```
   ✅ Your app is healthy — prereq scan found no blockers.

   Since your repo has a complete azd setup, I'm handing off to **azure-prepare** — it's purpose-built
   for repos with existing IaC and works natively with `azd up`.
   ```
3. **Invoke azure-prepare directly:** Call `{"skill": "azure-prepare"}` to load the skill, then follow its workflow using the user's original prompt from `context.json.intent.userPrompt`. This is the same pattern as prereq invocation in Step 3 — AppOnboard loads the skill and the agent follows its instructions. Do NOT ask the user to type a command.
4. **STOP the AppOnboard pipeline.** Do NOT continue to Step 5 (plan architecture). Do NOT generate IaC. Do NOT run `azd up` yourself. azure-prepare owns the rest of the conversation.

**Option 2 — Start fresh:**

1. Write override to `context.json.overrides[]`: `{ "key": "ignoreExistingInfra", "value": "true", "reason": "User chose greenfield over existing azd template" }`
2. If `infra/` directory exists, rename it to `infra.bak/` (single folder rename). This preserves the user's existing IaC as a backup before scaffold writes new files.
3. Continue AppOnboard pipeline from Step 5 (plan architecture).
4. Scaffold Step 3 is skipped (override exists) — the backup was already done here.

**Option 3 — Just scan:**

1. Update `context.json.statusSummary` to reflect the scan-only outcome.
2. Present prereq results summary. STOP.

## Edge cases

| Scenario | Handling |
|----------|----------|
| `azure.yaml` exists but `infra/` is empty | NOT an azd template — continue AppOnboard (repo needs IaC) |
| `azure.yaml` exists with `infra.provider: terraform` | Route same as Bicep — azure-prepare handles both |
| User chose "Start fresh" then hits scaffold guard | Scaffold guard bypassed via `ignoreExistingInfra` override |
| Prereq found blockers AND repo has azure.yaml | Present blockers first (prereq triage), then present azd gate. Blockers take priority. |
| `azure.yaml`/`infra/` looks like it might be an AppOnboard leftover | It's ours only if **any** `.copilot-azure/sessions/*/scaffold-manifest.json` `files[]` lists it (checking every session, not just the active one, catches leftovers from a prior abandoned run); otherwise treat as the user's → route → STOP. ⛔ Never decide by git commit status; never delete/overwrite — move to `.copilot-azure/sessions/<id>/replaced-files/` (mirror path). |
