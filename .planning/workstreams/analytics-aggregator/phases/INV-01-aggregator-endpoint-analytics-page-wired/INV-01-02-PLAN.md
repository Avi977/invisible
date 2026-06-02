---
phase: INV-01-aggregator-endpoint-analytics-page-wired
plan: 02
type: execute
wave: 2
depends_on:
  - INV-01-01
files_modified:
  - frontend/pages/analytics.jsx
  - frontend/data.jsx
autonomous: false
requirements:
  - REQ-05

must_haves:
  truths:
    - "Opening the Analytics page in the app fires a single GET /api/v1/analytics?range=30d on mount"
    - "Clicking the 7d / 14d / 30d range pills refetches /api/v1/analytics with the new range and re-renders the chart + tables"
    - "Clicking a project pill refetches with ?project=<slug> and the chart, totals, top tools, and top actions all update"
    - "All existing UI sections (stat strip, stacked area chart, by-project bars, time-by-project bars, most-used tools bars, top actions table) still render — none were deleted"
    - "Mock fields under the `// ── Analytics ─` section of frontend/data.jsx are removed; the page no longer references the global ANALYTICS object"
    - "Client refetches every 30 seconds via setInterval (matches PLAN-01's 30s cache TTL — NO SSE in this phase)"
    - "The setInterval is cleared on component unmount (no leaked timers)"
    - "Auth token is read from window.location.search ?token= (with optional window.__INVISIBLE_TOKEN__ fallback) and appended as ?token= on every analytics fetch — this is the pattern sibling workstreams will copy"
  artifacts:
    - path: "frontend/pages/analytics.jsx"
      provides: "Analytics page fetching real /api/v1/analytics data via inline getToken() helper"
      contains: "fetch"
    - path: "frontend/data.jsx"
      provides: "DATA_SETS / FOLDERS / TOOL_WORKFLOWS / TERM_CONTEXT unchanged; ANALYTICS section removed"
      contains: "// ── Analytics ─"
  key_links:
    - from: "frontend/pages/analytics.jsx"
      to: "GET /api/v1/analytics on the dashboard daemon (127.0.0.1:8765)"
      via: "fetch in useEffect with URL constructed via new URL() + URLSearchParams"
      pattern: "fetch.*api/v1/analytics"
    - from: "frontend/pages/analytics.jsx (range/project pill onClick)"
      to: "refetch /api/v1/analytics with updated query string"
      via: "useEffect dependency on [range, projFilter]"
      pattern: "useEffect.*\\[range.*projFilter|useEffect.*projFilter.*range"
    - from: "frontend/pages/analytics.jsx"
      to: "polling refresh loop"
      via: "setInterval / clearInterval inside useEffect cleanup"
      pattern: "setInterval|clearInterval"
    - from: "frontend/pages/analytics.jsx getToken()"
      to: "window.location.search (?token=) + window.__INVISIBLE_TOKEN__ fallback"
      via: "URLSearchParams(window.location.search).get('token')"
      pattern: "getToken|URLSearchParams.*window.location"
---

<objective>
Wire `frontend/pages/analytics.jsx` to consume `GET /api/v1/analytics` from PLAN-01. The page already renders every UI section correctly off the mock `ANALYTICS` object in `frontend/data.jsx`. This plan replaces the data source — every UI section must keep rendering, but now off live fetched data — and adds a 30-second polling loop so the chart updates without a manual reload.

Purpose: closes REQ-05's user-visible side. After this plan, opening the Analytics page in the app shows real token + time + tool numbers from the orchestrator's Notion review history, with live filters and live refresh.

Output: an edited `frontend/pages/analytics.jsx` that fetches on mount, refetches on filter change, polls every 30 seconds, and renders the same six sections (filter bar, stat strip, stacked area chart, three horizontal-bar cards, top-actions table) off the fetched payload. Mock `ANALYTICS` block in `frontend/data.jsx` is removed in-place (the rest of `data.jsx` — `DATA_SETS`, `FOLDERS`, `TOOL_WORKFLOWS`, `TERM_CONTEXT` — is untouched because sibling workstreams depend on those).

Polling-vs-SSE decision (sourced from PLAN-01): **30-second polling via `setInterval`**, matched to PLAN-01's 30-second in-process cache TTL. No SSE / EventSource code.

Auth strategy (PINNED by this plan — sibling workstreams should copy this pattern):

The React frontend is served from :8090 with permissive CORS; the dashboard daemon on :8765 accepts the bearer token from EITHER an `Authorization: Bearer` header OR a `?token=` query-string parameter (see `bin/invisible-dashboard` lines 219–236). The pywebview host in `bin/invisible-app` already opens the window with `?token=<t>` appended to the URL (see lines 87–99). The current React frontend has **zero** existing fetch calls and **zero** existing token wiring — this phase is the first integration. We therefore pin the pattern here for all future workstreams to follow:

- Inline a tiny `getToken()` helper at the top of `frontend/pages/analytics.jsx`.
- `getToken()` reads `window.location.search`'s `?token=` first, then falls back to `window.__INVISIBLE_TOKEN__` (a global that a future host shell may inject — pywebview / Tauri / etc.).
- Append the token to the fetch URL as `?token=<t>`. Do NOT use the `Authorization` header — it would require setting a request header, and while CORS is currently permissive, the query-string form is the simpler primitive that survives a future CORS tightening AND matches the pywebview URL convention already in use.
- In `--no-auth` dev mode (loopback only), `getToken()` returns `''`; the daemon accepts the unauthed request because `server.no_auth=True`. Same code path, no branching.

Project-id values from the backend are SLUGS (PLAN-01 Task 2 resolves Notion UUIDs to slugs server-side), so the existing `PROJECT_ORDER` filter in the page works without changes. The page no longer needs to defensively handle UUID-shaped pids.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/REQUIREMENTS.md
@.planning/workstreams/analytics-aggregator/ROADMAP.md
@START_HERE.md
@.planning/workstreams/analytics-aggregator/phases/INV-01-aggregator-endpoint-analytics-page-wired/INV-01-01-PLAN.md
@frontend/pages/analytics.jsx
@frontend/data.jsx

<interfaces>
<!-- Endpoint contract (delivered by PLAN-01). Mirror these field names exactly. -->

GET /api/v1/analytics?range={7|14|30}d&project={slug}? — JSON response shape:

  {
    "totals": {
      "input_tokens": int,
      "output_tokens": int,
      "cache_read_tokens": int,
      "cost_usd": float,
      "total_minutes": float
    },
    "by_project": {
      "<slug>": {
        "input_tokens": int,
        "output_tokens": int,
        "cost_usd": float,
        "minutes": float
      },
      ...
    },
    "top_tools": [
      { "name": str, "calls": int, "total_tokens": int, "color": str },
      ...   // sorted desc by total_tokens
    ],
    "top_actions": [
      { "name": str, "tool": str, "calls": int, "tokens": int },
      ...   // top 8, sorted desc by tokens
    ],
    "series": {
      "tokensByDay": { "<slug>": [float, float, ..., float] },   // length == range_days, oldest first
      "timeByDay":   { "<slug>": [float, float, ..., float] }    // hours per day, oldest first
    }
  }

  Error shapes:
    400 -> { "error": "invalid range, must be 7d|14d|30d" }
    500 -> { "error": "internal", "message": "<str>" }
    401 -> plain text "unauthorized\n" from the daemon (auth gate)

Auth (PINNED — see objective preamble): inline `getToken()` reading
`?token=` from `window.location.search`, falling back to
`window.__INVISIBLE_TOKEN__`. Append as `?token=` on the fetch URL via
`URLSearchParams.set('token', tok)`. No `Authorization` header. Works in dev
(--no-auth on 127.0.0.1, getToken returns '', daemon ignores) and packaged
(pywebview injects ?token= into window URL, getToken picks it up). This is
the canonical pattern for the codebase — sibling workstreams will copy it.

From frontend/pages/analytics.jsx current state — fields the existing render
code consumes (these are the contracts your fetched payload must satisfy):

  // Stat strip
  fmtK(totalTokensK * 1000)   <- totals.input_tokens + totals.output_tokens (then /1000 since UI multiplies *1000 back)
  fmtH(totalHours)             <- totals.total_minutes / 60
  tokenDelta                    <- comparison to previous-window data (computed locally from the series)

  // StackedAreaChart receives:
  data       = { <slug>: number[] }     <- series.tokensByDay[slug] (or timeByDay for mode=time)
  range      = days                     <- the active range
  projects   = visibleProjects          <- PROJECT_ORDER intersected with by_project keys
  projectMap = projectMap               <- from props.projects (which comes from DATA_SETS — unchanged)
  mode       = "tokens" | "time"

  // HorizontalBars items shape: [{ id, label, value, color }]
  // ActionsTable rows shape:   [{ name, tool, calls, tokens }]
  // toolAgg uses the t.name / t.color / t.tokens fields the current code already expects

  PROJECT_ORDER at line 6: ["echo", "lumen", "drift", "atlas", "rune", "ferry"]
  projectMap is built from `projects` prop (passed by parent — these come from
  DATA_SETS, owned by sibling workstreams, MUST NOT TOUCH). Since PLAN-01 Task 2
  resolves project ids to slugs server-side, `by_project` and `series` keys are
  already slugs that line up with PROJECT_ORDER. No client-side UUID handling
  required. If an unknown slug (e.g. a project not in PROJECT_ORDER) appears
  in `by_project`, the existing `PROJECT_ORDER.filter(pid => projectMap[pid])`
  drops it naturally.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Replace mock-driven data with fetched data + 30s polling + inline getToken() in analytics.jsx</name>
  <files>frontend/pages/analytics.jsx</files>
  <read_first>
    - frontend/pages/analytics.jsx (whole file — note useState hooks at line 200-202, the data slicing block at lines 211-246, and the JSX render block at lines 248-360 you must keep intact)
    - frontend/data.jsx lines 360-460 (the mock shape, for field-name parity)
    - .planning/workstreams/analytics-aggregator/phases/INV-01-aggregator-endpoint-analytics-page-wired/INV-01-01-PLAN.md (interfaces block — the endpoint response contract you're consuming, plus the by_project-keys-are-slugs guarantee)
    - bin/invisible-dashboard lines 219-237 (auth: bearer token in Authorization header OR ?token= query string — we use ?token= here)
    - bin/invisible-app lines 87-99 (confirms pywebview opens the window with ?token= in the URL, so window.location.search contains it at runtime)
  </read_first>
  <action>
    Edit `frontend/pages/analytics.jsx` in place. Preserve every JSX section (filter bar, stat strip, charts grid, all four HorizontalBars instances, ActionsTable). Preserve every helper (`fmtK`, `fmtH`, `sum`, `lastN`, `StatCard`, `StackedAreaChart`, `HorizontalBars`, `ActionsTable`). Change only the data plumbing.

    1. **Inline a getToken() helper** at the top of the file (just below the imports / above the `PROJECT_ORDER` constant). Exact shape:

       ```
       function getToken() {
         try {
           const fromUrl = new URLSearchParams(window.location.search).get('token');
           if (fromUrl) return fromUrl;
         } catch (_) { /* SSR / non-browser: ignore */ }
         return (typeof window !== 'undefined' && window.__INVISIBLE_TOKEN__) || '';
       }
       ```

       This is the canonical pattern future workstreams will copy — keep the implementation identical so siblings can grep-and-paste.

    2. **Add data + error state.** Inside the Analytics function (around line 200, next to the existing useStateA calls), add:

       ```
       const [data, setData] = useStateA(null);
       const [err, setErr]   = useStateA(null);
       ```

    3. **Add the fetch useEffect.** Place it after the existing useStateA hooks. The effect builds the URL with `new URL()` + `URLSearchParams.set()` so we never hand-concat query strings (avoids encoding bugs). Pseudocode (write actual JSX/JS in the file):

       ```
       useEffectA(() => {
         let alive = true;
         const refetch = () => {
           const u = new URL('http://127.0.0.1:8765/api/v1/analytics');
           u.searchParams.set('range', `${range}d`);
           if (projFilter && projFilter !== 'all') u.searchParams.set('project', projFilter);
           const tok = getToken();
           if (tok) u.searchParams.set('token', tok);
           fetch(u.toString())
             .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
             .then(json => { if (alive) { setData(json); setErr(null); } })
             .catch(e => { if (alive) setErr(String(e.message || e)); });
         };
         refetch();
         const id = setInterval(refetch, 30000);
         return () => { alive = false; clearInterval(id); };
       }, [range, projFilter]);
       ```

       Notes:
       - `useEffectA` / `useStateA` are the existing aliases in this codebase — use whatever the rest of analytics.jsx already uses (grep the file for `useEffect` / `useState` to confirm the import alias).
       - Dependency array MUST be exactly `[range, projFilter]` so the effect re-runs (and the interval is rebuilt) when either filter changes — this also triggers the immediate refetch on filter change.
       - The `alive` flag prevents `setData` after unmount or after a rapid filter change.
       - Use `http://127.0.0.1:8765` literally — this is a loopback-only desktop app, not a webapp behind a domain.

    4. **Replace the mock-driven slicing at lines 211-246 with derivations from `data`.** While `data === null` (initial mount, pre-first-response), render a low-key loading placeholder:

       ```
       if (!data) {
         return <div className="anlt" style={{padding: 24, opacity: 0.6}}>Loading analytics…</div>;
       }
       ```

       Once `data` exists, derive:
       - `totalTokensK = (data.totals.input_tokens + data.totals.output_tokens) / 1000`
       - `totalHours = data.totals.total_minutes / 60`
       - `avgPerDay = Math.round((totalTokensK * 1000) / range)`
       - `tokenDelta`: compute from first-half vs second-half sums of `series.tokensByDay` summed across `visibleProjects`. If both halves are zero, render `—` instead of a number; otherwise render `((second - first) / first) * 100` as a percentage. Implement inline.
       - `tokenData = data.series.tokensByDay` (already correct shape + length)
       - `timeData = data.series.timeByDay`
       - `projTotals = activeProjects.map(pid => ({ pid, tokens: (data.by_project[pid]?.input_tokens || 0) + (data.by_project[pid]?.output_tokens || 0), time: (data.by_project[pid]?.minutes || 0) / 60 }))`
       - `toolAgg = data.top_tools.map(t => ({ id: t.name, label: t.name, value: t.total_tokens, color: t.color })).slice(0, 6)`
       - `actionRows = data.top_actions` (fields already match `{name, tool, calls, tokens}`)

       For `activeProjects`: keep `PROJECT_ORDER.filter(pid => projectMap[pid] && data.by_project[pid])`. Unknown slugs from the backend drop out naturally.

    5. **Error indicator.** Render a small red dot somewhere in the filter bar when `err` is non-null. Keep showing the previous `data` underneath — do NOT replace the whole UI with an error screen. Example: `{err && <span title={err} style={{color: '#ff6b6b', marginLeft: 8}}>●</span>}`.

    6. **No SSE / EventSource / WebSocket.** The 30-second `setInterval` is the only refresh mechanism. The polling matches PLAN-01's 30s cache TTL.

    DO NOT touch the `StackedAreaChart`, `HorizontalBars`, `ActionsTable`, or `StatCard` components (they're already correct). DO NOT modify the JSX render tree's structure — only swap the data variables those components read from. DO NOT change `PROJECT_ORDER` (line 6) — that's the project-slug allowlist the UI presents. DO NOT reference the global `ANALYTICS` object — it will be removed in Task 2.
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/analytics-aggregator && grep -qE "fetch\(['\"\`][^'\"\`]*\/api\/v1\/analytics" frontend/pages/analytics.jsx && grep -qE "setInterval\(" frontend/pages/analytics.jsx && grep -qE "clearInterval\(" frontend/pages/analytics.jsx && grep -qE "getToken|URLSearchParams\(window\.location\.search\)" frontend/pages/analytics.jsx && grep -qE "\[\s*range\s*,\s*projFilter\s*\]|\[\s*projFilter\s*,\s*range\s*\]" frontend/pages/analytics.jsx && ! grep -v '^\s*//' frontend/pages/analytics.jsx | grep -v '^\s*\*' | grep -qE '\bANALYTICS\.' && echo OK</automated>
  </verify>
  <done>
    `frontend/pages/analytics.jsx` defines an inline `getToken()` helper that reads `?token=` from `window.location.search` with a `window.__INVISIBLE_TOKEN__` fallback. It fetches `http://127.0.0.1:8765/api/v1/analytics` in a useEffect keyed to `[range, projFilter]`, builds the URL with `new URL()` + `URLSearchParams.set()`, appends `range`, optional `project`, and `token` (when present), sets up a 30-second `setInterval` polling loop with `clearInterval` cleanup + an `alive` guard, and renders all six existing UI sections off the fetched payload. The file no longer references the `ANALYTICS` global anywhere outside comments. A loading placeholder shows on first mount. Transient fetch errors set `err`, render a small red dot in the filter bar, and leave previous data on screen. The grep-based verification passes.
  </done>
</task>

<task type="auto">
  <name>Task 2: Remove the mock ANALYTICS block from data.jsx (in-place, no other sections touched)</name>
  <files>frontend/data.jsx</files>
  <read_first>
    - frontend/data.jsx (whole file — confirm the ANALYTICS object lives at lines 363-458 between the `// ── Analytics ─` banner at line 360 and the `Object.assign` blocks at lines 460-461; understand that `DATA_SETS`, `FOLDERS`, `TOOL_WORKFLOWS`, `TERM_CONTEXT` are sibling-workstream territory and MUST NOT be modified)
    - frontend/pages/analytics.jsx (post-Task-1 — confirm it no longer references `ANALYTICS`)
    - Grep the rest of the frontend for any other `ANALYTICS` reference before deleting: `grep -rn "\\bANALYTICS\\b" frontend/`
  </read_first>
  <action>
    If the grep in `read_first` shows the only `ANALYTICS` reference is inside `frontend/data.jsx` and `frontend/pages/analytics.jsx` (post-Task-1, the latter should be gone or comment-only), proceed. If any other file references `ANALYTICS`, STOP and report — that's a sibling-workstream coupling that needs investigation.

    Edit `frontend/data.jsx`:

    1. Replace the entire `const ANALYTICS = { ... };` block (lines 363-458) with a brief comment marker:
       ```
       // ANALYTICS mock removed in INV-01 (REQ-05) — Analytics page now fetches
       // GET /api/v1/analytics from the dashboard daemon. See
       // lib/api/analytics.py and frontend/pages/analytics.jsx.
       ```
       Keep the `// ── Analytics ─` banner at line 360 so the section's spot is documented.

    2. Edit line 460 `Object.assign(window, { ANALYTICS });` to remove the `ANALYTICS` key. Prefer outright deletion of that line — Task 1 already established that nothing else reads `ANALYTICS`.

    3. DO NOT touch line 461 `Object.assign(window, { DATA_SETS, FOLDERS, TOOL_WORKFLOWS, TERM_CONTEXT });`. DO NOT touch the `DATA_SETS` object (lines 1-358). DO NOT touch `FOLDERS`, `TOOL_WORKFLOWS`, `TERM_CONTEXT` (any blocks before the ANALYTICS section). Sibling workstreams depend on these.

    4. After the edit, re-grep to confirm zero `ANALYTICS\\.` accesses remain in non-comment lines of `frontend/`.
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/analytics-aggregator && bash -c '
      # No ANALYTICS.* accesses on non-comment lines anywhere in frontend/
      bad=$(grep -rn "ANALYTICS\." frontend/ 2>/dev/null | grep -v "^[^:]*:[0-9]*:\s*//" | grep -v "^[^:]*:[0-9]*:\s*\*" || true)
      if [ -n "$bad" ]; then echo "FAIL: ANALYTICS.* still referenced in non-comment code:"; echo "$bad"; exit 1; fi
      # ANALYTICS is no longer declared
      if grep -qE "^\s*const\s+ANALYTICS\s*=" frontend/data.jsx; then echo "FAIL: const ANALYTICS still declared in data.jsx"; exit 1; fi
      # Sibling Object.assign line is intact
      grep -q "DATA_SETS, FOLDERS, TOOL_WORKFLOWS, TERM_CONTEXT" frontend/data.jsx || { echo "FAIL: sibling Object.assign line was modified"; exit 1; }
      echo OK
    '</automated>
  </verify>
  <done>
    `frontend/data.jsx` no longer defines `ANALYTICS`. The `// ── Analytics ─` banner remains with a one-line comment noting where the data now comes from. The sibling-workstream-owned objects (`DATA_SETS`, `FOLDERS`, `TOOL_WORKFLOWS`, `TERM_CONTEXT`) and their `Object.assign(window, {...})` line are byte-identical to before. No file in `frontend/` reads `ANALYTICS.*` on a non-comment line.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Human verification — Analytics page shows real data, filters work, polling refreshes</name>
  <what-built>
    The Analytics page now fetches from `GET /api/v1/analytics` on mount (with `?token=` from the URL), refetches on range/project filter change, and polls every 30 seconds. Mock data is gone from `data.jsx`. PLAN-01's backend endpoint is wired to the route.
  </what-built>
  <how-to-verify>
    Prerequisites (must already be running):
    - `bin/invisible-dashboard` on http://127.0.0.1:8765 (started from this worktree)
    - `bin/invisible-frontend` on http://127.0.0.1:8090 (serves the React pages)
    - `INVISIBLE_DASHBOARD_TOKEN`, `NOTION_TOKEN`, `NOTION_DB_REVIEWS` exported in env
    - At least a handful of Notion review rows in the Reviews DB (run the orchestrator once or two if the DB is empty — review rows from `log_review` accumulate naturally)
    - The frontend URL must be opened with `?token=$INVISIBLE_DASHBOARD_TOKEN` in the query string. The pywebview app (`bin/invisible-app`) does this automatically. If you're testing in a plain browser, open `http://127.0.0.1:8090/?token=<paste-token>` manually.

    Steps:
    1. Open the desktop app (`invisible-app`) OR navigate to `http://127.0.0.1:8090/?token=$INVISIBLE_DASHBOARD_TOKEN` in a browser, then navigate to the Analytics page.
    2. Confirm the page renders — stat strip, stacked area chart, three horizontal-bar cards, top-actions table. The "Loading analytics…" placeholder may flash briefly on first paint; that's expected.
    3. Observe initial values. They should look like real numbers (small integers, not the mock six-figure totals).
    4. Click `7d`. The chart and totals must change. Click `14d`, then `30d`. The numbers must change each time. The chart's day-count must match the selected range (7, 14, or 30 days of x-axis).
    5. Click an individual project pill (e.g. `Echo`). The chart should reduce to a single layer; totals should drop; top-tools and top-actions should reflect only that project's reviews.
    6. Click `All projects`. Multi-layer chart and aggregate totals return.
    7. Open browser DevTools → Network tab. Filter for `analytics`. Watch for a fresh request every ~30 seconds while the page stays open. The request URL must include the active `range`, (if filtered) `project`, AND `token` query params.
    8. Open DevTools → Console. There must be NO uncaught errors (warnings about React 18 Babel-standalone strict-mode quirks are fine).
    9. Sibling-page sanity (no regressions): navigate to Dashboard, Folders, Terminals, AI bubble pages. They must render identically to before — your changes must not have affected them.

    Verify behavior list:
    - [ ] Analytics page renders with all six UI sections present
    - [ ] Range pills (7d/14d/30d) change the chart, stat strip, and table
    - [ ] Project pills filter the data
    - [ ] Network tab shows a fetch every ~30 seconds with `?token=` present
    - [ ] No console errors
    - [ ] Sibling pages (Dashboard / Folders / Terminals / AI bubble) still work
  </how-to-verify>
  <resume-signal>Type "approved" to ship, OR describe what's broken (range pill not working, numbers wrong, console error, sibling page regression, etc.) for a fix pass.</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser → daemon (127.0.0.1:8765) | Frontend now makes a new GET to the dashboard daemon for analytics. Same trust boundary as the existing pages will use; no new boundary introduced. |
| user input → fetch URL | The `range` and `project` values come from in-page React state (constrained by which pills are clickable), not from URL params or external input. Token comes from window.location.search. |
| polling loop → daemon | A new periodic outbound request every 30s while the Analytics page is mounted. |
| token in URL query string | Token is appended as `?token=` per the pinned auth strategy. On loopback only — never transits a network in normal usage. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-INV-01-06 | Tampering | `range` value in fetched URL | mitigate | `range` is sourced from React state constrained to {7, 14, 30} by the existing pills onClick handlers. The backend (PLAN-01) re-validates via `RANGE_DAYS_ALLOWED` and returns 400 if it ever sees an out-of-set value. Two layers, both enforced. |
| T-INV-01-07 | Tampering | `project` slug value | mitigate | Sourced from pills wired to `PROJECT_ORDER` slugs or `"all"`. Backend reverse-maps slug → UUID via `_build_slug_map`; unknown slugs map to None → empty filter, not error. No SQLi surface (Notion JSON filter). |
| T-INV-01-08 | DoS | Polling storm if user opens many Analytics tabs / leaves it open for days | mitigate | 30-second polling matches PLAN-01's 30-second in-process cache. Most polls hit cache and return in <10ms. Cleanup via `clearInterval` on unmount + `alive` flag prevents leaked timers and stale `setData` after navigating away. |
| T-INV-01-09 | Information disclosure | Bearer token in URL query string | accept | Loopback-only single-user desktop app. The token lands in `window.location.search` only (no `document.referrer` leak across origins since fetches are same-host loopback). DevTools / browser history exposes the token to the user themselves, which is fine — they own it. The query-string form is the canonical pattern for this codebase (matches pywebview's URL convention and the daemon's `_token_from_request` fallback). |
| T-INV-01-10 | Information disclosure | Error response leaking internal details | mitigate | PLAN-01's `handle_request` returns `{"error": "internal", "message": str(e)}` on 500. The frontend renders only a small error indicator — it does NOT surface `message` to the user UI. The body is still visible in DevTools but that's an accepted local-only exposure on a single-user app. |
| T-INV-01-11 | Repudiation | Logging of analytics fetches | accept | No new server-side logging added by this plan. The daemon's existing `log_message` is suppressed (line 216 of bin/invisible-dashboard). Single-user app; no audit trail required. |
| T-INV-01-SC | Tampering | npm/pip/cargo installs | mitigate | N/A — this plan adds ZERO new dependencies. Pure edits to two existing files using React 18 hooks already in use elsewhere in the codebase (`useState`, `useEffect`, `useMemo`). |
</threat_model>

<verification>
Static verification (no daemon required):

```bash
# Analytics page fetches the new endpoint
grep -qE "fetch\(['\"\\\`][^'\"\\\`]*/api/v1/analytics" frontend/pages/analytics.jsx && echo OK || echo FAIL

# Polling primitives present
grep -qE "setInterval\(" frontend/pages/analytics.jsx && echo OK || echo FAIL
grep -qE "clearInterval\(" frontend/pages/analytics.jsx && echo OK || echo FAIL

# Inline getToken helper
grep -qE "getToken|URLSearchParams\(window\.location\.search\)" frontend/pages/analytics.jsx && echo OK || echo FAIL

# useEffect deps cover both filters
grep -qE "\[\s*range\s*,\s*projFilter\s*\]|\[\s*projFilter\s*,\s*range\s*\]" frontend/pages/analytics.jsx && echo OK || echo FAIL

# Analytics page no longer reads from the ANALYTICS global on non-comment lines
if grep -v '^\s*//' frontend/pages/analytics.jsx | grep -v '^\s*\*' | grep -qE '\bANALYTICS\.'; then
  echo "FAIL: still references ANALYTICS on a non-comment line"
else
  echo OK
fi

# data.jsx no longer defines ANALYTICS
if grep -qE "^\s*const\s+ANALYTICS\s*=" frontend/data.jsx; then echo "FAIL: ANALYTICS still defined"; else echo OK; fi

# Sibling-owned globals are intact in data.jsx
grep -q "DATA_SETS, FOLDERS, TOOL_WORKFLOWS, TERM_CONTEXT" frontend/data.jsx && echo OK || echo FAIL

# Scope-fence diff check — these MUST be unchanged by this plan
git diff --name-only HEAD~1 -- \
  frontend/pages/dashboard.jsx \
  frontend/pages/folders.jsx \
  frontend/pages/terminals.jsx \
  frontend/ai-chat.jsx \
  lib/api/projects.py \
  lib/api/chat.py \
  bin/invisible-pty \
  lib/pty_server.py
# expect: empty
```

Live verification (covered in Task 3 checkpoint above):

```bash
# Endpoint reachable + JSON shape (header form works for curl)
curl -s "http://127.0.0.1:8765/api/v1/analytics?range=30d" \
  -H "Authorization: Bearer $INVISIBLE_DASHBOARD_TOKEN" \
  | python3 -m json.tool | head -40

# Token-in-querystring form (the form the frontend uses)
curl -s "http://127.0.0.1:8765/api/v1/analytics?range=7d&project=echo&token=$INVISIBLE_DASHBOARD_TOKEN" \
  | python3 -m json.tool | head -40

# In the running app at http://127.0.0.1:8090/?token=$INVISIBLE_DASHBOARD_TOKEN:
# - Analytics page loads, shows real numbers (not mock six-figure values)
# - Range pills change the chart + totals
# - Project pills filter
# - Network tab shows a /api/v1/analytics?...&token=... request every ~30s
# - Console clean
```
</verification>

<success_criteria>
- `frontend/pages/analytics.jsx` fetches `GET /api/v1/analytics?range=<N>d&project=<slug>?&token=<t>?` on mount and on every change to `range` or `projFilter`.
- The page polls every 30 seconds via `setInterval` (matched to PLAN-01's 30s cache).
- `setInterval` is cleared on unmount (verified by code grep for `clearInterval` inside the useEffect cleanup return).
- Inline `getToken()` helper reads `?token=` from `window.location.search` with a `window.__INVISIBLE_TOKEN__` fallback. URL is built with `new URL()` + `URLSearchParams.set()`.
- All six UI sections (filter bar, stat strip, stacked area chart, three horizontal-bar cards, top-actions table) still render — none deleted.
- The page no longer references the `ANALYTICS` global from `data.jsx` on any non-comment line.
- `frontend/data.jsx`'s `ANALYTICS` object is removed; the section-banner comment remains; `DATA_SETS`, `FOLDERS`, `TOOL_WORKFLOWS`, `TERM_CONTEXT` and their `Object.assign(window, ...)` line are byte-identical to before.
- Transient fetch failures leave previous data on screen with a small red error dot — no whole-page blanking.
- Loading state shows on first mount before the first response.
- Human-verify checkpoint approved: range pills, project pills, and 30s polling are visibly working in the live app with `?token=` in the request URL.
- Scope fences honored: NO changes to `frontend/pages/{dashboard,folders,terminals}.jsx`, `frontend/ai-chat.jsx`, `lib/api/projects.py`, `lib/api/chat.py`, `lib/api/tree_*`, `bin/invisible-pty`, `lib/pty_server.py`, `src-tauri/`, or `frontend-vite/`.
- No SSE / EventSource / WebSocket code introduced in this phase (polling-vs-SSE decision committed to polling).
</success_criteria>

<output>
Create `.planning/workstreams/analytics-aggregator/phases/INV-01-aggregator-endpoint-analytics-page-wired/INV-01-02-SUMMARY.md` when done.
</output>
