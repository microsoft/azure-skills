# Delivery Options

After the Plan Card is approved (Step 5) and the output format is chosen (Step 6), the workflow has a generated artifact. **Before printing it into the chat**, ask one more question — where should it go?

| Mode | When the user wants this | File |
|---|---|---|
| **A. Print in chat** | Quick one-off, copy-paste, just learning | [print.md](print.md) |
| **B. Save to local folder** | Wants files on disk, will commit/run later | [save-local.md](save-local.md) |
| **C. Sync to a GitHub repo** | Has an infra repo, wants the change as a PR | [github-pr.md](github-pr.md) |

> **Skip the question for Adapter 4 (Apply via MCP).** Delivery is moot — the resources get created in Azure directly.

## Asking

> *"Where should I drop this {format} artifact?"*
> *1. Print in the chat (default for quick / one-off)*
> *2. Save to a local folder — I'll suggest a path based on your current workspace*
> *3. Sync to a GitHub repo as a new branch + PR*

If the user already implied a target ("save it to my infra repo" / "open a PR" / "just print it"), skip the question and use that mode.

## Re-emitting / changing delivery mid-flow

After delivery, the Plan Card is cached. The user can say:

| User says | Action |
|---|---|
| "also save it locally" | Re-run Mode B with the same artifact |
| "open a PR instead" | Re-run Mode C |
| "give me terraform now too" | Re-render that adapter, then re-ask delivery |
| "delete that file you wrote" | `rm` the path that was written |

Never re-ask Plan Card questions when only the delivery target is changing.

## Safety checks (B and C)

| Check | Why |
|---|---|
| Don't overwrite without showing the diff and getting explicit yes | User may have manual edits |
| Scrub `adminPassword` from generated files → replace with `${VM_ADMIN_PASSWORD}` env var | Repos leak passwords |
| Never push directly to `main` / `master` / default branch — feature branch + PR only | Auditability and review |
| Never `git push --force` (use `--force-with-lease` if a rewrite is truly needed) | Catastrophic on shared branches |
| Emit a parameter placeholder for SSH keys, not the literal key contents | Keys committed to git stay there forever |
| If the repo has `CODEOWNERS` for the path, mention who'll be auto-tagged | User shouldn't be surprised by review routing |
