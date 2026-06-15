# Transient ARM error handling for `az ... create`

Load this file only when an `az group create`, `az appservice plan create`, or `az webapp create` command fails. Healthy runs never need it.

## Which errors are transient

ARM `PUT` operations sometimes fail with **transient** errors:

- `Connection reset`, `Connection aborted`, `ConnectionError`
- `Read timed out`, `Max retries exceeded`
- `BadGatewayConnection`, `ServiceUnavailable`
- `TooManyRequests` / HTTP `429`
- HTTP `502` / `503` / `504`

These are ARM frontend / network blips, not configuration problems — they almost always succeed on retry.

**Do NOT retry on** `AuthorizationFailed`, `SubscriptionNotFound`, `ResourceGroupNotFound`, `InvalidTemplateDeployment`, `SkuNotAvailable`, `QuotaExceeded`, or any non-429 4xx. Those are real config errors — surface them to the user.

## Rules

- Apply to every `az ... create` in [create-app.md](create-app.md) §§2–4.
- Retry **silently** — do not narrate "let me retry".
- Up to **2 retries** (3 attempts total); wait **5s** before retry #1 and **15s** before retry #2. If the error carries a `Retry-After` header, honour that instead.
- **Wrap the full idempotent pair** `(az ... show ...) || (az ... create ...)` — never the bare `create`. The `show` short-circuits any partially-succeeded prior attempt and avoids false `Conflict` / `NameAlreadyExists`.
- After 3 failed attempts, surface the original error with one line of context (e.g., `"ARM frontend is returning transient errors — please retry in a few minutes"`).

## Use the wrapper scripts

Both shells have a ready-to-call wrapper that implements the loop, the transient-error filter, and the backoff. Prefer these over inlining the loop:

- Bash / zsh (Linux, macOS): [`scripts/retry-az-create.sh`](../scripts/retry-az-create.sh)
  ```bash
  ./scripts/retry-az-create.sh \
      "az group show -n my-rg --only-show-errors" \
      "az group create -n my-rg -l eastus2"
  ```
- PowerShell (Windows): [`scripts/retry-az-create.ps1`](../scripts/retry-az-create.ps1)
  ```powershell
  .\scripts\retry-az-create.ps1 `
      -ShowCommand "az group show -n my-rg --only-show-errors" `
      -CreateCommand "az group create -n my-rg -l eastus2"
  ```

Both scripts run the `show` command first, fall through to `create` on failure, and retry up to 2 times on transient errors only.
