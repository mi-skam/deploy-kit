#!/usr/bin/env bash
set -euo pipefail

TARGET="$1"
TARBALL="$2"
TEMPLATE="$3"
ENV_FILE="$4"
SKIP_TARBALL="${5:-false}"

if [ "$SKIP_TARBALL" = "true" ]; then
    echo "Skipping tarball transfer (already exists with matching hash)"
else
    echo "Transferring tarball..."
    scp "$TARBALL" "$TARGET:/tmp/"
fi

echo "Transferring compose template..."
scp "$TEMPLATE" "$TARGET:/tmp/docker-compose.prod.yml.template"

if [ -n "$ENV_FILE" ]; then
    echo "Transferring env file..."
    scp "$ENV_FILE" "$TARGET:/tmp/.env"
else
    echo "No env file to transfer (deploying without environment variables)"
fi
