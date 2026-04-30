# Agent Observability Loop

Orchestrate the full eval-driven optimization cycle for a Foundry agent. This skill manages the **multi-step workflow** for a selected agent root and environment: reusing or refreshing `.foundry` cache in that folder only, auto-creating evaluators, generating test datasets, running batch evals, clustering failures, optimizing prompts, redeploying, and comparing versions. Use this skill instead of calling individual `azure` MCP evaluation tools manually.

## When to Use This Skill

USE FOR: evaluate my agent, run an eval, test my agent, check agent quality, run batch evaluation, analyze eval results, why did my eval fail, cluster failures, improve agent quality, optimize agent prompt, compare agent versions, re-evaluate after changes, set up CI/CD evals, agent monitoring, eval-driven optimization, set up continuous monitoring, production quality monitoring, why are eval scores dropping.

> ⚠️ **DO NOT manually call** `evaluation_agent_batch_eval_create`, `evaluator_catalog_create`, `evaluation_comparison_create`, `prompt_optimize`, or `continuous_eval_create` **without reading this skill first.** This skill defines required pre-checks, environment selection, cache reuse, artifact persistence, and multi-step orchestration that the raw tools do not enforce.

## Quick Reference

| Property | Value |
|----------|-------|
| MCP server | `azure` |
| Key MCP tools | `evaluator_catalog_get`, `evaluation_agent_batch_eval_create`, `evaluator_catalog_create`, `evaluation_comparison_create`, `evaluation_get`, `prompt_optimize`, `agent_update`, `continuous_eval_create`, `continuous_eval_get`, `continuous_eval_delete` |
| Prerequisite | Agent deployed and running (use [deploy skill](../deploy/deploy.md)) |
| Local cache | selected `.foundry/agent-metadata*.yaml` file, `.foundry/evaluators/`, `.foundry/datasets/`, `.foundry/results/` |

## Entry Points

| User Intent | Start At |
|-------------|----------|
| "Deploy and evaluate my agent" | [Step 1: Auto-Setup Evaluators](references/deploy-and-setup.md) (deploy first via [deploy skill](../deploy/deploy.md)) |
| "Agent just deployed" / "Set up evaluation" | [Step 1: Auto-Setup Evaluators](references/deploy-and-setup.md) (skip deploy, run auto-create) |
| "Evaluate my agent" / "Run an eval" | [Step 1: Auto-Setup Evaluators](references/deploy-and-setup.md) first if `.foundry/evaluators/` or `.foundry/datasets/` cache is missing, stale, or the user requests refresh, then [Step 2: Evaluate](references/evaluate-step.md) |
| "Why did my eval fail?" / "Analyze results" | [Step 3: Analyze](references/analyze-results.md) |
| "Improve my agent" / "Optimize prompt" | [Step 4: Optimize](references/optimize-deploy.md) |
| "Compare agent versions" | [Step 5: Compare](references/compare-iterate.md) |
| "Set up CI/CD evals" | [Step 6: CI/CD & Monitoring](references/cicd-monitoring.md) |
| "Enable continuous monitoring" / "Set up production monitoring" / "Evaluation results dropping" | [Continuous Eval](references/continuous-eval.md) |

> ⚠️ **Important:** Before running any evaluation (Step 2), always resolve the selected agent root, metadata file, and environment, then inspect that metadata file plus `.foundry/evaluators/` and `.foundry/datasets/` in that root only. If the cache is missing, stale, or the user wants to refresh it, route through [Step 1: Auto-Setup](references/deploy-and-setup.md) first — even if the user only asked to "evaluate." Do **not** merge `.foundry` cache or source context from sibling agent folders or sibling metadata files.

## Before Starting — Detect Current State

1. Resolve the target agent root, selected metadata file, and environment from `.foundry/agent-metadata*.yaml`.
2. Use `agent_get` and `agent_container_status_get` to verify the environment's agent exists and is running.
3. Inspect the selected environment's `evaluationSuites[]` plus cached files under `.foundry/evaluators/` and `.foundry/datasets/` in the selected agent root only. If the metadata still uses older `testSuites[]` or legacy `testCases[]`, normalize that list to evaluation suites first using the shared migration rule.
4. Use `evaluation_get` to check for existing eval runs.
5. Jump to the appropriate entry point.

## Loop Overview

```text
1. Auto-setup evaluators or refresh .foundry cache for the selected environment
   -> ask: "Run an evaluation to identify optimization opportunities?"
2. Evaluate (batch eval run)
3. Download and cluster failures
4. Pick a category or evaluation suite to optimize
5. Optimize prompt
6. Deploy new version (after user sign-off)
7. Re-evaluate (same env + same evaluation suite)
8. Compare versions -> decide which to keep
9. Loop to next category or finish
10. Prompt: enable CI/CD pipeline evals and/or continuous production monitoring
```

## Behavioral Rules

1. **Keep context visible.** Restate the selected agent root, metadata file, and environment in setup, evaluation, and result summaries.
2. **Stay inside the selected agent root.** Once the agent root is resolved, inspect only that folder's `.foundry/` cache and source tree when suggesting tools, datasets, evaluators, or prompt optimizations. Do not merge sibling agent folders.
3. **Reuse cache before regenerating.** Prefer existing `.foundry/evaluators/` and `.foundry/datasets/` when they match the active environment. Ask before refreshing or overwriting them.
4. **Start with smoke suites.** Run evaluation suites tagged `tier=smoke` before broader `tier=regression` or `tier=coverage` suites unless the user explicitly chooses otherwise.
5. **Auto-poll in background.** After creating eval runs or starting containers, poll in a background terminal. Only surface the final result.
6. **Confirm before changes.** Show diff/summary before modifying agent code, refreshing cache, or deploying. Wait for sign-off.
7. **Prompt for next steps.** After each step, present options. Never assume the path forward.
8. **Write scripts to files.** Python scripts go in `scripts/` - no inline code blocks.
9. **Persist eval artifacts.** Save local artifacts to `.foundry/evaluators/`, `.foundry/datasets/`, and `.foundry/results/` for version tracking and comparison.
10. **Migrate legacy metadata on write.** If the selected environment still uses older `testSuites[]` or legacy `testCases[]`, treat that list as the suite source for the current run, then rewrite that environment to `evaluationSuites[]` on the next metadata update. Preserve dataset/evaluator fields and map `priority` to `tags.tier` only when `tags.tier` is missing.
11. **Use exact eval parameter names.** Use `evaluationId` only on batch-eval create calls that group runs; use `evalId` on `evaluation_get` and `evaluation_comparison_create`; use `evalRunId` for a specific run lookup.
12. **Check existing evaluators before creating new ones.** Always call `evaluator_catalog_get` before proposing or creating evaluators. Present the existing catalog to the user and map existing evaluators to the agent's evaluation needs. Only create a new evaluator when no existing one covers the required dimension. This applies to every workflow that involves evaluator selection - initial setup, re-evaluation, and optimization loops.
13. **Use correct parameters when deleting evaluators.** `evaluator_catalog_delete` requires both `name` (not `evaluatorName`) and `version`. When cleaning up redundant evaluators, always pass the explicit version string. If an evaluator has multiple versions (for example, `v1`, `v2`, `v3`), delete each version individually - there is no "delete all versions" shortcut. Discover version numbers with `evaluator_catalog_get` before attempting deletions.
14. **Use a two-phase evaluator strategy.** Phase 1 is built-in only: `relevance`, `task_adherence`, `intent_resolution`, `indirect_attack`, and `builtin.tool_call_accuracy` when the agent uses tools. Generate seed datasets with `query` and `expected_behavior` so Phase 2 can reuse or create targeted custom evaluators only after the first run exposes gaps.
15. **Account for LLM judge knowledge cutoff.** When the agent uses real-time data sources (web search, Bing Grounding, live APIs), the LLM judge's training cutoff means it cannot verify current facts. Custom evaluators that score factual accuracy or behavioral adherence will produce systematic false negatives - flagging the agent's real-time data as "fabricated" or "beyond knowledge cutoff." Mitigations: (a) instruct the evaluator prompt to accept sourced claims it cannot verify, (b) use `expected_behavior` rubrics that describe the shape of a good answer rather than specific facts, (c) flag suspected knowledge-cutoff false negatives in the failure analysis rather than treating them as real failures.
16. **Show Data Viewer deeplinks (for VS Code runtime only).** Append a Data Viewer deeplink immediately after reference to a dataset file or evaluation result file in your response. Format: "[Open in Data Viewer](vscode://ms-windows-ai-studio.windows-ai-studio/open_data_viewer?file=<file_path>&source=microsoft-foundry-skill) for details and perform analysis". This applies to files in `.foundry/datasets/`, `.foundry/results/`.

## Two-Phase Evaluator Strategy

| Phase | When | Evaluators | Dataset fields | Goal |
|-------|------|------------|----------------|------|
| Phase 1 - Initial setup | Before the first eval run | <=5 built-in evaluators only: `relevance`, `task_adherence`, `intent_resolution`, `indirect_attack`, plus `builtin.tool_call_accuracy` when the agent uses tools | `query`, `expected_behavior` (plus optional `context`, `ground_truth`) | Establish a fast baseline and identify which failure patterns built-ins can and cannot explain |
| Phase 2 - After analysis | After reviewing the first run's failures and clusters | Reuse existing custom evaluators first; create a new custom evaluator only when the built-in set cannot capture the gap | Reuse `expected_behavior` as a per-query rubric | Turn broad failure signals into targeted, domain-aware scoring |

Phase 1 keeps the first setup fast and comparable across agents. Even though the initial built-in evaluators do not consume `expected_behavior`, include it in every seed dataset row so the same dataset is ready for Phase 2 custom evaluators without regeneration.

When built-in evaluators reveal patterns they cannot fully capture - for example, false negatives from `task_adherence` missing tool-call context or domain-specific quality gaps - first call `evaluator_catalog_get` again to see whether an existing custom evaluator already covers the dimension. Only create a new evaluator when the catalog still lacks the required signal.

Example custom evaluator for Phase 2:

```yaml
name: behavioral_adherence
promptText: |
  Given the query, response, and expected behavior, rate how well
  the response fulfills the expected behavior (1-5).
  ## Query
  {{query}}
  ## Response
  {{response}}
  ## Expected Behavior
  {{expected_behavior}}
```

> 💡 **Tip:** This evaluator scores against the per-query behavioral rubric in `expected_behavior`, not just the agent's global instructions. That usually produces a cleaner signal when broad built-in judges are directionally correct but too coarse for optimization.

## Related Skills

| User Intent | Skill |
|-------------|-------|
| "Analyze production traces" / "Search conversations" / "Find errors in App Insights" | [trace skill](../trace/trace.md) |
| "Debug hosted agent issues" / "Hosted-agent logs" | [troubleshoot skill](../troubleshoot/troubleshoot.md) |
| "Deploy or redeploy agent" | [deploy skill](../deploy/deploy.md) |
| "Enable continuous evaluation" / "Set up ongoing monitoring" | [Continuous Eval](references/continuous-eval.md) (reference within this skill) |
