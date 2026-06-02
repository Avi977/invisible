---
phase: INV-01-aggregator-endpoint-analytics-page-wired
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - lib/api/__init__.py
  - lib/api/analytics.py
  - lib/notion.py
  - bin/invisible-dashboard
autonomous: false
requirements:
  - REQ-05

must_haves:
  truths:
    - "GET /api/v1/analytics?range=30d returns 200 with JSON body containing top-level keys: totals, by_project, top_tools, top_actions, series"
    - "GET /api/v1/analytics?range=7d&project=echo filters by project (slug) and shorter window without erroring"
    - "Token totals are summed from review-row usage.input_tokens + usage.output_tokens, NOT from mock data"
    - "Codex review rows (usage is None) are counted in time + action stats but excluded from token totals"
    - "Repeated requests with the same (range, project) cache key inside a 30-second window do not re-hit Notion"
    - "Polling decision is committed: client polls /api/v1/analytics every 30 seconds (NO SSE in this phase)"
    - "by_project keys are project slugs (e.g. 'echo', 'lumen') NOT raw Notion page UUIDs — backend resolves the mapping"
    - "Before any code runs against the Reviews DB, the Notion DB schema has the seven new properties added by a human checkpoint (Input tokens, Output tokens, Cache read tokens, Cache creation tokens, Cost USD, Started, Completed)"
  artifacts:
    - path: "lib/api/__init__.py"
      provides: "package marker importing analytics submodule"
      contains: "from . import analytics"
    - path: "lib/api/analytics.py"
      provides: "get_analytics(range_days, project_id) aggregator + 30s in-process cache + UUID→slug project mapping"
      exports: ["get_analytics"]
    - path: "lib/notion.py"
      provides: "query_reviews_since(since_iso, project_id=None) helper (additive only)"
      contains: "def query_reviews_since"
    - path: "bin/invisible-dashboard"
      provides: "GET /api/v1/analytics route bound to lib.api.analytics.get_analytics"
      contains: "/api/v1/analytics"
  key_links:
    - from: "bin/invisible-dashboard"
      to: "lib/api/analytics.py:get_analytics"
      via: "import + dispatch from do_GET on path == /api/v1/analytics"
      pattern: "from api.analytics|from api import analytics|api\\.analytics\\.get_analytics"
    - from: "lib/api/analytics.py"
      to: "lib/notion.py:query_reviews_since"
      via: "module import + call inside get_analytics"
      pattern: "notion\\.query_reviews_since|from notion import"
    - from: "lib/api/analytics.py"
      to: "lib/notion.py:query_active_projects"
      via: "build {notion_uuid → slug} map once per cache miss"
      pattern: "query_active_projects"
    - from: "lib/api/analytics.py"
      to: "review row usage envelope"
      via: "sum usage.input_tokens + usage.output_tokens per review"
      pattern: "input_tokens.*output_tokens|usage"
---

<objective>
Build the backend aggregator that turns Notion review-row history into the JSON shape `frontend/pages/analytics.jsx` consumes. Create `lib/api/analytics.py` with a single public function `get_analytics(range_days, project_id)` that queries `lib/notion.py` for review rows in the window, sums tokens and time, groups by project (resolving raw Notion relation UUIDs to human-readable slugs like `echo`/`lumen`/etc.), tool, and action, builds a per-day stacked-area series, and caches the result for 30 seconds per `(range, project)` key. Register the route `GET /api/v1/analytics` in `bin/invisible-dashboard`.

Purpose: deliver REQ-05's data layer so the Analytics page can stop reading mock data from `data.jsx` and start reading real orchestrator telemetry.

Output: `lib/api/__init__.py`, `lib/api/analytics.py`, an additive `query_reviews_since` helper in `lib/notion.py`, an additive extension of `log_review` to persist usage telemetry, and one route binding in `bin/invisible-dashboard`. The endpoint returns 200 + the full envelope for `?range=7d|14d|30d&project=<slug>?`.

Polling-vs-SSE decision (committed here, mirrored in PLAN-02): **the client polls `/api/v1/analytics` every 30 seconds.** The 30s in-process cache TTL is sized to match — fresh data delivered without re-hitting Notion on every poll, no SSE broadcast infrastructure required. PLAN-02 implements the matching `setInterval`-driven refetch.

Notion DB schema gap (committed approach — **Option A: human checkpoint**, see Task 0): the Reviews DB does not currently have the seven number/date properties this plan wants to write via `log_review`. Rather than swallowing 400 errors defensively, we add a blocking human-verify checkpoint BEFORE any code change. The user adds the properties in the Notion UI. Once confirmed, the code in Task 1 can write them safely. This keeps `lib/notion.py` simple (no per-property try/except retry logic in `_request`) and prevents the rollout from silently dropping fields on a schema mismatch. Plan is therefore `autonomous: false` due to the checkpoint.

Project-id slug vs UUID (MEDIUM #5 fix): Notion review rows store the `Project` relation as a page UUID, but `frontend/data.jsx` keys projects by human slugs (`echo`, `lumen`, `drift`, `atlas`, `rune`, `ferry`). The aggregator owns the mapping — it calls `notion.query_active_projects()` once per cache miss to build a `{uuid → slug}` dict and rewrites `project_id` on each extracted review before grouping. `by_project` keys are therefore slugs, not UUIDs. The 30s cache absorbs the extra Notion round-trip per miss.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/REQUIREMENTS.md
@.planning/workstreams/analytics-aggregator/ROADMAP.md
@.planning/workstreams/analytics-aggregator/STATE.md
@START_HERE.md
@lib/notion.py
@lib/runners.py
@bin/invisible-dashboard
@frontend/pages/analytics.jsx
@frontend/data.jsx

<interfaces>
<!-- Extracted from the codebase so the executor does not need to re-explore. -->

From lib/notion.py — review-row property schema (set by log_review at line ~133, read shape used by bin/invisible-dashboard:fetch_recent_reviews at line ~148):

  Notion properties on each Reviews-DB row TODAY (before this plan):
    - "Title"     (title)            e.g. "iter 3 · claude · approve"
    - "Iteration" (number)
    - "Agent"     (select)           "codex" | "claude"
    - "Verdict"   (select)           "approve" | "changes" | "block"
    - "Summary"   (rich_text)        one-line summary
    - "Diff SHA"  (rich_text)
    - "Created"   (date)             ISO timestamp
    - "Project"   (relation)         optional — links to Projects DB row id (UUID)

  Notion properties ADDED by Task 0's human checkpoint (must exist before Task 1 runs):
    - "Input tokens"          (number)
    - "Output tokens"         (number)
    - "Cache read tokens"     (number)
    - "Cache creation tokens" (number)
    - "Cost USD"              (number)
    - "Started"               (date)
    - "Completed"             (date)

From lib/runners.py:_extract_claude_usage (line ~97):

  Returns dict | None:
    {
      "input_tokens": int,
      "output_tokens": int,
      "cache_read_input_tokens": int,
      "cache_creation_input_tokens": int,
      "cost_usd": float,
      "duration_ms": int,
    }
  Returns None for codex (which doesn't report tokens).

From bin/invisible-dashboard:DashboardHandler.do_GET (line ~266):

  Routing pattern: a sequence of `if path == "..."` / `if path.startswith("...")`
  blocks. Responses go through self._send_json(obj, status). Auth gate at line
  274 (self._auth_ok()) — your new route MUST live after the auth gate so it
  inherits bearer-token protection like all other /api/* routes.

  Auth model (from bin/invisible-dashboard lines 13-22, 219-236): bearer token
  accepted from either `Authorization: Bearer <t>` header OR `?token=<t>` query
  string. `--no-auth` is allowed only when `--host 127.0.0.1`. CORS is permissive
  (the React frontend on :8090 reaches the daemon on :8765). PLAN-02 commits
  to the `?token=` query-string form on the client; the backend already supports
  both transparently via `_token_from_request`.

  Existing /api/* routes that you mirror:
    - /api/projects           -> list_projects()
    - /api/p/<project>        -> project_detail(project)
    - /api/reviews            -> fetch_recent_reviews(n)

  Query-string parsing pattern (used by /api/reviews at line ~310):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
    n = int(q.get("n", ["20"])[0])

From frontend/pages/analytics.jsx — fields the endpoint must produce (so the
React page can consume them with minimal transformation):

  - totals.input_tokens, totals.output_tokens, totals.cache_read_tokens,
    totals.cost_usd, totals.total_minutes
  - by_project: { <slug>: { input_tokens, output_tokens, cost_usd, minutes } }
    — keys are project SLUGS (echo/lumen/...), NOT Notion UUIDs.
  - top_tools: [{ name, calls, total_tokens, color }]   (sorted desc by total_tokens)
  - top_actions: [{ name, tool, calls, tokens }]        (top 8 by tokens, sorted desc)
  - series: { tokensByDay: { <slug>: number[] },
              timeByDay:   { <slug>: number[] } }
    Each array has exactly `range_days` entries, oldest-first. Token values
    are in raw token counts (NOT thousands — the frontend already converts
    via fmtK). Time values are in hours.

  PROJECT_ORDER constant at frontend/pages/analytics.jsx line 6:
    ["echo", "lumen", "drift", "atlas", "rune", "ferry"]
  These are the project slugs the analytics page expects to find in by_project /
  series. If a Notion relation maps to a project slug outside this list, the
  aggregator still emits it; the page tolerates extra ids by ignoring any it
  doesn't have a color for. If a relation maps to a UUID the slug-map can't
  resolve (e.g. project soft-deleted in Notion), the aggregator emits the raw
  UUID as a fallback key — the frontend then drops it from PROJECT_ORDER's
  intersect filter naturally.
</interfaces>
</context>

<tasks>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 0: Human checkpoint — add usage/timing properties to the Notion Reviews DB</name>
  <what-built>
    Nothing yet. This is a pre-flight schema gate. Task 1 will extend `log_review` to write four new number properties and two new date properties to the Reviews DB. Notion rejects writes to properties that don't exist on the database with a 400 `validation_error`. We add them via the Notion UI BEFORE deploying the code so the first review row that lands post-deploy doesn't crash.
  </what-built>
  <how-to-verify>
    Open the Notion Reviews database (the one whose ID is exported as `NOTION_DB_REVIEWS`) in the Notion web UI. Add the following SEVEN properties to the database. Property names are case-sensitive and must match exactly — `lib/notion.py` will reference them verbatim.

    | Property name           | Type   |
    | ----------------------- | ------ |
    | `Input tokens`          | Number |
    | `Output tokens`         | Number |
    | `Cache read tokens`     | Number |
    | `Cache creation tokens` | Number |
    | `Cost USD`              | Number |
    | `Started`               | Date   |
    | `Completed`             | Date   |

    Steps:
    1. In Notion, open the Reviews DB (full-page view).
    2. Click `+` next to the rightmost column header SEVEN times, once per property.
    3. For each, type the exact name from the table above and select the type from the dropdown.
    4. For the Number columns, leave the number format as "Number" (no currency formatting, no commas — `Cost USD` is just a plain number, the unit is implicit in the name).
    5. Confirm all seven new column headers are visible in the database.

    No code change has happened yet — the rest of the plan runs only after you confirm here.
  </how-to-verify>
  <resume-signal>Type "User confirms the seven new properties exist on the Reviews DB" (or simply "approved") to unblock Task 1. If you skipped a property or typed a name differently, describe the discrepancy and we'll fix the plan before continuing.</resume-signal>
</task>

<task type="auto">
  <name>Task 1: Persist usage telemetry on review rows (additive log_review extension + new query helper)</name>
  <files>lib/notion.py</files>
  <read_first>
    - lib/notion.py (whole file — confirm property-builder helpers _title/_rich/_number/_date/_relation/_select and the log_review function around line 133; also re-read query_recent_reviews at line 303 to mirror its style; confirm query_active_projects exists and returns the Projects DB rows for the slug map Task 2 needs)
    - lib/runners.py lines 40-120 (AgentResult.usage envelope shape; _extract_claude_usage return contract)
    - lib/orchestrator.py (grep for `log_review(` to find the call sites you must update — additive kwargs must default to None so existing callers keep working)
  </read_first>
  <action>
    Extend `log_review` additively (DO NOT change existing parameter order or names — only add new keyword-only optional args). Add: `usage: dict | None = None`, `started_at: str | None = None`, `completed_at: str | None = None`. When `usage` is provided, write these Notion properties: `Input tokens` (number, from usage.input_tokens), `Output tokens` (number, from usage.output_tokens), `Cache read tokens` (number, from usage.cache_read_input_tokens), `Cache creation tokens` (number, from usage.cache_creation_input_tokens), `Cost USD` (number, from usage.cost_usd). When `started_at`/`completed_at` are provided, write them as `Started` (date) and `Completed` (date) properties. When any of these are None or absent, simply do not set that property — never write a Notion property with a None value. Property names MUST match the ones the user added in Task 0 byte-for-byte.

    Update every call site of `log_review` you grep up (e.g. in `lib/orchestrator.py`) to pass `usage=result.usage`, `started_at=...`, `completed_at=...` where those values exist; for codex (usage is None), only pass started_at/completed_at.

    Add a new public function `query_reviews_since(since_iso: str, project_id: str | None = None, page_size: int = 100) -> list[dict]`. Mirror `query_recent_reviews` style. Build a Notion query body with a sort on `Created` descending, page_size clamped to 1..100, and filter — if project_id given, filter `Project` relation contains project_id AND `Created` on_or_after since_iso. If no project_id, only the `Created` on_or_after filter. Loop with `start_cursor` to fetch all pages (Notion paginates at 100); stop on `has_more=False`. Return the concatenated raw `results` list (do not transform — keep parsing in the aggregator).

    DO NOT refactor any existing function. DO NOT touch `query_recent_reviews`, `query_active_projects`, `query_recent_gsd`, or any other sibling-workstream-relied function. Only additive insertions. DO NOT add try/except retry logic to `_request` — the Task 0 checkpoint guarantees the schema is correct; defensive retry would mask future schema drift.
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/analytics-aggregator && python3 -c "import sys; sys.path.insert(0,'lib'); import notion; assert callable(notion.query_reviews_since), 'query_reviews_since missing'; import inspect; sig = inspect.signature(notion.log_review); assert 'usage' in sig.parameters and 'started_at' in sig.parameters and 'completed_at' in sig.parameters, f'log_review missing new kwargs: {list(sig.parameters)}'; print('OK')"</automated>
  </verify>
  <done>
    `lib/notion.py` exports `query_reviews_since(since_iso, project_id=None, page_size=100)` that paginates through Notion. `log_review` accepts three new keyword-only optional args (`usage`, `started_at`, `completed_at`) and writes the corresponding properties only when provided. No existing function signature changed; no existing call site broken. Call sites of `log_review` in `lib/orchestrator.py` updated to pass the new fields where available.
  </done>
</task>

<task type="auto">
  <name>Task 2: Build the analytics aggregator with 30s cache + UUID→slug map (lib/api/__init__.py + lib/api/analytics.py)</name>
  <files>lib/api/__init__.py, lib/api/analytics.py</files>
  <read_first>
    - lib/notion.py (your new `query_reviews_since` from Task 1 — note property names exactly as written by `log_review`; also `query_active_projects` for the UUID→slug map)
    - lib/runners.py lines 97-115 (token envelope shape — input_tokens, output_tokens, cache_read_input_tokens, cost_usd)
    - frontend/pages/analytics.jsx (the consumer — confirm the exact field names in `totals`, `by_project`, `top_tools`, `top_actions`, `series`; see PROJECT_ORDER at line 6)
    - frontend/data.jsx lines 360-460 (mock shape — your output's `top_tools`, `top_actions`, `tokensByDay`, `timeByDay` keys must match what analytics.jsx pulls from `ANALYTICS`)
    - bin/invisible-dashboard lines 148-200 (fetch_recent_reviews — model for how to walk Notion `results[].properties` and pluck typed fields safely)
  </read_first>
  <action>
    Create `lib/api/__init__.py` containing exactly one line: `from . import analytics`. This makes `lib.api.analytics` importable from `bin/invisible-dashboard` via `sys.path.insert(0, str(HERE.parent / "lib"))` which is already done at line 56 of `bin/invisible-dashboard`.

    Create `lib/api/analytics.py` with these elements:

    1. Module-level constants: `RANGE_DAYS_ALLOWED = {7, 14, 30}`, `CACHE_TTL_SECONDS = 30`, `PROJECT_ORDER = ("echo", "lumen", "drift", "atlas", "rune", "ferry")`.

    2. A module-level cache dict `_CACHE: dict[tuple[int, str | None], tuple[float, dict]] = {}` keyed by `(range_days, project_slug_filter)`, value is `(monotonic_timestamp, payload_dict)`. Use `time.monotonic()`. Implement `_cache_get(key)` returning the payload if its monotonic timestamp is within `CACHE_TTL_SECONDS`, else None. Implement `_cache_put(key, payload)`.

    3. A private helper `_build_slug_map() -> dict[str, str]` that calls `notion.query_active_projects()` and returns `{notion_page_uuid → project_slug}`. The slug source on each project row depends on what `query_active_projects` returns — read it; it likely surfaces a `Slug` rich-text or a `Name` title from which the slug is derived. If the row has an explicit slug property, use it; otherwise lowercase the project name and strip whitespace. Cache the slug map alongside the analytics payload (same TTL, but rebuild it on cache miss — one extra Notion call per miss, absorbed by the 30s TTL).

    4. A private helper `_extract_review(page: dict, slug_map: dict[str, str]) -> dict | None` that reads one Notion page from `query_reviews_since` and returns a normalized dict with keys: `agent` (str), `project_id` (str slug, or None if the relation is empty / unmappable), `iteration` (int), `verdict` (str), `summary` (str), `created` (ISO str), `started` (ISO str or None), `completed` (ISO str or None), `input_tokens` (int), `output_tokens` (int), `cache_read_tokens` (int), `cost_usd` (float). For `project_id`: read the first relation UUID, look it up in `slug_map`, and emit the slug. If unmappable, emit the raw UUID (the frontend's `PROJECT_ORDER.filter(projectMap[pid])` drops it naturally — never crash on unmapped). Mirror the `_rt` pattern from `bin/invisible-dashboard:fetch_recent_reviews`. Return None if essential fields are missing.

    5. A private helper `_minutes_between(started: str | None, completed: str | None, created: str | None) -> float` that returns minutes between started and completed when both are present (parse with `datetime.fromisoformat`, handle trailing 'Z'), else 0.0. Created is a fallback signal but not used for duration.

    6. The public `get_analytics(range_days: int, project_id: str | None = None) -> dict` function. `project_id` here is a SLUG (caller may pass e.g. "echo"). Validate `range_days in RANGE_DAYS_ALLOWED` — raise `ValueError` otherwise. Check cache; return cached payload on hit. On miss: compute `since = datetime.now(timezone.utc) - timedelta(days=range_days)`, build the slug map via `_build_slug_map()`, and if `project_id` is given, reverse-lookup the slug → UUID so the Notion filter gets the correct UUID (the relation filter is UUID-based). Call `notion.query_reviews_since(since.isoformat(), project_id=<uuid_or_none>)`, run each result through `_extract_review` with the slug map, then build:

       - `totals`: dict with `input_tokens`, `output_tokens`, `cache_read_tokens`, `cost_usd`, `total_minutes` — sums across all reviews (codex rows where input/output are 0 are still counted in total_minutes).
       - `by_project`: dict mapping project SLUG → `{input_tokens, output_tokens, cost_usd, minutes}`. Group reviews by their `project_id` field (which is already a slug after `_extract_review`).
       - `top_tools`: list of dicts. The "tool" for each review is its `agent` (claude or codex) — also count non-LLM tools if the summary contains markers (Postgres, Redis, GitHub) by simple substring match on `summary`. Each entry: `{name, calls, total_tokens, color}`. Use colors `#f5b343` (claude/codex LLM), `#5cc8ff` (Postgres/Redis), `#b794ff` (GitHub). Sort by `total_tokens` desc.
       - `top_actions`: list of dicts. Use the review's `summary` field (truncated to 60 chars) as the action name, with `tool=agent`. Group by (summary, agent), aggregate `calls` (count) and `tokens` (sum input+output). Sort by `tokens` desc, take top 8.
       - `series`: dict with `tokensByDay` and `timeByDay`, each mapping project SLUG → list of exactly `range_days` floats, oldest-first. Bucket each review by UTC day of `started` (or `created` if `started` missing). For days with no reviews, emit 0.

       Cache the result under `(range_days, project_id)` and return it.

    7. Add a thin `handle_request(query_params: dict[str, list[str]]) -> tuple[int, dict]` helper that the dashboard route can call: parse `range` (e.g. "7d", "14d", "30d") → int, parse optional `project` → str | None, invoke `get_analytics`, return `(200, payload)`. On `ValueError` from bad range, return `(400, {"error": "invalid range, must be 7d|14d|30d"})`. On any other exception, return `(500, {"error": "internal", "message": str(e)})`. This keeps the route handler in `bin/invisible-dashboard` short.

    Do NOT use any external cache library. Do NOT add new dependencies. Use only stdlib (`time`, `datetime`, `typing`).
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/analytics-aggregator && python3 -c "import sys; sys.path.insert(0,'lib'); from api import analytics; assert callable(analytics.get_analytics), 'get_analytics missing'; assert callable(analytics.handle_request), 'handle_request missing'; assert analytics.CACHE_TTL_SECONDS == 30, 'cache TTL wrong'; assert 7 in analytics.RANGE_DAYS_ALLOWED and 14 in analytics.RANGE_DAYS_ALLOWED and 30 in analytics.RANGE_DAYS_ALLOWED, 'range set wrong'; status, body = analytics.handle_request({'range': ['99d']}); assert status == 400, f'expected 400 for bad range, got {status}'; print('OK')"</automated>
  </verify>
  <done>
    `lib/api/__init__.py` exists with `from . import analytics`. `lib/api/analytics.py` exports `get_analytics(range_days, project_id=None)`, `handle_request(query_params)`, `CACHE_TTL_SECONDS=30`, and `RANGE_DAYS_ALLOWED={7,14,30}`. Repeated calls within 30s for the same (range, project) hit the in-process cache (no Notion request, no slug-map rebuild). Bad range raises ValueError; `handle_request` converts that to (400, {...}). The returned payload has all five top-level keys: `totals`, `by_project`, `top_tools`, `top_actions`, `series`. `by_project` keys are project slugs (echo/lumen/...), NOT Notion UUIDs. The verification one-liner passes.

    Manual acceptance: `curl -s 'http://127.0.0.1:8765/api/v1/analytics?range=30d' -H "Authorization: Bearer $INVISIBLE_DASHBOARD_TOKEN" | jq '.by_project | keys'` returns lowercase slug strings (e.g. `["echo", "lumen"]`), never anything matching the UUID pattern `^[0-9a-f]{8}-[0-9a-f]{4}-`.
  </done>
</task>

<task type="auto">
  <name>Task 3: Wire GET /api/v1/analytics into bin/invisible-dashboard</name>
  <files>bin/invisible-dashboard</files>
  <read_first>
    - bin/invisible-dashboard lines 55-65 (sys.path insertion — confirms `lib/` is on path so `from api import analytics` works)
    - bin/invisible-dashboard lines 265-316 (do_GET routing block — your new route MUST live after `self._auth_ok()` gate at line 274 and before the final 404 fallback at line 315; mirror the /api/reviews pattern at line 309)
    - lib/api/analytics.py (the handle_request signature you're calling)
  </read_first>
  <action>
    Add one import at the top of the file, alongside the existing `from dashboard_render import ...` import (around line 59-61): `from api import analytics as analytics_api`. Place it AFTER the `sys.path.insert(0, str(HERE.parent / "lib"))` line at 56 so the import resolves correctly.

    Inside `DashboardHandler.do_GET`, add a new route block immediately after the `if path == "/api/reviews":` block (which ends around line 313) and BEFORE the final `self._send_text("not found\n", 404)` fallback at line 315. The block:

    - If `path == "/api/v1/analytics"`:
      - Parse the query string: `q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)`
      - Call `status, body = analytics_api.handle_request(q)`
      - Call `self._send_json(body, status)` and return.

    Update the docstring at the top of the file (lines 4-10 — the "What it serves" comment block) to add a new bullet: `  - /api/v1/analytics    aggregated token + time + tool stats from Notion review history (REQ-05)`. Keep alignment consistent with existing bullets. Do not change any other line in the file.

    DO NOT touch `fetch_recent_reviews`, `list_projects`, `project_detail`, the auth code, the HTML routes, or the `serve`/`main` functions.
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/analytics-aggregator && grep -c "from api import analytics as analytics_api" bin/invisible-dashboard | grep -q '^1$' && grep -c '/api/v1/analytics' bin/invisible-dashboard | awk '{exit ($1 >= 2) ? 0 : 1}' && python3 -c "import ast; ast.parse(open('bin/invisible-dashboard').read()); print('parse OK')"</automated>
  </verify>
  <done>
    `bin/invisible-dashboard` imports `analytics as analytics_api` from `api`, routes `GET /api/v1/analytics` through `analytics_api.handle_request`, returns JSON via `_send_json`. The route lives inside the auth-gated section (after `_auth_ok()`). Python parses the file cleanly. The docstring lists the new endpoint. No other endpoint or function modified.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| frontend → /api/v1/analytics | Untrusted query-string input (`range`, `project`) crosses from the browser into the daemon. Same trust boundary as existing /api/reviews. |
| daemon → Notion API | Outbound — Notion token in env crosses to api.notion.com. No new boundary, reuses existing notion.py auth. |
| in-process cache | No boundary — single-process dict, no IPC. |
| Notion DB schema (human-managed) | New trust assumption: the Reviews DB has the seven new properties (Task 0 enforces). If the schema drifts, `log_review` will emit a Notion 400; we accept that crash-loud failure mode rather than silently dropping fields. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-INV-01-01 | Tampering | `range` query-string param | mitigate | Whitelist via `RANGE_DAYS_ALLOWED = {7, 14, 30}` in `get_analytics`; `handle_request` returns 400 on anything else. No string concat into Notion query body — only an int. |
| T-INV-01-02 | Tampering | `project` query-string param (slug from client) | mitigate | Slug is reverse-mapped to a Notion UUID via `_build_slug_map`. Unknown slugs map to None and produce an empty filter (no results), not an error. The UUID is then passed into a structured JSON filter (`{"property": "Project", "relation": {"contains": uuid}}`). No string concatenation; Notion's API validates the relation-id format. |
| T-INV-01-03 | Information disclosure | bearer-token bypass | mitigate | New route is wired AFTER `self._auth_ok()` gate in `do_GET`, inheriting the same bearer-token check as /api/projects and /api/reviews. Token accepted from header OR `?token=` query string (per existing _token_from_request). |
| T-INV-01-04 | Denial of service | Notion rate limits / large reviews windows | mitigate | 30-second in-process cache absorbs poll storms (the planned client polls every 30s). `query_reviews_since` paginates server-side via Notion's `page_size` cap of 100. The aggregator runs in-process — no thread-pool exhaustion concern given the daemon's `ThreadingHTTPServer`. The extra `query_active_projects` call per cache miss is also absorbed by the same TTL. |
| T-INV-01-05 | Information disclosure | Notion token leakage in logs | accept | Existing notion.py path; no new logging added. We do not log the token, the query body, or raw response bodies. |
| T-INV-01-12 | Tampering | Notion DB schema drift (someone deletes a property in the UI) | accept | A removed property causes `log_review` to crash with a Notion 400 on the next write — crash-loud, not silent. Acceptable for a single-user app; the alternative (defensive try/except in `_request`) would mask schema drift indefinitely. |
| T-INV-01-SC | Tampering | npm/pip/cargo installs | mitigate | N/A — this plan adds ZERO new dependencies. Stdlib only (`time`, `datetime`, `typing`, `urllib`). No package-manager invocations. |
</threat_model>

<verification>
After all four tasks complete (including Task 0 human checkpoint), with the dashboard daemon running and `NOTION_TOKEN` + `NOTION_DB_REVIEWS` set in env:

```bash
# Endpoint shape — top-level keys
curl -s 'http://127.0.0.1:8765/api/v1/analytics?range=30d' \
  -H "Authorization: Bearer $INVISIBLE_DASHBOARD_TOKEN" \
  | python3 -m json.tool | head -40

# Filtered by project (use a real slug)
curl -s 'http://127.0.0.1:8765/api/v1/analytics?range=7d&project=echo' \
  -H "Authorization: Bearer $INVISIBLE_DASHBOARD_TOKEN" \
  | python3 -m json.tool | head -40

# by_project keys are slugs, NOT UUIDs
curl -s 'http://127.0.0.1:8765/api/v1/analytics?range=30d' \
  -H "Authorization: Bearer $INVISIBLE_DASHBOARD_TOKEN" \
  | python3 -c "import json,sys,re; keys=list(json.load(sys.stdin)['by_project'].keys()); bad=[k for k in keys if re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}', k)]; print('FAIL UUIDs leaked:', bad) if bad else print('OK slugs only:', keys)"

# Bad range -> 400
curl -s -o /dev/null -w '%{http_code}\n' \
  'http://127.0.0.1:8765/api/v1/analytics?range=99d' \
  -H "Authorization: Bearer $INVISIBLE_DASHBOARD_TOKEN"
# expect: 400

# Auth gate -> 401
curl -s -o /dev/null -w '%{http_code}\n' \
  'http://127.0.0.1:8765/api/v1/analytics?range=7d'
# expect: 401

# Cache behavior — back-to-back identical requests, second should be sub-10ms
time curl -s 'http://127.0.0.1:8765/api/v1/analytics?range=7d' \
  -H "Authorization: Bearer $INVISIBLE_DASHBOARD_TOKEN" > /dev/null
time curl -s 'http://127.0.0.1:8765/api/v1/analytics?range=7d' \
  -H "Authorization: Bearer $INVISIBLE_DASHBOARD_TOKEN" > /dev/null
```

Static checks (no daemon needed):

```bash
python3 -c "import sys; sys.path.insert(0,'lib'); from api import analytics; \
  assert hasattr(analytics, 'get_analytics') and hasattr(analytics, 'handle_request') \
     and analytics.CACHE_TTL_SECONDS == 30 \
     and {7,14,30}.issubset(analytics.RANGE_DAYS_ALLOWED); print('analytics OK')"

python3 -c "import sys; sys.path.insert(0,'lib'); import notion, inspect; \
  s = inspect.signature(notion.log_review); \
  assert callable(notion.query_reviews_since); \
  assert {'usage','started_at','completed_at'} <= set(s.parameters); \
  print('notion OK')"

python3 -c "import ast; ast.parse(open('bin/invisible-dashboard').read()); print('dashboard parse OK')"
```

Sibling-workstream non-interference check (these files MUST NOT have been touched):

```bash
git diff --name-only origin/main -- \
  frontend/pages/dashboard.jsx \
  frontend/pages/folders.jsx \
  frontend/pages/terminals.jsx \
  frontend/ai-chat.jsx \
  lib/api/projects.py \
  lib/api/chat.py \
  'lib/api/tree_*' \
  bin/invisible-pty \
  lib/pty_server.py \
  src-tauri/ \
  frontend-vite/ \
  2>/dev/null
# expect: empty output (none of these exist or none are modified)
```
</verification>

<success_criteria>
- Task 0 human checkpoint approved: the Reviews DB has all seven new properties with exact names and types.
- `GET /api/v1/analytics?range=30d` returns 200 with a JSON body whose top-level keys are exactly `totals`, `by_project`, `top_tools`, `top_actions`, `series`.
- `GET /api/v1/analytics?range=7d&project=echo` returns 200 with the same shape, scoped to that project (slug, not UUID).
- `by_project` keys are project slugs (echo / lumen / ...). Verifiable by `jq '.by_project | keys'` returning no UUID-shaped strings.
- `GET /api/v1/analytics?range=99d` returns 400.
- `GET /api/v1/analytics?range=7d` without an `Authorization` header AND without a `?token=` query string returns 401 (auth gate inherited).
- `totals.input_tokens` and `totals.output_tokens` are summed from review-row token properties (zero when older rows lack them — that's expected during rollout, not a bug).
- `series.tokensByDay[slug]` and `series.timeByDay[slug]` each contain exactly `range_days` elements, oldest-first, per project slug.
- Codex reviews (where the original `usage` was None) contribute to `total_minutes` and `top_actions` but contribute 0 to token sums.
- Two identical back-to-back requests within 30 seconds: the second does NOT hit Notion (cache absorbs it, including the `query_active_projects` call).
- The polling-vs-SSE decision is committed: **client polls every 30 seconds. No SSE endpoint is created in this phase.**
- Scope fences honored: NO changes to `frontend/pages/{dashboard,folders,terminals}.jsx`, `frontend/ai-chat.jsx`, `lib/api/projects.py`, `lib/api/chat.py`, `lib/api/tree_*`, `bin/invisible-pty`, `lib/pty_server.py`, `src-tauri/`, or `frontend-vite/`.
- `lib/notion.py` modifications are strictly additive — `query_recent_reviews`, `query_active_projects`, `query_recent_gsd`, `log_standup`, `log_health`, `log_gsd_start`, `update_gsd_outcome`, `find_or_create_client`, `find_or_create_project` signatures are unchanged.
</success_criteria>

<output>
Create `.planning/workstreams/analytics-aggregator/phases/INV-01-aggregator-endpoint-analytics-page-wired/INV-01-01-SUMMARY.md` when done.
</output>
