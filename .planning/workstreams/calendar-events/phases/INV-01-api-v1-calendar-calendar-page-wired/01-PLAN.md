---
phase: 01-api-v1-calendar-calendar-page-wired
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - lib/api/calendar.py
  - lib/api/__init__.py
  - bin/invisible-dashboard
  - lib/notion.py
  - invisible.toml.example
autonomous: true
requirements: []
tags: [calendar, api, ssrf, ical, notion, cache]

must_haves:
  truths:
    - "GET /api/v1/calendar?from=YYYY-MM-DD&to=YYYY-MM-DD returns HTTP 200 with a JSON array"
    - "Each event in the response has id, title, start (RFC3339), end (RFC3339), color (hex), source (notion|ics|local); project_id is present when known"
    - "When no calendar source is configured the endpoint returns [] (HTTP 200), never an error"
    - "Notion, iCal, and local-file sources are all merged into one response with (title, start) dedupe across sources"
    - "Server-side responses to identical (from, to) within 60 seconds are served from cache without re-hitting Notion / iCal"
    - "iCal fetcher rejects http://, file://, redirects to private addresses, and any URL resolving to RFC1918/loopback/link-local"
    - "events.json path stays inside ~/.invisible/ (path traversal rejected)"
    - "iCal parsing uses stdlib only (no new entry in requirements.txt)"
  artifacts:
    - path: "lib/api/calendar.py"
      provides: "calendar event aggregator + HTTP handler"
      contains: "def handle_calendar(handler"
      min_lines: 200
    - path: "lib/api/__init__.py"
      provides: "calendar route registered"
      contains: "/api/v1/calendar"
    - path: "bin/invisible-dashboard"
      provides: "registry dispatch returns after handler so calendar 200s do not race a fallback 404"
      contains: "API_V1_ROUTES[path](self)"
    - path: "lib/notion.py"
      provides: "query_calendar_db helper (additive)"
      contains: "def query_calendar_db"
    - path: "invisible.toml.example"
      provides: "[calendar] block template"
      contains: "[calendar]"
  key_links:
    - from: "bin/invisible-dashboard"
      to: "lib/api/calendar.handle_calendar"
      via: "API_V1_ROUTES dict in lib/api/__init__.py"
      pattern: "/api/v1/calendar"
    - from: "lib/api/calendar._fetch_notion_events"
      to: "lib/notion.query_calendar_db"
      via: "direct import"
      pattern: "from notion import query_calendar_db"
    - from: "lib/api/calendar._fetch_ics_events"
      to: "urllib.request.urlopen with SSRF guards"
      via: "_safe_ics_url + size cap + redirect denial"
      pattern: "urllib.request"
---

<objective>
Build `lib/api/calendar.py`, register `GET /api/v1/calendar` on the dashboard, and add the `[calendar]` config template. The handler aggregates events from up to three sources (Notion DB, iCal URLs, local `~/.invisible/events.json`), merges with dedupe, caches per `(from, to)` for 60 seconds, and degrades to `[]` when nothing is configured.

Purpose: Replace the hardcoded `EVENTS` array in `frontend/pages/calendar.jsx` (Plan 01-02) with a real backend so the Calendar page can show actual events from the user's existing tools. M1 deferred calendar to M2 explicitly because event-source choice was unresolved; this plan resolves it by supporting all three.

Output: New `lib/api/calendar.py` module (handler + 3 source loaders + dedupe + cache + SSRF guards), one-line route registration in `lib/api/__init__.py`, one-line `return` fix in `bin/invisible-dashboard`'s registry dispatch, additive `query_calendar_db` helper in `lib/notion.py`, and `[calendar]` block in `invisible.toml.example`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/workstreams/calendar-events/ROADMAP.md
@.planning/CONTEXT.md
@.planning/PROJECT.md

<interfaces>
<!-- Key contracts the executor needs. Use directly — no codebase scavenging. -->

From lib/api/__init__.py (current registry):
```
ROUTES: dict = {
    "/api/v1/projects": projects.handle_projects,
}
```
Add ONE import line + ONE ROUTES entry. The contract is documented in the module docstring at lines 1-16.

From lib/api/projects.py (source-of-truth analog for HTTP handlers):
```
def handle_projects(handler: Any) -> None:
    try:
        rows = build_projects()
        handler._send_json(rows)
    except Exception as exc:
        sys.stderr.write(f"[api/projects] internal error: {type(exc).__name__}\n")
        handler._send_json({"error": "internal error"}, status=500)
```
Mirror this exactly for `handle_calendar`: never raise, never leak paths or stack traces in the response.

From lib/api/projects.py (trust-boundary helper to mirror for events.json):
```
def _safe_path(p: str) -> Path | None:
    # Resolves p and confirms it is inside $HOME or $INVISIBLE_HOME.
    # Returns None on escape or resolution failure.
```
Use the same pattern in calendar.py for the local events.json path: only accept a path that resolves inside `config.home()` (i.e. `~/.invisible/`).

From bin/invisible-dashboard (registry dispatch at lines 361-365):
```
# /api/v1/* dispatch — registry lives in lib/api/__init__.py.
if path in API_V1_ROUTES:
    API_V1_ROUTES[path](self)
```
The block is MISSING a `return` — control falls through to the tree-route checks and ultimately to `_send_text("not found\n", 404)` at line 407, which attempts a second response. Add `return` after `API_V1_ROUTES[path](self)` as part of this plan. This is a one-line change that also benefits sister workstreams' existing routes (projects).

From lib/notion.py:
- `_token()` returns `os.environ.get("NOTION_TOKEN")`. Reuse for the calendar helper — do NOT introduce a new auth path.
- `_request(method, path, body)` is the canonical HTTP client (3-retry on 429, 20s timeout, returns None on failure). Use it from `query_calendar_db`.
- DB IDs come from `os.environ.get("NOTION_DB_<NAME>")` via `_db(name)`. For calendar, accept the DB id from `invisible.toml` `[calendar] notion_database_id` first; fall back to `NOTION_DB_CALENDAR` env var if you want symmetry with existing helpers. The toml path is REQUIRED; env var is an optional convenience.
- Existing functions (`log_review`, `find_or_create_project`, etc.) MUST NOT be modified. Only ADD `query_calendar_db`.

Frontend contract (consumed by Plan 01-02):
```
GET /api/v1/calendar?from=YYYY-MM-DD&to=YYYY-MM-DD
→ HTTP 200, [{
    "id":         "<str — stable per (source, source_uid)>",
    "title":      "<str>",
    "start":      "<RFC3339 timestamp>",
    "end":        "<RFC3339 timestamp>",
    "color":      "<hex string, e.g. #5cc8ff>",
    "project_id": "<str, optional — frontend uses to look up DATA_SETS color>",
    "source":     "notion" | "ics" | "local"
}, ...]
```
On bad/missing `from` or `to`: HTTP 400 `{"error": "bad_request", "hint": "from and to are required YYYY-MM-DD"}`.
On unrecoverable internal error: HTTP 500 `{"error": "internal error"}` (no paths, no traceback).
No source configured: HTTP 200 `[]`.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add query_calendar_db helper to lib/notion.py (additive only)</name>
  <files>lib/notion.py</files>
  <read_first>
    - lib/notion.py (full file — confirm existing function shapes, see `_request`, `_token`, `_db`, `query_active_projects` for analogs)
  </read_first>
  <behavior>
    - Given NOTION_TOKEN unset → returns []
    - Given a valid database_id and a date range → returns Notion `results[]` list of page objects
    - Given Notion HTTP error → returns [] (logs to stderr via _request, never raises)
    - Function does NOT mutate or wrap existing helpers; only adds the new symbol
  </behavior>
  <action>
    Append a new public function `query_calendar_db(database_id: str, date_from: str, date_to: str) -> list[dict]` to lib/notion.py (place it AFTER `query_recent_reviews` near line 320). It must call the existing `_request("POST", f"/databases/{database_id}/query", body)` with a filter body of the form `{"filter": {"property": "Date", "date": {"on_or_after": date_from, "on_or_before": date_to}}, "page_size": 100}`. The property name "Date" is the Notion convention but configurable later — for v1, hard-code "Date" and document in a docstring line that callers can patch this if their DB uses a different property name. Treat `database_id == ""` as "no DB configured → return []". Wrap the `_request` result with `(r or {}).get("results", [])` exactly like `query_active_projects` does. NEVER print the token. NEVER print the database_id in error paths (Notion DB ids are mildly sensitive — they leak collaboration scope). Add ONLY this function; do not modify any existing import, constant, or function in the file.
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/calendar-events &amp;&amp; python3 -c "from lib.notion import query_calendar_db, log_review, query_active_projects; assert callable(query_calendar_db); assert query_calendar_db('', '2026-06-01', '2026-06-30') == []; print('ok')"</automated>
  </verify>
  <done>query_calendar_db exists, returns [] for empty database_id, does not raise when NOTION_TOKEN unset, and pre-existing functions (log_review, query_active_projects) remain importable and unchanged.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Build lib/api/calendar.py with 3 sources, SSRF guards, dedupe, 60s cache, handle_calendar</name>
  <files>lib/api/calendar.py</files>
  <read_first>
    - lib/api/projects.py (source-of-truth analog: handle_projects signature, _safe_path pattern, defensive try/except in HTTP path)
    - lib/api/chat.py (analog for: error-sentinel dataclass pattern, _redact path-masker, _MAX_*_BYTES constants pattern, structured failure classification)
    - lib/notion.py (confirm `query_calendar_db` from Task 1 imports cleanly)
    - bin/invisible-dashboard (lines 280-310 — `_send_json` signature so handle_calendar calls it with the right shape)
  </read_first>
  <behavior>
    Module-level constants:
      - CACHE_TTL_S = 60
      - ICS_FETCH_TIMEOUT_S = 10
      - ICS_MAX_BYTES = 1_048_576  (1 MiB)
      - ALLOWED_ICS_SCHEMES = ("https",)  (NOTE: https only, not http)
      - PRIVATE_IP_NETS = list of ipaddress networks: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8, 169.254.0.0/16, ::1/128, fc00::/7, fe80::/10

    Source loaders (each returns list[dict] in the canonical event shape, never raises):
      - _fetch_notion_events(db_id, date_from, date_to) → list[event]
      - _fetch_ics_events(urls: list[str], date_from, date_to) → list[event]
      - _fetch_local_events(date_from, date_to) → list[event]

    Date filtering: each loader filters events whose start falls in [date_from 00:00, date_to 23:59:59] UTC.

    Merge + dedupe:
      - merge_events(notion, ics, local) → deduped list
      - Dedupe key: (title.strip().lower(), start)
      - Source priority on collision: notion > ics > local (notion wins, ics second, local last)
      - Result list is sorted by start timestamp ascending

    Cache:
      - _CACHE: dict[(date_from, date_to)] = (timestamp_epoch, list[event])
      - _CACHE_LOCK: threading.Lock — single-flight: while one thread is computing, others wait on the lock and then read the freshly-populated entry instead of re-fetching
      - get_calendar(date_from, date_to) returns cached result if (now - timestamp_epoch) < CACHE_TTL_S, else recomputes under the lock
      - Cache is GLOBAL (module-level) — survives across requests, dies on daemon restart

    SSRF guards in _safe_ics_url(url) → str | None:
      - Parse with urllib.parse.urlparse
      - REJECT if scheme not in ALLOWED_ICS_SCHEMES (i.e. only https; reject http, file, ftp, javascript, data)
      - REJECT if hostname is empty
      - REJECT if hostname or any A/AAAA resolution lands in PRIVATE_IP_NETS — use socket.getaddrinfo with AF_UNSPEC and check EVERY returned address (an attacker can register a public DNS name that resolves to 127.0.0.1)
      - On any resolution failure → return None (treat as unsafe)

    iCal fetcher specifics:
      - urllib.request.Request with method="GET" and a custom OpenerDirector that does NOT follow redirects (use a HTTPRedirectHandler subclass that raises HTTPError on 3xx); the 3xx response body is the only resource we accept, no follow
      - timeout=ICS_FETCH_TIMEOUT_S
      - Read at most ICS_MAX_BYTES bytes; if Content-Length > cap or stream exceeds cap mid-read, abort and return []
      - If the streamed body read exceeds `ICS_MAX_BYTES` mid-response (server lied about Content-Length or omitted it), abort that connection and treat the URL as failed — return `[]` for that URL but continue processing other configured URLs.
      - On any exception (network, timeout, redirect, size cap): return [] for THAT url; continue with remaining urls

    iCal parser _parse_ical(text) → list[event]:
      - Stdlib only — no `icalendar` package, no `pip install`
      - State-machine over lines: BEGIN:VEVENT / END:VEVENT delimit one event
      - Extract DTSTART, DTEND, SUMMARY, UID
      - Handle line-folding (RFC 5545: a line that starts with a SPACE or TAB is a continuation of the previous logical line)
      - Handle DTSTART with both `DTSTART:20260601T140000Z` (UTC) and `DTSTART;TZID=America/New_York:20260601T100000` (local) — for v1 the TZID branch may emit the timestamp without TZ shift if zoneinfo lookup fails (document this as a known limitation; do NOT skip the event)
      - RRULE expansion is OUT OF SCOPE for v1; emit a TODO comment near the parser noting "recurrence: single occurrence only; RRULE deferred to a later iteration"
      - Emit RFC3339 ISO strings for start/end via datetime.isoformat()

    Local events.json loader:
      - Path = config.home() / "events.json"  (i.e. ~/.invisible/events.json)
      - Use Path.resolve() and confirm it is_relative_to(config.home().resolve()) — defense against symlink trickery
      - Missing file → return []
      - JSON parse error → return [] (log to stderr WITHOUT the path)
      - Expected schema: list of objects with title (str), start (RFC3339), end (RFC3339), color (str, optional), project_id (str, optional)
      - Skip entries failing schema validation; do NOT raise

    Color resolution:
      - Notion source: color comes from a Notion select property "Color" if present, else fall back to "#8aa9ff"
      - iCal source: iCal has no canonical color; default "#8aa9ff"
      - Local source: use the event's `color` field if present and matches r"^#[0-9a-fA-F]{6}$"; else "#8aa9ff"
      - The frontend (Plan 01-02) overrides color when project_id matches a DATA_SETS project, so the backend default of "#8aa9ff" is correct as a safe fallback

    handle_calendar(handler) entry point:
      - Parse from / to from `handler.path` query string using urllib.parse.urlparse + parse_qs
      - Validate YYYY-MM-DD format with datetime.datetime.strptime; on failure → handler._send_json({"error":"bad_request","hint":"from and to are required YYYY-MM-DD"}, status=400) and return
      - Wrap get_calendar() in try/except; on Exception log `[api/calendar] internal error: {type(exc).__name__}` to stderr (NEVER the message, NEVER the traceback, NEVER the URL) and send handler._send_json({"error":"internal error"}, status=500)
      - On success → handler._send_json(events, status=200)
  </behavior>
  <action>
    Create lib/api/calendar.py with the structure described in &lt;behavior&gt;. Follow the module-docstring style of lib/api/projects.py and lib/api/chat.py (security-notes section at the top documenting SSRF posture, cache stampede mitigation, info-disclosure stance). Imports: from __future__ import annotations; json, os, re, socket, sys, threading, time, urllib.parse, urllib.request, ipaddress, datetime, pathlib.Path, typing.Any; import config; import notion (the lib/notion module). Use config.home() for the events.json directory (matches projects.py and the established pattern). Use try/except around EVERY external call (socket.getaddrinfo, urllib.request.urlopen, json.loads, datetime.strptime). NEVER print absolute paths or URLs to stderr — use type name only (e.g. f"[api/calendar] ics fetch failed: {type(exc).__name__}"). For the single-flight cache: take _CACHE_LOCK, check cache, if hit return cached; if miss, compute, store, release. The lock is held for the duration of the network calls — that is acceptable for v1 since the dashboard is a personal cockpit (low concurrency); the alternative (per-key locks) is overkill for the threat model. Add a module-level comment near the cache noting this tradeoff. DO NOT add any package to requirements.txt. DO NOT import `icalendar`, `dateutil`, or any non-stdlib parser.
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/calendar-events &amp;&amp; python3 -c "
import sys; sys.path.insert(0, 'lib')
from api import calendar
# SSRF guard
assert calendar._safe_ics_url('http://example.com/cal.ics') is None, 'http rejected'
assert calendar._safe_ics_url('file:///etc/passwd') is None, 'file rejected'
assert calendar._safe_ics_url('https://127.0.0.1/cal.ics') is None, 'loopback rejected'
assert calendar._safe_ics_url('https://192.168.1.1/cal.ics') is None, 'rfc1918 rejected'
# iCal parser
SAMPLE = 'BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:abc123\nDTSTART:20260601T140000Z\nDTEND:20260601T150000Z\nSUMMARY:Test event\nEND:VEVENT\nEND:VCALENDAR\n'
events = calendar._parse_ical(SAMPLE)
assert len(events) == 1, f'expected 1 event, got {len(events)}'
assert events[0]['title'] == 'Test event', events[0]
assert events[0]['source'] == 'ics'
# Dedupe
notion_ev = [{'id': 'n1', 'title': 'Standup', 'start': '2026-06-01T09:30:00Z', 'end': '2026-06-01T10:00:00Z', 'color': '#fff', 'source': 'notion'}]
ics_ev = [{'id': 'i1', 'title': 'standup', 'start': '2026-06-01T09:30:00Z', 'end': '2026-06-01T10:00:00Z', 'color': '#000', 'source': 'ics'}]
merged = calendar.merge_events(notion_ev, ics_ev, [])
assert len(merged) == 1, f'dedupe failed: {merged}'
assert merged[0]['source'] == 'notion', f'notion priority lost: {merged[0]}'
# No config → empty
assert calendar.get_calendar('2026-06-01', '2026-06-30') == [], 'expected [] for unconfigured'
print('ok')
"</automated>
  </verify>
  <done>lib/api/calendar.py exists and imports cleanly; _safe_ics_url rejects http, file, loopback, RFC1918; _parse_ical parses a minimal VEVENT; merge_events dedupes by (title, start) with notion priority; get_calendar returns [] when no source configured.</done>
</task>

<task type="auto">
  <name>Task 3: Register calendar route and fix registry dispatch fall-through</name>
  <files>lib/api/__init__.py, bin/invisible-dashboard</files>
  <read_first>
    - lib/api/__init__.py (full file — currently 40 lines; confirm exact location of ROUTES dict and the sister-workstream comment)
    - bin/invisible-dashboard (lines 311-407 — the do_GET method, especially the registry dispatch at 361-365 and the unconditional 404 at 407)
  </read_first>
  <action>
    Two edits, each one line:

    (a) lib/api/__init__.py: Add `from . import calendar` immediately after the existing `from . import projects` import (preserve alphabetical-ish order; calendar comes before chat by alphabetical sort if you re-order, but the simpler diff is to add it right after `projects`). Then add `"/api/v1/calendar": calendar.handle_calendar,` to the ROUTES dict immediately after the `"/api/v1/projects": projects.handle_projects,` line. Update the module __all__ to include `"calendar"`.

    (b) bin/invisible-dashboard: At line 365 (immediately after `API_V1_ROUTES[path](self)`), add a `return` statement so the handler does not fall through to subsequent tree-route checks and ultimately the unconditional `_send_text("not found\n", 404)` at line 407 (which currently sends a second HTTP response after the handler already wrote one — latent bug fixed as part of this plan). The indentation of `return` must match the inside of the `if path in API_V1_ROUTES:` block (8 spaces from line start inside do_GET, i.e. one indent past the `if`).

    NEVER edit any other line in either file. DO NOT touch the do_OPTIONS handlers, tree-route handlers, do_POST, or any of the existing routing. DO NOT touch sister workstreams' imports (chat, tree_*).
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/calendar-events &amp;&amp; python3 -c "
import sys; sys.path.insert(0, 'lib')
from api import ROUTES, calendar
assert '/api/v1/calendar' in ROUTES, f'route not registered: {list(ROUTES.keys())}'
assert ROUTES['/api/v1/calendar'] is calendar.handle_calendar
print('ok')
" &amp;&amp; grep -n 'API_V1_ROUTES\[path\](self)' bin/invisible-dashboard | head -1 &amp;&amp; awk '/API_V1_ROUTES\[path\]\(self\)/{f=1; print NR": "$0; next} f &amp;&amp; /^[[:space:]]+return$/{print NR": "$0; f=0}' bin/invisible-dashboard | head -2</automated>
  </verify>
  <done>`/api/v1/calendar` is in ROUTES, maps to `calendar.handle_calendar`, and the line immediately after `API_V1_ROUTES[path](self)` in bin/invisible-dashboard is `return`.</done>
</task>

<task type="auto">
  <name>Task 4: Add [calendar] template block to invisible.toml.example</name>
  <files>invisible.toml.example</files>
  <read_first>
    - invisible.toml.example (full file — see how [vps], [orchestrator], [[clients]], [[projects]], [[terminals]] are commented and structured)
  </read_first>
  <action>
    Append a new section to invisible.toml.example AFTER the existing `[[terminals]]` blocks. The section uses TOML table syntax (not array-of-tables):

    Block content (literal TOML, including documentation comments):
      - A `# ── Calendar ──` separator banner matching the visual style of `# ── Clients ──` / `# ── Projects ──` / `# ── Terminals ──` in the existing file.
      - 4-6 lines of comment describing what the section configures: "Event sources for the Calendar page. All three are optional; if none are set, /api/v1/calendar returns []. iCal URLs MUST use https:// and resolve to public addresses (RFC1918 / loopback are rejected by the SSRF guard)."
      - A `[calendar]` table header.
      - `notion_database_id = ""` with a comment explaining it is the 32-char Notion DB id of a calendar database; leave empty to disable the Notion source. Also note that the DB must have a "Date" property and optionally a "Color" select property.
      - `ics_urls = []` with a comment: example `["https://calendar.google.com/calendar/ical/YOUR_ID/public/basic.ics"]`.
      - A trailing comment noting that ~/.invisible/events.json is a third source (auto-discovered when present) and does not need to be configured in this file.

    Use the existing file's commenting style: `#` at column 0 followed by a single space, doc lines wrap at ~78 chars.
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/calendar-events &amp;&amp; grep -q '^\[calendar\]' invisible.toml.example &amp;&amp; grep -q '^notion_database_id' invisible.toml.example &amp;&amp; grep -q '^ics_urls' invisible.toml.example &amp;&amp; python3 -c "
try:
    import tomllib
except ImportError:
    import tomli as tomllib
with open('invisible.toml.example', 'rb') as f:
    cfg = tomllib.load(f)
assert 'calendar' in cfg, f'calendar table missing: {list(cfg.keys())}'
assert cfg['calendar'].get('notion_database_id') == '', cfg['calendar']
assert cfg['calendar'].get('ics_urls') == [], cfg['calendar']
print('ok')
"</automated>
  </verify>
  <done>invisible.toml.example parses as valid TOML, contains a [calendar] table with notion_database_id (empty string) and ics_urls (empty list), with explanatory comments matching the existing file's style.</done>
</task>

<task type="auto">
  <name>Task 5: End-to-end smoke — start dashboard daemon, curl the endpoint, assert empty-200</name>
  <files></files>
  <read_first>
    - bin/invisible-dashboard (lines 495-547 — the serve()/main() functions, so the executor knows how to start the daemon for verification)
  </read_first>
  <action>
    Run a short smoke test that exercises the full path: start invisible-dashboard with --no-auth on 127.0.0.1:8765 in the background, wait briefly for the listener to bind, curl GET /api/v1/calendar with valid from/to params, then with invalid params, then kill the daemon. Use a project that has no calendar source configured (i.e. the current repo's invisible.toml or no toml at all) — the expected response is an HTTP 200 with body `[]`. The bad-params case should be HTTP 400 with `{"error":"bad_request",...}`. Do NOT add a calendar source for this smoke; the goal is to prove the route is wired and the no-source path returns the empty-array contract from Success Criterion #7. Capture exit code, kill the background daemon, and fail loudly if either request did not return the expected status. Use only stdlib (curl + python -c for JSON assertions) — do NOT add pytest fixtures to the repo for this single check.
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/calendar-events &amp;&amp; (./bin/invisible-dashboard --no-auth --port 18765 &amp; echo $! &gt; /tmp/cal-dash.pid) &amp;&amp; sleep 2 &amp;&amp; (STATUS_OK=$(curl -s -o /tmp/cal-ok.json -w '%{http_code}' 'http://127.0.0.1:18765/api/v1/calendar?from=2026-06-01&amp;to=2026-06-30'); STATUS_BAD=$(curl -s -o /tmp/cal-bad.json -w '%{http_code}' 'http://127.0.0.1:18765/api/v1/calendar?from=notadate&amp;to=2026-06-30'); kill $(cat /tmp/cal-dash.pid) 2&gt;/dev/null; python3 -c "
import json, sys
ok_status = '$STATUS_OK'
bad_status = '$STATUS_BAD'
assert ok_status == '200', f'expected 200, got {ok_status}'
assert bad_status == '400', f'expected 400, got {bad_status}'
ok_body = json.load(open('/tmp/cal-ok.json'))
assert ok_body == [], f'expected [], got {ok_body!r}'
bad_body = json.load(open('/tmp/cal-bad.json'))
assert bad_body.get('error') == 'bad_request', bad_body
print('ok')
")</automated>
  </verify>
  <done>GET /api/v1/calendar with valid YYYY-MM-DD params returns HTTP 200 with an empty JSON array (no source configured); invalid params return HTTP 400 with {"error":"bad_request",...}; the daemon stays alive across the two requests (no second-response crash from the dispatch-fall-through bug fixed in Task 3).</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser → /api/v1/calendar | Untrusted query string (`from`, `to`) crosses into the handler |
| daemon → iCal upstream | User-configured URL crosses out to the internet; response body crosses back in |
| daemon → Notion API | Notion token (env / Infisical) used to fetch DB rows; response body crosses back in |
| daemon → ~/.invisible/events.json | Filesystem path crosses trust boundary into the handler |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-01 | Tampering | iCal fetcher accepts user-configured URL | mitigate | `_safe_ics_url`: scheme allowlist (`https` only), reject empty hostname, resolve every A/AAAA record and reject any in RFC1918/loopback/link-local/ULA via `ipaddress.ip_address().is_private/is_loopback/is_link_local` checks against `socket.getaddrinfo(..., AF_UNSPEC)` |
| T-01-02 | Tampering | iCal fetcher follows redirects to private addresses | mitigate | Custom `HTTPRedirectHandler` subclass that raises `HTTPError` on 3xx; on any redirect → return [] for that URL |
| T-01-03 | DoS | iCal upstream returns 100MB body | mitigate | `ICS_MAX_BYTES = 1_048_576` (1 MiB) cap on Content-Length AND on streamed read; `ICS_FETCH_TIMEOUT_S = 10` socket timeout |
| T-01-04 | Tampering | events.json path traversal via symlink | mitigate | `Path.expanduser().resolve()` + `.is_relative_to(config.home().resolve())`; reject and return [] if escape detected |
| T-01-05 | Information disclosure | Handler error path leaks filesystem path / URL / Notion DB id / traceback | mitigate | Generic `{"error":"internal error"}` body on Exception; stderr log uses `type(exc).__name__` only (no message, no URL, no path) — mirrors `lib/api/projects.py` and `lib/api/chat.py` discipline |
| T-01-06 | DoS | Cache stampede — N concurrent requests trigger N Notion/iCal fetches | mitigate | Module-level `threading.Lock` held for the duration of a cache miss; concurrent requests wait, then read the freshly-populated cache entry. Acceptable for personal-cockpit concurrency (low qps); documented tradeoff |
| T-01-07 | Information disclosure | Notion token leaks in error log | mitigate | The existing `lib/notion.py` `_request` already redacts: it never prints the token, only HTTP status + first 200 chars of body. New `query_calendar_db` reuses `_request` verbatim — no new token-handling code paths |
| T-01-08 | Injection | iCal SUMMARY contains control chars / HTML | mitigate | Parser preserves SUMMARY as a Python str; JSON encoder escapes any control chars. Frontend (Plan 01-02) renders via React text node (auto-escaped), not dangerouslySetInnerHTML |
| T-01-09 | Tampering | Query-string `from`/`to` injection | mitigate | `datetime.strptime(value, "%Y-%m-%d")` strict validation; on parse fail → HTTP 400 with generic hint, no echo of malicious input |
| T-01-SC | Tampering | npm/pip/cargo installs | accept | No package installs in this plan — all parsing is stdlib-only (urllib, re, ipaddress, datetime, zoneinfo, socket, threading, json). No legitimacy gate needed |
</threat_model>

<verification>
- `grep -q '/api/v1/calendar' lib/api/__init__.py` — route registered
- `grep -q 'def handle_calendar' lib/api/calendar.py` — handler exists
- `grep -q 'def query_calendar_db' lib/notion.py` — helper added
- `grep -q '\[calendar\]' invisible.toml.example` — config template present
- `grep -A1 'API_V1_ROUTES\[path\](self)' bin/invisible-dashboard | grep -q 'return'` — dispatch returns
- `grep -q "import icalendar\|from icalendar\|dateutil" lib/api/calendar.py` MUST return empty (stdlib only)
- `grep -q 'icalendar\|python-dateutil' requirements.txt 2>/dev/null` MUST return empty
- E2E smoke (Task 5) — daemon serves 200 `[]` for unconfigured, 400 for bad params, daemon survives both requests
</verification>

<success_criteria>
- All five tasks' `<verify>` blocks pass
- `python3 -m py_compile lib/api/calendar.py lib/api/__init__.py lib/notion.py` exits 0
- requirements.txt unchanged (no new dependencies)
- Plan 01-02 can begin: the endpoint exists, returns the contracted shape on success, returns `[]` when nothing is configured, and 400 on bad input
</success_criteria>

<output>
Create `.planning/workstreams/calendar-events/phases/INV-01-api-v1-calendar-calendar-page-wired/01-01-SUMMARY.md` when done. Use Conventional Commits: `feat(INV-01-01): /api/v1/calendar with notion + ics + local sources, 60s cache, SSRF guards`. Also run `./scripts/update-changelog.py` before push (pre-push hook will block otherwise).
</output>
