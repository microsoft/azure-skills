#!/usr/bin/env bash
# generate-app-name.sh
# Generates a valid Azure App Service name from a folder name + 8 hex chars
# of randomness, suitable for `az webapp create -n <name>`.
#
# Rules enforced (matches Azure App Service naming requirements):
#   - lowercase a-z, 0-9, and hyphens only
#   - starts with a letter, ends with letter or digit
#   - total length <= 40 chars (slug truncated as needed)
#   - regex: ^[a-z][a-z0-9-]{1,38}[a-z0-9]$
#
# Usage:
#   ./generate-app-name.sh [folder-name]
#
# If folder-name is omitted, the current working directory's basename is used.
#
# Examples:
#   ./generate-app-name.sh                 # uses current folder
#   ./generate-app-name.sh my-flask-app    # → my-flask-app-a3f9c1d2

set -euo pipefail

INPUT="${1:-$(basename "$PWD")}"

# Lowercase, replace non-[a-z0-9] with '-', collapse repeats, trim hyphens.
SLUG=$(echo "$INPUT" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9]+/-/g; s/-+/-/g; s/^-//; s/-$//')

# Fallback if the slug ended up empty (e.g. folder was only symbols).
if [ -z "$SLUG" ]; then
    SLUG="app"
fi

# 8 hex chars from a fresh GUID (segment before the first '-').
if command -v uuidgen >/dev/null 2>&1; then
    SUFFIX=$(uuidgen | tr '[:upper:]' '[:lower:]' | cut -d- -f1 | cut -c1-8)
else
    # Fallback: /dev/urandom + xxd / od.
    SUFFIX=$(head -c 4 /dev/urandom | od -An -tx1 | tr -d ' \n' | cut -c1-8)
fi

# Reserve 9 chars for "-XXXXXXXX" so the total stays <= 40.
MAX_SLUG_LEN=31
if [ ${#SLUG} -gt $MAX_SLUG_LEN ]; then
    SLUG=$(echo "$SLUG" | cut -c1-$MAX_SLUG_LEN | sed -E 's/-$//')
fi

NAME="${SLUG}-${SUFFIX}"

# Ensure the name starts with a letter (Azure requirement). Prefix 'a' if not.
case "$NAME" in
    [a-z]*) ;;
    *) NAME="a${NAME}";;
esac

# Final length guard.
NAME=$(echo "$NAME" | cut -c1-40 | sed -E 's/-$//')

echo "$NAME"
