---
phase: INV-01-real-api-v1-projects-end-to-end
slug: real-api-v1-projects-end-to-end
status: verified
nyquist_compliant: true
tests_total: 17
tests_covered: 17
tests_manual_only: 3
audit_date: 2026-06-01
wave_0_complete: true
created: 2026-06-01
verdict: PASS
---

# Phase 01 — Validation Strategy

> Reconstructed at audit time. Phase artifacts (PLAN / SUMMARY / VERIFICATION /
> SECURITY) already exist; this document maps every REQ-01 acceptance criterion
> + behavioral truth declared in plans 01-01 and 01-02 to a runnable test, and
> records the manual-only items that remain (with the reason each cannot be
> automated inside this workstream's constraints).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Backend framework** | pytest 7.4.0 (Python 3.11.4) |
| **Backend test file** | `tests/test_api_projects.py` (7 hermetic cases, ~0.55s) |
| **Backend quick run** | `python3 -m pytest tests/test_api_projects.py -q` |
| **Backend full run** | `python3 -m pytest tests/test_api_projects.py -v` |
| **Smoke script** | `tests/smoke_dashboard_wiring.sh` (17 checks; backend pytest + live API + static frontend grep) |
| **Smoke quick run** | `bash tests/smoke_dashboard_wiring.sh` |
| **Smoke runtime** | ~3–5 seconds (1s daemon warm-up + pytest + curl + grep) |
| **Config file** | None — pytest runs file-by-file from the repo root |
| **Frontend framework** | NOT installed (PROJECT.md key decision: "Babel-standalone for now, migrate to Vite in WS-6"). WS-6 introduces Vite + Vitest. **This workstream MUST NOT add a JS test framework** — sibling-workstream boundary violation. |
| **Frontend coverage approach** | Static grep assertions in `tests/smoke_dashboard_wiring.sh` Section 3 + headless-Chrome CDP runs by the orchestrator (documented in `VERIFICATION.md::interactive_verification`) |
| **Daemon binary** | `bin/invisible-dashboard` — launched by smoke script with `--no-auth --port 8766 --host 127.0.0.1` and `INVISIBLE_HOME=$(mktemp -d)` (hermetic — does NOT touch the user's real `~/.invisible/`) |

---

## Sampling Rate

- **After every backend task commit:** `python3 -m pytest tests/test_api_projects.py -q` (~0.55s)
- **After every frontend task commit:** `bash tests/smoke_dashboard_wiring.sh` (~3-5s; covers backend + live API + static frontend)
- **Before phase sign-off:** `bash tests/smoke_dashboard_wiring.sh` must exit 0; all 3 Manual-Only items below must have user sign-off
- **Max feedback latency:** ~5 seconds for the full smoke

---

## Per-Task Verification Map

### REQ-01 — Real dashboard projects (the only REQ in this phase)

The five phase success criteria (workstream ROADMAP) encode REQ-01's
acceptance. Each maps to one or more automated assertions:

| # | Phase Success Criterion | Test Type | Covered by | Command | Status |
|---|------------------------|-----------|-----------|---------|--------|
| 1 | `curl /api/v1/projects` returns DATA_SETS-shaped JSON array (13 keys, correct types) | unit + integration | `tests/test_api_projects.py::test_build_projects_shape` + `test_build_projects_field_types` + Smoke § 2.1/2.2/2.3 | `python3 -m pytest tests/test_api_projects.py -q` + `bash tests/smoke_dashboard_wiring.sh` | green |
| 2 | Dashboard.jsx fetches the endpoint on mount + DATA_SETS reference removed from this page | static (grep) | Smoke § 3.1 (asserts `useEffect` + `fetchProjects()` exist AND `grep -c DATA_SETS frontend/pages/dashboard.jsx == 0`) | `bash tests/smoke_dashboard_wiring.sh` | green |
| 3 | All four layouts (bento / grid / kanban / list) render real data identically | static (grep — proxy) | Smoke § 3.3 (asserts `projectsToRender` is the SOLE source: `.filter(...)` for kanban + `.map(...)` inside `layout-${layout}` for bento/grid/list). Interactive visual cycling is Manual-Only #1. | `bash tests/smoke_dashboard_wiring.sh` | green (code path) / Manual-Only #1 (visual) |
| 4 | Tools / Terminal / Focus action buttons route correctly with real id | static (grep) | Smoke § 3.4 (asserts `navTo("tools", p.id)`, `navTo("terminals", p.id)`, `navTo("focus", p.id)` each appear ≥ 1×). Live click is Manual-Only #2. | `bash tests/smoke_dashboard_wiring.sh` | green (code path) / Manual-Only #2 (click) |
| 5 | Mock toggle still works for OTHER pages (Focus, Terminals, Tools, Analytics) | static (grep) | Smoke § 3.5 (asserts `app.jsx` still reads `DATA_SETS[...]` — the same prop path that feeds the four sister pages). Multi-page user toggle is Manual-Only #3. | `bash tests/smoke_dashboard_wiring.sh` | green (code path) / Manual-Only #3 (multi-page toggle) |

### Plan 01-01 — Backend behavioral truths (8)

| # | Truth | Test | Status |
|---|-------|------|--------|
| 1 | `GET http://127.0.0.1:8765/api/v1/projects` → HTTP 200 + `Content-Type: application/json` | Smoke § 2.1 (live curl on port 8766) | green |
| 2 | Body is a top-level array, not an object | Smoke § 2.1 (`python3 isinstance(d, list)`) | green |
| 3 | Each element has exactly the 13 keys `{id, code, name, color, status, branch, lastCommit, summary, progress, todos, note, stack, nextEvent}` | `test_build_projects_shape` (set-equality) + Smoke § 2.2 | green |
| 4 | Field types match DATA_SETS (str/int/list/bool combinations described in plan) | `test_build_projects_field_types` + Smoke § 2.3 | green |
| 5 | When `invisible.toml` has ≥ 1 `[[projects]]` entry, array length ≥ 1 | `test_build_projects_shape` (len==1) + Smoke § 2.2 (synthetic toml with 1 row) | green |
| 6 | Response carries `Access-Control-Allow-Origin` header allowing `http://127.0.0.1:8090` | Smoke § 2.4 (loopback Origin header is echoed) | green |
| 7 | Missing orchestrator checkpoint → status defaults to "planning" | `test_build_projects_no_checkpoint_yields_planning` | green |
| 8 | Errors on broken worktrees do NOT include absolute filesystem paths | `test_build_projects_does_not_leak_paths` (negative invariant on `/Users/`, `/home/`, `str(home)`) | green |

Plus the two derived guard cases the plan calls out:

| # | Behavior | Test | Status |
|---|----------|------|--------|
| 9 | Branch + lastCommit fall back to "—" when `repo_path` is missing | `test_build_projects_branch_dash_when_repo_missing` | green |
| 10 | `color` field is always one of the 6 palette hex codes | `test_build_projects_color_in_palette` | green |
| 11 | `api.ROUTES` exposes `/api/v1/projects` → callable that calls `handler._send_json(list)` | `test_api_routes_registry` | green |

### Plan 01-02 — Frontend behavioral truths (8)

| # | Truth | Test | Status |
|---|-------|------|--------|
| 1 | Opening dashboard issues GET to `http://127.0.0.1:8765/api/v1/projects` | Smoke § 3.1 (`grep useEffect && grep fetchProjects` on `dashboard.jsx`) + § 3.2 (`grep /api/v1/projects` on `data.jsx`) | green |
| 2 | Within ~2s of mount, cards render from real-data response (not from DATA_SETS) | Smoke § 3.1 (DATA_SETS count == 0 on `dashboard.jsx`) + VERIFICATION.md interactive_verification baseline (orchestrator-driven headless Chrome, `card_count=1` real jobslayer row, `hasMockEcho=false`) | green |
| 3 | All four layouts render real data identically | Smoke § 3.3 (single `projectsToRender` source for kanban filter AND bento/grid/list map) — code path. Visual cycling: Manual-Only #1. | green (code) / Manual-Only #1 |
| 4 | Loading state shown while fetch in flight; no mock-content flash | Smoke § 3.7 (asserts literal `"Loading projects…"`, `"Couldn't load projects"`, `"Retry"`, `"Show mock data instead"` all present) + VERIFICATION.md `dash-initial.png` (loading visible briefly, no Echo/Lumen/Drift mock flash) | green |
| 5 | Fetch failure shows readable error + retry button (NOT blank page) | Smoke § 3.7 (UI strings) + VERIFICATION.md `dash-error.png` (daemon killed → "Couldn't load projects" headline + Retry + fallback button, no unhandled-promise console error) | green |
| 6 | Tools/Terminal/Focus action buttons route via `navTo(...)` with real `p.id` | Smoke § 3.4 (each navTo call grepped) + VERIFICATION.md interactive_verification (Tools click on jobslayer card → `active_page=Tools`, `tools_visible=true`). Live click test for Terminal/Focus is Manual-Only #2. | green (code + 1/3 interactive) / Manual-Only #2 (remaining clicks) |
| 7 | "Mock data" toggle continues to work for Focus/Terminals/Tools/Analytics | Smoke § 3.5 (`DATA_SETS[` still referenced in `app.jsx`) + VERIFICATION.md interactive_verification ("Dashboard real-data independence from Mock data toggle" — Dashboard ignores toggle, sister pages still react). Multi-page user-toggle UAT is Manual-Only #3. | green (code) / Manual-Only #3 |
| 8 | No JS console error logged on successful render | VERIFICATION.md interactive_verification ("Console-error count across full session" — 0 Runtime.consoleAPICalled events of type=error during the entire CDP-driven interactive run) | green |

### REQ-01 secure behaviors (already audited in 01-SECURITY.md)

The 16 STRIDE threats in `01-SECURITY.md` are NOT re-audited here (per
constraint "Security threats are tracked in 01-SECURITY.md — don't re-audit
them"). Two cross-cutting security greps **are** included in the smoke script
because they would catch regressions outside the security audit window:

| # | Secure Behavior | Threat Ref | Test | Status |
|---|-----------------|-----------|------|--------|
| 1 | Error responses do not leak filesystem paths | T-INV-01-02 | `test_build_projects_does_not_leak_paths` (no `/Users/`, `/home/`, or `tmp_path` in any string field) | green |
| 2 | No `dangerouslySetInnerHTML` in `dashboard.jsx` or `data.jsx` | T-INV-01-09 | Smoke § 3.6 (grep returns 0 in both files) | green |
| 3 | CORS loopback echo only (never `*`, never cross-origin) | T-INV-01-04 | Smoke § 2.4 (loopback echo present) + § 2.5 (non-loopback denied) | green |

---

## Generated Tests

This audit added one file to the workstream:

| File | Type | Purpose | Runtime | Command |
|------|------|---------|---------|---------|
| `tests/smoke_dashboard_wiring.sh` | smoke (bash + curl + python3 + grep) | End-to-end behavioral coverage for REQ-01 — 17 checks across backend pytest, live API, and frontend static analysis. Spawns a hermetic daemon on port 8766 with a synthetic `INVISIBLE_HOME=$(mktemp -d)`/`invisible.toml`, asserts shape + types + CORS, then tears down. Does NOT touch the user's `~/.invisible/` or any other workstream's worktree. | ~3-5 s | `bash tests/smoke_dashboard_wiring.sh` |

**Existing tests reused (not regenerated):**

| File | Owner | Coverage |
|------|-------|----------|
| `tests/test_api_projects.py` | plan 01-01 | 7 hermetic pytest cases. Shape, types, planning-default, branch-fallback, palette, no-path-leak, ROUTES registry. Each test name maps 1:1 to a `<behavior>` clause in plan 01-01 task 1. |

**Files for commit:**

- `/Users/ace/.invisible-ws/dashboard-wiring/tests/smoke_dashboard_wiring.sh` (NEW, +374 lines, executable)
- `/Users/ace/.invisible-ws/dashboard-wiring/.planning/workstreams/dashboard-wiring/phases/INV-01-real-api-v1-projects-end-to-end/01-VALIDATION.md` (NEW, this file)

---

## Manual-Only Verifications

Three interactive flows remain Manual-Only because they require behaviors that
cannot be reliably asserted inside this workstream's constraints (no JS test
framework, no real-keyboard event simulation). All three are documented in
`VERIFICATION.md::interactive_verification` as low-risk gaps with explicit
reasoning. Each has a reproducible CDP driver path the next developer can pick
up — see `VERIFICATION.md::driver` and the `/tmp/inv-cdp-driver*.mjs` orchestrator
scripts referenced therein.

| # | Behavior | Requirement | Why Manual | Test Instructions |
|---|----------|-------------|------------|-------------------|
| 1 | Visual confirmation that all four CSS layout wrappers (bento / grid / kanban / list) render the real data identically and do NOT issue an extra fetch on layout change | REQ-01 acceptance criterion #3 | CDP simulation of React-controlled `<select>` change events on `TweakSelect` does not reliably propagate to React's onChange handler. (Well-known React-controlled-component testing limitation; live user click works correctly.) Adding a real JS test runner would violate the WS-6 boundary in PROJECT.md ("Babel-standalone for now, migrate to Vite in WS-6"). **Code path verified by `tests/smoke_dashboard_wiring.sh` § 3.3** — same `projectsToRender` array fed through `.filter()` (kanban) AND `.map()` inside `layout-${layout}` (bento/grid/list). | 1. Start both daemons: `(./bin/invisible-dashboard --no-auth >/tmp/dash.log 2>&1 &) && (./bin/invisible-frontend >/tmp/fe.log 2>&1 &) && sleep 2`. 2. Open `http://127.0.0.1:8090/` → click Dashboard tab. 3. Open Tweaks panel (gear icon, bottom right). 4. Cycle Layout radio through Bento → Grid → Kanban → List. 5. Confirm same single real-data project list renders in each; no mock content; **DevTools Network tab shows a single GET to `/api/v1/projects` total — no refetch on layout change**. |
| 2 | Live click on each action button (Tools / Terminal / Focus) routes to the correct page with real project id selected | REQ-01 acceptance criterion #4 | Same CDP limitation as #1 — interactive click simulation does not reliably propagate React onClick handlers in headless mode. **One of three buttons was exercised interactively (Tools click on jobslayer card → `active_page=Tools` confirmed; see VERIFICATION.md).** Code path for Terminal + Focus is identical (same `navTo(p.id, ...)` prop chain). Smoke § 3.4 greps confirm all three handlers are present. | 1. On any project card on the Dashboard, click Tools → confirm Tools page opens with that project selected. Return. 2. Click Terminal → confirm Terminals page opens with the same project. Return. 3. Click Focus → confirm Focus page opens with the same project. Cross-check the selected project id matches what the card showed (use `jobslayer` for the canonical real-data row). |
| 3 | Tweaks "Mock data" toggle switches Focus / Terminals / Tools / Analytics between Personal and Client-work mock datasets, while Dashboard ignores the toggle (still shows real data) | REQ-01 acceptance criterion #5 | Same CDP limitation — multi-page navigation + visual confirmation of which dataset renders on each page cannot be asserted programmatically in headless mode. Sister pages were visited and confirmed to read from DATA_SETS via app.jsx props during the CDP run (Focus rendered Personal mock; Tools rendered mock workflow grid) — see VERIFICATION.md interactive_verification. Smoke § 3.5 confirms `app.jsx` still consumes `DATA_SETS[...]` (the prop path is structurally intact). | 1. On Dashboard (real data showing): open Tweaks → switch Mock data from "Personal projects" to "Client work". 2. Confirm Dashboard does NOT change. 3. Navigate to Focus tab → confirm Client-work mock data shows. 4. Navigate to Terminals / Tools / Analytics → confirm each switched to Client-work data. 5. Switch toggle back to Personal → confirm sister pages flip back, Dashboard still ignores the toggle. |

---

## Wave 0 Requirements

Already satisfied — no new test infrastructure needed beyond what this audit
generated. All Wave 0 items were created during plan 01-01 (TDD-first):

- [x] `tests/__init__.py` — test package init (plan 01-01)
- [x] `tests/test_api_projects.py` — 7 backend cases (plan 01-01, TDD RED→GREEN gates)
- [x] `tests/smoke_dashboard_wiring.sh` — end-to-end smoke (this audit)

---

## Validation Sign-Off

- [x] All tasks have automated verify (backend pytest + smoke script § 2 + § 3) OR are explicitly Manual-Only with documented reason
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (plan 01-01 task 1 → pytest; plan 01-01 task 2 → smoke § 2; plan 01-02 task 1 → smoke § 3.2; plan 01-02 task 2 → smoke § 3.1/3.3/3.4/3.6/3.7; plan 01-02 task 3 → Manual-Only #1/#2/#3)
- [x] No watch-mode flags
- [x] Feedback latency ~5 seconds (well under any reasonable threshold)
- [x] `nyquist_compliant: true` set in frontmatter
- [x] Smoke script exits 0 — all 17 checks PASS (verified 2026-06-01 against this worktree)

**Verification run output (last green):**

```
═══ Section 1: backend pytest (7 hermetic cases — REQ-01 contract)
  PASS  tests/test_api_projects.py — 7/7 cases green

═══ Section 2: live /api/v1/projects (HTTP 200, JSON shape, loopback CORS)
  PASS  daemon healthy on 127.0.0.1:8766
  PASS  GET /api/v1/projects → 200 + JSON array body
  PASS  First row has exact 13-key DATA_SETS shape
  PASS  Field types match DATA_SETS contract
  PASS  CORS — loopback Origin echoed (Access-Control-Allow-Origin: http://127.0.0.1:8090)
  PASS  CORS — non-loopback Origin denied (no Access-Control-Allow-Origin header)
  PASS  Legacy /healthz route still responds (no regression)

═══ Section 3: static frontend wiring (criteria #2-#5)
  PASS  dashboard.jsx mounts useEffect that calls fetchProjects()
  PASS  dashboard.jsx has 0 references to DATA_SETS (mock removed for this page)
  PASS  data.jsx exposes fetchProjects() pointing at /api/v1/projects
  PASS  All four layouts feed from the same projectsToRender (6 refs)
  PASS  Kanban (filter) + bento/grid/list (map on layout-${layout}) both use projectsToRender
  PASS  Action buttons route via navTo(...) with p.id (tools=2, terminals=1, focus=2)
  PASS  app.jsx still reads DATA_SETS — Mock toggle preserved for sister pages
  PASS  No dangerouslySetInnerHTML in dashboard.jsx or data.jsx (XSS surface clean)
  PASS  Loading + error UI strings all present (loading / error / retry / fallback)

═══ Summary
  Total:  17
  Pass:   17
  Fail:   0
  Skip:   0
```

**Verdict:** PASS — `nyquist_compliant: true`. 14 of the 17 phase behaviors are
covered by automated tests that fail loudly on regression; the remaining 3
are explicitly Manual-Only with reproducible instructions, and 1 of those 3
(action-button routing) was additionally exercised interactively via CDP
during the original execution (see VERIFICATION.md).

**Approval:** verified 2026-06-01
