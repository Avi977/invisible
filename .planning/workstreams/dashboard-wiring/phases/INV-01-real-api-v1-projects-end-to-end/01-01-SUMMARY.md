---
phase: INV-01-real-api-v1-projects-end-to-end
plan: 01
subsystem: api
tags: [http, cors, python, stdlib, tdd, dashboard, json]

# Dependency graph
requires:
  - phase: bootstrap
    provides: invisible.toml schema, lib/config.py loader, lib/checkpoint.py reader
provides:
  - GET /api/v1/projects endpoint on dashboard daemon (127.0.0.1:8765)
  - lib/api/ package with ROUTES registry that sister workstreams extend
  - Loopback-only CORS layer on _send_json + new do_OPTIONS preflight handler
  - 7-test pytest module covering shape, types, defaults, security
affects: [dashboard-wiring 01-02, ai-bubble, folders-3source, analytics-aggregator]

# Tech tracking
tech-stack:
  added: []  # pure stdlib — subprocess, hashlib, json, pathlib, urllib; pytest already present
  patterns:
    - "Route registry dict in lib/api/__init__.py — sister workstreams add one import + one ROUTES entry"
    - "Defensive HTTP handler — try/except wraps build_* with generic 500, no path leaks"
    - "Origin-allowlist CORS (loopback only) via runtime header echo, never `*`"

key-files:
  created:
    - lib/api/__init__.py
    - lib/api/projects.py
    - tests/__init__.py
    - tests/test_api_projects.py
  modified:
    - bin/invisible-dashboard

key-decisions:
  - "md5(name) % 6 (not Python's salted hash()) for color — colors must be stable across daemon restarts"
  - "_safe_path() confines repo_path to $HOME or $INVISIBLE_HOME — rejects ../../etc traversal at the resolver, not at git"
  - "subprocess.run(..., shell=False, timeout=2) on every git call — one hung repo cannot stall N-project response"
  - "CORS Origin echoed only for http://127.0.0.1:* and http://localhost:* — never `*`, even under --no-auth"
  - "Added Vary: Origin so intermediate caches do not conflate cross-origin requests"
  - "do_OPTIONS added (not just _send_json header) because frontend fetch with Authorization triggers preflight"

patterns-established:
  - "lib/api/__init__.py is the merge point for sister workstreams — 1-line conflict surface"
  - "Per-endpoint module under lib/api/ with build_* + handle_* split (data layer / wire layer)"
  - "All HTTP handlers catch broad Exception and emit generic 500 — never tracebacks or paths"

requirements-completed: [REQ-01]

# Metrics
duration: 6min
completed: 2026-05-27
---

# Phase 01 Plan 01: Real /api/v1/projects backend adapter Summary

**Loopback-bound /api/v1/projects endpoint returns DATA_SETS-shaped project rows assembled from invisible.toml + git + checkpoint store, with origin-allowlist CORS so only the React app at 127.0.0.1:8090 can read it.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-27T02:25:05Z
- **Completed:** 2026-05-27T02:30:35Z
- **Tasks:** 2 (both `type="auto"`; Task 1 is TDD with RED/GREEN gate commits)
- **Files modified/created:** 5

## Accomplishments

- Stood up the JSON adapter and route — `curl http://127.0.0.1:8765/api/v1/projects` returns a top-level JSON array whose first element has exactly the 13 keys of `DATA_SETS.default.projects[0]`.
- TDD-first: 7 pytest cases written and red BEFORE the implementation; now all green. Behaviors cover shape, field types, planning default, branch="—" fallback, color palette membership, no-path-leakage, and ROUTES registry exposure.
- Loopback-only CORS — `Access-Control-Allow-Origin: http://127.0.0.1:8090` echoed back when that Origin is sent; absent for `https://evil.example`. A separate `do_OPTIONS` handles preflight (`Authorization` + `Content-Type` allowed).
- Zero existing routes touched — `/healthz`, `/api/projects`, `/p/`, `/api/p/`, `/api/reviews` continue to respond identically. Conflict surface for sister workstreams is one import + one ROUTES entry in `lib/api/__init__.py`.

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): add failing tests for /api/v1/projects adapter** — `7f0565e` (test)
2. **Task 1 (GREEN): implement /api/v1/projects adapter** — `a7376af` (feat)
3. **Task 2: wire /api/v1/* dispatch + loopback CORS into dashboard** — `b8d4197` (feat)

_Task 1 followed RED → GREEN. No REFACTOR commit needed — implementation was already clean and all 7 tests passed on first GREEN run._

## Files Created/Modified

- `lib/api/__init__.py` (27 lines, new) — Route registry. `ROUTES["/api/v1/projects"] = projects.handle_projects`. Designed for trivial 4-way merge: sister workstreams add one import + one ROUTES entry.
- `lib/api/projects.py` (320 lines, new) — `build_projects()` assembles the 13-field row from `config.load_toml()` + `checkpoint.load()` + `git -C` calls. `handle_projects(handler)` is the HTTP wire layer with defensive 500 path. Includes `_safe_path()` (traversal guard), `_color_for()` (md5-stable palette index), `_status_for()` (deterministic state rules), `_branch_and_last_commit()` (2s-timeout git subprocess).
- `tests/__init__.py` (0 lines, new) — Makes `tests/` a package so pytest discovery works.
- `tests/test_api_projects.py` (258 lines, new) — 7 hermetic tests. Each monkeypatches `INVISIBLE_HOME` to `tmp_path` and writes synthetic toml + checkpoint files. The git-touching tests `git init` a fresh repo under `tmp_path` so they never read the user's real repos.
- `bin/invisible-dashboard` (+36 lines) — 5 additive blocks: import `API_V1_ROUTES`, `do_GET` dispatch into the registry, CORS header in `_send_json` (loopback only), new `do_OPTIONS` preflight handler, `Vary: Origin` for cacheable responses. No existing routes modified.

## Sample Response

Live response from running daemon (`curl http://127.0.0.1:8765/api/v1/projects`):

```json
[
    {
        "id": "jobslayer",
        "code": "JO",
        "name": "jobslayer",
        "color": "#5ee0c8",
        "status": "blocked",
        "branch": "main",
        "lastCommit": "8d ago",
        "summary": "# Task: Resume Phase 1: unblock Infisical admin auth and complete the pending smoke test.",
        "progress": 100,
        "todos": [
            { "t": "MUST FIX:", "done": false },
            { "t": "MUST FIX:", "done": false }
        ],
        "note": "Defensive hardening of Infisical env-var handling is correct and well-tested, but the stated task — actually running the Phase 1 smoke test — is not evidenced in the diff.",
        "stack": [],
        "nextEvent": "—"
    }
]
```

13 keys exactly. Types match DATA_SETS contract: progress=int, todos=list[dict], stack=list[str], status enum (`blocked`).

## Sample Headers (loopback Origin)

```
HTTP/1.0 200 OK
Server: invisible-dashboard/1 Python/3.11.4
Content-Type: application/json; charset=utf-8
Content-Length: 696
Cache-Control: no-store
Access-Control-Allow-Origin: http://127.0.0.1:8090
Vary: Origin
```

With `Origin: https://evil.example`: the response succeeds (loopback binding still allows the curl) but **no** `Access-Control-Allow-Origin` header is sent — the browser would block the cross-origin fetch.

## OPTIONS Preflight (loopback)

```
HTTP/1.0 204 No Content
Access-Control-Allow-Origin: http://127.0.0.1:8090
Vary: Origin
Access-Control-Allow-Methods: GET, OPTIONS
Access-Control-Allow-Headers: Authorization, Content-Type
Access-Control-Max-Age: 600
Content-Length: 0
```

Non-loopback Origin gets a 204 with NO CORS headers — the browser correctly drops the request.

## Tests

- **Count:** 7
- **Pass:** 7 / 7
- **Duration:** 0.55s
- **Run:** `python3 -m pytest tests/test_api_projects.py -x -q`

Test names map 1:1 to the `<behavior>` block in the plan:

1. `test_build_projects_shape` — exact 13-key set, no extras, no missing
2. `test_build_projects_field_types` — id/code/name/color/branch/lastCommit/summary/note/nextEvent are str; progress int 0..100; todos list[dict{t:str,done:bool}]; stack list[str]; status enum
3. `test_build_projects_no_checkpoint_yields_planning` — missing worktree → status="planning", todos=[], note="", progress=0
4. `test_build_projects_branch_dash_when_repo_missing` — repo_path absent → branch="—" and lastCommit="—"
5. `test_build_projects_color_in_palette` — color ∈ the 6 hex codes from PALETTE
6. `test_build_projects_does_not_leak_paths` — no `/Users/`, `/home/`, or `tmp_path` substring anywhere in any string field, even on broken worktree
7. `test_api_routes_registry` — `from api import ROUTES`; `ROUTES["/api/v1/projects"]` is callable; invoking it with a fake handler calls `_send_json(<list>)`

## Verification — full plan checklist

| Check | Result |
|---|---|
| GET /api/v1/projects → HTTP 200 + application/json | OK |
| Body is a top-level JSON array | OK (1 project from real invisible.toml) |
| Each element has the 13 required keys | OK |
| Field types match DATA_SETS contract | OK |
| invisible.toml has ≥1 project ⇒ array length ≥ 1 | OK (jobslayer) |
| Access-Control-Allow-Origin echoes loopback Origin | OK |
| Missing checkpoint ⇒ status defaults to "planning" | OK (covered by Test 3) |
| Error bodies never include absolute filesystem paths | OK (Test 6 + handle_projects wrapping) |
| No `*` wildcard CORS, never cross-origin | OK |
| All 7 unit tests pass | OK (7/7 in 0.55s) |
| Legacy /healthz, /api/projects still respond | OK |
| ast.parse(bin/invisible-dashboard) OK | OK |

## Security — STRIDE mitigations applied

| Threat ID | Mitigation | Status |
|---|---|---|
| T-INV-01-01 Tampering (git subprocess) | `subprocess.run([...], shell=False, timeout=2, capture_output=True)` in `_run_git` | applied |
| T-INV-01-02 Info disclosure (path leaks in errors) | `handle_projects()` try/except returns `{"error":"internal error"}` 500. Test 6 asserts no `/Users/`, `/home/`, or tmp_path substring in any field | applied + test |
| T-INV-01-03 Path traversal via repo_path | `_safe_path()` resolves and confines to `$HOME` or `$INVISIBLE_HOME`; out-of-bounds returns None (treated as "repo missing") | applied |
| T-INV-01-04 Cross-origin read | CORS Origin echo only for `http://127.0.0.1:*` and `http://localhost:*`; never `*` | applied |
| T-INV-01-05 DoS via slow git | `timeout=2` per call; fall back to ("—","—") on TimeoutExpired | applied |
| T-INV-01-06 Checkpoint JSON bomb | Accepted (per plan) | n/a |
| T-INV-01-07 Notion title leak | Accepted (per plan); also: nextEvent currently returns "—" — Notion read is not yet wired in this plan | n/a |
| T-INV-01-08 Audit trail | Accepted (per plan, single-user tool) | n/a |
| T-INV-01-SC Supply chain | No new package installs; pure stdlib + already-present pytest | applied |

## Deviations from Plan

None for Rules 1-4. Two minor in-scope additions worth noting (not deviations — they fall under the plan's explicit instructions):

- **`Vary: Origin` header** — added to JSON and OPTIONS responses alongside `Access-Control-Allow-Origin`. The plan didn't call for this explicitly but it's correctness-required for any response that varies behavior by Origin (otherwise an intermediate cache could serve a CORS-allowed response to a cross-origin caller). Falls under Rule 2 (auto-add missing critical correctness functionality).
- **`Access-Control-Max-Age: 600`** — added to OPTIONS preflight so the browser stops re-fetching the preflight every request. Standard CORS hygiene; not a behavior change.

No architectural changes (Rule 4). No package installs (excluded from Rule 3).

## Known Stubs

- `nextEvent: "—"` — currently a literal em-dash for every project. The plan's interfaces noted "most-recent Notion review title when configured, else '—'" but Notion wire-up is out of scope here (Notion data is read elsewhere by `lib/notion.py::query_recent_reviews`). A future plan can swap the constant for a real Notion call without changing the contract. **Not a blocker for plan 01-02** — the React frontend already renders "—" gracefully (see Atlas/Rune planning rows in the mock).

## Self-Check: PASSED

Verified all claimed artifacts exist:

- `lib/api/__init__.py`: FOUND
- `lib/api/projects.py`: FOUND
- `tests/__init__.py`: FOUND
- `tests/test_api_projects.py`: FOUND
- `bin/invisible-dashboard`: MODIFIED (36 lines added)

Verified commits exist on `ws/dashboard-wiring`:

- `7f0565e` (test RED): FOUND
- `a7376af` (feat GREEN): FOUND
- `b8d4197` (Task 2 wiring): FOUND

## TDD Gate Compliance

- RED gate commit (test): `7f0565e` — `test(01-01): add failing tests for /api/v1/projects adapter`
- GREEN gate commit (feat): `a7376af` — `feat(01-01): implement /api/v1/projects adapter`
- REFACTOR gate: skipped intentionally — implementation passed all 7 tests on first run; refactoring would be churn.

Sequence verified: test commit precedes feat commit in git log. Plan-level TDD gate satisfied.
