#!/usr/bin/env bash
# retry-az-create.sh
# Wraps the idempotent `(az ... show ...) || (az ... create ...)` pair with
# silent retries against transient ARM frontend errors (connection resets,
# 429/502/503/504, timeouts).
#
# Usage:
#   ./retry-az-create.sh "<show-command>" "<create-command>"
#
# Both commands are passed as single shell-quoted strings. The script:
#   - runs `show` first (short-circuits any partially-succeeded prior attempt
#     and avoids false NameAlreadyExists / Conflict errors);
#   - if `show` fails, runs `create`;
#   - on transient failure, retries up to 2 times (3 attempts total) with
#     5s then 15s backoff;
#   - on non-transient failure, surfaces the original error and exits 1.
#
# Examples:
#   ./retry-az-create.sh \
#       "az group show -n my-rg --only-show-errors" \
#       "az group create -n my-rg -l eastus2"
#
#   ./retry-az-create.sh \
#       "az appservice plan show -n my-plan -g my-rg --only-show-errors" \
#       "az appservice plan create -n my-plan -g my-rg --is-linux --sku P0v3 -l eastus2"

set -uo pipefail

SHOW_CMD="${1:?Usage: $0 \"<show-command>\" \"<create-command>\"}"
CREATE_CMD="${2:?Usage: $0 \"<show-command>\" \"<create-command>\"}"

TRANSIENT='Connection reset|Connection aborted|ConnectionError|Read timed out|BadGatewayConnection|ServiceUnavailable|Max retries exceeded|TooManyRequests|\b429\b|\b50[234]\b'

for attempt in 1 2 3; do
    # Run show silently; on failure, run create and capture stderr.
    if err=$({ eval "$SHOW_CMD -o none 2>/dev/null" || eval "$CREATE_CMD -o none"; } 2>&1); then
        exit 0
    fi

    if ! echo "$err" | grep -qE "$TRANSIENT"; then
        echo "$err" >&2
        exit 1
    fi

    if [ "$attempt" -eq 3 ]; then
        echo "$err" >&2
        echo "ARM frontend is returning transient errors — please retry in a few minutes." >&2
        exit 1
    fi

    sleep "$([ "$attempt" -eq 1 ] && echo 5 || echo 15)"
done
