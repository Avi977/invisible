# Roadmap: invisible — Milestone M1 (Frontend Wiring)

## Overview

The Claude Design React frontend landed today with eight pages of working
UI driven entirely by mock data. M1 turns five of those pages into real,
data-driven surfaces, and migrates the desktop shell from pywebview +
Babel-standalone to Tauri + Vite. The work is split into **6 phases that
are designed to run in parallel** — each Claude session loads one workstream
and ships it independently. The file-overlap surface across the four
HTTP-backend phases (P1, P2, P3, P5) is one `__init__.py` and a one-line
route registration — trivial to merge.

## Phases

**Phase Numbering:** Integers (1–6), no decimals expected for M1. Each
phase corresponds to a workstream of the same number under
`.planning/workstreams/`.

- [ ] **Phase 1: Dashboard wiring** — Real `/api/v1/projects` adapter; Dashboard page consumes it
- [ ] **Phase 2: AI bubble** — `/api/v1/chat` proxy to `claude -p`; AI bubble fully functional
- [ ] **Phase 3: Folders 3-source** — Local + VPS + GitHub tree endpoints; Folders page renders real trees
- [ ] **Phase 4: Terminals PTY** — New WebSocket PTY daemon; Terminals page hosts 6 real shells
- [ ] **Phase 5: Analytics aggregator** — Token + time aggregator from Notion reviews; Analytics page consumes it
- [ ] **Phase 6: Tauri shell + Vite** — Production desktop shell; replaces pywebview wrapper

## Phase Details

### Phase 1: Dashboard wiring
**Goal**: The Dashboard page renders the user's real projects (from `invisible.toml` + checkpoint store + git + Notion), not mock `DATA_SETS`.
**Depends on**: Nothing — pure parallel.
**Requirements**: REQ-01
**Success Criteria** (what must be TRUE):
  1. Opening Dashboard with no mock data toggled shows actual projects from `invisible.toml`.
  2. Each card's status / branch / lastCommit comes from git in the worktree directory.
  3. Each card's todos / note come from the orchestrator's checkpoint state.
  4. All four layouts (bento / grid / kanban / list) work identically with real data.
**Plans**: 2 plans
- [ ] 01-01: Backend adapter — `lib/api/projects.py` + register on dashboard daemon
- [ ] 01-02: Frontend wiring — `frontend/pages/dashboard.jsx` fetches from `/api/v1/projects`

### Phase 2: AI bubble
**Goal**: The AI chat bubble actually talks to Claude on every page.
**Depends on**: Nothing — pure parallel.
**Requirements**: REQ-02
**Success Criteria** (what must be TRUE):
  1. Typing in the bubble sends a request to `/api/v1/chat`.
  2. Backend invokes `claude -p --output-format json` and returns the reply.
  3. Page context (current page id + selected project) accompanies each request.
  4. Errors (auth, network, rate-limit) render readable messages in the bubble.
**Plans**: 2 plans
- [ ] 02-01: Backend proxy — `lib/api/chat.py` + route
- [ ] 02-02: Frontend wiring — `frontend/ai-chat.jsx` posts to `/api/v1/chat`

### Phase 3: Folders 3-source
**Goal**: The Folders page shows live trees for Local · VPS · GitHub.
**Depends on**: Nothing — pure parallel. (VPS column degrades gracefully if `vps.host` empty.)
**Requirements**: REQ-03
**Success Criteria** (what must be TRUE):
  1. Local column shows the actual filesystem trees of configured projects.
  2. GitHub column shows the actual `gh api` tree for each project's repo.
  3. VPS column shows an SSH-fetched tree from `srv982719` (or "not configured" gracefully).
  4. Files appearing/disappearing locally reflect in the UI within 5s.
**Plans**: 3 plans
- [ ] 03-01: Local walker + watcher — `lib/api/tree_local.py`
- [ ] 03-02: VPS + GitHub walkers — `lib/api/tree_vps.py`, `lib/api/tree_repo.py`
- [ ] 03-03: Frontend wiring — `frontend/pages/folders.jsx` fetches the three endpoints + SSE

### Phase 4: Terminals PTY
**Goal**: The Terminals page hosts 6 real PTYs (local shells + ssh to VPS) over WebSocket.
**Depends on**: Nothing — pure parallel. New daemon, new port (8091).
**Requirements**: REQ-04
**Success Criteria** (what must be TRUE):
  1. `bin/invisible-pty` daemon runs and accepts WebSocket PTY connections.
  2. Each of the 6 panes in the Terminals page connects to a real shell.
  3. Typing in a pane reaches the PTY; output streams back live.
  4. Panes can be configured to launch `ssh <host>` inside the shell.
  5. Project context header reads from the orchestrator checkpoint store.
**Plans**: 3 plans
- [ ] 04-01: PTY daemon — `bin/invisible-pty` + `lib/pty_server.py` (websockets + ptyprocess)
- [ ] 04-02: Persistent session store — PTYs survive page reload
- [ ] 04-03: Frontend wiring — `frontend/pages/terminals.jsx` connects via xterm.js

### Phase 5: Analytics aggregator
**Goal**: The Analytics page shows real token + time data from Notion review history.
**Depends on**: Nothing — pure parallel.
**Requirements**: REQ-05
**Success Criteria** (what must be TRUE):
  1. `/api/v1/analytics` returns aggregate token + time + tool-usage data.
  2. Filters (7d/14d/30d, all-projects vs one) work on real data.
  3. Top-actions table comes from review row analysis grouped by action.
  4. Chart updates without page reload (SSE or short polling).
**Plans**: 2 plans
- [ ] 05-01: Backend aggregator — `lib/api/analytics.py`
- [ ] 05-02: Frontend wiring — `frontend/pages/analytics.jsx` fetches `/api/v1/analytics`

### Phase 6: Tauri shell + Vite
**Goal**: Production desktop shell — Tauri 2.x loading a Vite-bundled React frontend.
**Depends on**: Nothing — pure parallel. Operates in new directories.
**Requirements**: REQ-06
**Success Criteria** (what must be TRUE):
  1. `cargo tauri dev` launches the app with hot reload.
  2. `cargo tauri build` produces a working `.app` (macOS) and `.msi` (Windows cross-compile).
  3. All 8 pages render identically in the Tauri shell to the current Babel-standalone build.
  4. Tray with Open / Hide / Quit (parity with current pystray).
**Plans**: 3 plans
- [ ] 06-01: Vite frontend — migrate `frontend/*.jsx` to `frontend-vite/src/`
- [ ] 06-02: Tauri shell — `src-tauri/` with Rust commands wrapping CLI surface
- [ ] 06-03: Cross-compile + package for Windows; tray + auto-update

## Progress

**Execution Order:** Phases execute **in any order** (P1–P6 are fully parallel).
Recommended: spawn 6 Claude sessions, each `cd`'d into its workstream worktree
and given the prompt:
> `/gsd:plan-phase <N>` followed by `/gsd:execute-phase <N>` once approved.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Dashboard wiring     | 0/2 | Not started | — |
| 2. AI bubble            | 0/2 | Not started | — |
| 3. Folders 3-source     | 0/3 | Not started | — |
| 4. Terminals PTY        | 0/3 | Not started | — |
| 5. Analytics aggregator | 0/2 | Not started | — |
| 6. Tauri shell + Vite   | 0/3 | Not started | — |

## File overlap map (merge-conflict prediction)

| File | P1 | P2 | P3 | P4 | P5 | P6 |
|------|:--:|:--:|:--:|:--:|:--:|:--:|
| `bin/invisible-dashboard` (route registration) | + | + | + |   | + |   |
| `lib/api/__init__.py` (new file)                | + | + | + |   | + |   |
| `lib/api/<module>.py` (new per phase)           | + | + | + |   | + |   |
| `frontend/data.jsx` (fetch helpers)             | + | + | + |   | + |   |
| `frontend/pages/<page>.jsx`                     | dashboard | — | folders | terminals | analytics | — |
| `frontend/ai-chat.jsx`                          |   | + |   |   |   |   |
| `bin/invisible-pty` (new daemon)                |   |   |   | + |   |   |
| `lib/pty_server.py` (new)                       |   |   |   | + |   |   |
| `src-tauri/` (new tree)                         |   |   |   |   |   | + |
| `frontend-vite/` (new tree)                     |   |   |   |   |   | + |

Only one true shared edit: `lib/api/__init__.py` gets one import line per
phase. The 4-way merge there is trivial.
