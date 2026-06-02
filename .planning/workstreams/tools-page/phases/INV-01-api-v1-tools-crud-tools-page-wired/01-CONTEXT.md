# Phase 1: /api/v1/tools CRUD + Tools page wired - Context

**Gathered:** 2026-06-01
**Status:** Ready for planning
**Source:** Pre-planning investigation — all START_HERE.md required reads completed, live `invisible-dashboard` daemon driven with curl to verify behavior, plus a user decision on CORS scope. Not a discuss-phase transcript; decisions below are evidence-backed.

<domain>
## Phase Boundary

**Delivers:** The Tools page (n8n-style node canvas) reads and writes **real**, per-project workflow definitions through a new `/api/v1/tools` CRUD endpoint, replacing the static `TOOL_WORKFLOWS` mock. Persistence is a tiny JSON file per project on disk at `~/.invisible/workflows/<project>.json` — no database, lock-free single-writer.

This is a **wiring phase**, not a design phase: the canvas UI (drag/drop, palette, wires, styling) already exists in `frontend/pages/tools.jsx`. The only new UI element is a small autosave status footer ("saving…" / "saved Ns ago"). Hence no UI-SPEC.md is required (planned with `--skip-ui`).

It mirrors the proven M1 pattern (dashboard-wiring / ai-bubble / folders-3source / analytics-aggregator): a new `lib/api/*.py` module + a tiny conflict surface (one import in `lib/api/__init__.py`, route registration in `bin/invisible-dashboard`, one mock removal in `frontend/data.jsx`).

## Out of bounds (scope fence — do NOT touch)

- `frontend/pages/{dashboard,focus,folders,relations,terminals,calendar,analytics}.jsx` and `frontend/ai-chat.jsx`
- Sibling APIs: `lib/api/{projects,chat,tree_local,tree_vps,tree_repo,analytics}.py`
- `src-tauri/`, `bin/invisible-pty`, `lib/pty_server.py`

Owned (write freely): `lib/api/tools.py` (new), `frontend/pages/tools.jsx`.
Edit lightly (shared 6-way merge surface — keep changes minimal & self-contained): `lib/api/__init__.py`, `bin/invisible-dashboard`, `frontend/data.jsx`, `.gitignore`.

</domain>

<decisions>
## Implementation Decisions

### Persistence & backend module (`lib/api/tools.py`)
- **D-01:** Persist each project's workflow at `config.home()/"workflows"/f"{project}.json"` (resolves to `~/.invisible/workflows/<project>.json`), deriving the root from `config.home()` exactly like `lib/api/projects.py` — never a hardcoded path.
- **D-02:** Writes are atomic and lock-free single-writer — serialize to a temp file in the same directory then `os.replace()` onto the target, and create the `workflows/` dir with `mkdir(parents=True, exist_ok=True)` on first write.
- **D-03:** [SECURITY] Validate the `project` query param as a strict slug (e.g. `^[a-z0-9][a-z0-9_-]{0,63}$`) BEFORE constructing any path; reject empty / `.` / `..` / slashes / other characters with HTTP 400 so no value can traverse outside `workflows/`.
- **D-04:** `lib/api/tools.py` mirrors `projects.py`'s shape — transport-agnostic `handle_*(handler)` functions that call `handler._send_json(obj, status)`, with every handler wrapping IO in try/except and returning a generic `{"error":"internal error"}` 500 that never leaks a filesystem path or traceback.

### HTTP contract (`/api/v1/tools`)
- **D-05:** GET `/api/v1/tools?project=<slug>` returns `{nodes, edges, updated_at}` — parse and return the file when present; when the file is missing return HTTP 200 with `{"nodes":[],"edges":[],"updated_at":null}` (empty workflow, NOT 404) so the canvas loads cleanly for never-saved projects; missing or invalid `project` → 400.
- **D-06:** PUT `/api/v1/tools?project=<slug>` accepts a JSON body `{nodes:[...],edges:[...]}`, validates both are lists, stamps a server-side `updated_at` (ISO-8601 UTC via `datetime.now(timezone.utc).isoformat()`), writes atomically, and returns at least `{"updated_at": <new value>}`; malformed body → 400, oversized body → 413.
- **D-07:** DELETE `/api/v1/tools?project=<slug>` removes the workflow file and returns 200 `{"deleted":true}`; if the file does not exist → 404.

### Daemon wiring (`bin/invisible-dashboard`, `lib/api/__init__.py`)
- **D-08:** Register the module by adding `from . import tools` to `lib/api/__init__.py` (matching the existing bottom-block import pattern used by `chat` and `tree_*`) and importing it in `bin/invisible-dashboard` alongside the other `from api import ...` lines.
- **D-09:** Add the GET route in `do_GET` as an explicit, `return`-terminated branch (`if path == "/api/v1/tools": tools.handle_get(self); return`) modeled on the existing `/api/v1/tree/*` branches — do NOT route it through the `API_V1_ROUTES[path](self)` dispatch, which is verified to be missing its `return` and falls through toward the trailing 404.
- **D-10:** Add NEW `do_PUT` and `do_DELETE` methods to `DashboardHandler`, each mirroring `do_POST` — call `_auth_ok()` first (so `--no-auth` still short-circuits), enforce the Content-Length cap + JSON-parse→400 for PUT, dispatch `/api/v1/tools` to `tools.handle_put` / `tools.handle_delete`, return 404 for unknown paths, and guard with a last-resort try/except → 500 that keeps the traceback out of the response body.

### CORS central fix (USER DECISION: "fix centrally" — `bin/invisible-dashboard`)
- **D-11:** [USER DECISION] Single-source the CORS headers so every response carries exactly ONE `Access-Control-Allow-Origin` — eliminate the duplicate-ACAO bug where `end_headers()` emits `*` while `_send_json` also echoes the loopback Origin; keep the loopback-only echo (`http://127.0.0.1:*` / `http://localhost:*`) as the single source, and confirm with a real browser that the cross-origin fetch from the frontend (:8090 → :8765) is no longer rejected.
- **D-12:** Collapse the two duplicate `do_OPTIONS` definitions into one and advertise `Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS` (preserving the loopback-only origin policy and `Access-Control-Max-Age`) so the browser preflight permits the autosave PUT and the DELETE.

### Frontend (`frontend/pages/tools.jsx`, `frontend/data.jsx`, `.gitignore`)
- **D-13:** `tools.jsx` loads the workflow via `fetch(API_BASE + "/api/v1/tools?project=" + projId)` on project switch (mirroring `frontend/pages/folders.jsx`'s `API_BASE = "http://127.0.0.1:8765"` + headers + loading/error handling), seeding the canvas from the fetched `{nodes,edges}` instead of `TOOL_WORKFLOWS[projId]`.
- **D-14:** Autosave — on every node add / drag-end / wire add or remove, debounce 1s then PUT `{nodes,edges}`; cancel or flush any pending timer on project switch so a save for project A can never land on project B; render a footer indicator with "saving…", "saved Ns ago", and an error state.
- **D-15:** Remove the `TOOL_WORKFLOWS` mock entirely from `frontend/data.jsx` — delete the `const TOOL_WORKFLOWS` (~line 171) AND drop `TOOL_WORKFLOWS` from the `Object.assign(window, {...})` (line 461) — and update `ProjectPicker`'s "N nodes · M wires" preview so it no longer reads the deleted mock (fetch counts or show a neutral "open to view" label).
- **D-16:** Add `workflows/` to `.gitignore` (per-machine state; the daemon creates it under the repo root whenever it runs with `INVISIBLE_HOME=$(pwd)` inside a worktree).

### Claude's Discretion
- The exact response envelope beyond the required keys (e.g. whether PUT also echoes `nodes`/`edges` or returns counts) — keep it minimal.
- Debounce implementation detail (a `useRef` timer vs a tiny helper) and whether drag autosave fires only on drag-end (recommended) vs throttled mid-drag.
- The precise slug regex character set, as long as it provably blocks traversal (D-03).
- Whether `tools.py` exposes three `handle_get/put/delete` functions or one `handle_tools(handler, method)` dispatcher.
- The exact footer copy/relative-time formatting, within the page's existing design tokens.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Backend pattern (closest analog)
- `lib/api/projects.py` — the sibling module to mirror: `build_*()` + `handle_*(handler)`, `handler._send_json(...)`, `config.home()` usage, defensive try/except → generic 500, and `_safe_path()` as the trust-boundary analog for D-03's slug validation.
- `lib/api/__init__.py` — the import-registration pattern; note the bottom-block `from . import chat / tree_local / ...` where the new `from . import tools` belongs.

### Daemon wiring + CORS surface
- `bin/invisible-dashboard` — `DashboardHandler`: `do_POST` (the auth-gate + body-cap + JSON-parse + dispatch template to copy for `do_PUT`/`do_DELETE`), `do_GET`'s `/api/v1/tree/*` branches (the correct `return`-terminated route pattern), the TWO `do_OPTIONS` defs (collapse → one), `_send_json` + the `end_headers()` override (the duplicate-ACAO source), and `_auth_ok()`.

### Frontend
- `frontend/pages/tools.jsx` — the component being wired: `ToolsCanvas` currently owns `nodes`/`edges` in internal state seeded from `initialNodes/initialEdges` (needs a change-notification or controlled-state refactor for autosave); `ProjectPicker` reads `TOOL_WORKFLOWS[p.id]` for its preview; `Tools` receives `{projects, selectedProject, setSelectedProject}`.
- `frontend/pages/folders.jsx` — sibling fetch pattern: `API_BASE`, request headers, loading/error states (and SSE, for reference only).
- `frontend/data.jsx` — `const TOOL_WORKFLOWS` (~line 171) and the `Object.assign(window, { ... TOOL_WORKFLOWS ... })` (line 461) to remove.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets
- `projects.py` helpers: `_id_for()` slug style, `config.home()`, the `_send_json`-based handler contract — directly reusable shapes for `tools.py`.
- `folders.jsx` fetch scaffolding (`API_BASE`, headers, error handling) — the template for `tools.jsx`'s load + save calls.

### Established patterns
- API modules are transport-agnostic; the daemon's `do_GET`/`do_POST` call `handler._send_json`. Routes that `return` after handling are correct; the `API_V1_ROUTES` registry path currently does NOT `return` (latent double-write — avoid it for new routes).
- Frontend is Babel-standalone React with globals on `window` (no bundler); pages read mock data via `window.<MOCK>` assigned in `data.jsx`. Removing a mock means deleting both the `const` and its `Object.assign(window, …)` entry.

### Integration points
- New HTTP surface: `do_GET` (GET branch), new `do_PUT`, new `do_DELETE`, `do_OPTIONS` (methods advertisement), `lib/api/__init__.py` (import).
- `ProjectPicker` in `tools.jsx` depends on the mock for its node/wire counts — touching D-15 requires updating it so the picker keeps rendering.

</code_context>

<specifics>
## Specific Ideas — verified evidence (drove the decisions above)

Confirmed against the **live** daemon (`./bin/invisible-dashboard --no-auth --port 8799`, curl):
- A `GET /api/v1/projects` with `Origin: http://127.0.0.1:8090` returns **two** `Access-Control-Allow-Origin` headers (`http://127.0.0.1:8090` AND `*`) → browsers reject multi-valued ACAO. Root: `end_headers()` adds `*` on every response while `_send_json` also echoes the Origin. (→ D-11)
- `OPTIONS /api/v1/tools` advertises only `Access-Control-Allow-Methods: GET, OPTIONS` and `GET, POST, OPTIONS` (two headers, neither lists PUT/DELETE). `do_OPTIONS` is defined twice; the second (line ~409) wins. (→ D-12)
- After `API_V1_ROUTES[path](self)` in `do_GET` there is no `return`; the projects response is clean only because Content-Length-honoring clients ignore the trailing bytes. (→ D-09)

## Verify locally (backend, from ROADMAP)
```bash
PROJECT=jobslayer
curl -X PUT -H 'Content-Type: application/json' \
  "http://127.0.0.1:8765/api/v1/tools?project=$PROJECT" \
  -d '{"nodes":[{"id":"a","kind":"Claude"}],"edges":[]}' | python3 -m json.tool
curl -s "http://127.0.0.1:8765/api/v1/tools?project=$PROJECT" | python3 -m json.tool
curl -X DELETE "http://127.0.0.1:8765/api/v1/tools?project=$PROJECT"
# traversal must be rejected (expect 400, NOT a write outside workflows/):
curl -s -o /dev/null -w '%{http_code}\n' "http://127.0.0.1:8765/api/v1/tools?project=../etc"
```

## Verify in a real browser (MANDATORY — see memory `feedback_verify_yourself`)
Drive with Playwright / chrome-devtools-mcp against the running frontend (:8090): open Tools → pick a project → confirm the canvas loads from the API (network tab shows the GET, no CORS error) → add/drag a node → observe the debounced PUT fire and the footer move "saving…" → "saved" → reload and confirm persistence → switch projects and confirm no state bleed and a clean per-project load. Don't hand back a manual checklist for what can be automated.

</specifics>

<deferred>
## Deferred Ideas

- Deep validation/normalization of the internal node/edge shape — the canvas defines that shape; the backend is intentionally a dumb blob store that only checks the top-level `{nodes:list, edges:list}` envelope.
- Frontend auth-token handling when the daemon is NOT run with `--no-auth` — follow whatever `folders.jsx` does (consistency over new behavior); a real token UX is out of scope.
- Any CORS work beyond the shared single-source fix (the central fix in D-11/D-12 incidentally repairs the already-merged sibling pages; no per-endpoint CORS work is in scope).
- Multi-writer concurrency / file locking — explicitly out of scope (lock-free single-writer per project is the chosen model).

</deferred>

---

*Phase: 01-api-v1-tools-crud-tools-page-wired*
*Context gathered: 2026-06-01 (pre-planning investigation + user CORS decision)*
