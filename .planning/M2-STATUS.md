# Milestone M2 — status

_Generated 2026-06-02 at M2 bootstrap._

## Overview

Milestone M2 takes the app from "5-of-8 pages wired, 1 stranded PR, 1 unshipped workstream" to **v1.0-ready**: signed Windows + macOS builds, VPS connection live, all 8 pages real, CI + onboarding wizard in place.

## Phase A — M1.5 Recovery (in progress)

Two recovery PRs open on GitHub:

| PR | Branch | Status | What it brings |
|---|---|---|---|
| **#7** | `ws/tauri-shell` | OPEN | Re-PR after #4 missed `src-tauri/`. Lands all 10 stranded Tauri Phase 2 implementation commits (Cargo.toml, build.rs, capabilities, icons, 5 commands, tray, SSE bridge). |
| **#8** | `ws/analytics-aggregator` | OPEN | First-time push of the analytics workstream. Lands `/api/v1/analytics` + Analytics page wiring + CORS tightening. |

After both merge, run:
```bash
./scripts/cleanup-merged-worktrees.sh         # dry run first
./scripts/cleanup-merged-worktrees.sh --go    # actually clean up
```
That's **R3** of the M1.5 recovery — removes the 6 merged M1 worktrees and writes `SHIPPED.md` markers per workstream.

## Phase B — M2 Completion (6 parallel workstreams)

All 6 worktrees created off `577c048` (current main). Each has a populated `.planning/workstreams/<name>/ROADMAP.md` (committed) and `START_HERE.md` (untracked, per the gitignore convention).

| # | Workstream | Branch | Worktree | Phases | Depends on |
|---|---|---|---|---|---|
| 1 | `tauri-windows` | `ws/tauri-windows` | `~/.invisible-ws/tauri-windows` | 3 (Windows .msi → macOS .app → release.yml) | **PR #7 merged** |
| 2 | `vps-connection` | `ws/vps-connection` | `~/.invisible-ws/vps-connection` | 3 (SSH ControlMaster → systemd+nginx → in-app reach) | — |
| 3 | `tools-page` | `ws/tools-page` | `~/.invisible-ws/tools-page` | 1 (`/api/v1/tools` CRUD + Tools page) | — |
| 4 | `relations-page` | `ws/relations-page` | `~/.invisible-ws/relations-page` | 1 (graph derivation + Relations page) | — |
| 5 | `calendar-events` | `ws/calendar-events` | `~/.invisible-ws/calendar-events` | 1 (Notion+iCal+local source + Calendar page) | — |
| 6 | `ci-and-onboarding` | `ws/ci-and-onboarding` | `~/.invisible-ws/ci-and-onboarding` | 3 (CI → first-run wizard → doctor polish) | partial: Phase 2 depends on PR #7 |

5 of 6 are fully parallel from day one. WS1 (tauri-windows) is blocked on PR #7; WS6 Phase 2 (wizard) is blocked on PR #7.

## Conflict matrix (predicted merge surface)

| File | WS1 | WS2 | WS3 | WS4 | WS5 | WS6 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| `lib/api/__init__.py` | | | + | + | + | |
| `bin/invisible-dashboard` | | | + | + | + | |
| `frontend/data.jsx` | | | + | + | + | |
| `frontend/pages/*.jsx` | | | tools | relations | calendar | |
| `frontend/app.jsx` | | | | | | + |
| `src-tauri/tauri.conf.json` | + | | | | | |
| `lib/api/tree_vps.py` | | + | | | | |
| `lib/pty_server.py` | | + | | | | |
| `lib/notion.py` (additive) | | | | + | + | |
| `bin/invisible-doctor` | | + | | | | + |
| `.github/workflows/` | release.yml | | | | | ci.yml + security |
| `README.md` (additive) | + | + | | | | + |

Three files are the merge-conflict hot zones — exactly the same as M1:
- `lib/api/__init__.py` — 3-way union (one import per WS), trivial
- `bin/invisible-dashboard` — 3-way route registration, trivial
- `frontend/data.jsx` — 3-way mock removal, requires care to keep sibling mocks intact

`bin/invisible-doctor` has a 2-way overlap (WS2 adds SSH check, WS6 rewrites the file). The doctor-rewrite WS (WS6) should merge LAST so it absorbs WS2's additive SSH check.

`README.md` is touched by 3 workstreams (WS1, WS2, WS6) — but each adds a different section, so conflict is positional only.

## Lessons from M1 baked into M2

- **No PRs before implementation lands.** Each START_HERE.md explicitly says "do not open the PR until your workstream's PHASE-VERIFICATION.md exists."
- **/gsd:ship is idempotent.** If interrupted, re-running picks up where it left off (we'll wire this when the M2 ship flow is built).
- **Untracked CONTEXT.md files lost on cleanup.** Each session's CONTEXT.md is created at plan-phase time inside `.planning/workstreams/<ws>/phases/`, not at the worktree root.
- **`START_HERE.md` is now gitignored.** Lives in each worktree locally, doesn't leak across PRs.

## How to spawn the 6 M2 sessions

See the project-level `.planning/CONTEXT.md` for the per-workstream prompts, OR re-derive them from each worktree's `START_HERE.md`.

## Definition of "done" for M2

- [ ] All 8 pages read real data (Tools, Relations, Calendar shipped via WS3-5)
- [ ] VPS column on Folders + ssh variant on Terminals both work (WS2)
- [ ] Signed Windows `.msi` and macOS `.app/.dmg` available on Releases (WS1)
- [ ] CI green on every PR (WS6)
- [ ] First-run wizard onboards a fresh user (WS6)
- [ ] Tag `v1.0.0`, publish release
