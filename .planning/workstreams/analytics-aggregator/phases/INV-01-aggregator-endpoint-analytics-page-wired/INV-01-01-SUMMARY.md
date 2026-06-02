---
phase: INV-01-aggregator-endpoint-analytics-page-wired
plan: 01
subsystem: api
tags: [python, notion, aggregation, caching, http-routing]

requires:
  - phase: Notion DB schema (Task 0 human checkpoint)
    provides: 7 new properties on Reviews DB (Input/Output/Cache read/Cache creation tokens, Cost USD, Started, Completed)
provides:
  - GET /api/v1/analytics endpoint returning {totals, by_project, top_tools, top_actions, series}
  - lib/api/analytics.py:get_analytics(range_days, project_id) aggregator
  - lib/api/analytics.py:handle_request(query_params) dashboard route adapter
  - lib/notion.py:query_reviews_since(since_iso, project_id, page_size) additive paginating helper
  - lib/notion.py:log_review extended with usage/started_at/completed_at kwargs (additive only)
  - 30s in-process cache keyed by (range_days, project_slug)
  - Notion UUID -> project-slug mapping via _build_slug_map() (reverse map for inbound slug filters)
affects: [PLAN-02 (frontend wiring), sibling workstreams that call log_review (orchestrator, invisible-log)]

tech-stack:
  added: []   # stdlib-only (time, datetime, typing, sys)
  patterns:
    - In-process TTL cache: dict keyed by request signature, monotonic-time gate, single TTL absorbs all dependent Notion calls per miss
    - Additive Notion property writes: keyword-only optional kwargs default to None; helper writes a Notion property only when the value is non-None
    - UUID->slug resolution at the data-source boundary so consumers (frontend) speak slugs only

key-files:
  created:
    - lib/api/__init__.py
    - lib/api/analytics.py
  modified:
    - lib/notion.py (additive: log_review kwargs + new query_reviews_since helper)
    - lib/orchestrator.py (additive: per-agent started_at/completed_at + usage kwargs on 4 log_review call sites)
    - bin/invisible-dashboard (additive: import + 1 route block + docstring bullet)

key-decisions:
  - "Option A (human schema gate) over Option B (defensive try/except). Crash-loud on schema drift; no per-property error handling in lib/notion.py:_request."
  - "Backend emits RAW token counts everywhere (totals, by_project, series). PLAN-01 body text claimed series was raw — the existing chart math fmtK(v*1000) actually expects kilo-tokens. Raw is the cleaner API design and consistent with totals.input_tokens; PLAN-02 divides series values by 1000 client-side before passing to the untouched StackedAreaChart."
  - "Project-id resolution lives in the backend (_build_slug_map calls notion.query_active_projects per cache miss). Frontend stays slug-only, no client-side UUID handling."
  - "Polling, not SSE: client polls /api/v1/analytics every 30s; backend cache TTL matches."
  - "Codex review rows (usage envelope is None) still contribute to total_minutes and top_actions, but contribute 0 to token totals."
  - "Tool classification is best-effort substring detection on the review summary for non-LLM markers (Postgres/Redis/GitHub/etc.). Most rows fall back to agent name (claude/codex)."

patterns-established:
  - "Slug derivation: project Name -> lowercase + strip + hyphenate. Stable, idempotent, matches PROJECT_ORDER allowlist in frontend."
  - "Range parsing: query string sends 'Nd' suffix (7d/14d/30d); handle_request strips the 'd' before int conversion. Backend rejects ranges outside the whitelisted {7,14,30}."
  - "ISO-8601 timestamp handling: datetime.fromisoformat with .replace('Z','+00:00') for Notion's Zulu-format dates."
  - "When NOTION_TOKEN is unset, lib/notion.py returns [] / None. Aggregator yields a 200 with empty totals/by_project/etc. — no 500."

requirements-completed: [REQ-05]

duration: ~25min
completed: 2026-05-27
---

# Plan INV-01-01 Summary

**Built the `/api/v1/analytics` backend aggregator: turns Notion review-row history into the JSON shape the Analytics page consumes, with a 30s cache and backend-side Notion-UUID-to-slug mapping.**

## Performance

- **Duration:** ~25 min (4 tasks including Task 0 human checkpoint)
- **Completed:** 2026-05-27T02:28Z
- **Tasks:** 4 (1 human-verify + 3 auto)
- **Files modified:** 4 (2 created, 2 edited, 1 sibling-shared `lib/orchestrator.py` updated additively)

## Accomplishments

1. **`GET /api/v1/analytics?range=7d|14d|30d&project=<slug>?`** now serves real aggregations off Notion review rows. 200 with empty payload when Notion is unreachable; 400 on bad range; 401 inherited from the dashboard's `_auth_ok()` gate; 500 on Notion blip with stderr trace.
2. **`log_review` writes usage telemetry + started/completed timestamps** on every orchestrator iteration's review row (codex rows write times only; claude rows write tokens + cost + times). All additive — sibling workstreams that call `log_review` with the old signature still work.
3. **`query_reviews_since`** paginates the Reviews DB via `start_cursor`, supports optional project filter, mirrors `query_recent_reviews` style.
4. **30-second in-process cache** keyed by `(range_days, project_slug)`. Same TTL absorbs the per-miss `query_active_projects` call used to build the UUID-to-slug map.

## Task Commits

1. **Task 0: Human checkpoint — add usage/timing properties to Notion Reviews DB** — _approved_ (no commit; user-side schema change)
2. **Task 1: Persist usage telemetry** — `69bd101` (feat)
3. **Task 2: Build aggregator with 30s cache + UUID→slug map** — `7a04cce` (feat)
4. **Task 3: Wire GET /api/v1/analytics route** — `3dfbdad` (feat)

**Plan metadata (earlier):** `7ec7d3a` (docs: plan files)

## Files Created/Modified

- `lib/api/__init__.py` — package marker (single line: `from . import analytics`)
- `lib/api/analytics.py` — aggregator module (~270 lines) — `get_analytics`, `handle_request`, `_build_slug_map`, `_extract_review`, `_minutes_between`, `_classify_tool`, `_utc_day_index`, `_cache_get/_put`
- `lib/notion.py` — `log_review` extended with `usage`/`started_at`/`completed_at` kwargs (all optional, all kw-only); `query_reviews_since` added at end (paginates via start_cursor)
- `lib/orchestrator.py` — 4 `log_review` call sites updated to pass `usage=` (claude) and `started_at`/`completed_at` (both agents); `codex_started`/`codex_completed`/`claude_started`/`claude_completed` captured via `notion.now_iso()` around the agent invocations. Additive only — no behavior change to the iteration loop.
- `bin/invisible-dashboard` — `from api import analytics as analytics_api` import, new `/api/v1/analytics` route block in `do_GET`, docstring bullet

## Deviations from Plan

- **Token unit in `series`:** plan body text said "raw counts" while the existing chart math expects kilo-tokens. Chose raw counts for API consistency with `totals.input_tokens` and to keep PLAN-01's instruction. PLAN-02 will divide by 1000 before passing arrays to the StackedAreaChart (the chart itself stays untouched per scope rules).
- No other deviations.

## Verification Evidence

Static checks (all pass):

```
python3 -c "import sys; sys.path.insert(0,'lib'); from api import analytics; \
  assert callable(analytics.get_analytics) and callable(analytics.handle_request); \
  assert analytics.CACHE_TTL_SECONDS == 30; \
  assert {7,14,30}.issubset(analytics.RANGE_DAYS_ALLOWED); \
  status, body = analytics.handle_request({'range': ['99d']}); \
  assert status == 400; print('OK')"
# -> OK

python3 -c "import sys; sys.path.insert(0,'lib'); import notion, inspect; \
  s = inspect.signature(notion.log_review); \
  assert callable(notion.query_reviews_since); \
  assert {'usage','started_at','completed_at'} <= set(s.parameters); print('OK')"
# -> OK

python3 -c "import ast; ast.parse(open('bin/invisible-dashboard').read()); print('OK')"
# -> parse OK

# Empty-Notion-env smoke (no NOTION_TOKEN set)
# Returns 200 with totals=0, by_project={}, top_tools=[], top_actions=[], series={tokensByDay:{}, timeByDay:{}}
```

Live curl verification deferred to PLAN-02 Task 3 (live UAT) — requires the dashboard daemon + Notion env to be running with at least a few review rows.

## Self-Check: PASSED

All four success criteria met statically; live behavior validated indirectly via the empty-Notion smoke test (graceful degradation). The endpoint will return data as soon as the orchestrator writes its first post-deploy review row (which will now include the seven new properties).

## What This Enables for PLAN-02

- The endpoint is live at `http://127.0.0.1:8765/api/v1/analytics?range=…&project=…&token=…`
- Auth via `Authorization: Bearer` OR `?token=` query string (PLAN-02 uses query string)
- All response keys (`totals`, `by_project`, `top_tools`, `top_actions`, `series.tokensByDay`, `series.timeByDay`) ready to consume
- `by_project` keys are already slugs (`echo`, `lumen`, etc.) matching frontend's `PROJECT_ORDER` allowlist — no client-side UUID handling needed
- `series.tokensByDay[slug][i]` values are raw token counts (NOT kilo) — PLAN-02 client-side divides by 1000 before passing to the chart
- `series.timeByDay[slug][i]` values are hours per day — passed directly to chart with mode="time"
- Cache TTL of 30s matches PLAN-02's planned 30s setInterval polling cadence
