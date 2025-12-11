#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="$1"
IMAGE_TAG="$2"
REGISTRY_URL="$3"

# Full image name with registry prefix
REGISTRY_IMAGE="${REGISTRY_URL}/${PROJECT_NAME}:${IMAGE_TAG}"

# Tag the local image with registry prefix
docker tag "${PROJECT_NAME}:${IMAGE_TAG}" "${REGISTRY_IMAGE}"

# Push to registry
docker push "${REGISTRY_IMAGE}"
