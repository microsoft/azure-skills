# Intent Gathering

## Scope Triage (Step 2 — before prereq)

> ⛔ **Scope triage — BEFORE prereq.** Check for azd template markers (`azure.yaml` + IaC in `infra/`).
>
> **Skip triage when:**
> - User explicitly asks for cost estimates, service recommendations, or code analysis
> - Empty workspace (prereq’s zero-code-path handles it)
> - Code exists but no infra files (no `.bicep`, `.tf`, `azure.yaml`, or `infra/` dir) — full pipeline is the only sensible path
> - Intentionally vulnerable app signals (🛑 detection) — proceed to prereq directly
>
> ### If azd template detected
>
> ⛔ **You MUST read [`azd-template-routing.md`](azd-template-routing.md)** for detection criteria, gate presentation, and routing protocol.
>
> ### If NO azd template BUT infra files present
>
> Ask ONE `ask_user` question:
> 1. **Yes — analyze and deploy end-to-end** (Recommended)
> 2. **Just scaffold Bicep/Terraform**
> 3. **Just deploy it** (I have IaC ready)
> 4. **Other**
>
> Option 1 / vague → full pipeline (Step 3). Any other → invoke `{"skill": "azure-prepare"}`.

## After Prereq Returns (Step 4 — scan-informed intent gathering)

Prereq has written `prereq-output.json` and `context.json.components[]` — this is the authoritative source for all downstream phases (prepare and scaffold consume `context.json`, not `prereq-output.json`). 

Confirm the Azure target ("☁️ **Azure target**: {subscriptionName} ({subscriptionId})"). If the user wants a different subscription, write to `context.json.overrides[]`.

**Present scan results first, then ask only what prereq didn't answer** (≤2 if mostly covered, ≤4 if gaps):

| # | Topic | Ask if... |
|---|-------|----------|
| 1 | App purpose | Not obvious from `detectedStack` + `components[]` |
| 3 | Data/storage | Prereq didn't detect DB/compose |
| 4 | Auth approach | No MSAL/passport/auth library detected |
| 5 | Scale | Always — prereq doesn't know traffic expectations |

⛔ Do NOT ask about stack/language (always answered by prereq) or budget (only if user mentioned cost). User corrections → `context.json.overrides[]`. Stop when covered or user says "just go."

**Update intent:** Merge scan results into `context.json.intent`. Set `refinedFromScan: true` and populate `scanDiscoveredFacts[]`.
