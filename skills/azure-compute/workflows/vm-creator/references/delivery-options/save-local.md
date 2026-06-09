# Mode B — Save to a local folder

## Step 1 — Suggest a path

Detect the user's current working context (in priority order; pick the **first** that succeeds):

| Signal | Suggested path |
|---|---|
| Host session has an `--add-dir` workspace containing a `.git` directory | `<workspace>/infra/{vm-name}/` |
| User mentioned a repo path earlier in the conversation | `<that-path>/infra/{vm-name}/` |
| `pwd` is inside a git repo | `<repo-root>/infra/{vm-name}/` |
| None of the above | `~/Desktop/{vm-name}-infra/` |

Present the suggestion and let the user override:

> *"I'll save to `~/Desktop/dev-vm-infra/` (no repo detected). Use that, or pick another path?"*

If the path already exists with files, **always show the diff and ask before overwriting**. Never silently clobber.

## Step 2 — Choose the filename(s)

| Format | Files written |
|---|---|
| bash | `create-vm.sh` (chmod +x) |
| Bicep | `main.bicep`, `README.md` |
| Terraform | `main.tf`, `variables.tf`, `outputs.tf`, `terraform.tfvars.example`, `README.md` |

The `README.md` contains:
- The full **Plan Card** markdown (so the next reader knows what this deploys)
- **Deploy** section with exact commands (`az deployment group create ...` / `terraform init && apply ...` / `bash create-vm.sh`)
- **Verify** section: `az vm show` / `az vm list-ip-addresses`
- **Cleanup** section: `az group delete --name <rg> --yes --no-wait`

## Step 3 — Write and confirm

After writing, echo back absolute paths and the single command the user runs next:

> ✅ Wrote 2 files:
> - `~/source/my-infra/infra/dev-vm/main.bicep`
> - `~/source/my-infra/infra/dev-vm/README.md`
>
> Next step:
> ```bash
> cd ~/source/my-infra/infra/dev-vm
> az deployment group create --resource-group dev-vm-rg --template-file main.bicep \
>   --parameters vmName=dev-vm adminUsername=azureuser \
>                adminPublicKey="$(cat ~/.ssh/id_rsa.pub)"
> ```

## Tool implementation

Use the `Write` tool (or the host's equivalent) for each file. For shell scripts: write, then `chmod +x` via Bash.
