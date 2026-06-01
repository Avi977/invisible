---
phase: INV-01-websocket-pty-daemon-terminals-page-wired
plan: 02
subsystem: terminals
tags: [websocket, pty, asyncio, tomllib, ssh, security, asvs-l1, session-persistence]

# Dependency graph
requires:
  - phase: INV-01 / plan 01
    provides: lib/pty_server.py with PTYServer, PTYRegistry, PANE_ID_RE, ALLOWED_ORIGINS, validate_host, spawn_pty, load_pane_context, validate_pane_id (all preserved verbatim)
provides:
  - PTYRegistry extended with attach_ws / detach_ws / record_output / get_backlog / sweep
  - RECONNECT_GRACE_SECONDS (=600), BACKLOG_BYTES (=8192), REAPER_INTERVAL_SECONDS (=30)
  - load_pane_configs(path) -> dict[str, dict] reading invisible.toml [[terminals]] blocks
  - resolve_command(config) -> list[str] (bash default vs ssh whitelist)
  - spawn_pty_for_config(pane_id, config) -> PtyProcess (cwd expanduser + env overlay)
  - PTYServer.__init__ now accepts (pane_configs, reconnect_grace) kwargs
  - PTYServer._reap_loop background coroutine — sweeps every 30s
  - bin/invisible-pty CLI flags: --config PATH, --reconnect-grace SECONDS
  - invisible.toml.example [[terminals]] documented sample with kind=bash + kind=ssh
affects: [terminals-pty/03-frontend-wire]

# Tech tracking
tech-stack:
  added: [tomllib (stdlib Python 3.11+)]
  patterns:
    - "Bounded `bytearray` ring buffer per pane; trim from front on overflow (O(n) but only on overflow)"
    - "Park-on-disconnect + periodic reaper coroutine; sweep is a pure observation function safe to call from event loop"
    - "TOML pane configs validated entry-by-entry with stderr warnings; never raise — daemon survives malformed [[terminals]]"
    - "Argv lock for ssh kind: host comes only from server-side config; `command` override silently dropped for ssh"
    - "`# PLAN-02 verification log` end-of-file comment is the grep marker Plan 03 uses to confirm surface stability"

key-files:
  created:
    - .planning/workstreams/terminals-pty/phases/INV-01-websocket-pty-daemon-terminals-page-wired/02-SUMMARY.md (this file)
  modified:
    - lib/pty_server.py (586 → 1211 lines; +625 net, all extensions, zero deletions of named exports)
    - bin/invisible-pty (96 → 145 lines; added --config + --reconnect-grace + load_pane_configs plumbing)
    - invisible.toml.example (24 → 53 lines; appended documented [[terminals]] section)

key-decisions:
  - "Backlog stored as a single bytearray (not deque-of-chunks) because the read side is `send the whole buffer in one frame on reconnect`; byte-granular trim with `del backlog[:n]` is amortised O(1) over the steady-state stream."
  - "Reaper counts ALL PtyProcesses in the registry against the 32-cap, including parked orphans waiting for reap. Cap is about daemon memory, not active clients. Reaper is what actually shrinks the count."
  - "Daemon restart clears all PTYs — in-memory only, intentional. Durable cross-restart persistence would require checkpointing termios + cwd + env + running fg process, well out of scope for v1."
  - "ssh kind's argv is locked to `['ssh', host]`. Allowing `command` override for ssh would reopen T-02-01 (URL-controlled argv), so the loader silently drops `command` for kind=ssh with a stderr warning."
  - "TOML env table validation: if ANY value is non-string, the whole env table is dropped (not just the bad key). Partial overlays are too easy to misread when debugging a running daemon."
  - "PTYServer constructor adds two NEW kwargs (pane_configs, reconnect_grace) but preserves positional `host`/`port`. No breaking change to Plan 01 callers."
  - "`/context/{pane_id}` worktree mapping NOT swapped for `pane_configs[id]['cwd']`. Endpoint exposes checkpoint context (per-worktree), not pane cwd. Out of scope for Plan 02; the legacy mapping `home()/worktrees/{id}/feature` still applies."

patterns-established:
  - "Constants block + new methods slot in below the Plan 01 PTYRegistry surface; old methods (register/get/count/unregister) preserved verbatim."
  - "Per-pane spawn dispatcher (`_spawn_for_pane`) on PTYServer keeps `handle_pty` ignorant of bash-vs-ssh — Plan 02 only swaps the body."
  - "PLAN-NN verification log marker at EOF: structured comment block listing which gates were verified end-to-end vs unit-asserted. Plan 03 greps for this marker."

requirements-completed: [REQ-04]

# Metrics
duration: 9m43s
completed: 2026-05-26
---

# Phase INV-01 Plan 02: Session Persistence + SSH Variant Summary

**Replaced Plan 01's kill-on-disconnect PTY teardown with a 600s reconnect-grace + 8 KiB backlog ring + background reaper; wired `invisible.toml [[terminals]]` so `kind="ssh"` spawns `ssh <host>` with the host coming from server-side config only (never the URL).**

## Performance

- **Duration:** 9m43s
- **Started:** 2026-05-27T02:03:54Z
- **Completed:** 2026-05-27T02:13:37Z
- **Tasks:** 3 / 3
- **Files created:** 0 (plus this SUMMARY.md)
- **Files modified:** 3 (`lib/pty_server.py`, `bin/invisible-pty`, `invisible.toml.example`)
- **LOC added:** ~700 net (extensions only — Plan 01 exports preserved verbatim)

## Accomplishments

- **`PTYRegistry` extended** with five new methods — `attach_ws`, `detach_ws`, `record_output`, `get_backlog`, `sweep` — without touching the Plan 01 surface (`register`, `get`, `count`, `unregister`). Each pane entry now carries `{proc, created_at, ws, disconnected_at, backlog}` so the reconnect path can reuse the same `PtyProcess` instance.
- **`PTYServer.handle_pty` rewritten** to a reconnect-first flow:
  - `attach_ws` → True → replay backlog as a single text frame, reuse the parked `PtyProcess`.
  - `attach_ws` → False → enforce the cap (orphans count), spawn via `_spawn_for_pane`, register, then `attach_ws`.
  - Exit branch chooses kill-and-unregister (PTY died) vs park-and-detach (ws gone).
- **`_reap_loop` background coroutine** launched in `serve_async`, sweeps the registry every 30s, terminates panes whose `(now - disconnected_at) > reconnect_grace`, logs `reaped {id} after {n}s idle` to stderr. Cancelled cleanly on shutdown.
- **`load_pane_configs`** reads `[[terminals]]` blocks via `tomllib`. Every entry validated against `PANE_ID_RE`, `kind ∈ {bash, ssh}`, required `host` for ssh. Malformed entries dropped individually with descriptive stderr warnings. Missing/unparsable file ⇒ `{}` (daemon survives).
- **`resolve_command`** hard-codes argv-by-kind: `["ssh", host]` for ssh (host pulled only from trusted TOML), `[DEFAULT_SHELL, "-i"]` (or the bash entry's `command` override) for bash. `command` override silently dropped for ssh — argv is locked. (T-02-01)
- **`bin/invisible-pty` CLI** gains `--config PATH` (defaults to `$INVISIBLE_HOME/invisible.toml`) and `--reconnect-grace SECONDS` (default 600). Prints `loaded N pane config(s) from PATH` at startup.
- **`invisible.toml.example`** gets a fully-commented `[[terminals]]` section with one `bash` and one `ssh` sample, plus inline notes on the PANE_ID_RE pattern and the server-side-only host policy.
- **End-to-end persistence proven**: WS-connect, `export PERSIST_MARKER=42`, disconnect, sleep 3s, reconnect — received an 988-byte backlog replay followed by `MARKER_IS_42` from the same `PtyProcess`. Plan's verbatim verify scenario passes.

## Task Commits

Each task was committed atomically on branch `worktree-agent-a4ecf8bc87fbf2aae`:

1. **Task 1: Extend PTYRegistry with backlog, grace timer, and reaper** — `1444d5a` (feat)
2. **Task 2: Add SSH variant and load pane configs from invisible.toml** — `a20c0db` (feat)
3. **Task 3: Verify reconnect persistence + SSH config end-to-end** — `8262065` (test)

_Plan metadata commit (this SUMMARY.md) follows the three task commits._

## Files Created / Modified

- `lib/pty_server.py` — Plan 02 adds module constants (RECONNECT_GRACE_SECONDS / BACKLOG_BYTES / REAPER_INTERVAL_SECONDS), extended PTYRegistry methods, the load_pane_configs + resolve_command + spawn_pty_for_config trio, rewritten handle_pty (reconnect-aware) + _spawn_for_pane dispatcher, _reap_loop coroutine, and the `# PLAN-02 verification log` EOF marker. All Plan 01 named exports preserved verbatim — `validate_host`, `validate_pane_id`, `check_origin`, `spawn_pty`, `load_pane_context`, `PANE_ID_RE`, `ALLOWED_ORIGINS`, `MAX_CONCURRENT_PTYS`, `DEFAULT_SHELL`, `PTYServer`, `PTYRegistry` all still importable with the same signatures. PTYServer.__init__ gained two new kwargs (positional args unchanged).
- `bin/invisible-pty` — Argparse extended with `--config PATH` and `--reconnect-grace SECONDS`. Loads `pane_configs` via `load_pane_configs(args.config)` before instantiating `PTYServer`. Prints `[invisible-pty] loaded N pane config(s) from PATH` at startup so the user can confirm the TOML was found.
- `invisible.toml.example` — Appended a `# ── Terminals ──` section with documented `[[terminals]]` blocks (one bash, one ssh) and inline comments enforcing the PANE_ID_RE pattern + the server-side-only host policy. Existing `[[projects]]` / `[[clients]]` / `[vps]` / `[orchestrator]` blocks untouched.

## Decisions Made

- **Bytearray ring buffer over deque-of-chunks.** Drop-from-front via `del backlog[:n]` is O(n) per overflow, but the steady-state path is the cheap `extend` — overflow only fires when output exceeds 8 KiB. Read side is `bytes(entry["backlog"])` snapshot for replay.
- **Reaper counts parked entries against the cap.** Justification: the 32-cap is about daemon memory pressure, not active clients. If a user opens 32 tabs, closes them all without reaping, then opens a 33rd, they should get "try again later" not a new spawn — the prior 32 PtyProcesses are still resident.
- **ssh argv locked.** `load_pane_configs` accepts `command` override for kind=bash but silently drops it for kind=ssh with a stderr warning. Allowing ssh to override `command` would reopen the URL→argv injection path that T-02-01 closes.
- **Env table all-or-nothing.** If any TOML env value is non-string, the whole env table is dropped with a warning. Partial overlays are an operational footgun — easier to fix the TOML once than to debug a daemon running with half the intended environment.
- **`/context/{pane_id}` worktree mapping not changed.** The endpoint exposes checkpoint context (per-worktree), not pane state. Plan 02's scope was "session persistence + ssh variant", not endpoint refactoring. Comment in the code documents the path for a future plan that wants to align them.
- **No durable cross-restart persistence.** PTY state (termios, cwd, env, running fg process) lives only in process memory. Restarting the daemon clears all panes. Implementing durability would require either ptrace-style state capture (complex, fragile) or pinning panes to detached `tmux` sessions (adds an external dependency the project explicitly doesn't want for v1).

## Deviations from Plan

None — plan executed exactly as written. All three task `<verify>` checks passed on the first end-to-end run. No Rule 1 / 2 / 3 auto-fixes triggered. No Rule 4 architectural questions.

Two operational notes worth recording (neither a deviation):

- **Reaper sweep interval is 30s.** A short `--reconnect-grace=2` doesn't reap in 2 seconds — the reaper still only sweeps every 30s. This is fine for production use (grace defaults to 600s, so 30s granularity is invisible) but Task 3's verify spec uses the 60s grace + 3s disconnect path which doesn't depend on the sweep firing — only on `attach_ws` finding the existing entry. The reaper logic was therefore validated at the registry level via `sweep(future_time, short_grace)` in Task 1's verify, not via a wall-clock end-to-end run.
- **Daemon stdout is line-buffered when backgrounded** (carried over from Plan 01). The startup banner only flushes on signal/shutdown when no TTY is attached. The LISTEN socket appears immediately, so the verify scripts use `lsof -iTCP:8091 -sTCP:LISTEN` (Plan 01 pattern) and direct WS connection rather than tailing the log.

## Threat-Model Gates Verified

| ID | Category | Disposition | Verified by |
|----|----------|-------------|-------------|
| T-02-01 | Elevation of Privilege (SSH argv) | mitigate | Task 2 unit: `load_pane_configs` rejects ssh-without-host; `resolve_command` produces `['ssh', host]` with host from TOML only. URL pane id reaches `pane_configs.get(id, {})` for lookup, never reaches `resolve_command`. ssh `command` override silently dropped. |
| T-02-02 | Denial of Service (orphan PTYs) | mitigate | Task 1 unit: `sweep(now+grace+1, grace)` returns parked panes; reaper terminates + unregisters. Registry-level test (no 30s wall-clock wait) proved the sweep+terminate+unregister cycle. |
| T-02-03 | Information Disclosure (backlog) | accept | Documented — single-user daemon, backlog replay IS the feature. |
| T-02-04 | Tampering (TOML env injection) | mitigate | Task 2 unit: non-string env values drop the whole env table with stderr warning. cwd is `os.path.expanduser`'d only — no shell expansion. Verified with `env = { GOOD = "yes", BAD = 42 }` test case. |
| T-02-05 | Spoofing (cross-pane reconnect) | accept | Documented — Plan 01's Origin check + 127.0.0.1 binding is the trust boundary. No per-pane auth for single-user daemon. |

## Threat Flags

None. Plan 02 did not introduce new security surface beyond what `02-PLAN.md`'s `<threat_model>` enumerates. The `/context/{pane_id}` endpoint is unchanged from Plan 01. `--config` and `--reconnect-grace` flags consume local-process state only.

## Verification Run Log

End-to-end Task 3 transcript (abridged, escape sequences redacted):

```
[step] first connection
[step] initial prompt: 'Restored session: Tue May 26 19:09:37 PDT 2026\r\n'
[step] after pwd: '…(base) ace@…macbook-air-… agent-… % …'
[step] sleeping 3s (well under 60s grace)
[step] reconnecting
[step] reconnect first frame (988B): backlog replay (cwd path, prompt)
[step] full transcript: '…export PERSIST_MARKER=42\r\n…pwd\r\n/Users/ace/…\r\n
                         …echo MARKER_IS_$PERSIST_MARKER\r\nMARKER_IS_42\r\n…'
persistence + backlog OK
```

The reconnected shell observed `PERSIST_MARKER=42` — proving the same `PtyProcess` survived the 3-second WS disconnect. Backlog frame size (988 B) is below the 8192 B cap, so no ring trim was exercised; the trim path is asserted by the Task 1 unit test that records `b'x' * (BACKLOG_BYTES + 200)` and verifies `len(get_backlog) == BACKLOG_BYTES`.

## Next Phase Readiness

- **Plan 03 (frontend wiring of `frontend/pages/terminals.jsx`)** can connect to `ws://127.0.0.1:8091/pty/{id}` with confidence that:
  - A reconnect within `--reconnect-grace` (default 600s) reattaches to the same shell — so page reloads, AI-chat detours, and tab restores all preserve session state.
  - The first frame after reconnect is the backlog (may be empty if the prior session produced nothing). The frontend's xterm.js should render this verbatim before subscribing to subsequent frames.
  - `[[terminals]]` blocks in `~/.invisible/invisible.toml` control which panes are `ssh` vs `bash`. The frontend addresses panes purely by id — `kind` and `host` come from server config.
- **All Plan 01 + Plan 02 named exports remain stable.** Plan 03 should not need to touch `lib/pty_server.py` at all; if it does, the `# PLAN-02 verification log` marker is the grep target to confirm surface stability before edits.
- **No blockers.** The daemon survives full lifecycle: spawn, connect, disconnect-park, reconnect-replay, reaper-cleanup, ssh-config-load. Three independent unit/integration checks pass on the persistence + backlog + config paths.

## Self-Check: PASSED

Verified before commit:

- `lib/pty_server.py` exists at 1211 lines (was 620 post-Plan-01). All Plan 01 + Plan 02 imports succeed.
- `bin/invisible-pty` exists at 145 lines (was 96 post-Plan-01), `chmod +x` preserved, `--help` shows `--config` and `--reconnect-grace`.
- `invisible.toml.example` exists at 53 lines (was 24 post-Plan-01), `^\[\[terminals\]\]` grep-hits.
- Task 1 commit `1444d5a` present in git log.
- Task 2 commit `a20c0db` present in git log.
- Task 3 commit `8262065` present in git log.
- `# PLAN-02 verification log` marker present in `lib/pty_server.py`.
- Zero remaining `TODO(plan-02)` markers in source — all consumed.
- End-to-end persistence test passed verbatim against a live daemon on port 8091.

---
*Phase: INV-01-websocket-pty-daemon-terminals-page-wired*
*Plan: 02*
*Completed: 2026-05-26*
