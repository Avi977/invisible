---
phase: INV-01-api-v1-tools-crud-tools-page-wired
plan: 02
subsystem: frontend
tags: [react, fetch, debounce, autosave, n8n-canvas, babel-standalone, mock-removal]

# Dependency graph
requires:
  - phase: INV-01 plan 01-01 (backend)
    provides: GET/PUT/DELETE /api/v1/tools, single-source loopback CORS, OPTIONS advertising PUT/DELETE
provides:
  - Tools page wired to real per-project workflow CRUD (load on switch + 1s-debounced autosave + status footer)
  - TOOL_WORKFLOWS mock fully removed from frontend/data.jsx (const + window assignment)
  - per-machine workflows/ gitignored
affects: [end of M2 tools-page workstream — ready to ship]

# Tech tracking
tech-stack:
  added: []  # no new packages — Babel-standalone React on window, same as the rest of frontend/
  patterns:
    - "fetch-on-switch in a [projId]-keyed effect with a cancelled flag + cleanup (folders.jsx mechanism)"
    - "1s-debounced autosave PUT; target project captured at fire-time via projIdRef; cancel-on-switch in the load-effect cleanup"
    - "ToolsCanvas lifted to controlled-ish change notification: onChange(nodes,edges) via a [nodes,edges] effect with a first-render seed-skip guard"
    - "stale-response guard: a PUT/GET that resolves after the user switched away is ignored (projIdRef.current !== target)"

key-files:
  created: []
  modified:
    - frontend/pages/tools.jsx
    - frontend/data.jsx
    - .gitignore

key-decisions:
  - "ToolsCanvas keeps internal nodes/edges state but emits onChange(nodes,edges); the seed-skip guard (reference-identity vs initialNodes/initialEdges) stops the async GET from echoing back as a PUT"
  - "projId captured at fire-time in projIdRef so the PUT body and ?project= always agree even mid-render (plan-checker advisory folded in); cancel-on-switch remains the primary no-bleed guard"
  - "ProjectPicker preview shows a neutral 'open to view' label rather than N per-card fetches (D-15 discretion)"
  - "key={projId} remount on ToolsCanvas resets the per-project seed guard and canvas state"

patterns-established:
  - "Cross-origin fetch+autosave pattern for the Babel-standalone frontend pages (API_BASE + debounced PUT + status footer)"

requirements-completed: []

# Metrics
duration: 6min
completed: 2026-06-02
---

# Phase INV-01 Plan 02: Tools page wired (fetch + debounced autosave) Summary

**The n8n-style Tools canvas now loads each project's real workflow from `/api/v1/tools` on project switch and autosaves node/wire changes back via a 1s-debounced PUT with a saving…/saved footer — replacing the static `TOOL_WORKFLOWS` mock — verified end-to-end in a real browser.**

## Performance

- **Duration:** ~6 min (code) + orchestrator-driven real-browser verification
- **Completed:** 2026-06-02
- **Tasks:** 3 (2 code tasks + 1 real-browser checkpoint, verified by the orchestrator)
- **Files modified:** 3 (0 created, 3 edited)

## Accomplishments
- `frontend/pages/tools.jsx`: on project switch a `[projId]`-keyed effect fetches `GET /api/v1/tools?project=<id>` (folders.jsx pattern: headers, `cancelled` flag, loading/error) and seeds the canvas from `{nodes,edges}` (D-13).
- 1s-debounced autosave (D-14): every node add / drag-end / wire change resets a timer; on fire it PUTs `{nodes,edges}` to `projIdRef.current` (captured at fire-time); the load-effect cleanup `clearTimeout`s any pending save on project switch so a save for A can never land on B; a stale PUT/GET response is ignored if the user already switched away. Footer shows `saving…` / `saved Ns ago` / `save failed` (+ `loading…` / `load failed`).
- `frontend/data.jsx`: `TOOL_WORKFLOWS` const removed AND dropped from the `Object.assign(window, {...})` token; both `ProjectPicker` call sites and the Tools-body read fixed so nothing references the deleted mock (D-15). `grep -c TOOL_WORKFLOWS` = 0 in both files.
- `.gitignore`: `workflows/` added (D-16) — per-machine state the daemon creates under the repo root when run with `INVISIBLE_HOME=$(pwd)` in a worktree.

## Task Commits

1. **Task 1: load on switch + debounced autosave + status footer in tools.jsx** — `ca4be48` (feat)
2. **Task 2: remove TOOL_WORKFLOWS mock + fix ProjectPicker + `.gitignore workflows/`** — `0ded410` (feat)
3. **Task 3: real-browser end-to-end verification** — orchestrator-driven (no code commit; results recorded below)

## Real-browser verification (Task 3 — checkpoint, driven by orchestrator)

Driven via an isolated headless Chromium (raw CDP) against the live app — daemon (`bin/invisible-dashboard`, port 8765, `INVISIBLE_HOME=$(pwd)`) + frontend (`bin/invisible-frontend`, port 8090) — because both shared browser-MCP profiles were held by sibling sessions. fetch was instrumented in-page to capture method/url/status/CORS-error. All five plan assertions observed PASS:

| # | Assertion | Observed |
|---|-----------|----------|
| 1 | GET fires on project switch, no CORS error | `GET /api/v1/tools?project=echo` → **200**, `cors_error: null` (cross-origin :8090→:8765 completes — D-11/D-12 fix confirmed in-browser) |
| 2 | Single debounced PUT + footer transition | exactly **1** `PUT` → **200**; footer → **"saved"** (not one-PUT-per-event) |
| 3 | Reload persistence | node added via the canvas → autosaved → **persists after full reload** (1 node) — the real UI→disk→UI round-trip |
| 4 | Switch project, no state bleed | switched Echo→Lumen: Lumen shows **0 nodes** (clean per-project load), GET for Lumen fired |
| 5 | No stray PUT for prior project after switch | **0** PUTs after switch (cancel-on-switch works) |

Console errors: **none**. (A first run surfaced 404s — correctly diagnosed as a foreign daemon on :8765 lacking the tools route after a sibling `pkill` killed our daemon; re-run against our own daemon went fully green, which also proved the frontend was correct and only the backend instance was wrong.)

## Decisions Made
- **onChange notification with seed-skip** — ToolsCanvas keeps its internal state and notifies the parent via `onChange(nodes,edges)`; a first-render guard (reference-identity vs the seeded initialNodes/initialEdges) ensures the async GET that seeds the canvas does not immediately fire a redundant PUT.
- **Fire-time projId capture** — the debounced PUT reads `projIdRef.current` inside the timer callback (plan-checker advisory) so body and `?project=` always agree; cancel-on-switch is the primary guard, this closes the last race.
- **Neutral picker label** — D-15 leaves per-card counts to Claude's discretion; chose "open to view" over N grid fetches.

## Deviations from Plan
None. Both code tasks implemented exactly as planned (D-13..D-16); the fire-time-ref hardening was the plan-checker advisory already folded into the plan before execution.

## Issues Encountered
The first real-browser run returned 404/save-failed because our daemon on :8765 had been SIGTERM'd (sibling `pkill -f invisible-dashboard` in the 6-session environment) and a foreign daemon without the tools route had taken the port. Reclaimed :8765 with our own daemon and re-ran — all green. This is an environment/contention artifact, not a code defect; it actually strengthened confidence (the frontend issued correct requests both times; only the backend instance differed).

## Known Stubs
None.

## Threat Surface
Client-side only; trusts the now-hardened API (traversal/DoS/auth/CORS mitigated in 01-01). No new HIGH threats (per plan `<threat_model>`). The cross-project-save tampering vector (T-INV02-01) is mitigated on three layers (seed-skip, cancel-on-switch, fire-time projId) and observed clean in the browser (assertions 4 + 5).

## User Setup Required
None — no new packages, env vars, or accounts. To see it locally: `INVISIBLE_HOME="$(pwd)" ./bin/invisible-dashboard --no-auth --port 8765 &` and `INVISIBLE_HOME="$(pwd)" ./bin/invisible-frontend --port 8090 &`, then open `http://127.0.0.1:8090/` → Tools → pick a project.

## Next Phase Readiness
- The Tools page is fully wired and verified end-to-end. This is the last plan of the tools-page M2 workstream — ready for `/gsd:ship`.
- Conflict surface stayed minimal (1 import + route in 01-01's daemon edit; 1 mock removal here) — clean 6-way merge surface with sibling M2 workstreams.

## Self-Check: PASSED

- Modified files verified on disk: `frontend/pages/tools.jsx`, `frontend/data.jsx`, `.gitignore` — all present; `grep -c TOOL_WORKFLOWS` = 0 in both jsx/data files.
- Task commits verified in git log: `ca4be48` (feat), `0ded410` (feat) — both FOUND.
- Real-browser E2E: all 5 assertions PASS against our daemon (GET 200 no-CORS-error, single PUT 200, reload persistence, no bleed, no stray PUT); zero console errors.
- `STATE.md` / `ROADMAP.md` not modified by the executor (orchestrator owns them).

---
*Phase: INV-01-api-v1-tools-crud-tools-page-wired*
*Completed: 2026-06-02*
