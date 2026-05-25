#!/usr/bin/env bash
# Install invisible's git hooks. Idempotent.
#
# We use `git config core.hooksPath .githooks` so hooks are versioned with
# the repo (no symlink dance, no manual copy step).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -d .git ]]; then
  echo "[install-hooks] not a git repo — run 'git init' first" >&2
  exit 1
fi

git config core.hooksPath .githooks
chmod +x .githooks/*

echo "[install-hooks] hooksPath set to .githooks"
echo "[install-hooks] installed hooks:"
ls -1 .githooks | sed 's/^/  - /'
