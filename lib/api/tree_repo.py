"""GitHub tree walker for the Folders page (gh-api backed, 60s in-process cache).

Replaces the ``FOLDERS.repo`` mock in ``frontend/data.jsx`` with a real
tree of every project's GitHub repository, derived via the ``gh`` CLI.

Module exports (consumed by ``bin/invisible-dashboard`` in Plan INV-01-03):

- ``walk_all(project=None) -> list[dict]`` — one top-level node per project,
  keyed by ``@<owner>/<repo>``. Returns ``[]`` if ``project`` is provided but
  not found in invisible.toml — never ``[None]`` (cross-walker BLOCKER #2
  contract; mirrors ``tree_local.walk_all``).
- ``clear_cache() -> None`` — empty the in-process TTL cache. Used by tests
  and by Plan 03's "force refresh" path.

Cache:

The ``gh api`` endpoint we call (``repos/<owner>/<repo>/git/trees/HEAD?recursive=1``)
costs one rate-limit unit per call. Authenticated requests get 5000/hr,
unauthenticated 60/hr. A 60-second in-process TTL cache absorbs the case
where the user mashes refresh in the UI; the trade-off is a stale tree
for up to one minute after a push (acceptable for v1).

GitHub truncates trees at 100k entries (``truncated: true`` flag in the
response). We log to stderr and continue with whatever was returned; a
``truncated`` marker on the frontend is a future enhancement.

Tree-node shape (matches ``frontend/data.jsx:151-167``):

    Top-level: {name: "@owner/repo", type: "folder", badge: "main",
                 open: true, children: [...]}
    Children:  {name: "<basename>", type: "folder" | "file",
                  children?: [<node>, ...]}

Security:

- All subprocess calls use a list ``argv`` with ``shell=False`` (the default).
- The owner and repo strings derived from ``git remote get-url origin`` are
  each re-validated against ``^[A-Za-z0-9][A-Za-z0-9._-]*$`` before being
  interpolated into the gh API path. This is the T-INV01-08 mitigation in
  the plan's threat register.
- A bogus or hostile ``repo_path`` in invisible.toml that points at a repo
  with a weird ``origin`` URL will cause ``_derive_owner_repo`` to return
  ``None``; that project is silently skipped rather than crashing the walker.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from config import load_toml

# ────────────────────────────────────────────────────────────────────────
# Cache
# ────────────────────────────────────────────────────────────────────────

# (owner/repo) → (expires_at_epoch, tree_node_list). One entry per repo.
# Module-level state is fine because the daemon is a single process; the
# cache is per-process and resets on restart.
_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_CACHE_TTL_S = 60


def clear_cache() -> None:
    """Empty the in-process TTL cache.

    Used by tests, and by any future "force refresh" UI control. Safe to
    call concurrently — dict.clear() is atomic in CPython under the GIL.
    """
    _CACHE.clear()


# ────────────────────────────────────────────────────────────────────────
# Validation
# ────────────────────────────────────────────────────────────────────────

# GitHub owner and repo names allow [A-Za-z0-9._-] with the constraint
# that they can't start with a dot or hyphen in practice. We enforce a
# stricter prefix character class to defend against ``..``-style relative
# paths sneaking into the gh API URL. This is the T-INV01-08 mitigation.
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

# Match both SSH and HTTPS remote URLs. The trailing ``[^/.]+`` allows
# dots and slashes only in the owner segment, not the repo segment, so
# ``foo/bar.git`` parses as owner=foo, repo=bar. Trailing ``.git`` (and
# any further path) is implicitly dropped by the ``[^/.]+`` greediness.
_REMOTE_RE = re.compile(
    r"(?:git@github\.com:|https?://github\.com/)([^/]+)/([^/.]+)"
)


# ────────────────────────────────────────────────────────────────────────
# Owner/repo derivation
# ────────────────────────────────────────────────────────────────────────


def _derive_owner_repo(repo_path: str) -> tuple[str, str] | None:
    """Resolve a local repo path to its GitHub (owner, repo) tuple.

    Returns ``None`` on any failure: missing dir, not-a-repo, no origin,
    non-GitHub origin URL, or a name that fails the security regex.

    Implementation note: ``git -C <path> remote get-url origin`` works
    even from outside the repo (no chdir needed) and is the canonical way
    to read a remote URL non-interactively.
    """
    if not repo_path or not isinstance(repo_path, str):
        return None

    path = Path(os.path.expanduser(repo_path))
    if not path.is_dir():
        return None

    try:
        # subprocess.run with a list argv and shell=False (the default) —
        # the path string is passed as a single argument and cannot be
        # interpreted as a shell command.
        result = subprocess.run(
            ["git", "-C", str(path), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        sys.stderr.write(f"[tree_repo] git remote get-url failed for {path}: {exc}\n")
        return None

    if result.returncode != 0 or not result.stdout.strip():
        return None

    url = result.stdout.strip()
    m = _REMOTE_RE.match(url)
    if not m:
        return None

    owner, repo = m.group(1), m.group(2)

    # T-INV01-08 security gate: re-validate the parsed strings before they
    # reach the gh API argv. The regex above already constrains the
    # alphabet, but a defense-in-depth check here means any future tweak
    # to ``_REMOTE_RE`` can't accidentally widen the trust boundary.
    if not _NAME_RE.match(owner) or not _NAME_RE.match(repo):
        return None

    return owner, repo


# ────────────────────────────────────────────────────────────────────────
# Tree fetching
# ────────────────────────────────────────────────────────────────────────


def _insert(node_list: list[dict[str, Any]], parts: list[str], kind: str) -> None:
    """Insert a single ``parts`` path into the nested tree under ``node_list``.

    ``kind`` is the gh API's ``type`` field: ``"blob"`` → file leaf,
    ``"tree"`` → folder. For intermediate path segments (every part except
    the last), we always create a folder node, even if the original gh
    entry didn't list the intermediate as a tree separately (it usually
    does, but we don't rely on insertion order).
    """
    if not parts:
        return
    head, *rest = parts

    # Find or create the node for this segment at the current level.
    existing = next((n for n in node_list if n.get("name") == head), None)
    if existing is None:
        if rest:
            # Intermediate segment — must be a folder.
            existing = {"name": head, "type": "folder", "children": []}
        else:
            # Leaf segment — type comes from the gh entry.
            existing = (
                {"name": head, "type": "file"}
                if kind == "blob"
                else {"name": head, "type": "folder", "children": []}
            )
        node_list.append(existing)
    else:
        # If the node exists as a file but we're trying to descend into
        # it, the gh data is malformed; we tolerate it by upgrading to a
        # folder (rare; the gh API doesn't normally do this).
        if rest and existing.get("type") == "file":
            existing["type"] = "folder"
            existing["children"] = []

    if rest:
        # Recurse into children. ``children`` always exists for folders we
        # created above; defensive ``setdefault`` here in case ``existing``
        # was a folder from a previous fetch that had no children yet.
        children = existing.setdefault("children", [])
        _insert(children, rest, kind)


def _fetch_tree(owner: str, repo: str) -> list[dict[str, Any]]:
    """Fetch ``owner/repo``'s recursive tree from GitHub, with 60s caching.

    Returns the nested children list (not wrapped in a top-level node —
    that's ``_walk_one``'s job). Returns ``[]`` on any failure so the
    caller can still produce a valid (empty) tree response.
    """
    key = f"{owner}/{repo}"
    now = time.time()
    cached = _CACHE.get(key)
    if cached is not None and cached[0] > now:
        return cached[1]

    try:
        # Argv list, shell=False (default). The ``owner`` and ``repo``
        # strings have been validated by ``_derive_owner_repo`` against
        # ``_NAME_RE``; the f-string interpolates them into a single
        # argv element, not into a shell command line.
        result = subprocess.run(
            ["gh", "api", f"repos/{owner}/{repo}/git/trees/HEAD?recursive=1"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        sys.stderr.write(f"[tree_repo] gh api failed for {key}: {exc}\n")
        return []

    if result.returncode != 0:
        # gh prints the API error body to stderr; surface it once.
        err = (result.stderr or "").strip()
        sys.stderr.write(f"[tree_repo] gh api {key} returned {result.returncode}: {err}\n")
        return []

    try:
        import json as _json  # local import — tomllib is std-lib and json too
        payload = _json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        sys.stderr.write(f"[tree_repo] gh api {key} returned invalid JSON: {exc}\n")
        return []

    if payload.get("truncated"):
        sys.stderr.write(
            f"[tree_repo] gh api {key} returned truncated tree "
            f"(>100k entries); rendering partial result\n"
        )

    entries = payload.get("tree", [])
    tree: list[dict[str, Any]] = []
    for entry in entries:
        path = entry.get("path", "")
        kind = entry.get("type", "")
        if not path or kind not in ("blob", "tree"):
            continue
        parts = path.split("/")
        _insert(tree, parts, kind)

    _CACHE[key] = (now + _CACHE_TTL_S, tree)
    return tree


# ────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────


def _walk_one(p: dict[str, Any]) -> dict[str, Any] | None:
    """Build one top-level project node, or None if the project can't be resolved.

    Shared helper between the single-project and all-projects branches of
    ``walk_all`` so the BLOCKER #2 filter (no ``[None]`` leakage) is
    enforced in exactly one place.
    """
    repo_path = p.get("repo_path", "")
    owner_repo = _derive_owner_repo(repo_path)
    if owner_repo is None:
        return None
    owner, repo = owner_repo
    subtree = _fetch_tree(owner, repo)
    return {
        "name": f"@{owner}/{repo}",
        "type": "folder",
        "badge": "main",
        "open": True,
        "children": subtree,
    }


def walk_all(project: str | None = None) -> list[dict[str, Any]]:
    """Return the GitHub tree for all projects, or just one.

    BLOCKER #2 contract (cross-walker consistency): an unknown ``project``
    MUST return ``[]``, never ``[None]``. The single-project branch
    explicitly filters out a None result from ``_walk_one``.
    """
    cfg = load_toml()
    projects = cfg.get("projects", [])

    if project is not None:
        # Find the named project. If missing OR if _walk_one can't resolve
        # it (e.g. repo_path missing/invalid, no GitHub origin, etc.),
        # return [] — never [None].
        matched = next((p for p in projects if p.get("name") == project), None)
        if matched is None:
            return []
        node = _walk_one(matched)
        return [node] if node is not None else []

    # All projects: drop any project whose _walk_one returned None.
    out: list[dict[str, Any]] = []
    for p in projects:
        if not p.get("name"):
            continue
        node = _walk_one(p)
        if node is not None:
            out.append(node)
    return out
