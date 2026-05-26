# invisible

## What This Is

A personal multi-agent developer cockpit. Orchestrates Codex + Claude in
turn-taking loops against your projects, with a unified desktop UI that
fuses local, GitHub, and VPS state into one workspace — eight pages, six
embedded terminals, an AI chat bubble, and live analytics.

## Core Value

**One window to run every project on every machine.** If everything else
fails, the unified file/terminal/project view across local + GitHub + VPS
must work — that is the headline reason `invisible` exists.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ Codex↔Claude orchestrator loop with checkpoints, context budgeting, retries — `lib/orchestrator.py`
- ✓ Infisical-backed secrets bootstrap — `lib/infisical.py`, verified by `invisible-doctor`
- ✓ Notion sync of project rows + review log — `lib/notion.py`
- ✓ Dashboard HTTP daemon with project/review JSON API — `bin/invisible-dashboard` on 127.0.0.1:8765
- ✓ Conventional-commits + auto-generated CHANGELOG + pre-push hook
- ✓ pywebview desktop wrapper with system tray — `bin/invisible-app`
- ✓ Claude Design React frontend dropped — eight pages, glass aesthetic, served by `bin/invisible-frontend` on 127.0.0.1:8090

### Active

<!-- Current milestone: M1 — Frontend wiring -->

- [ ] **REQ-01** Dashboard page reads real project data from `/api/v1/projects` (no more `DATA_SETS` mock)
- [ ] **REQ-02** AI chat bubble proxies to `claude -p` so any page can ask Claude questions in context
- [ ] **REQ-03** Folders page shows live trees for Local · VPS · GitHub, with refresh on filesystem change
- [ ] **REQ-04** Terminals page hosts 6 real PTYs over WebSocket — local shells and ssh to VPS
- [ ] **REQ-05** Analytics page aggregates real token + time data from Notion review history
- [ ] **REQ-06** Production-grade frontend shell (Vite + Tauri) replacing Babel-standalone + pywebview

### Out of Scope

- **Tools page (n8n-style canvas)** — deferred to M2. Lower immediate value than Folders/Terminals.
- **Relations page (Obsidian graph)** — deferred to M2. Requires backend graph derivation.
- **Calendar page** — deferred to M2. Mock UI is good enough until event sources are decided.
- **Focus page deep integration** — Pomodoro + task subtask work stays client-side for M1; deeper task store waits.
- **Mobile / iOS companion** — explicit non-goal for v1.
- **Multi-user / team mode** — single-operator tool; team mode is a v2 conversation.

## Context

The repo at `~/.invisible` started life as a Python CLI scaffolding for an
agent orchestrator (28 commands, 11 libs, ~7,000 LOC). Today's session
turned it into a real GitHub repo (`Avi977/invisible`, public) with proper
Conventional-Commits flow, dropped the Claude Design frontend, and surfaced
two real bugs in the first orchestrator run (codex sandbox + auth) that are
both fixed.

The next milestone wires the eight-page React UI to actual backend data so
the app stops being a mockup. Six independent workstreams let the user run
six Claude sessions in parallel — each owns one page/feature, with minimal
file overlap.

## Constraints

- **Tech stack**: Python 3.11+ for backend, React 18 (Babel-standalone for now, Vite later) for frontend, Tauri 2.x for the desktop shell.
- **Cross-platform**: must work on macOS now and Windows by v1.0. Linux is nice-to-have.
- **Single user**: no multi-tenant concerns.
- **Public repo**: no secrets in commits. `.env`, `invisible.toml`, `logs/`, `worktrees/` all gitignored.
- **VPS connection is non-negotiable**: the file dashboard and terminal panes must reach `srv982719` reliably. SSH ControlMaster multiplex over a single connection is the planned path.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Public GitHub repo | Forces strict secret hygiene; lets the design be reviewed openly | — Pending |
| Conventional Commits + auto-CHANGELOG | Zero manual changelog work; pre-push hook prevents drift | ✓ Good |
| Frontend = React (not Svelte) | Claude Design dropped React; rewriting would waste the design | ✓ Good |
| Tauri (Rust) replacing pywebview | ~10MB binaries vs ~100MB+ Electron; native Windows; auto-update | — Pending (M1 WS-6) |
| Babel-standalone for now | Zero-build dev loop; ship the design today, migrate to Vite in WS-6 | ✓ Good |
| Frontend served on 8090, dashboard on 8765, PTY on 8091 (planned) | Decoupled daemons = simpler permissions; lets the React app fetch all three | — Pending |
| 6 parallel workstreams for M1 | User wants 6 simultaneous Claude sessions; phases are designed to minimize file overlap | — Pending |

---

*Last updated: 2026-05-26 after dropping Claude Design frontend.*
