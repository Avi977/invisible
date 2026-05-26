---
phase: 01-websocket-pty-daemon-terminals-page-wired
plan: 02
type: execute
wave: 2
depends_on: ["01"]
files_modified:
  - lib/pty_server.py
  - bin/invisible-pty
  - invisible.toml.example
autonomous: true
requirements: [REQ-04]
must_haves:
  truths:
    - "Disconnecting a WebSocket from `/pty/{id}` does NOT immediately kill the PTY — the PtyProcess remains in the registry for a configurable grace period (default 600 seconds)."
    - "Reconnecting to `/pty/{id}` within the grace window reattaches to the SAME PtyProcess: the new client receives a backlog of the most recent N bytes (default 8 KiB) followed by live output. The PTY's working state (cwd, env, running foreground process) is preserved."
    - "PTYs whose grace window expires without a reconnect are reaped: PtyProcess.terminate(force=True) called, registry entry removed. Daemon restart clears all PTYs (intentional — in-memory only)."
    - "Pane configs loaded from `invisible.toml` under `[[terminals]]` blocks. Each block has `id` (matches PANE_ID_RE), `kind` ∈ {`bash`, `ssh`}, optional `host` (ssh-only), optional `cwd`. Unknown ids fall back to a default plain-bash pane."
    - "SSH variant: when a pane's config kind is `ssh`, spawn_pty launches `ssh <host>` instead of bash. Host comes from server-side config ONLY — never from the WebSocket path or query string."
    - "Concurrent-PTY cap (32) still enforced; reaper counts only live (not orphaned) PTYs."
  artifacts:
    - path: lib/pty_server.py
      provides: "Extended PTYRegistry with grace-window reaper + reconnect semantics; SSH variant in spawn_pty; pane_configs loaded from invisible.toml"
      contains: "RECONNECT_GRACE_SECONDS, BACKLOG_BYTES, reaper task, load_pane_configs, kind='ssh' branch"
    - path: bin/invisible-pty
      provides: "CLI gains --reconnect-grace and --config flags; loads pane configs at startup"
      contains: "load_pane_configs, --config /path/to/invisible.toml"
    - path: invisible.toml.example
      provides: "Documented [[terminals]] block sample"
      contains: "[[terminals]]"
  key_links:
    - from: lib/pty_server.py
      to: invisible.toml
      via: "load_pane_configs(path) reads [[terminals]] blocks via tomllib"
      pattern: "tomllib|\\[\\[terminals\\]\\]"
    - from: lib/pty_server.py (PTYRegistry)
      to: "asyncio reaper task"
      via: "asyncio.create_task on PTYServer.serve_async() startup, sweeps registry every 30s for entries whose ws is None and (now - disconnected_at) > grace"
      pattern: "asyncio.create_task|sweep|grace"
    - from: lib/pty_server.py
      to: "ptyprocess.PtyProcess (ssh)"
      via: "spawn_pty(..., command=['ssh', host]) when pane kind == 'ssh'"
      pattern: "'ssh'|spawn.*ssh"
---

<objective>
Replace Plan 01's "every disconnect kills the PTY" behavior with a real
session-persistence layer: WebSocket disconnect parks the PTY in the registry
with a backlog ring buffer; the next connection to the same pane id within the
grace window reattaches and replays the backlog; PTYs whose grace expires are
reaped. Also wires the SSH variant by loading `[[terminals]]` pane configs
from `invisible.toml` (server-side only, never URL-controlled).

Purpose: This is what makes Success Criterion #3 (sessions survive page reload)
and #4 (SSH variants from config) actually true.

Output: An extended `lib/pty_server.py` with a grace-window reaper + reconnect
path + ssh branch, an extended `bin/invisible-pty` that loads pane configs at
startup, and an `invisible.toml.example` block documenting the schema.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/workstreams/terminals-pty/phases/INV-01-websocket-pty-daemon-terminals-page-wired/01-01-SUMMARY.md
@.planning/workstreams/terminals-pty/ROADMAP.md

@lib/pty_server.py
@bin/invisible-pty
@invisible.toml.example

<interfaces>
<!-- Stable contracts from Plan 01 you extend. DO NOT rename. -->

Already in lib/pty_server.py from Plan 01:
- PANE_ID_RE, ALLOWED_ORIGINS, MAX_CONCURRENT_PTYS, DEFAULT_SHELL
- validate_host(host), validate_pane_id(pane_id), check_origin(origin)
- spawn_pty(pane_id, cwd=None, env=None, command=None) -> PtyProcess
- PTYRegistry: register/get/count/unregister (you EXTEND, don't rename)
- load_pane_context(worktree_path) -> dict
- PTYServer.handle_pty (you REWRITE the disconnect branch)
- PTYServer.serve_async (you ADD reaper task here)

Python 3.11+ tomllib is stdlib — `import tomllib` (read mode is binary):
- `with open(path, 'rb') as f: cfg = tomllib.load(f)`
- `cfg.get('terminals', [])` returns list[dict]
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Extend PTYRegistry with backlog, grace timer, and reaper</name>
  <files>lib/pty_server.py</files>
  <read_first>
    - lib/pty_server.py (full file — find the `TODO(plan-02): reconnect grace` marker from Plan 01)
    - .planning/workstreams/terminals-pty/phases/INV-01-websocket-pty-daemon-terminals-page-wired/01-01-SUMMARY.md (to confirm the Plan 01 surface that landed)
  </read_first>
  <action>
    Add module constants near the top: `RECONNECT_GRACE_SECONDS = 600`,
    `BACKLOG_BYTES = 8 * 1024`, `REAPER_INTERVAL_SECONDS = 30`.

    Extend `PTYRegistry` entries to the shape
    `{proc, created_at, ws, disconnected_at: datetime | None, backlog: bytearray}`.
    `backlog` is a fixed-size ring (use a `collections.deque` with `maxlen` set
    to BACKLOG_BYTES, OR a bytearray that drops from the front when its length
    exceeds BACKLOG_BYTES — pick whichever is simpler; deque-of-bytes-chunks
    is fine if you also track total length).

    Add methods:
      - `attach_ws(pane_id, ws) -> bool`. If an entry exists and its `ws` is
        None, set `ws = ws`, clear `disconnected_at`, return True (reconnect
        path). If entry exists with a live ws, close the prior ws and replace
        (takeover — log to stderr). If no entry exists, return False (caller
        must spawn).
      - `detach_ws(pane_id) -> None`. Set `ws = None`, `disconnected_at = utcnow()`.
        Do NOT call `proc.terminate` here — that's the reaper's job.
      - `record_output(pane_id, chunk: bytes) -> None`. Appends to backlog,
        trims from the front if length > BACKLOG_BYTES.
      - `get_backlog(pane_id) -> bytes`. Returns current backlog.
      - `sweep(now: datetime, grace_seconds: int) -> list[str]`. Returns
        list of pane_ids whose `ws is None` AND
        `(now - disconnected_at).total_seconds() > grace_seconds`. Caller
        terminates + unregisters each.

    Rewrite `PTYServer.handle_pty(websocket, path)`:
      1. Parse + validate pane_id as before.
      2. If `registry.attach_ws(pane_id, websocket)` returned True: send the
         backlog to the new client immediately (`await websocket.send(backlog)`),
         then enter the bidi loop using the EXISTING proc from the registry
         entry. This is the reconnect path.
      3. Else: enforce cap; resolve config via `self.pane_configs.get(pane_id, {})`;
         spawn PTY using config's kind/host/cwd (Task 3 below adds the SSH branch
         to spawn_pty); register entry with `ws = websocket`,
         `backlog = bytearray()`, `disconnected_at = None`. This is the fresh
         path.
      4. Bidi loop changes: in the `pty_to_ws` direction, ALSO call
         `registry.record_output(pane_id, chunk)` before sending — so the
         backlog stays current for any reconnect.
      5. On either direction ending (ConnectionClosed or PTY EOF): if the PTY
         is still alive, call `registry.detach_ws(pane_id)` and EXIT the
         handler WITHOUT terminating the proc. If the PTY is dead (EOF from
         proc.read), `registry.unregister(pane_id)` and close the ws.

    Add a reaper coroutine `async def _reap_loop(self)`:
      - `while True: await asyncio.sleep(REAPER_INTERVAL_SECONDS); for pane_id
        in self.registry.sweep(datetime.now(timezone.utc), self.reconnect_grace):
        terminate the proc, unregister, log to stderr
        f"[invisible-pty] reaped {pane_id} after {self.reconnect_grace}s idle"`.

    In `PTYServer.serve_async`, before `await websockets.serve(...)`, start the
    reaper: `self._reaper_task = asyncio.create_task(self._reap_loop())`. On
    shutdown (catch CancelledError or finally), cancel the reaper.

    Replace Plan 01's `# TODO(plan-02): reconnect grace` markers with the new
    code; remove the markers.

    Keep all Plan 01 public exports stable (do not rename any of: PTYServer,
    spawn_pty, validate_host, validate_pane_id, load_pane_context,
    PANE_ID_RE, ALLOWED_ORIGINS).
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/terminals-pty &amp;&amp; python3 -c "
import sys; sys.path.insert(0, 'lib')
from pty_server import PTYRegistry, RECONNECT_GRACE_SECONDS, BACKLOG_BYTES
from datetime import datetime, timezone, timedelta
r = PTYRegistry()
# Simulate spawn
class FakeProc: pass
r.register('a', FakeProc())
r.attach_ws('a', object())
r.record_output('a', b'hello ')
r.record_output('a', b'world')
assert r.get_backlog('a').endswith(b'hello world'), r.get_backlog('a')
# Disconnect — proc must survive
r.detach_ws('a')
e = r.get('a')
assert e['ws'] is None and e['disconnected_at'] is not None and e['proc'] is not None
# Sweep with short grace — should reap
now = datetime.now(timezone.utc) + timedelta(seconds=RECONNECT_GRACE_SECONDS + 1)
reaped = r.sweep(now, RECONNECT_GRACE_SECONDS)
assert reaped == ['a'], reaped
print('registry persistence + sweep OK; grace=%ds backlog=%d' % (RECONNECT_GRACE_SECONDS, BACKLOG_BYTES))
"</automated>
  </verify>
  <done>
    PTYRegistry exposes the six methods above. Backlog truncates to
    BACKLOG_BYTES. Detached entries survive `detach_ws`. `sweep` returns
    pane_ids past grace. Plan 01 exports remain intact (import test).
  </done>
</task>

<task type="auto">
  <name>Task 2: Add SSH variant and load pane configs from invisible.toml</name>
  <files>lib/pty_server.py, bin/invisible-pty, invisible.toml.example</files>
  <read_first>
    - invisible.toml.example (full file — current shape)
    - lib/pty_server.py (find Plan 01 `TODO(plan-02): ssh variant` marker)
    - bin/invisible-pty (argparse block)
  </read_first>
  <action>
    In `lib/pty_server.py`:

    Define `load_pane_configs(path: Path | str) -> dict[str, dict]`. If path
    doesn't exist OR can't be parsed, return `{}` (do not raise — daemon still
    runs with all-default bash panes). Use `tomllib.load(open(path, 'rb'))`.
    Iterate `cfg.get('terminals', [])` and build a `{id: entry}` map. Each
    entry MUST have a string `id` matching PANE_ID_RE and a `kind` ∈
    {`"bash"`, `"ssh"`}. SSH entries MUST have `host` (string). Drop any entry
    that fails validation, printing a stderr warning naming the bad id and the
    reason. Allowed optional keys: `cwd` (string), `env` (table of strings),
    `command` (list[str] — overrides the default for kind='bash' if present).

    Define `resolve_command(config: dict) -> list[str]`:
      - kind 'bash': `config.get('command') or [DEFAULT_SHELL, '-i']`.
      - kind 'ssh': `['ssh', config['host']]` (host is the SERVER-SIDE config,
        NEVER from the URL). Hardcode this — the path id is only the lookup key.

    Update `spawn_pty(pane_id, cwd=None, env=None, command=None)`:
      - If `command is None` callers should now go through `resolve_command`
        — but keep the old signature working. Add a second helper
        `spawn_pty_for_config(pane_id, config)` that calls `resolve_command(config)`,
        merges `config.get('env')` over os.environ, uses `config.get('cwd')`
        (expanded with `os.path.expanduser`), and delegates to `spawn_pty(...)`.
      - Cap check (MAX_CONCURRENT_PTYS) still applies.

    Update `PTYServer.__init__` signature to accept `pane_configs: dict[str, dict] | None = None`
    and `reconnect_grace: int = RECONNECT_GRACE_SECONDS`. Store on self.

    In `handle_pty`'s fresh-spawn branch, call `spawn_pty_for_config(pane_id,
    self.pane_configs.get(pane_id, {'kind': 'bash'}))` instead of bare
    `spawn_pty(pane_id)`.

    Replace the `# TODO(plan-02): ssh variant` marker with the call to
    `spawn_pty_for_config`.

    In `bin/invisible-pty`:

    Add argparse flags:
      - `--config PATH` (default: `Path(os.environ.get('INVISIBLE_HOME', Path.home() / '.invisible')) / 'invisible.toml'`)
      - `--reconnect-grace SECONDS` (int, default RECONNECT_GRACE_SECONDS — import this constant from pty_server)

    Before instantiating PTYServer, call
    `pane_configs = load_pane_configs(args.config)`. Print to stdout one line
    summarizing what loaded: `f"[invisible-pty] loaded {len(pane_configs)} pane config(s) from {args.config}"`.
    Pass both `pane_configs=pane_configs` and `reconnect_grace=args.reconnect_grace`
    into PTYServer.

    In `invisible.toml.example`:

    Append a `# ── Terminals ──` section with a sample documented block:

      [[terminals]]
      id = "local-1"
      kind = "bash"
      cwd = "~/code"

      [[terminals]]
      id = "vps-srv"
      kind = "ssh"
      host = "srv982719"

      # id must match ^[a-z0-9_-]{1,32}$
      # kind ∈ {"bash", "ssh"}; ssh requires host
      # host is server-side ONLY — the frontend cannot override it via the URL

    DO NOT touch any [[projects]] / [[clients]] entries already in the file.
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/terminals-pty &amp;&amp; python3 -c "
import sys, tempfile, pathlib
sys.path.insert(0, 'lib')
from pty_server import load_pane_configs, resolve_command, PANE_ID_RE
toml = b'''
[[terminals]]
id = \"vps-srv\"
kind = \"ssh\"
host = \"srv982719\"

[[terminals]]
id = \"local-1\"
kind = \"bash\"

[[terminals]]
id = \"BAD ID\"
kind = \"bash\"

[[terminals]]
id = \"ssh-no-host\"
kind = \"ssh\"
'''
p = pathlib.Path(tempfile.mktemp(suffix='.toml')); p.write_bytes(toml)
cfg = load_pane_configs(p)
assert 'vps-srv' in cfg and cfg['vps-srv']['kind'] == 'ssh' and cfg['vps-srv']['host'] == 'srv982719'
assert 'local-1' in cfg
assert 'BAD ID' not in cfg, 'invalid id should be rejected'
assert 'ssh-no-host' not in cfg, 'ssh without host should be rejected'
assert resolve_command(cfg['vps-srv']) == ['ssh', 'srv982719']
assert resolve_command(cfg['local-1'])[0].endswith('sh'), resolve_command(cfg['local-1'])
print('configs OK; ssh whitelist enforced')
" &amp;&amp; grep -q '^\[\[terminals\]\]' invisible.toml.example &amp;&amp; echo "toml example OK"</automated>
  </verify>
  <done>
    `load_pane_configs` parses the sample, rejects invalid ids + ssh-no-host
    entries with stderr warnings. `resolve_command` returns `['ssh', host]`
    for ssh kind. `invisible.toml.example` contains a `[[terminals]]` block
    with comment lines explaining the regex + ssh host policy. `bin/invisible-pty`
    accepts `--config` and `--reconnect-grace` and reports load count on
    startup.
  </done>
</task>

<task type="auto">
  <name>Task 3: Verify reconnect persistence + SSH config end-to-end</name>
  <files>lib/pty_server.py</files>
  <read_first>
    - lib/pty_server.py (the two prior tasks landed here)
    - bin/invisible-pty
  </read_first>
  <action>
    Run a verification scenario that proves persistent sessions across
    WebSocket disconnects:

    1. Write a temp invisible.toml with one bash entry (`id = "persist-1"`).
    2. Start `bin/invisible-pty --port 8091 --config <tmp> --reconnect-grace 60`.
    3. Connect WS to `ws://127.0.0.1:8091/pty/persist-1`. Send
       `export PERSIST_MARKER=42\n` then `pwd\n`. Wait for output. Close the
       WS.
    4. Wait 3 seconds (well under the 60s grace).
    5. Reconnect WS to the same pane_id. Send `echo "marker=$PERSIST_MARKER"\n`.
       Expect the response to contain `marker=42`. THIS IS THE TEST — if the
       env var survives, the PTY persisted.
    6. Backlog smoke: the reconnect should also receive at least 1 byte
       immediately upon connect (the backlog frame from the prior session).

    If the env var is lost, the persistence path is broken — fix the
    `handle_pty` reconnect branch in `lib/pty_server.py` (likely the
    `attach_ws` lookup or the bidi loop is spawning a new proc instead of
    reusing the registry's). Re-run until green.

    Append a `# PLAN-02 verification log` comment block at the bottom of
    `lib/pty_server.py` listing the three checks that pass (persistence,
    backlog replay, ssh config validation). Plan 03 greps for this marker
    before wiring the frontend.

    SSH end-to-end is NOT required to hit a real host in this task — the
    config-loading test in Task 2 is sufficient. Hitting srv982719 belongs
    in the phase-level UAT, not this task.
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/terminals-pty &amp;&amp; TMPCFG=$(mktemp -t inv-pty.XXXXXX.toml); printf '[[terminals]]\nid = "persist-1"\nkind = "bash"\n' > "$TMPCFG"; bin/invisible-pty --port 8091 --config "$TMPCFG" --reconnect-grace 60 &amp; DAEMON=$!; sleep 1.5; python3 -c "
import asyncio, websockets
from websockets.exceptions import ConnectionClosed

async def collect(ws, n_frames=8, timeout=1.5):
    out = ''
    for _ in range(n_frames):
        try:
            out += await asyncio.wait_for(ws.recv(), timeout=timeout)
        except (asyncio.TimeoutError, ConnectionClosed):
            break
    return out

async def main():
    async with websockets.connect('ws://127.0.0.1:8091/pty/persist-1', origin='http://127.0.0.1:8090') as ws:
        await ws.send('export PERSIST_MARKER=42\n')
        await asyncio.sleep(0.3)
        await ws.send('pwd\n')
        await collect(ws)
    # Disconnect for a moment, then reconnect.
    await asyncio.sleep(3)
    async with websockets.connect('ws://127.0.0.1:8091/pty/persist-1', origin='http://127.0.0.1:8090') as ws:
        # Backlog should be delivered ASAP — read a frame quickly:
        try:
            first = await asyncio.wait_for(ws.recv(), timeout=2.0)
        except asyncio.TimeoutError:
            first = ''
        # Now ask the SAME shell whether the env var still exists.
        await ws.send('echo MARKER_IS_$PERSIST_MARKER\n')
        out = await collect(ws, n_frames=10, timeout=2.0)
        full = first + out
        assert 'MARKER_IS_42' in full, f'env var did NOT survive reconnect: {full!r}'
        print('persistence + backlog OK')

asyncio.run(main())
"; RC=$?; kill $DAEMON 2>/dev/null; wait $DAEMON 2>/dev/null; rm -f "$TMPCFG"; exit $RC</automated>
  </verify>
  <done>
    Reconnecting after a 3-second disconnect to the same pane_id finds the
    `PERSIST_MARKER=42` env var still set in the shell — proving the PtyProcess
    persisted. The reconnect also receives at least one frame of backlog.
    `# PLAN-02 verification log` comment block exists at the bottom of
    `lib/pty_server.py`.
  </done>
</task>

</tasks>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| URL → pane config | Pane id from the URL is used ONLY as a lookup key into server-side `pane_configs`. The SSH host and command come from `invisible.toml` (server-side, trusted). |
| invisible.toml → daemon | The TOML file is user-controlled but local-only and read-once at startup. Malformed entries are dropped with a stderr warning, not silently merged. |
| persisted PTY → next user | If two different humans share the same daemon process and the same pane id, the second connection inherits the first's running shell. Out of scope (REQ states single-user). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-01 | Elevation of Privilege | SSH host derivation | mitigate | `resolve_command` reads `host` from `pane_configs[pane_id]['host']` ONLY. The URL path's pane id is a lookup key, never interpolated into the ssh argv. Pane configs are loaded from `invisible.toml` at startup, validated against PANE_ID_RE, and ssh entries without `host` are dropped. (Task 2 verified by the `ssh-no-host` rejection assertion.) |
| T-02-02 | Denial of Service | Orphaned PTYs from disconnected clients | mitigate | Reaper task runs every 30 seconds, terminates PTYs whose `ws is None` AND `disconnected_at` is older than `--reconnect-grace` (default 600s). MAX_CONCURRENT_PTYS cap still applies. (Task 1) |
| T-02-03 | Information Disclosure | Backlog buffer leaking previous output to next ws | accept | Backlog replay is the FEATURE that delivers Success Criterion #3. Single-user daemon. The same human runs both connections. Recorded explicitly so this disposition is auditable. |
| T-02-04 | Tampering | TOML config injection via env vars | mitigate | Pane `env` entries from TOML are validated as `dict[str, str]`; values are not shell-expanded; merged via dict overlay on os.environ. `cwd` is `os.path.expanduser`'d only — no shell expansion. (Task 2) |
| T-02-05 | Spoofing | Reconnect to someone else's pane id | accept | Local 127.0.0.1 binding + Plan 01's Origin check are the trust boundary. No per-user auth on individual panes — REQ-04 doesn't ask for one and this is a single-user daemon. |

</threat_model>

<verification>

```bash
# Registry persistence + sweep — Task 1 automated check.

# Config loading + ssh whitelist — Task 2 automated check.

# End-to-end persistence across WS disconnect — Task 3 automated check.

# Daemon still imports cleanly after edits:
python3 -c "import sys; sys.path.insert(0, 'lib'); from pty_server import PTYServer, PTYRegistry, load_pane_configs, resolve_command, RECONNECT_GRACE_SECONDS, BACKLOG_BYTES; print('OK')"

# All Plan 01 exports still intact:
python3 -c "import sys; sys.path.insert(0, 'lib'); from pty_server import PANE_ID_RE, ALLOWED_ORIGINS, spawn_pty, load_pane_context, validate_host, validate_pane_id; print('plan-01 surface intact')"
```

</verification>

<success_criteria>

- Plan 01's seven exports still importable (no breaking renames).
- New exports landed: `PTYRegistry` enhanced methods, `load_pane_configs`,
  `resolve_command`, `RECONNECT_GRACE_SECONDS`, `BACKLOG_BYTES`.
- PTY survives a 3-second disconnect; env var set before disconnect is
  observable after reconnect.
- TOML config loads with malformed entries dropped (not crashed-on).
- `bin/invisible-pty` CLI documents `--config` and `--reconnect-grace`.
- `invisible.toml.example` shows the schema with a comment about the SSH
  host policy.

</success_criteria>

<output>
Create `.planning/workstreams/terminals-pty/phases/INV-01-websocket-pty-daemon-terminals-page-wired/01-02-SUMMARY.md` when done.
</output>
