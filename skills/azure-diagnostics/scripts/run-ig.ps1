<#
.SYNOPSIS
  Runs an Inspektor Gadget (IG) trace on an AKS node via `kubectl debug`.

.DESCRIPTION
  Handles the mechanical, error-prone assembly of the IG invocation:
    - resolves the target node from a pod (or takes a node directly)
    - injects the pinned IG image + version
    - applies the correct default -Timeout for the gadget type
    - adds the k8s namespace/pod/container filters
    - handles the special `tcpdump` gadget (pcap-ng output piped to tcpdump)

  The privileged debug pod requires explicit user approval and appropriate RBAC.
  Use -DryRun to print the assembled command without running it.

.PARAMETER Gadget
  Gadget to run, e.g. trace_dns, snapshot_socket, tcpdump (required).

.PARAMETER Pod
  Pod name; the node is resolved automatically.

.PARAMETER Namespace
  Namespace of the pod (required with -Pod).

.PARAMETER Node
  Run directly against a node (node-wide scope).

.PARAMETER Container
  Scope to a specific container.

.PARAMETER Timeout
  Override the gadget-type default timeout (seconds).

.PARAMETER Filter
  Extra IG flags, passed through verbatim (e.g. -Filter --max-entries,20).

.PARAMETER Pf
  tcpdump packet filter (tcpdump gadget only, e.g. "port 80").

.PARAMETER IgVersion
  Override the pinned IG image tag.

.PARAMETER DryRun
  Print the assembled command; do not execute.

.EXAMPLE
  ./run-ig.ps1 -Gadget trace_dns -Pod web-0 -Namespace default

.EXAMPLE
  ./run-ig.ps1 -Gadget snapshot_process -Node aks-nodepool1-1234

.EXAMPLE
  ./run-ig.ps1 -Gadget tcpdump -Pod web-0 -Namespace default -Pf "port 80"

.EXAMPLE
  ./run-ig.ps1 -Gadget traceloop -Pod web-0 -Namespace default -Filter --syscall-filters,open,connect

.EXAMPLE
  ./run-ig.ps1 -Gadget trace_dns -Pod web-0 -Namespace default -DryRun
#>
[CmdletBinding()]
param(
    [string]$Gadget,
    [string]$Pod,
    [Alias('Ns')]
    [string]$Namespace,
    [string]$Node,
    [string]$Container,
    [int]$Timeout,
    [string[]]$Filter,
    [string]$Pf,
    # Pinned IG image tag. Bump this default (and run-ig.sh) to update the IG version.
    [string]$IgVersion = 'v0.51.0',
    [switch]$DryRun
)

$IgImageRepo = 'mcr.microsoft.com/oss/v2/inspektor-gadget/ig'

if (-not $Gadget) {
    Write-Error 'Provide -Gadget <name> (e.g. trace_dns, snapshot_socket, tcpdump).'
    exit 2
}
if (-not $Node -and -not $Pod) {
    Write-Error 'Provide either -Node <node> or -Pod <pod> -Namespace <namespace>.'
    exit 2
}
if ($Pod -and -not $Namespace) {
    Write-Error '-Pod requires -Namespace <namespace>.'
    exit 2
}
if ($Pf -and $Gadget -ne 'tcpdump') {
    Write-Error '-Pf is only valid for the tcpdump gadget.'
    exit 2
}

# Default timeout by gadget type, inferred from the gadget name prefix.
#   snapshot_* / top_*            -> 5s  (point-in-time / quick aggregate)
#   trace_* / profile_* / tcpdump -> 30s (streaming / sampling)
function Get-DefaultTimeout([string]$g) {
    switch -Wildcard ($g) {
        'snapshot_*' { return 5 }
        'top_*'      { return 5 }
        'trace_*'    { return 30 }
        'profile_*'  { return 30 }
        'tcpdump'    { return 30 }
        default      { return 30 }  # unknown gadget: use the safer streaming default
    }
}

if (-not $PSBoundParameters.ContainsKey('Timeout') -or $Timeout -le 0) {
    $Timeout = Get-DefaultTimeout $Gadget
}

# Resolve the node name from the pod when not given directly.
if (-not $Node) {
    $Node = ((& kubectl get pod $Pod -n $Namespace -o "jsonpath={.spec.nodeName}" 2>$null) | Out-String).Trim()
    if (-not $Node) {
        Write-Error "Could not resolve node for pod '$Pod' in namespace '$Namespace'."
        exit 1
    }
}

$IgImage = "${IgImageRepo}:${IgVersion}"

# Assemble the k8s scoping filters.
$filters = @()
if ($Namespace) { $filters += @('--k8s-namespace', $Namespace) }
if ($Pod)       { $filters += @('--k8s-podname', $Pod) }
if ($Container) { $filters += @('--k8s-containername', $Container) }

# Base kubectl debug invocation.
$debug = @('debug', '--profile=sysadmin', "node/$Node", '--attach', '--quiet', "--image=$IgImage", '--')

if ($Gadget -eq 'tcpdump') {
    # tcpdump emits raw pcap-ng; pipe through tcpdump for readable output when available.
    $igCmd = @('ig', 'run', "tcpdump:$IgVersion", '-o', 'pcap-ng') + $filters + @('--timeout', "$Timeout")
    if ($Pf) { $igCmd += @('--pf', $Pf) }
    if ($Filter) { $igCmd += $Filter }
}
else {
    $igCmd = @('ig', 'run', "${Gadget}:$IgVersion", '-o', 'json') + $filters + @('--timeout', "$Timeout")
    if ($Filter) { $igCmd += $Filter }
}

$fullArgs = $debug + $igCmd

# Pretty-print a shell-quoted version of the command for display.
function Format-Cmd([string[]]$parts) {
    ($parts | ForEach-Object {
        if ($_ -match '\s') { '"' + $_ + '"' } else { $_ }
    }) -join ' '
}

$displayCmd = 'kubectl ' + (Format-Cmd $fullArgs)

# The tcpdump gadget is only piped through `tcpdump` when that binary is present.
# Reflect the real behavior in the displayed command so -DryRun does not mislead.
$tcpdumpAvail = $Gadget -eq 'tcpdump' -and [bool](Get-Command tcpdump -ErrorAction SilentlyContinue)
if ($tcpdumpAvail) {
    $displayCmd = "$displayCmd | tcpdump -nvr -"
}

Write-Host "Gadget:  $Gadget"
Write-Host "Node:    $Node"
Write-Host "Timeout: ${Timeout}s"
Write-Host "Image:   $IgImage"
Write-Host "Command: $displayCmd"
if ($Gadget -eq 'tcpdump' -and -not $tcpdumpAvail) {
    Write-Host 'Note:    tcpdump not found; emitting raw pcap-ng to stdout.'
}

if ($DryRun) {
    Write-Host '(dry-run: command not executed)'
    exit 0
}

Write-Host "Ran gadget $Gadget on node $Node (timeout ${Timeout}s)"

if ($tcpdumpAvail) {
    & kubectl @fullArgs | & tcpdump -nvr -
}
else {
    & kubectl @fullArgs
}
