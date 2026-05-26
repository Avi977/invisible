---
phase: INV-01-three-tree-endpoints-live-folders-page
plan: 03
type: execute
wave: 2
depends_on:
  - INV-01-01
  - INV-01-02
files_modified:
  - lib/api/__init__.py
  - bin/invisible-dashboard
  - frontend/pages/folders.jsx
autonomous: false
requirements:
  - REQ-03
tags:
  - http-routes
  - sse-client
  - eventsource
  - react
  - cors

must_haves:
  truths:
    - "frontend/pages/folders.jsx fetches all three endpoints on mount and renders them in three columns matching the existing visual."
    - "GET /api/v1/tree/local returns 200 with a JSON list of project trees, matching the {name,type,children?,badge?,open?} shape."
    - "GET /api/v1/tree/repo returns 200 with a JSON list of repo trees."
    - "GET /api/v1/tree/vps returns 503 with {\"error\":\"vps.host not configured\"} when vps.host is empty; otherwise 200 with the tree."
    - "GET /api/v1/tree/local?watch=1 streams SSE diff events; the UI updates within 5s of a filesystem change without a page reload."
    - "EventSource cannot set Authorization headers — the watch endpoint accepts ?token=<t> (mirroring the dashboard's existing query-param fallback pattern)."
    - "Dashboard JSON responses (_send_json) and SSE responses include Access-Control-Allow-Origin: * so the browser on :8090 can call/subscribe to the dashboard on :8765. OPTIONS preflight on /api/v1/tree/* returns 204 with the CORS headers."
    - "EventSource error storms are bounded: 3 consecutive errors with no intervening snapshot/diff surfaces a column-level placeholder ('Local stream disconnected — check daemon')."
    - "Per-project filtering works: ?project=<name> on any of the three endpoints returns only that project's subtree."
    - "Clicking a project in the dashboard's Dive in → Folders link focuses only that project's subtree (via the project query param)."
  artifacts:
    - path: "lib/api/__init__.py"
      provides: "Package marker exposing tree_local, tree_vps, tree_repo for clean imports"
      min_lines: 5
      contains: "from . import tree_local"
    - path: "bin/invisible-dashboard"
      provides: "Three new route branches in do_GET for /api/v1/tree/{local,vps,repo} plus the SSE watch branch, CORS headers on _send_json, and an OPTIONS preflight branch"
      contains: "/api/v1/tree/local"
    - path: "frontend/pages/folders.jsx"
      provides: "Real fetch + EventSource wiring replacing the FOLDERS mock, with bounded reconnect-error counter"
      contains: "fetch('/api/v1/tree/"
  key_links:
    - from: "frontend/pages/folders.jsx"
      to: "/api/v1/tree/{local,vps,repo}"
      via: "fetch() on mount with bearer token from URL ?token= param"
      pattern: "fetch\\(.*api/v1/tree"
    - from: "frontend/pages/folders.jsx"
      to: "/api/v1/tree/local?watch=1&token=<t>"
      via: "new EventSource(...) subscription"
      pattern: "new EventSource"
    - from: "bin/invisible-dashboard:do_GET"
      to: "lib/api/tree_local::stream_diffs"
      via: "if path == '/api/v1/tree/local' and query['watch']==['1']: tree_local.stream_diffs(self, project=...)"
      pattern: "stream_diffs"
    - from: "bin/invisible-dashboard:_send_json"
      to: "browser CORS preflight"
      via: "Access-Control-Allow-Origin/Headers/Methods on every JSON response + dedicated do_OPTIONS or in-line OPTIONS branch for /api/v1/tree/*"
      pattern: "Access-Control-Allow-Origin"
---

<objective>
Wire the three walkers from Plans 01 and 02 into the dashboard's HTTP routes, add CORS headers so the cross-port browser can actually consume them, and replace the `FOLDERS` mock in `frontend/pages/folders.jsx` with live fetches plus an SSE subscription for the local source.

Purpose: Plans 01 and 02 produced backend modules but no HTTP routes. Without this plan, none of the success criteria can be verified end-to-end. Additionally, the frontend runs on `127.0.0.1:8090` while the dashboard runs on `127.0.0.1:8765` — without CORS headers on the dashboard's responses the browser silently blocks every fetch and EventSource. This plan delivers the user-visible outcome: three real columns in the Folders page that update when files change.

Output:
- `lib/api/__init__.py` (new, makes `lib/api/` a Python package).
- Three new route branches plus one SSE branch in `bin/invisible-dashboard:do_GET`.
- CORS headers (`Access-Control-Allow-Origin/Headers/Methods`) added to `_send_json`, plus an `OPTIONS` preflight branch covering `/api/v1/tree/*`. (The SSE CORS header is added in Plan 01's `stream_diffs` directly.)
- A rewritten `frontend/pages/folders.jsx` that fetches on mount, subscribes to the local SSE stream, handles loading / empty / error / 503-vps states, and surfaces a column-level placeholder after 3 consecutive EventSource errors.

This plan contains a human-verification checkpoint at the end because the SSE 5-second-latency requirement and the <1s cold-load requirement are fundamentally perceptual UX checks.
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

@.planning/workstreams/folders-3source/phases/INV-01-three-tree-endpoints-live-folders-page/INV-01-01-SUMMARY.md
@.planning/workstreams/folders-3source/phases/INV-01-three-tree-endpoints-live-folders-page/INV-01-02-SUMMARY.md

@frontend/pages/folders.jsx
@frontend/data.jsx
@frontend/index.html
@bin/invisible-dashboard

<interfaces>
<!-- Functions to import from the Wave 1 modules — extracted from this plan's depends_on. -->

From lib/api/tree_local.py (Plan 01):
- `walk_all(project: str | None = None) -> list[dict]`  — JSON-serializable tree list
- `walk_project(name: str) -> dict | None`              — single project tree
- `stream_diffs(handler, project: str | None = None) -> None`  — SSE loop; takes the BaseHTTPRequestHandler and blocks until client disconnect. Emits `snapshot`, `diff`, `error` event types. Emits `Access-Control-Allow-Origin: *` in its own response headers (Plan 01 Task 2 fix).

From lib/api/tree_repo.py (Plan 02):
- `walk_all(project: str | None = None) -> list[dict]`  — list of `{name: "@owner/repo", type: "folder", ...}` nodes

From lib/api/tree_vps.py (Plan 02):
- `walk_all(project: str | None = None) -> tuple[list[dict], int]`  — `(payload, status_code)`. status 503 when vps.host empty.
- `VPS_NOT_CONFIGURED: dict`  — `{"error": "vps.host not configured"}` (re-used in the route only if you want to double-check the contract)

DashboardHandler internals (bin/invisible-dashboard:212-316):
- `self._auth_ok() -> bool`               — bearer-token check (applies to SSE too — call before stream_diffs!)
- `self._token_from_request() -> str|None` — pulls token from Authorization header or `?token=` param
- `self._send_json(obj, status=200)`       — JSON response helper (THIS plan adds CORS headers here)
- `self._send_text(body, status=200)`      — text/plain response helper
- `self.wfile`                              — raw socket writer (used by stream_diffs directly)
- routing pattern: chain of `if path == '...':` branches in `do_GET` — new branches go after the `/api/reviews` branch at line ~309 and before the `_send_text("not found\n", 404)` fallback at line ~315

Frontend constraints (frontend/index.html:13-37):
- Babel-standalone, no build step. JSX is interpreted at runtime.
- React 18 UMD; hooks accessed via `React.useState`, `React.useEffect`, etc.
- frontend/pages/folders.jsx uses `const { useState: useStateF } = React;` — add `useEffect: useEffectF, useRef: useRefF` to the same destructure.
- Page is served by `bin/invisible-frontend` on :8090; the dashboard daemon is on :8765 with CORS headers added by THIS plan (BLOCKER #1 from checker pass — CORS must come from the dashboard, the resource being requested, not from the frontend, the page making the request).
- No prior page has wired real fetches yet — folders.jsx is the pioneer. Mint the token-passing convention here.

Token-passing convention (NEW — established in this plan):
- The Babel page reads `new URLSearchParams(window.location.search).get('token')` once on mount.
- Falls back to `window.INVISIBLE_TOKEN` if not in URL (lets a future bootstrap inject it).
- For fetch: pass as `Authorization: Bearer <t>` header. **Triggers a CORS preflight** because Authorization is not a CORS-safelisted header — the dashboard's OPTIONS branch (added in Task 1) handles it.
- For EventSource: append as `?token=<t>` query param (EventSource cannot set headers; the dashboard's `_token_from_request` already accepts the query-param form).

Dashboard URL composition:
- The dashboard's HTTP base is `http://127.0.0.1:8765` (different port from the frontend's :8090).
- Hardcode the base in folders.jsx as a constant `const API_BASE = "http://127.0.0.1:8765";` at the top of the file. A future plan can move this into a shared config; for now, this is the minimum viable wiring.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create lib/api/__init__.py, add CORS to dashboard JSON + OPTIONS preflight, register four new routes</name>
  <files>lib/api/__init__.py, bin/invisible-dashboard</files>
  <read_first>
    - lib/api/tree_local.py (verify the exact function signatures — `walk_all`, `walk_project`, `stream_diffs`)
    - lib/api/tree_vps.py (verify `walk_all` returns the (payload, status) tuple)
    - lib/api/tree_repo.py (verify `walk_all` returns a plain list)
    - bin/invisible-dashboard:50-60 (the sys.path insert that makes `lib/` importable)
    - bin/invisible-dashboard:248-255 (the `_send_json` helper — THIS is where CORS headers get added)
    - bin/invisible-dashboard:266-316 (the do_GET routing chain — insertion point is after the `/api/reviews` branch at ~line 309 and before the `_send_text("not found\n", 404)` fallback at ~line 315)
  </read_first>
  <action>
    **Step A — Create `lib/api/__init__.py`** (new file):
    ```
    """API submodules consumed by bin/invisible-dashboard.

    Each submodule is responsible for a single data source. The dashboard's
    do_GET wires them into HTTP routes; the submodules themselves are
    transport-agnostic (with the documented exception of tree_local.stream_diffs,
    which writes SSE chunks directly to the handler's wfile).
    """
    from . import tree_local  # noqa: F401
    from . import tree_vps    # noqa: F401
    from . import tree_repo   # noqa: F401
    ```
    Three imports. Nothing else. This makes `lib/api/` a package so the dashboard can do `from api import tree_local, tree_vps, tree_repo`.

    **Step B — Edit `bin/invisible-dashboard`:**

    1. After the existing `from config import home, load_env` import block at line ~58, add:
       ```
       from api import tree_local, tree_vps, tree_repo  # noqa: E402
       ```
       Place it after `from dashboard_render import ...` so the import order matches the existing convention (config first, app modules next).

    2. **CORS fix on `_send_json` (BLOCKER #1).** Locate the `_send_json` helper (line ~248). Before `self.end_headers()` (line ~254), insert three response headers so cross-origin browser fetches from the frontend on :8090 are not silently blocked:
       ```
       self.send_header("Access-Control-Allow-Origin", "*")
       self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
       self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
       ```
       Rationale: the frontend's `Authorization: Bearer <token>` header is not CORS-safelisted, so every `/api/v1/tree/*` fetch will trigger a preflight `OPTIONS` request. Without `Access-Control-Allow-Origin` on the response, the browser blocks the actual `GET` even if the server replied 200.

    3. **OPTIONS preflight branch.** Add a `do_OPTIONS` method on `DashboardHandler` (next to `do_GET`), OR add an OPTIONS branch at the top of `do_GET` keyed off `self.command == "OPTIONS"`. Preferred: dedicated `do_OPTIONS` method (cleaner, doesn't pollute the GET routing chain):
       ```
       def do_OPTIONS(self) -> None:  # noqa: N802
           path = urllib.parse.urlparse(self.path).path
           # Preflight for cross-origin GETs to the tree endpoints.
           if path.startswith("/api/v1/tree/"):
               self.send_response(204)
               self.send_header("Access-Control-Allow-Origin", "*")
               self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
               self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
               self.send_header("Access-Control-Max-Age", "600")
               self.end_headers()
               return
           # Fallback: no preflight for non-API paths.
           self.send_response(204)
           self.end_headers()
       ```
       Note: `do_OPTIONS` is INTENTIONALLY NOT auth-gated — preflight requests do not carry the Authorization header (that's the whole point of the preflight), so requiring auth would 401 the preflight and break every cross-origin call.

    4. In `do_GET` (line ~266), after the `/api/reviews` branch (ends at line ~313) and BEFORE the `self._send_text("not found\n", 404)` fallback (line ~315), insert these branches in this exact order:

       ```
       # Three-source tree endpoints (REQ-03).
       if path == "/api/v1/tree/local":
           q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
           project = q.get("project", [None])[0]
           if q.get("watch") == ["1"]:
               # SSE — stream_diffs blocks until client disconnect.
               # Auth was already checked at the top of do_GET via _auth_ok().
               # stream_diffs emits its OWN CORS header in its response header block (Plan 01).
               try:
                   tree_local.stream_diffs(self, project=project)
               except (BrokenPipeError, ConnectionResetError):
                   pass  # client went away; nothing to do
               return
           self._send_json(tree_local.walk_all(project=project))
           return

       if path == "/api/v1/tree/repo":
           q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
           project = q.get("project", [None])[0]
           self._send_json(tree_repo.walk_all(project=project))
           return

       if path == "/api/v1/tree/vps":
           q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
           project = q.get("project", [None])[0]
           payload, status = tree_vps.walk_all(project=project)
           self._send_json(payload, status=status)
           return
       ```

       The watch sub-branch is folded into the `/api/v1/tree/local` branch so the routing chain stays one-conditional-per-path.

    5. Verify by reading the surrounding code that the `_auth_ok()` check at line ~274 ALREADY guards every `/api/*` path, including these new ones (do_GET only; `do_OPTIONS` deliberately bypasses it). Add a comment in the SSE branch noting this dependency.

    Do not modify any other part of `bin/invisible-dashboard`. The diff should be: 1 import line + 3 CORS header lines inside `_send_json` + 1 new `do_OPTIONS` method (~15 lines) + 1 contiguous block of ~25 lines inside `do_GET`. Keep the file under 420 total lines.
  </action>
  <verify>
    <automated>cd "$INVISIBLE_HOME" && python3 -c "import sys; sys.path.insert(0, 'lib'); from api import tree_local, tree_vps, tree_repo; assert callable(tree_local.walk_all) and callable(tree_local.stream_diffs); assert callable(tree_vps.walk_all); assert callable(tree_repo.walk_all); print('package OK')" && grep -v '^[[:space:]]*#' "$INVISIBLE_HOME/bin/invisible-dashboard" | grep -c "/api/v1/tree/" | awk '$1 < 3 {print "FAIL: expected >=3 /api/v1/tree/ routes, got " $1; exit 1} {print "routes OK (" $1 " matches)"}' && grep -q 'Access-Control-Allow-Origin' "$INVISIBLE_HOME/bin/invisible-dashboard" || { echo "FAIL: dashboard missing Access-Control-Allow-Origin header"; exit 1; } && grep -q 'do_OPTIONS' "$INVISIBLE_HOME/bin/invisible-dashboard" || { echo "FAIL: dashboard missing do_OPTIONS preflight handler"; exit 1; } && echo "CORS scaffolding OK"</automated>
  </verify>
  <done>
    - `lib/api/__init__.py` exists with the three `from . import` lines.
    - `bin/invisible-dashboard` imports `tree_local, tree_vps, tree_repo` from the `api` package.
    - `_send_json` emits `Access-Control-Allow-Origin: *`, `Access-Control-Allow-Headers: Authorization, Content-Type`, `Access-Control-Allow-Methods: GET, OPTIONS` on every response (BLOCKER #1 fix).
    - `do_OPTIONS` method exists; returns 204 with the three CORS headers + `Access-Control-Max-Age: 600` for any `/api/v1/tree/*` preflight. NOT auth-gated.
    - `do_GET` contains the three new path branches (`/api/v1/tree/local`, `/api/v1/tree/repo`, `/api/v1/tree/vps`) plus the inline SSE handling for `?watch=1`.
    - `python3 -c "from api import tree_local, tree_vps, tree_repo"` (with lib/ on sys.path) succeeds.
    - The daemon can be started with `bin/invisible-dashboard` and the routes return data with CORS headers — verified by Task 2's curl assertions.
  </done>
</task>

<task type="auto">
  <name>Task 2: Smoke-test all four routes + CORS preflight + cold-load timing</name>
  <files>(no file modifications — runs the daemon and curls it)</files>
  <read_first>
    - bin/invisible-dashboard (verify your route additions, CORS headers, and do_OPTIONS from Task 1 are present)
    - lib/api/tree_vps.py (confirm `VPS_NOT_CONFIGURED` is the 503 body the curl assertion expects)
  </read_first>
  <action>
    Start the daemon in the background, capture the auto-generated token, and run a battery of curl assertions covering JSON contracts, CORS headers, OPTIONS preflight, the SSE stream, the auth gate, and cold-load timing. Tear down at the end.

    Step 1 — Start the daemon with a known token:
    ```
    export T="test-token-$(uuidgen 2>/dev/null || python3 -c 'import secrets;print(secrets.token_hex(8))')"
    INVISIBLE_DASHBOARD_TOKEN="$T" "$INVISIBLE_HOME/bin/invisible-dashboard" --host 127.0.0.1 --port 8765 >/tmp/inv-dash.log 2>&1 &
    DASH_PID=$!
    for i in 1 2 3 4 5 6 7 8 9 10; do
      curl -sf http://127.0.0.1:8765/healthz >/dev/null && break
      sleep 0.5
    done
    ```

    Step 2 — Local tree contract:
    ```
    curl -sf -H "Authorization: Bearer $T" http://127.0.0.1:8765/api/v1/tree/local \
      | python3 -c 'import sys,json; t=json.load(sys.stdin); assert isinstance(t,list), f"expected list, got {type(t)}"; assert all("name" in n and "type" in n for n in t), f"nodes must have name+type: {t[:1]}"; print("local OK", len(t), "projects")'
    ```

    Step 3 — Repo tree contract (cache-friendly; OK if empty):
    ```
    curl -sf -H "Authorization: Bearer $T" http://127.0.0.1:8765/api/v1/tree/repo \
      | python3 -c 'import sys,json; t=json.load(sys.stdin); assert isinstance(t,list), f"expected list, got {type(t)}"; print("repo OK", len(t), "repos")'
    ```

    Step 4 — VPS 503 (the headline graceful-degradation test):
    ```
    STATUS=$(curl -s -o /tmp/vps-body.json -w "%{http_code}" -H "Authorization: Bearer $T" http://127.0.0.1:8765/api/v1/tree/vps)
    test "$STATUS" = "503" || { echo "FAIL: expected 503 for empty vps.host, got $STATUS"; cat /tmp/vps-body.json; exit 1; }
    grep -q '"error"' /tmp/vps-body.json || { echo "FAIL: vps 503 body must contain \"error\" key"; cat /tmp/vps-body.json; exit 1; }
    grep -q 'vps.host not configured' /tmp/vps-body.json || { echo "FAIL: vps 503 body must mention vps.host"; cat /tmp/vps-body.json; exit 1; }
    echo "vps 503 OK"
    ```

    Step 5 — CORS headers on GET (BLOCKER #1 assertion):
    ```
    curl -s -H "Origin: http://127.0.0.1:8090" -H "Authorization: Bearer $T" -I http://127.0.0.1:8765/api/v1/tree/local \
      | grep -qi "access-control-allow-origin: \*" \
      || { echo "FAIL: /api/v1/tree/local missing Access-Control-Allow-Origin: *"; exit 1; }
    echo "cors-get OK"
    ```

    Step 6 — CORS preflight (OPTIONS) returns 204:
    ```
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X OPTIONS \
      -H "Origin: http://127.0.0.1:8090" \
      -H "Access-Control-Request-Method: GET" \
      -H "Access-Control-Request-Headers: authorization" \
      http://127.0.0.1:8765/api/v1/tree/local)
    test "$STATUS" = "204" || { echo "FAIL: OPTIONS preflight expected 204, got $STATUS"; exit 1; }
    curl -s -X OPTIONS -H "Origin: http://127.0.0.1:8090" -H "Access-Control-Request-Method: GET" -H "Access-Control-Request-Headers: authorization" -I http://127.0.0.1:8765/api/v1/tree/local \
      | grep -qi "access-control-allow-headers:.*authorization" \
      || { echo "FAIL: OPTIONS response missing access-control-allow-headers: authorization"; exit 1; }
    echo "cors-preflight OK"
    ```

    Step 7 — SSE smoke test (does the snapshot frame arrive? does SSE response include CORS?):
    ```
    # CORS header on SSE (Plan 01 added it in stream_diffs):
    curl -s --max-time 2 -H "Origin: http://127.0.0.1:8090" -I "http://127.0.0.1:8765/api/v1/tree/local?watch=1&token=$T" \
      | grep -qi "access-control-allow-origin: \*" \
      || { echo "FAIL: SSE response missing Access-Control-Allow-Origin: *"; exit 1; }
    echo "cors-sse OK"

    timeout 4 curl -sN "http://127.0.0.1:8765/api/v1/tree/local?watch=1&token=$T" > /tmp/sse.log &
    SSE_PID=$!
    sleep 2
    # If a configured project exists, touch a file inside it; the diff event should arrive within ~3s
    PROJ_PATH=$(python3 -c 'import sys; sys.path.insert(0,"'"$INVISIBLE_HOME"'/lib"); from config import load_toml; import os; cfg=load_toml(); p=cfg.get("projects",[]); print(os.path.expanduser(p[0]["repo_path"]) if p else "")')
    if [ -n "$PROJ_PATH" ] && [ -d "$PROJ_PATH" ]; then
      touch "$PROJ_PATH/inv-sse-probe.tmp"
      sleep 2
      rm -f "$PROJ_PATH/inv-sse-probe.tmp"
    fi
    wait $SSE_PID 2>/dev/null
    grep -q "event: snapshot" /tmp/sse.log || { echo "FAIL: no snapshot event in SSE output"; head -20 /tmp/sse.log; exit 1; }
    echo "sse OK"
    ```
    (The diff-event assertion is intentionally soft — the touch+remove dance may race with the SSE handshake on slow machines. The snapshot frame arriving is the hard contract; the diff event is verified perceptually in Task 4.)

    Step 8 — Auth gate:
    ```
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/api/v1/tree/local)
    test "$STATUS" = "401" || { echo "FAIL: no-token request must 401, got $STATUS"; exit 1; }
    echo "auth gate OK"
    ```

    Step 9 — Cold-load timing (REQ-03 "<1s per source for projects under 1k files" — soft check):
    ```
    # Warm the path (avoid TCP slow-start being counted as the cold-load cost):
    curl -sf -H "Authorization: Bearer $T" http://127.0.0.1:8765/healthz >/dev/null
    # Measure local-tree fetch:
    LOCAL_MS=$( { time -p curl -sf -H "Authorization: Bearer $T" http://127.0.0.1:8765/api/v1/tree/local >/dev/null; } 2>&1 | awk '/^real/ {printf "%d", $2 * 1000}' )
    echo "local-tree fetch: ${LOCAL_MS}ms"
    # Soft assertion: warn (not fail) if >1000ms — the hard <1s check is the Task 4 human-verify stopwatch
    # against a project with <1k files. CI / large local projects may legitimately exceed this.
    test "${LOCAL_MS:-9999}" -lt 1500 || echo "WARN: local-tree took ${LOCAL_MS}ms — investigate if project has <1k files"
    ```

    Step 10 — Teardown:
    ```
    kill $DASH_PID 2>/dev/null
    wait $DASH_PID 2>/dev/null
    ```

    If any step fails, dump `/tmp/inv-dash.log` to stderr before exiting non-zero so the failure is diagnosable.

    Wrap the whole thing in a single shell script invocation (do not split across Bash tool calls — context-cheaper to keep it one block, and the daemon must stay alive for the duration).
  </action>
  <verify>
    <automated>bash -c 'set -e; export T="inv-test-$(python3 -c "import secrets; print(secrets.token_hex(8))")"; INVISIBLE_DASHBOARD_TOKEN="$T" "$INVISIBLE_HOME/bin/invisible-dashboard" --host 127.0.0.1 --port 8765 >/tmp/inv-dash.log 2>&1 & DASH_PID=$!; trap "kill $DASH_PID 2>/dev/null; wait $DASH_PID 2>/dev/null" EXIT; for i in 1 2 3 4 5 6 7 8 9 10; do curl -sf http://127.0.0.1:8765/healthz >/dev/null && break; sleep 0.5; done; curl -sf -H "Authorization: Bearer $T" http://127.0.0.1:8765/api/v1/tree/local | python3 -c "import sys,json; t=json.load(sys.stdin); assert isinstance(t,list); assert all(\"name\" in n and \"type\" in n for n in t)"; curl -sf -H "Authorization: Bearer $T" http://127.0.0.1:8765/api/v1/tree/repo | python3 -c "import sys,json; t=json.load(sys.stdin); assert isinstance(t,list)"; STATUS=$(curl -s -o /tmp/vps-body.json -w "%{http_code}" -H "Authorization: Bearer $T" http://127.0.0.1:8765/api/v1/tree/vps); test "$STATUS" = "503"; grep -q "vps.host not configured" /tmp/vps-body.json; curl -s -H "Origin: http://127.0.0.1:8090" -H "Authorization: Bearer $T" -I http://127.0.0.1:8765/api/v1/tree/local | grep -qi "access-control-allow-origin: \*"; STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X OPTIONS -H "Origin: http://127.0.0.1:8090" -H "Access-Control-Request-Method: GET" -H "Access-Control-Request-Headers: authorization" http://127.0.0.1:8765/api/v1/tree/local); test "$STATUS" = "204"; curl -s --max-time 2 -H "Origin: http://127.0.0.1:8090" -I "http://127.0.0.1:8765/api/v1/tree/local?watch=1&token=$T" | grep -qi "access-control-allow-origin: \*"; STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/api/v1/tree/local); test "$STATUS" = "401"; timeout 4 curl -sN "http://127.0.0.1:8765/api/v1/tree/local?watch=1&token=$T" > /tmp/sse.log || true; grep -q "event: snapshot" /tmp/sse.log; echo ALL_OK'</automated>
  </verify>
  <done>
    - All four routes respond as designed: `/local` and `/repo` return 200+JSON list; `/vps` returns 503 with the configured error body; `/local?watch=1` streams an initial `event: snapshot` frame.
    - JSON GET responses include `Access-Control-Allow-Origin: *` (BLOCKER #1 fix verified).
    - OPTIONS preflight to `/api/v1/tree/local` returns 204 with `Access-Control-Allow-Headers: Authorization` (BLOCKER #1 fix verified).
    - SSE response includes `Access-Control-Allow-Origin: *` (Plan 01 Task 2 fix verified end-to-end).
    - The auth gate returns 401 for requests without a token.
    - Cold-load timing for `/api/v1/tree/local` is logged (soft check; hard <1s assertion happens in Task 4 against a known <1k-file project).
    - The verify block exits 0 with `ALL_OK` printed.
    - The daemon is cleanly torn down (no orphan PID on 127.0.0.1:8765 after the test).
  </done>
</task>

<task type="auto">
  <name>Task 3: Rewrite frontend/pages/folders.jsx with fetch + bounded-error EventSource subscription</name>
  <files>frontend/pages/folders.jsx</files>
  <read_first>
    - frontend/pages/folders.jsx (the current file — keep TreeNode and FolderColumn components UNCHANGED; only replace the Folders() component's data source)
    - frontend/data.jsx:104-168 (the FOLDERS mock — this is the shape the existing TreeNode renders; the new fetched data must be structurally identical)
    - frontend/index.html (verify React 18 UMD is loaded so useEffect/useRef are available via `React.useEffect` etc.)
    - .planning/workstreams/folders-3source/phases/INV-01-three-tree-endpoints-live-folders-page/INV-01-01-SUMMARY.md (the exact SSE event names emitted by stream_diffs — snapshot/diff/error)
  </read_first>
  <action>
    Rewrite `frontend/pages/folders.jsx` end-to-end, preserving the existing visual.

    **Top of file** (replace `const { useState: useStateF } = React;`):
    ```
    const { useState: useStateF, useEffect: useEffectF, useRef: useRefF } = React;

    const API_BASE = "http://127.0.0.1:8765";
    const SSE_ERROR_CEILING = 3; // after 3 consecutive errors with no good event, show a column-level placeholder

    // Token discovery: URL ?token= takes precedence (lets you bookmark from
    // phone), then window.INVISIBLE_TOKEN (future bootstrap injection).
    function getToken() {
      const u = new URLSearchParams(window.location.search).get("token");
      if (u) return u;
      if (window.INVISIBLE_TOKEN) return window.INVISIBLE_TOKEN;
      return "";
    }

    // Source metadata mirrors the data.jsx FOLDERS object's non-tree fields
    // so the column header / chip rendering doesn't change.
    const SOURCE_META = {
      local: { label: "Local",  meta: "MBP",                   color: "var(--c-fold)"  },
      vps:   { label: "VPS",    meta: "via SSH",               color: "var(--c-graph)" },
      repo:  { label: "GitHub", meta: "gh api · 60s cache",    color: "var(--c-tools)" },
    };
    ```

    **Keep `TreeNode` and `FolderColumn` UNCHANGED** — they consume the same `{name, type, children?, badge?, open?}` node shape that the new endpoints emit, so they need no changes. Verify this by re-reading the existing implementations and confirming no field references would break on real data.

    **Replace the `Folders` component** with this implementation:

    ```
    function Folders({ project } = {}) {
      // project (optional) — if set, fetches ?project=<name> from every endpoint
      // for the per-project Dive-in filter (success criterion 6).
      const [q, setQ] = useStateF("");
      const [trees, setTrees] = useStateF({ local: null, vps: null, repo: null });
      const [errors, setErrors] = useStateF({ local: null, vps: null, repo: null });
      const [loading, setLoading] = useStateF(true);
      const sseRef = useRefF(null);
      const consecutiveErrorCount = useRefF(0); // bounded SSE error counter (WARNING #6 fix)

      // Pull ?project from URL if not passed as prop (lets the dashboard's
      // Dive-in link work as <a href="?page=folders&project=jobslayer">).
      const effectiveProject = project
        || new URLSearchParams(window.location.search).get("project")
        || null;

      useEffectF(() => {
        const token = getToken();
        const headers = token ? { Authorization: "Bearer " + token } : {};
        const qs = effectiveProject ? "?project=" + encodeURIComponent(effectiveProject) : "";

        let cancelled = false;
        const fetchOne = (key) =>
          fetch(API_BASE + "/api/v1/tree/" + key + qs, { headers })
            .then((r) => r.json().then((body) => ({ ok: r.ok, status: r.status, body })))
            .then(({ ok, status, body }) => {
              if (cancelled) return;
              if (!ok) {
                setErrors((e) => ({ ...e, [key]: (body && body.error) || ("HTTP " + status) }));
                setTrees((t) => ({ ...t, [key]: [] }));
                return;
              }
              setTrees((t) => ({ ...t, [key]: body }));
            })
            .catch((err) => {
              if (cancelled) return;
              setErrors((e) => ({ ...e, [key]: String(err) }));
              setTrees((t) => ({ ...t, [key]: [] }));
            });

        Promise.all([fetchOne("local"), fetchOne("repo"), fetchOne("vps")])
          .finally(() => { if (!cancelled) setLoading(false); });

        // SSE subscription for the local source.
        // EventSource can't set Authorization headers; pass token as ?token= query.
        const sseUrl = API_BASE + "/api/v1/tree/local?watch=1"
          + (token ? "&token=" + encodeURIComponent(token) : "")
          + (effectiveProject ? "&project=" + encodeURIComponent(effectiveProject) : "");
        const es = new EventSource(sseUrl);
        sseRef.current = es;

        es.addEventListener("snapshot", (ev) => {
          consecutiveErrorCount.current = 0; // reset on any successful event
          try {
            const payload = JSON.parse(ev.data);
            if (!cancelled && payload && Array.isArray(payload.tree)) {
              setTrees((t) => ({ ...t, local: payload.tree }));
              setErrors((e) => e.local ? ({ ...e, local: null }) : e); // clear any prior "stream disconnected" notice
            }
          } catch (_) {}
        });
        es.addEventListener("diff", (ev) => {
          consecutiveErrorCount.current = 0;
          // Cheap MVP strategy: any diff event triggers a re-fetch of the local tree.
          // Future optimization: apply the diff payload in-place to the existing tree.
          // TODO: debounce — successive diffs during `npm install` cause re-fetch storms.
          if (cancelled) return;
          fetchOne("local");
        });
        es.addEventListener("error", () => {
          // EventSource auto-reconnects with backoff. Track consecutive errors so a
          // flapping/dead daemon surfaces a visible signal instead of silent retries forever.
          consecutiveErrorCount.current += 1;
          if (consecutiveErrorCount.current >= SSE_ERROR_CEILING) {
            if (!cancelled) {
              setErrors((e) => ({ ...e, local: "Local stream disconnected — check daemon" }));
            }
          }
        });

        return () => {
          cancelled = true;
          consecutiveErrorCount.current = 0;
          if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }
        };
      }, [effectiveProject]);

      const sources = ["local", "vps", "repo"].map((k) => {
        const meta = SOURCE_META[k];
        const tree = trees[k];
        const err = errors[k];
        let body;
        if (tree === null) body = [{ name: loading ? "Loading…" : "—", type: "file" }];
        else if (err)      body = [{ name: err, type: "file", badge: "error" }];
        else if (tree.length === 0) body = [{ name: "(empty)", type: "file" }];
        else body = tree;
        return [k, { label: meta.label, meta: meta.meta, color: meta.color, tree: body }];
      });

      return (
        <>
          <div style={{ display: "flex", gap: "var(--pad-3)", marginBottom: "var(--pad-4)", alignItems: "center" }}>
            <div style={{ position: "relative", flex: 1, maxWidth: 360 }}>
              <span style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-4)" }}>
                <I.Search size={14}/>
              </span>
              <input
                className="field"
                placeholder="Search across all sources…"
                value={q}
                onChange={e => setQ(e.target.value)}
                style={{ paddingLeft: 32, width: "100%" }}
              />
            </div>
            {effectiveProject && <span className="chip"><span className="chip-dot" style={{ color: "var(--c-fold)" }}/>filter: {effectiveProject}</span>}
            <button className="btn accent" style={{ marginLeft: "auto" }}>
              <I.Plus size={13}/> New source
            </button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--pad-3)", height: "calc(100% - 60px)" }}>
            {sources.map(([k, s]) => (
              <FolderColumn key={k} sourceKey={k} source={s} active={true}/>
            ))}
          </div>
        </>
      );
    }

    window.Folders = Folders;
    ```

    **DELETE** the existing reference to `FOLDERS.local`, `FOLDERS.vps`, `FOLDERS.repo` in `folders.jsx` — the only call site was the destructure in the old `Folders()` component, replaced above. The `FOLDERS` mock in `data.jsx` is NOT touched (other workstreams may still reference it during their own wiring; let them remove their own consumers).

    **Search-input wiring:** the `q` state is kept (visual parity) but search is not yet wired to filter the tree. That's a Phase 2 enhancement; document the gap with a `// TODO(REQ-03, future): wire q to filter tree nodes` comment so the next planner sees it.
  </action>
  <verify>
    <automated>cd "$INVISIBLE_HOME" && grep -c "fetch.*api/v1/tree/" frontend/pages/folders.jsx | grep -v '^#' | awk '$1 < 1 {print "FAIL: no fetch to /api/v1/tree/ in folders.jsx"; exit 1} {print "fetch OK ("$1" calls)"}' && grep -c "new EventSource" frontend/pages/folders.jsx | awk '$1 < 1 {print "FAIL: no EventSource in folders.jsx"; exit 1} {print "EventSource OK ("$1" subscriptions)"}' && ! grep -q "FOLDERS\\.local\\|FOLDERS\\.vps\\|FOLDERS\\.repo" frontend/pages/folders.jsx && echo "mock removed OK" && grep -q "consecutiveErrorCount" frontend/pages/folders.jsx || { echo "FAIL: folders.jsx must track consecutiveErrorCount in the EventSource setup (WARNING #6 fix)"; exit 1; } && grep -q "SSE_ERROR_CEILING" frontend/pages/folders.jsx || { echo "FAIL: folders.jsx must define SSE_ERROR_CEILING (WARNING #6 fix)"; exit 1; } && echo "error-ceiling OK"</automated>
  </verify>
  <done>
    - `frontend/pages/folders.jsx` contains `fetch('` (or `fetch("`) targeting all three `/api/v1/tree/{local,vps,repo}` endpoints.
    - Contains `new EventSource(` for the local watch endpoint.
    - Contains the `getToken()` helper reading from `?token=` URL param.
    - Does NOT reference `FOLDERS.local`, `FOLDERS.vps`, or `FOLDERS.repo` anywhere.
    - The page imports `useEffect` and `useRef` from React (alongside the existing `useState`).
    - Defines `SSE_ERROR_CEILING = 3` and tracks `consecutiveErrorCount` via `useRef`; on `>= SSE_ERROR_CEILING` errors with no intervening successful event, sets a column-level error placeholder. Counter resets to 0 on any `snapshot` or `diff` event (WARNING #6 fix from checker pass).
    - Empty/loading/error/503 states each render a sensible single-node placeholder in the column instead of crashing.
    - The `effectiveProject` derivation pulls from both the prop and `?project=` URL param (supports the Dive-in flow from success criterion 6).
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 4: Human-verify cold-load, SSE latency, CORS in browser, and visual parity</name>
  <what-built>
    All three columns (Local · VPS · GitHub) on the Folders page now render live data instead of mock data. The local column subscribes to an SSE stream and re-fetches when filesystem changes occur. The dashboard emits CORS headers so the cross-port browser can actually consume the API.
  </what-built>
  <how-to-verify>
    1. Start both daemons in separate terminals (or background):
       ```
       export T="manual-test-$(python3 -c 'import secrets;print(secrets.token_hex(8))')"
       INVISIBLE_DASHBOARD_TOKEN="$T" "$INVISIBLE_HOME/bin/invisible-dashboard" --host 127.0.0.1 --port 8765 &
       "$INVISIBLE_HOME/bin/invisible-frontend" --host 127.0.0.1 --port 8090 &
       ```
    2. Open the Folders page in a browser:
       `http://127.0.0.1:8090/?token=$T#folders` (or whatever the app's routing convention is; check the app shell after start).
    3. **CORS / cross-port check** (BLOCKER #1 in the browser): open DevTools → Network tab BEFORE you load the page. After load:
       - Each `/api/v1/tree/{local,repo,vps}` request should show two entries: an `OPTIONS` preflight returning 204, then a `GET` returning 200 (or 503 for vps). No CORS errors in the Console.
       - If you see "blocked by CORS policy" in the Console, the dashboard CORS fix in Task 1 is incomplete — go back and re-verify the `_send_json` and `do_OPTIONS` edits.
    4. **Cold-load <1s check** (REQ-03, WARNING #5 fix): with a project containing <1k files configured in invisible.toml, hard-reload the page (Cmd-Shift-R) with the DevTools Network tab open. The `/api/v1/tree/local` row's "Time" column should be under 1000ms (look at the total time, including waiting/TTFB and download). Stopwatch the visual: from "Reload clicked" to "Local column populated", under 1 second.
    5. Verify all three columns render WITHOUT the mock data:
       - **Local:** shows your real project(s) from `invisible.toml` (e.g. `jobslayer` with its actual subdirectories).
       - **VPS:** shows the column header but displays an error placeholder ("vps.host not configured") — this is the correct 503 graceful-degradation behavior.
       - **GitHub:** shows `@Avi977/<repo>` style entries for each project that has a discoverable git remote.
    6. **5-second SSE latency check** (success criterion 5):
       - In a terminal, run `touch ~/Projects/jobslayer/sse-probe.txt` (substitute the actual configured project path).
       - Stopwatch yourself: within 5 seconds, the local column should re-render and contain `sse-probe.txt`.
       - Now `rm ~/Projects/jobslayer/sse-probe.txt` — within 5 seconds, the file should disappear from the column.
    7. **EventSource error-ceiling check** (WARNING #6 fix):
       - Kill the dashboard daemon (`kill %1` or Ctrl-C in its terminal).
       - Wait 10–20 seconds (3 EventSource error events at the default 3s backoff).
       - The Local column should now show "Local stream disconnected — check daemon" instead of stale data and silent reconnects.
       - Restart the dashboard. Within a few seconds the column should clear the error and resume showing live data.
    8. **Per-project filtering check** (success criterion 6):
       - Navigate to `http://127.0.0.1:8090/?token=$T&project=jobslayer#folders`.
       - All three columns should show ONLY jobslayer's subtree (a "filter: jobslayer" chip should appear in the toolbar).
    9. **Visual parity check:**
       - The column borders, accent colors, tree-row icons, and font sizes should be identical to the pre-wiring mock version. The only visible difference is the data inside.
       - Open the browser console — there should be no React warnings or fetch errors (other than possibly EventSource reconnect attempts if you stop the dashboard daemon — those are expected and bounded by step 7).
    10. **Auth gate check:**
       - Open `http://127.0.0.1:8090/#folders` (no `?token=`). The columns should render error placeholders ("HTTP 401") instead of crashing. This proves the auth gate is enforced and the frontend handles the failure cleanly.

    Type "approved" if all ten checks pass. If any check fails, describe which step failed and what you saw instead.
  </how-to-verify>
  <resume-signal>Type "approved" or describe issues</resume-signal>
</task>

</tasks>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Browser → dashboard API (cross-origin) | Frontend on :8090, dashboard on :8765; the dashboard MUST emit `Access-Control-Allow-Origin` and handle OPTIONS preflight for `Authorization`-bearing requests (THIS plan owns the fix) |
| EventSource → SSE endpoint | EventSource API cannot set Authorization headers; mitigated by accepting `?token=` query param (mirroring the dashboard's existing HTML-page convention at bin/invisible-dashboard:224-228). SSE response also needs `Access-Control-Allow-Origin` (Plan 01 added it in `stream_diffs`) |
| URL `?project=` param → server-side `walk_all(project=...)` lookup | Server-side, project is matched against the in-memory list of configured project names (exact-match string equality in invisible.toml); not used in shell commands; safe. Unknown project returns `[]` (BLOCKER #2 cross-walker fix), never `[None]` |
| EventSource reconnect loop | A flapping daemon (auth fail or port closed) auto-reconnects every ~3s forever. Mitigated by a client-side `consecutiveErrorCount` ceiling of 3 (WARNING #6 fix) that surfaces a column-level placeholder; combined with the server-side 200-event polling cap (Plan 01) the storm is bounded on both sides |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-INV01-13 | Spoofing | SSE auth bypass via EventSource | mitigate | `_token_from_request()` in bin/invisible-dashboard already accepts both `Authorization: Bearer` and `?token=` query param; frontend EventSource appends `?token=$T` (Task 1, Task 3) |
| T-INV01-14 | Information Disclosure | token in URL query string | accept | Token in URL is the established convention for the dashboard (see bin/invisible-dashboard:18-22 "HTML pages also accept ?token=<t> in the URL so you can bookmark from your phone"). Risk surface is the browser history and any server access log; mitigated by the daemon's `log_message` override at line 216-217 which suppresses access logs. **Document in folders.jsx as a known property of the token-in-URL convention; revisit if/when the dashboard introduces cookie-based auth** |
| T-INV01-15 | Denial of Service | client-side SSE re-fetch storm + reconnect storm | mitigate | (a) Re-fetch on diff: server-side `stream_diffs` caps 200 events per polling cycle (Plan 01, T-INV01-04); client-side `// TODO: debounce` comment documented for future optimization. (b) Reconnect storm: `consecutiveErrorCount` ref ceiling of 3 surfaces a visible placeholder and prevents silent infinite retries (Task 3, WARNING #6 fix) |
| T-INV01-16 | Tampering | XSS via tree node names | mitigate | `TreeNode` renders `{node.name}` as React text content (not `dangerouslySetInnerHTML`); React auto-escapes. Safe by default. No special action needed; documented for completeness |
| T-INV01-17 | Spoofing / Confused-Deputy | CORS configuration | mitigate | Dashboard `_send_json` emits `Access-Control-Allow-Origin: *`, `Access-Control-Allow-Headers: Authorization, Content-Type`, `Access-Control-Allow-Methods: GET, OPTIONS`. `do_OPTIONS` returns 204 with the same headers for `/api/v1/tree/*` preflight (NOT auth-gated, because preflight has no Authorization header). SSE response includes the same `Access-Control-Allow-Origin` header (Plan 01's `stream_diffs`). The dashboard binds to 127.0.0.1 by default (line 345-346), so the permissive `*` origin is acceptable for the single-user dev environment per PROJECT.md "Single user: no multi-tenant concerns" — cross-origin requests from arbitrary internet pages still cannot reach loopback. (BLOCKER #1 fix from checker pass: the previous plan incorrectly attributed CORS to `bin/invisible-frontend` — but CORS headers must come from the resource being requested, the dashboard, not from the page making the request) |

No new pip/npm installs in this plan. No `[ASSUMED]` / `[SUS]` flags. No blocking-human-checkpoint required for package legitimacy.

</threat_model>

<verification>
- Task 1 verify: package importable, ≥3 `/api/v1/tree/` route registrations grepped in `bin/invisible-dashboard` (comments excluded), `Access-Control-Allow-Origin` present, `do_OPTIONS` defined.
- Task 2 verify: end-to-end curl battery with the daemon running — 200 for local/repo, 503 with the configured error body for vps, 401 for unauthenticated, `event: snapshot` frame on the SSE stream, CORS headers on GET + SSE, 204 on OPTIONS preflight, cold-load time logged.
- Task 3 verify: frontend file contains `fetch('/api/v1/tree/`, `new EventSource(`, no `FOLDERS.local|vps|repo` references, defines `SSE_ERROR_CEILING` and tracks `consecutiveErrorCount`.
- Task 4 (human-verify): the 5-second perceptual SSE latency, the <1s cold-load stopwatch, the in-browser CORS check (no console errors, OPTIONS+GET pair in Network), the EventSource error-ceiling placeholder behavior, the 503-vps placeholder rendering, and the per-project filtering visual check.

Phase-level success criteria from ROADMAP (all six must be true after this plan):
1. ✓ `GET /api/v1/tree/local` — routed in Task 1, verified in Task 2, rendered in Task 3, in-browser CORS verified in Task 4.
2. ✓ `GET /api/v1/tree/repo` — routed in Task 1, verified in Task 2, rendered in Task 3.
3. ✓ `GET /api/v1/tree/vps` 503 — routed in Task 1, explicitly asserted in Task 2 with the error-body grep.
4. ✓ Folders page renders three columns — Task 3 + Task 4 visual parity check.
5. ✓ SSE 5-second update — Task 2 smoke for the snapshot frame + CORS, Task 4 human-verify for the latency + error-ceiling behavior.
6. ✓ Per-project filtering — `?project=` param threaded through fetch and EventSource URL, verified in Task 4.
</verification>

<success_criteria>
- All four tasks complete (3 auto + 1 human-verify).
- Folders page in the browser shows real data from all three sources (no CORS errors in console).
- VPS column renders the "not configured" placeholder cleanly (no white screen, no console error).
- A `touch` on a configured project file causes the local column to update within 5 seconds.
- Cold-load of the local tree for a <1k-file project completes under 1 second (stopwatched in Task 4).
- Killing the dashboard surfaces "Local stream disconnected — check daemon" after 3 EventSource errors instead of silent infinite retries.
- The dashboard daemon's other routes (`/`, `/p/`, `/api/projects`, `/api/p/`, `/api/reviews`, `/healthz`) are unaffected by the additions.
</success_criteria>

<output>
Create `.planning/workstreams/folders-3source/phases/INV-01-three-tree-endpoints-live-folders-page/INV-01-03-SUMMARY.md` when done. Include:
- The final byte-count of `bin/invisible-dashboard` before/after (proves the touch was surgical — should be ~+45 lines: ~25 for routes + ~3 CORS headers + ~15 for do_OPTIONS).
- The exact token-passing convention established (URL `?token=` for both fetch and EventSource) — so the other five workstreams can mirror it.
- The exact CORS posture established (`*` origin, `Authorization, Content-Type` allowed headers, `GET, OPTIONS` allowed methods, 600s preflight cache) so the other five workstreams don't re-debate it.
- A note on the `// TODO: debounce` comment in the diff handler so REQ-03 has a known-deferred follow-up.
- The cold-load timing observed in Task 2 step 9 (informational; the hard <1s check is the Task 4 human-verify).
- Confirmation that the phase-level must_haves truths are observable in the running app (or which one failed and why).
</output>
</output>
