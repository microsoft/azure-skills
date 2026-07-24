# Readiness Gate — Step 4

## Write Artifacts

⛔ **You MUST read [`prereq-artifacts.md`](prereq-artifacts.md)** for complete artifact write procedures and phase exit checklist.

---

## Severity Tiers

| Verdict | Icon | Meaning |
|---------|------|---------|
| Hard Halt | 🛑 | App is intentionally vulnerable — pipeline stops, no fix possible |
| Major Migration | 🔶 | Large-scope change (EOL runtime, cloud SDK migration, >5 files) — redirect or warn |
| Critical | ❌ FAIL | Deployment will fail — agent can fix (≤5 files, config-level) |
| Recommended Fix | 🔧 | App deploys but has quality/security issues — agent offers fix |
| Warning | ⚠️ WARN | Informational, non-blocking — can proceed with caveats |
| Pass | ✅ PASS | No issues |

---

## Overall Health Gate

**Compute `overallHealth`:** ALL ✅ PASS → `"ready"` | Any ⚠️ WARN no ❌ FAIL → `"readyWithCaveats"` | ANY ❌ FAIL → `"blocked"`

**Component `readiness.status` alignment:**
- `"ready"` → `readiness.status: "ready"`
- `"readyWithCaveats"` → `readiness.status: "ready"` (WARNs aren't "needs fixes")
- `"blocked"` → `readiness.status: "needsFixes"`
- After remediation → `readiness.status: "fixesApplied"`

⛔ `readiness.status: "needsFixes"` requires at least one ❌ FAIL. If all ⚠️/✅, use `"ready"`.

---

## Critical Readiness Gate

⛔ **Verdict propagation cross-check** before computing `overallHealth`:
1. Any finding with `verdict: "FAIL"` → axis verdict MUST be `"FAIL"`.
2. Any finding with `verdict: "WARN"` + `fixPhase: "prereq"` → escalate to `"FAIL"` (prevents wasting a deploy cycle). ⛔ Escalate only WARNs that would actually break THIS deploy (build/startup failure, or a health probe wired to a route the app lacks). Issues that deploy and run fine — missing trust proxy, README, in-memory sessions — stay `fixPhase: "postdeploy"`/`"scaffold"`; `engines`/health-endpoint escalate only on a real version/probe mismatch (see [completeness-check.md](completeness-check.md) § Stack-Specific Checks).

| Tiers | Reference file |
|-------|---------------|
| 🛑 🔶 🔧 ⚠️ | [`dependency-compatibility.md`](dependency-compatibility.md) |
| ❌ 🔧 | [`completeness-check.md`](completeness-check.md) |
| ❌ | [`build-check.md`](build-check.md) |

**Post-evaluation HALT cross-check:** Intentionally vulnerable apps (≥2 code signals from dependency-compatibility.md) → `overallHealth: "blocked"` MUST be written to `prereq-output.json` on disk (Step 4) BEFORE any halt message. If the artifact is not on disk when you reach the halt, write it NOW via the `create` tool and read it back — do NOT present the halt until it exists.

---

## Batch-Then-Approve Flow

⛔ **Artifacts before message.** Write AND read back all 3 artifacts (`prereq-output.json`, `context.json`, `readiness-report.md`) to confirm they exist on disk BEFORE presenting any findings, cloud-SDK stop prompt, or 🛑 hard-halt message. Those messages can end the turn, so every artifact MUST already be persisted — NEVER batch artifact writes after the message.

1. **Detect ALL issues first** — full 3-axis scan, all components.
2. **Present ALL findings at once** — summary: "🔍 Readiness: 2 critical, 1 recommended fix, 3 warnings". Group: 🛑 → 🔶 → ❌ → 🔧 → ⚠️.
3. **Fix plan** — for ❌, 🔧, 🔶, ⚠️ with `fixPhase: "prereq"`: describe WHAT and WHY. ⛔ Exclude 🔶 with `routeToSkill` set. Never include 🛑.
4. **User choice** (based on highest severity):
   - **🛑:** Pipeline stops. No formal gate.
   - **🔶 + others:** "Fix {N} issues including {M} migration(s) — scope warning" / "Fix blockers only" / "Continue with risks" / "Cancel"
   - **🔶 only:** "Attempt migration" / "Continue as-is" / "Cancel"
   - **❌/🔧/⚠️ with fixPhase prereq:** "Fix {N} deployment issues" / "Continue with risks" / "Cancel"
5. **After approval** → apply fixes per [remediation-protocol.md](remediation-protocol.md).

> ⛔ **Two-gate rule:** Intent approval ≠ fix execution approval. Present the fix prompt here even if user agreed earlier.

---

## Fast-Track

Single-component + no DB + no auth + **no Dockerfile** → `fastTrackEligible: true`.

---

## Present Findings (Step 5)

⛔ Do NOT skip — user must see scan results before pipeline continues.

**Part 1 — Summary:** "🔍 Readiness: {N} critical, {M} fixes, {K} warnings" (or "✅ Ready").
**Part 2 — Per-axis reasoning:** Verdict icon + 1–2 sentence summary per axis.
**Part 3 — Findings table:** Grouped by severity. Include warning ID and actionable detail.

**Data-loss warnings** (SQLite, in-memory sessions, local file storage) require explicit acknowledgment. Other ⚠️ are informational.

End with: "📄 Full evaluation saved to `readiness-report.md`."

### Remediation Decision Gate

⛔ **STOP after presenting findings.** Options:
1. **"Fix deployment issues"** — fix all actionable items (❌, 🔧, ⚠️ with `fixPhase: "prereq"`). Re-evaluate after.
2. **"I have context — let me guide the fixes"**
3. **"Continue without fixing — I accept the risks"**

Wait for explicit choice. Generic "Yes"/"Go ahead" ≠ remediation consent — clarify if ambiguous.

> ⛔ **Remediation budget:** Max 3 cycles. See [remediation-protocol.md](remediation-protocol.md) step 7.

> ⛔ **ARTIFACT CHECKPOINT.** After presenting findings, verify all 3 artifacts exist: `context.json`, `prereq-output.json`, `readiness-report.md`. Write any missing ones NOW.
