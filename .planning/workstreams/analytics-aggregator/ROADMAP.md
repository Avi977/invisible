# Workstream: analytics-aggregator (Phase 5 of M1)

> Sister-workstreams: dashboard-wiring, ai-bubble, folders-3source,
> terminals-pty, tauri-shell. All independent.

## Phases

- [ ] **Phase 1: Aggregator endpoint + Analytics page wired**

## Phase Details

### Phase 1: Aggregator endpoint + Analytics page wired
**Goal**: The Analytics page shows real token spend, time spent, and tool usage from the orchestrator's Notion review history. Today's mock numbers in `data.jsx` are replaced by aggregations of `lib/notion.py` data.

**Depends on**: Nothing. Pure parallel.

**Requirements**: REQ-05 (see `.planning/REQUIREMENTS.md`)

**Success Criteria** (what must be TRUE):
  1. `GET /api/v1/analytics?range=7d|14d|30d&project=<id>?` returns:
     - `totals` — input tokens, output tokens, cache reads, cost USD, total minutes
     - `by_project` — same totals grouped by project id
     - `top_tools` — Claude / Codex / Postgres / GitHub / Redis usage counts and token totals
     - `top_actions` — table of (action, tool, call_count, total_tokens) sorted by token cost
     - `series` — stacked-area time-series for the chart, one layer per project
  2. Token totals come from `usage.input_tokens` + `usage.output_tokens` in the Claude `--output-format json` envelope already stored in Notion review rows.
  3. Time-spent derived from `started_at` → `completed_at` per review.
  4. `frontend/pages/analytics.jsx` fetches the endpoint and renders all existing UI sections with real data.
  5. Range + project filters update the chart and tables live (SSE or 30-second polling acceptable).

**Plans**: 2 plans
- [ ] 05-01: Backend aggregator — `lib/api/analytics.py` reads via `lib/notion.py`, caches for 30s
- [ ] 05-02: Frontend wiring — `frontend/pages/analytics.jsx` fetches `/api/v1/analytics`, plumbs filters

## Files this workstream OWNS

- `lib/api/analytics.py` (new)
- `frontend/pages/analytics.jsx` (edit)

## Files this workstream EDITS LIGHTLY

- `lib/api/__init__.py` (add `from . import analytics`)
- `bin/invisible-dashboard` (route binding)
- `lib/notion.py` (may need new query helper — keep additive, don't refactor existing functions)

## Files this workstream MUST NOT TOUCH

- Other pages, AI bubble, PTY daemon, Tauri shell.

## Verify locally

```bash
curl -s 'http://127.0.0.1:8765/api/v1/analytics?range=30d' | python3 -m json.tool | head -40
curl -s 'http://127.0.0.1:8765/api/v1/analytics?range=7d&project=echo' | python3 -m json.tool | head -40
```

## Resume in a fresh Claude session

```bash
cd /Users/ace/.invisible
gsd-sdk query workstream.set analytics-aggregator --raw --cwd .
# then in Claude:
/gsd:plan-phase 1
```
