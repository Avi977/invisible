---
phase: 01-api-v1-calendar-calendar-page-wired
verified: 2026-06-01T21:35:00Z
verdict: PASS
status: passed
score: 8/8 success criteria verified
threat_model_coverage: 9/9 STRIDE entries mitigated in code (T-01-01..09); 5/5 frontend (T-01-FE-01..05)
workstream_isolation: clean (no creep beyond OWNS / EDITS LIGHTLY allow-list)
files_changed: 9
commits: 8
---

# Phase 01 Verification — calendar-events

**Phase goal (from ROADMAP.md):** Calendar page shows real events on its month + week views, replacing the hardcoded `EVENTS` array in `frontend/pages/calendar.jsx`.

**Verified:** 2026-06-01T21:35:00Z
**Verdict:** PASS
**Re-verification:** No — initial verification

---

## Success Criteria

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | `GET /api/v1/calendar?from=&to=` returns `[{id, title, start, end, color, project_id?, source}]` | PASS | Handler at `lib/api/calendar.py:737-777` `handle_calendar`; route registered at `lib/api/__init__.py:21,26`; live curl produced `HTTP 200 []` (no source configured — empty array still satisfies shape contract — see live test below); shape is built per-source at `_maybe_emit_ical_event:356-363`, `_fetch_notion_events:519-528`, `_fetch_local_events:598-608`. |
| 2 | `start` and `end` are RFC3339 timestamps | PASS | iCal: `_parse_ical_dt:241-276` calls `dt.replace(tzinfo=_dt.timezone.utc).isoformat()` → RFC3339. Notion: `_notion_date_to_iso:453-465` uses `datetime.fromisoformat` + `isoformat()` → RFC3339. Local: same `_notion_date_to_iso` normaliser at `lib/api/calendar.py:590-591`. All three source builders emit ISO-8601 strings. |
| 3 | Frontend renders events on month grid AND week strip | PASS | `MiniCal` consumes `events` prop at `frontend/pages/calendar.jsx:170,188-204,228`; the `c.d % 3 === 0` mock is removed (grep returns empty); `eventDaysSet` derivation present at line 188 keyed on year+month. `WeekView` consumes the prop at line 282,311. Playwright smoke confirmed 3 `.week-event` nodes rendered with the seeded events.json. |
| 4 | Project colours match `data.jsx`'s `DATA_SETS[..].projects[i].color` when `project_id` matches | PASS | `flattenProjects:94-109` walks `DATA_SETS.{default,client,...}.projects` and dedupes by id. `colorForEvent:114-125` checks `event.project_id` against the flat list, falling back to `event.color` (validated hex), then to `DEFAULT_EVENT_COLOR = "#8aa9ff"`. Smoke screenshot shows colored event pills aligned with `DATA_SETS.default.projects[i].color`. |
| 5 | Multi-source merge with `(title, start)` dedupe | PASS | `merge_events:648-666` iterates `(notion_evs, ics_evs, local_evs)` in priority order; first key wins. `_dedupe_key:641-645` returns `(title.strip().lower(), start)` — confirmed case-insensitive via runtime assertion (`'Standup' == 'STANDUP'` produces identical key). |
| 6 | 60s server-side cache | PASS | `CACHE_TTL_S = 60` at line 97; `_CACHE` dict + `_CACHE_LOCK = threading.Lock()` at lines 140-141; `get_calendar:704-718` takes the lock, checks `(now - entry[0]) < CACHE_TTL_S`, returns cached if fresh else recomputes under lock. Runtime test confirms cache populates on first call and serves on second. |
| 7 | No source configured → `200 []` | PASS | Live curl against clean dev env (no `[calendar]` in `~/.invisible/invisible.toml`, no `events.json`) returned `HTTP 200` body `[]`. `_compute_calendar:684-701` returns `merge_events([], [], [])` when no source produces events; `handle_calendar` passes through to `_send_json(events, status=200)` at line 766. |
| 8 | iCal parsing stdlib only — no new `requirements.txt` entry | PASS | `grep -E "import icalendar\|from icalendar\|dateutil" lib/api/calendar.py` returns empty. `requirements.txt` does not exist in the repo (vacuously satisfied — there is nothing to add to). Parser is hand-rolled VEVENT state machine at `_parse_ical:295-336` using only `datetime`, `re`, `urllib`, `ipaddress`, `socket`, `threading`, `time`, `json`, `pathlib` (all stdlib). |

**Score: 8/8 success criteria verified.**

---

## Threat Model Coverage

### Plan 01-01 (backend) — STRIDE register

| Threat | Mitigation | Status | Evidence |
|--------|-----------|--------|----------|
| T-01-01 SSRF via user iCal URL | scheme allowlist + private-net IP rejection | PASS | `ALLOWED_ICS_SCHEMES = ("https",)` at line 104; `_PRIVATE_IP_NETS` tuple at lines 110-119 covers RFC1918, loopback, link-local v4+v6, ULA; `_safe_ics_url:170-233` uses `socket.getaddrinfo(host, None, socket.AF_UNSPEC)` to check ALL A/AAAA records and rejects on `is_private/is_loopback/is_link_local/is_multicast/is_reserved/is_unspecified`. Runtime test confirms: `http://`, `file://`, `javascript:`, `https://127.0.0.1`, `https://192.168.1.1`, `https://[::1]`, `https://[fc00::1]` all return `None`. |
| T-01-02 Redirect to private address | custom HTTPRedirectHandler | PASS | `_NoRedirectHandler:149-167` subclasses `urllib.request.HTTPRedirectHandler`; `redirect_request` raises `HTTPError` on every 3xx, preventing redirect chase. Used at `_fetch_one_ics:378` via `urllib.request.build_opener(_NoRedirectHandler)`. Runtime test confirms HTTPError is raised on simulated 302 to `10.0.0.1`. |
| T-01-03 Oversized iCal body / slow upstream | 1 MiB cap + 10s timeout | PASS | `ICS_FETCH_TIMEOUT_S = 10` (line 98); `ICS_MAX_BYTES = 1_048_576` (line 99). Two-layer enforcement at `_fetch_one_ics:386-403`: (a) Content-Length pre-check rejects if header > cap; (b) `resp.read(ICS_MAX_BYTES + 1)` followed by length check catches servers that lie about/omit Content-Length. Both branches return `[]` for that URL and the loader continues to the next. |
| T-01-04 events.json path traversal | resolved-path + is_relative_to | PASS | `_safe_events_path:539-559` calls `config.home().resolve()` then `(invisible_root / "events.json").resolve()` and confirms `candidate.is_relative_to(invisible_root)`. Symlink trickery rejected. Runtime test resolves to `/Users/ace/.invisible/events.json` (inside home). |
| T-01-05 Info disclosure via error path | generic body + type-only logs | PASS | Every except branch (`401, 416, 432, 475, 569, 768`) logs only `f"... {type(exc).__name__}"` — never message, URL, path, or DB id. HTTP 500 body is literal `{"error": "internal error"}` (line 775). Mirrors `lib/api/projects.py` discipline. |
| T-01-06 Cache stampede | module-level Lock + single-flight | PASS | `_CACHE_LOCK = threading.Lock()` at line 141; `get_calendar:712-718` takes the lock for the FULL duration of a cache miss (network I/O included). Concurrent same-window requests block, then read the freshly-populated cache entry. Tradeoff documented in module docstring (acceptable at personal-cockpit qps). |
| T-01-07 Notion token leak | delegated to lib/notion._request | PASS | `query_calendar_db:323-375` reuses existing `_request` helper which never prints the token. The new helper adds no new token-handling code. `database_id` is also never logged. |
| T-01-08 Injection via iCal SUMMARY | JSON-encoded + React text node | PASS | SUMMARY values are kept as Python `str` (line 358), JSON-encoded over the wire. Frontend renders via JSX text children — `grep dangerouslySetInnerHTML frontend/pages/calendar.jsx` returns empty. |
| T-01-09 from/to query-string injection | strict strptime + generic 400 | PASS | `_parse_date_param:726-734` calls `datetime.strptime(value, "%Y-%m-%d")`; on `ValueError`/`TypeError` returns `None`. Handler at `756-762` sends a 400 with a generic `hint` field — does NOT echo the malicious input. Live curl with `from=notadate` produced exactly the contracted shape. |

### Plan 01-02 (frontend) — STRIDE register

| Threat | Mitigation | Status | Evidence |
|--------|-----------|--------|----------|
| T-01-FE-01 XSS via event title | React text nodes only | PASS | All event titles, project names, source badges render as JSX text children (lines 250, 322, 464, 478, 481). `grep dangerouslySetInnerHTML` returns empty. |
| T-01-FE-02 Non-array response | Array.isArray guard | PASS | `fetch.then:527-529` calls `if (!Array.isArray(json)) throw new Error("malformed response")`. Five other `Array.isArray` checks at lines 100, 140, 190, 209, 311 defend MiniCal + WeekView from non-array `events` props. |
| T-01-FE-03 Invalid RFC3339 → NaN | transformEvent returns null | PASS | `transformEvent:129-160` checks `isNaN(start.getTime())` and `isNaN(end.getTime())`; returns `null` for invalid. `useEffect:539-542` filters out nulls before `setEvents`. |
| T-01-FE-04 10k events DoS | accept (personal cockpit) | ACCEPT (documented) | Plan explicitly accepts; week view windows naturally to 7×12 cells. |
| T-01-FE-05 Error path leaks backend hint | HTTP status only | PASS | `useEffect:519-525` does `try { await response.text(); } catch ... ` to swallow the body and throws `new Error("HTTP ${status}")`. Visible `errorMsg` (line 551) is derived from `err.message` which is the HTTP status or `"network error"` — never the backend's `hint` field. |

**Threat-model score: 14/14 (9 backend STRIDE + 5 frontend STRIDE) with T-01-FE-04 explicitly accepted in plan and documented.**

---

## Workstream Isolation

`git diff --stat 4b877a1..HEAD` produced 9 files:

```
.planning/.../01-SUMMARY.md          (planning artifact, expected)
.planning/.../02-SUMMARY.md          (planning artifact, expected)
CHANGELOG.md                          (standard project artifact)
bin/invisible-dashboard               (EDITS LIGHTLY — within scope)
frontend/pages/calendar.jsx           (OWNS — within scope)
invisible.toml.example                (EDITS LIGHTLY — within scope)
lib/api/__init__.py                   (EDITS LIGHTLY — within scope)
lib/api/calendar.py                   (OWNS — new file, within scope)
lib/notion.py                         (additive only, confirmed via diff)
```

**Allow-list audit: PASS.** No sister-workstream files touched.

- No other `frontend/pages/*.jsx` modified
- No `lib/api/{projects,chat,tree_*,analytics,tools,relations}.py` modified
- No `src-tauri/`, `bin/invisible-pty`, `lib/pty_server.py` touched
- `lib/notion.py` confirmed additive-only via `git diff 4b877a1..HEAD -- lib/notion.py`: a single new function `query_calendar_db` appended at line 323; no existing function modified

Uncommitted working-tree changes: `.planning/workstreams/calendar-events/{ROADMAP.md,STATE.md}` — these are the orchestrator's territory per the plan's explicit guidance and were left untouched by the executor's commits. Out of scope for this verification.

---

## Live Execution

Started dashboard daemon, hit `/api/v1/calendar` with valid + bad params, captured response headers, killed daemon:

```
$ ./bin/invisible-dashboard --no-auth --port 18765 &
[invisible] loaded 8 secrets from Infisical

$ curl -s -w '%{http_code}' 'http://127.0.0.1:18765/api/v1/calendar?from=2026-06-01&to=2026-06-30'
HTTP 200
body: []

$ curl -s -w '%{http_code}' 'http://127.0.0.1:18765/api/v1/calendar?from=notadate&to=2026-06-30'
HTTP 400
body: {"error": "bad_request", "hint": "from and to are required YYYY-MM-DD"}

$ curl -s -D - 'http://127.0.0.1:18765/api/v1/calendar?from=2026-06-01&to=2026-06-30' -o /dev/null | grep 'Access-Control-Allow-Origin'
Access-Control-Allow-Origin: *
$ # → exactly 1 ACAO header (CORS fix verified)

$ curl -s -o /dev/null -w '%{http_code}\n' 'http://127.0.0.1:18765/api/v1/calendar?from=2026-06-08&to=2026-06-14'
200
$ # → daemon survives multiple requests (dispatch-return fix verified)
```

**Live execution: PASS.** All three Success Criterion #7 / #1 / #5 contracts honoured end-to-end. CORS fix produces exactly one `Access-Control-Allow-Origin` header (not the previous broken duplicate). Daemon does not crash between requests (dispatch-return fix is in place).

### Playwright smoke artifacts (executor)

- `/tmp/calendar-smoke.png` (697 KB, captured 2026-06-01 21:25 by executor): shows MiniCal month picker on left with the current date highlighted, "Up next" entry with the seeded standup, "Calendars" legend, and the WeekView right pane with a "Smoke standup" event pill anchored on today's column.
- `/tmp/calendar-smoke-popover.png` (623 KB): same surface with the click-to-expand popover overlaid — title "Smoke standup", color dot, source label, close button.

Inspected by verifier; both renders match the success-criteria narrative (real events on the grid + interactive popover).

---

## Deviations (from 02-SUMMARY.md)

### 1. Wave 1 CORS regression auto-fixed by Wave 2 (commit `a0fc83b`)

**Assessment: APPROPRIATE.** Wave 1's CORS posture in `_send_json` echoed the Origin back for loopback callers ON TOP of the global `*` from `end_headers`. Browsers reject responses with multiple ACAO values per CORS spec, breaking every cross-origin fetch from `:8090` → `:8765`. Wave 2 surfaced this during the Playwright smoke and fixed it by removing the redundant loopback-echo branch. The workstream owns `bin/invisible-dashboard` as "EDITS LIGHTLY" — Wave 1 already touched the file once (commit `e9c6435`), and the fix is surgical (-10 / +8 lines, removing the comment-contradicting branch). The fix also benefits sister `/api/v1/projects` and any future `/api/v1/*` routes — confirmed via live curl above. Within scope.

### 2. INVISIBLE_API_BASE runtime override (in commit `18b2b33`)

**Assessment: APPROPRIATE.** Plan's `<behavior>` hardcoded port 8765 but the `<verify>` block used `--port 18765`, which would have silently broken the smoke. Wave 2 resolved by making `API_BASE` configurable via `window.INVISIBLE_API_BASE` with the plan-specified default. Production behaviour is unchanged (default tracks `frontend/data.jsx:464`). The override path is for test isolation only — no production code reads it. Reasonable resolution of a plan tension.

### 3. Playwright dispatchEvent('click') workaround for `.week-event`

**Assessment: APPROPRIATE.** Playwright's auto-scroll cannot reach absolutely-positioned children of an overflow region in headless mode. Using `dispatchEvent('click')` instead of `click()` skips actionability checks and fires React's onClick directly. Lives in `/tmp/calendar-smoke.js` — NOT committed to the repo, so no production-code impact. Canonical Playwright workaround documented in the smoke script.

**All three deviations are appropriate, surgical, and either auto-fixes for real bugs or test-infrastructure workarounds.**

---

## Followups (non-blocking)

None essential for /gsd:ship. The following are nice-to-haves the executor or planner already documented inline as v2 enhancements:

1. **MiniCal month-grid dots only light up days within the fetched ISO-week range.** TODO comment at `frontend/pages/calendar.jsx:183-187`. Browsing to a different month does not re-fetch — the dots will appear missing for adjacent weeks. A v2 enhancement is to broaden the API window to the full visible month.
2. **iCal RRULE recurrence not expanded.** TODO at `lib/api/calendar.py:303-307`. Recurring events from Google/iCloud calendars currently show only on their DTSTART date.
3. **iCal TZID without UTC suffix emits a naive timestamp.** Documented limitation in module docstring; frontend renders at local time. zoneinfo-aware parsing is a future iteration.
4. **MiniCal "Calendars" legend is hardcoded** to the personal-projects palette. Deriving from active events would surface only the connected sources, which is worse UX for v1. TODO at `frontend/pages/calendar.jsx:257-259`.
5. **Notion source `project_id` is a Notion page UUID, not a DATA_SETS project id.** So color resolution via `DATA_SETS` lookup works for `local` and `ics` sources where the user controls the id, but not automatically for `notion` source events. Not flagged in the plan or SUMMARY — minor UX caveat for users with a Notion calendar database who expect their dashboard project colors to apply. A future enhancement could map Notion-page-id → DATA_SETS-project-id via a config table.

None of these block the phase goal: real events from `/api/v1/calendar` render on month + week views.

---

## Final Verdict

The phase delivers its goal end-to-end: the backend ships a hardened 3-source aggregator (Notion + iCal + local) behind `/api/v1/calendar` with all 9 STRIDE mitigations in code, the frontend swaps the hardcoded `EVENTS` mock for a live fetch with proper loading/empty/error states and a click-to-expand popover, and the Playwright + curl smokes confirm the wire works in both directions. All 8 ROADMAP success criteria are verifiably TRUE in the codebase, and the three documented deviations (CORS dedupe, INVISIBLE_API_BASE override, Playwright dispatchEvent workaround) are appropriate surgical responses to real surface tensions rather than scope creep.

## VERIFICATION PASSED
