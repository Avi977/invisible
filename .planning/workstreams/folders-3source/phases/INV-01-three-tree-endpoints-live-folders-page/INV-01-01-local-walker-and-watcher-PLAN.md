---
phase: INV-01-three-tree-endpoints-live-folders-page
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - lib/api/tree_local.py
autonomous: true
requirements:
  - REQ-03
tags:
  - filesystem
  - sse
  - watchdog
  - python-stdlib

must_haves:
  truths:
    - "GET /api/v1/tree/local returns a recursive tree of every project path listed in invisible.toml under [[projects]]."
    - "GET /api/v1/tree/local?watch=1 (SSE) emits diff events when files appear/disappear locally; the UI updates within 5s without a page reload."
    - "Per-project filtering works via ?project=<name> query param (returns only that project's subtree)."
    - "walk_all(project='<unknown>') returns [] (empty list), never [None] — protects downstream renderers from null-deref."
    - "If the watchdog library is unavailable, the daemon does NOT crash; it falls back to a poll-based diff loop."
    - "A misconfigured [[projects]].repo_path that escapes its declared root (.. traversal) is rejected; walker only walks paths it can resolve to inside the configured repo_path."
    - "SSE response includes Access-Control-Allow-Origin: * so the browser on :8090 can subscribe to the dashboard on :8765."
  artifacts:
    - path: "lib/api/tree_local.py"
      provides: "walk_all(project=None), walk_project(name), stream_diffs(handler, project=None) functions consumed by bin/invisible-dashboard"
      min_lines: 120
      exports: ["walk_all", "walk_project", "stream_diffs"]
  key_links:
    - from: "lib/api/tree_local.py::walk_all"
      to: "lib/config.py::load_toml"
      via: "reads [[projects]] list"
      pattern: "load_toml|projects"
    - from: "lib/api/tree_local.py::stream_diffs"
      to: "http.server.BaseHTTPRequestHandler.wfile"
      via: "writes 'data: <json>\\n\\n' chunks directly"
      pattern: "wfile\\.write|data:"
---

<objective>
Build the local-filesystem tree walker and SSE watcher in a single, self-contained module under `lib/api/tree_local.py`.

Purpose: Replaces the `FOLDERS.local` mock in `frontend/data.jsx` with a real recursive tree of every project path listed in `invisible.toml`, and streams diff events over Server-Sent Events so the UI updates within 5 seconds of any filesystem change.

Output: A Python module exporting three functions (`walk_all`, `walk_project`, `stream_diffs`) ready to be wired into `bin/invisible-dashboard` in Wave 2. No routes are registered in this plan — the module is consumed in Plan 03.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/REQUIREMENTS.md
@.planning/workstreams/folders-3source/ROADMAP.md
@.planning/workstreams/folders-3source/STATE.md

@frontend/data.jsx
@bin/invisible-dashboard
@lib/config.py
@invisible.toml.example

<interfaces>
<!-- The exact tree-node shape the frontend renderer expects.
     Extracted from frontend/data.jsx:104-168 (FOLDERS mock) and
     frontend/pages/folders.jsx:1-31 (TreeNode component).
     Endpoint output MUST match this shape exactly. -->

Tree node shape (recursive):
```
{
  "name": "<basename>",          // string, required
  "type": "folder" | "file",      // string, required
  "children": [<node>, ...]?,     // present only on folders that have children
  "badge": "<string>"?,           // optional — used for git status, file size, etc.
  "open": true?                   // optional — pre-open this folder in the UI
}
```

Endpoint top-level response shape (for /api/v1/tree/local):
```
[
  { "name": "<project-name>", "type": "folder", "open": true, "badge": "git"?, "children": [...] },
  ...
]
```
One top-level node per project in invisible.toml. Children are the project's directory contents, recursively walked.

invisible.toml project shape (from invisible.toml.example:19-25):
```toml
[[projects]]
name = "jobslayer"
client = "personal"
repo_path = "~/Projects/jobslayer"
# vps_repo_path = "/srv/jobslayer"   # optional
max_iters = 3
```

lib/config.py exports:
- `home() -> Path` — returns $INVISIBLE_HOME (default ~/.invisible)
- `load_toml() -> dict` — returns parsed invisible.toml as a dict; returns {} if file missing
- The cfg dict's `cfg.get("projects", [])` returns the list of [[projects]] tables.

bin/invisible-dashboard helpers (lib/api/tree_local.py does NOT call these directly; the Wave 2 plan wires them in do_GET):
- `handler._send_json(obj, status=200)` — writes JSON with Content-Type and Content-Length
- `handler._send_text(body, status=200)` — writes text/plain
- `handler.wfile` — raw socket writer (use this for SSE streaming)
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Implement walk_all and walk_project (recursive local tree builder with path-traversal guard)</name>
  <files>lib/api/tree_local.py</files>
  <read_first>
    - lib/config.py (entire file — uses `load_toml()` and `home()`)
    - invisible.toml.example (the `[[projects]]` shape and field names)
    - frontend/data.jsx:104-130 (the exact tree-node shape — verify the shape contract before implementing)
    - bin/invisible-dashboard:248-255 (the `_send_json` helper — confirms the response gets json.dumps'd, so return native dict/list)
  </read_first>
  <action>
    First, ensure the parent directory exists. Run `mkdir -p lib/api` (idempotent; safe for Wave 1 parallelism with Plan 02 which also creates files under `lib/api/`).

    Create `lib/api/tree_local.py` (this is a new file — `lib/api/` is created by the `mkdir` above; the Wave 2 plan creates `lib/api/__init__.py`).

    Top of file: standard imports (`from __future__ import annotations`, `os`, `sys`, `json`, `time`, `pathlib.Path`, `typing.Any`). Add `from config import load_toml, home` (the dashboard already inserts `lib/` onto `sys.path` at startup — see `bin/invisible-dashboard:56` — so a flat import is correct).

    Constants at module top:
    - `MAX_DEPTH = 12` (cap recursion depth; protects against symlink loops and pathological trees)
    - `MAX_NODES_PER_DIR = 2000` (cap children per directory; truncates noisy node_modules/ etc. and sets `badge="+N more"` on the parent when truncated)
    - `IGNORE_NAMES = {".git", "node_modules", ".venv", "venv", "__pycache__", ".next", "dist", "build", ".DS_Store"}` (skip these dir/file names entirely; document the rationale inline — they explode the tree without adding signal)

    Implement `_safe_resolve(repo_path_raw: str) -> Path | None`:
    - `Path(os.path.expanduser(repo_path_raw)).resolve()`
    - Return None if path does not exist, is not a directory, or resolves to `/` or the user's home root (anti-foot-gun: a config of `~/` would expose the entire home dir).
    - Return None if any path component after resolve is `..` (defense-in-depth — `.resolve()` already eliminates `..` but the assertion documents intent).

    Implement `_walk(path: Path, root: Path, depth: int = 0) -> dict`:
    - Build a node `{"name": path.name or str(path), "type": "folder" if path.is_dir() else "file"}`.
    - If `path.is_dir()` and `depth < MAX_DEPTH`:
      - Sort children: directories first (alphabetically), then files (alphabetically).
      - Skip names in `IGNORE_NAMES`.
      - **Containment check:** for each child, ensure `child.resolve().is_relative_to(root)` (Python 3.9+); skip otherwise (this guards against symlinks that escape the repo).
      - Cap at `MAX_NODES_PER_DIR`; if truncated, set `node["badge"] = f"+{remaining} more"` on the parent.
      - Recurse and attach as `node["children"]`.
    - On OSError (permission denied, broken symlink): skip the child silently, do not abort the whole walk.
    - Return the node.

    Implement `walk_project(name: str) -> dict | None`:
    - Load `cfg = load_toml()`.
    - Find the project dict where `proj.get("name") == name`.
    - Resolve `repo_path` via `_safe_resolve`; return None if not found or unsafe.
    - Return `_walk(resolved_path, root=resolved_path, depth=0)` with the node's `name` overridden to the project name (not the directory's basename) and `open=True` and `badge="git"` (matches the existing mock's top-level shape — see data.jsx:110).

    Implement `walk_all(project: str | None = None) -> list[dict]`:
    - If `project` is given, call `result = walk_project(project)`; return `[result]` only if `result is not None`, else return `[]`. **Never return `[None]`** — downstream renderers (frontend TreeNode in Plan 03) will null-deref on `node.name` if a None leaks through.
    - Otherwise iterate every `[[projects]]` entry, call `walk_project(p["name"])`, filter out Nones, return the list.

    Add a module-level docstring explaining: shape contract, ignore list rationale, depth/node caps, that `stream_diffs` is implemented in Task 2.
  </action>
  <verify>
    <automated>cd "$INVISIBLE_HOME" && python3 -c "import sys; sys.path.insert(0, 'lib'); from api.tree_local import walk_all, walk_project; t = walk_all(); assert isinstance(t, list), f'walk_all must return list, got {type(t)}'; assert all('name' in n and 'type' in n for n in t), f'every node must have name+type, got {t}'; u = walk_all(project='__does_not_exist__'); assert u == [], f'unknown project must return [], got {u}'; print('OK', len(t), 'projects')"</automated>
  </verify>
  <done>
    - File `lib/api/tree_local.py` exists with `walk_all`, `walk_project`, `_safe_resolve`, `_walk`, and constants defined.
    - `walk_all()` returns a list of dicts matching the `{name, type, children?, badge?, open?}` contract from `data.jsx:104-130`.
    - `walk_all(project="__nope__")` returns `[]` (empty list) — never `[None]`. This is the BLOCKER #2 fix from the checker pass.
    - `walk_project("jobslayer")` returns a single dict with `type="folder"`, `name="jobslayer"`, `open=True`, and a `children` array of the project's contents (or None if the project is missing from invisible.toml).
    - Symlink escapes, `..` paths, `~/` configs, and non-existent paths return None instead of leaking data.
    - `node_modules`, `.git`, `.venv` are excluded from output.
    - Recursion depth and node count are bounded by `MAX_DEPTH` and `MAX_NODES_PER_DIR`.
  </done>
</task>

<task type="auto">
  <name>Task 2: Implement stream_diffs (SSE watcher with watchdog + polling fallback + CORS header)</name>
  <files>lib/api/tree_local.py</files>
  <read_first>
    - lib/api/tree_local.py (the version written in Task 1 — reuse `walk_all`, `_safe_resolve`, `IGNORE_NAMES`)
    - bin/invisible-dashboard:212-265 (DashboardHandler — note: `self.wfile` is the raw socket writer; SSE writes go there directly)
    - bin/invisible-dashboard:266-316 (do_GET routing pattern — confirms how the handler is invoked)
  </read_first>
  <action>
    Append to `lib/api/tree_local.py`:

    **Watchdog import guard (top of file, with the other imports):**
    ```
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        HAVE_WATCHDOG = True
    except ImportError:
        HAVE_WATCHDOG = False
    ```
    Do not crash on missing watchdog. The daemon must keep working with polling fallback (watchdog is not in any project dependency manifest yet — `pip show watchdog` may succeed on the dev machine but downstream installs cannot rely on it).

    **Implement `_collect_paths(root: Path) -> set[str]`:**
    - Walk the tree using `os.walk(root, followlinks=False)`, skip `IGNORE_NAMES`, return the set of relative path strings for every file and directory under `root`. Used for the polling diff and as the initial snapshot for watchdog.

    **Implement `_format_sse(event_type: str, payload: dict) -> bytes`:**
    - Returns `f"event: {event_type}\\ndata: {json.dumps(payload)}\\n\\n".encode("utf-8")`.
    - Document: SSE chunks must end with a blank line (two newlines); `event:` is optional but lets the client dispatch differently per type.

    **Implement `stream_diffs(handler, project: str | None = None) -> None`:**
    The function takes the dashboard's `BaseHTTPRequestHandler` instance and runs the SSE loop until the client disconnects.

    Step 1 — Send SSE response headers via `handler.send_response(200)`, then:
    - `handler.send_header("Content-Type", "text/event-stream")`
    - `handler.send_header("Cache-Control", "no-store")`
    - `handler.send_header("Connection", "keep-alive")`
    - `handler.send_header("X-Accel-Buffering", "no")` (defeats nginx buffering for any future proxy)
    - `handler.send_header("Access-Control-Allow-Origin", "*")` — **REQUIRED.** EventSource requests are cross-origin (frontend on :8090, dashboard on :8765). Without this header, the browser blocks the SSE connection silently. Mirrors the JSON-response CORS fix that Plan 03 adds to `_send_json`.
    - `handler.end_headers()`

    Step 2 — Resolve the watched paths:
    - Load `cfg = load_toml()`.
    - If `project` is None, watch every project; otherwise just that one.
    - Build a list of `(project_name, root_path)` tuples using `_safe_resolve`; skip any that return None.
    - If the list is empty, write an `error` SSE event with payload `{"error": "no valid project paths"}` and return.

    Step 3 — Send an initial `snapshot` event:
    - `handler.wfile.write(_format_sse("snapshot", {"tree": walk_all(project)}))` and `handler.wfile.flush()`.
    - This lets the client render once before diffs start streaming (avoids a race where a file is added/removed during the SSE handshake).

    Step 4 — Watch loop. Two implementations:

    **(a) Watchdog path** (`if HAVE_WATCHDOG`):
    - Create a thread-safe `queue.Queue()` for events.
    - Define a `_Handler(FileSystemEventHandler)` subclass that pushes a normalized dict `{"kind": "added"|"removed"|"modified", "project": <name>, "path": <relative_path>}` onto the queue for `on_created`, `on_deleted`, `on_modified`. Ignore paths whose any component is in `IGNORE_NAMES`. Ignore events for symlinks that escape the root.
    - Start an `Observer()`; `observer.schedule(_Handler(project_name=p), str(root), recursive=True)` for each `(p, root)` pair. `observer.start()`.
    - In a `while True:` loop, `evt = q.get(timeout=15)`; on timeout write a `: keepalive\\n\\n` comment frame (SSE comment, keeps proxies happy); on event write an SSE `diff` event with the payload.
    - On `BrokenPipeError`/`ConnectionResetError` (client disconnect), `observer.stop(); observer.join(timeout=2); return`.

    **(b) Polling path** (else):
    - `snapshot = {p: _collect_paths(root) for (p, root) in watched}`.
    - Loop: `time.sleep(2)`; for each `(p, root)`, recompute `current = _collect_paths(root)`; compute `added = current - snapshot[p]`, `removed = snapshot[p] - current`; for each, write a `diff` SSE event with payload `{"kind": "added"|"removed", "project": p, "path": str(path)}`. Update `snapshot[p] = current`.
    - Every 15 seconds (track elapsed), write a `: keepalive\\n\\n` comment frame.
    - Cap effective change-batch size at 200 per cycle (avoid storming the client on first run of `npm install`).
    - Same exit-on-disconnect handling as the watchdog path.

    After every `handler.wfile.write(...)`, call `handler.wfile.flush()` so the browser sees the bytes immediately (no buffering).

    Add a docstring on `stream_diffs` noting: caller is responsible for auth (must be checked before invoking); function blocks until client disconnect; uses watchdog when available, polling otherwise; emits `Access-Control-Allow-Origin: *` so the cross-port browser EventSource can connect.
  </action>
  <verify>
    <automated>cd "$INVISIBLE_HOME" && python3 -c "import sys; sys.path.insert(0, 'lib'); from api import tree_local as t; assert callable(t.stream_diffs), 'stream_diffs must be callable'; assert callable(t.walk_all), 'walk_all must be callable'; assert hasattr(t, 'HAVE_WATCHDOG'), 'HAVE_WATCHDOG flag must exist'; import inspect; src = inspect.getsource(t.stream_diffs); assert 'Access-Control-Allow-Origin' in src, 'stream_diffs MUST emit CORS header for cross-port EventSource'; print('imports OK, watchdog=', t.HAVE_WATCHDOG)" 2>&1 | tee /tmp/inv-01-01-task2-imports.log && grep -q "imports OK" /tmp/inv-01-01-task2-imports.log</automated>
  </verify>
  <done>
    - `stream_diffs(handler, project=None)` exists, type-annotated, with the SSE header sequence, initial `snapshot` event, and the watchdog+polling branches above.
    - The SSE header block includes `handler.send_header("Access-Control-Allow-Origin", "*")` before `handler.end_headers()`. This is the BLOCKER #1 fix on the SSE side (Plan 03 fixes the JSON `_send_json` helper and adds OPTIONS preflight).
    - `HAVE_WATCHDOG` boolean exists at module scope; `from watchdog.observers import Observer` is guarded by try/except so the import does not crash when watchdog is absent.
    - The polling path runs end-to-end without watchdog (verified by importing `api.tree_local` in a Python where `watchdog` is forced unavailable, e.g., `python3 -c "import sys; sys.modules['watchdog'] = None; from api import tree_local; assert tree_local.HAVE_WATCHDOG is False"`).
    - Once the route is registered in Plan 03, cross-origin SSE check: `curl -s --max-time 2 -H "Origin: http://127.0.0.1:8090" -I "http://127.0.0.1:8765/api/v1/tree/local?watch=1&token=$TOKEN" | grep -qi "access-control-allow-origin: \*"` succeeds.
    - Final end-to-end verification (`touch /tmp/proj/foo.txt && timeout 6 curl -N "http://127.0.0.1:8765/api/v1/tree/local?watch=1&token=$T" | grep foo.txt`) is deferred to Plan 03 once the route is registered.
  </done>
</task>

</tasks>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| invisible.toml → walker | Operator-controlled config — a misconfigured `repo_path` (e.g. `~/`, `/`) would expose unintended files via the API |
| filesystem symlinks → walker | A symlink inside a project dir could point to `/etc/passwd` or another user's home; `.resolve()` + `is_relative_to(root)` containment guards this |
| HTTP client → SSE endpoint | Unbounded SSE connections could exhaust file descriptors; per-project handler limit + the daemon's existing bearer-token gate addresses this (the auth check is in Plan 03's wiring task) |
| Browser (cross-origin) → SSE endpoint | Frontend on :8090 subscribes to dashboard on :8765; without `Access-Control-Allow-Origin` on the SSE response the browser silently blocks the connection. `stream_diffs` emits `*` (Task 2) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-INV01-01 | Information Disclosure | `_safe_resolve` / `_walk` | mitigate | Reject `repo_path` that resolves to `/`, `~/`, or any path with `..` components after resolve; assert `child.resolve().is_relative_to(root)` for every descendant (Task 1) |
| T-INV01-02 | Information Disclosure | symlink in walked tree | mitigate | `os.walk(root, followlinks=False)` in `_collect_paths`; explicit `is_relative_to` check in `_walk` (Task 1, Task 2) |
| T-INV01-03 | Denial of Service | `_walk` recursion | mitigate | `MAX_DEPTH = 12`, `MAX_NODES_PER_DIR = 2000`, ignore list for noise dirs (`node_modules`, `.git`, etc.) (Task 1) |
| T-INV01-04 | Denial of Service | `stream_diffs` polling/watchdog | mitigate | 200-event cap per polling cycle; queue-based watchdog dispatch with 15s timeout; explicit close on `BrokenPipeError` (Task 2) |
| T-INV01-05 | Tampering | watchdog import | mitigate | try/except ImportError around watchdog imports; polling fallback path is fully functional without the lib (Task 2). Watchdog is not in pyproject yet — do NOT add it as a hard dep in this plan; that decision goes to the orchestrator |
| T-INV01-06 | Spoofing | SSE endpoint auth | accept (in this plan) | This module does not check auth; the dashboard's `_auth_ok()` is called in `do_GET` before `stream_diffs` is invoked. The wiring task in Plan 03 owns the EventSource-can't-set-headers problem (must accept `?token=` query param) |
| T-INV01-17 | Spoofing | CORS bypass on SSE | mitigate | Dashboard `stream_diffs` emits `Access-Control-Allow-Origin: *` directly in its header block (Task 2). Plan 03 mirrors this on `_send_json` and adds an OPTIONS preflight branch in `do_GET`. The browser-on-:8090 → daemon-on-:8765 cross-origin path is the legitimate use case |
| T-INV{phase}-SC | Tampering | watchdog (PyPI package) | accept | `watchdog` is widely-used (10M+ downloads/week, gorakhargosh/watchdog on GitHub since 2012). No `[ASSUMED]` or `[SUS]` flag; the import is guarded by try/except so a missing/typo'd dep cannot crash the daemon. Package legitimacy audit is not blocking for this plan because watchdog is not being added to a dependency manifest in this plan |

No `[ASSUMED]` or `[SUS]` package adds in this plan — the `try/except ImportError` shield means the runtime tolerates watchdog being missing. The decision to formally add `watchdog` to `pyproject.toml` or a `requirements.txt` is out-of-scope for this plan and deferred to whoever creates the project's dependency manifest.

</threat_model>

<verification>
- `lib/api/tree_local.py` exists with `walk_all`, `walk_project`, `stream_diffs` exported.
- `python3 -c "from api.tree_local import walk_all, walk_project, stream_diffs"` (with `lib/` on PYTHONPATH) succeeds.
- Forced absence of watchdog (`sys.modules['watchdog'] = None` before import) does not crash; `HAVE_WATCHDOG is False`.
- `walk_all()` returns a list of dicts; every dict has at least `name` and `type` keys; types are only `"folder"` or `"file"`.
- `walk_all(project="__unknown__")` returns `[]` (not `[None]`).
- A project whose `repo_path` resolves to `/` is rejected (returns None) instead of being walked.
- `stream_diffs` source contains `Access-Control-Allow-Origin` (grep / inspect.getsource check).
- End-to-end HTTP/curl verification is in Plan 03 once the routes are registered in `bin/invisible-dashboard`.
</verification>

<success_criteria>
- Two tasks complete with the file `lib/api/tree_local.py` checked in.
- Three public functions exported: `walk_all`, `walk_project`, `stream_diffs`.
- `walk_all(project=...)` returns `[]` (not `[None]`) for unknown/unsafe project names.
- SSE response emits `Access-Control-Allow-Origin: *` so cross-port browser EventSource works.
- Watchdog optional; polling fallback proven to work via the forced-unavailability import test.
- Path-traversal and symlink-escape guards in place.
- No route registration in this plan — that belongs to Plan 03.
</success_criteria>

<output>
Create `.planning/workstreams/folders-3source/phases/INV-01-three-tree-endpoints-live-folders-page/INV-01-01-SUMMARY.md` when done. Include:
- Exact function signatures (so Plan 03's wiring author has the contract without re-reading the source)
- Whether watchdog was importable on the build machine (informs Plan 03's testing plan)
- The exact SSE event names emitted (`snapshot`, `diff`, `error`) so the frontend `EventSource` handler in Plan 03 dispatches correctly
- Confirmation that the SSE response includes `Access-Control-Allow-Origin: *` (so Plan 03 doesn't need to re-add it)
</output>
</output>
