# Subscription Resolution — Defensive Fallback

The `azure-app-onboard` orchestrator resolves the subscription at Step 1 (login hard gate) and writes `subscriptionId`, `subscriptionName`, `tenantId` to `context.json.azure` before any sub-skill runs. In normal operation, `context.json.azure.subscriptionId` is always set by the time prepare runs.

At prepare phase entry, verify `context.json.azure.subscriptionId` is set. If it is (expected path), use it — done.

If `context.json.azure` is somehow empty, resolve now rather than halting the flow:

1. **Check env vars** — if `AZURE_SUBSCRIPTION_ID` is set, use it directly (with `AZURE_TENANT_ID` if set). Write `subscriptionId`, `subscriptionName`, `tenantId` to `context.json.azure`, done.
2. **Run `az account show`** — `az account show --query "{id:id, name:name, tenantId:tenantId}" -o json`. If it succeeds, **auto-select** — write `subscriptionId`, `subscriptionName`, `tenantId` to `context.json.azure`. Do NOT run `az account list` or present a picker.
3. **Fallback: `mcp_azure_mcp_subscription_list` + picker** — only if `az account show` fails. Call `mcp_azure_mcp_subscription_list` to retrieve all subscriptions (returns `subscriptionId`, `displayName`, `isDefault`).
   - **1 subscription** → auto-select, no question. Write `subscriptionId`, `subscriptionName`, `tenantId` to `context.json.azure`.
   - **2+ subscriptions** → present a picker via `ask_user`: list each subscription as a choice `"{displayName} ({subscriptionId})"` with the default marked. The user selects one. Write `subscriptionId`, `subscriptionName`, `tenantId` to `context.json.azure`.
4. **MCP tool fails** → run `az login` (interactive browser login). If that fails (no browser, remote session), fall back to `az login --use-device-code`. After login succeeds, retry from step 2. Do NOT proceed without a resolved subscription.
