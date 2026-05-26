# Workstream: dashboard-wiring (Phase 1 of M1)

> Sister-workstreams in this milestone: ai-bubble, folders-3source,
> terminals-pty, analytics-aggregator, tauri-shell. All independent —
> see `.planning/ROADMAP.md` for the file overlap map.

## Phases

- [ ] **Phase 1: Real `/api/v1/projects` end-to-end** — adapter + frontend wiring

## Phase Details

### Phase 1: Real /api/v1/projects end-to-end
**Goal**: The Dashboard page in the running frontend (127.0.0.1:8090) renders the user's actual projects — pulled from `invisible.toml`, the orchestrator's checkpoint store, the git state of each worktree, and Notion review history — replacing the `DATA_SETS.default.projects` mock.

**Depends on**: Nothing. Pure parallel with WS-2, 3, 4, 5, 6.

**Requirements**: REQ-01 (see `.planning/REQUIREMENTS.md`)

**Success Criteria** (what must be TRUE):
  1. `curl http://127.0.0.1:8765/api/v1/projects` returns a JSON array of projects shaped exactly like `DATA_SETS.default.projects` entries (`{id, code, name, color, status, branch, lastCommit, summary, progress, todos, note, stack, nextEvent}`).
  2. The Dashboard page in `frontend/pages/dashboard.jsx` fetches that endpoint on mount and renders the result; the mock `DATA_SETS` reference for this page is removed.
  3. All four layouts (bento / grid / kanban / list) render real data identically.
  4. Tools / Terminal / Focus action buttons on each card route correctly with the real project id.
  5. The "Mock data" toggle in the Tweaks panel still works for the OTHER pages (it falls back to mock for any data not yet wired).

**Plans**: 2 plans
- [ ] 01-01: Backend — `lib/api/projects.py` builds project objects from real sources; `bin/invisible-dashboard` mounts `/api/v1/projects` via `lib/api/__init__.py` registry
- [ ] 01-02: Frontend — `frontend/pages/dashboard.jsx` fetches `/api/v1/projects` on mount, adds loading + error states, keeps Tweaks fallback for other pages

## Files this workstream OWNS

- `lib/api/projects.py` (new)
- `frontend/pages/dashboard.jsx` (edit)

## Files this workstream EDITS LIGHTLY (one-line conflict surface)

- `lib/api/__init__.py` (add `from . import projects` and register)
- `bin/invisible-dashboard` (add route binding to api registry)
- `frontend/data.jsx` (add `fetchProjects()` helper)

## Files this workstream MUST NOT TOUCH

- `frontend/pages/{ai-chat,folders,terminals,analytics}.jsx` and any other page — owned by sibling workstreams.
- `frontend-vite/`, `src-tauri/` — owned by WS-6.

## Verify locally

```bash
# Backend route alive
curl -s http://127.0.0.1:8765/api/v1/projects | python3 -m json.tool | head -30

# Frontend page rendering
open http://127.0.0.1:8090/   # then click Dashboard in the sidebar
```

## Resume in a fresh Claude session

```bash
cd /Users/ace/.invisible
gsd-sdk query workstream.set dashboard-wiring --raw --cwd .
# then in Claude:
/gsd:plan-phase 1
```
