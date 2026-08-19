# Pod Failures & Application Issues

## Evidence Bundle Script

For **any** pod symptom below, run the **pod-evidence** script to collect the same
read-only evidence bundle. Per pod it digests **STATUS**, **STATE** (exit code, reason,
last state), **EVENTS**, current/previous **LOGS**, and **RESOURCES** (requests vs
`top`). It only gathers; interpret with the tables.

Bash [`../../scripts/pod-evidence.sh`](../../scripts/pod-evidence.sh) · PowerShell [`../../scripts/pod-evidence.ps1`](../../scripts/pod-evidence.ps1)

```bash
../../scripts/pod-evidence.sh <pod-name> -n <namespace>   # one pod
../../scripts/pod-evidence.sh --all-failing               # all unhealthy pods
```

PowerShell: `../../scripts/pod-evidence.ps1 <pod-name> -Namespace <namespace>` (`-AllFailing` scans all).

---

## CrashLoopBackOff

Pod starts, crashes, restarts with exponential backoff (10s, 20s, 40s... up to 5m).

**Diagnostics:** [pod-evidence](#evidence-bundle-script) → read **STATE** (exit code, reason, last state) and **PREV LOGS** (last crashed container).

**Decision tree:**

| Exit Code | Meaning                                               | Fix Path                                                      |
| --------- | ----------------------------------------------------- | ------------------------------------------------------------- |
| `0`       | App exited successfully (unexpected for long-running) | Check if entrypoint/command is correct; app may be a one-shot |
| `1`       | Application error                                     | Read logs - unhandled exception, missing config, bad startup  |
| `137`     | OOMKilled (SIGKILL)                                   | Increase `resources.limits.memory`; check for memory leaks    |
| `139`     | Segfault (SIGSEGV)                                    | Binary compatibility issue or native code bug                 |
| `143`     | SIGTERM - graceful shutdown                           | Pod was terminated; check if liveness probe killed it         |

**OOMKilled specifically:** the **STATE** section shows `terminated=OOMKilled` and **RESOURCES** shows the memory limit vs live usage. Fix: increase `resources.limits.memory` or optimize application memory usage.

**OOM kill tracing with Inspektor Gadget:** Run `trace_oomkill` for the pod to see which process was killed and memory at kill time: `scripts/run-ig.sh --gadget trace_oomkill --pod <pod-name> --ns <namespace>` (or `run-ig.ps1`).

**Deep diagnostics with Inspektor Gadget** (when logs and describe are inconclusive):

Use [`scripts/run-ig.sh`](references/inspektor-gadget.md) (or `run-ig.ps1`) with `--pod <pod-name> --ns <namespace>` and these gadgets:

- `trace_exec` — see what the container executes at startup
- `trace_open` — find missing configs/secrets (retval -2 = ENOENT, -13 = EACCES)
- `snapshot_process` — list running processes in the pod

---

## ImagePullBackOff

Pod can't pull the container image.

**Diagnostics:** [pod-evidence](#evidence-bundle-script) → read **EVENTS** for the exact pull error.

| Error Message                           | Cause                        | Fix                                                            |
| --------------------------------------- | ---------------------------- | -------------------------------------------------------------- |
| `ErrImagePull` / `ImagePullBackOff`     | Image name or tag is wrong   | Verify image name and tag exist in the registry                |
| `unauthorized: authentication required` | Missing or wrong pull secret | Create/update `imagePullSecrets` on the pod or service account |
| `manifest unknown`                      | Tag doesn't exist            | Check available tags in the registry                           |
| `context deadline exceeded`             | Registry unreachable         | Check network/firewall; for ACR, verify AKS -> ACR integration |

**ACR integration check:**

```bash
# Verify AKS is attached to ACR
az aks check-acr -g <rg> -n <cluster> --acr <acr-name>.azurecr.io
```

---

## Pending Pods

Pod stays in `Pending` - scheduler can't place it.

**Diagnostics:** [pod-evidence](#evidence-bundle-script) → read **EVENTS** for why scheduling failed.

| Event Message                                                          | Cause                               | Fix                                                             |
| ---------------------------------------------------------------------- | ----------------------------------- | --------------------------------------------------------------- |
| `Insufficient cpu` / `Insufficient memory`                             | No node has enough resources        | Scale node pool; reduce resource requests; check for overcommit |
| `node(s) had taint ... that the pod didn't tolerate`                   | Taint/toleration mismatch           | Add matching toleration or use a different node pool            |
| `node(s) didn't match Pod's node affinity/selector`                    | Affinity rule unsatisfiable         | Check `nodeSelector` or `nodeAffinity` rules                    |
| `persistentvolumeclaim ... not found` / `unbound`                      | PVC not ready                       | Check PVC status; verify storage class exists                   |
| `0/N nodes are available: N node(s) had volume node affinity conflict` | Zonal disk vs pod in different zone | Use ZRS storage class or ensure same zone                       |

---

## Readiness & Liveness Probe Failures

**Readiness probe failure** -> pod removed from Service endpoints (no traffic). **Liveness probe failure** -> pod killed and restarted.

**Diagnostics:** [pod-evidence](#evidence-bundle-script) → **EVENTS** shows `Readiness/Liveness probe failed`; **STATUS** shows the READY column (must be n/n).

| Symptom                              | Cause                   | Fix                                                        |
| ------------------------------------ | ----------------------- | ---------------------------------------------------------- |
| READY shows `0/1` but pod is Running | Readiness probe failing | Check probe path, port, and app health endpoint            |
| Pod restarts repeatedly              | Liveness probe failing  | Increase `initialDelaySeconds`; check if app starts slowly |
| Probe timeout errors                 | App responds too slowly | Increase `timeoutSeconds`; check app performance           |

> 💡 **Tip:** Set `initialDelaySeconds` on liveness probes to be longer than your app's startup time. A common mistake is killing pods before they finish initializing.

---

## Resource Constraints (CPU/Memory)

**Check actual usage vs limits:** [pod-evidence](#evidence-bundle-script) → **RESOURCES** compares requests/limits against live `top` usage. To rank a namespace by memory: `kubectl top pod -n <namespace> --sort-by=memory`.

| Symptom                          | Cause                                   | Fix                                                 |
| -------------------------------- | --------------------------------------- | --------------------------------------------------- |
| OOMKilled (exit code 137)        | Container exceeded memory limit         | Increase `limits.memory` or fix memory leak         |
| CPU throttling (slow responses)  | Container hitting CPU limit             | Increase `limits.cpu` or remove CPU limits          |
| Pending - insufficient resources | Requests exceed available node capacity | Lower requests, scale nodes, or use larger VM sizes |

> ⚠️ **Warning:** Setting CPU limits can cause unnecessary throttling even when the node has spare capacity. Many teams set CPU requests but not limits. Memory limits should always be set.
