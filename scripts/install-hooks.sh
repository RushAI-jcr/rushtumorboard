#!/usr/bin/env bash
# Install git hooks for this repository.
# Run once after cloning: bash scripts/install-hooks.sh

set -euo pipefail

HOOKS_DIR="$(git rev-parse --git-dir)/hooks"
SCRIPTS_HOOKS_DIR="$(git rev-parse --show-toplevel)/scripts/git-hooks"

for hook in "$SCRIPTS_HOOKS_DIR"/*; do
    hook_name=$(basename "$hook")
    target="$HOOKS_DIR/$hook_name"
    cp "$hook" "$target"
    chmod +x "$target"
    echo "Installed: $target"
done

echo "Git hooks installed."
