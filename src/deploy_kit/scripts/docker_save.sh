#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="$1"
IMAGE_TAG="$2"
TARBALL="$3"

docker save "${PROJECT_NAME}:${IMAGE_TAG}" | gzip > "$TARBALL"
