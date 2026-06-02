---
phase: INV-01-api-v1-relations-relations-page-wired
workstream: relations-page
status: deferred-from-phase-1
created: 2026-06-02
---

# Phase 1 Follow-ups

Code is committed and shipped. Phase 1 verifier returned PASSED (6/6 ROADMAP criteria + 23/23 plan must-haves). Code review (`01-REVIEW.md`) found 3 WARNINGs after the fact; one was fixed in-session (`c6a58e7`), two are deferred here with intent.

## ✓ WR-02 (latent symlink bug) — RESOLVED in-session (2026-06-02)

`_project_root("invisible")` returned `config.home()` unresolved while `_derive_import_edges` compared candidates via `candidate.resolve().is_relative_to(project_root)`. Under any INVISIBLE_HOME that traversed a symlink, the unresolved root vs resolved candidate silently mismatched and every JSX import edge was dropped.

**Fix shipped** in `lib/api/relations.py` line 238: `return config.home().resolve()`.

Production setup happens not to symlink, which is why Plan 01-01 verify caught 220 edges (well within bounds). Sandbox repro of the bug was real. Commit: `c6a58e7`.

## 1. WR-01 — Fetch race on rapid Retry (frontend/pages/relations.jsx)

**Symptom:** If fetch #1 is slow-failing and the user clicks **Retry**, fetch #2 can succeed while fetch #1's `.catch(setError)` still resolves *after* and clobbers the loaded state. Render shows the error card despite valid data being in component state.

**Reproduce:** Throttle dashboard to ~3s response time, click Retry twice in <1s, observe error+data flicker.

**Fix sketch:** Sequence-numbered guard:
```js
const fetchSeqRef = useRefG(0);
const loadGraph = useCallbackG(async () => {
  const seq = ++fetchSeqRef.current;
  try { const d = await fetchRelations("invisible"); if (seq === fetchSeqRef.current) setData(d); }
  catch (e) { if (seq === fetchSeqRef.current) setError(e); }
}, []);
```

**Decision:** deferred. Single-user app, loopback fetch, real-world latency ~50ms — race is theoretically reachable but practically rare. Drop into the next polish pass on this page.

## 2. WR-03 — Endpoint deriver hardcodes slash-id (lib/api/relations.py:686-712)

**Symptom:** `_derive_endpoint_nodes` emits `id="bin/invisible-dashboard"` (slash) while every other module id is dot-separated (`lib.api.relations`, `frontend.pages.dashboard`). The grep deriver's basename-to-id map therefore can never derive a working pattern for the dashboard module, so docs that mention `invisible-dashboard` produce zero grep edges to it.

**Fix:** normalize the dashboard module id to dot form (e.g. `bin.invisible-dashboard`) consistent with sibling modules, OR maintain a dedicated basename→id index for the endpoint deriver.

**Decision:** deferred. Low-impact (one node out of ~94 misses a few cross-doc edges); doesn't change the rendered graph's overall topology or the 50–500 sanity bound. Follow-up for a polish-edges plan.

## 3. INFO — Stale `"18 NODES · 22 LINKS"` chip in app shell (frontend/app.jsx:91)

**Symptom:** The global page-title chip below the `relations` H1 still reads `"18 NODES · 22 LINKS"` (hardcoded `PAGE_HEADERS["relations"]` literal in app.jsx). The Relations content area renders its own correct dynamic chip `"94 nodes · 220 links · API · /api/v1/relations"` below it.

**Why not fixed here:** `frontend/app.jsx` is OUTSIDE this workstream's OWNS / EDITS LIGHTLY scope — it's the shared shell that every page renders inside of. Touching it would violate the hard sibling-workstream boundary.

**Right home for the fix:** either `dashboard-wiring` workstream (it owns the shell-level page header pattern) or a new follow-up plan dedicated to wiring the page-title chips to live data sources.

**Sketch:** thread per-page chip text through a context provider that each page populates on mount, e.g. `const { setPageChip } = usePageChrome(); useEffectG(() => setPageChip(`${nodes.length} nodes · ${edges.length} links`), [nodes, edges]);`.

## 4. Operational gotcha (worth documenting workstream-wide)

`bin/invisible-frontend` and `bin/invisible-dashboard` both default `INVISIBLE_HOME=~/.invisible` (canonical home), NOT the workstream worktree. If you start either daemon bare in a workstream worktree, it serves/walks the **canonical checkout's** files, not the workstream's edits.

**Always start daemons explicitly rooted at the workstream:**
```bash
cd ~/.invisible-ws/<workstream>
INVISIBLE_HOME="$(pwd)" ./bin/invisible-dashboard --no-auth --port 8765
INVISIBLE_HOME="$(pwd)" ./bin/invisible-frontend --port 8090
```

This is identical to the gotcha documented by ai-bubble workstream's FOLLOWUPS.md. Worth promoting into the project's top-level README or each START_HERE.md scaffold — both sibling workstreams have hit it independently now.

## Defer-or-not summary

| ID | Severity | Fix here? | Reasoning |
|----|----------|-----------|-----------|
| WR-01 fetch race | WARNING | deferred | Theoretical, requires very narrow timing |
| WR-02 symlink-unstable home | WARNING | **fixed `c6a58e7`** | One-line, clearly correct, low risk |
| WR-03 dashboard id format | WARNING | deferred | Cosmetic edge case; one node out of 94 |
| app.jsx stale chip | INFO | not in scope | Owned by sibling shell workstream |
| Daemon HOME gotcha | INFO | docs only | Workstream-wide; same as ai-bubble's note |

Medium / Low / Info findings from `01-REVIEW.md` (cache-key collision on `"__all__"` slug, slug-regex permissivity, grep O(N²) growth, Header redefined per render, etc.) are recorded in the review and not duplicated here; address in a polish plan when there's appetite.
