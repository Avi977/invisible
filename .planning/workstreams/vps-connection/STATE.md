---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: M2 — VPS hardening
current_phase: 1
current_plan: 2
status: executing
stopped_at: N/A
last_updated: "2026-06-02T04:45:00.000Z"
last_activity: 2026-06-02
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 6
  completed_plans: 1
  percent: 17
---

# Project State

## Project Reference

See: .planning/PROJECT.md
See: .planning/workstreams/vps-connection/ROADMAP.md

**Workstream:** vps-connection (1 of 6 parallel M2 sessions)
**Milestone:** M2 — VPS hardening (srv982719 wired end-to-end)

## Current Position

Phase: 1 (SSH ControlMaster + invisible.toml host) — EXECUTING
Plan: 2 of 2 (01-01 complete, 01-02 next)
**Status:** Plan 01-01 complete; ready for Plan 01-02 (tree_vps walker live integration)
**Current Phase:** 1
**Last Activity:** 2026-06-02
**Last Activity Description:** Completed Plan 01-01 — SSH ControlMaster + invisible.toml host wiring (3 files modified, 4 commits, srv982719 alias working, warm SSH 6× faster than cold)

## Progress

**Phases Complete:** 0 / 3
**Plans Complete:** 1 / 6
**Current Plan:** 2 (within Phase 1)

## Plan 01-01 outcomes

- `invisible.toml.example` `[vps]` block fleshed out with worked example + Decision A + 4 success criteria quoted inline (`e8af0bc`).
- `README.md` gained `### VPS connection setup` subsection (95 lines) between `## Setup` and `## Usage` (`10f61e3`).
- `bin/invisible-doctor` `check_ssh()` upgraded with ControlMaster timing probe + `_sanitize_ssh_stderr()` redaction helper (`19a5759`).
- User-side bootstrap completed: `~/.ssh/config` has `Host srv982719` block (with `Port 2222` — discovered the VPS sshd is on 2222 not 22); `~/.invisible/invisible.toml` `[vps].host = "srv982719"`; passwordless auth works.
- Phase 1 ROADMAP criteria 1, 2, 3 PASS. Criterion 4 ("warm < 200ms") is RTT-bound and not achievable — recommend rewording as "warm at least 4× faster than cold" (6× speedup IS achieved: 2.486s cold → 0.401-0.456s warm). See `01-01-SUMMARY.md` for full measurements.

## Decisions to date

- Decision A — Two ControlMaster sockets coexist (~/.ssh/cm-* for user shell vs `$INVISIBLE_HOME/run/ssh-cm-*` for dashboard daemon). Documented in 3 places to prevent silent consolidation.
- Doctor host regex must mirror `lib/api/tree_vps.py::_HOST_RE` byte-for-byte (T-INV01H-03 drift prevention).
- Doctor drops `-i <identity>` from argv — lets `~/.ssh/config` handle identity for the user-shell verification path.

## Deferred items

1. Doctor `master=cached` threshold (`<200ms`) collides with realistic remote-VPS RTT (200-300ms). Consider switching to socket-existence check or RTT-relative threshold.
2. Deploy the workstream's `bin/invisible-doctor` to `~/.invisible/bin/invisible-doctor` (the running deployed copy is stale from 2026-05-25 — pre-ControlMaster-probe).
3. ROADMAP Phase 1 criterion 4 rewording (RTT-naive "<200ms" should become "at least 4× faster than cold" or "within 1.5-2× the network RTT").

## Sister-workstream callouts

- **Port 2222 discovery:** The VPS sshd listens on port 2222, not the default 22. The user's pre-existing `Host vps` alias was missing `Port` and was silently broken in batch mode. Phase 2 (systemd-deploy) and Phase 3 (ssh terminals) must respect this. Worth appending to `~/.claude/projects/-Users-ace/memory/vps_infra.md`.
- **Passphrase-protected `~/.ssh/id_ed25519`:** The user's existing identity at the canonical default path is passphrase-protected. Local workaround uses `~/.ssh/vps_avi` (passphrase-less). `invisible.toml.example` still documents the canonical default — fresh installs with `ssh-keygen -t ed25519 -N ""` will work.

## Session Continuity

**Stopped At:** Plan 01-01 complete; ready for Plan 01-02
**Resume File:** None

## Sister Workstreams

- tauri-windows, tools-page, relations-page, calendar-events, ci-and-onboarding (all M2)
- Conflict surface: `lib/api/tree_vps.py` (this workstream rewrites) and `lib/pty_server.py` (this workstream extends with ssh variant)
