# Workstream: calendar-events (M2 — Calendar page wired)

> Sister-workstreams: tauri-windows, vps-connection, tools-page,
> relations-page, ci-and-onboarding. Same conflict surface as
> tools-page / relations-page.

## Phases

- [ ] **Phase 1: `/api/v1/calendar` + Calendar page wired**

## Phase 1 Details

**Goal:** Calendar page shows real events on its month + week views,
replacing the mock events in `frontend/data.jsx`.

**Event sources** (priority order):

1. **Notion Calendar DB**: if the user has a calendar database in
   Notion (likely; check `lib/notion.py` for existing project-related
   DBs), query it via the Notion API with month-range filters.
2. **iCal feeds**: if `invisible.toml` `[calendar]` section lists
   `ics_urls`, fetch and parse them stdlib-only (no `icalendar`
   package — we already have a no-dep policy from analytics-aggregator).
3. **Local `~/.invisible/events.json`**: a tiny user-editable file for
   ad-hoc events. Format: `[{title, start, end, color, project_id?}]`.

If no source is configured, return `[]` (NOT an error). The frontend
shows "no events configured" gracefully.

**Success criteria:**
1. `GET /api/v1/calendar?from=YYYY-MM-DD&to=YYYY-MM-DD` returns
   `[{id, title, start, end, color, project_id?, source}]`.
2. Each event's `start` and `end` are RFC3339 timestamps.
3. The frontend renders them on the month grid and week strip.
4. Project colours match `data.jsx`'s `DATA_SETS[..].projects[i].color`
   when `project_id` matches.
5. If multiple sources, events from all are merged (dedupe by
   `(title, start)` if needed).
6. 60s cache server-side.

**Plans:** 2 plans
- [ ] 01-01: Backend — `lib/api/calendar.py` with the 3 sources, dedupe, cache
- [ ] 01-02: Frontend — `frontend/pages/calendar.jsx` swap; preserve visual + interactions (live "now" line, click-to-expand)

## Files this workstream OWNS

- `lib/api/calendar.py` (new)
- `frontend/pages/calendar.jsx` (edit)

## Files this workstream EDITS LIGHTLY

- `lib/api/__init__.py` — add `from . import calendar`
- `bin/invisible-dashboard` — add `/api/v1/calendar` route
- `frontend/data.jsx` — remove `CALENDAR_EVENTS` mock (check existence)
- `invisible.toml.example` — add `[calendar]` block template

## Files this workstream MUST NOT TOUCH

- Other pages, ai-chat
- lib/api/{projects,chat,tree_*,analytics,tools,relations}.py
- src-tauri/, bin/invisible-pty, lib/pty_server.py
- lib/notion.py — additive only (you may add a `query_calendar_db` helper, must not modify existing functions)

## Verify locally

```bash
curl -s 'http://127.0.0.1:8765/api/v1/calendar?from=2026-06-01&to=2026-06-30' | python3 -m json.tool | head -20
# In-app: Calendar page → see month grid with real events
```

## Resume

```bash
cd ~/.invisible-ws/calendar-events
gsd-sdk query workstream.set calendar-events --raw --cwd .
/gsd:plan-phase 1
```
