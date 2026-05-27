"""Local-filesystem tree walker for the Folders page.

Replaces the ``FOLDERS.local`` mock in ``frontend/data.jsx`` with a real,
recursive tree of every project listed under ``[[projects]]`` in
``invisible.toml``.

Module exports (consumed by ``bin/invisible-dashboard`` in Plan INV-01-03):

- ``walk_all(project=None) -> list[dict]`` — one top-level node per project.
- ``walk_project(name) -> dict | None`` — single project's subtree, or None
  if the project isn't configured / its ``repo_path`` is unsafe.
- ``stream_diffs(handler, project=None) -> None`` — SSE watcher (implemented
  in Task 2).

Tree-node shape (matches ``frontend/data.jsx:104-130``):

    {
      "name": "<basename>",          # required
      "type": "folder" | "file",     # required
      "children": [<node>, ...]?,    # only for folders that have children
      "badge": "<string>"?,          # optional (git, size, truncation marker)
      "open": true?                  # optional pre-open hint for the UI
    }

Safety rails:

- ``IGNORE_NAMES`` skips noise directories (node_modules, .git, .venv, …) so
  the response stays under a few thousand nodes even on large repos.
- ``MAX_DEPTH`` caps recursion to defeat symlink loops and pathological
  trees.
- ``MAX_NODES_PER_DIR`` caps children per directory; the parent gets a
  ``badge="+N more"`` when truncation kicks in.
- ``_safe_resolve`` rejects configs that resolve to ``/`` or ``~/`` and
  enforces ``is_relative_to(root)`` on every descendant so a symlink can't
  walk us out of the repo.

``stream_diffs`` is implemented in Task 2 of this plan; it shares the
``IGNORE_NAMES`` + ``_safe_resolve`` plumbing defined here.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from config import home, load_toml  # noqa: F401  # home() reserved for future use

# ────────────────────────────────────────────────────────────────────────
# Limits & ignore list
# ────────────────────────────────────────────────────────────────────────

# Cap recursion. 12 levels is deep enough for any real-world repo layout
# while still bounding us against symlink loops or accidental cycles.
MAX_DEPTH = 12

# Cap children per directory. node_modules, .next/cache, target/ etc. can
# easily push tens of thousands of entries into the JSON response and lock
# up the React renderer. When we truncate, we set ``badge="+N more"`` on
# the parent so the UI can show the user that the tree was clipped.
MAX_NODES_PER_DIR = 2000

# Directories/files we never recurse into. Each entry explodes the tree
# without adding signal:
#   .git        — repo metadata, opaque
#   node_modules — npm dep tree, often >100k files
#   .venv/venv  — Python virtualenvs
#   __pycache__ — bytecode cache
#   .next/dist/build — JS framework build output
#   .DS_Store   — macOS noise
IGNORE_NAMES: set[str] = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".next",
    "dist",
    "build",
    ".DS_Store",
}


# ────────────────────────────────────────────────────────────────────────
# Path safety
# ────────────────────────────────────────────────────────────────────────


def _safe_resolve(repo_path_raw: str) -> Path | None:
    """Resolve a config-supplied repo_path to an absolute Path, or None.

    Returns None if:
    - The path is empty / not a string.
    - The path doesn't exist or isn't a directory.
    - The path resolves to ``/`` or the user's home root (a config of
      ``~/`` would walk the entire home dir — refuse it loudly).
    - The path contains a literal ``..`` component after resolve
      (``.resolve()`` already eats ``..`` but the explicit check documents
      the intent for future readers / future Pythons).
    """
    if not repo_path_raw or not isinstance(repo_path_raw, str):
        return None
    try:
        resolved = Path(os.path.expanduser(repo_path_raw)).resolve()
    except (OSError, RuntimeError):
        return None
    if not resolved.exists() or not resolved.is_dir():
        return None
    # Refuse filesystem roots and the user's home root.
    home_root = Path(os.path.expanduser("~")).resolve()
    if resolved == Path("/") or resolved == home_root:
        return None
    # Defensive: ``.resolve()`` has already collapsed ``..`` segments, so
    # this assert documents intent more than it catches anything real.
    if any(part == ".." for part in resolved.parts):
        return None
    return resolved


# ────────────────────────────────────────────────────────────────────────
# Walker
# ────────────────────────────────────────────────────────────────────────


def _walk(path: Path, root: Path, depth: int = 0) -> dict[str, Any]:
    """Recursively build a tree node rooted at ``path``.

    ``root`` is the project's resolved repo_path; we use it for the
    ``is_relative_to(root)`` containment check, which is the primary
    defense against symlinks pointing outside the repo.

    OSError (permission denied, broken symlink, vanished file) on a child
    is swallowed silently — we skip that child and keep walking.
    """
    node: dict[str, Any] = {
        "name": path.name or str(path),
        "type": "folder" if path.is_dir() else "file",
    }

    if not path.is_dir() or depth >= MAX_DEPTH:
        return node

    children: list[dict[str, Any]] = []
    try:
        raw_children = list(path.iterdir())
    except OSError:
        # Permission denied on a directory — leave it as a leaf folder.
        return node

    # Sort: directories first (alpha), then files (alpha). Matches the
    # visual order most file explorers use.
    raw_children.sort(key=lambda p: (0 if p.is_dir() else 1, p.name.lower()))

    truncated = 0
    for child in raw_children:
        if child.name in IGNORE_NAMES:
            continue
        # Containment guard: a symlink pointing outside the repo would
        # leak data via the walker. ``is_relative_to`` is Python 3.9+
        # and matches the project's stated 3.11+ floor.
        try:
            resolved_child = child.resolve()
            if not resolved_child.is_relative_to(root):
                continue
        except OSError:
            continue

        if len(children) >= MAX_NODES_PER_DIR:
            truncated += 1
            continue

        try:
            children.append(_walk(child, root, depth + 1))
        except OSError:
            continue

    if truncated:
        node["badge"] = f"+{truncated} more"

    if children:
        node["children"] = children

    return node


# ────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────


def walk_project(name: str) -> dict[str, Any] | None:
    """Return one project's tree, or None if missing/unsafe.

    The returned node uses the project's logical ``name`` (not the
    directory's basename) and sets ``open=True`` + ``badge="git"`` so the
    UI pre-opens the top-level node — matches the mock's behavior in
    ``frontend/data.jsx:110``.
    """
    if not name or not isinstance(name, str):
        return None

    cfg = load_toml()
    proj = next(
        (p for p in cfg.get("projects", []) if p.get("name") == name),
        None,
    )
    if proj is None:
        return None

    resolved = _safe_resolve(proj.get("repo_path", ""))
    if resolved is None:
        return None

    node = _walk(resolved, root=resolved, depth=0)
    # Override the basename with the logical project name and add the
    # top-level UI hints.
    node["name"] = name
    node["type"] = "folder"
    node["open"] = True
    node["badge"] = "git"
    return node


def walk_all(project: str | None = None) -> list[dict[str, Any]]:
    """Return all projects' trees, or just one if ``project`` is given.

    BLOCKER #2 contract (from checker pass): an unknown project name MUST
    return ``[]`` (empty list), never ``[None]``. The frontend TreeNode
    component will null-deref on ``node.name`` if a None leaks through.
    """
    if project is not None:
        result = walk_project(project)
        return [result] if result is not None else []

    cfg = load_toml()
    out: list[dict[str, Any]] = []
    for p in cfg.get("projects", []):
        name = p.get("name")
        if not name:
            continue
        node = walk_project(name)
        if node is not None:
            out.append(node)
    return out
