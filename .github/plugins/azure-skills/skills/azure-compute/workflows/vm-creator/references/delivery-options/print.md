# Mode A — Print in chat

Default. Render fenced code blocks for each file, in this order:

1. **Bicep:** `main.bicep` + the `az deployment group create` command at the bottom
2. **Terraform:** `main.tf` + `variables.tf` (separate fenced blocks) + the `terraform init && terraform apply` command
3. **bash:** the single script

Append a one-liner reminder: *"Want me to save this to disk or open a PR? Just ask."* — so the user can shift to Mode B/C without restarting.
