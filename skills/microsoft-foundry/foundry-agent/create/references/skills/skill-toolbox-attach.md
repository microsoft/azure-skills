# Skills in Toolbox

How to attach, list, remove, and version **skills** (reusable behavioral guidelines) in a Foundry toolbox using `azd ai toolbox skill`.

Skills are not a tool `type` — they live in a separate `skills[]` array in the toolbox manifest. At the MCP level, skills are exposed as **resources** (`resources/list` / `resources/read` with `skill://` URIs).

## Install

```bash
azd extension install azure.ai.skills       # skill CRUD
azd extension install azure.ai.toolboxes    # toolbox management
```

## CLI surface — `azd ai toolbox skill`

| Command | What it does |
|---------|--------------|
| `azd ai toolbox skill add <toolbox> <skill>` | Attach skill (follows default version); new immutable toolbox version. |
| `azd ai toolbox skill add <toolbox> <skill>@<ver>` | Attach skill pinned to a specific version. |
| `azd ai toolbox skill add <toolbox> --from-file <path>` | Attach multiple skills from JSON/YAML. |
| `azd ai toolbox skill list <toolbox>` | List skill references in the toolbox. |
| `azd ai toolbox skill remove <toolbox> <skill> [<skill>...] [--force]` | Detach skills; one new version. |

> Every `skill add` / `skill remove` creates a new immutable toolbox version but does **not** change the default. Run `azd ai toolbox publish <toolbox> <version>` to promote.

## Recipe: attach skill to existing toolbox

```bash
# 1. Create the skill (if not already uploaded)
azd ai skill create support-style --file ./skills/support-style/

# 2. Attach to toolbox
azd ai toolbox skill add agent-tools support-style

# 3. Promote the new toolbox version
azd ai toolbox publish agent-tools <new-version>

# 4. Verify
azd ai toolbox skill list agent-tools
```

## Recipe: include skills in toolbox creation

Skills are a top-level `skills[]` array in the `--from-file` manifest:

```yaml
description: Agent toolbox with skills
connections:
  - name: my-mcp-server
skills:
  - name: support-style
  - name: escalation-policy
    version: "2"         # pin to version 2; omit to follow default
tools:
  - type: web_search
    name: web
```

```bash
azd ai toolbox create agent-tools --from-file tools.yaml
```

Get the toolbox endpoint after creation:

```bash
ENDPOINT=$(azd ai toolbox show agent-tools -o json | jq -r .endpoint)
azd env set TOOLBOX_ENDPOINT "$ENDPOINT"
```

When `version` is omitted from a skill entry, the toolbox resolves the skill's `default_version` at read time. If the skill is updated (`azd ai skill update`), agents on the consumer endpoint pick up the new content without a toolbox republish.

## Recipe: remove skill from toolbox

```bash
# Remove one or more skills (one new version)
azd ai toolbox skill remove agent-tools my-skill --force

# Promote
azd ai toolbox publish agent-tools <new-version>
```

Removing the last skill is allowed (the toolbox can still have connections and tools).

## Versioning behavior

- Each `skill add` / `skill remove` creates a new immutable toolbox version (default unchanged until `publish`).
- Skill references without a pinned version follow the skill's `default_version` at read time.
- Skill references with a pinned version (`skill@2`) stay on that version regardless of skill updates.
- To rollback: `azd ai toolbox publish <toolbox> <previous-version>`.

## How skills appear at runtime (raw MCP protocol)

Skills are exposed through the MCP **resources** protocol (not `tools/list`):

- `resources/list` advertises each skill as a resource with a `skill://<name>/SKILL.md` URI (name + description).
- `resources/list` also exposes `skill://index.json` — a discovery index listing every skill on the toolbox version with URLs to read each skill's `SKILL.md` and (for multi-file skills) its ZIP archive.
- `resources/read` with a `skill://` URI retrieves the full `SKILL.md` body on demand.

### Raw MCP call examples

```bash
# Get a bearer token
TOK=$(az account get-access-token --resource "https://ai.azure.com" --query accessToken -o tsv)

# Foundry project endpoint (no trailing slash)
PE="<FOUNDRY_PROJECT_ENDPOINT>"
URL="$PE/toolboxes/<toolbox>/mcp?api-version=v1"
# List available skills (resources/list)
curl -s -X POST "$URL" \
  -H "Authorization: Bearer $TOK" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"resources/list","params":{}}'

# Read skill index
curl -s -X POST "$URL" \
  -H "Authorization: Bearer $TOK" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"resources/read","params":{"uri":"skill://index.json"}}'

# Read a specific skill's content
curl -s -X POST "$URL" \
  -H "Authorization: Bearer $TOK" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"resources/read","params":{"uri":"skill://my-skill/SKILL.md"}}'
```

## Skill + Tool Search interaction

When `toolbox_search_preview` is enabled, regular tools are hidden from `tools/list` and discovered via `tool_search`. Skills remain in `resources/list` regardless of this setting — they are not affected by Tool Search.

## References

- [skill-manage.md](skill-manage.md) — create, version, and manage skills
- [skill-attach.md](skill-attach.md) — consume skills in agent code (direct download or toolbox MCP), choosing an approach
