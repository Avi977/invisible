# Workstream: folders-3source (Phase 3 of M1)

> Sister-workstreams: dashboard-wiring, ai-bubble, terminals-pty,
> analytics-aggregator, tauri-shell. All independent.

## Phases

- [x] **Phase 1: Three tree endpoints + live Folders page** (completed 2026-05-27)

## Phase Details

### Phase 1: Three tree endpoints + live Folders page
**Goal**: The Folders page shows real file trees for Local · VPS · GitHub side-by-side. Today's mock data in `data.jsx` is replaced by live data from three endpoints. Filesystem changes locally appear in the UI within 5 seconds.

**Depends on**: Nothing. Pure parallel. (VPS column degrades gracefully if `vps.host` is empty in `invisible.toml`.)

**Requirements**: REQ-03 (see `.planning/REQUIREMENTS.md`)

**Success Criteria** (what must be TRUE):
  1. `GET /api/v1/tree/local` returns a recursive tree of every project path listed in `invisible.toml` under `[[projects]]`.
  2. `GET /api/v1/tree/repo` returns the GitHub tree for each project (via `gh api repos/<owner>/<repo>/git/trees/HEAD?recursive=1`).
  3. `GET /api/v1/tree/vps` returns the VPS-side tree (SSH-driven `find`, multiplexed via ControlMaster). Returns 503 with a clear message if `vps.host` empty.
  4. `frontend/pages/folders.jsx` fetches all three on mount and renders them in three columns matching the existing visual.
  5. `GET /api/v1/tree/local?watch=1` (SSE) emits diff events when files appear/disappear locally; the UI updates within 5s without a page reload.
  6. Per-project filtering works: clicking a project in the dashboard's "Dive in" → Folders should focus only that project's subtree.

**Plans**: 3 plans (planned 2026-05-26)

Wave 1 (parallel, no file overlap):
- [x] INV-01-01-local-walker-and-watcher-PLAN.md — `lib/api/tree_local.py` (walker + SSE watcher, polling fallback if watchdog absent) — done 2026-05-27, commits c7cb09e, 1ba48fa
- [x] INV-01-02-vps-and-github-walkers-PLAN.md — `lib/api/tree_vps.py` (503 graceful-degradation), `lib/api/tree_repo.py` (60s gh-api cache) — done 2026-05-27, commits baf1628, 3224bed

Wave 2:
- [x] INV-01-03-frontend-wiring-and-routes-PLAN.md — `lib/api/__init__.py` (package marker), `bin/invisible-dashboard` (3 route branches + SSE + CORS + OPTIONS preflight), `frontend/pages/folders.jsx` (fetch + EventSource + bounded error counter) — done 2026-05-27, commits 1fe8240, 2e812d8. Task 4 verified 2026-05-27 via Puppeteer headless render: 3 columns render with real data (jobslayer local + @Avi977/jobslayer GitHub + "vps.host not configured" placeholder); error-ceiling placeholder appeared 6036ms after SIGKILL.

## Progress

| Plan | Status | PLAN tasks | SUMMARY tasks | Commits |
|------|--------|-----------|---------------|---------|
| INV-01-01 | Done | 2 | 2 | c7cb09e, 1ba48fa |
| INV-01-02 | Done | 2 | 2 | baf1628, 3224bed |
| INV-01-03 | Done | 4 | 4 | 1fe8240, 2e812d8 |

## Files this workstream OWNS

- `lib/api/tree_local.py`, `lib/api/tree_vps.py`, `lib/api/tree_repo.py` (all new)
- `frontend/pages/folders.jsx` (edit)

## Files this workstream EDITS LIGHTLY

- `lib/api/__init__.py` (add three imports)
- `bin/invisible-dashboard` (route bindings)

## Files this workstream MUST NOT TOUCH

- Other pages, AI bubble, PTY daemon, Tauri shell.

## Verify locally

```bash
curl -s http://127.0.0.1:8765/api/v1/tree/local | python3 -m json.tool | head -40
curl -s http://127.0.0.1:8765/api/v1/tree/repo  | python3 -m json.tool | head -40
curl -s http://127.0.0.1:8765/api/v1/tree/vps   | python3 -m json.tool | head -40

# Watch endpoint
curl -N http://127.0.0.1:8765/api/v1/tree/local?watch=1
```

## Resume in a fresh Claude session

```bash
cd /Users/ace/.invisible
gsd-sdk query workstream.set folders-3source --raw --cwd .
# then in Claude:
/gsd:plan-phase 1
```
