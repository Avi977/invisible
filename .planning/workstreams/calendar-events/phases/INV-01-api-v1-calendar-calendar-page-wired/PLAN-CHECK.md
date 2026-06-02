# Plan Check — Phase 01 (calendar-events)

**Checked:** 2026-06-01
**Verdict:** FLAG (executable with caveats; 2 fixes recommended before execute, 1 BLOCKER for SC3 month-grid coverage)

## Dimension Scores

| # | Dimension | Score | Note |
|---|-----------|-------|------|
| 1 | Goal coverage | **FLAG** | 7 of 8 SCs fully covered. SC3 says "month + week views" — plan wires events into WeekView and MiniCal's "Up next" list, but does NOT explicitly replace the mock `hasEvent = (c.d % 3 === 0 || c.d === now.getDate())` (calendar.jsx:62) that drives the month-grid event dots. Verdict downgrade to FLAG / borderline BLOCK depending on how strict "month view" reading is. |
| 2 | Frontmatter validity | PASS | 01-01 wave 1 deps=[], 01-02 wave 2 depends_on=["01-01"]. files_modified, autonomous, must_haves all present and consistent with the plan body. |
| 3 | Task completeness | PASS | Every `<task>` has files, action, verify, done; tdd tasks also have behavior. Task 5 (smoke) intentionally has empty `<files>` because it's an integration check, which matches the pattern. |
| 4 | Concrete actions | PASS | Actions name specific identifiers: `_safe_ics_url`, `_parse_ical`, `query_calendar_db`, `handle_calendar`, `API_V1_ROUTES[path](self)` line, `mondayOf`, `flattenProjects`, `colorForEvent`. No fenced code-block dumps, no copy-paste implementations. |
| 5 | Workstream isolation | PASS | files_modified in 01-01: `lib/api/calendar.py` (OWNS, new), `lib/api/__init__.py` (light), `bin/invisible-dashboard` (light, one-line `return` — verified the existing bug is real at line 365), `lib/notion.py` (additive only — only adds `query_calendar_db`, plan explicitly forbids mutating existing helpers), `invisible.toml.example` (light). 01-02: `frontend/pages/calendar.jsx` (OWNS), `frontend/data.jsx` (light, audit-and-no-op if CALENDAR_EVENTS absent — confirmed it IS absent so the file should remain untouched). No creep into sister-workstream files (chat.py, tree_*.py, pty_server.py, src-tauri/). |
| 6 | Security threat model | PASS | 01-01 STRIDE register covers all 4 baseline threats: SSRF (T-01-01 + T-01-02 with concrete `ipaddress.ip_address().is_private/is_loopback/is_link_local` + `socket.getaddrinfo AF_UNSPEC` checks AND a redirect-denying HTTPRedirectHandler subclass), path traversal (T-01-04 with `is_relative_to(config.home().resolve())`), info disclosure (T-01-05 with `type(exc).__name__` only + T-01-07 token redaction reuse), cache stampede (T-01-06 with module-level threading.Lock single-flight + documented tradeoff). 01-02 STRIDE covers XSS (T-01-FE-01 no dangerouslySetInnerHTML), shape tampering (T-01-FE-02 Array.isArray guard), info disclosure (T-01-FE-05 derive errorMsg from HTTP status only, never `hint`). Mitigations are concrete, not hand-wavy. |
| 7 | Goal-backward traceability | FLAG | must_haves.truths in 01-01 map cleanly to SC1, SC2, SC5, SC6, SC7, SC8. 01-02's truths cover SC3 (week strip) and SC4 (project color match). NO truth in either plan asserts month-grid event presence — this is the same gap as Dimension 1. |
| 8 | Executability | FLAG | 01-01: A fresh executor can do this without clarification — analog files are named, exact lines are quoted, the contract is fully specified. 01-02 Task 3 has a routing bug: Playwright navigates to `http://127.0.0.1:18090/?page=calendar`, but app.jsx (line 118) uses React state `pageId` initialized to "dashboard" with NO `?page=` URL-parsing. The Playwright check will land on the Dashboard page, not Calendar, and the `.week-event` / `.glass:has-text("No events configured")` selectors will not match. Smoke will either time out or silently pass on irrelevant DOM. |
| 9 | Dependency correctness | PASS | 01-02 depends_on: ["01-01"] is correct (frontend needs the endpoint). No circular references. Wave numbers (1 and 2) match dep depth. |
| 10 | No-source-configured path | PASS | 01-01 truth #3 + Task 2 behavior + Task 5 smoke all assert HTTP 200 with `[]` for unconfigured. 01-02 truth #4 + Task 2 status="empty" branch renders the "No events configured" placeholder. SC7 fully addressed on both sides. |
| 11 | Threat model — Notion DB id leakage | PASS | T-01-07 + the inline note in Task 1 ("NEVER print the database_id in error paths — Notion DB ids are mildly sensitive — they leak collaboration scope") shows the plan thought about a second-order info-disclosure vector beyond just the token. |
| 12 | Stdlib-only constraint (SC8) | PASS | 01-01 verification grep: `grep -q 'import icalendar\|from icalendar\|dateutil' lib/api/calendar.py` MUST return empty AND `grep -q 'icalendar\|python-dateutil' requirements.txt` MUST return empty. Belt + suspenders. Module-level imports list in `<action>` is explicit and stdlib-only. |

## Findings

### BLOCK findings (must fix before execution)

**B-1 — SC3 month-grid coverage is missing in Plan 01-02**
The phase goal says "month + week views" and the ROADMAP success criteria #3 says "The frontend renders them on the **month grid and week strip**" (emphasis mine). Plan 01-02 wires real events into:
- `WeekView` (week strip) — covered
- `MiniCal`'s "Up next" list (today's column) — covered

But it does NOT replace the mock `hasEvent` calculation in `MiniCal`'s month grid (current code at frontend/pages/calendar.jsx:62):

```javascript
const hasEvent = !c.other && (c.d % 3 === 0 || c.d === now.getDate());
```

This is hardcoded to dot every third day and today, regardless of real events. After execution, the month grid will still show fake event dots while the week strip shows real ones — a visible inconsistency that the goal explicitly forbids.

**Fix:** Add to Plan 01-02 Task 2 behavior:
> "MiniCal({ today, selected, setSelected, events }): replace the line-62 `hasEvent` mock with `const eventDaysSet = useMemoC(() => new Set(events.map(e => parseRfc3339(e.start).getDate())), [events]); const hasEvent = !c.other && eventDaysSet.has(c.d);` so the month-grid dots reflect real events. Note: this only covers the CURRENT month (events fetched are for the current week); a follow-up plan could fetch the full visible month range, but for v1 the dots correctly reflect events within the fetched range."

Also add to must_haves.truths: `"MiniCal's month-grid dots reflect days with real events from the API response (replacing the hardcoded c.d % 3 mock)"`.

### FLAG findings (recommend fix, not blocking)

**F-1 — Playwright route doesn't activate the Calendar page**
Plan 01-02 Task 3's Playwright command:
```
await page.goto('http://127.0.0.1:18090/?page=calendar', { waitUntil: 'networkidle', timeout: 15000 });
```

But `frontend/app.jsx:118` reads `const [pageId, setPageId] = useStateApp("dashboard");` with no URL-parsing useEffect. The `?page=calendar` query param is ignored and Playwright will land on the Dashboard page.

**Fix options (pick one):**
- (a) Add a Playwright step before the selector wait: `await page.click('text=Calendar');` (clicks the sidebar nav-item with label "Calendar") to activate the page.
- (b) Use page.evaluate to set state: `await page.evaluate(() => { document.querySelector('[class*="nav-item"]:nth-child(8)'); /* etc */ });` — fragile, prefer (a).
- (c) Document this as a known UX gap and add a tiny query-string handler in app.jsx during Plan 01-02 (additive, ~3 lines) so future smoke tests can deep-link. Out of scope for SC3, so prefer (a).

**F-2 — Plan 01-02 Task 2 does not specify that events flow through the existing project-color resolution when iCal source is used**
The plan's color resolver says: "if event.project_id matches → use DATA_SETS color; else event.color; else default". But iCal events have NO project_id from the backend (Notion can populate it from a "Project" relation; iCal cannot). This means iCal events will always fall through to event.color = "#8aa9ff" — SC4 ("Project colours match when project_id matches") is technically satisfied because there's no match to fail on, but the chip line "8 events · 14h booked" total computation will mix in untyped iCal events without project attribution. Low-impact for v1; flag for awareness, no edit required.

**F-3 — 01-01 Task 2 behavior says "ICS_MAX_BYTES = 1_048_576 (1 MiB)" but does not say what happens on a streamed read that exceeds the cap mid-response**
The action does cover it ("abort and return [] for THAT url"), but the behavior block only mentions the Content-Length pre-check. The two should agree. Trivial; the behavior reader (executor) might miss the streamed-read enforcement if they only read `<behavior>`. Tighten: add a behavior bullet "if streamed read exceeds ICS_MAX_BYTES mid-response → abort connection and treat URL as failed (return [] for it; continue other URLs)."

### PASS notes

- The `return` fix in `bin/invisible-dashboard` line 365 is a real bug. I confirmed it: control falls through into `if path == "/api/v1/tree/local":` and ultimately to `_send_text("not found\n", 404)` at line 407, which would call `send_response`/`end_headers`/`wfile.write` a second time after the handler. This would either crash the connection or interleave two HTTP responses on the same TCP stream. The fix is bounded, one-line, and fixes a latent bug for the existing `/api/v1/projects` route too (which is the same workstream's surface). Net positive scope creep — keep.
- 01-01 Task 1 (additive `query_calendar_db`) correctly preserves notion.py's existing API surface. The placement directive ("AFTER `query_recent_reviews` near line 320") matches the file structure I verified.
- 01-01 Task 4 (invisible.toml.example) correctly writes a TOML table (not array-of-tables) and the verify command parses it with `tomllib`/`tomli` — robust.
- 01-02 correctly identifies that `EVENTS` lives in calendar.jsx (lines 5-29), not data.jsx, and Task 1 correctly audits data.jsx for `CALENDAR_EVENTS` (I confirmed it is NOT present) → no-op outcome documented in `<done>`.
- Threat models in both plans cite specific Python primitives (ipaddress, socket.getaddrinfo with AF_UNSPEC, threading.Lock, Path.is_relative_to) rather than hand-wavy "validate URLs" language. ASVS L1 compliance is concrete.
- Loopback CORS handling (bin/invisible-dashboard line 289-296) means the frontend on :18090 calling :18765 works without credentials AND without origin-wildcard exposure. Plan 01-02's `credentials: "omit"` matches this posture.

## Recommended actions

1. **BLOCKER B-1 — fix month-grid event dots in Plan 01-02 Task 2**: add the `eventDaysSet` derivation and document the corresponding truth in must_haves. ~5 lines of additional behavior spec.
2. **FLAG F-1 — fix Playwright navigation in Plan 01-02 Task 3**: replace `goto('?page=calendar')` with `goto('/')` followed by a click on the Calendar sidebar nav item.
3. **FLAG F-3 — tighten 01-01 Task 2 behavior**: add the streamed-read enforcement bullet to mirror what `<action>` already requires.

After fixing B-1 (and ideally F-1), both plans are executable.

## Iteration 2 — Re-check after revision

**Re-checked:** 2026-06-01
**Iteration:** 2 of 3
**Scope:** B-1 (BLOCKER), F-1 (FLAG), F-3 (FLAG), regression sweep

### Re-check 1 — B-1 (BLOCKER): SC3 month-grid event coverage — **PASS**

All five sub-conditions satisfied in Plan 01-02:

- (a) `must_haves.truths` now contains line 24: `"MiniCal's month-grid dots reflect days that have real events from the API response (replacing the hardcoded `c.d % 3` mock)"` — the missing truth from iteration 1 is now present and maps directly to SC3.
- (b) Task 2 `<behavior>` lines 166–167 explicitly spec `MiniCal({ today, selected, setSelected, events })` receiving `events` as a new prop and the derivation `const eventDaysSet = useMemoC(() => new Set(events.map(e => parseRfc3339(e.start).getDate())), [events]);`, plus the explicit replacement `const hasEvent = !c.other && eventDaysSet.has(c.d);` for the former line-62 `c.d % 3 === 0` mock.
- (c) Task 2 `<action>` (line 191) names both the prop (`events`) and the memo identifier (`eventDaysSet`) concretely: "derive `eventDaysSet` inside MiniCal via `useMemoC` keyed on [events]; this `Set<number>` of day-of-month integers is the input to the replacement `hasEvent` computation at the former line 62 — the literal `c.d % 3 === 0` mock MUST be removed from the file."
- (d) Task 2 verify command (line 194) contains BOTH `! grep -F 'c.d % 3 === 0' frontend/pages/calendar.jsx` AND `grep -q 'eventDaysSet' frontend/pages/calendar.jsx` — verification is symmetric (removal + replacement both asserted).
- (e) Strategy is sound: `parseRfc3339(e.start).getDate()` returns the day-of-month (1–31), which is exactly the key space the month-grid cells use (`c.d` in cells comes from a 1..N day-of-month loop, verified against `frontend/pages/calendar.jsx:41-42`). The plan documents the scope limitation (events fetched are for the current week, so dots only appear within the visible week's days that fall in the current month) as a v2 enhancement with an inline TODO. Acceptable for v1 since SC3 says "reflect real events on the month grid" — not "reflect every event in the visible month range".

### Re-check 2 — F-1 (FLAG): Playwright navigation — **PASS**

All four sub-conditions satisfied in Plan 01-02 Task 3:

- (a) Verify snippet at line 221: `await page.goto('http://127.0.0.1:18090/', { waitUntil: 'networkidle', timeout: 15000 });` — bare `/`, no `?page=calendar` deep-link.
- (b) Followed at line 222 by: `await page.click('text=Calendar');` — clicks the sidebar nav-item.
- (c) Confirmed against `frontend/app.jsx`: line 12 has `{ id: "calendar", label: "Calendar", icon: "Calendar", ... }` and line 52 renders `<span className="nav-label">{p.label}</span>` — so the literal text node "Calendar" appears inside `.nav-label`. Playwright's `text=Calendar` selector matches text-containing elements; it will resolve to the `.nav-item` div whose `.nav-label` child has text "Calendar". The selector is valid. (Note: the string `"Calendar"` also appears as a prop value `icon: "Calendar"`, but that is not rendered text — it controls which `<I.Calendar size={18}/>` icon component renders at line 49, which has no text node.)
- (d) Line 223: `await page.waitForSelector('.week-view, .glass:has-text("No events configured"), .glass:has-text("Couldn\\'t load events")', { timeout: 10000 });` — waits on `.week-view` OR the empty-state placeholder OR the error-state placeholder before assertions run. The action prose at line 208 also explicitly documents the choice: "frontend/app.jsx line 118 initializes `pageId` to 'dashboard' via React useState and has NO query-string router, so a `?page=` deep-link is silently ignored and the page lands on Dashboard" — the planner's rationale is correctly captured.

### Re-check 3 — F-3 (FLAG): Streamed-read enforcement bullet — **PASS**

Both sub-conditions satisfied in Plan 01-01 Task 2 `<behavior>`:

- (a) Line 210 retains the pre-existing bullet: `"Read at most ICS_MAX_BYTES bytes; if Content-Length > cap or stream exceeds cap mid-read, abort and return []"`. Line 211 ADDS a new dedicated bullet: `"If the streamed body read exceeds \`ICS_MAX_BYTES\` mid-response (server lied about Content-Length or omitted it), abort that connection and treat the URL as failed — return \`[]\` for that URL but continue processing other configured URLs."` This explicitly addresses the iteration-1 gap (behavior/action mismatch) and names the threat motivation (server lying about Content-Length).
- (b) Consistent with `<action>` block at line 244 ("Use try/except around EVERY external call... NEVER print absolute paths or URLs to stderr...") and the per-URL failure model the action requires. The new behavior bullet promotes streamed-read overrun from an implementation detail buried inside the fetcher to an explicit failure mode listed alongside scheme rejection, redirect rejection, and timeout — symmetric coverage.

### Re-check 4 — Regression sweep — **PASS**

- (a) **Frontmatter validity**: 01-01 frontmatter (lines 1–57) parses cleanly: `phase`, `plan`, `type`, `wave: 1`, `depends_on: []`, `files_modified` (5 entries unchanged), `autonomous: true`, `requirements: []`, `tags`, `must_haves` (8 truths, 5 artifacts, 3 key_links). 01-02 frontmatter (lines 1–39) parses cleanly: `phase`, `plan`, `type`, `wave: 2`, `depends_on: ["01-01"]`, `files_modified` (2 entries unchanged), `autonomous: true`, `requirements: []`, `tags`, `must_haves` (9 truths — the new month-grid truth was inserted at position 9, 1 artifact, 2 key_links). The new truth is well-formed and grammatically consistent with the surrounding truths.
- (b) **`<threat_model>` blocks**: 01-01 lines 367–391 — 10 STRIDE entries intact (T-01-01 through T-01-09, T-01-SC). 01-02 lines 241–260 — 6 STRIDE entries intact (T-01-FE-01 through T-01-FE-05, T-01-FE-SC). No threats deleted; no fabricated additions.
- (c) **`files_modified` unchanged**: 01-01 still lists exactly `lib/api/calendar.py`, `lib/api/__init__.py`, `bin/invisible-dashboard`, `lib/notion.py`, `invisible.toml.example` (5 files). 01-02 still lists exactly `frontend/pages/calendar.jsx`, `frontend/data.jsx` (2 files). No file added, no file removed during the revision.
- (d) **Workstream isolation preserved**: 01-01 stays inside calendar surface + the documented shared-registry edits + the additive notion helper. 01-02 stays inside `frontend/pages/calendar.jsx` (OWNS) and audit-only of `frontend/data.jsx`. The MiniCal revision is confined to `frontend/pages/calendar.jsx` (the file the workstream already owns) — no creep into `frontend/data.jsx`, `frontend/app.jsx`, or any sister-workstream file (chat.py, tree_*.py, pty_server.py, tools.py, relations.py, src-tauri/, bin/invisible-pty).
- (e) **Dependency chain intact**: 01-02 `depends_on: ["01-01"]` and `wave: 2` unchanged. 01-01 `depends_on: []` and `wave: 1` unchanged. Wave depth matches dependency depth. No cycles introduced.

### Final verdict (iteration 2)

All 3 iteration-1 findings (1 BLOCKER, 2 FLAGS) are resolved with concrete, verifiable fixes. No regressions detected: frontmatter validity, threat models, files_modified, workstream isolation, and dependency chain are all preserved. The plans are executable as written.

**Verdict: PASS — proceed to execution.**
