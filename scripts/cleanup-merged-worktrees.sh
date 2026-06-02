#!/usr/bin/env bash
# cleanup-merged-worktrees.sh — R3 of the M1.5 recovery.
#
# Run AFTER PRs #7 (ws/tauri-shell re-PR) and #8 (ws/analytics-aggregator)
# have merged into main. Removes the now-stale worktrees + deletes the
# corresponding branches locally and on the remote.
#
# Idempotent: skips anything already cleaned up. Will refuse to delete
# anything with uncommitted changes (run `git status` in the worktree
# first if it complains).
#
# Usage:
#   ./scripts/cleanup-merged-worktrees.sh         # dry-run (default)
#   ./scripts/cleanup-merged-worktrees.sh --go    # actually do it

set -euo pipefail

DRY_RUN=true
if [[ "${1:-}" == "--go" ]]; then
  DRY_RUN=false
fi

cd "$(git rev-parse --show-toplevel)"
git fetch --all --prune >/dev/null

# All M1 workstreams that should be merged into main by now.
M1_WORKSTREAMS=(
  ai-bubble
  dashboard-wiring
  folders-3source
  terminals-pty
  tauri-shell           # via PR #7 (re-PR)
  analytics-aggregator  # via PR #8
)

echo "=== checking merge state of each M1 workstream ==="
ALL_MERGED=true
for ws in "${M1_WORKSTREAMS[@]}"; do
  if git rev-parse --quiet --verify "origin/ws/$ws" >/dev/null 2>&1; then
    # Branch exists on remote — is it fully merged into main?
    if git merge-base --is-ancestor "origin/ws/$ws" origin/main 2>/dev/null; then
      printf "  ✓ %-25s merged into main\n" "$ws"
    else
      printf "  ✗ %-25s NOT merged into main yet — skip cleanup\n" "$ws"
      ALL_MERGED=false
    fi
  else
    printf "  · %-25s no remote branch (likely already cleaned)\n" "$ws"
  fi
done

if ! $ALL_MERGED; then
  echo
  echo "Not all M1 workstreams are merged. Review the unmerged ones above"
  echo "and either merge their PRs first, or remove them from this script."
  exit 1
fi

echo
if $DRY_RUN; then
  echo "=== DRY RUN — would remove these worktrees + branches ==="
else
  echo "=== removing worktrees + branches ==="
fi

for ws in "${M1_WORKSTREAMS[@]}"; do
  worktree_path="$HOME/.invisible-ws/$ws"
  removed_anything=false

  if [[ -d "$worktree_path" ]]; then
    if $DRY_RUN; then
      echo "  would: git worktree remove $worktree_path"
    else
      # Refuse if uncommitted changes
      if [[ -n "$(git -C "$worktree_path" status --porcelain 2>/dev/null)" ]]; then
        echo "  ! $worktree_path has uncommitted changes — SKIPPING"
        continue
      fi
      git worktree remove "$worktree_path" 2>&1 | sed 's/^/    /'
      removed_anything=true
    fi
  fi

  if git rev-parse --quiet --verify "ws/$ws" >/dev/null 2>&1; then
    if $DRY_RUN; then
      echo "  would: git branch -D ws/$ws"
    else
      git branch -D "ws/$ws" 2>&1 | sed 's/^/    /'
      removed_anything=true
    fi
  fi

  if git rev-parse --quiet --verify "origin/ws/$ws" >/dev/null 2>&1; then
    if $DRY_RUN; then
      echo "  would: git push origin --delete ws/$ws"
    else
      git push origin --delete "ws/$ws" 2>&1 | sed 's/^/    /'
      removed_anything=true
    fi
  fi

  if ! $DRY_RUN && $removed_anything; then
    # Write a SHIPPED.md marker (matching the existing terminals-pty/SHIPPED.md convention)
    marker=".planning/workstreams/$ws/SHIPPED.md"
    if [[ ! -f "$marker" ]]; then
      cat > "$marker" <<MARKER_EOF
---
status: shipped
workstream: $ws
cleaned_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
cleaned_by: scripts/cleanup-merged-worktrees.sh
---

This workstream is merged into main. The branch and worktree have been
removed; this marker preserves the workstream's metadata in main's planning
tree.
MARKER_EOF
      git add "$marker"
    fi
  fi
done

if $DRY_RUN; then
  echo
  echo "Dry run complete. Re-run with --go to actually remove."
else
  echo
  if [[ -n "$(git status --porcelain .planning/)" ]]; then
    git -c user.name="Ace" -c user.email="avitpp977@gmail.com" commit -m "chore(planning): SHIPPED markers for merged M1 workstreams

Cleanup pass after PRs #7 (Tauri Phase 2) and #8 (analytics) merged.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
    ./scripts/update-changelog.py
    git add CHANGELOG.md
    git -c user.name="Ace" -c user.email="avitpp977@gmail.com" commit -m "docs: update CHANGELOG"
    git push origin main
  fi
  echo "Cleanup complete. Final worktree list:"
  git worktree list
fi
