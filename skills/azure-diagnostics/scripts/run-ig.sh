#!/usr/bin/env bash
# run-ig.sh
# Runs an Inspektor Gadget (IG) trace on an AKS node via `kubectl debug`.
#
# Handles the mechanical, error-prone assembly of the IG invocation:
#   - resolves the target node from a pod (or takes a node directly)
#   - injects the pinned IG image + version
#   - applies the correct default --timeout for the gadget type
#   - adds the k8s namespace/pod/container filters
#   - handles the special `tcpdump` gadget (pcap-ng output piped to tcpdump)
#
# The privileged debug pod requires explicit user approval and appropriate RBAC.
# Use --dry-run to print the assembled command without running it.
#
# Usage:
#   ./run-ig.sh --gadget <name> (--pod <pod> --ns <namespace> | --node <node>) [options]
#
# Options:
#   --gadget <name>        Gadget to run, e.g. trace_dns, snapshot_socket, tcpdump (required)
#   --pod <pod>            Pod name; the node is resolved automatically
#   --ns <namespace>       Namespace of the pod (required with --pod)
#   --node <node>          Run directly against a node (node-wide scope)
#   --container <name>     Scope to a specific container
#   --timeout <seconds>    Override the gadget-type default timeout
#   --filter <arg>         Extra IG flag, repeatable (e.g. --filter --max-entries --filter 20)
#   --pf "<expr>"          tcpdump packet filter (tcpdump gadget only, e.g. "port 80")
#   --ig-version <tag>     Override the pinned IG image tag (default below)
#   --dry-run              Print the assembled command; do not execute
#
# Examples:
#   ./run-ig.sh --gadget trace_dns --pod web-0 --ns default
#   ./run-ig.sh --gadget snapshot_process --node aks-nodepool1-1234
#   ./run-ig.sh --gadget tcpdump --pod web-0 --ns default --pf "port 80"
#   ./run-ig.sh --gadget traceloop --pod web-0 --ns default --filter --syscall-filters --filter open,connect
#   ./run-ig.sh --gadget trace_dns --pod web-0 --ns default --dry-run

set -euo pipefail

# Pinned IG image tag. Bump this line (and run-ig.ps1) to update the IG version.
IG_VERSION="v0.51.0"
IG_IMAGE_REPO="mcr.microsoft.com/oss/v2/inspektor-gadget/ig"

GADGET=""
POD=""
NS=""
NODE=""
CONTAINER=""
TIMEOUT=""
PF=""
DRY_RUN="false"
EXTRA_FILTERS=()

usage() {
    # Print the leading comment block (from line 2) as help, stopping at the
    # first non-comment line so script code is never echoed.
    awk 'NR>1 && /^#/ { sub(/^# ?/, ""); print; next } NR>1 { exit }' "$0"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --gadget) GADGET="${2:?--gadget requires a value}"; shift 2;;
        --pod) POD="${2:?--pod requires a value}"; shift 2;;
        --ns|--namespace) NS="${2:?--ns requires a value}"; shift 2;;
        --node) NODE="${2:?--node requires a value}"; shift 2;;
        --container) CONTAINER="${2:?--container requires a value}"; shift 2;;
        --timeout) TIMEOUT="${2:?--timeout requires a value}"; shift 2;;
        --filter) EXTRA_FILTERS+=("${2:?--filter requires a value}"); shift 2;;
        --pf) PF="${2:?--pf requires a value}"; shift 2;;
        --ig-version) IG_VERSION="${2:?--ig-version requires a value}"; shift 2;;
        --dry-run) DRY_RUN="true"; shift;;
        -h|--help) usage; exit 0;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2;;
    esac
done

if [[ -z "$GADGET" ]]; then
    echo "Error: --gadget is required." >&2
    exit 2
fi

if [[ -z "$NODE" && -z "$POD" ]]; then
    echo "Error: provide either --node <node> or --pod <pod> --ns <namespace>." >&2
    exit 2
fi

if [[ -n "$POD" && -z "$NS" ]]; then
    echo "Error: --pod requires --ns <namespace>." >&2
    exit 2
fi

# Default timeout by gadget type, inferred from the gadget name prefix.
#   snapshot_* / top_*            -> 5s  (point-in-time / quick aggregate)
#   trace_* / profile_* / tcpdump -> 30s (streaming / sampling)
default_timeout() {
    case "$1" in
        snapshot_*|top_*) echo 5;;
        trace_*|profile_*|tcpdump) echo 30;;
        *) echo 30;;  # unknown gadget: use the safer streaming default
    esac
}

if [[ -z "$TIMEOUT" ]]; then
    TIMEOUT="$(default_timeout "$GADGET")"
fi

# Resolve the node name from the pod when not given directly.
if [[ -z "$NODE" ]]; then
    NODE="$(kubectl get pod "$POD" -n "$NS" -o jsonpath='{.spec.nodeName}')"
    if [[ -z "$NODE" ]]; then
        echo "Error: could not resolve node for pod '$POD' in namespace '$NS'." >&2
        exit 1
    fi
fi

IG_IMAGE="${IG_IMAGE_REPO}:${IG_VERSION}"

# Assemble the k8s scoping filters.
FILTERS=()
[[ -n "$NS" ]] && FILTERS+=(--k8s-namespace "$NS")
[[ -n "$POD" ]] && FILTERS+=(--k8s-podname "$POD")
[[ -n "$CONTAINER" ]] && FILTERS+=(--k8s-containername "$CONTAINER")

# Base kubectl debug invocation.
DEBUG=(kubectl debug --profile=sysadmin "node/${NODE}" --attach --quiet --image="$IG_IMAGE" --)

if [[ "$GADGET" == "tcpdump" ]]; then
    # tcpdump emits raw pcap-ng; pipe through tcpdump for readable output when available.
    IG_CMD=(ig run "tcpdump:${IG_VERSION}" -o pcap-ng "${FILTERS[@]}" --timeout "$TIMEOUT")
    [[ -n "$PF" ]] && IG_CMD+=(--pf "$PF")
    [[ ${#EXTRA_FILTERS[@]} -gt 0 ]] && IG_CMD+=("${EXTRA_FILTERS[@]}")
else
    if [[ -n "$PF" ]]; then
        echo "Error: --pf is only valid for the tcpdump gadget." >&2
        exit 2
    fi
    IG_CMD=(ig run "${GADGET}:${IG_VERSION}" -o json "${FILTERS[@]}" --timeout "$TIMEOUT")
    [[ ${#EXTRA_FILTERS[@]} -gt 0 ]] && IG_CMD+=("${EXTRA_FILTERS[@]}")
fi

FULL_CMD=("${DEBUG[@]}" "${IG_CMD[@]}")

# Pretty-print a shell-quoted version of the command for display.
quote_cmd() {
    local out=""
    local a
    for a in "$@"; do
        if [[ "$a" =~ [[:space:]] ]]; then
            out+="\"$a\" "
        else
            out+="$a "
        fi
    done
    echo "${out% }"
}

DISPLAY_CMD="$(quote_cmd "${FULL_CMD[@]}")"

# The tcpdump gadget is only piped through `tcpdump` when that binary is present.
# Reflect the real behavior in the displayed command so --dry-run does not mislead.
TCPDUMP_AVAIL="false"
if [[ "$GADGET" == "tcpdump" ]] && command -v tcpdump >/dev/null 2>&1; then
    TCPDUMP_AVAIL="true"
    DISPLAY_CMD="$DISPLAY_CMD | tcpdump -nvr -"
fi

echo "Gadget:  $GADGET" >&2
echo "Node:    $NODE" >&2
echo "Timeout: ${TIMEOUT}s" >&2
echo "Image:   $IG_IMAGE" >&2
echo "Command: $DISPLAY_CMD" >&2
if [[ "$GADGET" == "tcpdump" && "$TCPDUMP_AVAIL" == "false" ]]; then
    echo "Note:    tcpdump not found; emitting raw pcap-ng to stdout." >&2
fi

if [[ "$DRY_RUN" == "true" ]]; then
    echo "(dry-run: command not executed)" >&2
    exit 0
fi

echo "Ran gadget $GADGET on node $NODE (timeout ${TIMEOUT}s)" >&2

if [[ "$TCPDUMP_AVAIL" == "true" ]]; then
    "${FULL_CMD[@]}" | tcpdump -nvr -
else
    "${FULL_CMD[@]}"
fi
