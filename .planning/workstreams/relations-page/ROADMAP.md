# Workstream: relations-page (M2 — Relations page wired)

> Sister-workstreams: tauri-windows, vps-connection, tools-page,
> calendar-events, ci-and-onboarding. Same conflict surface as
> tools-page (1 import + 1 route + 1 mock removal).

## Phases

- [x] **Phase 1: `/api/v1/relations` + Relations page wired** **(SHIPPED 2026-06-02 — both plans complete)**

## Phase Details

### Phase 1: `/api/v1/relations` + Relations page wired

**Goal:** Obsidian-style graph page renders **real** nodes + edges
derived from the project's own code, not the mock graph in `data.jsx`.

**Graph derivation rules** (do them all; the React frontend already
filters by type, so emit all and let the frontend choose):

1. **`import`** edges: parse `import` / `from X import Y` statements
   across `frontend/pages/`, `lib/`, `src-tauri/src/`. Each import is a
   directed edge from the importer's module-node to the importee's
   module-node.
2. **`grep`** edges: cross-file string references — if `foo.py` mentions
   the literal string `"bar"` and `bar.md` exists in `.planning/`, draw
   an edge.
3. **`notion`** edges: project rows in Notion's projects DB linked via
   `relation` properties (`linked_projects`, etc.) — derive edges from
   the relation lists.
4. **Node types**: `module` (.py/.jsx file), `doc` (.md), `project`
   (Notion-derived), `endpoint` (HTTP route, derived from
   `bin/invisible-dashboard` route blocks).

**Success criteria:**
1. `GET /api/v1/relations?project=<slug>` returns `{nodes: [...], edges: [...]}`
   for the given project (or all projects if omitted).
2. Edge count for the `invisible` project itself is between 50 and 500
   (sanity bounds — too few means parsing broken; too many means
   noise / no filtering).
3. Each node has `{id, label, type, project?, file_path?}`.
4. Each edge has `{from, to, kind: "import"|"grep"|"notion"}`.
5. `frontend/pages/relations.jsx` swaps from mock to fetch on mount.
6. Cache the derivation per-project for 60s.

**Plans:** 2/2 plans complete
- [x] 01-01: Backend — `lib/api/relations.py` with the 3 derivers + a unified `build_graph(project)`; 60s cache **(SHIPPED 2026-06-02 — see 01-01-SUMMARY.md)**
- [x] 01-02: Frontend — `frontend/pages/relations.jsx` swap; preserve existing visual + interactions (drag, hover-focus, filter chips) **(SHIPPED 2026-06-02 — see 01-02-SUMMARY.md; includes Wave 2 deviation `c18ca74` removing duplicate ACAO header in `bin/invisible-dashboard` that was breaking browser CORS; human-verified via Chrome DevTools MCP — 5/5 checks PASS)**

## Files this workstream OWNS

- `lib/api/relations.py` (new)
- `frontend/pages/relations.jsx` (edit)

## Files this workstream EDITS LIGHTLY

- `lib/api/__init__.py` — add `from . import relations`
- `bin/invisible-dashboard` — add `/api/v1/relations` route
- `frontend/data.jsx` — remove `RELATIONS` mock (if it exists; check first)

## Files this workstream MUST NOT TOUCH

- Other pages, ai-chat, lib/api/{projects,chat,tree_*,analytics,tools}.py
- src-tauri/, bin/invisible-pty, lib/pty_server.py

## Verify locally

```bash
curl -s 'http://127.0.0.1:8765/api/v1/relations?project=invisible' | python3 -m json.tool | head -40
# In-app: Relations page → see nodes for actual files + imports
```

## Resume

```bash
cd ~/.invisible-ws/relations-page
gsd-sdk query workstream.set relations-page --raw --cwd .
/gsd:plan-phase 1
```
