# Azure VM Connectivity Troubleshooting

> Diagnose and resolve Azure VM connectivity failures (RDP/SSH) by identifying symptoms, routing to the right solution, fetching the latest Microsoft documentation, and guiding the user through resolution.

## Quick Reference

| Property      | Details                                                                                                           |
| ------------- | ----------------------------------------------------------------------------------------------------------------- |
| Best for      | RDP/SSH connection failures, NSG/firewall misconfig, credential resets, NIC issues                                |
| Primary tools | Azure CLI, Azure PowerShell, Serial Console, Boot Diagnostics, Run Command                                        |
| Reference     | [references/cannot-connect-to-vm.md](references/cannot-connect-to-vm.md) |

## MCP Tools

| Tool            | Purpose                                                | Parameters                                                                                                           |
| --------------- | ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| `fetch_webpage` | Fetch latest Microsoft troubleshooting docs at runtime | `urls` (Required): Array of doc URLs from reference file; `query` (Optional): User's symptom for relevant extraction |

## Triggers

Activate this skill when user mentions:

- "can't connect to my VM" / "can't RDP" / "can't SSH"
- "RDP not working" / "SSH refused" / "connection timed out"
- "black screen" on VM
- "reset VM password" / "forgot password"
- "NSG blocking" / "firewall blocking" / "port 3389"
- "serial console" access
- "internal error" on RDP
- "VM not reachable" / "public IP not working"
- "RDP disconnects" / "session dropped"

---

## Workflow

### Phase 1: Determine User Intent

Infer the connectivity issue from the user's message. If the issue is clear, proceed to Phase 2. If ambiguous, ask **one** clarifying question:

| Signal in User Message                                                    | Inferred Category  |
| ------------------------------------------------------------------------- | ------------------ |
| "can't RDP", "RDP timeout", "RDP error", "black screen", "internal error" | Unable to RDP      |
| "can't SSH", "SSH refused", "permission denied", "publickey"              | Unable to SSH      |
| "NSG", "firewall", "port blocked", "no public IP", "NIC disabled"         | Network / Firewall |
| "credentials", "password", "wrong password", "access denied"              | Credential / Auth  |
| "VM agent", "Run Command not working", "Serial Console"                   | VM Agent / Tools   |

If unclear, ask: **"Are you trying to connect via RDP (Windows) or SSH (Linux), and what error message or behavior are you seeing?"**

If the user shares an Azure VM name or resource ID, attempt to use the azure-resource-lookup skill if available. If not available, attempt to the use the Azure CLI.

### Phase 2: Route to Solution

Open [references/cannot-connect-to-vm.md](references/cannot-connect-to-vm.md) and find the **Symptoms → Solutions** table that matches the user's category. Narrow down to the specific row matching their symptom.

If additional details are needed to narrow to a specific solution row, ask the user. For example:
- "What error message do you see in the RDP dialog?"
- "Does the connection time out, or do you get an error immediately?"
- "Is this a Windows or Linux VM?"

### Phase 3: Fetch Documentation

Once you've identified the specific solution row, fetch the linked Microsoft documentation URL for the latest troubleshooting guidance:

```javascript
fetch_webpage({
  urls: ["<documentation-url-from-solution-row>"],
  query: "<user's specific symptom or error message>"
})
```

This ensures the user gets current guidance even if Microsoft updates their docs.

### Phase 4: Diagnose and Respond

Combine the fetched documentation with the quick commands from the reference file to give the user a response:

1. **Explain the likely cause** based on their symptom
2. **Provide the immediate diagnostic/fix commands** from the reference file's Quick Commands section
3. **Summarize the key resolution steps** from the fetched documentation
4. **If the user is logged into Azure**, offer to run diagnostic CLI commands to confirm the root cause before applying fixes
5. **Recommend next steps** — what to verify after the fix, and what to do if it doesn't work

### Phase 5: Escalation (if needed)

If the symptom doesn't match any solution in the reference file, or the fix doesn't resolve the issue:

1. Check Azure Resource Health: `az vm get-instance-view --name <vm> -g <rg> --query "instanceView.statuses" -o table`
2. Try restart: `az vm restart --name <vm> -g <rg>`
3. Try redeploy: `az vm redeploy --name <vm> -g <rg>`
4. Fetch the comprehensive guide: [Troubleshoot RDP connections](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/windows/troubleshoot-rdp-connection) or [Troubleshoot SSH connections](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/troubleshoot-ssh-connection)

---

## Error Handling

| Error                                  | Likely Cause                    | Action                                                                             |
| -------------------------------------- | ------------------------------- | ---------------------------------------------------------------------------------- |
| `fetch_webpage` fails or returns empty | URL may have changed            | Fall back to quick commands in reference file; suggest user check the URL manually |
| CLI command fails with "not found"     | VM name or resource group wrong | Ask user to verify VM name and resource group                                      |
| Run Command times out                  | VM agent not responding         | Route to "VM Agent Not Responding" section in reference file                       |
| Serial Console not available           | Boot diagnostics not enabled    | Run `az vm boot-diagnostics enable` first                                          |
| Password reset fails                   | VMAccess extension error        | Check reference file for VMAccess alternatives (offline reset, Serial Console)     |

---

## References

- [Cannot Connect to VM — Symptom Router](references/cannot-connect-to-vm.md)