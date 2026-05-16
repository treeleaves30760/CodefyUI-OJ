#!/usr/bin/env bash
# Stage the sandbox build context (cdui repo + sandbox scripts) and build the image.
#
# Usage:
#   ./build_sandbox.sh                              # default cdui at ../../CodefyUI
#   CDUI_PATH=/abs/path/to/CodefyUI ./build_sandbox.sh
#   TAG=codefyui-oj-sandbox:dev ./build_sandbox.sh

set -euo pipefail

HERE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT="$( cd "$HERE/../.." && pwd )"
CDUI_PATH="${CDUI_PATH:-$ROOT/../CodefyUI}"
TAG="${TAG:-codefyui-oj-sandbox:latest}"

if [[ ! -d "$CDUI_PATH" ]]; then
    echo "cdui repo not found at $CDUI_PATH" >&2
    exit 1
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "Staging build context in $STAGE"
rsync -a --exclude='.git' --exclude='.venv' --exclude='node_modules' \
    --exclude='__pycache__' --exclude='frontend' --exclude='.worktrees' \
    "$CDUI_PATH/" "$STAGE/cdui/"
cp -r "$ROOT/backend/sandbox" "$STAGE/sandbox"
cp "$ROOT/backend/docker/sandbox.Dockerfile" "$STAGE/Dockerfile"

echo "Building $TAG"
docker build -t "$TAG" "$STAGE"
