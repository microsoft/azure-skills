# Depth Probe — Meet the User Where They Are

The VM Creator adapts its questioning to the user's expertise and intent. A beginner asking for a "dev VM" should not get peppered with networking and egress questions. An advanced networking engineer specifying "VMSS behind App Gateway with private endpoints" should not be asked whether they want a public IP.

## Philosophy

1. **Never ask a question whose answer can be inferred or safely defaulted.**
2. **Batch silent inferences into a Plan Card.** Defaulted decisions should be visible and editable.
3. **Defaults ladder.** When you must ask, prefer `[recommended default] / [show alternatives] / [I have specifics]`.
4. **Branching is signal-driven, not flag-driven.** Reclassify any time the user volunteers a deep signal.

## Classification — read the initial request

Score each signal that appears in the user's first 1-2 messages. The highest-scoring branch wins; a user can be in multiple branches.

| Signal phrase / keyword | Branch |
|---|---|
| "VNet", "subnet", "NSG", "egress", "private endpoint", "App Gateway", "accelerated networking", "service tag", "UDR", "IPv6", "DNS", "Bastion" | [networking-deep](networking-deep.md) |
| "vCPUs", "GPU", "memory", "family", "D-series", "N-series", "ephemeral OS disk", "proximity placement", "AMD", "Intel", "generation", "SR-IOV", "trusted launch" | [spec-deep](spec-deep.md) |
| "spot", "reserved", "savings plan", "hybrid benefit", "autoscale floor/ceiling", "$", "budget", "cheapest", "cost-optimize" | [cost-deep](cost-deep.md) |
| "managed identity", "Entra", "RBAC", "Key Vault", "JIT", "encryption at host", "CMK", "confidential", "compliance", "FedRAMP", "HIPAA" | [security-deep](security-deep.md) |
| "dev", "sandbox", "quick", "test out", "play with", "just need", "simple", or nothing specific | [beginner](beginner.md) |

> **Tiebreak:** prefer the branch that affects the most expensive defaults: Networking > Security > Spec > Cost > Beginner. Networking mistakes are the hardest to undo post-deployment.

## Cross-branch follow-ups (ask once, after primary branch)

| Question | When to ask |
|---|---|
| "Tags? (env, owner, cost-center)" | Always — but accept "none" without follow-up |
| "Resource group: existing or new?" | Always — propose `<vm-name>-rg` if new |
| "Number of instances?" | Only for VMSS |
| "Orchestration mode (Flexible/Uniform)?" | Only for VMSS — default Flexible |

## Reclassification mid-flow

If the user volunteers a deep signal at any step ("oh wait, I also need a NAT Gateway"), jump into that branch's questions for that topic. Never restart the whole flow — append the new questions and update the Plan Card.

## Anti-patterns

- ❌ Asking "what OS?" when the user said "Ubuntu sandbox"
- ❌ Asking about spot pricing for a Windows production VM
- ❌ Asking 8 networking questions before showing a Plan Card
- ❌ Defaulting to public IP open to `*` without flagging it in the Plan Card
- ❌ Burying the cost estimate at the bottom — put it on the Plan Card top row
