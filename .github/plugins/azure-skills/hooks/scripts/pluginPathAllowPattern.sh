# --- azure-skills plugin ---
# The Copilot CLI pattern wildcards the catalog/marketplace folder name
# because it does not necessarily match the published plugin name.
[[ "$p" == *".copilot/installed-plugins/"*"/azure/skills/"* ]] && return 0
[[ "$p" == *".claude/plugins/cache/azure-skills/azure/"*"/skills/"* ]] && return 0
[[ "$p" == *".claude/plugins/cache/claude-plugins-official/azure/"*"/skills/"* ]] && return 0
[[ "$p" == *".cursor/plugins/cache/"*"/azure/"*"/skills/"* ]] && return 0
[[ "$p" == *"agent-plugins/github.com/microsoft/azure-skills/.github/plugins/azure-skills/skills/"* ]] && return 0
