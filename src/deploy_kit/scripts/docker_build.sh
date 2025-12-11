#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="$1"
IMAGE_TAG="$2"
ARCHITECTURE="$3"

docker build \
    --platform "${ARCHITECTURE}" \
    -t "${PROJECT_NAME}:${IMAGE_TAG}" \
    -t "${PROJECT_NAME}:latest" \
    .
