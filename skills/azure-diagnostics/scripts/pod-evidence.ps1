<#
.SYNOPSIS
    Collects the invariant, read-only AKS pod-failure evidence bundle and prints a
    single labeled digest.
.DESCRIPTION
    Gathers the same evidence bundle for one or more pods regardless of the symptom
    (CrashLoopBackOff, OOMKilled, Pending, probe failures, ImagePullBackOff). For each
    pod it collects and summarizes:
      STATUS     - READY / phase / restart count          (kubectl get pod -o wide)
      STATE      - exit code, reason, last-state snippet   (jsonpath over containerStatuses)
      EVENTS     - the Events section                      (kubectl describe pod)
      LOGS       - current container logs (tailed)         (kubectl logs)
      PREV LOGS  - previous/crashed container logs (tailed)(kubectl logs --previous)
      RESOURCES  - requests/limits vs live usage           (jsonpath + kubectl top pod)

    This script only GATHERS and DIGESTS evidence. It never mutates cluster state.
    Interpreting the digest to pick a fix stays with the caller.
.PARAMETER Pod
    Pod name (single-pod mode). Omit when using -AllFailing.
.PARAMETER Namespace
    Namespace of the pod. Required in single-pod mode. In -AllFailing mode, limits the
    scan to this namespace.
.PARAMETER AllFailing
    Auto-select every pod not in Running/Succeeded phase (across all namespaces unless
    -Namespace is given) and digest each.
.PARAMETER Tail
    Number of log lines to show per stream. Default 50.
.EXAMPLE
    .\pod-evidence.ps1 my-api-7d9f-abcde -Namespace prod
.EXAMPLE
    .\pod-evidence.ps1 -AllFailing
.EXAMPLE
    .\pod-evidence.ps1 -AllFailing -Namespace prod -Tail 100
#>
param(
    [Parameter(Position = 0)][string]$Pod,
    [Alias("n")][string]$Namespace,
    [switch]$AllFailing,
    [int]$Tail = 50
)

# Best-effort: individual kubectl reads may fail (unreachable cluster, missing
# metrics-server, no previous logs). PowerShell's default $ErrorActionPreference is
# "Continue", so a single failed read is suppressed via 2>$null and the digest proceeds
# instead of aborting — no explicit assignment needed.

if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    Write-Error "kubectl not found on PATH."
    exit 1
}

if ($Tail -le 0) {
    Write-Error "-Tail must be a positive integer (got '$Tail')."
    exit 2
}

function Digest-Pod {
    param([string]$Ns, [string]$Name)

    Write-Host "=================================================================="
    Write-Host "POD: $Name   NAMESPACE: $Ns"
    Write-Host "=================================================================="

    Write-Host "--- STATUS (ready / phase / restarts) ---"
    $status = kubectl get pod $Name -n $Ns -o wide 2>&1
    if ($LASTEXITCODE -eq 0 -and $status) { $status | ForEach-Object { Write-Host "$_" } } else { Write-Host "(unable to get pod)" }
    Write-Host ""

    Write-Host "--- STATE (exit code / reason / last state) ---"
    $jp = '{range .status.containerStatuses[*]}container={.name}{"`n"}  ready={.ready} restarts={.restartCount}{"`n"}  current: waiting={.state.waiting.reason} running={.state.running.startedAt} terminated={.state.terminated.reason}(exit={.state.terminated.exitCode}){"`n"}  lastState: terminated={.lastState.terminated.reason}(exit={.lastState.terminated.exitCode}) at {.lastState.terminated.finishedAt}{"`n"}{end}'
    $state = kubectl get pod $Name -n $Ns -o jsonpath=$jp 2>$null
    if ($state) { Write-Host $state } else { Write-Host "(no container status available)" }
    Write-Host ""

    Write-Host "--- EVENTS ---"
    $desc = kubectl describe pod $Name -n $Ns 2>$null
    if ($desc) {
        $idx = ($desc | Select-String -Pattern '^Events:' | Select-Object -First 1).LineNumber
        if ($idx) {
            $desc | Select-Object -Skip ($idx - 1) | Select-Object -First 25 | ForEach-Object { Write-Host "$_" }
        } else {
            Write-Host "(no Events section)"
        }
    } else {
        Write-Host "(unable to describe pod)"
    }
    Write-Host ""

    Write-Host "--- LOGS (current, last $Tail lines) ---"
    $logs = kubectl logs $Name -n $Ns --tail=$Tail 2>&1
    if ($logs) { $logs | ForEach-Object { Write-Host "$_" } } else { Write-Host "(no current logs)" }
    Write-Host ""

    Write-Host "--- PREV LOGS (previous instance, last $Tail lines) ---"
    $prev = kubectl logs $Name -n $Ns --previous --tail=$Tail 2>$null
    if ($LASTEXITCODE -eq 0 -and $prev) {
        Write-Host $prev
    } else {
        Write-Host "(no previous-instance logs - pod has not restarted or they were rotated)"
    }
    Write-Host ""

    Write-Host "--- RESOURCES (requests/limits vs live usage) ---"
    Write-Host "requests/limits:"
    $res = kubectl get pod $Name -n $Ns -o jsonpath='{range .spec.containers[*]}  {.name}: requests={.resources.requests} limits={.resources.limits}{"`n"}{end}' 2>$null
    if ($res) { Write-Host $res } else { Write-Host "  (unable to read resources)" }
    Write-Host "live usage:"
    $top = kubectl top pod $Name -n $Ns 2>&1
    if ($top) { $top | ForEach-Object { Write-Host "  $_" } } else { Write-Host "  (metrics-server unavailable)" }
    Write-Host ""
}

if ($AllFailing) {
    $scope = if ($Namespace) { " in namespace '$Namespace'" } else { "" }
    Write-Host "pod-evidence: scanning for pods not in Running/Succeeded$scope..."

    $cols = "custom-columns=NS:.metadata.namespace,NAME:.metadata.name"
    if ($Namespace) {
        $rows = kubectl get pods -n $Namespace --field-selector=status.phase!=Running,status.phase!=Succeeded --no-headers -o $cols 2>$null
    } else {
        $rows = kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded --no-headers -o $cols 2>$null
    }

    $rows = @($rows | Where-Object { $_ -and $_.Trim() })
    if ($rows.Count -eq 0) {
        Write-Host "No unhealthy pods found (all pods are Running or Succeeded)."
        exit 0
    }

    Write-Host "Found $($rows.Count) unhealthy pod(s). Collecting evidence for each below."
    Write-Host ""
    foreach ($row in $rows) {
        $parts = ($row -split '\s+') | Where-Object { $_ }
        Digest-Pod -Ns $parts[0] -Name $parts[1]
    }
    Write-Host "pod-evidence: done. Reviewed $($rows.Count) failing pod(s) - use the STATE/EVENTS/LOGS above to pick a fix."
} else {
    if (-not $Pod) {
        Write-Error "A pod name is required (or use -AllFailing)."
        exit 2
    }
    if (-not $Namespace) {
        Write-Error "-Namespace is required in single-pod mode."
        exit 2
    }
    Write-Host "pod-evidence: collecting the read-only evidence bundle for pod '$Pod' in namespace '$Namespace'."
    Write-Host ""
    Digest-Pod -Ns $Namespace -Name $Pod
    Write-Host "pod-evidence: done. Use the STATE/EVENTS/LOGS/RESOURCES digest above to pick a fix."
}
