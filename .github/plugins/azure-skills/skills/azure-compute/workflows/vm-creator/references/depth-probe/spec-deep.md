# Spec-deep branch

Goal: nail the SKU. Lean on `compute_vm_list-skus` (with filters) instead of asking the user to memorize SKU names.

| Topic | Question | How to answer |
|---|---|---|
| vCPUs / RAM | "Target vCPUs and memory?" | Call `compute_vm_list-skus` with `minVCpus` + `minMemoryGb`; show top 3 |
| GPU | "GPU workload?" | If yes: `familyPrefix=Standard_N`; ask CUDA vs render |
| Family | "Family preference (general D, compute F, memory E, burstable B, GPU N)?" | Skip if vCPU/RAM already nailed it down |
| Generation | "VM generation (v5/v6, AMD/Intel)?" | Default to latest gen available in region |
| Ephemeral OS disk | "Ephemeral OS disk (faster, but no resize/restore)?" | `false` unless workload is stateless tier |
| Trusted Launch / Gen2 | "Gen2 / Trusted Launch?" | `true` (Azure default for new VMs since 2023) |
| Proximity placement | "Need low-latency between VMs?" | Skip unless multi-VM cluster |
| Zone | "Pin to an Availability Zone?" | Skip for single VM unless HA; default `1` for VMSS spreading |

## Notes

- For GPU asks, always include the per-hour price in the Plan Card — N-series VMs can hit $3-30/hr.
- If the user says "compute-heavy", default to F-series (compute-optimized) before D-series.
- Burstable B-series is only correct for spiky/idle workloads — flag it explicitly so the user knows it'll throttle under sustained load.
