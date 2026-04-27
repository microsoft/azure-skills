# Azure Functions Templates

Dynamic template selection for Azure Functions projects.

## Prerequisites: Check MCP Availability

Before proceeding, verify Azure MCP Server and Functions tools are available:

```
functions_template_get(language: "python")
```

| Result | Action |
|--------|--------|
| ✅ Returns template list | Use **Primary Path: MCP Tools** below |
| ❌ Tool not found / Error | Jump to **[Fallback (MCP Unavailable)](#fallback-mcp-unavailable)** |

---

## Primary Path: MCP Tools

**Use Azure MCP tools** — they provide complete, up-to-date AZD templates with IaC, RBAC, and managed identity.

### Step 1: Discover Templates

```
functions_template_get(language: "<python|csharp|typescript|javascript|java|powershell>")
```

Returns template list with metadata:

- `templateName` — pass to generate call
- `description` — use for selection (describes trigger, bindings, security features)
- `resource` — filter by trigger type (http, cosmos, timer, eventhub, blob, sql, mcp, ai)
- `infrastructure` — prefer `bicep` (default), use `terraform` if user requests

### Step 2: Select Template

Use the intent→resource mapping in [selection.md](selection.md) to map user intent to a `resource` filter value.

> **Default behavior:** When user intent cannot be determined or no trigger type is known, use `http` as the default.

**Single-template optimization:** If description mentions BOTH trigger AND binding user needs, fetch that one template only.

**IaC selection:**

- Default: `infrastructure: "bicep"`
- If user says "terraform": `infrastructure: "terraform"`

### Step 3: Generate Project

```
functions_template_get(
  language: "<language>",
  template: "<selected-template-name>"
)
```

### Step 4: Write All Files

> Write files directly from the MCP tool output — CLI scaffolding tools produce incomplete projects missing IaC, RBAC, and managed identity configuration. NEVER hand-write Bicep/Terraform and use `azd init -t <template>`/`func init`/`func new` as fallback when composing multiple recipes and required templates are not found in MCP.

Each array entry contains `{ path, content }`. For every entry in BOTH arrays:

1. **Create directories** — extract the parent directory from each `path` (e.g., `infra/` from `infra/main.bicep`, `.azure/` from `.azure/config.json`). Create all unique parent directories first.
2. **Write the file** — use the `path` as the file path and `content` as the file body. Write every file exactly as specified.

| Array | Contains | Action |
|-------|----------|--------|
| `functionFiles[]` | Function source code, infra, and config files | Write all — these are the trigger/binding code and IaC |
| `projectFiles[]` | host.json, dependencies, settings files | Write all — these are runtime configuration |

**PRESERVE generated IaC security patterns** — keep RBAC, managed identity, and security config intact. When composing multiple templates, merge additively (see [composition.md](recipes/composition.md)).

> **Skip content verification** — MCP template files are pre-validated. After writing, do not `view`/`cat` files unless you customized them. Check success via exit code and file count only.

### Step 5: Deploy

```bash
azd env set AZURE_LOCATION <region>
azd up --no-prompt
```

---

## Recipe Composition (Multiple Templates)

When user needs trigger + bindings not in a single template:

1. **Discover** all templates for language
2. **Select trigger template** as base (has complete project structure)
3. **Select binding templates** for additional integrations
4. **Fetch all** templates (parallel calls)
5. **Compose**:
   - Use trigger template as base
   - Extract binding patterns from binding templates
   - Merge IaC resources and RBAC roles
   - Add user's custom logic
6. **Trim** unused demo code from samples

> **AzureWebJobsStorage exception**: Always keep storage account + RBAC — runtime requires it.

---

## Fallback (MCP Unavailable)

If MCP tools are unavailable, download the CDN manifest which points to the same GitHub repos:

### Step 1: Fetch Manifest

```
GET https://cdn.functions.azure.com/public/templates-manifest/manifest.json
```

> ⚠️ **If manifest fetch fails** (any error):
> 1. Fall back to the source manifest at `https://github.com/Azure/azure-functions-templates/blob/dev/Functions.Templates/Template-Manifest/manifest.json`
> 2. If both sources are unreachable, fall back to known-good repos: `Azure-Samples/functions-quickstart-*` keyed by language + resource (e.g., `functions-quickstart-python-http-azd`)
> 3. If all fallbacks fail, report the error to the user and ask them to retry later

### Step 2: Filter Templates

Each template entry contains:

| Field | Description | Example |
|-------|-------------|---------|
| `language` | Programming language | `Python`, `TypeScript`, `JavaScript`, `Java`, `CSharp`, `PowerShell` |
| `resource` | Trigger type (see [selection.md](selection.md)) | `http`, `cosmos`, `timer`, `eventhub`, `servicebus`, `blob`, `sql`, `mcp`, `durable` |
| `iac` | Infrastructure type | `bicep`, `terraform` |
| `repositoryUrl` | GitHub repo with complete project | `https://github.com/Azure-Samples/functions-quickstart-python-http-azd` |
| `folderPath` | Path within repo | `.` or `src/api` |

Filter: `language == <user-lang> AND resource == <mapped-resource> AND iac == <user-iac>`

### Step 3: Download Template

**If `folderPath` is `.` (root):** ZIP download + unzip

```
GET https://github.com/{owner}/{repo}/archive/refs/heads/main.zip
unzip main.zip -d <project-dir>
```

**If `folderPath` is a subfolder:** Fetch tree + raw file downloads

```
1. GET https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1
2. Filter tree entries where path starts with {folderPath}/
3. For each file:
   GET https://raw.githubusercontent.com/{owner}/{repo}/main/{path}
```

**If downloads fail:** Fall back to git clone

```bash
git clone <repositoryUrl> --depth 1
# If folderPath != ".", copy only that folder
```

The downloaded content is the **same** as MCP `functionFiles[]` + `projectFiles[]`:

- Source code (function triggers, bindings)
- IaC (Bicep/Terraform with RBAC, managed identity)
- azure.yaml (azd configuration)
- host.json, dependencies

### Step 4: Deploy

```bash
azd up --no-prompt
```

---

## References

- [Composition Details](recipes/composition.md) — recipe algorithm
- [Selection Guide](selection.md) — intent→resource mapping
- [Recipes Index](recipes/README.md) — all available recipes
- [Base Template Eval](base/eval/summary.md) — HTTP base evaluation results

**Browse all:** [Awesome AZD Functions](https://azure.github.io/awesome-azd/?tags=functions)
