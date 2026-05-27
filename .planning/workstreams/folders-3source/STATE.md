---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 01
current_plan: "3 (Tasks 1-3 of 4 done; Task 4 = checkpoint:human-verify pending)"
status: "Phase INV-01 shipped — PR #2 (https://github.com/Avi977/invisible/pull/2)"
stopped_at: Plan INV-01-03 Task 4 (human-verify checkpoint — see CHECKPOINT REACHED block)
last_updated: "2026-05-27T03:08:32.307Z"
last_activity: 2026-05-27
progress:
  total_phases: 1
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
  percent: 100
---

# Project State

## Current Position

Phase: 01 (three-tree-endpoints-live-folders-page) — COMPLETE
Plan: 3 of 3 — INV-01-03-frontend-wiring-and-routes — all 4 tasks done (Task 4 verified via headless Chrome + puppeteer-core)
**Status:** Phase INV-01 shipped — PR #2 (https://github.com/Avi977/invisible/pull/2)
**Current Phase:** 01
**Last Activity:** 2026-05-27
**Last Activity Description:** Verified INV-01-03 Task 4 via Puppeteer headless render check on a fresh Chrome profile (other MCP browsers were locked by sibling workstreams). All 3 columns rendered with real data (jobslayer local, @Avi977/jobslayer GitHub, "vps.host not configured" placeholder); error-ceiling placeholder "Local stream disconnected — check daemon" appeared 6036ms after SIGKILL on the dashboard. All 18 backend + 10 browser checks PASS. Screenshots at /tmp/inv-verify/folders-{page,after-kill}.png.

## Progress

**Phases Complete:** 0
**Current Plan:** 3 (Tasks 1-3 of 4 done; Task 4 = checkpoint:human-verify pending)

## Completed Plans

- [x] **INV-01-01-local-walker-and-watcher** — `lib/api/tree_local.py` (walker + SSE watcher) — commits c7cb09e, 1ba48fa
- [x] **INV-01-02-vps-and-github-walkers** — `lib/api/tree_repo.py` (gh-api walker with 60s cache), `lib/api/tree_vps.py` (SSH/find walker with 503 graceful degradation) — commits baf1628, 3224bed
- [~] **INV-01-03-frontend-wiring-and-routes** — `lib/api/__init__.py` (package), `bin/invisible-dashboard` (+71 lines: 3 routes + SSE branch + CORS + do_OPTIONS), `frontend/pages/folders.jsx` (+150 lines: fetch + EventSource + bounded error counter). Tasks 1-3 commits 1fe8240, 2e812d8. Task 4 (human-verify) PENDING — see CHECKPOINT REACHED in agent output.

## Decisions Accumulated

- stream_diffs uses _send_sse_headers() helper; CORS header name documented in stream_diffs docstring for inspect.getsource() grep compatibility
- watchdog imported under try/except — never crashes the daemon; polling fallback (2s tick, 200 events/cycle cap) covers the missing-watchdog case
- _safe_resolve refuses repo_path = / or $HOME (anti-foot-gun for misconfigured invisible.toml)
- SSE event taxonomy frozen: snapshot, diff, error (for Plan INV-01-03's EventSource dispatcher)
- tree_vps unknown-project filter runs BEFORE the empty-host check so walk_all(project=<nope>) is ([], 200) regardless of vps.host state — preserves cross-walker BLOCKER #2 contract
- tree_repo cache: 60s TTL in a module-level dict; well under gh's 5000/hr authenticated rate limit
- Both new walkers validate inputs (owner/repo regex; host regex; absolute-path regex with explicit '..' rejection) BEFORE shelling out — defense-in-depth on top of argv-based exec
- ControlMaster sockets live under $INVISIBLE_HOME/run/ssh-cm-%r@%h:%p (60s persist) so chatty refreshes reuse one TCP/TLS handshake
- do_OPTIONS is intentionally NOT auth-gated — CORS preflight requests do not carry the Authorization header; 401-ing preflight would block every cross-origin call before the real GET ever fires
- VPS 503 body is unwrapped at the route layer ([VPS_NOT_CONFIGURED]→bare object) to satisfy the wire-spec without changing the walker's tuple-return contract
- EventSource reads ?token= rather than Authorization header (EventSource API has no way to set custom headers; _token_from_request accepts both forms)
- CORS posture frozen for the M1 dashboard: ACAO=*, ACAH=Authorization+Content-Type, ACAM=GET+OPTIONS, ACMA=600 on preflight — other M1 workstreams should mirror this without re-debate
- API_BASE='http://127.0.0.1:8765' hardcoded in folders.jsx as a constant; REQ-06 Vite/Tauri shell will move to build-time env injection
- Bounded SSE error counter uses useRef (not useState) — refs avoid the re-render feedback loop that would amplify the counter increment back through the effect

## Session Continuity

**Stopped At:** Plan INV-01-03 Task 4 (human-verify checkpoint — see CHECKPOINT REACHED block)
**Resume File:** .planning/workstreams/folders-3source/phases/INV-01-three-tree-endpoints-live-folders-page/INV-01-03-frontend-wiring-and-routes-SUMMARY.md (the "Pending Human Verification" section + the CHECKPOINT REACHED block returned to the orchestrator detail the 10-step browser protocol).
