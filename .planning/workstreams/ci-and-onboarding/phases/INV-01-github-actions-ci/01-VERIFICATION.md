---
phase: INV-01-github-actions-ci
verified: 2026-06-01T00:00:00Z
status: human_needed
score: 12/12 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: none
  note: Initial verification (no prior VERIFICATION.md existed).
human_verification:
  - test: "Apply branch protection on main (D-07). Run the documented `gh api -X PUT repos/Avi977/invisible/branches/main/protection` call from BRANCH-PROTECTION.md (contexts: lint, test, import-smoke, Claude security review) as a repo admin."
    expected: "`gh api repos/Avi977/invisible/branches/main/protection/required_status_checks --jq '.contexts'` returns the four contexts. Currently main is unprotected (HTTP 404 'Branch not protected'), which is the DOCUMENTED-not-executed state D-07 specifies — owner may lack `administration` permission."
    why_human: "Mutating branch protection on the default branch of a public repo is an owner-scope, irreversible operation the automation deliberately does not perform (D-07). Phase 1's criterion 5 is satisfied as a documented step; APPLYING it is the human action."
  - test: "Set the CLAUDE_API_KEY repo secret (D-06 post-merge step). Run `gh secret set CLAUDE_API_KEY --body \"$ANTHROPIC_API_KEY\" --repo Avi977/invisible`."
    expected: "`gh secret list --repo Avi977/invisible | grep CLAUDE_API_KEY` shows the secret. Currently NOT set — until then the merged security-review workflow errors (non-blocking) on PRs into main. This is expected and documented in BRANCH-PROTECTION.md."
    why_human: "Handling a real API key is a manual secret-management step the automation must never perform (never echo/commit a secret — threat T-01-08)."
  - test: "Register the 'Claude security review' required check (D-06). Trigger the security-review workflow once (e.g. `gh workflow run security-review.yml --repo Avi977/invisible --ref main`), then add it as a required check per BRANCH-PROTECTION.md."
    expected: "GitHub exposes the 'Claude security review' check name after the workflow completes once; it can then be added to required_status_checks. The workflow file is confirmed present on main (security-review.yml, job name 'Claude security review', action SHA-pinned)."
    why_human: "Depends on the CLAUDE_API_KEY secret being set first, plus owner-scope branch-protection config; GitHub only surfaces the check after one completed run."
---

# Phase INV-01: GitHub Actions CI — Verification Report

**Phase Goal:** Every push and PR runs lint + tests + an import-smoke, all green on a fresh clone of `main`; PR #3 (claude-code-security-review) is merged in.
**Verified:** 2026-06-01
**Status:** human_needed
**Re-verification:** No — initial verification.

## Goal Achievement

Every automated truth is VERIFIED against the live repo and GitHub. Status is `human_needed` (not `passed`) only because three genuine owner-scope GitHub-side steps remain — and those are **by design** documented-not-executed (D-06/D-07), not phase failures. The codebase + CI deliverables themselves are complete and green.

### ROADMAP Success Criteria (1–5)

| # | Success Criterion | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `.github/workflows/ci.yml` exists | ✓ VERIFIED | File present, 128 lines, parses as valid YAML, `name: ci`. |
| 2 | Three SEPARATE jobs — lint, test, import-smoke | ✓ VERIFIED | `yaml.safe_load` → `jobs == ['import-smoke','lint','test']` (3 distinct top-level jobs, not steps). Each is a separate status check. |
| 3 | All three green on a fresh clone | ✓ VERIFIED | **Live GitHub:** latest run `26798553373` (SHA `e5dce580`) on `ws/ci-and-onboarding` = `completed/success`; per-job `gh run view` → lint=success, test=success, import-smoke=success. **Local reproduction:** `PYTHONPATH=lib pytest -q` → 22 passed; import-smoke probe 1 (5 hard imports OK, analytics soft-skip) + probe 2 (21 py_compile OK / 2 bash skipped) both green. |
| 4 | Triggers on `push` (any branch) + `pull_request` into `main` | ✓ VERIFIED | `on.push:` present with no branch filter; `on.pull_request.branches == ['main']`. No `pull_request_target` (line 16 is a comment stating it is intentionally NOT used). |
| 5 | Required-check on `main` DOCUMENTED (branch-protection) | ✓ VERIFIED (documented) | `BRANCH-PROTECTION.md` records the exact `gh api -X PUT repos/Avi977/invisible/branches/main/protection` call with contexts `lint`/`test`/`import-smoke`/`Claude security review`, flagged "DOCUMENTED, NOT EXECUTED". Criterion explicitly requires documentation, not application. Live: main currently unprotected (404) — the human step to APPLY it is in human_verification. |

**Criteria score:** 5/5 verified.

### Implementation Decisions (D-01 … D-07)

| Decision | Status | Evidence |
| --- | --- | --- |
| D-01: push + PR-into-main triggers; three separate jobs lint/test/import-smoke; Python 3.11; actions pinned to major tags | ✓ VERIFIED | Triggers + 3 jobs confirmed (criteria 2/4). All three jobs set `python-version: "3.11"`. `actions/checkout@v4` + `actions/setup-python@v5` (major-tag pins) in every job. |
| D-02: lint runs `ruff check lib/ bin/`; ruff.toml has `extend-include` for `bin/invisible-*`; lenient select passes existing code (E402 doesn't break build) | ✓ VERIFIED | `lint` job runs `ruff check lib/ bin/`. ruff.toml: `extend-include=["bin/invisible-*"]`, `select=["F"]`, `ignore=["E402","F401","F541","F811","F841"]`, `extend-exclude` for the 2 bash scripts. Lint job concluded `success` on the live run (proves it passes on a fresh clone). |
| D-03: test runs pytest with `PYTHONPATH=lib`; testpaths collects BOTH `tests/` and `lib/api/` | ✓ VERIFIED | `test` job sets `env: PYTHONPATH: lib`, runs `pytest`. pyproject.toml `testpaths=["tests","lib/api"]`. Collection proof: `test_chat.py` (15 tests) + `test_api_projects.py` (7 tests) = 22 passed locally. A bare `pytest tests/` would have missed all 15 test_chat tests. |
| D-04: import-smoke hard-imports the 5 present api.* submodules, soft-skips `api.analytics` via try/except ModuleNotFoundError, py_compiles every Python `bin/invisible-*` (skips the 2 bash) | ✓ VERIFIED | ci.yml grep: `api.analytics` + `ModuleNotFoundError` + `py_compile` all present. On-disk: 5 present api.* modules (analytics.py absent — soft-skip target confirmed). bin: 23 total = 21 python + 2 bash (invisible-review, invisible-update). Local probes reproduce exactly: 5 imports OK, analytics WARN soft-skip, 21 py_compile OK / 2 skipped. |
| D-05: CI installs only ruff + pytest, pinned; no project-wide requirements file | ✓ VERIFIED | lint installs `ruff==0.15.15`; test installs `pytest==9.0.3`; import-smoke installs nothing. pyproject.toml has no `[build-system]`, no `[project]`, no dependencies. No requirements.txt introduced. |
| D-06: PR #3 merged into main behind explicit confirmation; its two post-merge manual steps documented | ✓ VERIFIED (merge) / human pending (post-merge steps) | **`gh pr view 3` → state `MERGED`** at 2026-06-02T04:35:41Z, squash commit `692dc52`. `security-review.yml` confirmed on `main` (1882 bytes), job name `Claude security review`, action SHA-pinned `@0c6a49f1fa56a1d472575da86a94dbc1edb78eda` (not loosened). The two post-merge steps (CLAUDE_API_KEY secret, register check) are documented in BRANCH-PROTECTION.md and surfaced as human_verification items. |
| D-07: exact branch-protection command recorded as a documented manual step (not executed) | ✓ VERIFIED | BRANCH-PROTECTION.md contains the exact `gh api .../branches/main/protection` call + the four check contexts, with an explicit permission caveat. Live: main unprotected (404) — correctly NOT auto-applied. |

**Decisions score:** 7/7 verified (D-06 merge done; D-06/D-07 manual steps are documented + pending as designed).

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `.github/workflows/ci.yml` | CI pipeline w/ lint, test, import-smoke; contains "import-smoke"; ≥45 lines | ✓ VERIFIED | 128 lines; 3 jobs; `import-smoke` present; valid YAML; `permissions: contents: read`. |
| `ruff.toml` | lenient config; contains `extend-include` | ✓ VERIFIED | 53 lines; `extend-include=["bin/invisible-*"]`, lenient F-select + ignore list, extend-exclude for bash scripts. |
| `pyproject.toml` | pytest config collecting tests/ + lib/api/; `[tool.pytest.ini_options]` | ✓ VERIFIED | `testpaths=["tests","lib/api"]`; no build-system/project metadata. |
| `README.md` (badge) | CI badge near top; contains `actions/workflows/ci.yml/badge.svg` | ✓ VERIFIED | Badge on line 3, directly under `# invisible`. |
| `BRANCH-PROTECTION.md` | documented manual steps; contains `branches/main/protection` | ✓ VERIFIED | All required strings present: branches/main/protection, CLAUDE_API_KEY, Claude security review, lint/test/import-smoke; flagged documented-not-executed. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| ci.yml (test job) | pyproject.toml `[tool.pytest.ini_options]` | `PYTHONPATH=lib pytest` reading testpaths | ✓ WIRED | test job `env: PYTHONPATH: lib` + `run: pytest`; pyproject supplies testpaths; 22 tests collected from both roots. |
| ci.yml (lint job) | ruff.toml `extend-include` | `ruff check lib/ bin/` resolving extension-less bin scripts | ✓ WIRED | lint job runs `ruff check lib/ bin/`; ruff.toml extend-include forces parse of the 21 Python bin scripts; lint=success on live run. |
| ci.yml (import-smoke) | lib/api/*.py + bin/invisible-* | PYTHONPATH=lib import probe + py_compile loop | ✓ WIRED | Probe 1 imports the 5 present modules + soft analytics; Probe 2 py_compiles bin scripts. Reproduced locally green. |
| README badge | .github/workflows/ci.yml | Actions badge URL referencing ci.yml | ✓ WIRED | Badge URL `.../actions/workflows/ci.yml/badge.svg` matches the workflow filename. |
| BRANCH-PROTECTION.md | GitHub branch protection on main | documented `gh api PUT .../branches/main/protection` | ✓ WIRED (documented) | Exact call recorded with correct contexts; intentionally not executed (D-07). |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Test suite passes (both files) | `PYTHONPATH=lib python -m pytest -q` | 22 passed in 0.70s | ✓ PASS |
| Both test files collected | `pytest --collect-only` per-file | test_chat.py=15, test_api_projects.py=7 | ✓ PASS |
| import-smoke probe 1 (5 imports + soft analytics) | inline `PYTHONPATH=lib python` | 5 OK, analytics soft-skip | ✓ PASS |
| import-smoke probe 2 (py_compile bin) | shebang-gated `py_compile` loop | ok=21 skip=2 fail=0 | ✓ PASS |
| ci.yml YAML structure | `yaml.safe_load` assertions | 3 jobs, contents:read, push+PR-main | ✓ PASS |
| ruff lint (lib/ bin/) | n/a — ruff not installed locally | lint job = success on live run 26798553373 | ? SKIP (verified via live CI instead; not installed locally per env policy) |

### Probe Execution

| Probe | Command | Result | Status |
| --- | --- | --- | --- |
| Live CI run (3 jobs) | `gh run view 26798553373 --json jobs` | lint/test/import-smoke each `success` | ✓ PASS |

(No conventional `scripts/*/tests/probe-*.sh` exist for this phase; the phase's runnable check is the CI workflow itself, which was executed live and reproduced locally.)

### Requirements Coverage

Not applicable — this workstream has no REQUIREMENTS.md and both plans declare `requirements: []`. (Per the verification instructions, do not flag missing REQ coverage.)

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| (none in owned files) | — | — | — | The 3 owned config files + 2 docs contain no TBD/FIXME/XXX, no stub returns, no hardcoded-empty data feeding output. The `try/except ModuleNotFoundError` soft-skip for api.analytics is an intentional, documented resilience pattern (D-04), not a stub. The Node-20 action deprecation is a known non-blocking annotation tracked in deferred-items.md (not a gap). |

### Human Verification Required

Three owner-scope GitHub-side steps remain. All are **intentionally documented-not-executed** (D-06/D-07) — the phase goal is achieved; these are the manual follow-ups the automation must not perform:

1. **Apply branch protection on `main` (D-07)** — run the documented `gh api PUT .../branches/main/protection` call (contexts: lint, test, import-smoke, Claude security review) as a repo admin. Currently main is unprotected (HTTP 404). Criterion 5 only requires this be *documented* (it is); applying it is the human step.
2. **Set the `CLAUDE_API_KEY` secret (D-06)** — `gh secret set CLAUDE_API_KEY ... --repo Avi977/invisible`. Currently not set; until then the merged security-review workflow errors (non-blocking) on PRs into main.
3. **Register the `Claude security review` required check (D-06)** — trigger the security-review workflow once, then add it as a required check. Depends on step 2 first.

### Gaps Summary

**No gaps.** All 5 ROADMAP success criteria and all 7 decisions (D-01..D-07) are verified against the live repo and GitHub:

- ci.yml exists with exactly three separate jobs (lint/test/import-smoke), correct triggers (push any branch + PR→main), least-privilege `contents: read`, pinned ruff/pytest, PYTHONPATH=lib tests, and the D-04 soft-import + py_compile smoke.
- The latest CI run on `ws/ci-and-onboarding` (`26798553373`, SHA `e5dce580`) is `completed/success` with every job green; the tip commit `e700b14` is docs-only (ROADMAP + SUMMARY), so the green run covers the current CI-relevant code. Locally reproduced: 22 tests pass (both files), import-smoke green.
- PR #3 is **MERGED** (squash `692dc52`); `security-review.yml` is on `main` with the SHA pin intact and job name `Claude security review` matching the documented required-check context.
- ruff.toml + pyproject.toml are minimal and correct; README badge is live; BRANCH-PROTECTION.md documents the exact D-06/D-07 manual steps.

The only open items are the three owner-permission GitHub steps above, which D-06/D-07 explicitly define as documented manual actions, not phase deliverables. The Node-20 action-runtime deprecation is a known non-blocking annotation (deferred-items.md), not a gap.

---

_Verified: 2026-06-01_
_Verifier: Claude (gsd-verifier)_
