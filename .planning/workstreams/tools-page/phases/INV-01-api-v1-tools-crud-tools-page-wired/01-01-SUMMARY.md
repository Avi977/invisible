---
phase: INV-01-api-v1-tools-crud-tools-page-wired
plan: 01
subsystem: api
tags: [http, crud, cors, atomic-write, path-traversal, stdlib, python]

# Dependency graph
requires:
  - phase: M1 dashboard daemon (bin/invisible-dashboard, lib/api/projects.py)
    provides: DashboardHandler do_POST/_send_json/_auth_ok template, projects.py handler contract, config.home()
provides:
  - GET/PUT/DELETE /api/v1/tools — per-project workflow CRUD over config.home()/workflows/<slug>.json
  - lib/api/tools.py transport-agnostic handlers (handle_get/handle_put/handle_delete)
  - atomic lock-free single-writer JSON persistence (tmpfile + fsync + os.replace)
  - strict slug trust boundary (^[a-z0-9][a-z0-9_-]{0,63}$) rejecting traversal before any path build
  - do_PUT / do_DELETE write methods on DashboardHandler (auth-gated, body-capped)
  - single-source loopback-only CORS (one ACAO per response) + one do_OPTIONS advertising PUT/DELETE
affects: [tools-page frontend plan 01-02, any future write endpoint on the dashboard daemon]

# Tech tracking
tech-stack:
  added: []  # pure stdlib — json/os/re/tempfile/datetime/urllib; no new packages
  patterns:
    - "Atomic JSON write: tempfile.mkstemp(dir=same) + fsync + os.replace (first repo writer)"
    - "Validate-and-reject regex slug gate BEFORE Path construction (stricter than projects._safe_path)"
    - "Single-source CORS via _cors_headers() helper called by every response helper + do_OPTIONS"
    - "Write HTTP verbs (do_PUT/do_DELETE) mirror do_POST: auth-gate first, body cap, JSON-parse→400, last-resort 500"

key-files:
  created:
    - lib/api/tools.py
    - tests/test_api_tools.py
  modified:
    - lib/api/__init__.py
    - bin/invisible-dashboard

key-decisions:
  - "Three handlers (handle_get/put/delete) over a single dispatcher — matches the projects.py/registry style"
  - "PUT body hand-off via handler._json_body attribute; do_PUT parses+stashes, handle_put reads (identical name both sides)"
  - "PUT response envelope kept minimal: {\"updated_at\": <ISO>} only (Claude's-discretion D allows omitting echoed nodes/edges)"
  - "end_headers() stripped of all CORS; _cors_headers() is the single ACAO source — also added to _send_text/_send_html which previously had none"
  - "do_OPTIONS Max-Age now emitted unconditionally for loopback origins (the deleted def #1 was the only tree-specific Max-Age path)"

patterns-established:
  - "Atomic-write helper pattern for any future on-disk JSON state in lib/api/"
  - "Loopback-only single-source CORS that all response helpers share via _cors_headers()"

requirements-completed: []

# Metrics
duration: 6min
completed: 2026-06-02
---

# Phase INV-01 Plan 01: /api/v1/tools CRUD backend + hardened HTTP surface Summary

**Traversal-safe, atomically-written per-project workflow CRUD (GET/PUT/DELETE) over a JSON blob on disk, plus do_PUT/do_DELETE write methods and a single-source loopback-only CORS fix that unblocks the :8090 → :8765 cross-origin fetch.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-06-02T04:21:40Z
- **Completed:** 2026-06-02T04:27:43Z
- **Tasks:** 3 (Task 1 was TDD: RED → GREEN)
- **Files modified:** 4 (2 created, 2 edited)

## Accomplishments
- New `lib/api/tools.py` CRUD module mirroring `projects.py`'s transport-agnostic `handle_*(handler)` + generic no-leak 500 shape, with a strict slug trust boundary, atomic lock-free write, and the D-05 missing-file empty-200 contract.
- Daemon wired: `from . import tools` registered, GET routed as an explicit return-terminated branch (NOT via the returnless `API_V1_ROUTES`), and brand-new auth-gated `do_PUT` (413 body cap + 400 JSON-parse, stashes `_json_body`) and `do_DELETE` methods.
- CORS bug fixed centrally: the duplicate `Access-Control-Allow-Origin` (`end_headers()` `*` vs `_send_json` echo) collapsed to one loopback-only source via a shared `_cors_headers()`; the two `do_OPTIONS` defs collapsed into one advertising `GET, POST, PUT, DELETE, OPTIONS`.
- Verified live against a scratch daemon: 11/11 end-to-end checks pass including all five mitigated threats (traversal 400, non-loopback origin denied ACAO, 413 oversized body, 400 malformed JSON, nothing written outside `workflows/`).

## Task Commits

Each task was committed atomically (hooks on, no `--no-verify`):

1. **Task 1 (TDD RED): failing tests for /api/v1/tools CRUD** - `63b5624` (test)
2. **Task 1 (TDD GREEN): implement /api/v1/tools CRUD module** - `f70e00a` (feat)
3. **Task 2: wire /api/v1/tools into daemon (GET branch, do_PUT, do_DELETE)** - `af2a9b2` (feat)
4. **Task 3: single-source loopback CORS + collapse duplicate do_OPTIONS** - `51deb7a` (fix)

_Task 1 is TDD so it has two commits (test → feat). No refactor commit was needed — the GREEN implementation was already clean._

## Files Created/Modified
- `lib/api/tools.py` (new) — `handle_get/handle_put/handle_delete` + `_valid_slug` regex gate + `_write_atomic` (tmpfile/fsync/os.replace) + `_fail_500`; root from `config.home()`.
- `tests/test_api_tools.py` (new) — 23 hermetic tests (FakeHandler recording (obj,status); INVISIBLE_HOME→tmp_path): GET empty-200/round-trip, PUT ISO updated_at + atomic no-tmp-leftover + list-validation 400, DELETE 200/404, parametrized slug-reject (traversal/uppercase/length) with no-write assertion, valid-slug acceptance.
- `lib/api/__init__.py` (edit) — one `from . import tools` line appended to the bottom import block (D-08).
- `bin/invisible-dashboard` (edit) — `from api import tools`; GET `/api/v1/tools` branch; new `do_PUT`/`do_DELETE`; `_cors_headers()` single source wired into `_send_json`/`_send_text`/`_send_html`/`do_OPTIONS`; first `do_OPTIONS` deleted, survivor advertises all verbs; stale "everything is GET / no writes" docstring corrected; orphaned `from http import HTTPStatus` import removed.

## Decisions Made
- **Three handlers, not one dispatcher** — matches the existing registry/route style and the `projects.py` analog.
- **`_json_body` body hand-off** — `do_PUT` parses the request body (reusing `do_POST`'s cap + parse) and stashes it on `self._json_body`; `tools.handle_put` reads the same attribute. Identical identifier verified in both files.
- **Minimal PUT envelope** — returns only `{"updated_at": <ISO>}` (D allows Claude's discretion on extra keys); GET is the read path for nodes/edges.
- **`_cors_headers()` as the single CORS source** — rather than leaving CORS in `end_headers()`, I removed it there and centralized the loopback echo in one helper called by all response helpers. This also fixed a latent gap: `_send_text`/`_send_html` previously emitted NO loopback ACAO of their own (they relied on the `end_headers()` wildcard), so removing the wildcard without this would have stripped their CORS.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed orphaned `from http import HTTPStatus` import**
- **Found during:** Task 3 (CORS / do_OPTIONS collapse)
- **Issue:** `HTTPStatus.NO_CONTENT` was used only inside the first `do_OPTIONS` def, which D-12 directs deleting. After deletion the import became unused — flake8 (installed in this env) would flag it F401, a lint finding introduced by my own edit.
- **Fix:** Deleted the `from http import HTTPStatus` line; the surviving `do_OPTIONS` uses the literal `204` (matching the original second def's style).
- **Files modified:** bin/invisible-dashboard
- **Verification:** `python3 -m flake8 --select=F bin/invisible-dashboard` returns no errors; `py_compile` clean; daemon serves correctly in the live E2E.
- **Committed in:** `51deb7a` (Task 3 commit)

**2. [Rule 2 - Missing Critical] Added loopback ACAO to `_send_text` / `_send_html`**
- **Found during:** Task 3 (CORS single-source)
- **Issue:** D-11 directs removing the wildcard ACAO from `end_headers()`. `_send_text` and `_send_html` had NO ACAO of their own — they depended entirely on the `end_headers()` wildcard. Removing it without compensating would leave text/HTML responses with zero CORS, breaking any cross-origin text response (e.g. 404/healthz/HTML) the browser reads. The plan's PATTERNS (lines 215-216) explicitly flagged this ("add the same loopback-gated echo block to _send_text/_send_html if removing it from end_headers() would otherwise leave them with no ACAO").
- **Fix:** Introduced a shared `_cors_headers()` helper and called it from `_send_json`, `_send_text`, `_send_html`, and `do_OPTIONS` so every response carries exactly one loopback-only ACAO.
- **Files modified:** bin/invisible-dashboard
- **Verification:** Live E2E asserts exactly one ACAO on a GET (which uses `_send_json`) and zero ACAO for a non-loopback origin; manual reasoning + the single-source helper guarantee text/HTML now also carry it.
- **Committed in:** `51deb7a` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking lint cleanup, 1 missing-critical CORS coverage)
**Impact on plan:** Both were anticipated by the plan/PATTERNS guidance and are necessary for correctness (no dead import; no response left without its CORS header). No scope creep — both confined to `bin/invisible-dashboard` within the plan's owned edits.

## Issues Encountered
None. RED failed as expected (ImportError — `tools` not importable), GREEN passed on first implementation, all acceptance criteria and the full live E2E passed without rework.

## Known Stubs
None. The empty `{"nodes":[],"edges":[],"updated_at":null}` body for a never-saved project is the intentional D-05 contract (so the canvas loads cleanly), not a stub.

## Threat Surface
All write/CORS surface introduced is covered by the plan's `<threat_model>` (T-INV01-01..06) and verified live: traversal → 400 (T-01), 413 oversized body (T-02), `_auth_ok()` first on do_PUT/do_DELETE (T-03), single loopback-only ACAO + no credentials (T-04), generic no-leak 500 (T-05), `os.replace` atomic single-writer (T-06 accepted). No new undocumented trust-boundary surface introduced — no threat flags.

## User Setup Required
None - no external service configuration required. (Pure stdlib; no new packages, no env vars, no accounts.)

## Next Phase Readiness
- Backend contract is live and hardened: Plan 01-02 (tools.jsx frontend) can now `fetch(API_BASE + "/api/v1/tools?project=...")` for load and PUT for debounced autosave. The CORS fix unblocks the :8090 → :8765 cross-origin call (single ACAO, OPTIONS permits PUT/DELETE).
- The `workflows/` dir is created on first write under `config.home()`; Plan 01-02's D-16 (`.gitignore` add) should ensure per-machine `workflows/` is not committed when the daemon runs with `INVISIBLE_HOME=$(pwd)` in a worktree.
- No blockers.

---
*Phase: INV-01-api-v1-tools-crud-tools-page-wired*
*Completed: 2026-06-02*
