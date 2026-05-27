---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 01
current_plan: 3
status: executing
stopped_at: N/A
last_updated: "2026-05-27T02:11:52Z"
last_activity: 2026-05-27
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 3
  completed_plans: 2
  percent: 67
---

# Project State

## Current Position

Phase: 01 (three-tree-endpoints-live-folders-page) — EXECUTING
Plan: 3 of 3 (next: INV-01-03-frontend-wiring-and-routes)
**Status:** Executing Phase 01
**Current Phase:** 01
**Last Activity:** 2026-05-27
**Last Activity Description:** Completed INV-01-02 (VPS + GitHub tree walkers)

## Progress

**Phases Complete:** 0
**Current Plan:** 3

## Completed Plans

- [x] **INV-01-01-local-walker-and-watcher** — `lib/api/tree_local.py` (walker + SSE watcher) — commits c7cb09e, 1ba48fa
- [x] **INV-01-02-vps-and-github-walkers** — `lib/api/tree_repo.py` (gh-api walker with 60s cache), `lib/api/tree_vps.py` (SSH/find walker with 503 graceful degradation) — commits baf1628, 3224bed

## Decisions Accumulated

- stream_diffs uses _send_sse_headers() helper; CORS header name documented in stream_diffs docstring for inspect.getsource() grep compatibility
- watchdog imported under try/except — never crashes the daemon; polling fallback (2s tick, 200 events/cycle cap) covers the missing-watchdog case
- _safe_resolve refuses repo_path = / or $HOME (anti-foot-gun for misconfigured invisible.toml)
- SSE event taxonomy frozen: snapshot, diff, error (for Plan INV-01-03's EventSource dispatcher)
- tree_vps unknown-project filter runs BEFORE the empty-host check so walk_all(project=<nope>) is ([], 200) regardless of vps.host state — preserves cross-walker BLOCKER #2 contract
- tree_repo cache: 60s TTL in a module-level dict; well under gh's 5000/hr authenticated rate limit
- Both new walkers validate inputs (owner/repo regex; host regex; absolute-path regex with explicit '..' rejection) BEFORE shelling out — defense-in-depth on top of argv-based exec
- ControlMaster sockets live under $INVISIBLE_HOME/run/ssh-cm-%r@%h:%p (60s persist) so chatty refreshes reuse one TCP/TLS handshake

## Session Continuity

**Stopped At:** End of INV-01-02
**Resume File:** .planning/workstreams/folders-3source/phases/INV-01-three-tree-endpoints-live-folders-page/INV-01-03-frontend-wiring-and-routes-PLAN.md
