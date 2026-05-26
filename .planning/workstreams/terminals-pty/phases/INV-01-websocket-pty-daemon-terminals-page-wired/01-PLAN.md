---
phase: 01-websocket-pty-daemon-terminals-page-wired
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - bin/invisible-pty
  - lib/pty_server.py
autonomous: true
requirements: [REQ-04]
must_haves:
  truths:
    - "Running `bin/invisible-pty --port 8091` binds 127.0.0.1:8091 and accepts WebSocket connections at `/pty/{id}`."
    - "Connecting `ws://127.0.0.1:8091/pty/{valid-id}` spawns a real bash PTY; bytes sent on the socket reach the shell stdin; shell stdout/stderr streams back as text frames."
    - "Pane ids that fail the `^[a-z0-9_-]{1,32}$` regex are rejected with a WebSocket close code 1008 before any PTY spawn."
    - "WebSocket upgrades whose `Origin` header is not `http://127.0.0.1:8090` / `http://localhost:8090` (or absent on a 127.0.0.1 connection — configurable) are rejected with HTTP 403."
    - "Daemon refuses to start with `--host` outside `{127.0.0.1, localhost, ::1}` (exit non-zero with a clear error)."
    - "Per-pane HTTP route `GET /context/{pane_id}` returns JSON with `task` / `last_summary` / `next_steps` derived from the checkpoint store for the pane's configured worktree, or `{}` if none found."
    - "Missing `websockets` or `ptyprocess` at import time aborts startup with a one-line install hint pointing to `python3 -m pip install --user websockets ptyprocess`."
  artifacts:
    - path: bin/invisible-pty
      provides: "Executable Python daemon entrypoint mirroring bin/invisible-dashboard CLI shape (argparse --host/--port, serve()/main())"
      contains: "argparse, --port 8091 default, --host 127.0.0.1 default, host validation, calls pty_server.serve()"
    - path: lib/pty_server.py
      provides: "WebSocket PTY server module: server class, pane-id validator, origin check, PTY spawn helper, per-pane context HTTP route, in-memory PTY registry (basic — Plan 02 extends)"
      exports: ["PTYServer", "PANE_ID_RE", "ALLOWED_ORIGINS", "spawn_pty", "load_pane_context"]
  key_links:
    - from: bin/invisible-pty
      to: lib/pty_server.py
      via: "sys.path insert of HERE.parent/'lib' then `from pty_server import PTYServer` (mirrors bin/invisible-dashboard import pattern)"
      pattern: "from pty_server import"
    - from: lib/pty_server.py
      to: lib/checkpoint.py
      via: "load() called with worktree Path resolved from pane config to read .invisible-checkpoint.json"
      pattern: "checkpoint.load|from checkpoint import"
    - from: lib/pty_server.py
      to: "ptyprocess.PtyProcess"
      via: "PtyProcess.spawn([shell, '-i']) with cwd & env per pane"
      pattern: "PtyProcess"
---

<objective>
Build the WebSocket PTY daemon scaffold: a new executable `bin/invisible-pty` and the
core server module `lib/pty_server.py`. This plan delivers a daemon that binds
127.0.0.1:8091, accepts WebSocket connections at `ws://127.0.0.1:8091/pty/{id}`,
spawns a real bash PTY per connection, streams bytes bidirectionally, exposes a
side-channel `GET /context/{pane_id}` HTTP route for the per-pane checkpoint
context header, and enforces the ASVS L1 security gates declared by the phase
(host binding, origin pinning, pane-id whitelist, concurrent-PTY cap, import
failure surfacing).

Purpose: Without this scaffold there is no daemon for Plan 02 (session
persistence + SSH variant) to extend and no endpoint for Plan 03 (frontend) to
connect to. Plans 02 and 03 both depend on this one.

Output: An executable `bin/invisible-pty`, a `lib/pty_server.py` module, both
runnable headlessly with no frontend involved.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/REQUIREMENTS.md
@.planning/workstreams/terminals-pty/ROADMAP.md
@.planning/workstreams/terminals-pty/STATE.md
@START_HERE.md

# Reference patterns (read but do not edit):
@bin/invisible-dashboard
@lib/checkpoint.py

<interfaces>
<!-- Key contracts extracted from existing code. Use these directly. -->

From lib/checkpoint.py (read-only — DO NOT modify):
- CHECKPOINT_FILE = ".invisible-checkpoint.json"
- path_for(feature_worktree: Path) -> Path
- load(feature_worktree: Path) -> dict | None
  Schema returned by load(): { project, task, iteration, max_iters,
  feedback_history: list[str], last_sha, last_verdict, last_summary,
  started_at, updated_at, host, context_chars_used, usage_total, usage_per_iter }
  NOTE: Schema does NOT contain `current_goal`, `recent_activity`, `next_steps`
  literal keys. Map to surfaceable fields: goal ← task, activity ← derived from
  feedback_history (most recent N entries), next_steps ← derived from last
  feedback_history entry or empty list. Document this mapping in pty_server.py
  load_pane_context() docstring.

From bin/invisible-dashboard (read-only — reference shape only):
- HERE = Path(__file__).resolve().parent
- sys.path.insert(0, str(HERE.parent / "lib"))  # then bare `from foo import …`
- argparse.ArgumentParser(prog=…) with --host/--port
- serve(host, port, …) + KeyboardInterrupt handler
- main() returns int, `raise SystemExit(main())`

From lib/config.py (used by bin/invisible-dashboard):
- home() -> Path  (returns $INVISIBLE_HOME or sensible default; worktrees live in home()/"worktrees")
- load_env() -> None
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create lib/pty_server.py with WebSocket PTY server module</name>
  <files>lib/pty_server.py</files>
  <read_first>
    - bin/invisible-dashboard (full file — argparse pattern, serve() shape, host validation idiom in `--no-auth` block)
    - lib/checkpoint.py (full file — load() signature, schema keys)
    - frontend/pages/terminals.jsx lines 1-80 (TERM_PRESETS shape — informs pane config schema this server will eventually receive)
  </read_first>
  <action>
    Create `lib/pty_server.py` as a new Python 3.11+ module. Place an early
    try/except ImportError around `import websockets` and `import ptyprocess`;
    on failure raise SystemExit with the message "missing dependency: run
    `python3 -m pip install --user websockets ptyprocess`".

    Define module-level constants: `PANE_ID_RE = re.compile(r"^[a-z0-9_-]{1,32}$")`,
    `ALLOWED_ORIGINS = {"http://127.0.0.1:8090", "http://localhost:8090"}`,
    `MAX_CONCURRENT_PTYS = 32`, `DEFAULT_SHELL = os.environ.get("SHELL", "/bin/bash")`.

    Define `validate_host(host: str) -> None` that raises ValueError if host
    is not in `{"127.0.0.1", "localhost", "::1"}`. Daemon CLI calls this before
    binding.

    Define `validate_pane_id(pane_id: str) -> bool` returning whether the id
    matches PANE_ID_RE. Reject anything else.

    Define `check_origin(origin: str | None) -> bool` returning True only if
    origin is in ALLOWED_ORIGINS. Used as the `process_request` hook on the
    websockets server to return a 403 Forbidden HTTP response before upgrade
    when the Origin header is absent or disallowed.

    Define `spawn_pty(pane_id: str, cwd: str | None = None, env: dict | None = None,
    command: list[str] | None = None) -> ptyprocess.PtyProcess`. Default
    command is `[DEFAULT_SHELL, "-i"]`. Sets `dimensions=(24, 80)` initially
    (resize support deferred to Plan 02 or 03 — note in docstring). Inherits
    process env unless overridden. Raises `RuntimeError("PTY cap reached")` if
    the in-memory registry already holds MAX_CONCURRENT_PTYS entries.

    Define an in-memory registry as a `PTYRegistry` class with `dict[str, dict]`
    storing per-pane state `{proc: PtyProcess, created_at: datetime, ws: WebSocket | None}`.
    Methods: `register(pane_id, proc)`, `get(pane_id) -> dict | None`,
    `count() -> int`, `unregister(pane_id) -> None`. Plan 02 extends this with
    reconnect + reap logic — for now, only `register/get/count/unregister` are
    needed. New connection to an existing pane_id in Plan 01 closes the old
    PTY and creates a new one (simplest behavior; Plan 02 changes this to
    reattach).

    Define `load_pane_context(worktree_path: Path | str) -> dict`. Imports
    `checkpoint` from the same lib/ directory. Calls `checkpoint.load(Path(worktree_path))`
    and maps the dict to a 3-key shape:
      - `goal` ← `state.get("task", "")` (the orchestrator task IS the goal)
      - `activity` ← list of the last 4 entries from `state.get("feedback_history", [])`
        each rendered as `{c: <truncated 120 chars>, k: "ok"}` (color/kind
        heuristics deferred — Plan 03 can refine)
      - `next` ← if `last_verdict == "changes"` return [last_summary], else []
    Returns `{}` when checkpoint absent. Docstring explicitly notes the
    checkpoint schema lacks literal `current_goal`/`recent_activity`/`next_steps`
    fields and what mapping was chosen.

    Define `PTYServer` class with attributes `host`, `port`, `registry: PTYRegistry`,
    `pane_configs: dict[str, dict]` (placeholder, populated from invisible.toml
    in Plan 02 — for Plan 01 default-empty so every pane gets a plain bash).

    Implement async handler `handle_pty(websocket, path)`:
      1. Parse `pane_id` from path. Path MUST start with `/pty/`; otherwise
         close with code 1008 ("policy violation") and reason "bad path".
      2. Run `validate_pane_id(pane_id)`; on failure close 1008 reason "bad pane id".
      3. Run cap check; if `registry.count() >= MAX_CONCURRENT_PTYS` close 1011
         ("internal error") reason "pty cap reached".
      4. Spawn PTY via spawn_pty(pane_id). Register in registry.
      5. Start two concurrent tasks (asyncio.gather):
         - `pty_to_ws`: read non-blocking from `proc.read(1024)` in a thread
           executor loop; forward bytes to websocket as text (decode utf-8,
           errors="replace"). Exit on EOF or PtyProcessUnexpectedClose.
         - `ws_to_pty`: `async for message in websocket`; encode utf-8 if str;
           `proc.write(...)`. Handles ConnectionClosed by returning.
      6. On either task ending: terminate the PtyProcess (`proc.terminate(force=True)`),
         unregister, close websocket. Plan 02 will replace this teardown with
         "keep alive for reconnect" — for Plan 01, every disconnect kills the PTY.

    Implement async `serve_http_context(request)` handler — a tiny ASGI-style
    or `websockets`-compatible HTTP handler bound to path `/context/{pane_id}`.
    Easiest: use the `process_request` hook on websockets.serve to handle
    non-WebSocket HTTP GETs. If path matches `/context/{pane_id}` and
    pane_id is valid, look up the pane's worktree (default: `home() / "worktrees" / pane_id / "feature"`
    — Plan 02 may replace with config lookup), call `load_pane_context`, and
    return `(http.HTTPStatus.OK, headers, json.dumps(ctx).encode())`. Return
    None to allow WS upgrades to proceed for other paths. CORS: allow
    `http://127.0.0.1:8090` as origin (Access-Control-Allow-Origin header).

    Implement `async def serve_async(self) -> None`: starts `websockets.serve(
    self.handle_pty, self.host, self.port, process_request=self._process_request,
    origins=list(ALLOWED_ORIGINS))`. Where `_process_request` first handles
    `/context/...` GETs then enforces origin pinning for WS upgrades by
    rejecting requests whose Origin header is absent or not in ALLOWED_ORIGINS.

    Implement sync `serve(self) -> None` that wraps `asyncio.run(self.serve_async())`
    and catches KeyboardInterrupt with a clean shutdown line printed to stdout
    (`"[invisible-pty] shutting down"`), matching the dashboard's exit log.

    Print on startup: `f"[invisible-pty] listening on ws://{host}:{port}"` and
    `"[invisible-pty] Ctrl-C to stop"`.

    DO NOT add SSH-variant logic here. DO NOT add the reconnect-grace timer
    here. Plan 02 owns those. Add a `# TODO(plan-02): reconnect grace` /
    `# TODO(plan-02): ssh variant` comment at each insertion point so the
    next plan's executor finds the seam.

    DO NOT touch lib/api/, frontend/pages/dashboard.jsx, or any of the
    MUST NOT TOUCH files listed in START_HERE.md.
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/terminals-pty &amp;&amp; python3 -c "import sys; sys.path.insert(0, 'lib'); from pty_server import PTYServer, PANE_ID_RE, ALLOWED_ORIGINS, spawn_pty, load_pane_context, validate_host, validate_pane_id; assert PANE_ID_RE.match('ws-1') and not PANE_ID_RE.match('../etc/passwd'); assert validate_pane_id('echo-ios') and not validate_pane_id('A B'); assert 'http://127.0.0.1:8090' in ALLOWED_ORIGINS; print('imports + regex + origins OK')"</automated>
  </verify>
  <done>
    `lib/pty_server.py` exists. All named exports import cleanly. Pane-id
    regex rejects path traversal + whitespace + uppercase. ALLOWED_ORIGINS
    contains both 127.0.0.1:8090 and localhost:8090. validate_host raises on
    `0.0.0.0`. spawn_pty docstring documents the 32-PTY cap and the deferred
    resize support. load_pane_context docstring documents the
    checkpoint→display field mapping.
  </done>
</task>

<task type="auto">
  <name>Task 2: Create bin/invisible-pty executable daemon entrypoint</name>
  <files>bin/invisible-pty</files>
  <read_first>
    - bin/invisible-dashboard lines 1-60 + 318-369 (shebang, sys.path insert, argparse, main(), SystemExit pattern)
    - lib/pty_server.py (the module just created — for the public API to call into)
  </read_first>
  <action>
    Create `bin/invisible-pty` as a Python 3.11+ executable script. Shebang
    `#!/usr/bin/env python3`. Mark the file executable (`chmod +x`) as part of
    this task.

    Mirror the structure of `bin/invisible-dashboard`:
      - Module docstring describing what the daemon serves (WebSocket PTY on
        127.0.0.1:8091, side-channel context endpoint, intended client is
        `frontend/pages/terminals.jsx`).
      - `HERE = Path(__file__).resolve().parent`
      - `sys.path.insert(0, str(HERE.parent / "lib"))`
      - `from pty_server import PTYServer, validate_host` (post-sys.path insert)
      - Optional: `from config import load_env` if pty_server uses any env;
        otherwise skip.

    Implement `main() -> int`:
      - argparse with `--host` (default `"127.0.0.1"`), `--port` (default `8091`).
      - Call `validate_host(args.host)`. On ValueError, print to stderr
        `f"[invisible-pty] {e}: --host must be 127.0.0.1, localhost, or ::1"`
        and return 2 (matches bin/invisible-dashboard return convention).
      - Optionally call `load_env()` (only if the rest of the daemon needs env;
        leave a comment noting Plan 02 will likely add `[[terminals]]` config
        loading from invisible.toml here).
      - Instantiate `PTYServer(host=args.host, port=args.port)` and call
        `.serve()`. Return 0.

    `if __name__ == "__main__": raise SystemExit(main())`.

    DO NOT touch `bin/invisible-dashboard` or any other `bin/invisible-*` script.
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/terminals-pty &amp;&amp; test -x bin/invisible-pty &amp;&amp; bin/invisible-pty --port 8091 &amp; PID=$!; sleep 1.5; lsof -nP -iTCP:8091 -sTCP:LISTEN | grep -q LISTEN &amp;&amp; LISTEN_OK=1 || LISTEN_OK=0; kill $PID 2>/dev/null; wait $PID 2>/dev/null; bin/invisible-pty --host 0.0.0.0 --port 8091; REFUSED=$?; [ "$LISTEN_OK" = "1" ] &amp;&amp; [ "$REFUSED" != "0" ] &amp;&amp; echo "daemon binds 127.0.0.1:8091 + refuses 0.0.0.0 OK" || (echo "FAIL: listen=$LISTEN_OK refused_exit=$REFUSED"; exit 1)</automated>
  </verify>
  <done>
    `bin/invisible-pty` is executable. With no args it binds 127.0.0.1:8091
    and `lsof` confirms a LISTEN socket. With `--host 0.0.0.0` it exits
    non-zero with a clear stderr error. Ctrl-C produces the shutdown line.
  </done>
</task>

<task type="auto">
  <name>Task 3: Verify headless PTY round-trip and threat-model gates end-to-end</name>
  <files>lib/pty_server.py</files>
  <read_first>
    - lib/pty_server.py (the module the prior tasks created — confirm handler paths)
    - bin/invisible-pty (entrypoint — confirm port default)
  </read_first>
  <action>
    Run the daemon and a headless Python WebSocket client that exercises:
      (a) Happy path: valid pane id `test-1` runs `pwd\n`, receives output
          containing a real working-directory path.
      (b) Bad pane id: connecting to `/pty/../etc/passwd` is rejected with
          close code 1008.
      (c) Bad origin: connecting with `Origin: http://evil.example` is rejected
          with HTTP 403 before upgrade.
      (d) Context route: `GET http://127.0.0.1:8091/context/test-1` returns
          200 with a JSON object (`{}` is acceptable if no checkpoint exists
          for that pane in this worktree).

    If any check fails, edit `lib/pty_server.py` to fix the relevant gate (no
    new files in this task — Plan 01 ships exactly two files). Each fix must
    keep the named exports stable so Plan 02 can extend without breaking imports.

    Document the verified gates by appending a `# PLAN-01 verification log` comment
    block at the bottom of `lib/pty_server.py` listing the four checks that pass.
    This is the marker Plan 02 and Plan 03 grep for to confirm the daemon
    surface is stable.
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/terminals-pty &amp;&amp; bin/invisible-pty --port 8091 &amp; DAEMON=$!; sleep 1.5; python3 -c "
import asyncio, json, urllib.request, websockets
from websockets.exceptions import InvalidStatus, ConnectionClosed

async def happy():
    async with websockets.connect('ws://127.0.0.1:8091/pty/test-1', origin='http://127.0.0.1:8090') as ws:
        await ws.send('pwd\n')
        # Collect a couple of frames — bash echoes input + emits prompt + output.
        out = ''
        for _ in range(6):
            try:
                out += await asyncio.wait_for(ws.recv(), timeout=2.0)
            except (asyncio.TimeoutError, ConnectionClosed):
                break
        assert '/' in out, f'no path in output: {out!r}'
        print('happy OK')

async def bad_id():
    try:
        async with websockets.connect('ws://127.0.0.1:8091/pty/..%2Fetc%2Fpasswd', origin='http://127.0.0.1:8090') as ws:
            await ws.recv()
        raise SystemExit('FAIL: bad id was accepted')
    except (ConnectionClosed, InvalidStatus, websockets.exceptions.InvalidURI):
        print('bad-id OK')

async def bad_origin():
    try:
        async with websockets.connect('ws://127.0.0.1:8091/pty/test-1', origin='http://evil.example') as ws:
            await ws.recv()
        raise SystemExit('FAIL: bad origin was accepted')
    except (InvalidStatus, ConnectionClosed):
        print('bad-origin OK')

asyncio.run(happy()); asyncio.run(bad_id()); asyncio.run(bad_origin())

# Context route
req = urllib.request.Request('http://127.0.0.1:8091/context/test-1', headers={'Origin': 'http://127.0.0.1:8090'})
with urllib.request.urlopen(req, timeout=3) as r:
    body = r.read().decode()
    json.loads(body)  # must parse
    print('context-route OK', r.status)
"
RC=$?; kill $DAEMON 2>/dev/null; wait $DAEMON 2>/dev/null; exit $RC</automated>
  </verify>
  <done>
    Four checks pass with the daemon running on 8091:
    (a) `pwd` over WS returns a path string. (b) Path-traversal pane id is
    rejected. (c) Foreign Origin is rejected pre-upgrade. (d)
    `/context/test-1` returns valid JSON (object or empty). The verification
    log comment block exists at the bottom of `lib/pty_server.py`.
  </done>
</task>

</tasks>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser → daemon | Frontend (`http://127.0.0.1:8090`) opens WebSocket to daemon (`ws://127.0.0.1:8091`). Untrusted browser-supplied path segments + headers cross here. |
| daemon → host shell | Daemon spawns real PTYs as the current user. Once spawned the shell can execute arbitrary commands the user could run interactively — that is the feature, not a vulnerability — but any attacker who can speak to the daemon inherits this capability. |
| daemon → filesystem | `load_pane_context` reads `.invisible-checkpoint.json` from worktree paths derived from pane id. Pane id must not become a path-traversal vector. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-01 | Tampering | pane_id path segment in `/pty/{id}` & `/context/{id}` | mitigate | `PANE_ID_RE = ^[a-z0-9_-]{1,32}$` enforced before PTY spawn and before checkpoint read. URL-decoded id is matched against the regex; failures close the WS with code 1008 / return HTTP 400. (Task 1 + Task 3 (c)) |
| T-01-02 | Spoofing | Origin header on WebSocket upgrade | mitigate | `process_request` hook on `websockets.serve` rejects Origins not in `{http://127.0.0.1:8090, http://localhost:8090}` with HTTP 403 before upgrade. Prevents DNS-rebinding shells. (Task 1, verified Task 3 (c)) |
| T-01-03 | Elevation of Privilege | Network exposure | mitigate | `validate_host()` refuses to start the daemon with `--host` outside `{127.0.0.1, localhost, ::1}`. CLI exits 2 with an error message. (Task 1 + Task 2; verified by the second half of Task 2's automated check.) |
| T-01-04 | Denial of Service | Unbounded PTY spawn | mitigate | `MAX_CONCURRENT_PTYS = 32` cap in `PTYRegistry`. Reaching the cap closes new WS with code 1011 reason `"pty cap reached"`. (Task 1) |
| T-01-05 | Information Disclosure | `load_pane_context` reading checkpoints | mitigate | Worktree path derived from `home() / "worktrees" / pane_id / "feature"` after pane_id passes PANE_ID_RE — cannot escape the worktrees root. Returns `{}` if checkpoint absent (no errors leak path existence beyond the boolean). (Task 1) |
| T-01-06 | Repudiation | Untracked daemon actions | accept | Single-user local daemon; full shell history lives in the OS's own bash history. No audit trail is in scope for M1. |
| T-01-SC | Tampering | Python package installs (`websockets`, `ptyprocess`) | mitigate | Both are widely-used, well-known PyPI packages (websockets: 30M+ downloads/month, written by Aymeric Augustin; ptyprocess: 100M+ downloads/month, pexpect/IPython family). User installs via `pip install --user` per START_HERE.md; no auto-install step in the daemon. Daemon prints the install hint and exits cleanly if imports fail (no silent fallback). Acceptable. |

</threat_model>

<verification>

```bash
# All three task <automated> checks chained:
cd /Users/ace/.invisible-ws/terminals-pty

# Module imports + regex/origin shape
python3 -c "import sys; sys.path.insert(0, 'lib'); from pty_server import PTYServer, PANE_ID_RE, ALLOWED_ORIGINS, spawn_pty, load_pane_context, validate_host, validate_pane_id; assert PANE_ID_RE.match('test-1'); assert not PANE_ID_RE.match('../x'); assert validate_pane_id('a'); print('module OK')"

# Daemon binds + refuses 0.0.0.0
bin/invisible-pty --port 8091 &
PID=$!; sleep 1.5
lsof -nP -iTCP:8091 -sTCP:LISTEN
kill $PID; wait $PID 2>/dev/null
bin/invisible-pty --host 0.0.0.0 --port 8091; echo "exit=$?"  # must be non-zero

# End-to-end gates — see Task 3 automated check.
```

</verification>

<success_criteria>

- `lib/pty_server.py` exists with the seven named exports (`PTYServer`,
  `PANE_ID_RE`, `ALLOWED_ORIGINS`, `spawn_pty`, `load_pane_context`,
  `validate_host`, `validate_pane_id`).
- `bin/invisible-pty` is executable and mirrors `bin/invisible-dashboard`'s
  argparse + sys.path + main() shape.
- All five STRIDE mitigations (T-01-01 through T-01-05) are verifiable by
  the Task 3 automated check.
- Plan 02 can resume by importing the named exports without breaking changes.

</success_criteria>

<output>
Create `.planning/workstreams/terminals-pty/phases/INV-01-websocket-pty-daemon-terminals-page-wired/01-01-SUMMARY.md` when done.
</output>
