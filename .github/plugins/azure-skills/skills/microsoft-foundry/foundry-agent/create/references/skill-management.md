# Skills (azd ai)

How to create, manage, and version **skills** (reusable behavioral guidelines) in a Foundry project using `azd ai skill` and the Python SDK.

A **skill** is a Markdown file with YAML front matter (`SKILL.md`), uploaded to a Foundry project, and attached to agents at runtime. Skills enable updating agent behavior **without code changes**.

> 📘 For attaching skills to a toolbox (`azd ai toolbox skill add/remove/list`) and the raw MCP protocol, see [skill-toolbox.md](skill-toolbox.md).
>
> 📘 For consuming skills in agent code (Agent Framework SDK integration, progressive disclosure, `load_skill`), see [use-skills-in-hosted-agent.md](use-skills-in-hosted-agent.md).

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

The `description` field drives skill discovery at runtime: the Agent Framework SDK uses it to decide when to load the skill. Write descriptions that clearly state **when** the agent should use the skill. See [use-skills-in-hosted-agent.md § How progressive disclosure works](use-skills-in-hosted-agent.md) for details.

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

The SDK uses `AIProjectClient.beta.skills` (preview API surface, requires `allow_preview=True`).

```python
import os
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential

async with (
    DefaultAzureCredential() as credential,
    AIProjectClient(
        endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        credential=credential,
        allow_preview=True,
    ) as project,
):
    # Create from package (in-memory ZIP)
    imported = await project.beta.skills.create_from_package(zip_bytes)

    # List
    async for skill in project.beta.skills.list():
        print(f"{skill.name}: {skill.description}")

    # Download
    stream = await project.beta.skills.download("my-skill")
    zip_bytes = b"".join([chunk async for chunk in stream])

    # Delete
    await project.beta.skills.delete("my-skill")
```

Full provisioning script: [provision_skills.py](https://github.com/microsoft-foundry/foundry-samples/blob/main/samples/python/hosted-agents/agent-framework/responses/12-foundry-skills/provision_skills.py).

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
| Skill attached but agent doesn't use it | Description too vague for progressive disclosure | Improve `description` in SKILL.md front matter |
| Agent still uses old skill content after `update` | Toolbox skill pinned to old version, or `SkillsProvider` caches at startup | Use consumer endpoint (no version pin), or redeploy agent |
| `create_from_package` fails | SDK client missing preview flag | `AIProjectClient(allow_preview=True)` |
