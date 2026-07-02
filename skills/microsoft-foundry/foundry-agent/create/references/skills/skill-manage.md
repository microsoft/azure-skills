# Skills (azd ai)

How to create, manage, and version **skills** (reusable behavioral guidelines) in a Foundry project using `azd ai skill` CLI and SDK.

A **skill** is a Markdown file with YAML front matter (`SKILL.md`), uploaded to a Foundry project, and attached to agents at runtime. Skills enable updating agent behavior **without code changes**.

## Install the extension

```bash
azd extension install azure.ai.skills
```

## Skill authoring format

Each skill lives in its own directory with `SKILL.md` at the root:

```
skills/
  my-skill/
    SKILL.md       # YAML front matter + Markdown body
```

```yaml
---
name: my-skill-name
description: What this skill does and when the agent should load it
---

# My Skill

Instructions the agent follows when this skill is loaded on demand...
```

> **The `name` and `description` values must be unquoted** in YAML front matter — quoting causes HTTP 500 on import.

The `description` field drives skill discovery at runtime: the Agent Framework SDK uses it to decide when to load the skill. Write descriptions that clearly state **when** the agent should use the skill. See [skill-attach.md § How progressive disclosure works](skill-attach.md) for details.

## CLI surface — `azd ai skill`

| Command | What it does |
|---------|--------------|
| `azd ai skill create <name> --file <path>` | Create skill + publish v1. Accepts SKILL.md, .zip, or directory. |
| `azd ai skill create <name> --description "..." --instructions "..."` | Inline create (no file). |
| `azd ai skill create <name> --file <path> --force` | Delete existing + recreate. Safe to re-run after edits. |
| `azd ai skill update <name> --file <path>` | New immutable version, promoted to default. |
| `azd ai skill update <name> --set-default-version <ver>` | Repoint default (rollback) without uploading new content. |
| `azd ai skill show <name>` | Show metadata (default_version, latest_version). |
| `azd ai skill list` | List skills in the project. |
| `azd ai skill download <name>` | Extract to `./.agents/skills/<name>/`. |
| `azd ai skill download <name> --version <ver>` | Download a specific version. |
| `azd ai skill download <name> --raw` | Write raw ZIP without extracting. |
| `azd ai skill delete <name> [--force]` | Delete skill. |

Every mutation creates a new immutable version. `create` promotes v1 to default; `update` promotes the new version to default.

Four mutually exclusive input modes for `create` and `update`:

1. **Directory:** `--file ./skills/my-skill/` (CLI packages as ZIP; requires `SKILL.md` at root)
2. **SKILL.md:** `--file ./SKILL.md` (CLI parses YAML front matter + body)
3. **ZIP:** `--file ./skill.zip` (uploaded as multipart/form-data)
4. **Inline:** `--description "..." --instructions "..."` (no file)

## Recipe: create a skill

```bash
azd ai skill create support-style --file ./skills/support-style/
```

## Recipe: batch provision (safe to re-run)

```bash
for dir in skills/*/; do
  name=$(basename "$dir")
  azd ai skill create "$name" --file "$dir" --force
done
```

## Recipe: update a skill

```bash
# Edit SKILL.md locally, then:
azd ai skill update my-skill --file ./skills/my-skill/
```

After update:
- Toolbox skill references (without pinned version) follow the new `default_version` — live immediately, no toolbox republish needed.
- `SkillsProvider` downloads at agent startup — redeploy agent to pick up the new version.

## Recipe: rollback a skill version

```bash
azd ai skill update my-skill --set-default-version 1
```

## Python SDK operations

For programmatic skill CRUD (create, list, download, delete) via the Python SDK, see the provisioning script in the sample:

[provision_skills.py](https://github.com/microsoft-foundry/foundry-samples/blob/main/samples/python/hosted-agents/agent-framework/responses/12-foundry-skills/provision_skills.py) — **read the script source** for the current API surface and usage patterns.

> The Skills SDK API is in preview and may change across versions. Always refer to the sample for the latest usage.

## RBAC

Skills require **Foundry User** on the Foundry project scope (for both the developer identity and the deployed agent's managed identity).

## Versioning

- Every `create` produces version 1 as the default.
- Every `update` creates a new immutable version and promotes it to default.
- `azd ai skill update <name> --set-default-version <ver>` repoints without uploading new content.
- Toolbox skill references without a pinned version follow the skill's `default_version`.
- Toolbox skill references with a pinned version (`skill@2`) stay on that version regardless.
- `SkillsProvider` downloads the `default_version` at agent startup.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|------------|-----|
| HTTP 500 on skill create | Quoted `name` or `description` in YAML front matter | Remove quotes from front matter values |
| `403 Forbidden` | Missing RBAC | Grant **Foundry User** on the project scope |
| `azd ai skill` not recognized | Extension not installed | `azd extension install azure.ai.skills` |
| Agent still uses old skill content after `update` | Toolbox skill pinned to old version, or skills provider caches at startup | Use consumer endpoint (no version pin), or redeploy agent |

## References

- [skill-toolbox-attach.md](skill-toolbox-attach.md) — attach skills to a toolbox, MCP protocol
- [skill-attach.md](skill-attach.md) — consume skills in agent code (direct download or toolbox MCP)
