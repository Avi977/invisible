# Requirements: M1 — Frontend Wiring

The Claude Design React frontend dropped 2026-05-26 has eight working pages
with mock data. M1 wires the five pages with the highest user value to real
backend data, plus migrates the desktop shell to Tauri for production
readiness.

Three pages — **Tools, Relations, Calendar** — stay on mock data through
M1 and are picked up in M2.

## Requirements

### REQ-01 — Real dashboard projects

**As** the developer
**I want** the Dashboard page to show my actual projects with live status,
last commit, and current todos
**So that** I can stop pretending the mockup is real and use the app as
my project overview.

**Acceptance:**
- Dashboard cards render from `GET /api/v1/projects` (no `DATA_SETS.default.projects` reference for this page)
- Each card shows: id, name, status, branch, lastCommit, progress, todos, note, stack, nextEvent
- All four layouts (bento / grid / kanban / list) work with real data
- Tools / Terminal / Focus action buttons route correctly

**Source:** PROJECT.md Active REQ-01

### REQ-02 — AI bubble proxies to Claude

**As** the developer
**I want** the AI chat bubble on every page to actually talk to Claude
**So that** I can ask questions in-context without switching to a separate
Claude tab.

**Acceptance:**
- Bubble sends user message to `POST /api/v1/chat` with `{message, page_context, project_id?}`
- Backend invokes `claude -p --output-format json` and streams the result
- Conversation history persists for the page session (in-memory; not durable yet)
- Failure modes surface to UI: rate-limited, network-down, Claude-unauthenticated

**Source:** PROJECT.md Active REQ-02

### REQ-03 — Folders: live trees for Local · VPS · GitHub

**As** the developer
**I want** the Folders page to show real, current file trees for each of
the three sources, indistinguishably presented
**So that** I can see all of my code in one place and know where each file
lives.

**Acceptance:**
- Three columns, one per source, each fetched from `GET /api/v1/tree/{local|vps|repo}`
- Local: walks configured project paths from `invisible.toml`
- VPS: SSH-driven `find` (ControlMaster-multiplexed)
- GitHub: `gh api repos/<owner>/<repo>/git/trees/HEAD?recursive=1` per project
- Tree nodes match the existing `data.jsx` shape (`{name, type, children?, badge?}`)
- Initial load < 1s per source for projects under 1k files
- Watch endpoint streams diffs via SSE (so the tree updates when files change)

**Source:** PROJECT.md Active REQ-03

### REQ-04 — Terminals: 6 real PTYs over WebSocket

**As** the developer
**I want** the Terminals page to host 6 real shells (local + ssh-to-VPS),
not the hardcoded `TERM_PRESETS` mock output
**So that** the page replaces my tmux cockpit and becomes the default
terminal surface.

**Acceptance:**
- New daemon `bin/invisible-pty` on 127.0.0.1:8091 (WebSocket)
- Each pane connects to `ws://127.0.0.1:8091/pty/{id}` and gets a real bash shell
- Input typed in the page reaches the PTY; output streams back in realtime
- SSH variant: panes can be configured to launch `ssh <host>` inside the PTY
- Project context header (goal / activity / next) reads from the orchestrator's checkpoint store
- Sessions survive page reload (PTY stays alive backend-side)

**Source:** PROJECT.md Active REQ-04

### REQ-05 — Analytics from real Notion review history

**As** the developer
**I want** the Analytics page to show actual token spend, time spent, and
tool usage from my orchestrator runs
**So that** I can see what's costing me money and where time goes.

**Acceptance:**
- `GET /api/v1/analytics?range=7d|14d|30d&project=<id>?` returns the aggregate shape Analytics page already consumes
- Token totals come from `usage.input_tokens` + `usage.output_tokens` in Notion review rows
- Time-spent derived from `started_at` → `completed_at` per review
- Top actions table reads the Codex/Claude review summaries and groups by action
- Live chart updates without a page reload (SSE or 30-second poll, your call)

**Source:** PROJECT.md Active REQ-05

### REQ-06 — Tauri shell + Vite-bundled React

**As** the developer
**I want** the app to be a native Tauri binary loading a Vite-bundled
React frontend, not pywebview loading Babel-standalone JSX
**So that** the app starts fast, ships signed `.msi` for Windows, and
hot-reloads in dev.

**Acceptance:**
- New `src-tauri/` with Tauri 2.x project
- New `frontend-vite/` migrates existing `frontend/*.jsx` to a Vite-bundled React 18 app (same components, same styles)
- `cargo tauri dev` starts the app with hot reload
- `cargo tauri build` produces an `.app` (macOS) and `.msi` (Windows cross-compile)
- Tauri tray with Open / Hide / Quit (parity with current pystray)
- `bin/invisible-app` (pywebview) is then marked deprecated in README but not deleted
- All existing pages render in the Vite build identically to the Babel-standalone version

**Source:** PROJECT.md Active REQ-06

## Out of scope for M1

- Tools page (n8n canvas), Relations (graph), Calendar — stay on mock data
- Focus page deeper task store — Pomodoro + UI work only
- VPS hardening (mTLS, systemd, mosh) — separate post-M1 phase
- Mobile companion
- Multi-user mode

## Dependencies between requirements

REQ-01 ↔ REQ-02 ↔ REQ-03 ↔ REQ-05: all add routes to `bin/invisible-dashboard`.
Conflict surface is `lib/api/__init__.py` and one route-registration line each.
Designed for trivial merges.

REQ-04: independent daemon (new `bin/invisible-pty`, separate port). Zero
overlap with REQ-01/02/03/05.

REQ-06: entirely new directories (`src-tauri/`, `frontend-vite/`). Zero
overlap with the others. **Can run last** to consume what the others
produce, OR in parallel using the current `frontend/` and re-pointing at
the end.
