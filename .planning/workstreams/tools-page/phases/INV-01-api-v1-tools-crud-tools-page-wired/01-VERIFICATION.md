---
phase: INV-01-api-v1-tools-crud-tools-page-wired
verified: 2026-06-01T00:00:00Z
status: passed
score: 16/16 must-haves verified
overrides_applied: 0
re_verification:
  none: true
---

# Phase INV-01: /api/v1/tools CRUD + Tools page wired — Verification Report

**Phase Goal:** The Tools page (n8n-style node canvas) reads + writes real workflow definitions per project, persisted to `~/.invisible/workflows/<project>.json`, replacing the `TOOL_WORKFLOWS` mock in `frontend/data.jsx`.
**Verified:** 2026-06-01 (initial verification)
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

The phase goal is achieved in the codebase. The Tools canvas no longer reads any static mock; it fetches each project's workflow from `GET /api/v1/tools` on switch and autosaves edits via a debounced `PUT`, persisted atomically to `config.home()/workflows/<slug>.json`. The static `TOOL_WORKFLOWS` mock is fully removed. Verified by reading the actual source of `lib/api/tools.py`, `bin/invisible-dashboard`, `frontend/pages/tools.jsx`, `frontend/data.jsx`, plus 30/30 hermetic tests passing and a full grep/AST sweep — not by trusting the SUMMARYs.

### Observable Truths (the 16 CONTEXT decisions = the contract)

| #    | Truth | Status | Evidence |
| ---- | ----- | ------ | -------- |
| D-01 | Persist at `config.home()/workflows/<project>.json`, root from `config.home()` (never hardcoded) | ✓ VERIFIED | `tools.py:82-88` `_target_for()` returns `config.home() / "workflows" / f"{project}.json"`; grep: 0 `~/.invisible` literals, 7 `config.home()` uses |
| D-02 | Atomic lock-free single-writer (tmpfile same dir + `os.replace`), `workflows/` dir created first write with `mkdir(parents=True, exist_ok=True)` | ✓ VERIFIED | `tools.py:91-112` `_write_atomic()`: `mkdir(parents=True, exist_ok=True)` → `tempfile.mkstemp(dir=same)` → `fsync` → `os.replace`; tmp unlinked on error. Test `test_put_leaves_no_tmp_file` passes |
| D-03 | `project` validated as strict slug `^[a-z0-9][a-z0-9_-]{0,63}$` BEFORE any path build; traversal/empty/dot/slash/encoded/uppercase → 400; nothing escapes `workflows/` | ✓ VERIFIED | `_SLUG_RE` compiled at module level (`tools.py:55`); `_valid_slug()` called as the FIRST action in all three handlers before any `_target_for()`. Parametrized tests (`"", ".", "..", "../etc", "a/b", "A", "foo%2e", "-leading", 65-char`) all assert 400 + no dir mutation — pass |
| D-04 | `tools.py` mirrors `projects.py` — transport-agnostic `handle_*(handler)` → `handler._send_json(obj,status)`; every handler try/except → generic `{"error":"internal error"}` 500, no path/traceback leak | ✓ VERIFIED | `handle_get/put/delete` each wrap IO in try/except → `_fail_500()` (`tools.py:115-124`) which logs only `type(exc).__name__` to stderr and sends `{"error":"internal error"}` 500 |
| D-05 | GET returns `{nodes,edges,updated_at}`; missing file → 200 `{nodes:[],edges:[],updated_at:null}` (NOT 404); missing/invalid project → 400 | ✓ VERIFIED | `handle_get` (`tools.py:132-162`): missing file → 200 empty envelope; present → parsed envelope; invalid slug → 400. Tests `test_get_missing_project_returns_empty_200` + `test_get_after_put_round_trips` pass |
| D-06 | PUT accepts `{nodes:[...],edges:[...]}`, validates both lists, stamps `datetime.now(timezone.utc).isoformat()`, writes atomically, returns `{"updated_at":...}`; malformed → 400; oversized → 413 | ✓ VERIFIED | `handle_put` (`tools.py:165-193`) list-validates → 400, ISO stamp, atomic write, returns `{"updated_at":...}`. 413 cap enforced in daemon `do_PUT` (`_MAX_POST_BYTES=32_768`). Tests for ISO `updated_at`, nodes-not-list 400, edges-not-list 400 pass |
| D-07 | DELETE removes file → 200 `{"deleted":true}`; missing → 404 | ✓ VERIFIED | `handle_delete` (`tools.py:196-214`): `unlink()` → 200 `{"deleted":True}`; `FileNotFoundError` → 404. Tests `test_delete_existing_file_returns_deleted_true` + `test_delete_missing_file_returns_404` pass |
| D-08 | Registered via `from . import tools` in `__init__.py` bottom block AND imported in `bin/invisible-dashboard` | ✓ VERIFIED | `lib/api/__init__.py:40` `from . import tools`; `bin/invisible-dashboard:65` `from api import tools`. Runtime import check confirms `handle_get/put/delete` reachable |
| D-09 | GET route added in `do_GET` as explicit return-terminated branch (NOT via `API_V1_ROUTES`) | ✓ VERIFIED | `bin/invisible-dashboard:401-403`: `if path == "/api/v1/tools": tools.handle_get(self); return` — line 403 is `return`. Not present in the `API_V1_ROUTES` dict (`__init__.py:23-25` only has `/api/v1/projects`) |
| D-10 | New `do_PUT`/`do_DELETE` each call `_auth_ok()` first; `do_PUT` 413 cap + 400 JSON-parse; both dispatch `/api/v1/tools`, 404 otherwise, last-resort try/except → 500 keeping traceback out of body | ✓ VERIFIED | `do_PUT` (`:502-565`) and `do_DELETE` (`:568-599`): `_auth_ok()` is the first gate (401 on fail); `do_PUT` enforces `_MAX_POST_BYTES`→413 and JSON-parse→400, stashes `self._json_body` (`:550`); both 404 unknown paths; last-resort `except` → `traceback.print_exc()` (stderr) + `{"error":"server_error"}` 500. `_json_body` identifier matches both files (3 occurrences each) |
| D-11 | Single-source CORS — exactly ONE `Access-Control-Allow-Origin` per response; duplicate-ACAO bug eliminated; loopback-only echo kept as single source | ✓ VERIFIED | `end_headers()` (`:236-237`) now bare `super().end_headers()` — no ACAO. `_cors_headers()` (`:239-252`) echoes only `http://127.0.0.1:*`/`http://localhost:*`, called by `_send_json`/`_send_text`/`_send_html`/`do_OPTIONS`. grep: 0 bare `"*"` ACAO |
| D-12 | Two duplicate `do_OPTIONS` collapsed into one advertising `GET, POST, PUT, DELETE, OPTIONS`; loopback gate + Max-Age preserved | ✓ VERIFIED | AST: exactly 1 `do_OPTIONS` (`:407-434`); advertises `GET, POST, PUT, DELETE, OPTIONS` (`:428-429`), loopback gate + `Access-Control-Max-Age: 600` preserved |
| D-13 | `tools.jsx` loads via `fetch(API_BASE + "/api/v1/tools?project=" + projId)` on switch (folders.jsx pattern), seeding canvas from fetched `{nodes,edges}` instead of mock | ✓ VERIFIED | `tools.jsx:307-347` `[projId]`-keyed effect with `API_BASE` + headers + `cancelled` flag; sets `wf` from `body.nodes`/`body.edges` (`:326-330`); fed to `ToolsCanvas` as `initialNodes={wf.nodes}`/`initialEdges={wf.edges}` (`:465-466`) |
| D-14 | Autosave — debounce 1s then PUT on add/drag-end/wire change; cancel/flush pending timer on switch (A never lands on B); footer saving…/saved Ns ago/error | ✓ VERIFIED | `handleCanvasChange` (`:351-377`): `clearTimeout`+`setTimeout(...,1000)`, `method:"PUT"`, captures `projIdRef.current` at fire-time, ignores stale response. Load-effect cleanup `clearTimeout`s pending save on switch (`:342-346`). Seed-skip guard (`:92-95`) stops GET echoing back as PUT. Footer states saving/saved/error/loading/load-failed (`:414-430`) |
| D-15 | `TOOL_WORKFLOWS` mock removed entirely from `data.jsx` (const + window token); `ProjectPicker` preview updated to not read the deleted mock | ✓ VERIFIED | grep: `TOOL_WORKFLOWS` count = 0 in BOTH `data.jsx` and `tools.jsx`; no `const TOOL_WORKFLOWS`. Siblings intact (`Object.assign(window,...)` keeps `ANALYTICS`/`DATA_SETS`/`FOLDERS`/`TERM_CONTEXT`/`fetchProjects`). `ProjectPicker` shows neutral "open to view" (`tools.jsx:266`) |
| D-16 | `workflows/` added to `.gitignore` | ✓ VERIFIED | `.gitignore:39` = `workflows/` (grep `^workflows/` → 1) |

**Score:** 16/16 truths verified

### ROADMAP Success Criteria (the roadmap contract)

| # | Success Criterion | Status | Maps to |
| - | ----------------- | ------ | ------- |
| 1 | GET returns `{nodes,edges,updated_at}` (200 empty for never-saved) | ✓ VERIFIED | D-05 |
| 2 | PUT writes atomically (tmpfile + rename), returns new `updated_at` | ✓ VERIFIED | D-02, D-06 |
| 3 | DELETE removes file (or 404 if missing) | ✓ VERIFIED | D-07 |
| 4 | Canvas loads on switch, saves debounced 1s, renders saving/saved footer | ✓ VERIFIED | D-13, D-14 |
| 5 | Switching projects loads that project's workflow without bleeding state | ✓ VERIFIED | D-14 (cancel-on-switch + fire-time projId capture + `key={projId}` remount) |

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `lib/api/tools.py` | GET/PUT/DELETE handlers + atomic write + slug validator | ✓ VERIFIED | 215 lines, all three handlers substantive, `_write_atomic`, `_SLUG_RE` gate, `config.home()`-derived path, generic 500 |
| `lib/api/__init__.py` | tools module registration | ✓ VERIFIED | `from . import tools` in bottom block (`:40`) |
| `bin/invisible-dashboard` | do_PUT, do_DELETE, GET branch, single-source CORS, collapsed do_OPTIONS | ✓ VERIFIED | All present and return-terminated; `py_compile` clean; imports OK |
| `tests/test_api_tools.py` | hermetic GET/PUT/DELETE + traversal + envelope tests | ✓ VERIFIED | 273 lines, FakeHandler, INVISIBLE_HOME→tmp_path, parametrized traversal + valid-slug cases |
| `frontend/pages/tools.jsx` | fetch-on-switch, debounced PUT, footer, mock-free | ✓ VERIFIED | 476 lines; all wiring present; 0 `TOOL_WORKFLOWS` refs |
| `frontend/data.jsx` | `TOOL_WORKFLOWS` removed (const + window) | ✓ VERIFIED | 0 occurrences; siblings intact |
| `.gitignore` | `workflows/` ignore entry | ✓ VERIFIED | line 39 |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `do_GET` | `tools.handle_get` | explicit return-terminated branch | ✓ WIRED | `:401-403`, line 403 `return` |
| `do_PUT` | `tools.handle_put` | auth-gated + body-capped dispatch + `_json_body` hand-off | ✓ WIRED | `:550` stash, `:554-556` dispatch; identifier matches `tools.py` |
| `do_DELETE` | `tools.handle_delete` | auth-gated dispatch | ✓ WIRED | `:588-590` |
| `tools.py` | `config.home() / workflows` | path derivation | ✓ WIRED | `_target_for` `:88` |
| `tools.jsx` | `GET /api/v1/tools` | fetch in `[projId]` effect with cancellation | ✓ WIRED | `:317` `fetch(API_BASE + "/api/v1/tools" + qs)` |
| `tools.jsx` | `PUT /api/v1/tools` | debounced autosave w/ flush-on-switch | ✓ WIRED | `:359-363` `method:"PUT"`; cleanup `clearTimeout` `:345` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `tools.jsx` ToolsCanvas | `wf.nodes` / `wf.edges` | `setWf({nodes:body.nodes, edges:body.edges})` from `GET /api/v1/tools` response (`:326-330`) | Yes — populated from live API; empty `[]` only on the error/never-saved branch (the intentional D-05 contract) | ✓ FLOWING |
| `tools.py` GET | file contents | `json.load(target)` from `config.home()/workflows/<slug>.json` (written by PUT) | Yes — real disk round-trip (verified by `test_get_after_put_round_trips`) | ✓ FLOWING |

The `{nodes:[],edges:[],updated_at:null}` empty fallback is the D-05 missing-file contract (canvas must load cleanly for never-saved projects), not a hollow stub — a real PUT populates it and a subsequent GET round-trips the exact data.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Backend CRUD + traversal + envelope (hermetic) | `pytest tests/test_api_tools.py tests/test_api_projects.py -q` | `30 passed in 0.59s` | ✓ PASS |
| Daemon imports + tools handlers reachable | `python3 -c "from api import tools; ..."` | `tools attrs: True` | ✓ PASS |
| Daemon syntax sane (no server start — port 8765 contended) | `python3 -m py_compile bin/invisible-dashboard` | clean | ✓ PASS |
| Exactly one `do_OPTIONS` advertising all verbs | AST + grep | 1 def, advertises `GET, POST, PUT, DELETE, OPTIONS` | ✓ PASS |
| No bare wildcard ACAO | grep `Access-Control-Allow-Origin", "*"` | 0 | ✓ PASS |

Live daemon NOT started: port 8765 is contended by 6 parallel sibling sessions (per verification guidance). Backend behaviors verified via hermetic tests; CORS/route behaviors verified via source + AST. The live cross-origin browser E2E was already driven by the orchestrator and recorded in 01-02-SUMMARY.md (see Runtime Checkpoint below).

### Probe Execution

No conventional `scripts/*/tests/probe-*.sh` exist and neither PLAN declares a probe path. Probe execution N/A — the phase's runnable verification is the hermetic pytest suite (run above, 30 passed).

### Requirements Coverage

No REQ-IDs are mapped to this phase (both PLANs declare `requirements: []`; ROADMAP maps none). The contract is the 5 ROADMAP Success Criteria + the 16 CONTEXT decisions D-01..D-16 — all verified above. No orphaned requirements.

### Threat-Model Mitigations (from 01-01 `<threat_model>`)

| Threat | Mitigation | Status |
| ------ | ---------- | ------ |
| T-INV01-01 Path traversal | D-03 slug regex BEFORE path build → 400 | ✓ PRESENT (gate is first action in every handler; parametrized traversal tests pass) |
| T-INV01-02 Unbounded body DoS | `_MAX_POST_BYTES=32_768` → 413 in `do_PUT` | ✓ PRESENT (`:530-536`) |
| T-INV01-03 Auth bypass on writes | `_auth_ok()` first in `do_PUT`/`do_DELETE` | ✓ PRESENT (`:514`, `:578`) |
| T-INV01-04 CORS over-permissiveness | D-11/D-12 loopback-only single ACAO, no `*`, no credentials | ✓ PRESENT (`_cors_headers` `:239-252`; 0 wildcard) |
| T-INV01-05 Path/traceback leak | generic `{"error":"internal error"}`/`{"error":"server_error"}` 500, traceback to stderr only | ✓ PRESENT (`_fail_500` + daemon last-resort guards) |
| T-INV01-06 Concurrent partial write | accepted: `os.replace` atomic single-writer | ✓ PRESENT (atomic rename; multi-writer out of scope by design) |

All HIGH threats (-01, -03, -04) are mitigated with the specified controls present in source. Block-on-HIGH satisfied.

### Anti-Patterns Found

None. Scan of all modified files (`lib/api/tools.py`, `bin/invisible-dashboard`, `frontend/pages/tools.jsx`, `frontend/data.jsx`, `tests/test_api_tools.py`) found zero debt markers (TBD/FIXME/XXX/HACK/TODO/PLACEHOLDER) and zero stub shapes. The single `return null` in `tools.jsx:178` is a legitimate SVG-edge render guard (skip an edge whose endpoints are absent), not a stub.

### Scope Fence

Honored. Files touched across all phase commits: `.gitignore`, `bin/invisible-dashboard`, `frontend/data.jsx`, `frontend/pages/tools.jsx`, `lib/api/__init__.py`, `lib/api/tools.py`, `tests/test_api_tools.py` — exactly the owned + edit-lightly set plus the allowed test file. Working tree is clean. NOTHING in the MUST-NOT-TOUCH list was modified (no sibling `frontend/pages/*.jsx`, no `ai-chat.jsx`, no sibling `lib/api/*.py`, no `src-tauri/`, no `bin/invisible-pty`, no `lib/pty_server.py`).

### Runtime Checkpoint (already executed by orchestrator)

01-02-PLAN Task 3 is a `checkpoint:human-verify` real-browser E2E. Per the verification guidance, port 8765 is contended by 6 sibling sessions, so this verifier did NOT start a live daemon/browser. The live cross-origin browser run was already driven by the orchestrator and recorded in 01-02-SUMMARY.md with PASS evidence for all five assertions: (1) GET-on-switch 200, `cors_error: null`; (2) single debounced PUT 200, footer → saved; (3) reload persistence (node survives full reload); (4) project switch Echo→Lumen shows 0 nodes (no bleed); (5) zero stray PUT after switch. Every code path that produces these behaviors is verified present in `tools.jsx`/daemon source above, so no outstanding human verification item remains for this phase.

### Gaps Summary

None. All 16 decisions (D-01..D-16) and all 5 ROADMAP Success Criteria are implemented and verified in the actual codebase: the backend CRUD module is substantive and hardened (slug-reject-before-path, atomic write, generic no-leak 500), the daemon is wired with auth-gated write methods + a single-source loopback CORS fix + a single do_OPTIONS advertising the write verbs, and the frontend fetches-on-switch + debounce-saves with a flush-on-switch guard while the `TOOL_WORKFLOWS` mock is fully removed. 30/30 hermetic tests pass, the scope fence is intact, and there are no anti-patterns or unresolved debt markers.

---

_Verified: 2026-06-01_
_Verifier: Claude (gsd-verifier)_
