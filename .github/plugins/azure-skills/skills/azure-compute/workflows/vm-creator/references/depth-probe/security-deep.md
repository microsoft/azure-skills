# Security-deep branch

| Topic | Question | Default |
|---|---|---|
| Managed identity | "System-assigned managed identity?" | `true` (off by default in raw `az vm create`, but we recommend on) |
| Encryption at host | "Encryption at host?" | `true` (requires subscription opt-in — flag if not enabled) |
| Disk encryption set | "Customer-managed key (CMK) on OS disk?" | Skip unless compliance mentioned |
| Confidential VM | "Confidential compute (AMD SEV-SNP)?" | Only if user mentioned `confidential` / `attestation` |
| JIT access | "Enable Just-In-Time RDP/SSH (Defender for Cloud)?" | Offer if subscription has Defender plan |
| Boot diagnostics | "Managed boot diagnostics?" | `true` (Azure-managed storage) |
| Vulnerability scanning | "Enable Defender for Servers Plan 2?" | Mention; do not auto-enable (incurs cost) |

## Notes

- Encryption-at-host needs the subscription feature flag `EncryptionAtHost` registered — check via `az feature show` and surface a remediation step if not.
- CMK setup is multi-resource (Key Vault + Disk Encryption Set + RBAC); for first-time users, suggest scaffolding via the `azure-prepare` skill instead.
- JIT access is per-VM and per-port; default to 3-hour windows on 22/3389, not the wider "all common ports" preset.
