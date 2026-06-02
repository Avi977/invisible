---
workstream: calendar-events
milestone: M2
phase: 01-api-v1-calendar-calendar-page-wired
shipped_at: 2026-06-02
pr: 9
pr_url: https://github.com/Avi977/invisible/pull/9
branch: ws/calendar-events
commits_on_branch: 12
verification_status: PASS
verification_score: 8/8 success criteria + 14/14 STRIDE mitigations
---

# calendar-events — SHIPPED (PR #9)

## What landed

`GET /api/v1/calendar?from=YYYY-MM-DD&to=YYYY-MM-DD` is live. The frontend Calendar page (`frontend/pages/calendar.jsx`) now fetches real events on mount and renders them across both the MiniCal month-grid (event dots) and the WeekView strip (positioned events). Three event sources, all optional, merge into one response.

## Files changed (9, all within OWNS / EDITS LIGHTLY / additive scope)

**OWNS:**
- `lib/api/calendar.py` (NEW, 777 lines, stdlib-only)
- `frontend/pages/calendar.jsx` (rewrite, 611 lines)

**EDITS LIGHTLY:**
- `lib/api/__init__.py` — `from . import calendar` + ROUTES entry
- `bin/invisible-dashboard` — registry dispatch `return` bugfix (latent fall-through that affected all `/api/v1/*`) + CORS dedupe fix in `_send_json` (surfaced by Wave 2 smoke)
- `invisible.toml.example` — `[calendar]` block template

**ADDITIVE ONLY:**
- `lib/notion.py` — new `query_calendar_db` helper at line 323, zero existing functions modified

## Event sources (priority order)

1. **Notion Calendar DB** — `[calendar] notion_database_id = "..."`. Uses existing `lib/notion.py::_request`. Filters server-side by date range.
2. **iCal feeds** — `[calendar] ics_urls = ["https://..."]`. Stdlib VEVENT state-machine parser (RFC 5545 line unfolding). SSRF-guarded.
3. **Local file** — `~/.invisible/events.json`. Format: `[{title, start, end, color?, project_id?}]`. Path-traversal-guarded.

No source configured → `[]` (HTTP 200), never an error. UI shows "no events configured" gracefully.

## Security mitigations (ASVS L1)

| Threat | Primitive |
|---|---|
| SSRF | `ipaddress.ip_address().is_private / is_loopback / is_link_local`, `socket.getaddrinfo(host, None, AF_UNSPEC)`, custom `_NoRedirectHandler` raising `HTTPError` on 3xx |
| iCal DoS | `ICS_FETCH_TIMEOUT_S = 10`, `ICS_MAX_BYTES = 1_048_576` (Content-Length AND streamed-read enforced) |
| Path traversal | `Path.expanduser().resolve().is_relative_to(config.home().resolve())` |
| Info disclosure | Generic `{"error":"internal error"}` body; `type(exc).__name__` only in stderr (no path, URL, DB id, or token) |
| Cache stampede | Module-level `threading.Lock` single-flight around the 60s TTL dict |
| Frontend XSS | React text-escaping only; no `dangerouslySetInnerHTML` |
| Shape tampering | `Array.isArray` guard + RFC3339 parse skip on malformed events |

## Verification

`gsd-verifier` ran goal-backward audit (read all 777 + 611 lines of code, ran live daemon + curl, ran runtime assertions against `_safe_ics_url` / `_parse_ical` / `merge_events` / `_NoRedirectHandler` / cache, audited `git diff --name-only main..HEAD` for sister-workstream creep). Verdict: **PASS** on all 8 ROADMAP success criteria. See `phases/INV-01-api-v1-calendar-calendar-page-wired/VERIFICATION.md`.

Playwright smoke (Chromium headless) navigated to `/`, clicked `text=Calendar`, loaded both the empty path (`[]` → placeholder) and a seeded path (3 events via temp `INVISIBLE_HOME` → render → click event → popover opens → ESC closes). Screenshots: `/tmp/calendar-smoke.png` (week strip + event) and `/tmp/calendar-smoke-popover.png` (popover open).

## Non-blocking v2 followups (documented inline as TODOs)

1. MiniCal month-grid dots scoped to fetched week range only — broader month-range fetch is v2.
2. iCal RRULE expansion not implemented — single-occurrence VEVENT only.
3. Naive `TZID` timestamps treated as UTC — `zoneinfo` lift is v2.
4. Notion page-id ≠ DATA_SETS project-id — Notion events fall through to event-level color until ID mapping is implemented.
5. MiniCal "Calendars" legend still hardcoded — deriving from event sources is v2.

## Where this fits in M2

1 of 6 M2 workstreams now PR-open. Sibling workstreams (`tools-page`, `relations-page`, `tauri-windows`, `vps-connection`, `ci-and-onboarding`) still in flight in their respective `~/.invisible-ws/<name>/` worktrees.

After merge: clean up this worktree with `git worktree remove ~/.invisible-ws/calendar-events && git branch -D ws/calendar-events` (per M1 cleanup pattern in `CONTEXT.md`).
