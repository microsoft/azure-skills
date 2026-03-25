# Global Rules

> **MANDATORY** — These rules apply to ALL skills. Violations are unacceptable.

## Rule 1: Destructive Actions Require User Confirmation

⛔ **ALWAYS use `ask_user`** before ANY destructive action.

### What is Destructive?

| Category | Examples |
|----------|----------|
| **Delete** | `az group delete`, `azd down`, `rm -rf`, delete resource |
| **Overwrite** | Replace existing files, overwrite config, reset settings |
| **Irreversible** | Purge Key Vault, delete storage account, drop database |
| **Cost Impact** | Provision expensive resources, scale up significantly |
| **Security** | Expose secrets, change access policies, modify RBAC |

### How to Confirm

```
ask_user(
  question: "This will permanently delete resource group 'rg-myapp'. Continue?",
  choices: ["Yes, delete it", "No, cancel"]
)
```

### No Exceptions

- Do NOT assume user wants to delete/overwrite
- Do NOT proceed based on "the user asked to deploy" (deploy ≠ delete old)
- Do NOT batch destructive actions without individual confirmation
- ⛔ Do NOT delete user project or workspace directories (e.g., `rm -rf <project-dir>`) even when adding features, converting, or migrating — use MODIFY mode to edit existing files instead. File deletions within a project (e.g., removing build artifacts or temp files) are permitted when appropriate.
- ⛔ `azd init -t <template>` (and any `azd init` command with a template argument) is for NEW projects only — run it **only** in an empty/new directory. If the user explicitly requests re-initialization of an existing project, create a separate new directory, run the template there, and then migrate changes into the existing project with user-confirmed edits. Never run `azd init -t` directly in a non-empty existing workspace. `azd init` without a template argument may be used in existing workspaces when appropriate.

---

## Rule 2: Never Assume Subscription or Location

⛔ **ALWAYS use `ask_user`** to confirm:
- Azure subscription (show actual name and ID)
- Azure region/location
