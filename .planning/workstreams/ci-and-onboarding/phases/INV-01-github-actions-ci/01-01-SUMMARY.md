---
phase: INV-01-github-actions-ci
plan: 01
subsystem: infra
tags: [github-actions, ci, ruff, pytest, lint, import-smoke, python]

# Dependency graph
requires:
  - phase: (none)
    provides: First plan of the phase; depends only on the existing repo (lib/api, bin/invisible-*, tests).
provides:
  - .github/workflows/ci.yml — CI pipeline with three independent jobs (lint, test, import-smoke) on push (any branch) + PR into main
  - ruff.toml — lenient lint config that sees the extension-less bin/invisible-* Python scripts and passes the existing E402-heavy code on a fresh clone
  - pyproject.toml — minimal pytest config collecting both tests/ and lib/api/
affects: [01-02 (push branch + verify all jobs green on GitHub, README CI badge, PR #3 merge), tightening-ruff-ruleset (deferred), api.analytics-hard-import (auto-activates when PR #8 lands)]

# Tech tracking
tech-stack:
  added: ["ruff==0.15.15 (CI-only, pinned)", "pytest==9.0.3 (CI-only, pinned)", "GitHub Actions (actions/checkout@v4, actions/setup-python@v5)"]
  patterns: ["PYTHONPATH=lib import contract in CI", "three-separate-jobs for independent status checks", "soft-import via try/except ModuleNotFoundError for in-flight cross-workstream modules", "py_compile (not import) for heavy-dep bin scripts", "least-privilege permissions: contents: read"]

key-files:
  created: [".github/workflows/ci.yml", "ruff.toml", "pyproject.toml"]
  modified: []

key-decisions:
  - "Ruff select=[F] with ignore=[E402,F401,F541,F811,F841] — the only lenient set that yields exit 0 on the unmodifiable lib/ + bin/ source while still catching F821 undefined-name in new code (extends D-02)."
  - "extend-exclude the 2 bash bin scripts (invisible-review, invisible-update) — extend-include forces Ruff 0.15.x to parse them as Python and they raise 218 invalid-syntax errors otherwise."
  - "Pinned ruff==0.15.15 and pytest==9.0.3 (both verified non-yanked stable on PyPI; first-party Astral / pytest-dev — no legitimacy checkpoint per threat T-01-04)."
  - "api.analytics imported soft (try/except ModuleNotFoundError → WARN) so the import-smoke job is green on main today and auto-covers when PR #8 lands (D-04, T-01-05)."

patterns-established:
  - "CI import contract mirrors bin/invisible-dashboard: PYTHONPATH=lib so `from api import ...` resolves with no lib/__init__.py."
  - "bin smoke = py_compile over Python scripts only (shebang-gated), never import — heavy runtime deps (websockets/ptyprocess) make import infeasible."

requirements-completed: []

# Metrics
duration: ~20min
completed: 2026-06-01
---

# Phase INV-01 Plan 01: GitHub Actions CI Pipeline Summary

**Three-job GitHub Actions CI (lint via ruff, test via pytest with PYTHONPATH=lib, and an import-smoke that soft-skips the stranded api.analytics and py_compiles 21 extension-less bin scripts) plus a lenient ruff.toml and a minimal pytest pyproject.toml — all green on a fresh clone of main.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-06-01
- **Completed:** 2026-06-01
- **Tasks:** 2
- **Files modified:** 3 (all created)

## Accomplishments
- `.github/workflows/ci.yml` — the repo's first workflow: `name: ci`, triggers on `push` (any branch) + `pull_request` into `main`, top-level `permissions: contents: read`, and three SEPARATE jobs (`lint`, `test`, `import-smoke`) on `ubuntu-latest` + Python 3.11 with `actions/checkout@v4` / `actions/setup-python@v5` pinned to major tags.
- `ruff.toml` — `target-version=py311`, `extend-include=["bin/invisible-*"]` so the 21 extension-less Python bin scripts are linted, the 2 bash scripts `extend-exclude`d, and a lenient `select=["F"]` / `ignore=[E402,F401,F541,F811,F841]` that exits 0 on the existing codebase while keeping real checks (e.g. F821) live.
- `pyproject.toml` — `[tool.pytest.ini_options]` with `testpaths=["tests","lib/api"]` so both `tests/test_api_projects.py` and the colocated `lib/api/test_chat.py` are collected; no `[build-system]`, no project metadata, no dependencies (D-05).
- All four plan-level verifications pass locally with the pinned tools: `ruff check lib/ bin/` → exit 0; `PYTHONPATH=lib pytest` → 22 passed; ci.yml parses with exactly the 3 jobs + `contents: read`; import-smoke logic runs green (5 hard imports, analytics soft-skipped, 21 py_compiled / 2 skipped).

## Task Commits

Each task was committed atomically (Conventional Commits):

1. **Task 1: Write ruff.toml and pytest config** — `5e88b4e` (chore)
2. **Task 2: Write .github/workflows/ci.yml (lint, test, import-smoke)** — `e2ec1a6` (ci)

_(STATE.md / ROADMAP.md are intentionally NOT updated here — the orchestrator owns those writes.)_

## Files Created/Modified
- `.github/workflows/ci.yml` (127 lines) — CI pipeline: push+PR-into-main triggers, `contents: read`, three jobs (lint / test / import-smoke), pinned ruff+pytest, PYTHONPATH=lib for tests, D-04 soft-import + py_compile smoke.
- `ruff.toml` (52 lines) — lenient lint config; extend-include for bin scripts, extend-exclude for the 2 bash scripts, E402/F401/F541/F811/F841 ignored.
- `pyproject.toml` (20 lines) — pytest-only config; `testpaths=["tests","lib/api"]`.

## Decisions Made
- **Rule selection (extends D-02 "Claude's Discretion"):** D-02's skeleton suggested `select=["F"]` as a "safe floor," but plain pyflakes flagged 26 genuine findings in source this plan must NOT modify. Chose `select=["F"]` with `ignore=[E402,F401,F541,F811,F841]` — the minimal set that achieves the binding acceptance criterion (`ruff check lib/ bin/` exits 0) while keeping high-value rules like F821 (undefined-name) active, proven by a probe. Re-tightening (removing the ignores after the source is cleaned) is explicitly deferred.
- **Version pins:** `ruff==0.15.15`, `pytest==9.0.3` — both confirmed against PyPI as real, non-yanked stable releases; both first-party tooling (Astral / pytest-dev), so no package-legitimacy checkpoint was required (threat T-01-04 / T-01-SC).
- Single Python 3.11 (no matrix), no pip caching — both within Discretion; kept minimal.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1/3 — Bug/Blocking] `extend-include` made Ruff parse the 2 bash scripts as Python → 218 invalid-syntax errors**
- **Found during:** Task 1 (behavioral verification of `ruff check lib/ bin/`).
- **Issue:** PATTERNS.md L100-102 assumed a glob hitting the bash scripts was harmless ("ruff only parses what looks like Python"). False for Ruff 0.15.x: `extend-include` *forces* parsing, so `bin/invisible-review` (3) and `bin/invisible-update` (215) emitted 218 `invalid-syntax` errors, making the lint job RED on a fresh clone — a direct violation of the phase's "all jobs green" criterion.
- **Fix:** Added `extend-exclude = ["bin/invisible-review", "bin/invisible-update"]` to `ruff.toml`. The `extend-include` key the acceptance criteria require is retained; only the 2 non-Python files are excluded.
- **Files modified:** `ruff.toml`
- **Verification:** `ruff check lib/ bin/` (pinned ruff==0.15.15) → "All checks passed!" exit 0; confirmed the only 2 non-python bin scripts are exactly those excluded.
- **Committed in:** `5e88b4e` (Task 1 commit)

**2. [Rule 1/3 — Bug/Blocking] `select=["F"]` floor did not pass the existing code (26 pyflakes findings)**
- **Found during:** Task 1 (behavioral verification).
- **Issue:** The plan/PATTERNS skeleton used `select=["F"]` as a "green floor," but real pyflakes findings in unmodifiable source broke the build: F401×16 (unused imports, e.g. `bin/invisible-app` `queue`, `bin/invisible-dashboard` `socket`), F541×6 (f-string w/o placeholders), F841×3 (unused locals), F811×1 (`do_OPTIONS` redefinition in dashboard). Since `lib/` and `bin/` are MUST-NOT-TOUCH fences, the config — not the source — had to absorb these.
- **Fix:** Added those four codes (plus the already-planned E402) to `ignore` in `ruff.toml`, with a comment tracing each to its real finding. F821 and the rest of pyflakes remain active (verified a synthetic undefined-name still fails), so the lint is not a no-op. Squarely within D-02's "lenient, passes existing code; tightening deferred" mandate and its explicit Discretion grant on rule selection.
- **Files modified:** `ruff.toml`
- **Verification:** `ruff check lib/ bin/` exit 0; a probe file with an undefined symbol still trips F821 (exit 1), proving the rule family still catches real breakage.
- **Committed in:** `5e88b4e` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1/3 — config did not achieve its required green-on-fresh-clone behavior).
**Impact on plan:** Both fixes were necessary to satisfy the phase's core success criterion ("all three jobs green on a fresh clone") under the MUST-NOT-TOUCH source fence. They live entirely inside the owned `ruff.toml`; the three owned files are exactly the deliverable set with no scope creep. Both changes fall under D-02's explicit Discretion grant on ruff rule selection.

## Issues Encountered
- PyPI's `info.version` for pytest reported `9.0.3` (newer than the local env's 7.4.0). Rather than trust a single field, queried PyPI release data directly to confirm `9.0.3` is a real, non-yanked stable release before pinning. Resolved — pinned with confidence.
- `py_compile` during local smoke verification left `__pycache__/` artifacts; confirmed `.gitignore:15` (`__pycache__/`) already excludes them, so nothing leaked into the commits.

## User Setup Required
None for this plan. (Plan 01-02 will document the manual steps: pushing `ws/ci-and-onboarding`, the `gh pr merge 3` confirm, the `CLAUDE_API_KEY` secret, the `Claude security review` required check, and making `ci.yml` a required check on `main` — none of which this plan executes.)

## Next Phase Readiness
- The three CI config files are committed on `ws/ci-and-onboarding` and verified green locally. Ready for plan 01-02 to push the branch, confirm all three jobs run green on GitHub, add the README CI badge, and handle the PR #3 merge + branch-protection documentation.
- **Note for the verifier:** GitHub-side green-run confirmation is intentionally NOT done here (this plan only writes config files and does not push) — it is plan 01-02's job.
- No MUST-NOT-TOUCH files were modified (`lib/`, `frontend/`, other `bin/`, `release.yml`, `security-review.yml` all untouched; STATE.md/ROADMAP.md left for the orchestrator).

## Self-Check: PASSED

- FOUND: `.github/workflows/ci.yml`
- FOUND: `ruff.toml`
- FOUND: `pyproject.toml`
- FOUND: `.planning/workstreams/ci-and-onboarding/phases/INV-01-github-actions-ci/01-01-SUMMARY.md`
- FOUND commit: `5e88b4e` (Task 1)
- FOUND commit: `e2ec1a6` (Task 2)

---
*Phase: INV-01-github-actions-ci*
*Completed: 2026-06-01*
