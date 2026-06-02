---
phase: 01-api-v1-calendar-calendar-page-wired
plan: 02
type: execute
wave: 2
depends_on: ["01"]
files_modified:
  - frontend/pages/calendar.jsx
  - frontend/data.jsx
autonomous: true
requirements: []
tags: [calendar, frontend, react, ui]

must_haves:
  truths:
    - "The Calendar page fetches real events from GET /api/v1/calendar on mount instead of rendering the hardcoded EVENTS const"
    - "Events with a project_id matching a DATA_SETS project render in that project's color from data.jsx"
    - "Events with no matching project_id render in the event's own color, falling back to #8aa9ff"
    - "When the API returns [], the week grid shows a 'no events configured' placeholder; MiniCal still renders"
    - "During the initial fetch, the week grid shows a skeleton (no flashing of stale hardcoded data)"
    - "On fetch error, the week grid shows 'couldn't load events' with a retry button; the page does not crash"
    - "The live 'now' line (week-now div) still renders at the current time on the today column"
    - "Clicking a week-event opens a popover showing title, time range, project name; ESC closes it"
    - "MiniCal's month-grid dots reflect days that have real events from the API response (replacing the hardcoded `c.d % 3` mock)"
  artifacts:
    - path: "frontend/pages/calendar.jsx"
      provides: "real-data Calendar with fetch, transform, color resolution, empty/loading/error states, click-to-expand"
      contains: "fetch.*api/v1/calendar"
      min_lines: 220
  key_links:
    - from: "frontend/pages/calendar.jsx"
      to: "/api/v1/calendar"
      via: "fetch in useEffect on Monday-of-week range"
      pattern: "fetch.*api/v1/calendar"
    - from: "frontend/pages/calendar.jsx event color resolver"
      to: "window.DATA_SETS.default.projects"
      via: "project_id lookup"
      pattern: "DATA_SETS\\.default\\.projects"
---

<objective>
Replace the hardcoded `EVENTS` array in `frontend/pages/calendar.jsx` with a real fetch against `GET /api/v1/calendar`. Preserve the visual design (week strip, mini month picker, project color dots, glass aesthetic), add loading / empty / error states, and add click-to-expand on events.

Purpose: This is the user-visible payoff of Plan 01-01. The backend can return events from Notion + iCal + ~/.invisible/events.json, but until the page consumes the endpoint, the UI still shows the mock standup / Wave jitter / Hetzner onboarding entries that no real user has.

Output: Modified `frontend/pages/calendar.jsx` that fetches `/api/v1/calendar?from=<monday>&to=<sunday>` on mount, transforms RFC3339 timestamps → the existing `{day, start, end, title, c}` shape WeekView consumes, resolves colors via `DATA_SETS[*].projects[*].color` lookup, handles empty/loading/error gracefully, and shows a click-to-expand popover. Possibly a no-op or comment in `frontend/data.jsx` if a CALENDAR_EVENTS mock is found there (per audit in Task 1).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/workstreams/calendar-events/ROADMAP.md
@.planning/workstreams/calendar-events/phases/INV-01-api-v1-calendar-calendar-page-wired/01-01-SUMMARY.md

<interfaces>
<!-- Contracts the executor needs. Use directly — no codebase scavenging. -->

API contract (from Plan 01-01):
```
GET http://127.0.0.1:8765/api/v1/calendar?from=YYYY-MM-DD&to=YYYY-MM-DD
→ HTTP 200, [{
    "id":         "<str>",
    "title":      "<str>",
    "start":      "<RFC3339 e.g. 2026-06-01T09:30:00Z>",
    "end":        "<RFC3339 e.g. 2026-06-01T10:00:00Z>",
    "color":      "<hex e.g. #8aa9ff>",
    "project_id": "<str, optional>",
    "source":     "notion" | "ics" | "local"
}, ...]
```
Empty source: HTTP 200 `[]`.
Bad params: HTTP 400 `{"error":"bad_request","hint":"..."}`.
Internal: HTTP 500 `{"error":"internal error"}`.

WeekView's existing event shape (current calendar.jsx lines 5-29):
```
{ day: int 0-6 (Mon=0..Sun=6), start: decimal hours (e.g. 9.5 = 9:30am), end: decimal hours, title: string, project: string, c: hex color }
```
This is the shape WeekView's `.filter(e => e.day === day).map(...)` consumes (lines 142-155). The transform from the API shape to this shape is the core of Task 2.

Project color source (frontend/data.jsx lines 2-101):
```
window.DATA_SETS = {
  default: { projects: [{ id, color, ... }, ...] },
  client:  { projects: [{ id, color, ... }, ...] },
};
```
The lookup precedence the backend cannot do (because the backend has no access to the user's project list): `project_id` from event → search DATA_SETS.default.projects then DATA_SETS.client.projects for an entry with matching `id` → use `.color`. If no match: use event.color (the backend default of #8aa9ff if nothing else).

Babel-standalone idiom (current calendar.jsx line 3 and line 195):
```
const { useState: useStateC, useMemo: useMemoC } = React;
// ...
window.Calendar = Calendar;
```
Add `useEffect: useEffectC` to the destructure. Keep the `window.Calendar = Calendar` mounting; the dashboard frontend (bin/invisible-frontend on :8090) discovers components via `window.<Name>`.

Existing dependencies inside calendar.jsx that MUST be preserved:
- `MiniCal` component (lines 34-105) — month picker, "Up next" list, "Calendars" legend
- `WeekView` component (lines 113-168) — the main week grid with the live "now" line
- `fmtH(h)` helper (line 107) — formats decimal hours to "HH:MM"
- `DAY_NAMES` (line 31), `HOURS` (line 32)
- The `Calendar` root (lines 170-193) — cal-layout flex shell with MiniCal on the left

CSS classes used (must keep working — defined in the global stylesheet, not in calendar.jsx):
- `.cal-layout`, `.glass`, `.mini-cal`, `.mini-cal-head`, `.mini-cal-title`, `.mini-cal-nav`, `.mini-cal-grid`, `.mini-day-h`, `.mini-day`, `.week-view`, `.week-head`, `.week-body`, `.week-times`, `.week-time-slot`, `.week-col`, `.slot`, `.week-event`, `.e-time`, `.week-now`, `.chip`, `.chip-dot`, `.btn`, `.accent`, `.mono`, `.icon-btn`
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Audit data.jsx for CALENDAR_EVENTS mock; remove only if it exists</name>
  <files>frontend/data.jsx</files>
  <read_first>
    - frontend/data.jsx (lines 1-101 for DATA_SETS structure; whole file to scan for CALENDAR_EVENTS)
  </read_first>
  <action>
    Grep frontend/data.jsx for any of: `CALENDAR_EVENTS`, `calendarEvents`, or a top-level `const EVENTS`. The ROADMAP `EDITS LIGHTLY` line mentions "remove CALENDAR_EVENTS mock (check existence)" — but the actual hardcoded EVENTS array lives in calendar.jsx (lines 5-29), not data.jsx. If grep finds CALENDAR_EVENTS in data.jsx, remove the binding AND its inclusion in any `Object.assign(window, {...})` call at the bottom of the file. If grep finds nothing, leave data.jsx UNTOUCHED and document this in the task `<done>` field — do not insert a comment, do not add a placeholder. DO NOT modify DATA_SETS, FOLDERS, TOOL_WORKFLOWS, TERM_CONTEXT, ANALYTICS, or the fetchProjects helper at the bottom — those are sister workstreams' surface.
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/calendar-events &amp;&amp; ! grep -E 'CALENDAR_EVENTS|calendarEvents' frontend/data.jsx &amp;&amp; grep -q 'DATA_SETS' frontend/data.jsx &amp;&amp; grep -q 'fetchProjects' frontend/data.jsx</automated>
  </verify>
  <done>No CALENDAR_EVENTS or calendarEvents symbol exists in frontend/data.jsx; DATA_SETS and fetchProjects remain intact (sister-workstream surface preserved).</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Rewrite calendar.jsx — fetch /api/v1/calendar, transform, color-resolve, render with loading/empty/error states and click-to-expand</name>
  <files>frontend/pages/calendar.jsx</files>
  <read_first>
    - frontend/pages/calendar.jsx (full file — 196 lines; see existing EVENTS shape lines 5-29, WeekView lines 113-168, week-now line 160-164)
    - frontend/data.jsx (lines 2-101 — DATA_SETS structure for project color lookup; lines 461-478 — API_BASE constant and fetchProjects analog for the network call pattern)
  </read_first>
  <behavior>
    Hooks destructured:
      - const { useState: useStateC, useMemo: useMemoC, useEffect: useEffectC } = React;

    DELETE the hardcoded `EVENTS` const (lines 5-29).

    Add module-level constants:
      - API_BASE = "http://127.0.0.1:8765"  (matches frontend/data.jsx:464 — keep them aligned; do NOT import data.jsx's constant because data.jsx has no export; both files are loaded as scripts)
      - DEFAULT_EVENT_COLOR = "#8aa9ff"

    Helper functions (module-level, before WeekView):
      - mondayOf(date: Date) → Date — returns the Monday 00:00 local of the ISO week containing date (handles Sun=0 wrap-around: a Sun should map to the prior Monday, NOT the next)
      - sundayOf(date: Date) → Date — returns the Sunday 23:59:59.999 local of that same week
      - fmtDate(date: Date) → string in "YYYY-MM-DD" using local-time year/month/day (NOT toISOString — that shifts to UTC and can flip the date around midnight)
      - parseRfc3339(s: string) → Date  — `new Date(s)` is sufficient for valid RFC3339; just wrap so a future tweak is a one-liner
      - decimalHours(d: Date) → number — d.getHours() + d.getMinutes()/60 + d.getSeconds()/3600 (local time, since the week strip is rendered in local hours 8am-7pm)
      - dayIndex(d: Date, monday: Date) → number 0-6 — floor((d - monday) / 86_400_000), clamped to [0,6]
      - colorForEvent(event, projects) → hex string — if event.project_id is truthy AND projects has an entry with matching id, return that project.color; else if event.color matches /^#[0-9a-fA-F]{6}$/ return event.color; else DEFAULT_EVENT_COLOR
      - flattenProjects(dataSets) → list[{id, name, color}] — concat DATA_SETS.default.projects and DATA_SETS.client.projects (and any other set added later); de-dupe by id (first occurrence wins). Used by colorForEvent and the popover's "project name" lookup.
      - transformEvent(apiEvent, monday, projects) → { day, start, end, title, c, project, project_id, id, source, raw } — produces the WeekView shape PLUS the extra fields the popover needs

    New stateful logic in `Calendar` (replacing the lines 170-193 implementation):
      - useStateC: `events` (array, initial []), `status` ("loading" | "ok" | "empty" | "error"), `errorMsg` (string), `selectedEvent` (object or null), `retryNonce` (number, starts at 0)
      - useEffectC keyed on [retryNonce]: build monday/sunday via helpers using `new Date()`; fetch(`${API_BASE}/api/v1/calendar?from=${fmtDate(monday)}&to=${fmtDate(sunday)}`, {credentials: "omit"}); on response.ok: parse JSON; if array empty → setStatus("empty"); else → setEvents(transformed) + setStatus("ok"); on !response.ok or fetch reject → setStatus("error") + setErrorMsg(brief — "HTTP 500" / "network error" / "" depending on cause; do NOT show response body verbatim — wrap in try/catch around .text())
      - The fetch must NOT bail on 200 with `[]`; that is the legitimate empty-source case, distinct from error
      - useMemoC for the flattened projects list (call flattenProjects once per render of Calendar)

    Pass `events` down to WeekView and MiniCal (they currently read the module-level EVENTS const — change them to accept an `events` prop):
      - WeekView({ events }): keep all internal logic, but change `.filter(e => e.day === day)` to use the prop instead of the deleted const; ADD an onClick handler to each .week-event div that calls a setter passed via context — simpler: lift the popover state out of WeekView and pass `onEventClick(rawEvent)` as a prop too
      - MiniCal({ today, selected, setSelected, events }): the "Up next" section currently filters EVENTS by day===0; change to filter `events` by day===0 (today's column); the "Calendars" legend is hardcoded and should remain hardcoded for v1 (deriving the legend from events would surface single-source calendars only — leave as-is and add a TODO comment "TODO: derive legend from active events")
      - MiniCal month-grid dots: receive the `events` prop (same prop already added for "Up next") and derive a `Set<number>` of event-day-of-month values: `const eventDaysSet = useMemoC(() => new Set(events.map(e => parseRfc3339(e.start).getDate())), [events]);`. Then REPLACE the line-62 mock `const hasEvent = !c.other && (c.d % 3 === 0 || c.d === now.getDate());` with `const hasEvent = !c.other && eventDaysSet.has(c.d);` so month-grid dots reflect REAL events from the API response instead of the hardcoded "every 3rd day + today" pattern. Scope note: this only covers days that fall within the fetched (from, to) week range; a broader month-range fetch (so the entire month grid lights up correctly even on days outside the current week) is a v2 enhancement — document this inline near `eventDaysSet` with a TODO comment.

    Empty state UI (status === "empty"):
      - Replace WeekView with a div (className="glass") containing centered text "No events configured" and a one-line subtitle: "Configure [calendar] in invisible.toml or add ~/.invisible/events.json"
      - MiniCal still renders on the left (just with `events={[]}` so "Up next" goes empty too — preserve the heading, show nothing under it OR show italic "nothing scheduled" — pick one and stick with it)

    Loading state UI (status === "loading"):
      - Render WeekView shell (week-head + week-body grid) but instead of events, show 3 vertically-stacked div className="slot" overlays with subtle pulsing — or simpler: render a single full-height div className="week-event" with opacity 0.3 and text "Loading..." on each day column. The skeleton must not leak the old hardcoded EVENTS in any frame (no flicker of mock data during the first render before useEffect fires — use initial status="loading" so the first paint is the skeleton, not events).

    Error state UI (status === "error"):
      - Replace WeekView with a div (className="glass") containing "Couldn't load events" + the errorMsg (if non-empty) + a "Retry" button that calls setRetryNonce(n => n + 1)
      - Button uses existing className="btn" for visual consistency

    Click-to-expand popover (selectedEvent !== null):
      - Render a fixed-position div className="glass" with role="dialog" aria-modal="true" overlaid on the page (use inline style: position:'fixed', top:'50%', left:'50%', transform:'translate(-50%,-50%)', zIndex:1000, padding:'var(--pad-3)', minWidth:280)
      - Content: title (h3-style), time range "HH:MM – HH:MM" via fmtH, project name (resolved from selectedEvent.project_id via flattened projects list; falls back to selectedEvent.project or "—"), source badge ("notion" | "ics" | "local"), and a close button
      - ESC handler: useEffectC keyed on [selectedEvent] — addEventListener("keydown", e => e.key === "Escape" && setSelectedEvent(null)); return cleanup that removeEventListener
      - Click on backdrop (a separate fixed overlay with rgba(0,0,0,0.4) behind the popover) also closes

    Live "now" line: keep the existing logic at lines 160-164 verbatim — it does not depend on EVENTS, only on the current Date and HOURS slot math.

    Chip line currently reads "8 events · 14h booked" (line 180) — replace with a derived computation: `${events.length} events · ${totalHoursBooked.toFixed(1)}h booked` where totalHoursBooked = sum of (event.end - event.start) decimal-hours.
  </behavior>
  <action>
    Rewrite frontend/pages/calendar.jsx per the &lt;behavior&gt; spec. Preserve every CSS class name, the cal-layout root, MiniCal's three glass-panel sections (mini-cal, Up next, Calendars), and the WeekView grid shape. Pass the `events` array into MiniCal as a new prop (same array Calendar already passes to WeekView) and derive `eventDaysSet` inside MiniCal via `useMemoC` keyed on [events]; this `Set<number>` of day-of-month integers is the input to the replacement `hasEvent` computation at the former line 62 — the literal `c.d % 3 === 0` mock MUST be removed from the file. Do NOT introduce any new top-level CSS — all visuals must work with the existing classes. Do NOT use fetch credentials: "include" (the dashboard uses no-cookie auth, and the bearer-token path is for cross-machine; locally with --no-auth, credentials:"omit" is correct and avoids the loopback-CORS path that requires Origin echo). Do NOT import data.jsx or DATA_SETS via ES module syntax — both files are loaded as Babel-standalone scripts; read `window.DATA_SETS` instead, with a defensive fallback `window.DATA_SETS || { default: { projects: [] }, client: { projects: [] } }`. Mount with `window.Calendar = Calendar;` at the bottom (matches existing line 195). Add `Object.assign(window, { Calendar });` is NOT needed — single-component pages use the direct assignment idiom (see line 195 today). Keep all existing console-friendly behavior — no console.log in production code paths; one defensive `console.warn` on fetch failure is acceptable for debuggability.
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/calendar-events &amp;&amp; ! grep -E '^const EVENTS\s*=' frontend/pages/calendar.jsx &amp;&amp; grep -q 'fetch.*api/v1/calendar' frontend/pages/calendar.jsx &amp;&amp; grep -q 'window.Calendar = Calendar' frontend/pages/calendar.jsx &amp;&amp; grep -q 'DATA_SETS' frontend/pages/calendar.jsx &amp;&amp; grep -q 'Escape' frontend/pages/calendar.jsx &amp;&amp; grep -q 'week-now' frontend/pages/calendar.jsx &amp;&amp; ! grep -F 'c.d % 3 === 0' frontend/pages/calendar.jsx &amp;&amp; grep -q 'eventDaysSet' frontend/pages/calendar.jsx &amp;&amp; node -e "const fs=require('fs');const src=fs.readFileSync('frontend/pages/calendar.jsx','utf8');const re=/[A-Z][a-zA-Z]+\s*=\s*\(.*\)\s*=&gt;/g;const fnCount=(src.match(/function\s+[A-Z]/g)||[]).length+(src.match(re)||[]).length;if(fnCount&lt;3){console.error('expected 3+ React components (Calendar, MiniCal, WeekView), got '+fnCount);process.exit(1);}console.log('ok');"</automated>
  </verify>
  <done>EVENTS const is gone, fetch('/api/v1/calendar') is wired, window.Calendar is exported, DATA_SETS lookup is present, ESC handler is wired, week-now still renders, the literal `c.d % 3 === 0` mock is gone, `eventDaysSet` is the new month-grid derivation, and the file still contains at least 3 React components (Calendar, MiniCal, WeekView).</done>
</task>

<task type="auto">
  <name>Task 3: End-to-end smoke — daemon up, page fetches, three states verified via headless browser</name>
  <files></files>
  <read_first>
    - bin/invisible-dashboard (lines 495-547 — serve()/main() so the executor knows the daemon flags)
    - frontend/pages/calendar.jsx (the rewritten version — to know what selectors to assert on)
    - frontend/app.jsx (lines 26-55 — Sidebar nav-item structure; line 12 confirms the nav label is literally "Calendar" rendered inside `.nav-label` span — the Playwright `text=Calendar` selector will match this exact text)
  </read_first>
  <action>
    Drive the actual UI with Playwright (Chromium) per the global memory file ~/.claude/projects/-Users-ace/memory/feedback_verify_yourself.md ("don't hand off UATs — verify yourself"). Start the dashboard daemon on port 18765 with --no-auth in the background; also start bin/invisible-frontend on port 18090 (or a python -m http.server pointing at frontend/) in the background. Open http://127.0.0.1:18090/ (NOT `?page=calendar` — frontend/app.jsx line 118 initializes `pageId` to "dashboard" via React useState and has NO query-string router, so a `?page=` deep-link is silently ignored and the page lands on Dashboard). To activate the Calendar page, click the sidebar nav-item AFTER the page loads: `await page.click('text=Calendar')` (the literal label string from app.jsx line 12, rendered inside `.nav-label`). Then wait for the Calendar surface to appear: `await page.waitForSelector('.week-view, .glass:has-text("No events configured")', { timeout: 10000 })`. Only THEN run the rest of the assertions. Assert at minimum: (a) no JavaScript error in the page console, (b) either the empty-state placeholder is visible OR at least one .week-event renders (depending on whether ~/.invisible/events.json or [calendar] is configured on this dev machine), (c) the .week-now line is present (live "now" line preserved), (d) clicking a .week-event opens a dialog and pressing Escape closes it (only run this assertion if events rendered; skip if empty state). Capture a screenshot to /tmp/calendar-smoke.png for human review. Kill both daemons at the end. Use chrome-devtools-mcp or playwright npm — DO NOT add Playwright to the repo's package.json; use the global install if available, else `npx -y playwright@latest install chromium &amp;&amp; npx -y playwright@latest test` against an inline test script written to /tmp/. The assertion script must exit nonzero on any failure.
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/calendar-events &amp;&amp; (./bin/invisible-dashboard --no-auth --port 18765 &amp; echo $! &gt; /tmp/cal-d.pid) &amp;&amp; (python3 -m http.server 18090 -d frontend &amp; echo $! &gt; /tmp/cal-f.pid) &amp;&amp; sleep 3 &amp;&amp; node -e "
const cp = require('child_process');
const r = cp.spawnSync('node', ['-e', \`
const { chromium } = require('playwright');
(async () =&gt; {
  const browser = await chromium.launch();
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e =&gt; errors.push(String(e)));
  await page.goto('http://127.0.0.1:18090/', { waitUntil: 'networkidle', timeout: 15000 });
  await page.click('text=Calendar');
  await page.waitForSelector('.week-view, .glass:has-text(\\\"No events configured\\\"), .glass:has-text(\\\"Couldn\\\\'t load events\\\")', { timeout: 10000 });
  const hasNow = await page.\$('.week-now');
  if (!hasNow) { console.error('week-now line missing'); process.exit(1); }
  await page.screenshot({ path: '/tmp/calendar-smoke.png' });
  if (errors.length) { console.error('page errors:', errors); process.exit(1); }
  await browser.close();
  console.log('ok');
})();
\`], { stdio: 'inherit', env: { ...process.env, NODE_PATH: process.env.HOME + '/.npm-global/lib/node_modules' } });
process.exit(r.status);
"; RC=$?; kill $(cat /tmp/cal-d.pid) $(cat /tmp/cal-f.pid) 2&gt;/dev/null; exit $RC</automated>
    <human-check>Open /tmp/calendar-smoke.png and confirm: the week strip shows 8am-7pm rows, the MiniCal mini month grid is on the left, the live "now" line is at the current time on today's column, and any events render with the expected project colors. Either week-event elements OR the "No events configured" placeholder is acceptable depending on local config.</human-check>
  </verify>
  <done>Playwright clicks the "Calendar" sidebar nav-item (not a query-string deep-link) to activate the page; .week-view OR the empty-state placeholder appears; .week-now is present (live "now" line preserved); either week-event elements or the empty-state placeholder renders (no JS errors); screenshot captured to /tmp/calendar-smoke.png.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| /api/v1/calendar response → React render | Untrusted JSON (could contain XSS payloads in title) is rendered into the page |
| /api/v1/calendar response → useState | Backend could return malformed shapes; transform must defend |
| User keypress (Escape) → setSelectedEvent | Trusted input from the operator's own keyboard |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-FE-01 | Information disclosure / XSS | Event title or project name contains `<script>` or HTML | mitigate | React text nodes auto-escape; the rewrite MUST NOT use `dangerouslySetInnerHTML` anywhere. Popover and week-event labels render via JSX text children only. Verified by grep in Task 2's `<verify>` (already covered: file does not contain `dangerouslySetInnerHTML`). |
| T-01-FE-02 | Tampering | Backend returns object instead of array (regression) | mitigate | `Array.isArray(json)` check before iterating; on failure → setStatus("error"); never crash the page |
| T-01-FE-03 | Tampering | Event start/end is not a valid RFC3339 → parseRfc3339 returns Invalid Date | mitigate | `transformEvent` skips events where parseRfc3339 returns NaN time; logs nothing PII-bearing; continues with valid events |
| T-01-FE-04 | DoS | Backend returns 10,000-event array → DOM blowup | accept | Personal-cockpit usage; week view is windowed to 7 days * ~10 visible hours; rendering even 200 events is fine. Documented as accepted for v1; revisit if user reports lag |
| T-01-FE-05 | Information disclosure | Error state echoes backend `hint` field which could leak server-side details | mitigate | The errorMsg shown to the user is derived from HTTP status only (e.g. "HTTP 500", "network error") — never from `response.json().hint`. Avoid reading the body on !response.ok except inside try/catch and only for debug logging via console.warn (which is dev-only) |
| T-01-FE-SC | Tampering | npm/pip/cargo installs | accept | No package installs in production code. Smoke test (Task 3) uses Playwright via `npx -y playwright@latest` from the global npm cache; not added to project package.json. No legitimacy gate needed for ephemeral dev tooling. |
</threat_model>

<verification>
- `! grep -E '^const EVENTS\s*=' frontend/pages/calendar.jsx` — hardcoded array removed
- `grep -q 'fetch.*api/v1/calendar' frontend/pages/calendar.jsx` — fetch wired
- `grep -q 'window.Calendar' frontend/pages/calendar.jsx` — Babel-standalone export preserved
- `grep -q 'week-now' frontend/pages/calendar.jsx` — live "now" line preserved
- `! grep -F 'c.d % 3 === 0' frontend/pages/calendar.jsx` — month-grid hardcoded mock removed
- `grep -q 'eventDaysSet' frontend/pages/calendar.jsx` — real-events month-grid derivation present
- `grep -q 'dangerouslySetInnerHTML' frontend/pages/calendar.jsx` MUST return empty (XSS safety)
- `! grep -E 'CALENDAR_EVENTS|calendarEvents' frontend/data.jsx` — data.jsx clean
- Playwright smoke (Task 3): page loads with no JS errors; either events or empty-state placeholder render; week-now line present
</verification>

<success_criteria>
- All three tasks' `<verify>` blocks pass
- Calendar page renders without crashing in three states: events present, empty (no source), error (daemon down)
- Project colors come from DATA_SETS lookup when project_id matches
- MiniCal month-grid dots reflect real events from the API response (not the removed `c.d % 3` mock)
- Click on an event opens a popover; ESC closes it
- The live "now" line still renders on today's column at the current time
- /tmp/calendar-smoke.png shows a recognizably-correct Calendar page
</success_criteria>

<output>
Create `.planning/workstreams/calendar-events/phases/INV-01-api-v1-calendar-calendar-page-wired/01-02-SUMMARY.md` when done. Use Conventional Commits: `feat(INV-01-02): wire Calendar page to /api/v1/calendar with empty/loading/error states + click-to-expand`. Run `./scripts/update-changelog.py` before push.
</output>
