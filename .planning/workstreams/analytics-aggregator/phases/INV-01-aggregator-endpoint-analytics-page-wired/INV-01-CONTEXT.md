# Context — Phase INV-01 / analytics-aggregator

> Handoff document for future Claude sessions or future-self. Written after a session that planned, executed, verified, and **almost** shipped Phase 1 of the analytics-aggregator workstream.

---

## ⚠ Current merge state (verified 2026-06-01)

**The branch `ws/analytics-aggregator` is NOT merged to `origin/main`.**

Evidence:
- `git ls-remote origin refs/heads/ws/analytics-aggregator` → empty (never pushed)
- `gh pr list --head ws/analytics-aggregator` → empty (no PR exists)
- `git ls-tree origin/main lib/api/analytics.py` → file not found
- `git show origin/main:frontend/data.jsx | grep "^const ANALYTICS"` → still defines the mock
- 11 commits remain ahead of `origin/main` only on the local branch

The 5 sibling workstreams DID merge (PRs #1 ai-bubble, #2 folders-3source, #4 tauri-shell, #5 terminals-pty, #6 dashboard-wiring) on 2026-05-27. Our work is the only one that didn't ship.

**Likely cause:** `/gsd:ship` was invoked at the end of the session but interrupted before the push/PR step ran. The defense doc (`SHIP-DEFENSE.md`) was written instead, then the session ended without re-running ship.

**To finish shipping (from this worktree):**

```bash
cd ~/.invisible-ws/analytics-aggregator

# 1. Rebase onto current origin/main (5 sibling merges may have changed
#    bin/invisible-dashboard, lib/api/__init__.py, lib/notion.py)
git fetch origin main
git rebase origin/main

# 2. Expect conflicts in:
#    - lib/api/__init__.py (siblings added imports too)
#    - bin/invisible-dashboard (siblings added routes too)
#    - Possibly lib/notion.py (but our changes are additive)
#    Resolve by keeping our analytics line + their lines.

# 3. Push and open the PR
git push -u origin ws/analytics-aggregator
gh pr create --title "Phase INV-01: Analytics aggregator + Analytics page wired (REQ-05)" \
  --body-file SHIP-DEFENSE.md \
  --base main
```

If the merge is desired but conflicts are non-trivial, the safer path is:
1. Cut a new branch off current `main`
2. Cherry-pick our 9 code commits (`69bd101 7a04cce 3dfbdad 9d0135d 82138b5 aaf14f8` + 2 summary commits) one at a time
3. Resolve per-commit instead of all at once

---

## What this phase delivered (functionally)

REQ-05 (Analytics page reads real Notion review history) — implemented end-to-end and verified live via Playwright UAT.

**The user-visible outcome:** opening the Analytics page in `bin/invisible-frontend` fetches `GET /api/v1/analytics?range=<N>d&project=<slug>?` on mount, polls every 30s, renders all six existing UI sections (filter bar, stat strip, stacked area chart, three horizontal-bar cards, top-actions table) off live Notion data. The 95-line `ANALYTICS` mock in `frontend/data.jsx` is gone.

**Cross-workstream gift:** the `Access-Control-Allow-Origin: *` header on `bin/invisible-dashboard`'s `_send_json` / `_send_text` was discovered missing during UAT and added. Sibling workstreams that wire React → daemon will benefit without rediscovery.

---

## Files touched in this phase

| File | Status | Lines | Why |
|---|---|---|---|
| `lib/api/__init__.py` | NEW | 1 | Package marker so `from api import analytics` works |
| `lib/api/analytics.py` | NEW | ~330 | The aggregator: `get_analytics`, `handle_request`, slug map, 30s cache |
| `lib/notion.py` | MODIFIED | +60 | `log_review` extended additively (`usage`, `started_at`, `completed_at` kwargs); new `query_reviews_since` paginating helper |
| `lib/orchestrator.py` | MODIFIED | +18 | Captures `codex_started/completed` + `claude_started/completed` via `notion.now_iso()`; passes them + `rr.usage` into the 4 existing `log_review` call sites |
| `bin/invisible-dashboard` | MODIFIED | +12 | Imports `analytics as analytics_api`; new route block in `do_GET`; CORS header on `_send_json` and `_send_text`; docstring bullet |
| `frontend/pages/analytics.jsx` | MODIFIED | +110 / −47 | Inline `getToken()`; useEffect fetch + 30s `setInterval` + `clearInterval` cleanup; new `data`/`err` state; loading placeholder; error dot in filter bar; data plumbing rewritten to derive from `data.totals` / `data.by_project` / `data.series` / `data.top_tools` / `data.top_actions`. All UI components and JSX structure untouched. |
| `frontend/data.jsx` | MODIFIED | +3 / −99 | Removed 95-line `const ANALYTICS = {…}` and its `Object.assign(window, { ANALYTICS })`; sibling globals (DATA_SETS, FOLDERS, TOOL_WORKFLOWS, TERM_CONTEXT) byte-identical |
| `.planning/.../INV-01-01-PLAN.md` | NEW | 429 | PLAN-01 (backend aggregator) — autonomous: false due to Task 0 human checkpoint |
| `.planning/.../INV-01-02-PLAN.md` | NEW | 449 | PLAN-02 (frontend wiring) |
| `.planning/.../INV-01-01-SUMMARY.md` | NEW | 136 | PLAN-01 outcome |
| `.planning/.../INV-01-02-SUMMARY.md` | NEW | 170 | PLAN-02 outcome (includes CORS discovery) |
| `.planning/.../INV-01-VERIFICATION.md` | NEW | 53 | Phase verification: PASS, 5/5 success criteria |
| `.planning/STATE.md` + workstream `STATE.md` + `ROADMAP.md` | MODIFIED | small | Phase begin/complete tracking |
| `SHIP-DEFENSE.md` | NEW | uncommitted | PR-defense doc per file change (must-have / removable verdict) |
| `CONTEXT.md` | NEW (this file) | — | Handoff for future sessions |

---

## External dependencies introduced

**Notion DB schema** — 7 new properties on the Reviews database (added manually by the user via Notion UI, NOT via code):

| Property | Type |
|---|---|
| Input tokens | Number |
| Output tokens | Number |
| Cache read tokens | Number |
| Cache creation tokens | Number |
| Cost USD | Number |
| Started | Date |
| Completed | Date |

The code refers to these property names verbatim. If they ever get renamed in Notion, `lib/notion.py:log_review` and `lib/api/analytics.py:_extract_review` need matching edits.

**No package dependencies added.** Aggregator uses only stdlib (`time`, `datetime`, `typing`, `sys`). Frontend uses only React hooks already present.

---

## Architectural decisions (load-bearing)

1. **30-second polling, not SSE.** ROADMAP allowed either. Polling needs no broadcast infrastructure; the backend's 30s in-process cache absorbs the load. Tradeoff: data is up-to-30-seconds stale.
2. **`?token=` query string, not `Authorization: Bearer` header.** Matches `bin/invisible-app`'s pywebview URL convention. Avoids CORS preflight risk. Sibling workstreams should copy `getToken()` verbatim (see `frontend/pages/analytics.jsx:11-17`).
3. **Backend resolves Notion UUID → project slug.** `_build_slug_map()` calls `notion.query_active_projects()` once per cache miss. Frontend stays slug-only — `PROJECT_ORDER` constant unchanged.
4. **Raw token counts in API, kilo conversion on frontend.** Backend emits raw everywhere (consistent with `totals.input_tokens`). Frontend divides by 1000 before passing to the StackedAreaChart whose internal `fmtK(v * 1000)` math expects kilo-tokens.
5. **Crash-loud on Notion schema drift (Option A).** No defensive try/except in `lib/notion.py:_request`. Schema gate (Task 0) is a human checkpoint before code runs. If a property is later removed from Notion, the next `log_review` write 400s loudly.
6. **30s cache keyed by `(range_days, project_slug | None)`.** Module-level dict + `time.monotonic()`. Survives across requests in the same daemon process; resets on restart.
7. **Best-effort tool classification.** `_classify_tool` substring-matches summary text for non-LLM markers (Postgres, Redis, GitHub, etc.) — agent-name (Claude / Codex) is the fallback. Not perfectly accurate. Documented as a known limitation in VERIFICATION.md.

---

## Verification evidence (from this session)

**Curl smokes (UAT against port 8766):**
- `GET /api/v1/analytics?range=30d` → 200, all 5 top-level keys present
- `GET /api/v1/analytics?range=7d` → 200, series arrays length 7
- `GET /api/v1/analytics?range=99d` → 400
- `by_project.keys()` → `["jobslayer"]` (slug, no UUID-shaped strings)

**Playwright visual UAT:**
- Page renders 5 cards + 4 stat cards + 6 filter pills
- Top actions table shows real Notion summaries ("Defensive hardening of Infisical env-var handling is correct", "codex committed 950bb04")
- Range pill clicks (7d/14d/30d) trigger fresh fetches
- 30s polling tick fired automatically after ~30s
- Unmount cleanup confirmed: no fetches after navigating to Dashboard
- 0 console errors (only Babel-standalone deprecation warning)
- Sibling pages (Dashboard, Folders, Terminals) survive unchanged

**CORS bug discovered + fixed during UAT.** Added `Access-Control-Allow-Origin: *` to `_send_json` and `_send_text` after seeing browser console block the cross-origin fetch.

**Token totals are currently 0** because review rows pre-date the Task 0 schema gate. The numbers will grow as the orchestrator runs new reviews. This is expected per ROADMAP success criterion #2 (which is about wiring, not historical backfill).

---

## Commit history (chronological, oldest first)

```
7ec7d3a  docs(01): plan phase 1 analytics aggregator + frontend wiring
13be0ab  docs(01): begin phase 1 — analytics aggregator + frontend wiring
69bd101  feat(INV-01-01): persist usage telemetry on review rows
7a04cce  feat(INV-01-01): aggregator with 30s cache + Notion UUID→slug map
3dfbdad  feat(INV-01-01): wire GET /api/v1/analytics route into invisible-dashboard
344b569  docs(INV-01-01): summary — backend aggregator + 30s cache complete
9d0135d  feat(INV-01-02): wire analytics.jsx to GET /api/v1/analytics with 30s polling
82138b5  feat(INV-01-02): remove ANALYTICS mock from data.jsx
aaf14f8  fix(INV-01-02): add CORS header to dashboard JSON/text responses
fb20625  docs(INV-01-02): summary — frontend wiring + live UAT + CORS fix complete
1698c15  docs(INV-01): phase verification PASS — REQ-05 complete
```

9 commits are pure code; 2 are summaries; 2 (`7ec7d3a`, `13be0ab`) are plan/state setup.

---

## Known follow-ups (non-blocking)

These were noted in `INV-01-VERIFICATION.md`:

1. **Hardcoded `http://127.0.0.1:8765` URL** in `frontend/pages/analytics.jsx:224`. Sibling REQ-06 (Tauri shell) will need a `window.__INVISIBLE_API_BASE__` global to avoid this.
2. **Tool substring-classifier** may misattribute Claude tokens to "Postgres" when a Claude summary mentions Postgres incidentally. Future fix: add a structured `tool` field to the review row.
3. **No automated tests** for `lib/api/analytics.py`. Project has no `tests/` dir for `lib/` yet (zero existing test files). Adding tests would diverge from current convention.

---

## How sibling workstreams interact with this

**The `getToken()` pattern.** Lives at `frontend/pages/analytics.jsx:11-17`. Sibling workstreams (dashboard-wiring REQ-01, ai-bubble REQ-02, folders-3source REQ-03, terminals-pty REQ-04) should copy it verbatim. As of merge of those siblings on 2026-05-27, they each implemented their own variant. Worth checking if any drifted from the canonical form.

**The CORS fix on `bin/invisible-dashboard`.** Lives at `_send_json` (line ~258) and `_send_text` (line ~267). Sibling workstreams have likely each fetched from the daemon — if any of their PRs landed without hitting CORS, either they added their own CORS lines (possible duplication / merge conflict with our edit) or they were saved by `bin/invisible-frontend`'s `Access-Control-Allow-Origin: *` somehow (unlikely — that's on the wrong daemon).

**On merge,** expect conflicts in:
- `lib/api/__init__.py` — siblings added their `from . import chat`, `from . import projects`, `from . import tree_local`, etc. Resolve by keeping their lines AND ours (`from . import analytics`).
- `bin/invisible-dashboard` — siblings added routes too. Resolve by keeping all route blocks. The CORS edits to `_send_json` / `_send_text` may need to be reconciled if a sibling added the same lines.
- `frontend/pages/analytics.jsx` — pure local addition, unlikely to conflict.
- `frontend/data.jsx` — siblings probably didn't touch the ANALYTICS section since it's our scope. Should be clean.

---

## Operational notes (running the app)

To run the analytics integration locally:

```bash
# Set INVISIBLE_HOME to the worktree so daemons load from our code
cd ~/.invisible-ws/analytics-aggregator

# Terminal 1: dashboard daemon (the API)
INVISIBLE_HOME=$(pwd) bin/invisible-dashboard            # 127.0.0.1:8765
# or with --no-auth for loopback testing:
INVISIBLE_HOME=$(pwd) bin/invisible-dashboard --no-auth

# Terminal 2: frontend daemon (the React bundle)
INVISIBLE_HOME=$(pwd) bin/invisible-frontend             # 127.0.0.1:8090

# Browser:
open "http://127.0.0.1:8090/?token=$INVISIBLE_DASHBOARD_TOKEN"
# (or just http://127.0.0.1:8090/ if dashboard is --no-auth)
```

**Gotcha:** If you run `bin/invisible-dashboard` WITHOUT setting `INVISIBLE_HOME`, it loads from `~/.invisible/` (the main repo) and serves the OLD code without the analytics route. Set `INVISIBLE_HOME=$(pwd)` to point at this worktree.

**Port collisions:** Multiple sibling sessions may have daemons running on 8090/8765/8091/8092. Check with `lsof -iTCP -sTCP:LISTEN | grep -E ':80[0-9]{2}|:87[0-9]{2}'` before starting yours.

**Env source:** Secrets (NOTION_TOKEN, NOTION_DB_REVIEWS, INVISIBLE_DASHBOARD_TOKEN) come from Infisical via `lib/config.py:load_env()`. `~/.invisible/.env` contains the Infisical bootstrap creds. The worktree itself has no `.env`.

---

## Pointers for future-me

- **Read first when resuming:** `INV-01-VERIFICATION.md` (proves what's working), `SHIP-DEFENSE.md` (per-change rationale), this file.
- **If reviewing the PR after eventual merge:** the 30s polling + CORS choices are the two most likely to attract pushback. Both are defended in SHIP-DEFENSE.md.
- **If extending the analytics endpoint:** the cache key tuple `(range_days, project_id)` is currently the only dimension. Adding a date-range cursor (e.g. `since=...`) would need either a new cache key or a cache-bypass mode.
- **If the orchestrator stops writing reviews to Notion:** SC2/SC3 will quietly stop progressing. Watch for empty `Input tokens` / `Started` properties on new rows.
