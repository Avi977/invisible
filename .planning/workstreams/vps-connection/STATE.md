---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: M2 — VPS hardening
current_phase: 2
current_plan: 1
status: executing
stopped_at: N/A
last_updated: "2026-06-02T05:30:00.000Z"
last_activity: 2026-06-02
progress:
  total_phases: 3
  completed_phases: 1
  total_plans: 6
  completed_plans: 2
  percent: 33
---

# Project State

## Project Reference

See: .planning/PROJECT.md
See: .planning/workstreams/vps-connection/ROADMAP.md

**Workstream:** vps-connection (1 of 6 parallel M2 sessions)
**Milestone:** M2 — VPS hardening (srv982719 wired end-to-end)

## Current Position

Phase: 1 (SSH ControlMaster + invisible.toml host) — **COMPLETE**
Next: Phase 2 (invisible-server systemd unit + nginx vhost) — not started
**Status:** Phase 1 done; tree_vps walker verified end-to-end against srv982719 (real bug found and fixed in 01-02)
**Current Phase:** 2 (cursor advanced; not yet executing)
**Last Activity:** 2026-06-02
**Last Activity Description:** Completed Plan 01-02 — tree_vps verify-and-harden. Live integration surfaced a glob-quoting bug (`*/.git*` was being expanded by remote bash against /home/avi). 13-line surgical fix at _ssh_argv boundary using shlex.quote. 18 hermetic + 5 live integration tests; full Plan 01-02 acceptance green.

## Progress

**Phases Complete:** 1 / 3
**Plans Complete:** 2 / 6
**Current Plan:** Phase 2 Plan 01 (not started)

## Plan 01-01 outcomes

- `invisible.toml.example` `[vps]` block fleshed out with worked example + Decision A + 4 success criteria quoted inline (`e8af0bc`).
- `README.md` gained `### VPS connection setup` subsection (95 lines) between `## Setup` and `## Usage` (`10f61e3`).
- `bin/invisible-doctor` `check_ssh()` upgraded with ControlMaster timing probe + `_sanitize_ssh_stderr()` redaction helper (`19a5759`).
- User-side bootstrap completed: `~/.ssh/config` has `Host srv982719` block (with `Port 2222` — discovered the VPS sshd is on 2222 not 22); `~/.invisible/invisible.toml` `[vps].host = "srv982719"`; passwordless auth works.
- Phase 1 ROADMAP criteria 1, 2, 3 PASS. Criterion 4 ("warm < 200ms") is RTT-bound and not achievable — recommend rewording as "warm at least 4× faster than cold" (6× speedup IS achieved: 2.486s cold → 0.401-0.456s warm). See `01-01-SUMMARY.md` for full measurements.

## Plan 01-02 outcomes

- `tests/test_tree_vps.py` — new file, 18 hermetic tests covering every branch of `walk_all` + `_walk_remote` + 2 regression tests for the shlex-quote contract (`36fa0ec`).
- `tests/test_tree_vps_live.py`, `tests/conftest.py`, `pytest.ini` — new files, 5 live integration tests gated by `--integration` + reachability + configured-project fixtures (`88d3acb`).
- `lib/api/tree_vps.py` — 13-line surgical fix: `shlex.quote` each remote_cmd element in `_ssh_argv` so OpenSSH's space-joined argv survives the remote `$SHELL -c` re-tokenization (`fa32e9f`).
- **Step 2B applied** (orchestrator's prior was 85% Step 2A): live integration surfaced a real bug. Walking `/srv/bg-remover` returned `badge="unreachable"` because remote bash glob-expanded `*/.git*` against `/home/avi` (matched `ace-claude-toolkit/.gitignore`). After fix: 8 real children returned.
- All 5 live tests PASS against srv982719 (with INVISIBLE_HOME pointed at a synthetic invisible.toml configuring `/srv/bg-remover`). Live tests SKIP cleanly against the user's real `~/.invisible/invisible.toml` because no project has a `vps_repo_path` set — designed-in behavior.
- Public API surface preserved: function names, constants (`VPS_NOT_CONFIGURED`, `MAX_DEPTH=6`, `SSH_TIMEOUT_S=15`), 4-branch return contract unchanged.
- Total tests: 30 (7 pre-existing + 18 hermetic + 5 live).

## Decisions to date

- Decision A — Two ControlMaster sockets coexist (~/.ssh/cm-* for user shell vs `$INVISIBLE_HOME/run/ssh-cm-*` for dashboard daemon). Documented in 3 places to prevent silent consolidation.
- Doctor host regex must mirror `lib/api/tree_vps.py::_HOST_RE` byte-for-byte (T-INV01H-03 drift prevention).
- Doctor drops `-i <identity>` from argv — lets `~/.ssh/config` handle identity for the user-shell verification path.
- `_ssh_argv` must `shlex.quote` every `remote_cmd` arg before appending after `--`. The remote shell DOES re-tokenize ssh's space-joined argv — argv-form local exec does NOT protect glob args from remote glob expansion. Plan 01-02 surfaced this against srv982719's `/home/avi` CWD.

## Deferred items

1. Doctor `master=cached` threshold (`<200ms`) collides with realistic remote-VPS RTT (200-300ms). Consider switching to socket-existence check or RTT-relative threshold.
2. Deploy the workstream's `bin/invisible-doctor` to `~/.invisible/bin/invisible-doctor` (the running deployed copy is stale from 2026-05-25 — pre-ControlMaster-probe).
3. ROADMAP Phase 1 criterion 4 rewording (RTT-naive "<200ms" should become "at least 4× faster than cold" or "within 1.5-2× the network RTT").

## Sister-workstream callouts

- **Port 2222 discovery:** The VPS sshd listens on port 2222, not the default 22. The user's pre-existing `Host vps` alias was missing `Port` and was silently broken in batch mode. Phase 2 (systemd-deploy) and Phase 3 (ssh terminals) must respect this. Worth appending to `~/.claude/projects/-Users-ace/memory/vps_infra.md`.
- **Passphrase-protected `~/.ssh/id_ed25519`:** The user's existing identity at the canonical default path is passphrase-protected. Local workaround uses `~/.ssh/vps_avi` (passphrase-less). `invisible.toml.example` still documents the canonical default — fresh installs with `ssh-keygen -t ed25519 -N ""` will work.
- **Remote-shell glob-expansion gotcha (Plan 01-02):** `lib/pty_server.py` ssh variant in Phase 3 will pass user-typed commands through ssh. The same `shlex.quote` discipline applies — if Phase 3 builds an `ssh -- argv` where argv contains glob/meta-chars (e.g. user types `ls *.py`), they will be glob-expanded by the remote shell. This is expected/desired for the pty variant (user input is intentionally remote-shell-evaluated). The fix only applies to argv-form invocations like `tree_vps`'s `find`.

## Session Continuity

**Stopped At:** Phase 1 complete; ready for Phase 2 Plan 01 (systemd unit + nginx config)
**Resume File:** None

## Sister Workstreams

- tauri-windows, tools-page, relations-page, calendar-events, ci-and-onboarding (all M2)
- Conflict surface: `lib/api/tree_vps.py` (this workstream rewrites) and `lib/pty_server.py` (this workstream extends with ssh variant)
