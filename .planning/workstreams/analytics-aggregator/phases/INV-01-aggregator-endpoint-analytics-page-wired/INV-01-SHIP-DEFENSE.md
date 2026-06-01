# Ship Defense — Phase INV-01 / analytics-aggregator

> **Purpose.** Reviewer-facing argument for every change in this branch. For each item: what it does, why it exists, and whether it's **MUST-HAVE**, **RECOMMENDED**, **OPTIONAL**, or **REMOVABLE** if the PR fails review.
>
> **Branch:** `ws/analytics-aggregator` · 9 commits · 15 files · +1849 / −201 lines (of which ~1240 are planning docs and ~600 are code/test scaffolding)
>
> **Goal:** REQ-05 — Analytics page renders real token spend + time + tool usage from Notion review history.

---

## Quick verdict table

| # | Change | Verdict | Removable? |
|---|---|---|---|
| 1 | Notion DB schema: 7 new properties (user-side) | **MUST-HAVE** | No — code depends on these property names exactly |
| 2 | `lib/api/__init__.py` | **MUST-HAVE** | No — Python needs it to import the submodule |
| 3 | `lib/api/analytics.py` (the aggregator) | **MUST-HAVE** | No — this IS the feature |
| 4 | `lib/notion.py` — extended `log_review` (3 kwargs) | **MUST-HAVE** | No — without it no review row carries token data |
| 5 | `lib/notion.py` — `query_reviews_since` helper | **MUST-HAVE** | Partially — could reuse `query_recent_reviews` with a manual since-filter at minor cost |
| 6 | `lib/orchestrator.py` — capture per-agent timestamps + pass to log_review | **MUST-HAVE** | No — without it `Started/Completed` are never written |
| 7 | `bin/invisible-dashboard` — register `/api/v1/analytics` route | **MUST-HAVE** | No — endpoint can't be reached without this |
| 8 | `bin/invisible-dashboard` — CORS fix on `_send_json` / `_send_text` | **MUST-HAVE** | No — browser blocks the cross-origin fetch without it (we verified this live) |
| 9 | `frontend/pages/analytics.jsx` — fetch + 30s polling + getToken | **MUST-HAVE** | No — without it the page still shows mock data |
| 10 | `frontend/data.jsx` — remove ANALYTICS mock | **RECOMMENDED** | Yes — could leave the const in place if reviewer prefers a soft cutover; analytics.jsx no longer references it either way |
| 11 | The 7 planning docs in `.planning/` | **OPTIONAL** | Yes — strip from PR if reviewer wants a code-only diff. They're project history, not runtime code |
| 12 | `.planning/STATE.md` + `ROADMAP.md` updates | **OPTIONAL** | Yes — same as above (project tracking, not feature) |
| 13 | Decision: 30s polling (no SSE) | **MUST-HAVE** (as chosen) | Swappable — SSE is equivalent per ROADMAP; switching cost is ~one weekend |
| 14 | Decision: `?token=` query string (not `Authorization` header) | **MUST-HAVE** (as chosen) | Swappable — bearer header works too, but adds CORS preflight risk and breaks pywebview's URL convention |
| 15 | Decision: raw token counts in API (not pre-divided to kilo) | **MUST-HAVE** (as chosen) | Swappable — could pre-divide in backend if reviewer prefers; PLAN-02 client-side divide would go away |
| 16 | Decision: backend resolves Notion UUID→slug (not client) | **MUST-HAVE** (as chosen) | Swappable — could push to client, but every page-load would need `query_active_projects` then |

---

## 1. Notion Reviews DB: 7 new properties (user-side schema change)

**What changed:** Before any code ran, the user manually added these properties to the Notion Reviews database:

| Property | Type |
|---|---|
| `Input tokens` | Number |
| `Output tokens` | Number |
| `Cache read tokens` | Number |
| `Cache creation tokens` | Number |
| `Cost USD` | Number |
| `Started` | Date |
| `Completed` | Date |

**Why:** `lib/notion.py:log_review` writes these property names verbatim. Notion's API returns a 400 if you write to a property that doesn't exist. Without the schema change, the FIRST review row logged post-deploy would crash — and break sibling workstreams that also call `log_review` (orchestrator, `bin/invisible-log`).

**Verdict: MUST-HAVE.** Removing any of these breaks future `log_review` writes. Removing `Started`/`Completed` would force the aggregator to fall back to `Created` for both endpoints of duration → loses SC3 ("Time-spent derived from started_at → completed_at").

**Fallback if reviewer rejects:** Switch to Option B (defensive try/except in `lib/notion.py:_request` that strips unknown properties on a 400). Cost: +~15 lines in `_request`, masks future schema drift, ROADMAP success criterion #2 still met. We chose Option A because it fails loud — a single-user app benefits from crash-loud over silent-skip.

---

## 2. `lib/api/__init__.py` (new file, 1 line)

**What:** `from . import analytics`

**Why:** Python package marker. Lets `bin/invisible-dashboard` do `from api import analytics as analytics_api`.

**Verdict: MUST-HAVE.** Zero alternative — Python won't recognize `lib/api/` as a package without it.

---

## 3. `lib/api/analytics.py` (new file, ~330 lines)

**What:** The aggregator. Exports `get_analytics(range_days, project_id)` and `handle_request(query_params)`. Internal helpers: `_build_slug_map`, `_extract_review`, `_minutes_between`, `_classify_tool`, `_utc_day_index`, `_cache_get/_put`.

**Why:** This IS the feature. Reads Notion reviews, sums tokens, derives time, builds the chart series, caches for 30s. Without it there's no endpoint to serve.

**Verdict: MUST-HAVE.** The plan's two plans are "the aggregator" and "wire it to the page." Removing the aggregator means there's nothing to wire.

**Stdlib-only.** Zero new dependencies (uses `time`, `datetime`, `typing`, `sys` — all stdlib). The 30s cache is a module-level dict, not a library.

**Possible reviewer pushback:**
- *"Why is the cache module-level state, not Redis?"* — Single-process daemon, single user, no need for cross-process state. Cheapest correct answer.
- *"Why is `_classify_tool` substring-matching summary text?"* — Best-effort. The review row only has agent (`Claude` / `Codex`) — for non-LLM tools (Postgres, GitHub) we have to guess from summary. Documented in code + SUMMARY. **Removable as a feature** (could drop `top_tools` to just `[Claude, Codex]`) without breaking SC1.
- *"Why aggregate in Python instead of pushing to Notion query?"* — Notion's database query API doesn't aggregate. We'd have to fetch all rows anyway. Doing the math here is correct.

---

## 4. `lib/notion.py` — `log_review` extended (additive, 3 kwargs)

**What:** Added three keyword-only optional parameters: `usage: dict | None`, `started_at: str | None`, `completed_at: str | None`. When provided, writes the 5 token/cost properties (from `usage`) and 2 date properties.

**Why:** SC2 requires token totals from `usage.input_tokens + usage.output_tokens` in the Claude envelope. The envelope lives in `lib/runners.py:_extract_claude_usage`, but never made it onto the review row. This bridges the gap.

**Verdict: MUST-HAVE.** Without it, no review row ever carries `Input tokens` / `Output tokens` → SC2 cannot be met.

**Backward compatibility:** All three new kwargs default to `None`. Existing call sites (`bin/invisible-log`, anywhere else) work unchanged. `inspect.signature` verified additive in the verification report.

**Fallback if reviewer rejects:** None. This is the SC2 hookup point.

---

## 5. `lib/notion.py` — `query_reviews_since` helper (new function, additive)

**What:** Paginated Notion query that returns all Reviews rows created on or after a given ISO timestamp, with optional project filter.

**Why:** The existing `query_recent_reviews(hours=24)` only takes hours and caps at 100 results. The aggregator needs 30 days of data, possibly hundreds of rows. We need pagination.

**Verdict: MUST-HAVE for >30d windows.** For the current ROADMAP window cap of 30d on a single-user app, we *could* survive with a single `query_recent_reviews(hours=30*24, page_size=100)` call if reviews stay under 100 in 30 days. Today that's true (Notion shows ~5 reviews). Tomorrow it won't be.

**Removable?** Partially:
- Could be DELETED if we accept the 100-row cap and route through `query_recent_reviews` instead — would work today, would break silently at row #101
- The cleaner answer is to keep it; cost is ~25 lines and is purely additive

---

## 6. `lib/orchestrator.py` — capture per-agent timestamps + pass to log_review (4 sites)

**What:** Before each `run_codex_with_retries` / `run_claude_with_retries` call, capture `notion.now_iso()`. After, capture again. Pass `started_at`/`completed_at` (both) and `usage=rr.usage` (claude only) to the 4 `log_review` call sites.

**Why:** SC3 requires `Started → Completed` per review. Those timestamps don't exist anywhere in the codebase today — the orchestrator never measured them. This is the smallest change that makes SC3 truthful.

**Verdict: MUST-HAVE.** Without it, `log_review` never gets `started_at`/`completed_at` and SC3 silently fails (the property stays empty on every row).

**Scope concern (anticipated reviewer pushback):** `lib/orchestrator.py` isn't in this workstream's OWNED file list. It IS in the EDITS-LIGHTLY domain — the plan explicitly instructed updating these call sites. The diff is purely additive (4 new local vars, 4 new kwargs on existing calls; no signature changes, no behavior changes to the iteration loop).

**Fallback if reviewer rejects orchestrator changes:** Drop the orchestrator edits → keep `lib/notion.py` extension. SC3 stays broken (Started/Completed always empty). SC2 stays partially broken (usage never flows from `rr.usage` into Notion either, since that path also lives in orchestrator). Effectively guts SC2 and SC3. Not viable.

---

## 7. `bin/invisible-dashboard` — register `/api/v1/analytics` route (+3 lines + 1 import + 1 docstring bullet)

**What:**
- New import: `from api import analytics as analytics_api`
- New route block in `do_GET` after `/api/reviews` and before the 404 fallback
- Docstring updated to list the new endpoint

**Why:** Without registering the route, `GET /api/v1/analytics` returns 404. SC1 cannot be met.

**Verdict: MUST-HAVE.** Cannot be reduced further; this is the smallest possible wiring.

---

## 8. `bin/invisible-dashboard` — CORS fix on `_send_json` / `_send_text` (+4 lines)

**What:** Added `Access-Control-Allow-Origin: *` to both `_send_json` and `_send_text` response helpers.

**Why:** Discovered during live UAT. The React frontend served from `127.0.0.1:8090` (or 8093 in my test) was BLOCKED by the browser when fetching from the dashboard daemon on `127.0.0.1:8765` (or 8766). PLAN-02's threat model claimed "CORS is permissive" — that was based on misreading the FRONTEND daemon's CORS (which applies to ITS responses) as covering the API. The dashboard daemon had no CORS headers at all.

**Verdict: MUST-HAVE.** Without it, SC4 is broken — the page renders the loading placeholder forever and the console shows a CORS error. We saw this happen, then fixed it, then re-verified.

**Anticipated reviewer concerns:**
- *"Scope creep — this wasn't in the original plan."* — Defense: this is the difference between code-that-compiles and code-that-works. The plan reviewer (in iteration 1) explicitly said the auth strategy was deferred to the executor; CORS is the second-order consequence of that deferral surfacing during the actual integration. One-line additive fix.
- *"Why `*` and not `http://127.0.0.1:8090`?"* — Loopback-only, single-user, single-machine app. `*` is the simplest correct answer. The trust boundary is `--no-auth` + loopback bind, not CORS.
- *"Sibling workstreams could conflict on this file."* — Possible. Resolution would be trivial since the change is additive in a stable location.

**Fallback if reviewer rejects:** Frontend would need to switch to a same-origin proxy via `bin/invisible-frontend` (more invasive — requires routing API requests through the frontend daemon). Worse design.

---

## 9. `frontend/pages/analytics.jsx` — rewrite data plumbing (+110, −47)

**What:** Added inline `getToken()` helper. Added `data` + `err` state. Added useEffect that fetches `/api/v1/analytics`, sets up 30s `setInterval`, cleans up with `clearInterval` + `alive` flag. Replaced the mock-data slicing block with derivations from `data.*`. Added loading placeholder + error indicator dot. Updated `tokenDelta` semantics (first-half vs second-half of visible window instead of vs prior 60d).

**Why:** This is SC4 + SC5 — the page must fetch real data and refresh live.

**Verdict: MUST-HAVE.** Removing any sub-piece breaks the goal:
- Drop `useEffect` → page stays on loading placeholder forever
- Drop `getToken` → can't auth (unless `--no-auth` is hardcoded)
- Drop `setInterval` → no live updates (SC5 fails)
- Drop `clearInterval` → leaked timers (minor leak, would compound across navigation)
- Drop the error indicator → silent failures
- Drop the loading placeholder → bad first-mount UX (would render with `data` null and crash)

**Components left untouched:** `StackedAreaChart`, `HorizontalBars`, `ActionsTable`, `StatCard`, `fmtK`, `fmtH`, `sum`, `lastN` — all preserved exactly. The JSX render tree is structurally identical to before; only the data variables those components consume changed.

---

## 10. `frontend/data.jsx` — remove ANALYTICS mock (−95 lines, +3 comment)

**What:** Deleted the 95-line `const ANALYTICS = { ... }` block and its `Object.assign(window, { ANALYTICS })` line. Left a 3-line comment marker noting where the data now comes from. Sibling globals (`DATA_SETS`, `FOLDERS`, `TOOL_WORKFLOWS`, `TERM_CONTEXT`) and their `Object.assign` line are byte-identical.

**Why:** Cleanup. The analytics.jsx page no longer reads it.

**Verdict: RECOMMENDED, not strict MUST-HAVE.**

**Removable?** Yes — could leave the const in place if the reviewer prefers a soft cutover where the mock data lingers as fallback. The page would still work (it doesn't reference ANALYTICS). The only downside of leaving it: 95 lines of dead code + a global `window.ANALYTICS` that nothing reads.

**If reviewer insists on a soft cutover:** Revert commit `82138b5` and add a one-line comment in `data.jsx` saying "ANALYTICS mock retained pending REQ-05 stability; remove in a follow-up."

---

## 11. Seven planning docs in `.planning/workstreams/analytics-aggregator/phases/INV-01-…/`

Files:
- `INV-01-01-PLAN.md` (429 lines)
- `INV-01-01-SUMMARY.md` (136 lines)
- `INV-01-02-PLAN.md` (449 lines)
- `INV-01-02-SUMMARY.md` (170 lines)
- `INV-01-VERIFICATION.md` (53 lines)

**Why:** GSD workflow artifacts. They're how the planning system tracks the work and gives future-me (or another developer / Claude session) the full context.

**Verdict: OPTIONAL.** They're documentation of intent, not runtime code.

**Removable?** Yes — if the reviewer wants a code-only PR, strip the `.planning/workstreams/analytics-aggregator/phases/` directory from the diff and ship just the code commits (`69bd101`, `7a04cce`, `3dfbdad`, `9d0135d`, `82138b5`, `aaf14f8`). The remaining 6 commits are pure code + the planning artifacts stay in the workstream worktree but don't land on `main`.

**Recommended approach (matches GSD norm):** Ship them. They make the merge history self-documenting and let `gsd-resume-work` / `gsd-stats` / etc. pick up the trail.

---

## 12. `.planning/STATE.md` + `.planning/workstreams/analytics-aggregator/ROADMAP.md` updates

**What:** Workstream state tracking — phase begin/complete markers, plan progress, last activity timestamps.

**Why:** GSD tracking. Same rationale as #11.

**Verdict: OPTIONAL.** Strip with `.planning/*` if the reviewer wants code-only.

---

## 13. Polling vs SSE (architectural decision)

**Chosen:** 30-second polling via `setInterval` on the frontend, 30-second in-process cache on the backend.

**Why this:** ROADMAP allows either. Polling needs zero broadcast infrastructure; cache TTL absorbs the load (~2 requests per minute per open Analytics tab, ~99% hit the cache); no upgrade path required for future Tauri shell.

**Removable?** No — something has to drive the refresh. But SWAPPABLE: SSE would require an EventSource on the frontend + a server-side broadcast channel on the daemon. Net effort to swap: ~half a day. Net benefit: ~30s lower latency on data freshness.

**If reviewer wants SSE:** Swap is contained in `analytics.jsx` (replace setInterval with EventSource) + add a `/api/v1/analytics/stream` route to the daemon that pushes payloads on Notion writes. Aggregator code stays the same.

---

## 14. Auth pattern: `?token=` query string (not `Authorization: Bearer` header)

**Chosen:** Inline `getToken()` reads `?token=` from `window.location.search` first, falls back to `window.__INVISIBLE_TOKEN__`. Appends to fetch URL as `?token=`.

**Why this:** Matches `bin/invisible-app`'s pywebview convention (the app already opens windows with `?token=…` appended). Avoids CORS preflight risk (header-based auth on cross-origin fetch is "non-simple" and triggers OPTIONS). Simpler primitive — a string in the URL vs. setting headers.

**Removable?** No — something has to auth. But SWAPPABLE: header approach is 2 lines different.

**If reviewer prefers Bearer header:**
```js
fetch(u.toString(), { headers: { Authorization: `Bearer ${tok}` } })
```
plus add an OPTIONS handler to the daemon for preflight. ~10 LoC, same auth strength.

---

## 15. Raw token counts in API (not pre-divided to kilo)

**Chosen:** Backend emits raw integer token counts everywhere. Frontend divides by 1000 in one place before passing to the chart.

**Why this:** API consistency — `totals.input_tokens` is a raw integer; if we emitted kilo in `series` only, callers would have to remember which fields are kilo and which are raw. Future API consumers (e.g. CLI tools, sibling pages) expect raw.

**Removable?** No — must pick a unit. But SWAPPABLE: backend could pre-divide series values, frontend's one-line conversion would go away.

**If reviewer wants kilo in series:** Change `lib/api/analytics.py:330` from `+= float(r["input_tokens"] + r["output_tokens"])` to `+= float(r["input_tokens"] + r["output_tokens"]) / 1000` and drop the `.map(v => v / 1000)` in `frontend/pages/analytics.jsx:248`. ~2 lines.

---

## 16. Backend resolves Notion UUID → slug (not client)

**Chosen:** `lib/api/analytics.py:_build_slug_map()` calls `notion.query_active_projects()` once per cache miss; aggregator emits slugs everywhere. Frontend never sees UUIDs.

**Why this:** Frontend stays slug-only (matches `PROJECT_ORDER` constant unchanged). The 30s cache absorbs the extra Notion round-trip cost. Backend has the natural place to do the join.

**Removable?** No — without it, `by_project` keys would be UUIDs, the frontend's `projectMap[pid]` filter would silently drop everything, the page would render with no project layers. We verified this matters during UAT.

**If reviewer wants client-side resolution:** Move the slug map to a `/api/v1/projects` call the frontend hits on mount, then map UUIDs → slugs client-side. ~50 LoC added (new endpoint + client-side `useMemo`). Effectively pushes the same Notion round-trip onto every browser tab. Worse design.

---

## Open questions a reviewer might raise

1. **"Why not write a unit test for `lib/api/analytics.py`?"** — The project has zero tests in `lib/` (verified via `find lib -name 'test_*.py' -o -name '*_test.py'` returns empty). Adding one would diverge from the project's testing norm. If the reviewer wants tests added, we can — would add ~150 lines in a new `tests/test_analytics.py`. Out of Phase 1 scope.

2. **"Why are `top_tools[].color` literals duplicated across backend (in `_classify_tool`) and frontend (in the chart)?"** — The frontend's mock data already shaped colors per-tool. Backend emits matching hex values so the existing components render without modification. Color taxonomy is a UI concern that should ideally live in one place; doing that consolidation would touch the chart components (out of scope).

3. **"The hardcoded `http://127.0.0.1:8765` URL in analytics.jsx will break when REQ-06 (Tauri) repackages the daemon."** — Correct. Sibling workstream `tauri-shell` will need to introduce a `window.__INVISIBLE_API_BASE__` global. Documented in INV-01-VERIFICATION.md as a non-blocking follow-up.

4. **"What if the orchestrator is mid-iteration when the dashboard restarts?"** — The 30s in-process cache resets on daemon restart. First request after restart pays one Notion round-trip, then caches normally. Acceptable.

5. **"Why are codex rows counted in `total_minutes` but zero in token totals?"** — Codex doesn't emit a usage envelope (per `lib/runners.py:_extract_claude_usage` returning None for codex). Time still measurable from Started/Completed. This was a deliberate plan decision and is the truthful representation.

---

## Minimum viable subset (if reviewer demands aggressive trimming)

If reviewer says "ship the smallest possible change that delivers REQ-05":

**Keep:** #1, #2, #3, #4, #6, #7, #8, #9 (8 items)
**Drop:** #5 (use `query_recent_reviews` with high `page_size`), #10 (leave the mock in `data.jsx`), #11–12 (planning docs)
**Net:** ~5 commits, ~500 lines of code, no planning docs in the PR

This still satisfies all 5 ROADMAP success criteria but is brittle (will fail silently at >100 reviews in window) and leaves dead code (`ANALYTICS` const in `data.jsx`). I'd push back unless the reviewer has strong space constraints.

---

## If the PR fails entirely

If the reviewer says "no, redo this," the highest-leverage path back is:

1. **Keep #1 (Notion DB schema)** — the user did this manually, no code to undo
2. **Revert all code commits** with `git revert 69bd101..aaf14f8` — restores the codebase exactly
3. **Keep the planning docs** as historical record of the attempt
4. **Replan** with the reviewer's feedback applied to PLAN-01 / PLAN-02

Total revert cost: ~5 minutes. The work that's hardest to undo is the Notion schema change — but it's additive, so leaving the 7 properties in place doesn't break anything in the meantime.
