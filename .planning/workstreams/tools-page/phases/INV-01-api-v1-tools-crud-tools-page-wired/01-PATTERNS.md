# Phase 1: /api/v1/tools CRUD + Tools page wired - Pattern Map

**Mapped:** 2026-06-01
**Files analyzed:** 6 (1 new, 5 modified)
**Analogs found:** 6 / 6 (every file has a concrete in-repo analog)

> All excerpts below are verbatim from the real files at the cited `path:line`. The CONTEXT.md `<canonical_refs>` were verified against the live source; the line numbers and the two bugs (duplicate-ACAO, duplicate `do_OPTIONS`, missing `return` after `API_V1_ROUTES[path]`) are confirmed present.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `lib/api/tools.py` (NEW) | service / API module | CRUD + file-I/O (JSON blob per project) | `lib/api/projects.py` | role-match (read-only analog → extend to write) |
| `lib/api/__init__.py` (EDIT) | config / registry | n/a (import wiring) | itself (bottom-block imports L36-39) | exact |
| `bin/invisible-dashboard` (EDIT) | controller / HTTP router | request-response (GET/PUT/DELETE/OPTIONS) | `do_POST` L433-492 + `do_GET` tree branches L371-405 | exact (same handler class) |
| `frontend/pages/tools.jsx` (EDIT) | component | request-response (load + debounced autosave) | `frontend/pages/folders.jsx` | role-match (fetch scaffolding) |
| `frontend/data.jsx` (EDIT) | config / mock store | n/a (mock removal) | itself L171 + L461 | exact |
| `frontend/pages/folders.jsx` | component (fetch template, read-only ref) | request-response | n/a — this IS the template | exact |

---

## Pattern Assignments

### `lib/api/tools.py` (NEW — service / CRUD + file-I/O)

**Analog:** `lib/api/projects.py`

**Module docstring + import shape** (`lib/api/projects.py:1-35`) — copy the "Data flow / Security notes" docstring style, `from __future__ import annotations`, and the `import config` / `import checkpoint` form (lib/ is already on `sys.path` via the daemon):
```python
from __future__ import annotations
import os, sys
from pathlib import Path
from typing import Any
import config        # config.home() resolves $INVISIBLE_HOME (~/.invisible)
```

**`config.home()` for the root (D-01)** — never hardcode; mirror how `projects.py` derives every path from `config.home()` (`lib/api/projects.py:94,100,259`):
```python
invisible_root = config.home().resolve()
worktree = config.home() / "worktrees" / name / "feature"
```
**Do it like this:** `wf_dir = config.home() / "workflows"`; target = `wf_dir / f"{project}.json"`.

**Trust-boundary check → slug validator (D-03)** — `_safe_path()` is the analog for "validate BEFORE building a path". It resolves then confirms the path stays inside a trusted root and returns `None` on any escape (`lib/api/projects.py:80-104`):
```python
def _safe_path(p: str) -> Path | None:
    if not p:
        return None
    try:
        resolved = Path(os.path.expanduser(p)).resolve()
    except (OSError, RuntimeError):
        return None
    home_dir = Path(os.path.expanduser("~")).resolve()
    invisible_root = config.home().resolve()
    try:
        if resolved.is_relative_to(home_dir):
            return resolved
        if resolved.is_relative_to(invisible_root):
            return resolved
    except (AttributeError, ValueError):
        pass
    return None
```
**Do it like this:** D-03 wants the *stricter* slug form (reject before constructing any path), so add a regex gate `re.match(r"^[a-z0-9][a-z0-9_-]{0,63}$", project)` → return 400 on no-match. Keep the same "return None / reject" posture as `_safe_path`. The existing slug-shape reference is `_id_for` (`lib/api/projects.py:218-220`): `name.lower().strip().replace(" ", "-").replace("_", "-")` — but for an attacker-supplied query param, validate-and-reject (regex) beats normalize.

**Handler contract + generic-500 (D-04)** — `handle_projects` is the exact transport-agnostic shape: take `handler`, do IO, call `handler._send_json(...)`, wrap everything so no traceback/path leaks (`lib/api/projects.py:301-321`):
```python
def handle_projects(handler: Any) -> None:
    try:
        rows = build_projects()
        handler._send_json(rows)
    except Exception as exc:  # noqa: BLE001 — generic 500 path
        try:
            sys.stderr.write(f"[api/projects] internal error: {type(exc).__name__}\n")
        except Exception:
            pass
        try:
            handler._send_json({"error": "internal error"}, status=500)
        except Exception:
            pass
```
**Do it like this:** Expose `handle_get(handler)`, `handle_put(handler)`, `handle_delete(handler)` (Claude's-discretion D-60 allows a single dispatcher, but three funcs match the registry/route style best). Each: read+validate the `project` query param via `urllib.parse` off `handler.path` (see the daemon's own `parse_qs` usage at `bin/invisible-dashboard:356-357`), call `handler._send_json(obj, status)`, and wrap in the try/except → `{"error":"internal error"}` 500 shown above. Log only `type(exc).__name__` to stderr — never the path.

**Atomic lock-free write (D-02)** — *no in-repo analog uses `os.replace`* (`projects.py` is read-only). Use the stdlib tmpfile-in-same-dir pattern:
```python
import json, os, tempfile
from datetime import datetime, timezone

def _write_atomic(target: Path, obj: dict) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)   # D-02 first-write mkdir
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)        # atomic rename, same filesystem
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise
```
**Do it like this:** PUT body → validate `nodes`/`edges` are both `list` (else 400), stamp `updated_at = datetime.now(timezone.utc).isoformat()` (D-06), `_write_atomic`, return `{"updated_at": <value>}`. GET: missing file → 200 `{"nodes":[],"edges":[],"updated_at":null}` (D-05, NOT 404). DELETE: `target.unlink()`; `FileNotFoundError` → 404, else `{"deleted":true}` (D-07).

---

### `lib/api/__init__.py` (EDIT — registry import)

**Analog:** itself (the bottom-block imports).

**Current bottom block** (`lib/api/__init__.py:36-39`):
```python
from . import chat        # noqa: F401  (ai-bubble: POST /api/v1/chat)
from . import tree_local  # noqa: F401  (folders: GET /api/v1/tree/local + SSE)
from . import tree_vps    # noqa: F401  (folders: GET /api/v1/tree/vps)
from . import tree_repo   # noqa: F401  (folders: GET /api/v1/tree/repo)
```
**Do it like this (D-08):** Append one line in this same block:
```python
from . import tools       # noqa: F401  (tools: GET/PUT/DELETE /api/v1/tools)
```
> Note: the `ROUTES` dict (L23-25) only registers GET-style handlers and the daemon dispatches it WITHOUT a `return` (the latent bug). Per D-09 do NOT add `/api/v1/tools` to `ROUTES`; route it explicitly in `do_GET` instead (see next section). Adding `tools` to `__all__` (L27) is optional and harmless.

---

### `bin/invisible-dashboard` (EDIT — HTTP router, the big merge surface)

**Analog:** `DashboardHandler` itself (`do_POST`, `do_GET` tree branches, the two `do_OPTIONS`, `_send_json`/`end_headers`).

**(a) Import the module (D-08)** — alongside the existing `from api import ...` lines (`bin/invisible-dashboard:62-64`):
```python
from api import ROUTES as API_V1_ROUTES  # noqa: E402
from api import tree_local, tree_vps, tree_repo  # noqa: E402
from api.chat import chat_handler  # noqa: E402
```
**Do it like this:** add `from api import tools  # noqa: E402  — GET/PUT/DELETE /api/v1/tools`.

**(b) GET route — the correct `return`-terminated pattern (D-09)** — the `/api/v1/tree/*` branches are the model; each ends in `return` (`bin/invisible-dashboard:386-390`):
```python
if path == "/api/v1/tree/repo":
    q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
    project = q.get("project", [None])[0]
    self._send_json(tree_repo.walk_all(project=project))
    return
```
Contrast — the registry dispatch is MISSING its `return` (`bin/invisible-dashboard:364-365`), which is exactly why D-09 says avoid it:
```python
if path in API_V1_ROUTES:
    API_V1_ROUTES[path](self)        # ← no return; falls through to the 404 below
```
**Do it like this:** add, in `do_GET`, a `return`-terminated branch BEFORE the trailing `self._send_text("not found\n", 404)` (L407):
```python
if path == "/api/v1/tools":
    tools.handle_get(self)
    return
```

**(c) NEW `do_PUT` / `do_DELETE` — mirror `do_POST` (D-10)** — `do_POST` is the full template: auth gate → Content-Length cap (`_MAX_POST_BYTES = 32_768`, L431) → JSON-parse→400 → dispatch → 404 → last-resort try/except→500 (`bin/invisible-dashboard:433-492`):
```python
def do_POST(self) -> None:  # noqa: N802
    path = urllib.parse.urlparse(self.path).path
    if not self._auth_ok():                                   # --no-auth short-circuits
        sys.stderr.write(f"[dashboard] auth failed ... POST {path}\n")
        self._send_text("unauthorized\n", 401); return
    try:
        length = int(self.headers.get("Content-Length", "0") or "0")
    except ValueError:
        length = 0
    if length < 0: length = 0
    if length > self._MAX_POST_BYTES:
        self._send_json({"error": "message_too_large", ...}, 413); return   # → D-06 413
    raw = self.rfile.read(length) if length else b""
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        self._send_json({"error": "bad_request", "hint": "body must be JSON"}, 400); return
    try:
        if path == "/api/v1/chat":
            status, body = chat_handler(payload); self._send_json(body, status); return
        self._send_text("not found\n", 404)
    except Exception:  # noqa: BLE001 — last-resort guard
        import traceback; traceback.print_exc()
        self._send_json({"error": "server_error", ...}, 500)
```
**Do it like this:**
- `do_PUT`: copy `do_POST` verbatim, swap the dispatch to `if path == "/api/v1/tools": tools.handle_put(self); return`. Reuse `_auth_ok()` + the Content-Length cap + JSON-parse→400 (so malformed body → 400, oversized → 413, matching D-06). Pass the parsed `payload` (or let `handle_put` re-read — prefer passing it; the daemon already parsed it).
- `do_DELETE`: copy the auth-gate + last-resort try/except, but NO body read needed; dispatch `if path == "/api/v1/tools": tools.handle_delete(self); return`, else 404.
- Both end every handled branch with `return` and keep the traceback in stderr only.

**(d) CORS single-source (D-11) — the duplicate-ACAO bug** — `end_headers()` unconditionally sends `*` (`bin/invisible-dashboard:228-232`):
```python
def end_headers(self) -> None:
    self.send_header("Access-Control-Allow-Origin", "*")              # ← duplicate source
    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
    super().end_headers()
```
…while `_send_json` ALSO echoes the loopback Origin (`bin/invisible-dashboard:283-301`):
```python
def _send_json(self, obj: Any, status: int = 200) -> None:
    b = json.dumps(obj, indent=2).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(b)))
    self.send_header("Cache-Control", "no-store")
    origin = self.headers.get("Origin", "")
    if (origin.startswith("http://127.0.0.1:") or origin.startswith("http://localhost:")):
        self.send_header("Access-Control-Allow-Origin", origin)       # ← second ACAO
        self.send_header("Vary", "Origin")
    self.end_headers()        # ← end_headers() then adds `*` → TWO ACAO headers
    self.wfile.write(b)
```
**Do it like this (D-11):** Keep the loopback echo in `_send_json` as the SINGLE source. Remove the `Access-Control-Allow-Origin: *` line from `end_headers()` (and move `Access-Control-Allow-Methods`/`-Headers` so they don't double-emit either — simplest is to drop ACAO/ACAM/ACAH from `end_headers()` entirely and emit the full loopback-gated set once, consistently, in the response helpers + `do_OPTIONS`). Net: exactly ONE `Access-Control-Allow-Origin` per response, only for `http://127.0.0.1:*` / `http://localhost:*`. Verify in a real browser that :8090 → :8765 fetch is no longer rejected (mandatory per CONTEXT `<specifics>` + memory `feedback_verify_yourself`).

**(e) Collapse the TWO `do_OPTIONS` (D-12)** — Python keeps the LAST def. First def (`bin/invisible-dashboard:234-252`) handles `Access-Control-Max-Age` for `/api/v1/tree/`; second def (`bin/invisible-dashboard:409-427`) is loopback-gated and WINS but advertises only `GET, OPTIONS`:
```python
# def #2 (the one that actually runs) — L409-427:
def do_OPTIONS(self) -> None:  # noqa: N802
    origin = self.headers.get("Origin", "")
    self.send_response(204)
    if (origin.startswith("http://127.0.0.1:") or origin.startswith("http://localhost:")):
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")   # ← no PUT/DELETE
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
    self.send_header("Content-Length", "0")
    self.end_headers()
```
**Do it like this (D-12):** Delete the FIRST `do_OPTIONS` (L234-252). Edit the surviving one to advertise `Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS`, keep the loopback-only origin gate + `Vary: Origin` + `Access-Control-Max-Age`. This lets the browser preflight permit the autosave PUT and the DELETE.

**(f) `_auth_ok()` reference** (`bin/invisible-dashboard:266-271`) — already correct; both new methods just call it first:
```python
def _auth_ok(self) -> bool:
    if self.server.no_auth: return True
    expected = self.server.auth_token
    got = self._token_from_request() or ""
    return hmac.compare_digest(expected, got)
```

---

### `frontend/pages/tools.jsx` (EDIT — component, load + debounced autosave)

**Analog:** `frontend/pages/folders.jsx` (fetch scaffolding); plus the page's own existing state shape.

**Fetch template from folders.jsx** — `API_BASE`, `getToken()`, header construction, `fetch().then(r => ...)`, cancellation flag, `?project=` encoding (`frontend/pages/folders.jsx:14,23-28,114-124,191-196`):
```js
const API_BASE = "http://127.0.0.1:8765";               // L14
function getToken() {                                    // L23-28
  const u = new URLSearchParams(window.location.search).get("token");
  if (u) return u;
  if (window.INVISIBLE_TOKEN) return window.INVISIBLE_TOKEN;
  return "";
}
useEffectF(() => {                                       // L114-124
  const token = getToken();
  const headers = token ? { Authorization: "Bearer " + token } : {};
  const qs = effectiveProject ? "?project=" + encodeURIComponent(effectiveProject) : "";
  let cancelled = false;
  fetch(API_BASE + "/api/v1/tree/" + key + qs, { headers })
    .then((r) => r.json().then((body) => ({ ok: r.ok, status: r.status, body })))
    .then(({ ok, status, body }) => { if (cancelled) return; /* setState */ })
    .catch((err) => { if (cancelled) return; /* setError */ });
  return () => { cancelled = true; /* cleanup */ };       // L191-196
}, [effectiveProject]);
```
**Do it like this (D-13):** In `Tools` (or a thin wrapper), on `projId` change run a `useEffect` that `fetch(API_BASE + "/api/v1/tools?project=" + encodeURIComponent(projId), { headers })`, parse `{nodes,edges,updated_at}`, and feed `nodes`/`edges` into `ToolsCanvas` as `initialNodes`/`initialEdges`. Keep a `cancelled` flag + cleanup exactly like folders so a slow A-fetch can't paint after switching to B. (Deferred per CONTEXT: token handling follows folders' approach — `{ Authorization: "Bearer " + token }` when present.)

**Canvas internal state seeded from props + remount key** — `ToolsCanvas` owns `nodes`/`edges` and re-seeds on prop change; `Tools` forces a fresh canvas with `key={projId}` (`frontend/pages/tools.jsx:33-47,294-299`):
```js
function ToolsCanvas({ initialNodes, initialEdges, accentC }) {
  const [nodes, setNodes] = useStateTL(initialNodes);     // L34-35
  const [edges, setEdges] = useStateTL(initialEdges);
  useEffectTL(() => {                                      // L43-47 — re-seed on project change
    setNodes(initialNodes); setEdges(initialEdges); setSelected(null);
  }, [initialNodes, initialEdges]);
  ...
}
// in Tools (L294-299):
<ToolsCanvas key={projId /* force fresh canvas per project */}
  initialNodes={wf.nodes} initialEdges={wf.edges} accentC={project.color}/>
```
**Do it like this (D-14):** For autosave, the canvas must notify the parent of `nodes`/`edges` changes (the canvas currently owns them internally). Add an `onChange(nodes, edges)` callback prop OR lift state — then in the parent debounce 1s (`useRef` timer per Claude's-discretion) and PUT `{nodes,edges}` to `/api/v1/tools?project=` + projId with `{ method:"PUT", headers:{...headers, "Content-Type":"application/json"}, body: JSON.stringify({nodes,edges}) }`. CRITICAL: on `projId` change, `clearTimeout`/flush the pending timer in the effect cleanup so a save for A can't land on B. The autosave-trigger points are the existing mutators: `onDrop` (L84-92), drag-end via the `up` handler (L60), `endConnect` add-edge (L75-82), `removeSelected` (L95-100). Render a footer indicator ("saving…" / "saved Ns ago" / error) near the existing toolbar `chip` at L181 (`{nodes.length} nodes · {edges.length} wires`).

**`ProjectPicker` mock read (must change with D-15)** — reads the soon-deleted mock (`frontend/pages/tools.jsx:203,216`):
```js
const wf = TOOL_WORKFLOWS[p.id];                          // L203
const has = !!wf;
// L216:
{has ? `${wf.nodes.length} nodes · ${wf.edges.length} wires` : "no workflow yet"}
```
Also the `Tools` body reads it (`frontend/pages/tools.jsx:236`): `const wf = TOOL_WORKFLOWS[projId] || { name: ..., nodes: [], edges: [] };`.
**Do it like this (D-15):** `TOOL_WORKFLOWS` is being deleted, so these references break the page. Replace the picker preview with a neutral label ("open to view") OR fetch counts; and in `Tools`, derive `wf.name`/`nodes`/`edges` from the API fetch (D-13) instead of the mock. Removing the mock without fixing both call sites here is a runtime ReferenceError.

---

### `frontend/data.jsx` (EDIT — remove the mock, D-15)

**Analog:** itself (the const + the window assignment).

**The const to delete** (`frontend/data.jsx:170-...`, opens at L171, runs through the `atlas`/etc. entries):
```js
// Per-project tool workflows. Each project has its own n8n-style graph.
const TOOL_WORKFLOWS = {                                   // L171 — DELETE whole const
  echo:  { name: "Echo · ingest pipeline", nodes: [...], edges: [...] },
  lumen: { ... }, drift: { ... }, atlas: { ... }, ...
};
```
**The window-export to edit** (`frontend/data.jsx:460-461`):
```js
Object.assign(window, { ANALYTICS });
Object.assign(window, { DATA_SETS, FOLDERS, TOOL_WORKFLOWS, TERM_CONTEXT });   // L461 — drop TOOL_WORKFLOWS
```
**Do it like this (D-15):** Delete the entire `const TOOL_WORKFLOWS = {...}` block (L171 through its closing `};`), and remove the `TOOL_WORKFLOWS` token from the L461 `Object.assign` so it reads `Object.assign(window, { DATA_SETS, FOLDERS, TERM_CONTEXT });`. Leave `ANALYTICS` (L460) and the `fetchProjects` fetcher (L464-478) untouched — they belong to other features and `fetchProjects` is the in-file proof that the real-data fetch pattern lives here too.

> Reference — the real-data fetcher already in `data.jsx` (`frontend/data.jsx:464-476`) is a second valid fetch shape (`credentials: "omit"`, throws on `!ok`). `tools.jsx` should follow **folders.jsx's** header+token shape (D-13 says so explicitly), but this confirms the no-bundler `window.<X>` + fetch convention.

---

## Shared Patterns

### Generic-500 / no-leak error handling
**Source:** `lib/api/projects.py:301-321` (`handle_projects` try/except → `{"error":"internal error"}`, log only `type(exc).__name__` to stderr) + `bin/invisible-dashboard:482-492` (do_POST last-resort guard → traceback to stderr, `{"error":"server_error"}` 500).
**Apply to:** every `tools.py` handler AND the new `do_PUT`/`do_DELETE`. Never put a path or traceback in a response body.

### Path / input trust boundary
**Source:** `lib/api/projects.py:80-104` (`_safe_path` resolve-then-`is_relative_to`), slug shape at `:218-220` (`_id_for`).
**Apply to:** `tools.py` D-03 — but use the stricter validate-and-reject regex (`^[a-z0-9][a-z0-9_-]{0,63}$` → 400) for the attacker-controlled `project` query param, before any path construction.

### `config.home()` for all filesystem roots
**Source:** `lib/api/projects.py:94,100,259`.
**Apply to:** `tools.py` workflows dir — `config.home() / "workflows"`. Never hardcode `~/.invisible`.

### Auth gate first (so `--no-auth` short-circuits)
**Source:** `bin/invisible-dashboard:266-271` (`_auth_ok`), called first in `do_GET:320` and `do_POST:437`.
**Apply to:** new `do_PUT` and `do_DELETE` — first line after computing `path`.

### Loopback-only CORS, single source
**Source (the fix target):** `bin/invisible-dashboard:228-232` (`end_headers` `*`) + `283-301` (`_send_json` echo) + `409-427` (surviving `do_OPTIONS`).
**Apply to:** D-11/D-12 — collapse to ONE `Access-Control-Allow-Origin` (loopback echo), advertise `GET, POST, PUT, DELETE, OPTIONS`.

### No-bundler `window.<GLOBAL>` convention
**Source:** `frontend/data.jsx:460-461,478` (`Object.assign(window, {...})`), pages read globals directly (`tools.jsx:203` reads `TOOL_WORKFLOWS`, `frontend/pages/*.jsx` end with `window.X = X`).
**Apply to:** D-15 — removing a mock = delete the `const` AND its `Object.assign` token AND every reader.

### Frontend fetch + cancellation
**Source:** `frontend/pages/folders.jsx:14,23-28,114-124,191-196` (`API_BASE`, `getToken`, `Authorization: Bearer`, `cancelled` flag + cleanup).
**Apply to:** `tools.jsx` D-13 load and D-14 autosave; the cleanup-cancels-pending-work pattern is the mechanism that prevents project-A saves landing on B.

---

## No Analog Found (use stdlib / RESEARCH guidance)

| Concern | Why no in-repo analog | Guidance |
|---------|----------------------|----------|
| Atomic JSON write (`tempfile` + `os.replace` + `mkdir(parents=True, exist_ok=True)`) | `projects.py` and all `tree_*` modules are read-only; nothing in `lib/api/` writes to disk | Use the stdlib pattern shown in the `lib/api/tools.py` section (D-02). `os.replace` is atomic on the same filesystem; tmpfile must be in the SAME dir as the target. |
| `do_PUT` / `do_DELETE` HTTP methods | Daemon is GET+POST only today (it even documents "Writes. Everything is GET." at `bin/invisible-dashboard:25-26`) | Build them by mirroring `do_POST` (D-10). The "does NOT do writes" docstring at L24-30 is now stale — updating that comment is in-scope-adjacent and harmless. |
| Debounced autosave timer | No existing page autosaves | `useRef` timer + `clearTimeout` on cleanup (Claude's discretion, D-58). |

---

## Metadata

**Analog search scope:** `lib/api/` (projects, __init__, chat, tree_* referenced), `bin/invisible-dashboard`, `frontend/pages/{tools,folders}.jsx`, `frontend/data.jsx`.
**Files scanned (full reads):** 6 (`projects.py` 320L, `__init__.py` 39L, `invisible-dashboard` 546L, `tools.jsx` 305L, `folders.jsx` 252L, `data.jsx` targeted L165-219 + L455-478).
**Confirmed-present bugs the plan must fix:** duplicate `Access-Control-Allow-Origin` (D-11), duplicate `do_OPTIONS` defs (D-12), missing `return` after `API_V1_ROUTES[path](self)` (D-09 → route explicitly instead).
**Pattern extraction date:** 2026-06-01
