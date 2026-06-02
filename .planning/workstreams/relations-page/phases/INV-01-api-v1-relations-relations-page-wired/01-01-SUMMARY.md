---
phase: 01-api-v1-relations-relations-page-wired
plan: 01
subsystem: api
tags: [graph, ast, regex, notion, http, cache, slug-validation]

requires:
  - phase: bootstrap
    provides: "lib/api/__init__.py ROUTES registry; bin/invisible-dashboard /api/v1/* dispatch; lib/config.py home() + load_toml(); lib/notion.py query_active_projects()"
  - phase: tree_local
    provides: "_safe_resolve symlink-bounding pattern (lib/api/tree_local.py:113-141) — verbatim port into relations._safe_resolve"

provides:
  - "GET /api/v1/relations?project=<slug> returning {nodes, edges} graph derived from import + grep + notion + endpoint sources"
  - "Aggregate GET /api/v1/relations across the synthetic invisible codebase + invisible.toml [[projects]] entries"
  - "PROJECT_SLUG_RE validator + 400 rejection of unsafe slugs before any filesystem/Notion/subprocess call"
  - "Per-project 60s TTL cache with min-expiry eviction at 32 entries"
  - "Notion deriver that degrades silently on missing token or API failure (endpoint still 200)"
  - "# PLAN-01-01 verification log marker that Plan 02 greps for before wiring the React frontend"

affects: [relations-frontend, plan-02, frontend/pages/relations.jsx]

tech-stack:
  added: []  # stdlib only: ast, os, re, sys, time, urllib.parse, pathlib, typing
  patterns:
    - "Bounded walker with size + symlink + binary caps (T-01-01-03/04)"
    - "Slug regex validation before downstream use (T-01-01-01)"
    - "Notion deriver wrapped in broad try/except → silent degrade, class-name-only stderr (T-01-01-06)"
    - "Per-key TTL cache with min-expiry eviction (mirrors lib/api/tree_repo.py)"
    - "Defensive _send_json wrapped in nested try/except blocks so error-path failures don't crash the handler"

key-files:
  created:
    - "lib/api/relations.py"
    - ".planning/workstreams/relations-page/phases/INV-01-api-v1-relations-relations-page-wired/01-01-SUMMARY.md"
  modified:
    - "lib/api/__init__.py"
    - "bin/invisible-dashboard"

key-decisions:
  - "Tightened grep-deriver basename filter to require length ≥ 5 AND (starts-uppercase OR contains-underscore) — necessary to keep edge count inside the 50–500 sanity bound; raw lowercase basenames matched too many English-prose tokens (initial run: 703 edges, post-fix: 216 edges)"
  - "Used port 8769 for the four Task-3 scenarios because a sibling-worktree daemon (calendar-events) grabbed port 8765 between my kill and relaunch; behavior is port-independent"
  - "Notion deriver silently short-circuits on missing NOTION_TOKEN (no stderr warning) — per plan spec: 'no notion configured' is a normal state, not a failure; the warning path triggers only on actual exceptions"

patterns-established:
  - "Slug validation gate: validate before resolve; reject with {\"error\": \"invalid_project\"} and never echo raw input"
  - "Aggregate-with-synthetic-slug pattern: build_graph(None) prepends 'invisible' to invisible.toml [[projects]] so the canonical codebase always appears in the rollup"
  - "Verification-log marker: append a `# PLAN-XX-YY verification log` comment block at the bottom of the implementation file documenting the e2e scenarios that passed (downstream plans grep for it as a stability gate)"

requirements-completed: []  # Plan frontmatter requirements field is empty (M2 relations not yet in REQUIREMENTS.md per orchestrator notes)

duration: ~25 min
completed: 2026-06-02
---

# Phase 01 Plan 01: Backend Relations API Summary

**`GET /api/v1/relations` returns a real Obsidian-style graph (97 nodes, 216 edges) derived from AST imports + .planning grep + notion relations + dashboard route literals, with 60s per-project caching and `^[a-z0-9_-]{1,64}$` slug validation; the new module ships behind a one-line route entry in `lib/api/__init__.py` and a one-line `return` fix in `bin/invisible-dashboard`'s dispatcher.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-06-02T04:11:36Z (workstream STATE.md timestamp)
- **Completed:** 2026-06-02T04:24:00Z (Task 3 commit)
- **Tasks:** 3
- **Files created:** 1 (lib/api/relations.py)
- **Files modified:** 2 (lib/api/__init__.py, bin/invisible-dashboard)

## Accomplishments

- New `lib/api/relations.py` (~1040 lines) with four derivers: import (Python AST + JSX regex), grep (.planning/**/*.md cross-refs), endpoint (`/api/v1/*` literal extraction from `bin/invisible-dashboard`), and notion (best-effort `query_active_projects()` traversal with silent degrade)
- Unified `build_graph(project)` with per-project 60s TTL cache, 32-entry min-expiry eviction
- `PROJECT_SLUG_RE = ^[a-z0-9_-]{1,64}$` slug validation rejects path-traversal and shell-meta inputs with HTTP 400 + `{"error": "invalid_project"}` — raw input never echoed back
- `_safe_resolve` ported verbatim from `lib/api/tree_local.py:113-141`; `_project_root` SPECIAL CASE for the synthetic `"invisible"` slug returns `config.home()`; general case mirrors `tree_local.py:224-234` (lookup invisible.toml `[[projects]]` by name, then `_safe_resolve(repo_path)`)
- Aggregate (`project=None`) prepends `"invisible"` to the invisible.toml project list so the canonical codebase always appears in the rollup
- `lib/api/__init__.py` registers the route with one import line + one ROUTES entry (additive — sister-workstream entries preserved verbatim)
- `bin/invisible-dashboard` gets a single `return` after the `API_V1_ROUTES[path](self)` dispatch so the new endpoint doesn't fall through into the tree-routes block and the final 404
- Four scenarios verified end-to-end against a live daemon: happy path, aggregate, bad-slug rejection (raw + URL-encoded), Notion-degrade with `NOTION_TOKEN` unset
- `# PLAN-01-01 verification log` marker block appended to `lib/api/relations.py` for Plan 02 to grep

## Task Commits

1. **Task 1: Create lib/api/relations.py with 4 derivers + cache + handler** — `5eefcdd` (feat)
2. **Task 2: Register /api/v1/relations route + fix dispatch fallthrough** — `9f86984` (feat)
3. **Task 3: Verify wire shape, slug validation, Notion-degrade against live daemon** — `06f0014` (test)

_Plan metadata commit follows this summary._

## Files Created/Modified

- `lib/api/relations.py` (new, ~1040 lines) — graph derivation module: imports + derivers + cache + handler + verification log
- `lib/api/__init__.py` (modified, +3 lines) — one import + one ROUTES entry + `__all__` update
- `bin/invisible-dashboard` (modified, +1 line) — `return` after `API_V1_ROUTES[path](self)` to stop fallthrough
- `.planning/workstreams/relations-page/phases/INV-01-api-v1-relations-relations-page-wired/01-01-SUMMARY.md` (new) — this file

## Decisions Made

- **Tightened grep-deriver basename filter** (in-task fix during Task 1 verify): the initial implementation produced 703 edges (above the 50–500 sanity bound). Root cause: 64 `.md` files in `.planning/` with many shared basenames (`STATE.md`, `ROADMAP.md`, `PROJECT.md` repeat across every workstream) created N² doc-to-doc edges, and lowercase module basenames like `projects` matched English prose. Fix: require basename length ≥ 5 AND (starts-uppercase OR contains-underscore). Result: 216 edges — well within the bound and the docs/modules that actually appear are semantically meaningful. This matches the threat-model anticipation ("consider requiring the basename match to be a capitalized form").
- **Used port 8769 for Task 3 scenarios** instead of 8765: a sibling-worktree daemon (calendar-events, PID 38346, cwd `/Users/ace/.invisible-ws/calendar-events`) bound port 8765 between my kill and relaunch. Cross-worktree isolation rule: I do not control sibling worktrees' daemons, so I switched ports rather than killing theirs. Behavior is port-independent (the dashboard binds to `127.0.0.1` on any `--port`); all four scenarios pass identically.
- **Notion deriver silent short-circuit on missing token**: per plan spec, "no notion configured" is a normal state and should NOT print the `notion deriver degraded:` warning. The warning fires only on actual exceptions during `query_active_projects()`. Verified by scenario (d): with `NOTION_TOKEN` unset, the endpoint returns 200 with 0 project nodes and stderr stays clean.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Grep deriver produced 703 edges (over the 50–500 sanity bound)**
- **Found during:** Task 1 verify
- **Issue:** Initial basename-matching regex used `len(basename) >= 4` for both module and doc basenames, with no case filter. The 64-file `.planning/` subtree contained ~10 each of `STATE.md`/`ROADMAP.md`/`PROJECT.md` across workstreams, and lowercase module basenames like `projects` / `config` matched English prose in docs ("the projects page", "current state"), producing 682 grep edges + 21 import edges = 703 total.
- **Fix:** Tightened both module and doc basename filters to require length ≥ 5 AND (starts-uppercase OR contains-underscore). This excludes English-noun-style lowercase basenames while keeping snake_case module names (`tree_local`, `dashboard_render`) and capitalized doc tags (`PROJECT`, `STATE`, `ROADMAP`, `START_HERE`).
- **Files modified:** `lib/api/relations.py` (in-task edit before Task 1 commit)
- **Verification:** Edge count dropped from 703 → 216, well inside 50–500. Threat-model anticipated this fix ("consider requiring the basename match to be a capitalized form (e.g. `PROJECT.md` not `the project`)").
- **Committed in:** `5eefcdd` (Task 1 commit — fix applied before the first commit landed)

---

**Total deviations:** 1 auto-fixed (Rule 1 — anticipated in plan's threat-model guidance)
**Impact on plan:** Necessary correctness fix to satisfy the 50–500 edge sanity bound. No scope creep; the filter logic was always expected to need tuning, and the plan documents the exact tuning that would be required.

## Issues Encountered

- **Stale sibling-worktree daemon on port 8765:** A `calendar-events` worktree daemon (PID 38346) bound port 8765 between my kill-and-relaunch cycle. Workaround: switched to port 8769 for the four Task-3 scenarios. The plan's literal verify-block uses 8765 but the behavior under test (route dispatch, slug validation, Notion degrade) is port-independent.
- **Daemon startup race:** First retry of scenario (d) hit `HTTP 000` because the `env -u NOTION_TOKEN bin/invisible-dashboard ...` child took longer than 2 s to bind (Infisical bootstrap timed out on the network call before falling through to read `.env`). Resolved by extending `sleep 2.5` and re-issuing the curl. Tracked in the verification log; not a code bug.

## User Setup Required

None — no new dependencies (stdlib only), no new env vars, no new external services. The Notion path uses the existing `NOTION_TOKEN` env var and silently no-ops if it's unset.

## Next Phase Readiness

- **Plan 02 (frontend) is unblocked.** The wire contract is frozen:
  ```
  {"nodes": [{"id", "label", "type" ∈ {module|doc|project|endpoint}, "project"?, "file_path"?}],
   "edges": [{"from", "to", "kind" ∈ {import|grep|notion}}]}
  ```
- **Verification marker exists** at the bottom of `lib/api/relations.py`: Plan 02 should `grep -q '^# PLAN-01-01 verification log' lib/api/relations.py` as a pre-fetch gate.
- **No backend follow-up required** to satisfy the Plan 02 React swap: the endpoint returns 200 with a valid graph for `project=invisible`, and the dashboard auto-dispatches via the `API_V1_ROUTES` table.
- **Deferred items (out of scope for Plan 01):** per-project Notion query filtering (T-01-01-08 disposition: "accept; deferred to Plan 02 frontend filter or follow-up plan"); SSE / watch-mode for live graph updates (Plan 02 may add via a separate route).
- **No M1 requirement IDs to mark complete** — phase frontmatter `requirements: []`. M2 relations are not yet enumerated in `.planning/REQUIREMENTS.md`; that file currently lists M1 REQ-01..REQ-06 only.

## Self-Check: PASSED

- **Files exist:**
  - `lib/api/relations.py` — FOUND (1040 lines, includes verification log marker)
  - `lib/api/__init__.py` — FOUND (modified, route registered)
  - `bin/invisible-dashboard` — FOUND (modified, return added)
  - `01-01-SUMMARY.md` — FOUND (this file)
- **Commits exist:**
  - `5eefcdd` (Task 1) — FOUND in `git log`
  - `9f86984` (Task 2) — FOUND in `git log`
  - `06f0014` (Task 3) — FOUND in `git log`
- **Verification:**
  - `python3 -c "import sys; sys.path.insert(0,'lib'); from api import relations; assert relations._CACHE_TTL_S == 60"` — passes
  - `grep -q '^# PLAN-01-01 verification log' lib/api/relations.py` — passes
  - Four-scenario daemon verify on port 8769 — all PASS

---
*Phase: 01-api-v1-relations-relations-page-wired*
*Completed: 2026-06-02*
