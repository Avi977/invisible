"""Git-worktree helpers for the three-worktree-per-project layout.

Convention:
    <repo>/                       ← main checkout (you stay on main here)
    $INVISIBLE_HOME/worktrees/<project>/
        research/                 ← branch: research/<task-slug>
        feature/                  ← branch: feature/<task-slug>   (Codex commits here)
        review/                   ← branch: feature/<task-slug>   (Claude reads here, same SHA)
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


def slugify(s: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s[:maxlen] or "task"


def invisible_home() -> Path:
    return Path(os.path.expanduser(os.environ.get("INVISIBLE_HOME", "~/.invisible")))


def project_root(project: str) -> Path:
    return invisible_home() / "worktrees" / project


def create_worktrees(repo: Path, project: str, task: str) -> dict[str, Path]:
    """Create research/feature/review worktrees for `task` under invisible_home."""
    slug = slugify(task)
    root = project_root(project)
    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "research": root / "research",
        "feature":  root / "feature",
        "review":   root / "review",
    }
    branches = {
        "research": f"research/{slug}",
        "feature":  f"feature/{slug}",
        # review uses --detach because git won't allow two worktrees on the
        # same branch. orchestrator advances it via `git checkout <sha>`
        # after each codex commit.
    }
    for role, p in paths.items():
        if p.exists():
            continue
        if role == "review":
            # Pin to the feature branch's current HEAD as detached.
            cmd = ["git", "-C", str(repo), "worktree", "add", "--detach",
                   str(p), f"feature/{slug}"]
        else:
            existing = subprocess.run(
                ["git", "-C", str(repo), "branch", "--list", branches[role]],
                capture_output=True, text=True, check=False,
            ).stdout.strip()
            cmd = ["git", "-C", str(repo), "worktree", "add"]
            if not existing:
                cmd += ["-b", branches[role], str(p)]
            else:
                cmd += [str(p), branches[role]]
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            raise RuntimeError(f"worktree add failed for {role}: {r.stderr}")
    return paths


def list_project_worktrees(project: str) -> dict[str, Path]:
    root = project_root(project)
    return {
        role: root / role
        for role in ("research", "feature", "review")
        if (root / role).exists()
    }
