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

import json
import os
import queue
import sys
import time
from pathlib import Path
from typing import Any

from config import home, load_toml  # noqa: F401  # home() reserved for future use

# ────────────────────────────────────────────────────────────────────────
# Watchdog (optional)
# ────────────────────────────────────────────────────────────────────────
#
# ``watchdog`` is not in any project dependency manifest yet. ``pip show
# watchdog`` may succeed on the dev machine but downstream installs cannot
# rely on it — so we guard the import and ship a polling fallback in
# ``stream_diffs`` that walks ``_collect_paths`` on a 2s tick. The daemon
# must keep working when watchdog is missing; the try/except shield is the
# T-INV01-05 mitigation in the threat register.
try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    HAVE_WATCHDOG = True
except ImportError:  # pragma: no cover — exercised by polling-path tests
    HAVE_WATCHDOG = False
    FileSystemEventHandler = object  # type: ignore[misc,assignment]
    Observer = None  # type: ignore[assignment]

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


# ────────────────────────────────────────────────────────────────────────
# SSE diff watcher
# ────────────────────────────────────────────────────────────────────────


# Limit how many added/removed events we emit per polling cycle. Without a
# cap, the first cycle after a fresh ``npm install`` could push tens of
# thousands of paths to the browser in one burst and stall the renderer.
_MAX_DIFF_BATCH = 200

# Cycle period for the polling path. 2s keeps the "5-second UI update"
# success criterion comfortable while staying cheap on CPU.
_POLL_INTERVAL_S = 2.0

# Keepalive period for both paths. Send a SSE comment (``: keepalive\n\n``)
# every N seconds so any intervening proxy doesn't drop the connection.
_KEEPALIVE_S = 15.0


def _collect_paths(root: Path) -> set[str]:
    """Return the set of paths (relative to ``root``) under ``root``.

    Skips ``IGNORE_NAMES`` and follows no symlinks (``followlinks=False``).
    Used both as the initial snapshot for the watchdog branch and as the
    per-cycle snapshot for the polling fallback.
    """
    out: set[str] = set()
    try:
        root_str = str(root)
        for dirpath, dirnames, filenames in os.walk(root_str, followlinks=False):
            # Prune ignored directories in-place so os.walk doesn't recurse
            # into them.
            dirnames[:] = [d for d in dirnames if d not in IGNORE_NAMES]
            try:
                rel_dir = os.path.relpath(dirpath, root_str)
            except ValueError:
                continue
            if rel_dir != ".":
                out.add(rel_dir)
            for fname in filenames:
                if fname in IGNORE_NAMES:
                    continue
                if rel_dir == ".":
                    out.add(fname)
                else:
                    out.add(os.path.join(rel_dir, fname))
    except OSError:
        # Permission denied / vanished root — return whatever we got.
        pass
    return out


def _format_sse(event_type: str, payload: dict[str, Any]) -> bytes:
    """Format a single SSE event frame.

    SSE chunks must end with a blank line (two newlines). ``event:`` is
    optional but lets the client's EventSource dispatch a different handler
    per type — we use ``snapshot``, ``diff``, ``error``.
    """
    body = json.dumps(payload, separators=(",", ":"))
    return f"event: {event_type}\ndata: {body}\n\n".encode("utf-8")


def _keepalive_bytes() -> bytes:
    """SSE comment frame; clients ignore it but proxies see traffic."""
    return b": keepalive\n\n"


def _send_sse_headers(handler: Any) -> None:
    """Emit the SSE response header block.

    The ``Access-Control-Allow-Origin: *`` header is REQUIRED — the
    frontend runs on :8090 and the dashboard on :8765, so EventSource
    requests are cross-origin. Without this header the browser silently
    blocks the connection. This mirrors the BLOCKER #1 fix that Plan 03
    adds to ``_send_json`` for the regular JSON endpoints.

    ``X-Accel-Buffering: no`` defeats nginx's response buffering for any
    future proxy in front of the daemon.
    """
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Connection", "keep-alive")
    handler.send_header("X-Accel-Buffering", "no")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()


def _resolve_watched(project: str | None) -> list[tuple[str, Path]]:
    """Resolve ``[[projects]]`` entries to ``(name, root_path)`` pairs.

    Honors the ``project`` filter, drops anything that fails the
    ``_safe_resolve`` containment check.
    """
    cfg = load_toml()
    pairs: list[tuple[str, Path]] = []
    for p in cfg.get("projects", []):
        name = p.get("name")
        if not name:
            continue
        if project is not None and name != project:
            continue
        resolved = _safe_resolve(p.get("repo_path", ""))
        if resolved is None:
            continue
        pairs.append((name, resolved))
    return pairs


def _path_passes_ignore(rel: str) -> bool:
    """Return True if *no* component of a relative path is in IGNORE_NAMES."""
    parts = rel.replace("\\", "/").split("/")
    return not any(part in IGNORE_NAMES for part in parts)


def stream_diffs(handler: Any, project: str | None = None) -> None:
    """SSE watcher loop — runs until the client disconnects.

    Caller is responsible for auth (``bin/invisible-dashboard``'s
    ``do_GET`` calls ``_auth_ok()`` before invoking this). The function
    blocks the worker thread; the daemon is ``ThreadingHTTPServer`` so
    that's fine. Uses watchdog when available, falls back to a 2s
    polling diff otherwise. Always emits
    ``Access-Control-Allow-Origin: *`` so the cross-port (8090 → 8765)
    browser EventSource can subscribe.

    Event types emitted:
    - ``snapshot``: payload ``{"tree": [...]}`` — initial state.
    - ``diff``: payload ``{"kind": "added"|"removed"|"modified", "project": name, "path": str}``.
    - ``error``: payload ``{"error": "<msg>"}`` — when no valid project paths.

    Required response headers (emitted via ``_send_sse_headers``):
    ``Content-Type: text/event-stream``, ``Cache-Control: no-store``,
    ``Connection: keep-alive``, ``X-Accel-Buffering: no``, and
    ``Access-Control-Allow-Origin: *`` (BLOCKER #1 — required so the
    browser EventSource on :8090 can subscribe to the daemon on :8765).
    """
    _send_sse_headers(handler)

    watched = _resolve_watched(project)
    if not watched:
        try:
            handler.wfile.write(
                _format_sse("error", {"error": "no valid project paths"})
            )
            handler.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        return

    # Initial snapshot so the client renders once before diffs start
    # streaming. Avoids a race where a file gets added/removed during the
    # SSE handshake and the client misses it.
    try:
        handler.wfile.write(
            _format_sse("snapshot", {"tree": walk_all(project)})
        )
        handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        return

    if HAVE_WATCHDOG and Observer is not None:
        _stream_diffs_watchdog(handler, watched)
    else:
        _stream_diffs_polling(handler, watched)


def _stream_diffs_watchdog(
    handler: Any, watched: list[tuple[str, Path]]
) -> None:
    """Watchdog-backed diff loop."""
    q: queue.Queue[dict[str, Any]] = queue.Queue()

    class _Handler(FileSystemEventHandler):  # type: ignore[misc]
        def __init__(self, project_name: str, root: Path) -> None:
            self._project = project_name
            self._root = root

        def _emit(self, kind: str, src_path: str) -> None:
            try:
                p = Path(src_path).resolve()
                # Symlink-escape guard, same as the walker.
                if not p.is_relative_to(self._root):
                    return
                rel = str(p.relative_to(self._root))
            except (OSError, ValueError):
                return
            if not _path_passes_ignore(rel):
                return
            q.put({"kind": kind, "project": self._project, "path": rel})

        def on_created(self, event: Any) -> None:
            self._emit("added", event.src_path)

        def on_deleted(self, event: Any) -> None:
            self._emit("removed", event.src_path)

        def on_modified(self, event: Any) -> None:
            # Only emit modified for files; directory mtime changes are
            # noise (touched on every child write).
            if getattr(event, "is_directory", False):
                return
            self._emit("modified", event.src_path)

    observer = Observer()
    for name, root in watched:
        try:
            observer.schedule(_Handler(name, root), str(root), recursive=True)
        except OSError:
            continue
    observer.start()

    last_keepalive = time.monotonic()
    try:
        while True:
            try:
                evt = q.get(timeout=_KEEPALIVE_S)
            except queue.Empty:
                evt = None

            try:
                if evt is not None:
                    handler.wfile.write(_format_sse("diff", evt))
                    handler.wfile.flush()

                now = time.monotonic()
                if now - last_keepalive >= _KEEPALIVE_S:
                    handler.wfile.write(_keepalive_bytes())
                    handler.wfile.flush()
                    last_keepalive = now
            except (BrokenPipeError, ConnectionResetError, OSError):
                return
    finally:
        try:
            observer.stop()
            observer.join(timeout=2)
        except Exception:  # noqa: BLE001 — best-effort cleanup
            pass


def _stream_diffs_polling(
    handler: Any, watched: list[tuple[str, Path]]
) -> None:
    """Polling fallback when watchdog is unavailable."""
    snapshot: dict[str, set[str]] = {
        name: _collect_paths(root) for name, root in watched
    }

    last_keepalive = time.monotonic()
    while True:
        time.sleep(_POLL_INTERVAL_S)

        events: list[dict[str, Any]] = []
        for name, root in watched:
            current = _collect_paths(root)
            prev = snapshot.get(name, set())
            added = current - prev
            removed = prev - current
            for path in sorted(added):
                events.append({"kind": "added", "project": name, "path": path})
                if len(events) >= _MAX_DIFF_BATCH:
                    break
            if len(events) < _MAX_DIFF_BATCH:
                for path in sorted(removed):
                    events.append(
                        {"kind": "removed", "project": name, "path": path}
                    )
                    if len(events) >= _MAX_DIFF_BATCH:
                        break
            snapshot[name] = current
            if len(events) >= _MAX_DIFF_BATCH:
                break

        try:
            for evt in events:
                handler.wfile.write(_format_sse("diff", evt))
            if events:
                handler.wfile.flush()

            now = time.monotonic()
            if now - last_keepalive >= _KEEPALIVE_S:
                handler.wfile.write(_keepalive_bytes())
                handler.wfile.flush()
                last_keepalive = now
        except (BrokenPipeError, ConnectionResetError, OSError):
            return
