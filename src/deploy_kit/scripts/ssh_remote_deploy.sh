#!/usr/bin/env bash
set -euo pipefail

TARGET="$1"
PROJECT_NAME="$2"
IMAGE_TAG="$3"
PORT="$4"
HEALTHCHECK_PATH="$5"

ssh "$TARGET" bash << ENDSSH
set -euo pipefail

PROJECT_NAME="$PROJECT_NAME"
IMAGE_TAG="$IMAGE_TAG"
PORT="$PORT"
HEALTHCHECK_PATH="$HEALTHCHECK_PATH"
IMAGE_REF="\$PROJECT_NAME:\$IMAGE_TAG"

echo "Loading Docker image..."
cd /tmp
gunzip -c \$PROJECT_NAME-\$IMAGE_TAG.tar.gz | docker load

echo "Preparing docker-compose.yml..."
export PROJECT_NAME IMAGE_TAG PORT HEALTHCHECK_PATH IMAGE_REF
envsubst < docker-compose.prod.yml.template > docker-compose.yml

echo "Stopping and removing old containers..."
docker compose down || true
docker rm -f \$PROJECT_NAME 2>/dev/null || true

echo "Starting services..."
docker compose up -d

echo "Deployment successful!"
docker compose ps
ENDSSH
