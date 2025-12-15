#!/usr/bin/env bash
set -euo pipefail

# Check if remote tarball exists and return its SHA256 hash
# Returns empty string if file doesn't exist

TARGET="$1"
TARBALL_NAME="$2"

# Use single quotes to prevent remote shell expansion, splice in the variable safely
ssh "$TARGET" 'if [ -f "/tmp/'"$TARBALL_NAME"'" ]; then sha256sum "/tmp/'"$TARBALL_NAME"'" | cut -d" " -f1; fi'
