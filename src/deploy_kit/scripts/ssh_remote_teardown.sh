#!/usr/bin/env bash
set -euo pipefail

SSH_TARGET=$1
PROJECT_NAME=$2
IMAGE_TAG=$3
KEEP_IMAGES=$4  # "true" or "false"
KEEP_FILES=$5   # "true" or "false"

# Execute teardown commands on remote server
ssh "$SSH_TARGET" bash <<EOF
set -euo pipefail

cd /tmp/

# Stop and remove containers
if [ -f docker-compose.yml ]; then
    docker compose down --remove-orphans
fi

# Remove container forcefully (in case compose.yml missing)
docker rm -f "$PROJECT_NAME" 2>/dev/null || true

# Remove Docker image (unless --keep-images)
if [ "$KEEP_IMAGES" = "false" ]; then
    docker rmi "$PROJECT_NAME:$IMAGE_TAG" 2>/dev/null || true
    docker rmi "$PROJECT_NAME:latest" 2>/dev/null || true
fi

# Remove transferred files (unless --keep-files)
if [ "$KEEP_FILES" = "false" ]; then
    rm -f "$PROJECT_NAME-$IMAGE_TAG.tar.gz"
    rm -f docker-compose.prod.yml.template
    rm -f docker-compose.yml
    rm -f .env
fi
EOF
