#!/usr/bin/env bash
# test-messaging-connectivity.sh
# Probes reachability of an Azure Service Bus / Event Hubs namespace and prints a
# normalized per-check report: DNS resolution, HTTPS reachability, and TCP
# connectivity to the well-known messaging ports (AMQP 5671/5672, HTTPS 443, and
# — with --kafka — Event Hubs Kafka 9093).
#
# A blocked port is a valid diagnostic result, not a failure: the script exits 0
# unless the arguments are invalid. Choosing which namespace to test and
# diagnosing a blocked port (IP firewall vs. corporate proxy vs. NSG) require
# judgment and stay in the skill prose.
#
# Usage:
#   ./test-messaging-connectivity.sh <namespace> [--kafka]
#
# The namespace may be a full FQDN or a bare namespace name; when no dot is
# present, ".servicebus.windows.net" is appended automatically.
#
# Examples:
#   ./test-messaging-connectivity.sh contoso                         # contoso.servicebus.windows.net
#   ./test-messaging-connectivity.sh contoso.servicebus.windows.net  # Service Bus / Event Hubs (AMQP + HTTPS)
#   ./test-messaging-connectivity.sh contoso --kafka                 # also probe Event Hubs Kafka port 9093

set -uo pipefail

INCLUDE_KAFKA=0
NAMESPACE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --kafka)
            INCLUDE_KAFKA=1
            ;;
        -h|--help)
            grep '^#' "$0" | grep -v '^#!' | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        --*)
            echo "Unknown option: $1" >&2
            echo "Usage: $0 <namespace> [--kafka]" >&2
            exit 2
            ;;
        *)
            if [ -z "$NAMESPACE" ]; then
                NAMESPACE="$1"
            else
                echo "Unexpected argument: $1" >&2
                echo "Usage: $0 <namespace> [--kafka]" >&2
                exit 2
            fi
            ;;
    esac
    shift
done

if [ -z "$NAMESPACE" ]; then
    echo "Usage: $0 <namespace> [--kafka]" >&2
    exit 2
fi

# Accept a bare namespace name or a full FQDN.
FQDN="$NAMESPACE"
case "$FQDN" in
    *.*) : ;;               # already looks like an FQDN
    *)   FQDN="${FQDN}.servicebus.windows.net" ;;
esac

echo "Testing messaging connectivity for: $FQDN"
echo ""

# ── DNS resolution ────────────────────────────────────────────────────────────
resolve_ip() {
    local host="$1" ip=""
    if command -v getent >/dev/null 2>&1; then
        ip=$(getent ahosts "$host" 2>/dev/null | awk '{print $1}' | head -n1)
    fi
    if [ -z "$ip" ] && command -v host >/dev/null 2>&1; then
        ip=$(host "$host" 2>/dev/null | awk '/has address/ {print $NF; exit}')
    fi
    if [ -z "$ip" ] && command -v python3 >/dev/null 2>&1; then
        ip=$(python3 -c "import socket,sys; print(socket.gethostbyname(sys.argv[1]))" "$host" 2>/dev/null)
    fi
    if [ -z "$ip" ] && command -v nslookup >/dev/null 2>&1; then
        # Skip the leading "Server/Address" block; the answer's address follows
        # the "Name:" line.
        ip=$(nslookup "$host" 2>/dev/null | awk '/^Name:/ {seen=1; next} seen && /^Address/ {print $NF; exit}')
    fi
    printf '%s' "$ip"
}

RESOLVED_IP="$(resolve_ip "$FQDN")"
if [ -n "$RESOLVED_IP" ]; then
    DNS_RESULT="resolved ($RESOLVED_IP)"
else
    DNS_RESULT="NOT RESOLVED"
fi

# ── TCP port probe ────────────────────────────────────────────────────────────
probe_tcp() {
    local host="$1" port="$2"
    if command -v nc >/dev/null 2>&1; then
        if nc -z -w 5 "$host" "$port" >/dev/null 2>&1; then
            return 0
        fi
        return 1
    fi
    # Fallback: bash /dev/tcp with a background timeout.
    ( exec 3<>"/dev/tcp/$host/$port" ) >/dev/null 2>&1 &
    local pid=$!
    local waited=0
    while kill -0 "$pid" 2>/dev/null; do
        sleep 1
        waited=$((waited + 1))
        if [ "$waited" -ge 5 ]; then
            kill "$pid" 2>/dev/null
            wait "$pid" 2>/dev/null
            return 1
        fi
    done
    wait "$pid"
    return $?
}

port_result() {
    if probe_tcp "$FQDN" "$1"; then
        echo "reachable"
    else
        echo "BLOCKED"
    fi
}

# ── HTTPS reachability ────────────────────────────────────────────────────────
# On success the namespace returns an Atom feed or HTTP 401 — either proves the
# endpoint is reachable. A connection failure (curl exit != 0) means blocked.
https_result() {
    if ! command -v curl >/dev/null 2>&1; then
        # No curl: fall back to a plain TCP probe of 443.
        if probe_tcp "$FQDN" 443; then
            echo "reachable (TCP 443 open; curl unavailable for HTTP check)"
        else
            echo "BLOCKED"
        fi
        return
    fi
    local code
    code=$(curl -s -o /dev/null -m 15 -w '%{http_code}' "https://$FQDN/" 2>/dev/null)
    local rc=$?
    if [ "$rc" -eq 0 ] && [ -n "$code" ] && [ "$code" != "000" ]; then
        echo "reachable (HTTP $code)"
    else
        echo "BLOCKED (curl exit $rc)"
    fi
}

DNS_OK=0; [ -n "$RESOLVED_IP" ] && DNS_OK=1

if [ "$DNS_OK" -eq 1 ]; then
    HTTPS_RESULT="$(https_result)"
    P443="$(port_result 443)"
    P5671="$(port_result 5671)"
    P5672="$(port_result 5672)"
    if [ "$INCLUDE_KAFKA" -eq 1 ]; then
        P9093="$(port_result 9093)"
    fi
else
    HTTPS_RESULT="skipped (DNS failed)"
    P443="skipped (DNS failed)"
    P5671="skipped (DNS failed)"
    P5672="skipped (DNS failed)"
    P9093="skipped (DNS failed)"
fi

# ── Report ────────────────────────────────────────────────────────────────────
printf '%-28s %-10s %s\n' "Check" "Port" "Result"
printf '%-28s %-10s %s\n' "-----" "----" "------"
printf '%-28s %-10s %s\n' "DNS resolution"        "-"    "$DNS_RESULT"
printf '%-28s %-10s %s\n' "HTTPS reachability"    "443"  "$HTTPS_RESULT"
printf '%-28s %-10s %s\n' "AMQP over TLS"         "5671" "$P5671"
printf '%-28s %-10s %s\n' "AMQP"                  "5672" "$P5672"
printf '%-28s %-10s %s\n' "HTTPS / WebSockets"    "443"  "$P443"
if [ "$INCLUDE_KAFKA" -eq 1 ]; then
    printf '%-28s %-10s %s\n' "Event Hubs Kafka"  "9093" "$P9093"
fi

echo ""
if [ "$DNS_OK" -eq 0 ]; then
    echo "Summary: could not resolve $FQDN. Check the namespace name and DNS/private-endpoint configuration before testing ports."
else
    echo "Summary: DNS resolved to $RESOLVED_IP. 'reachable' ports accept TCP connections; any 'BLOCKED' port points to an IP firewall, NSG, corporate proxy, or private-endpoint restriction to investigate. Port 443 (WebSockets) can be used as a fallback when AMQP ports 5671/5672 are blocked."
fi
