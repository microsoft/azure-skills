# Remediation Protocol — Step 6

## Pre-check

> **🛑 Hard Halt?** Skip remediation. Set `overallHealth: "blocked"`, write artifacts, go to Step 7.
> **🔶 Major Migration?** If user chose "Attempt migration," enter loop. Warn changes may need review.

## Remediation Scope

⛔ **Fix ONLY Azure-deployment blockers:** missing dependencies causing build/startup failure, missing entry point, startup crashes, Azure-required configuration (port binding, env var externalization, managed-DB client TLS/SSL — e.g. `W-MYSQL-SSL`). Everything else → `postDeployRecommendations[]`.

## Remediation Loop

If any ❌ FAIL, 🔧 Fix, or ⚠️ WARN with `fixPhase: "prereq"` exist:
1. Present ALL together in one batch. Lead with: "Found {N} blockers, {M} fixes, {P} prereq-phase warnings. Fix all?"
   > ⛔ `fixPhase: "prereq"` is a remediation trigger regardless of severity. If left unfixed → deploy-time failures. Warnings with `fixPhase: "scaffold"/"deploy-gate"/"post-deploy"` are NOT included.
2. After fixes, ⛔ **re-run full Step 3 evaluation (all 3 axes)** on affected components. Re-read each reference file and re-evaluate inline.
3. ⛔ **Verify fixes via static analysis only.** File exists → exports match imports (grep) → no syntax errors → config values present. Do NOT run install/build/test commands.
4. ⛔ **Re-read SKILL.md before applying fixes** if it hasn't been read this turn.
5. ⛔ **Print after re-evaluation:** `🔄 Re-evaluation complete — ✅ N issues resolved, ❌ M remaining.` If M > 0, loop back.
6. **Build-validation gate (agent-modified code only).** After re-evaluation passes AND agent modified >2 source files, ask via `ask_user`: "I've fixed {N} files. Want me to install, build, and test? (Yes / Skip)". ⛔ **General prior consent** (e.g., "fix my issues", "yes", "go ahead", "fix them") **does NOT constitute consent to run install/build/test.** The user must answer THIS specific question. If they say Skip, proceed to Step 7 without running commands. Max 3 build-fix attempts.
7. ⛔ **Max 3 cycles total** (re-evaluations + build-fix retries). Then STOP and ask: "Keep trying" (grants 3 more) / "Guide fixes" / "Stop — accept remaining issues".

## Post-Remediation Artifact Updates

⛔ Re-evaluation = full 3-axis re-scan, NOT just reading fixed files. After ANY successful remediation, update all 3 artifacts per [prereq-artifacts.md](prereq-artifacts.md):
1. `context.json`: `readiness.status: "fixesApplied"`, updated verdicts, `fixes[]`, updated `statusSummary`
2. `prereq-output.json`: Rewrite completely via `create` tool. Recompute `overallHealth` from updated verdicts.
3. `readiness-report.md`: Append "Post-Fix Re-evaluation" section.

⛔ Re-derive verdicts from findings — do NOT carry forward pre-fix values. Per axis: worst finding verdict wins. Then: any axis FAIL → `"blocked"`, else any WARN → `"readyWithCaveats"`, else `"ready"`.

## Write Final State (Step 7)

⛔ Write components to BOTH `prereq-output.json.components[]` AND `context.json.components[]`. `context.json.components[]` is authoritative for downstream.

⛔ **`fixesApplied` requires re-evaluation evidence** — verify `🔄 Re-evaluation complete` was printed.

Set `readiness.status` per component: All PASS → `ready` | Fixes applied + re-eval passed → `fixesApplied` | Unresolved FAILs → `needsFixes`.

Update `context.json`: append `"prereq"` to `completedPhases`, set `currentPhase: null`, update `lastModifiedUtc`.

> ⛔ `overallHealth` MUST be one of: `"ready"`, `"readyWithCaveats"`, `"blocked"`.
> ⛔ `repo.lastScanCommit` is required — run `git rev-parse HEAD`.
