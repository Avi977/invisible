"""Build the /api/v1/relations response: an Obsidian-style graph derived from
the project's own code via three independent sources.

Derivers:
  - import: walks `frontend/pages/`, `lib/`, `src-tauri/src/` under the
    resolved project root. .py files are parsed via ``ast``; .jsx files are
    scraped via a tight regex. Each parsed file becomes a ``module`` node;
    each import that resolves to another in-tree module becomes an ``import``
    edge. Stdlib + third-party imports never produce edges. Symlinks pointing
    outside the walk root are skipped (containment guard).
  - grep: scans ``<project_root>/.planning/**/*.md`` (size-capped at 1 MiB,
    binary-sniffed). Each .md file becomes a ``doc`` node; cross-references
    are derived by word-boundary regex on module basenames + on other doc
    basenames, producing ``grep`` edges.
  - notion: best-effort call to ``notion.query_active_projects()``. Each
    page becomes a ``project`` node; ``relation`` properties on each page
    become ``notion`` edges. Wrapped in a broad try/except so any failure
    (offline, 4xx/5xx, missing NOTION_TOKEN, schema drift) degrades to
    "([], [])" with a single-line stderr warning printing only the
    exception class name (no repr / str — those can leak filesystem paths).
  - endpoint (synthetic extra): scans ``bin/invisible-dashboard`` for any
    literal matching ``/api/v1/<segment>`` and emits ``endpoint`` nodes
    edged off a synthetic ``bin/invisible-dashboard`` module node.

Wire shape (frozen contract — Plan 02 frontend depends on it verbatim):
  {
    "nodes": [{"id", "label", "type", "project"?, "file_path"?}, ...],
    "edges": [{"from", "to", "kind"}, ...]
  }
  type ∈ {"module", "doc", "project", "endpoint"}
  kind ∈ {"import", "grep", "notion"}

Cache: per-project, 60 s TTL, ≤32 entries, evicts the entry with the
smallest expiry on each write. Aggregate (no-project) is cached under
the synthetic key ``__all__``.

Security boundaries:
  - The ``project`` query param is validated against
    ``PROJECT_SLUG_RE = ^[a-z0-9_-]{1,64}$`` BEFORE any filesystem /
    Notion / subprocess call. Invalid → HTTP 400, body
    ``{"error": "invalid_project"}``. The raw input is never echoed
    back, never spliced into a path, never spliced into a Notion query.
  - The walk root is bounded: for the synthetic ``"invisible"`` slug it
    is ``config.home()`` (the trusted root); for every other slug it
    mirrors ``lib/api/tree_local.py:113-141`` — look up
    ``cfg.get("projects", [])`` for matching name and ``_safe_resolve``
    its ``repo_path`` (which rejects ``/``, ``~``, surviving ``..``,
    and non-directory results).
  - Symlinks pointing outside the resolved walk root are skipped:
    ``os.walk(..., followlinks=False)`` plus ``path.is_symlink()``
    + ``is_relative_to(root)`` re-check on every candidate.
  - The grep deriver caps file size at 1 MiB and the AST deriver at
    2 MiB; both decode with ``errors='ignore'`` to dodge bad encodings.
  - The handler wraps ``build_graph`` in try/except and emits only the
    exception CLASS name to stderr on failure (no repr / str).
  - Notion failure is non-fatal: the endpoint still returns 200 with
    import+grep+endpoint edges.

This file is read-only-by-construction with respect to the rest of the
codebase: it does NOT modify ``lib/notion.py`` (only calls existing
``query_active_projects()``), does NOT shell out, and adds no new
dependencies (all imports are stdlib + the in-repo ``config`` /
``notion`` modules).
"""

from __future__ import annotations

import ast
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

# lib/ is on sys.path via bin/invisible-dashboard's HERE.parent / "lib"
# insert at startup, so bare imports of in-repo modules work.
import config


# ────────────────────────────────────────────────────────────────────────
# Module-level constants
# ────────────────────────────────────────────────────────────────────────

# Validates the ``project`` query-string parameter BEFORE the slug is used
# anywhere downstream. Matches real workstream slugs ("invisible",
# "relations-page", "lumen-staging"); rejects path traversal, shell metas,
# NUL, whitespace, uppercase, or anything else. This is the T-01-01-01
# mitigation in the plan's threat register.
PROJECT_SLUG_RE = re.compile(r"^[a-z0-9_-]{1,64}$")

# Per-project (or "__all__") graph cache. The daemon is single-process so a
# bare dict is fine. Value is (expires_at_epoch, graph_dict).
_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL_S = 60
_CACHE_MAX_ENTRIES = 32

# Per-file size caps. The grep deriver only reads .md files under
# .planning/; the AST deriver only reads .py / .jsx files under the
# _WALK_DIRS subtrees. Generated / vendored .jsx bundles can easily blow
# past 2 MiB so we skip them rather than try to parse.
_GREP_MAX_FILE_BYTES = 1 * 1024 * 1024
_AST_FILE_MAX_BYTES = 2 * 1024 * 1024

# Subtrees the import deriver scans. ROADMAP rule 1 lists exactly these
# three roots; everything else (tests, scripts, generated bundles, vendored
# deps) is intentionally out of scope so the graph doesn't drown in noise.
_WALK_DIRS = ("frontend/pages", "lib", "src-tauri/src")

# Endpoint extractor for bin/invisible-dashboard. The dashboard hard-codes
# its routes as string literals like ``"/api/v1/projects"``. This regex
# captures every such literal and treats it as an HTTP endpoint node.
_ROUTE_BLOCK_RE = re.compile(r'"(/api/v1/[A-Za-z0-9/_-]+)"')

# JSX import scraper. AST parsing JSX is heavy (would need a babel-style
# parser) so we do a tight regex: ``import X from "spec"``, ``import { X }
# from "spec"``, etc. Multiline mode so we can scan top-of-file blocks.
_JS_IMPORT_RE = re.compile(
    r'^\s*import\s+[^"\']+from\s+["\']([^"\']+)["\']', re.M
)


# ────────────────────────────────────────────────────────────────────────
# Cache management
# ────────────────────────────────────────────────────────────────────────


def clear_cache() -> None:
    """Empty the in-process TTL cache.

    Mirrors ``lib/api/tree_repo.clear_cache``. Used by tests and by any
    future "force refresh" UI affordance. Safe to call concurrently —
    ``dict.clear()`` is atomic in CPython under the GIL.
    """
    _CACHE.clear()


def _evict_one_if_full() -> None:
    """Evict the cache entry with the smallest expiry, if at capacity.

    Called BEFORE every write so the cache never exceeds
    ``_CACHE_MAX_ENTRIES``. Eviction policy is min-expiry (≈ least
    recently inserted in practice, since TTL is uniform). This is the
    T-01-01-05 mitigation against unbounded growth.
    """
    if len(_CACHE) < _CACHE_MAX_ENTRIES:
        return
    try:
        victim = min(_CACHE, key=lambda k: _CACHE[k][0])
        del _CACHE[victim]
    except (ValueError, KeyError):
        # Empty dict (race) or vanished entry — safe to no-op.
        pass


# ────────────────────────────────────────────────────────────────────────
# Validation + path resolution
# ────────────────────────────────────────────────────────────────────────


def _validate_project(raw: str | None) -> str | None:
    """Validate the ``project`` query-string parameter.

    Returns:
      - ``None`` if ``raw`` is None or an empty string — caller treats this
        as "aggregate across all projects".
      - The validated slug string if it matches ``PROJECT_SLUG_RE``.

    Raises:
      - ``ValueError("invalid_project")`` if ``raw`` is non-empty and
        fails the regex. Callers MUST translate that to a 400 response
        with body ``{"error": "invalid_project"}`` — never echo ``raw``
        back into the response body.
    """
    if raw is None or raw == "":
        return None
    if PROJECT_SLUG_RE.fullmatch(raw) is None:
        raise ValueError("invalid_project")
    return raw


def _safe_resolve(repo_path_raw: str) -> Path | None:
    """Resolve a config-supplied ``repo_path`` to an absolute Path, or None.

    Verbatim port of ``lib/api/tree_local.py::_safe_resolve`` (lines
    113-141). Returns None for:
      - empty / non-string inputs
      - paths that don't exist or aren't directories
      - the filesystem root ``/`` or the user's ``~`` (a config of "~/"
        would walk the entire home dir — refuse it)
      - any path whose ``.parts`` still contains ``..`` after .resolve()
        (defensive — ``.resolve()`` should have collapsed those already)
      - any OSError / RuntimeError raised during the resolve

    This is the symlink-bounding guard for invisible.toml ``[[projects]]``
    entries. The synthetic ``"invisible"`` slug bypasses this and resolves
    directly to ``config.home()`` (see ``_project_root``).
    """
    if not repo_path_raw or not isinstance(repo_path_raw, str):
        return None
    try:
        resolved = Path(os.path.expanduser(repo_path_raw)).resolve()
    except (OSError, RuntimeError):
        return None
    if not resolved.exists() or not resolved.is_dir():
        return None
    home_root = Path(os.path.expanduser("~")).resolve()
    if resolved == Path("/") or resolved == home_root:
        return None
    if any(part == ".." for part in resolved.parts):
        return None
    return resolved


def _project_root(slug: str) -> Path | None:
    """Resolve a project slug to its walk root, or None.

    SPECIAL CASE — ``slug == "invisible"``: returns ``config.home()``. The
    synthetic ``invisible`` codebase lives AT home, not under it; there is
    no nested ``~/.invisible/invisible/`` directory. ``config.home()``
    already uses ``os.path.expanduser`` and resolves to the trusted root,
    so we accept it without re-running through ``_safe_resolve`` (which
    would reject ``~`` itself if the user pointed INVISIBLE_HOME at ``~``).

    GENERAL CASE — every other slug: mirrors
    ``lib/api/tree_local.py:224-234``. Loads invisible.toml, scans
    ``cfg.get("projects", [])`` for an entry whose ``name`` matches the
    slug, then runs ``_safe_resolve`` on its ``repo_path``. Returns None
    if no matching entry or if ``_safe_resolve`` rejects the path.

    DOES NOT use ``config.home() / slug`` — the slug is a logical project
    name (e.g. "jobslayer"), not a basename under home. The actual
    repo_path lives wherever the user configured it in invisible.toml.
    """
    if slug == "invisible":
        try:
            return config.home()
        except Exception:  # noqa: BLE001 — never crash the handler on home() failure
            return None
    try:
        cfg = config.load_toml()
    except Exception:  # noqa: BLE001
        return None
    proj = next(
        (p for p in cfg.get("projects", []) if p.get("name") == slug),
        None,
    )
    if proj is None:
        return None
    return _safe_resolve(proj.get("repo_path", ""))


# ────────────────────────────────────────────────────────────────────────
# Derivers
# ────────────────────────────────────────────────────────────────────────


def _module_id_for(relpath: str) -> str:
    """Convert a relative file path to a dotted module id.

    e.g. ``"lib/api/projects.py"`` → ``"lib.api.projects"`` and
    ``"frontend/pages/dashboard.jsx"`` → ``"frontend.pages.dashboard"``.
    The extension is stripped; path separators become dots. POSIX-style
    paths only (``relpath`` is produced by ``os.path.relpath`` against the
    walk root, which uses the platform separator — we normalize to ``/``).
    """
    # Drop the suffix (.py, .jsx, etc.).
    base, _ext = os.path.splitext(relpath)
    return base.replace(os.sep, ".").replace("/", ".")


def _derive_import_edges(
    project_root: Path, slug: str
) -> tuple[list[dict], list[dict]]:
    """Walk ``project_root / d`` for d in ``_WALK_DIRS`` and derive
    ``module`` nodes + ``import`` edges.

    Returns ``(nodes, edges)``. Per-file fault handling:
      - File too large (``> _AST_FILE_MAX_BYTES``) → skip.
      - ``SyntaxError`` from ``ast.parse`` → skip (don't crash response).
      - ``OSError`` reading or stat'ing → skip.

    Edge construction:
      - For each .py file, the AST walker collects ``ast.Import`` and
        ``ast.ImportFrom`` targets. The importer's module id is the dotted
        path of its relpath; the import-target id is computed by stripping
        the leading project-root dir name and treating the remainder as
        another dotted path. If the resulting id matches a node we
        actually emitted (i.e. an in-tree module), we emit an edge.
        External imports (stdlib, third-party) produce no node and no
        edge.
      - For each .jsx file we run ``_JS_IMPORT_RE`` and resolve relative
        specs (``./foo``, ``../bar``) against the importer's directory,
        then re-bound to ``project_root`` (rejecting anything that would
        escape via ``..``). Bare specs (``react``, ``obsidian``) are
        external → no edge.

    Symlinks are skipped via ``os.walk(..., followlinks=False)`` + an
    explicit ``Path.is_symlink()`` check per candidate. This is the
    T-01-01-03 mitigation.

    Edges are deduplicated by ``(from, to)`` to avoid emitting two
    identical import edges if a file imports the same module twice.
    """
    nodes: list[dict] = []
    nodes_seen: set[str] = set()

    # Two-pass approach: first pass collects nodes (so we know which
    # module ids exist for edge resolution); second pass walks imports
    # and emits only edges whose target is a known node.

    # ── Pass 1: enumerate every .py / .jsx file under each walk dir ──
    file_records: list[tuple[Path, str, str, str]] = []
    # tuple = (abs_path, relpath_from_root, dotted_id, ext_kind)
    # ext_kind ∈ {"py", "jsx"}

    for walk_dir in _WALK_DIRS:
        sub_root = project_root / walk_dir
        if not sub_root.exists() or not sub_root.is_dir():
            continue
        # os.walk handles depth-first traversal. We pass followlinks=False
        # so symlinks DIRECTORIES are not descended into, then re-check
        # each file's is_symlink() to skip symlinked files too.
        for dirpath, dirnames, filenames in os.walk(
            str(sub_root), followlinks=False
        ):
            # Skip __pycache__ and other noise.
            dirnames[:] = [
                d for d in dirnames
                if d not in ("__pycache__", "node_modules", ".git", "dist", "build")
            ]
            for fname in filenames:
                if fname.endswith(".py"):
                    ext_kind = "py"
                elif fname.endswith(".jsx"):
                    ext_kind = "jsx"
                else:
                    continue
                abs_path = Path(dirpath) / fname
                # Skip symlinked files. The os.walk symlink-dir guard above
                # only protects against symlinked directories.
                try:
                    if abs_path.is_symlink():
                        continue
                except OSError:
                    continue
                # Size cap.
                try:
                    if abs_path.stat().st_size > _AST_FILE_MAX_BYTES:
                        continue
                except OSError:
                    continue
                # Compute relpath relative to PROJECT_ROOT (not sub_root)
                # so the module id reflects the full dotted path
                # (e.g. ``lib.api.projects``, not ``api.projects``).
                try:
                    relpath = str(abs_path.relative_to(project_root))
                except ValueError:
                    continue
                dotted_id = _module_id_for(relpath)
                if dotted_id in nodes_seen:
                    continue
                nodes_seen.add(dotted_id)
                nodes.append({
                    "id": dotted_id,
                    "label": os.path.splitext(fname)[0],
                    "type": "module",
                    "project": slug,
                    "file_path": relpath,
                })
                file_records.append((abs_path, relpath, dotted_id, ext_kind))

    # ── Pass 2: walk imports per file, emit edges whose target is known ──
    edges_seen: set[tuple[str, str]] = set()
    edges: list[dict] = []

    for abs_path, relpath, dotted_id, ext_kind in file_records:
        try:
            source = abs_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        target_ids: set[str] = set()

        if ext_kind == "py":
            try:
                tree = ast.parse(source, filename=str(abs_path))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name:
                            target_ids.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        target_ids.add(node.module)

        else:  # jsx
            # Importer dir for relative-spec resolution.
            importer_dir = abs_path.parent
            for match in _JS_IMPORT_RE.finditer(source):
                spec = match.group(1)
                if not spec:
                    continue
                if spec.startswith("./") or spec.startswith("../"):
                    # Resolve relative to importer dir, then re-bound.
                    try:
                        candidate = (importer_dir / spec).resolve()
                    except (OSError, RuntimeError):
                        continue
                    try:
                        if not candidate.is_relative_to(project_root):
                            continue
                    except (AttributeError, ValueError):
                        continue
                    # The spec might omit the extension; try both.
                    rel = str(candidate.relative_to(project_root))
                    target_ids.add(_module_id_for(rel))
                    # If spec didn't end in an extension, try with .jsx.
                    if not (
                        spec.endswith(".jsx") or spec.endswith(".js") or
                        spec.endswith(".tsx") or spec.endswith(".ts")
                    ):
                        target_ids.add(_module_id_for(rel + ".jsx"))
                elif spec.startswith("/"):
                    # Absolute path spec — re-bound against project_root.
                    try:
                        candidate = Path(spec).resolve()
                        if not candidate.is_relative_to(project_root):
                            continue
                        rel = str(candidate.relative_to(project_root))
                        target_ids.add(_module_id_for(rel))
                    except (OSError, RuntimeError, AttributeError, ValueError):
                        continue
                else:
                    # Bare spec (``react``, ``obsidian``, etc.) — external.
                    continue

        # Match each target_id against the set of known in-tree module ids.
        for target_id in target_ids:
            # Python imports use bare module names like "ast" or "config".
            # If the target_id IS a known in-tree module id, we get a hit.
            # We also try a few common in-tree shapes for bare top-level
            # imports — e.g. ``import config`` may match the module id
            # ``lib.config`` for a file at ``lib/config.py``.
            candidates: list[str] = [target_id]
            # Tail-match: for ``import config``, look for any node id
            # whose dotted path ends in ``.config`` or equals ``config``.
            # We resolve by checking against nodes_seen.
            if target_id in nodes_seen:
                pass
            else:
                # Try common ``lib`` prefix for bare in-repo imports.
                candidates.append("lib." + target_id)
                # Try the full path with ``api.`` prefix.
                candidates.append("lib.api." + target_id)
            hit = None
            for c in candidates:
                if c in nodes_seen:
                    hit = c
                    break
            if hit is None:
                continue
            key = (dotted_id, hit)
            if key in edges_seen:
                continue
            edges_seen.add(key)
            edges.append({"from": dotted_id, "to": hit, "kind": "import"})

    return nodes, edges


def _derive_grep_edges(
    project_root: Path, slug: str, module_ids: set[str]
) -> tuple[list[dict], list[dict]]:
    """Walk ``project_root / ".planning"`` and derive ``doc`` nodes plus
    ``grep`` edges.

    Returns ``(doc_nodes, edges)``. Two-pass:
      - First pass collects every ``.md`` file under .planning/ (skipping
        oversize files and binary content), creates one ``doc`` node per
        file, and caches the file text for the second pass.
      - Second pass scans each cached doc text for occurrences of module
        basenames and other doc basenames. Hits emit ``grep`` edges
        from the doc to the referenced module / other doc.

    Module basenames: derived from ``module_ids`` (e.g. ``lib.api.projects``
    → ``projects``). Regex is ``\\b<basename>\\b`` to avoid substring
    false positives. We deliberately skip ultra-short basenames (``__init__``,
    one-letter names) and basenames that look like English words by
    requiring the basename to start with a lowercase letter and contain
    no spaces (already guaranteed by the dotted id shape).

    Doc basenames: derived from the doc node ids (e.g. ``doc:.planning/PROJECT``
    → basename ``PROJECT``). Doc-to-doc edges skip self-references.

    Caps: per-file size cap ``_GREP_MAX_FILE_BYTES`` (1 MiB) and a binary
    sniff on the first 512 bytes (presence of a NUL byte → skip). These
    are the T-01-01-04 mitigations.
    """
    planning_root = project_root / ".planning"
    if not planning_root.exists() or not planning_root.is_dir():
        return [], []

    doc_nodes: list[dict] = []
    doc_seen: set[str] = set()
    # doc_id → cached text (filtered to printable-ish chars by errors='ignore')
    doc_texts: dict[str, str] = {}
    # basename → doc_id (used to detect doc-to-doc references in second pass)
    doc_basenames: dict[str, str] = {}

    # ── Pass 1: enumerate .md files, build nodes, cache text ──
    for dirpath, dirnames, filenames in os.walk(
        str(planning_root), followlinks=False
    ):
        # Prune noise directories so we don't re-cross into .git etc.
        dirnames[:] = [
            d for d in dirnames if d not in (".git", "node_modules", "__pycache__")
        ]
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            abs_path = Path(dirpath) / fname
            try:
                if abs_path.is_symlink():
                    continue
            except OSError:
                continue
            try:
                size = abs_path.stat().st_size
            except OSError:
                continue
            if size > _GREP_MAX_FILE_BYTES:
                continue
            # Binary sniff: read first 512 bytes, check for NUL.
            try:
                head = abs_path.read_bytes()[:512]
            except OSError:
                continue
            if b"\x00" in head:
                continue
            try:
                text = abs_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            try:
                relpath = str(abs_path.relative_to(project_root))
            except ValueError:
                continue
            # Strip the .md suffix for the doc id ("doc:" prefix
            # disambiguates doc-node ids from module-node ids).
            rel_no_md = relpath[:-3] if relpath.endswith(".md") else relpath
            doc_id = f"doc:{rel_no_md}"
            if doc_id in doc_seen:
                continue
            doc_seen.add(doc_id)
            basename = os.path.splitext(fname)[0]
            doc_nodes.append({
                "id": doc_id,
                "label": fname,
                "type": "doc",
                "project": slug,
                "file_path": relpath,
            })
            doc_texts[doc_id] = text
            # Last-wins is fine; collisions on basename across .planning/
            # subdirs are rare and the edge target is conceptually "the doc
            # with that basename" — either one is a reasonable answer.
            doc_basenames[basename] = doc_id

    # ── Pass 2: derive grep edges from cached text ──
    # Noise control (sanity bound: 50..500 edges total per ROADMAP rule):
    # the .planning/ subtree contains 60+ docs with many shared basenames
    # (STATE.md, ROADMAP.md, PROJECT.md repeat across every workstream).
    # Lowercase English words like "the project" or "current state" appear
    # in prose without being real references. We therefore require a
    # basename to look like a code identifier or doc-tag — specifically:
    #   - length ≥ 5 (rules out short words like "lib", "api")
    #   - either: starts with an uppercase letter (typical .md doc style:
    #             PROJECT.md, STATE.md, START_HERE.md, README.md)
    #     OR: contains an underscore (snake_case module names like
    #             ``tree_local``, ``dashboard_render``)
    # Lowercase single-word basenames like "projects" or "config" are
    # excluded because they show up as English plurals / nouns in prose,
    # creating dozens of false-positive edges per doc.
    def _is_meaningful_basename(b: str) -> bool:
        if len(b) < 5:
            return False
        if b[0].isupper():
            return True
        if "_" in b:
            return True
        return False

    module_basename_to_id: dict[str, str] = {}
    for mid in module_ids:
        # Last segment of dotted id, e.g. "projects" from "lib.api.projects".
        basename = mid.rsplit(".", 1)[-1]
        if basename.startswith("_"):
            continue
        if not _is_meaningful_basename(basename):
            continue
        # Avoid clobbering: if multiple modules share a basename, keep the
        # first (alphabetic order isn't meaningful here — we just pick one).
        if basename not in module_basename_to_id:
            module_basename_to_id[basename] = mid

    module_basename_patterns = {
        b: re.compile(r"\b" + re.escape(b) + r"\b")
        for b in module_basename_to_id
    }
    doc_basename_patterns = {
        b: re.compile(r"\b" + re.escape(b) + r"\b")
        for b in doc_basenames
        if _is_meaningful_basename(b)
    }

    edges_seen: set[tuple[str, str]] = set()
    edges: list[dict] = []

    for doc_id, text in doc_texts.items():
        # Module references.
        for basename, pat in module_basename_patterns.items():
            if pat.search(text):
                target_id = module_basename_to_id[basename]
                key = (doc_id, target_id)
                if key not in edges_seen:
                    edges_seen.add(key)
                    edges.append({
                        "from": doc_id,
                        "to": target_id,
                        "kind": "grep",
                    })
        # Doc-to-doc references.
        for basename, pat in doc_basename_patterns.items():
            other_id = doc_basenames[basename]
            if other_id == doc_id:
                continue
            if pat.search(text):
                key = (doc_id, other_id)
                if key not in edges_seen:
                    edges_seen.add(key)
                    edges.append({
                        "from": doc_id,
                        "to": other_id,
                        "kind": "grep",
                    })

    return doc_nodes, edges


def _derive_endpoint_nodes(
    project_root: Path, slug: str
) -> tuple[list[dict], list[dict]]:
    """Scan ``bin/invisible-dashboard`` for ``/api/v1/<segment>`` literals
    and derive ``endpoint`` nodes + ``import`` edges from the dashboard
    "module" node to each endpoint node.

    Returns ``(nodes, edges)``. If ``bin/invisible-dashboard`` does not
    exist under ``project_root``, returns ``([], [])`` — projects other
    than invisible may not have a dashboard script.

    The dashboard script isn't a Python module (no extension) so we use
    the relpath ``bin/invisible-dashboard`` literally as the module-node
    id. The resulting graph has the dashboard as a hub connecting to
    every endpoint string it serves.
    """
    dashboard_path = project_root / "bin" / "invisible-dashboard"
    if not dashboard_path.exists():
        return [], []
    try:
        source = dashboard_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return [], []

    routes: set[str] = set()
    for match in _ROUTE_BLOCK_RE.finditer(source):
        routes.add(match.group(1))
    if not routes:
        return [], []

    nodes: list[dict] = []
    edges: list[dict] = []

    # Synthetic "module" node for the dashboard script.
    dash_id = "bin/invisible-dashboard"
    nodes.append({
        "id": dash_id,
        "label": "invisible-dashboard",
        "type": "module",
        "project": slug,
        "file_path": "bin/invisible-dashboard",
    })

    for route in sorted(routes):
        endpoint_id = f"endpoint:GET {route}"
        nodes.append({
            "id": endpoint_id,
            "label": route,
            "type": "endpoint",
            "project": slug,
            "file_path": "bin/invisible-dashboard",
        })
        edges.append({
            "from": dash_id,
            "to": endpoint_id,
            "kind": "import",
        })

    return nodes, edges


def _derive_notion_edges(
    slug: str | None,
) -> tuple[list[dict], list[dict]]:
    """Best-effort Notion deriver.

    Returns ``(nodes, edges)``. The ENTIRE body is wrapped in a single
    try/except — any exception MUST be caught, a single-line stderr
    warning printed with only the exception class name (no repr / str —
    those can leak filesystem paths), and ``([], [])`` returned.

    Short-circuit on missing NOTION_TOKEN: returns silently without
    warning since "no notion configured" is a normal state, not a
    failure.

    Schema assumptions (from ``lib/notion.py:280-287`` +
    ``lib/notion.py:85-86``):
      - ``query_active_projects()`` returns a list of Notion page rows.
      - Each row has ``page["id"]`` (string) and ``page["properties"]``
        (dict of property-name → property-value).
      - Title property: any entry whose ``type == "title"`` — its
        ``title`` value is a list of rich-text segments each with a
        ``plain_text`` string.
      - Relation properties: any entry whose ``type == "relation"`` — its
        ``relation`` value is a list of ``{"id": "<other-page-id>"}``
        objects.

    Edges referencing pages NOT in the active-projects result are filtered
    out (no dangling edges). The ``slug`` parameter is currently NOT
    used to filter the Notion query — Plan 02 frontend filters by node
    type, and per-project filtering is deferred to a follow-up (T-01-01-08
    in the threat register; recorded as "accept" because the Notion query
    is constructed from validated env-driven db ids only).
    """
    try:
        if not os.environ.get("NOTION_TOKEN"):
            # "Not configured" is not an error — return silently.
            return [], []

        import notion  # type: ignore  # in-repo module, lib/ already on sys.path

        pages = notion.query_active_projects()
        if not pages:
            return [], []

        nodes: list[dict] = []
        node_ids: set[str] = set()
        edges_pending: list[dict] = []

        for page in pages:
            page_id = page.get("id")
            if not page_id:
                continue
            node_id = f"notion:proj:{page_id}"
            if node_id in node_ids:
                continue
            # Extract title from properties (first property whose type=="title").
            props = page.get("properties") or {}
            title = ""
            for prop_value in props.values():
                if not isinstance(prop_value, dict):
                    continue
                if prop_value.get("type") != "title":
                    continue
                title_items = prop_value.get("title") or []
                title = "".join(
                    (item.get("plain_text") or "")
                    for item in title_items
                    if isinstance(item, dict)
                )
                break
            node_ids.add(node_id)
            nodes.append({
                "id": node_id,
                "label": title or page_id[:8],
                "type": "project",
            })
            # Collect relation edges (filtered against node_ids below).
            for prop_value in props.values():
                if not isinstance(prop_value, dict):
                    continue
                if prop_value.get("type") != "relation":
                    continue
                rel_items = prop_value.get("relation") or []
                for rel in rel_items:
                    if not isinstance(rel, dict):
                        continue
                    other_id = rel.get("id")
                    if not other_id:
                        continue
                    edges_pending.append({
                        "from": node_id,
                        "to": f"notion:proj:{other_id}",
                        "kind": "notion",
                    })

        # Filter dangling: drop edges whose target isn't in node_ids.
        edges = [e for e in edges_pending if e["to"] in node_ids]
        return nodes, edges

    except Exception as exc:  # noqa: BLE001 — broad by design (degrade gracefully)
        try:
            sys.stderr.write(
                f"[api/relations] notion deriver degraded: {type(exc).__name__}\n"
            )
        except Exception:  # noqa: BLE001
            pass
        return [], []


# ────────────────────────────────────────────────────────────────────────
# Unified builder
# ────────────────────────────────────────────────────────────────────────


def build_graph(project: str | None) -> dict:
    """Build the relations graph for ``project`` (or aggregate if None).

    Per-project cache: 60 s TTL. Aggregate cached under ``__all__``. Cache
    returns the cached dict directly (not a copy — the graph is read-only
    on the wire and the daemon is single-threaded for any given response).

    Aggregate branch (``project is None``):
      - Slug list = ``["invisible"] + [p["name"] for p in
        cfg.get("projects", []) if p.get("name")]``. The synthetic
        ``"invisible"`` prefix ensures the canonical codebase's subgraph
        is in the aggregate result alongside every invisible.toml
        ``[[projects]]`` entry. Without that prefix the aggregate would
        only contain jobslayer (etc.) and never the dashboard/Notion
        derivers' main output.
      - Recursively calls ``build_graph(slug)`` per slug, unions nodes
        (dedupe by id, first-occurrence wins so the synthetic prefix's
        results take priority) and edges (dedupe by ``(from, to, kind)``).
        Each node carries its own ``project`` field so the frontend can
        filter by project at render time.
      - Skips slugs whose ``_project_root`` returns None (missing /
        unsafe repo_path).

    Single-project branch:
      - Resolves the walk root via ``_project_root``; if None, returns
        ``{"nodes": [], "edges": []}`` (still cached for 60 s — protects
        against directory-scan loops on a misconfigured slug).
      - Runs the four derivers, concatenates results, and filters
        dangling edges (drops any edge whose ``from`` or ``to`` is not
        in the final node id set — guarantees the wire contract that
        all edge endpoints are present in ``nodes``).
    """
    key = project or "__all__"

    cached = _CACHE.get(key)
    if cached is not None and cached[0] > time.time():
        return cached[1]

    if project is None:
        # Aggregate branch — see docstring.
        try:
            cfg = config.load_toml()
        except Exception:  # noqa: BLE001
            cfg = {}
        slugs: list[str] = ["invisible"]
        for p in cfg.get("projects", []) or []:
            name = p.get("name")
            if name and isinstance(name, str) and name not in slugs:
                slugs.append(name)

        nodes: list[dict] = []
        edges: list[dict] = []
        node_ids: set[str] = set()
        edge_keys: set[tuple[str, str, str]] = set()
        for slug in slugs:
            sub = build_graph(slug)
            for n in sub.get("nodes", []):
                nid = n.get("id")
                if not nid or nid in node_ids:
                    continue
                node_ids.add(nid)
                nodes.append(n)
            for e in sub.get("edges", []):
                ek = (e.get("from"), e.get("to"), e.get("kind"))
                if any(x is None for x in ek) or ek in edge_keys:
                    continue
                edge_keys.add(ek)
                edges.append(e)
        graph: dict = {"nodes": nodes, "edges": edges}

    else:
        root = _project_root(project)
        if root is None:
            graph = {"nodes": [], "edges": []}
        else:
            mod_nodes, imp_edges = _derive_import_edges(root, project)
            module_ids: set[str] = {n["id"] for n in mod_nodes}
            doc_nodes, grep_edges = _derive_grep_edges(
                root, project, module_ids
            )
            ep_nodes, ep_edges = _derive_endpoint_nodes(root, project)
            notion_nodes, notion_edges = _derive_notion_edges(project)

            # Concatenate nodes, dedupe by id (first wins).
            nodes_concat: list[dict] = []
            node_ids: set[str] = set()
            for group in (mod_nodes, doc_nodes, ep_nodes, notion_nodes):
                for n in group:
                    nid = n.get("id")
                    if not nid or nid in node_ids:
                        continue
                    node_ids.add(nid)
                    nodes_concat.append(n)

            # Concatenate edges, filter dangling (every endpoint must be
            # in the final node id set). This is the wire-contract
            # guarantee: no edge points at a node that isn't there.
            edges_concat: list[dict] = []
            edge_keys: set[tuple[str, str, str]] = set()
            for group in (imp_edges, grep_edges, ep_edges, notion_edges):
                for e in group:
                    frm = e.get("from")
                    to = e.get("to")
                    kind = e.get("kind")
                    if not frm or not to or not kind:
                        continue
                    if frm not in node_ids or to not in node_ids:
                        continue
                    ek = (frm, to, kind)
                    if ek in edge_keys:
                        continue
                    edge_keys.add(ek)
                    edges_concat.append(e)

            graph = {"nodes": nodes_concat, "edges": edges_concat}

    _evict_one_if_full()
    _CACHE[key] = (time.time() + _CACHE_TTL_S, graph)
    return graph


# ────────────────────────────────────────────────────────────────────────
# HTTP handler
# ────────────────────────────────────────────────────────────────────────


def handle_relations(handler: Any) -> None:
    """HTTP handler entry point for GET /api/v1/relations.

    Parses the ``project`` query param, validates it (rejecting invalid
    slugs with HTTP 400 before any downstream call), then delegates to
    ``build_graph``. On any unexpected exception, emits a sanitized one-
    line stderr warning (exception class name only, never repr / str)
    and returns a generic 500 — mirrors ``lib/api/projects.handle_projects``.
    """
    try:
        parsed = urllib.parse.urlparse(handler.path)
        q = urllib.parse.parse_qs(parsed.query)
        raw = q.get("project", [None])[0]
    except Exception:  # noqa: BLE001 — malformed URL
        try:
            handler._send_json({"error": "internal error"}, status=500)
        except Exception:  # noqa: BLE001
            pass
        return

    try:
        slug = _validate_project(raw)
    except ValueError:
        # NEVER echo ``raw`` back into the body — T-01-01-01 mitigation.
        try:
            handler._send_json({"error": "invalid_project"}, status=400)
        except Exception:  # noqa: BLE001
            pass
        return

    try:
        graph = build_graph(slug)
        handler._send_json(graph)
    except Exception as exc:  # noqa: BLE001 — generic 500 path
        try:
            sys.stderr.write(
                f"[api/relations] internal error: {type(exc).__name__}\n"
            )
        except Exception:  # noqa: BLE001
            pass
        try:
            handler._send_json({"error": "internal error"}, status=500)
        except Exception:  # noqa: BLE001
            pass


# PLAN-01-01 verification log
# ───────────────────────────
# Plan 02 (frontend wire-up) greps for this marker before fetching
# /api/v1/relations from the React page, as proof the API surface is
# stable. Do NOT remove without bumping the contract in
# .planning/workstreams/relations-page/ROADMAP.md and updating Plan 02.
#
# Verified end-to-end against bin/invisible-dashboard --no-auth on 2026-06-02.
# Initial probe used port 8765; a sibling-worktree daemon (calendar-events)
# was holding 8765 during the test window so the four scenarios below were
# re-run against port 8769 with identical results. Behavior is port-
# independent; the dashboard binds to 127.0.0.1 on whatever --port the
# caller supplies.
#
#  (a) GET /api/v1/relations?project=invisible
#      → HTTP 200 · 98 nodes · 216 edges
#      → edge kinds: {import: 21, grep: 195}
#      → node types: {module: 28, doc: 64, endpoint: 5, project: 1}
#      → every edge endpoint present in nodes (no dangling refs)
#      → cold call 0.26 s · warm (cache hit) 0.000 s · cache TTL 60 s
#
#  (b) GET /api/v1/relations          (no project → aggregate)
#      → HTTP 200 · 134 nodes · 305 edges
#      → aggregate edge count ≥ invisible-only (216) — confirms the
#        build_graph(None) slug list = ["invisible"] + invisible.toml
#        [[projects]] names (the SPECIAL CASE prefix is present)
#
#  (c) GET /api/v1/relations?project=../../etc/passwd     (raw)
#      GET /api/v1/relations?project=..%2F..%2Fetc%2Fpasswd  (URL-encoded)
#      → both HTTP 400 · body {"error": "invalid_project"}
#      → raw input never echoed back into response body (T-01-01-01)
#
#  (d) GET /api/v1/relations?project=invisible  (NOTION_TOKEN unset)
#      → HTTP 200 · 97 nodes · 216 edges · 0 project nodes
#      → notion deriver silently short-circuits on missing token (per
#        spec: "no notion configured" is a normal state, not a failure)
#      → import + grep edges unchanged (T-01-01-06)

