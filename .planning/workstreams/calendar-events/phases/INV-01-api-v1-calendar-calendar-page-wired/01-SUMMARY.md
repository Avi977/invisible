---
phase: 01-api-v1-calendar-calendar-page-wired
plan: 01
subsystem: calendar
tags: [calendar, api, ssrf, ical, notion, cache, dashboard]
requires:
  - lib/notion.py::_request (existing, reused via query_calendar_db)
  - lib/config.py::home (existing, reused for events.json safe-path check)
  - bin/invisible-dashboard::API_V1_ROUTES (existing registry pattern)
provides:
  - GET /api/v1/calendar?from=&to=  →  list[event] (HTTP 200)
  - lib/api/calendar.handle_calendar  (registered in ROUTES)
  - lib/api/calendar.get_calendar(from, to)  (cached aggregator)
  - lib/api/calendar.merge_events(notion, ics, local)  (dedupe + sort)
  - lib/api/calendar._safe_ics_url(url)  (SSRF guard, reusable)
  - lib/notion.query_calendar_db(db_id, from, to)  (additive helper)
affects:
  - Plan 01-02 (frontend) — endpoint contract now LIVE; frontend can fetch
  - All sister /api/v1/* routes — dispatch-return fix benefits projects too
tech-stack:
  added: []
  patterns:
    - "Single-flight cache (threading.Lock around 60s TTL dict)"
    - "SSRF-safe URL fetcher (https-only + getaddrinfo AF_UNSPEC + redirect-deny)"
    - "Stdlib iCal VEVENT state-machine parser with RFC 5545 line unfolding"
    - "Path traversal defense via Path.is_relative_to(config.home().resolve())"
key-files:
  created:
    - lib/api/calendar.py (777 lines)
  modified:
    - lib/notion.py (+55 lines — additive query_calendar_db only)
    - lib/api/__init__.py (+2 lines — import + ROUTES entry + __all__)
    - bin/invisible-dashboard (+1 line — `return` after dispatch)
    - invisible.toml.example (+21 lines — [calendar] block)
decisions:
  - "Single global threading.Lock for the cache, not per-key locks. Personal-cockpit qps (~1) doesn't justify per-key complexity; documented in module docstring as a known scale tradeoff."
  - "iCal SSRF guard is https-only by default (ALLOWED_ICS_SCHEMES = ('https',)). http would let an MITM swap calendar content; the 99% case (Google Calendar / iCloud / Outlook public feeds) is already https."
  - "Custom HTTPRedirectHandler raises HTTPError on every 3xx rather than re-validating the redirect target — the URL passes _safe_ics_url once; allowing follow-through would require re-checking the new target each hop, which is racy."
  - "RRULE expansion deferred to v2 — single occurrence per VEVENT in v1. TODO comment in _parse_ical."
  - "TZID without UTC suffix emits a naive timestamp (no offset) rather than dropping the event — frontend renders at local time. Documented limitation in module docstring."
  - "Notion calendar DB hard-codes 'Date' property name; future enhancement can take property_name kwarg. Documented in query_calendar_db docstring."
  - "Dispatch-return fix in bin/invisible-dashboard is broader-scope than just calendar — it also closes a latent second-response race in the existing /api/v1/projects route. Surgical one-line fix; safe."
metrics:
  duration: "~15 minutes (single agent, sequential)"
  completed: "2026-06-02"
  tasks_completed: 5
  files_touched: 5
  lines_added: 856
  commits: 4
---

# Phase 01 Plan 01: `/api/v1/calendar` backend Summary

Backend for the Calendar page: a 3-source event aggregator (Notion DB + iCal feeds + local `~/.invisible/events.json`) behind `GET /api/v1/calendar?from=&to=`, with hardened SSRF guards on the iCal path, 60-second single-flight cache, deterministic cross-source dedupe (notion > ics > local), and a generic 500-on-failure contract that never leaks paths, URLs, or DB ids. Endpoint returns `[]` (not an error) when no source is configured — unblocks Plan 01-02 to start the frontend wiring on a real wire.

## What shipped

| File | Change | Commit |
|---|---|---|
| `lib/notion.py` | Additive `query_calendar_db(db_id, from, to)` helper after `query_recent_reviews`. Reuses `_request` (no new auth path); returns `[]` on empty db_id or any API failure. Existing helpers untouched. | `57a6261` |
| `lib/api/calendar.py` (NEW) | 777-line module: 3 source loaders, SSRF-safe iCal fetcher with redirect-deny + 1 MiB cap + 10 s timeout, stdlib `_parse_ical` (RFC 5545 line-unfolding, VEVENT state-machine), `merge_events` dedupe (title.lower(), start) with notion > ics > local priority, `get_calendar` single-flight cached aggregator, `handle_calendar` HTTP entry point. | `8a3d961` |
| `lib/api/__init__.py` | `from . import calendar` + `"/api/v1/calendar": calendar.handle_calendar` + `__all__` updated. | `e9c6435` |
| `bin/invisible-dashboard` | `return` after `API_V1_ROUTES[path](self)` so the dispatch doesn't fall through to subsequent route checks and the unconditional `_send_text("not found\n", 404)` at the end of `do_GET`. Fixes a latent race for ALL /api/v1/* routes, not just calendar. | `e9c6435` |
| `invisible.toml.example` | `[calendar]` block (notion_database_id, ics_urls) with inline docs about the SSRF posture and the auto-discovered `~/.invisible/events.json` third source. | `0df89ff` |

## Tasks

| Task | Status | Commit |
|---|---|---|
| 1 — `query_calendar_db` in lib/notion.py | done, verified | `57a6261` |
| 2 — `lib/api/calendar.py` with sources + SSRF + cache + handler | done, verified | `8a3d961` |
| 3 — Route registration + dispatch-return fix | done, verified | `e9c6435` |
| 4 — `[calendar]` block in invisible.toml.example | done, verified | `0df89ff` |
| 5 — E2E smoke (daemon + 2 curls) | done, verified | n/a (verify-only) |

## End-to-end smoke (Task 5)

```bash
$ ./bin/invisible-dashboard --no-auth --port 18765 &
[invisible] loaded 8 secrets from Infisical
[dashboard] listening on http://127.0.0.1:18765
[dashboard] WARNING: --no-auth is on; do NOT expose this beyond localhost
[dashboard] Ctrl-C to stop

$ curl -s -o /tmp/cal-ok.json -w '%{http_code}\n' \
       'http://127.0.0.1:18765/api/v1/calendar?from=2026-06-01&to=2026-06-30'
200

$ cat /tmp/cal-ok.json
[]

$ curl -s -o /tmp/cal-bad.json -w '%{http_code}\n' \
       'http://127.0.0.1:18765/api/v1/calendar?from=notadate&to=2026-06-30'
400

$ cat /tmp/cal-bad.json
{
  "error": "bad_request",
  "hint": "from and to are required YYYY-MM-DD"
}
```

Daemon survived both requests (no second-response crash from the dispatch-fall-through bug fixed in Task 3).

## Threat model — implementation

| Threat | Mitigation as built |
|---|---|
| T-01-01 SSRF via user-configured iCal URL | `_safe_ics_url`: https-only allowlist; `socket.getaddrinfo(..., AF_UNSPEC)` resolves ALL A+AAAA records; every address checked against `_PRIVATE_IP_NETS` (RFC1918 + loopback + link-local + ULA); belt-and-braces `ip.is_private/is_loopback/is_link_local/is_multicast/is_reserved/is_unspecified`. |
| T-01-02 Redirect to private address | `_NoRedirectHandler` subclass of `urllib.request.HTTPRedirectHandler` — `redirect_request` raises `HTTPError` on every 3xx, so the validated URL is the only request that fires. |
| T-01-03 Oversized iCal body / slow upstream | `ICS_FETCH_TIMEOUT_S = 10`; `ICS_MAX_BYTES = 1_048_576` enforced via `Content-Length` check up-front AND via `resp.read(ICS_MAX_BYTES + 1)` with overrun check (catches servers that lie about or omit `Content-Length`). |
| T-01-04 events.json path traversal | `_safe_events_path`: `(config.home() / "events.json").resolve()` + `is_relative_to(config.home().resolve())`. Symlink trickery rejected. |
| T-01-05 Info disclosure via error path | Every except branch logs `type(exc).__name__` only — never `str(exc)`, never the URL, never the path, never the DB id. HTTP 500 body is the bare string `{"error":"internal error"}`. Mirrors `lib/api/projects.py` and `lib/api/chat.py` discipline. |
| T-01-06 Cache stampede | Module-level `threading.Lock` held for the full duration of a cache miss; concurrent requests block on the lock and read the fresh entry on release. Personal-cockpit tradeoff documented at the lock definition. |
| T-01-07 Notion token leak | Token never touches `calendar.py` — all Notion calls go through `lib/notion._request`, which never prints the token. New `query_calendar_db` adds no new token-handling code. |
| T-01-08 Injection via iCal SUMMARY | SUMMARY kept as Python str; JSON-encoded over the wire; frontend (Plan 01-02) renders as React text node (auto-escaped). No `dangerouslySetInnerHTML`. |
| T-01-09 from/to query-string injection | `datetime.strptime(value, "%Y-%m-%d")` strict-parse; bad input → 400 with generic hint that does NOT echo the malicious value. |

## Decisions

1. **Single global cache lock vs per-key.** Per-key locks are correct at scale but overkill for a 1-qps daemon. The single lock holds during all network I/O — concurrent requests for the same window are served from cache on lock release; concurrent requests for *different* windows serialise. Tradeoff documented in the cache definition.
2. **https-only iCal scheme.** Plan said `ALLOWED_ICS_SCHEMES = ("https",)`. Kept it. The 99% case (Google / iCloud / Outlook public feeds) is https; http would let an MITM swap calendar bodies, and we don't need it for any current source.
3. **Redirect-deny over redirect-revalidate.** Re-validating a 3xx target would require re-running `_safe_ics_url` per hop with its own getaddrinfo + ipaddress check, plus a hop count. Simpler: refuse every 3xx and let the user point us at the canonical URL.
4. **TZID-without-UTC events emitted as naive timestamps.** Documented limitation rather than silent drop. zoneinfo lookup may fail (e.g. unknown `TZID=Foo/Bar`); we'd rather show the event at a wrong-by-offset time than disappear it. Frontend renders at local time anyway.
5. **RRULE deferred.** Plan said v2. Inline `TODO(recurrence)` in `_parse_ical`.

## Deviations from Plan

None. The plan was implemented exactly as written.

Two notes worth recording:

- **STATE.md drift on entry.** The orchestrator's pre-execute `state` update left a non-staged change to `.planning/workstreams/calendar-events/STATE.md`. Per the prompt, STATE.md is the orchestrator's territory — left untouched in this plan's commits.
- **No requirements.txt at all.** The repo doesn't carry a `requirements.txt` file (Python stdlib + Infisical bootstrap covers it). The stdlib-only constraint is therefore vacuously satisfied — there's nothing to NOT add to.

## Authentication gates

None encountered. Notion path is fully optional: empty `database_id` short-circuits before any HTTP call, so the Notion client is never touched during the smoke run.

## Known Stubs

None. Every code path returns either real data or an empty list `[]`; there are no placeholder strings, no "coming soon" text, no hardcoded mock fixtures.

The HTTP response is `[]` for "no source configured" — by design, per Success Criterion #7 (the plan explicitly says this is NOT an error). Plan 01-02's frontend will render an empty state for that case.

## Verification gate (plan-level)

```
1. route registered          ── PASS  (grep /api/v1/calendar lib/api/__init__.py)
2. handler exists            ── PASS  (grep def handle_calendar lib/api/calendar.py)
3. helper added              ── PASS  (grep def query_calendar_db lib/notion.py)
4. template present          ── PASS  (grep ^\[calendar\] invisible.toml.example)
5. dispatch returns          ── PASS  (grep -A1 API_V1_ROUTES[path](self) | grep return)
6. no icalendar/dateutil     ── PASS  (no banned import in calendar.py)
7. requirements.txt clean    ── PASS  (no requirements.txt at all)
8. files compile             ── PASS  (python3 -m py_compile)
```

## Self-Check: PASSED

- [x] `lib/api/calendar.py` exists (777 lines, def handle_calendar present)
- [x] `lib/api/__init__.py` contains `"/api/v1/calendar"`
- [x] `lib/notion.py` contains `def query_calendar_db`
- [x] `bin/invisible-dashboard` has `return` after `API_V1_ROUTES[path](self)`
- [x] `invisible.toml.example` contains `[calendar]`
- [x] No `requirements.txt` modifications (no file exists)
- [x] Smoke: HTTP 200 `[]` for valid params; HTTP 400 `{"error":"bad_request",...}` for bad params
- [x] All four commits present: `57a6261`, `8a3d961`, `e9c6435`, `0df89ff`
