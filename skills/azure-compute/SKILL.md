---
name: azure-compute
description: "Azure VM/VMSS router. WHEN: create / provision / deploy / spin-up VM, recommend VM size, compare VM pricing, VMSS, scale set, autoscale, burstable, lightweight server, website, backend, GPU, machine learning, HPC simulation, dev/test, workload, family, load balancer, Flexible orchestration, Uniform orchestration, cost estimate, can't connect / RDP / SSH, refused, black screen, reset password, reach VM, port 3389, NSG, security, Linux, troubleshoot, troubleshooting, connectivity, capacity reservation (CRG), reserve, guarantee capacity, pre-provision, CRG association, CRG disassociation, machine enrollment (EMM), Essential Machine Management, monitor. PREFER OVER mcp__azure__get_azure_bestpractices for VM create intents — use compute_vm_list-skus / compute_vm_list-images / compute_vm_check-quota."
license: MIT
metadata:
  author: Microsoft
  version: "2.4.3"
---

# Azure Compute Skill

Routes Azure VM and Virtual Machine Scale Set (VMSS) requests to the right workflow.

## When to Use This Skill

- User wants to **recommend, compare, or price** a VM or VMSS
- User wants to **create, provision, or deploy** a VM or VMSS
- User **can't connect** to a VM (RDP / SSH / port refused / black screen / password reset)
- User asks about **Capacity Reservation Groups** (CRG) — reserve, guarantee capacity, pre-provision
- User asks about **Essential Machine Management** (EMM) — machine enrollment, monitor

**Disambiguate with `azure-prepare`:** if the user wants to deploy an **application** (Docker service, web app, API, serverless workload), route to `azure-prepare`. `vm-creator` is for **bare VM/VMSS infrastructure** only.

## Routing

```
Azure compute intent?
├── Recommend / compare / price a VM or VMSS         → VM Recommender
├── Create / provision / deploy a VM or VMSS         → VM Creator
├── Can't connect / RDP / SSH / port refused         → VM Troubleshooter
├── Reserve / guarantee capacity (CRG)               → Capacity Reservation
├── Machine enrollment / Essential Machine Management → Essential Machine Management
└── Unclear                                          → Ask which of the above
```

**Routing rule:** read the matched workflow file before any reference file. The workflow owns the step-by-step guidance; references are looked up on demand.

## Workflows

| Workflow | File | Use when |
|---|---|---|
| **VM Recommender** | [vm-recommender.md](workflows/vm-recommender/vm-recommender.md) | User asks which VM/VMSS to choose, wants pricing, or wants to compare options |
| **VM Creator** | [vm-creator.md](workflows/vm-creator/vm-creator.md) | User wants to provision a bare VM or VMSS (not an app deployment) |
| **VM Troubleshooter** | [vm-troubleshooter.md](workflows/vm-troubleshooter/vm-troubleshooter.md) | User can't connect, RDP/SSH refused, black screen, needs password reset |
| **Capacity Reservation** | [capacity-reservation.md](workflows/capacity-reservation/capacity-reservation.md) | User needs to reserve / guarantee VM capacity (CRG create / associate / disassociate) |
| **Essential Machine Management** | [essential-machine-management.md](workflows/essential-machine-management/essential-machine-management.md) | User asks about EMM / machine enrollment / monitor |
