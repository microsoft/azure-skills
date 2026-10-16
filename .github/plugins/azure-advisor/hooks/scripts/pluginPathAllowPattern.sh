# --- azure-advisor plugin ---
[[ "$p" == *".copilot/installed-plugins/"*"/azure-advisor/skills/"* ]] && return 0
[[ "$p" == *".claude/plugins/cache/azure-skills/azure-advisor/"*"/skills/"* ]] && return 0
[[ "$p" == *".cursor/plugins/cache/"*"/azure-advisor/"*"/skills/"* ]] && return 0
[[ "$p" == *"agent-plugins/github.com/microsoft/azure-skills/.github/plugins/azure-advisor/skills/"* ]] && return 0
