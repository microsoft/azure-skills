# End-to-End Test (VNet Access Required)

Continues from [post-deployment-validation.md](post-deployment-validation.md). Steps 1–3 there must be complete first.

## 4. VNet Access Setup

> ⚠️ The remaining tests require connectivity to the VNet.

Use `AskUserQuestion`: **"Steps 1-3 are done. The remaining tests need VNet access. How do you want to proceed?"**
Options:
- `I have a Bastion VM / jump box`
- `Set up a point-to-site VPN for me` — read [vpn-dns-setup.md](vpn-dns-setup.md)
- `I have VPN / ExpressRoute already`
- `Skip testing for now`

**Bastion VM:** User has direct access to all private endpoints from the VM. Setup is complete — do NOT proceed to Step 5.

---

## 5. End-to-End Test (VPN users only)

Three phases:
1. **Network** — DNS resolution + port 443 reachability
2. **Agent Lifecycle** — Create agent, thread, run, verify, cleanup
3. **Isolation Proof** — Repeat with VPN off — expect 403

> ⚠️ Chromium browsers may bypass VPN DNS via Secure DNS (DoH). If portal shows "Error loading agents" but CLI works, disable Secure DNS.

### Requirements

```bash
pip install azure-ai-projects azure-identity azure-ai-agents
```

### Phase 1: Network Validation

Resolve DNS and test port 443 for all private endpoints. Substitute actual resource names from the deployment.

PowerShell:

```powershell
$endpoints = @(
  '<ai-account>.services.ai.azure.com',
  '<ai-account>.openai.azure.com',
  '<ai-account>.cognitiveservices.azure.com',
  '<cosmos-account>.documents.azure.com',
  '<storage-account>.blob.core.windows.net',
  '<search-service>.search.windows.net'
)
foreach ($h in $endpoints) {
  $ip = (Resolve-DnsName $h | Where-Object {$_.IPAddress}).IPAddress
  $reach = Test-NetConnection $h -Port 443 -WarningAction SilentlyContinue
  Write-Host "$h -> $ip (reachable: $($reach.TcpTestSucceeded))"
}
```

Bash:

```bash
endpoints=(
  '<ai-account>.services.ai.azure.com'
  '<ai-account>.openai.azure.com'
  '<ai-account>.cognitiveservices.azure.com'
  '<cosmos-account>.documents.azure.com'
  '<storage-account>.blob.core.windows.net'
  '<search-service>.search.windows.net'
)
for h in "${endpoints[@]}"; do
  ip=$(dig +short "$h" | tail -n1)
  nc -z -w 3 "$h" 443 >/dev/null 2>&1 && reach=yes || reach=no
  echo "$h -> $ip (reachable: $reach)"
done
```

All should resolve to private IPs and be reachable.

Report results to the user (✅/❌ per endpoint) before proceeding to Phase 2.

### Phase 2: Agent Lifecycle Test

Create agent, thread, send message, verify response, cleanup. This exercises all 4 PEs (AI Services, Cosmos DB, Storage, AI Search).

```python
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

endpoint = "https://<ai-account>.services.ai.azure.com/api/projects/<project-name>"
client = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())
agents = client.agents

agent = agents.create_agent(model="<deployment-name>", name="vnet-test", instructions="Reply with 'OK'")
thread = agents.threads.create()
agents.messages.create(thread_id=thread.id, role="user", content="test")
run = agents.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)
msgs = agents.messages.list(thread_id=thread.id)
print(f"Response: {msgs.data[0].content[0].text.value}")
agents.threads.delete(thread.id)
agents.delete_agent(agent.id)
```

Report results to the user (which PEs passed, any failures) before proceeding to Phase 3.

Ask user to disconnect VPN. Repeat Phase 2 — it should fail with 403. Report whether isolation is confirmed before proceeding to cross-check.

### Requirements Cross-Check

After testing, compare each requirement gathered in [intake.md](intake.md) against the deployed state. Flag any mismatches with remediation steps.

### Cleanup (VPN users only)

Ask if user wants to delete VPN Gateway (~$140/month) and DNS Resolver (~$180/month), or keep for ongoing access.

```bash
az network vnet-gateway delete --resource-group <rg> --name vpn-gateway-<suffix> --no-wait
az network dns-resolver delete --resource-group <rg> --name dns-resolver-<suffix> --yes
az network public-ip delete --resource-group <rg> --name vpn-gateway-pip-<suffix>
```
