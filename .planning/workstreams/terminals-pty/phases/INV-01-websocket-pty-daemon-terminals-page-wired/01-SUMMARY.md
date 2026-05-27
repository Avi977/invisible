---
phase: INV-01-websocket-pty-daemon-terminals-page-wired
plan: 01
subsystem: terminals
tags: [websocket, pty, ptyprocess, asyncio, python, security, asvs-l1]

# Dependency graph
requires:
  - phase: bootstrap
    provides: bin/invisible-dashboard CLI shape + lib/checkpoint.py + lib/config.home()
provides:
  - bin/invisible-pty executable daemon on 127.0.0.1:8091
  - lib/pty_server.py with PTYServer, PANE_ID_RE, ALLOWED_ORIGINS, spawn_pty, load_pane_context, validate_host, validate_pane_id, PTYRegistry, MAX_CONCURRENT_PTYS
  - WebSocket route /pty/{pane_id} → bash PTY (bidirectional bytes)
  - HTTP side-channel /context/{pane_id} → checkpoint context JSON
  - Five enforced threat-model gates (T-01-01 .. T-01-05)
  - Stable named exports for Plan 02 to extend (reconnect grace, SSH variant, invisible.toml [[terminals]])
affects: [terminals-pty/02-session-persistence, terminals-pty/03-frontend-wire]

# Tech tracking
tech-stack:
  added: [websockets==16.0, ptyprocess==0.7.0]
  patterns:
    - "process_request hook as the pre-upgrade gate for Origin pinning + HTTP side-channel routing"
    - "asyncio.wait FIRST_COMPLETED race of pty_to_ws + ws_to_pty pumps with finally-teardown"
    - "PtyProcess.read run in default executor to keep loop responsive"
    - "Import-time dependency gate raises SystemExit with install hint (no silent fallback)"
    - "Plan-scoped TODO markers (`# TODO(plan-02): …`) identify extension seams"

key-files:
  created:
    - bin/invisible-pty (96 lines, executable Python daemon entrypoint)
    - lib/pty_server.py (620 lines, server module)
  modified: []

key-decisions:
  - "Module-level try/import block aborts startup with `python3 -m pip install --user websockets ptyprocess` hint if either dep is missing — matches START_HERE.md no-auto-install policy."
  - "Origin pinning is layered: explicit `_process_request` 403 + library `origins=` list, so the threat-model gate fires twice for defence-in-depth."
  - "Plan 01 behavior on reconnect to existing pane = last-writer-wins (kill old PTY, spawn new). Plan 02 owns the reattach-and-resume change."
  - "checkpoint.load → ContextHeader mapping documented inline since the persisted schema (task / feedback_history / last_summary / last_verdict) does not literally contain goal/activity/next."
  - "PTYServer constructor re-validates host (defence in depth) even though the CLI already calls validate_host — so a non-loopback host cannot be bypassed by importing the class directly."

patterns-established:
  - "Threat-model gates wired in code AND mapped to STRIDE IDs in the module docstring + verification log marker."
  - "`# PLAN-01 verification log` end-of-file comment is the grep target Plan 02 and Plan 03 use to confirm the daemon surface is stable."

requirements-completed: [REQ-04]

# Metrics
duration: 5min
completed: 2026-05-27
---

# Phase INV-01 Plan 01: PTY Daemon Scaffold Summary

**WebSocket PTY daemon on 127.0.0.1:8091 streaming real bash shells with five ASVS L1 threat-model gates and a `/context/{id}` checkpoint side-channel for the frontend's per-pane header.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-27T01:54:21Z
- **Completed:** 2026-05-27T01:59:17Z
- **Tasks:** 3 / 3
- **Files created:** 2 (`lib/pty_server.py`, `bin/invisible-pty`)
- **Files modified:** 0
- **LOC added:** ~716 (586 module + 96 CLI + 34 verification log marker)

## Accomplishments

- **`lib/pty_server.py` module** with seven named exports (`PTYServer`, `PANE_ID_RE`, `ALLOWED_ORIGINS`, `spawn_pty`, `load_pane_context`, `validate_host`, `validate_pane_id`) + `MAX_CONCURRENT_PTYS` + `PTYRegistry`. Surface is frozen for Plan 02 to extend.
- **`bin/invisible-pty` executable daemon** mirroring `bin/invisible-dashboard`'s argparse + sys.path + `main()` shape; binds 127.0.0.1:8091 by default; rejects non-loopback hosts with exit 2.
- **Five threat-model gates enforced and verified:**
  - T-01-01 — `PANE_ID_RE = ^[a-z0-9_-]{1,32}$` rejects path traversal / whitespace / uppercase / >32 chars before any PTY spawn.
  - T-01-02 — `_process_request` returns HTTP 403 pre-upgrade for any Origin not in `{http://127.0.0.1:8090, http://localhost:8090}`.
  - T-01-03 — `validate_host` raises `ValueError` (CLI translates to exit 2) for any host outside `{127.0.0.1, localhost, ::1}`.
  - T-01-04 — `MAX_CONCURRENT_PTYS = 32` cap closes excess connections with WS code 1013 ("try again later").
  - T-01-05 — `load_pane_context` returns `{}` when checkpoint absent; pane id is whitelisted before becoming a worktree path segment.
- **Side-channel `GET /context/{pane_id}`** maps the persisted checkpoint schema (`task`, `feedback_history`, `last_verdict`, `last_summary`) → display schema (`{goal, activity, next}`). Documented in `load_pane_context` docstring.
- **End-to-end verified live**: `pwd` round-trip over WebSocket succeeded (670 chars of shell output streamed back). Bad pane id closed with `ConnectionClosedError`. Foreign Origin closed with `InvalidStatus` (HTTP 403). Context route returned `200 {}` (JSON parses).

## Task Commits

Each task was committed atomically on branch `worktree-agent-a77808832c0755f28`:

1. **Task 1: Create `lib/pty_server.py` with WebSocket PTY server module** — `6a77347` (feat)
2. **Task 2: Create `bin/invisible-pty` executable daemon entrypoint** — `7fa29f3` (feat)
3. **Task 3: Verify headless PTY round-trip and threat-model gates end-to-end** — `1b241a5` (test)

_Plan metadata commit (SUMMARY.md + requirements update) follows this summary._

## Files Created / Modified

- `lib/pty_server.py` — 620 lines. Module that owns the daemon: dependency gate, constants (`PANE_ID_RE`, `ALLOWED_ORIGINS`, `MAX_CONCURRENT_PTYS`, `DEFAULT_SHELL`), validators (`validate_host`, `validate_pane_id`, `check_origin`), `spawn_pty` helper, `PTYRegistry`, `load_pane_context` checkpoint mapper, `PTYServer` class with async `handle_pty` / `_process_request` / `_handle_context_http` / `serve_async` / sync `serve`. Ends with a `PLAN-01 verification log` marker block listing which gates were verified end-to-end vs which are unit-asserted in adjacent tasks.
- `bin/invisible-pty` — 96 lines, chmod +x. Argparse (`--host`/`--port`), host gate via `validate_host`, instantiates `PTYServer`, calls `.serve()`. Mirrors `bin/invisible-dashboard` for visual familiarity.

## Decisions Made

- **Layered Origin enforcement** — `_process_request` returns a 403 explicitly, AND `websockets.serve(origins=...)` is passed the allow-list. Defence in depth; either alone would mitigate T-01-02 but having both is cheap.
- **Last-writer-wins on duplicate pane id (Plan 01 only)** — a fresh WS to an already-registered pane id terminates the old `PtyProcess` and spawns a new one. Plan 02 swaps this for "reattach to existing pane within grace window".
- **DEFAULT_SHELL pulls from `$SHELL`** — on this Mac that's `/bin/zsh`, on Linux usually `/bin/bash`. Either is fine; the round-trip test asserted the prompt + `pwd` worked regardless.
- **`PtyProcess.read` runs in `loop.run_in_executor`** — `proc.read` is blocking and `PtyProcess` doesn't expose an async variant. Default executor keeps the loop responsive without forcing aiofiles or aioprocess as new deps.
- **Constructor calls `validate_host` again** — even though the CLI gates `--host`, anyone importing `PTYServer` directly (e.g., from a future invisible.toml-driven invisible-orchestrator) gets the same gate. Cheap defence-in-depth.

## Deviations from Plan

None — plan executed exactly as written. All three task `<verify>` checks and the five threat-model mitigations passed on the first end-to-end run. No Rule 1 / 2 / 3 auto-fixes triggered. No Rule 4 architectural questions.

The only minor adjustment was operational: when the daemon launches via `nohup`/backgrounded shell (no TTY), Python's stdout is line-buffered and the `[invisible-pty] listening on …` banner only flushes on Ctrl-C. The LISTEN socket itself appears immediately, so `lsof` is the source of truth in the verify checks. Not a bug — just a stdout-buffering note for downstream tooling.

## Issues Encountered

- **Plan files were absent from the worktree at spawn time.** The orchestrator created the plan files in `/Users/ace/.invisible-ws/terminals-pty/.planning/...` after my worktree was forked from the base commit, so my worktree's `.planning/workstreams/terminals-pty/phases/` directory did not yet contain the plan or its phase folder. I read the plan from the orchestrator's CWD and created the phase folder in my worktree before writing this SUMMARY.md. No content was lost.
- **`websockets` v16 API note.** The `websockets.server.serve` import path is now deprecated; the module uses `websockets.asyncio.server.serve` instead. `additional_headers={'Origin': ...}` is the correct client kwarg for the Task 3 verification (the older `origin=` kwarg was removed in v15+). Mentioned here so Plan 02/03 don't trip on stale snippets.

## Threat Flags

None. All security surface introduced by this plan is enumerated in 01-PLAN.md's `<threat_model>` (T-01-01 through T-01-SC). No new endpoints, auth paths, file access patterns, or schema changes were added beyond what the plan declared.

## User Setup Required

None. The two Python dependencies (`websockets`, `ptyprocess`) are already importable in this environment. If the user installs Plan 01's outputs onto a fresh machine they will need:

```
python3 -m pip install --user websockets ptyprocess
```

The daemon prints this exact hint and exits cleanly if either import fails — no silent fallback (matches START_HERE.md no-auto-install policy).

## Next Phase Readiness

- **Plan 02 (session persistence + SSH variant)** can resume by importing the seven named exports from `lib/pty_server.py` without any breaking change. The `# TODO(plan-02): …` markers identify the four extension seams: handle_pty teardown (swap kill-on-disconnect for reconnect-grace + reap), spawn branch (add SSH variant when `cfg["ssh"]` is set), PTYServer constructor (populate `pane_configs` from `invisible.toml [[terminals]]`), and `_handle_context_http` (use `pane_configs[id]["worktree"]` instead of the hard-coded `home()/worktrees/{id}/feature` default).
- **Plan 03 (frontend wiring of `frontend/pages/terminals.jsx`)** can connect to `ws://127.0.0.1:8091/pty/{id}` and fetch `http://127.0.0.1:8091/context/{id}` immediately — both endpoints are stable. The ContextHeader's expected props are `{ctx: {goal, activity, next}, focused}` which exactly matches the JSON shape `load_pane_context` returns.
- **No blockers.** The daemon is runnable headlessly, all gates fire, and the contract for the next two plans is documented inline and in the verification log marker.

## Self-Check: PASSED

Verified before commit:

- `lib/pty_server.py` exists (586 lines pre-marker, 620 lines post-marker, all named exports importable).
- `bin/invisible-pty` exists, is `chmod +x`, and binds 127.0.0.1:8091 on `--port 8091`.
- Task 1 commit `6a77347` present in git log.
- Task 2 commit `7fa29f3` present in git log.
- Task 3 commit `1b241a5` present in git log.
- `# PLAN-01 verification log` marker grep-hits at `lib/pty_server.py:590`.
- End-to-end four-gate verification passed against a live daemon (happy path, bad pane id, bad origin, context route).

---
*Phase: INV-01-websocket-pty-daemon-terminals-page-wired*
*Plan: 01*
*Completed: 2026-05-27*
