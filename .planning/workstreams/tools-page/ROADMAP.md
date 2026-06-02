# Workstream: tools-page (M2 — Tools page wired)

> Sister-workstreams: tauri-windows, vps-connection, relations-page,
> calendar-events, ci-and-onboarding. Same M1-style conflict surface as
> the original dashboard-wiring/ai-bubble/folders-3source pattern: 1
> import line in `lib/api/__init__.py`, 1 route binding in
> `bin/invisible-dashboard`, 1 mock removal in `frontend/data.jsx`.

## Phases

- [ ] **Phase 1: `/api/v1/tools` CRUD + Tools page wired**

## Phase Details

### Phase 1: /api/v1/tools CRUD + Tools page wired

**Goal**: The Tools page (n8n-style node canvas) reads + writes real
workflow definitions per project, replacing the `TOOL_WORKFLOWS` mock
in `frontend/data.jsx`.

**Depends on**: Nothing — pure parallel with the other five M2 workstreams
(tauri-windows, vps-connection, relations-page, calendar-events, ci-and-onboarding).

**Persistence model**: Tool workflows are project-scoped. Store them
on disk at `~/.invisible/workflows/<project>.json` (a tiny JSON file per
project — matches the orchestrator's checkpoint-on-disk pattern). No
database. Lock-free single-writer per project.

**Success Criteria** (what must be TRUE):
  1. `GET /api/v1/tools?project=<slug>` returns the project's workflow as
     `{nodes: [...], edges: [...], updated_at}`.
  2. `PUT /api/v1/tools?project=<slug>` accepts a body with the same
     shape, writes to disk atomically (tmpfile + rename), returns the
     new `updated_at`.
  3. `DELETE /api/v1/tools?project=<slug>` removes the workflow file (or
     returns 404 if missing).
  4. The n8n-style canvas in `frontend/pages/tools.jsx`:
     - Loads from `/api/v1/tools?project=<currentProjectId>` on project switch.
     - Saves on each node add / drag / wire change, debounced 1s.
     - Renders a tiny "saving…" / "saved 3s ago" footer indicator.
  5. Cross-project: switching projects from the tab strip loads that
     project's workflow without bleeding state.

**Plans**: 2 plans
- [x] 01-01-PLAN.md — Backend `lib/api/tools.py` (GET/PUT/DELETE) + atomic lock-free write + daemon wiring (do_PUT/do_DELETE, explicit GET route) + central CORS fix (single-source ACAO, collapsed do_OPTIONS). Wave 1. [D-01..D-12]
- [ ] 01-02-PLAN.md — Frontend `frontend/pages/tools.jsx` fetch-on-switch + 1s-debounced autosave + status footer + `TOOL_WORKFLOWS` mock removal + `.gitignore`. Wave 2, depends_on 01-01. [D-13..D-16]

## Files this workstream OWNS

- `lib/api/tools.py` (new)
- `frontend/pages/tools.jsx` (edit)

## Files this workstream EDITS LIGHTLY

- `lib/api/__init__.py` — add `from . import tools` + `__all__` entry
- `bin/invisible-dashboard` — add GET/PUT/DELETE route for `/api/v1/tools`
- `frontend/data.jsx` — remove `TOOL_WORKFLOWS` const + its `Object.assign(window, ...)`
- `.gitignore` — add `workflows/` (per-machine state)

## Files this workstream MUST NOT TOUCH

- `frontend/pages/{dashboard,focus,folders,relations,terminals,calendar,analytics}.jsx`
- `frontend/ai-chat.jsx`
- `lib/api/{projects,chat,tree_*,analytics}.py`
- `src-tauri/`, `bin/invisible-pty`, `lib/pty_server.py`

## Verify locally

```bash
PROJECT=jobslayer
# create
curl -X PUT -H 'Content-Type: application/json' \
  "http://127.0.0.1:8765/api/v1/tools?project=$PROJECT" \
  -d '{"nodes":[{"id":"a","kind":"Claude"}],"edges":[]}' | python3 -m json.tool

# read
curl -s "http://127.0.0.1:8765/api/v1/tools?project=$PROJECT" | python3 -m json.tool

# delete
curl -X DELETE "http://127.0.0.1:8765/api/v1/tools?project=$PROJECT"

# In-app: Dashboard → click Tools on any card → see n8n canvas with real data
```

## Resume

```bash
cd ~/.invisible-ws/tools-page
gsd-sdk query workstream.set tools-page --raw --cwd .
/gsd:plan-phase 1
```
