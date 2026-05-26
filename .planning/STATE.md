# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-26)

**Core value:** One window to run every project on every machine.
**Current milestone:** M1 — Frontend wiring (6 parallel workstreams)

## Current Position

Phase: 1 of 6 (per workstream — see `.planning/workstreams/`)
Status: Ready to plan in each workstream
Last activity: 2026-05-26 — Bootstrapped .planning/, dropped Claude Design frontend

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: —
- Total execution time: —

## Accumulated Context

### Decisions

See PROJECT.md → Key Decisions.

Recent decisions affecting current work:
- 2026-05-26: Frontend stack locked as React (matches Claude Design handoff)
- 2026-05-26: 6 parallel workstreams for M1; each Claude session owns one
- 2026-05-26: Codex sandbox changed to `workspace-write`; codex auth verified by `invisible-doctor`

### Pending Todos

None at the project level. Per-workstream todos live in their `.planning/workstreams/<name>/STATE.md`.

### Blockers/Concerns

- **Infisical vault 403** — last `invisible-app` launch logged a 403 from `vault.theprofitplatform.com.au`. Frontend doesn't depend on it, but `lib/orchestrator.py` does at startup. Triage when working on WS-4 (terminals) since the PTY server may need vault-backed SSH creds.
- **VPS host empty** — `invisible.toml.example` ships with `vps.host = ""`. Needed for WS-3 (folders/VPS column) and WS-4 (terminals/ssh panes).

## Session Continuity

Last session: 2026-05-26 — Set up parallel workstreams.
Stopped at: Awaiting first plan in WS-1 (dashboard-wiring).
