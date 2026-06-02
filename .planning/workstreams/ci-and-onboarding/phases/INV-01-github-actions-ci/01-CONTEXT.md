# Phase 1: GitHub Actions CI — Context

**Gathered:** 2026-06-01
**Status:** Ready for planning
**Source:** Recon + workstream ROADMAP + ratified PR #3 decision, in lieu of `/gsd:discuss-phase` (START_HERE.md routes straight to plan-phase). Research is disabled in config (`workflow.research=false`); technical findings are captured here instead. Key claims below were **live-verified** against the working tree on `ws/ci-and-onboarding`.

<domain>
## Phase Boundary

**Delivers:** A GitHub Actions CI pipeline (`.github/workflows/ci.yml`) that runs on every push (any branch) and every PR into `main`, with three jobs — **lint**, **test**, **import-smoke** — all green on a fresh clone of `main`. Plus the security-review track resolved by merging PR #3.

**In scope:**
- `.github/workflows/ci.yml` (new) — lint + test + import-smoke jobs
- `ruff.toml` (new) + minimal pytest config — lint config tuned to pass existing code and to see the extension-less `bin/invisible-*` scripts
- Wiring the existing tests (`tests/test_api_projects.py`, `lib/api/test_chat.py`) so pytest collects them
- Merging PR #3 (security-review) and documenting its post-merge manual steps
- README CI badge (light edit)

**Out of scope (later phases / other workstreams):**
- First-run wizard (Phase 2 — blocked on PR #7)
- `invisible-doctor` rewrite (Phase 3)
- `.github/workflows/release.yml` (owned by the `tauri-windows` workstream — MUST NOT TOUCH)
- Authoring NEW tests for untested modules (CI runs what exists; broad test-writing is not this phase)
</domain>

<decisions>
## Implementation Decisions

### CI workflow structure
- **D-01:** `ci.yml` triggers on `push` (any branch) and `pull_request` targeting `main`. It defines exactly three jobs — `lint`, `test`, `import-smoke` (separate jobs, not steps, so each gives independent signal per ROADMAP success criterion 2). Python **3.11** (matches dev env 3.11.4). Pin `actions/checkout` and `actions/setup-python` to major versions.

### Lint job
- **D-02:** `lint` runs `ruff check` over `lib/` and `bin/`. Because `bin/invisible-*` are Python with **no `.py` extension**, `ruff.toml` MUST set `extend-include = ["bin/invisible-*"]` (or equivalent) and must not choke on any non-Python files in `bin/`. The initial ruleset MUST be lenient enough to pass the existing codebase on a fresh clone — existing code is full of post-`sys.path.insert` imports (E402) and `# noqa` markers. Start from a curated `select` (pyflakes `F` + a safe subset), NOT ruff's full default. Tightening the ruleset is explicitly deferred.

### Test job
- **D-03:** `test` runs `pytest` with `PYTHONPATH=lib` (tests import `from api import ...`; `lib/` has no `__init__.py`, so `api` is a top-level package reachable only with `lib/` on the path). Configure `testpaths` to include **both** `tests/` and `lib/api/` so `lib/api/test_chat.py` is collected alongside `tests/test_api_projects.py` (a bare `pytest tests/` would silently skip `test_chat.py`). Pytest config lives in a minimal `pyproject.toml` (`[tool.pytest.ini_options]`) or `pytest.ini`. Only dev dependency is `pytest`.

### Import-smoke job
- **D-04:** `import-smoke` MUST be resilient to an in-flight cross-workstream gap: `lib/api/analytics.py` does **not** exist on `main` yet (stranded in PR #8 / analytics-aggregator) — `import api.analytics` raises `ModuleNotFoundError` today (live-verified). A literal hard import of all six modules (as the ROADMAP success criterion lists) would FAIL on a fresh clone and violate "all three jobs green." Decision: smoke-import the `api.*` submodules **present on disk** under `lib/api/` with `PYTHONPATH=lib`, and treat `api.analytics` as a **soft/optional** import (warn, do not fail, when absent) so it auto-covers the moment PR #8 lands. Live-verified today: `PYTHONPATH=lib python -c "import api.projects, api.chat, api.tree_local, api.tree_vps, api.tree_repo"` succeeds on pure stdlib. A second smoke `python -m py_compile`s every `bin/invisible-*` **Python** script (syntax + executable-bit check) — NOT a full import (many bin scripts need heavy runtime deps to import).

### Dependencies
- **D-05:** No dependency manifest exists in the repo, and `lib/api/*` plus its transitive local imports (`config.py`, `checkpoint.py`, `dashboard_render.py`) are **pure stdlib** (live-verified — only `html`, `socket`, `threading`, `pathlib`, etc.). CI installs only `ruff` and `pytest`, pinned. Do NOT introduce a project-wide requirements file in this phase.

### Security-review track (PR #3)
- **D-06:** MERGE PR #3 as-is (ratified by the user). `ci.yml` is a **separate file** from PR #3's `security-review.yml` — they coexist with zero conflict (different filenames, different job names). Plan 01-02 performs `gh pr merge 3` **behind an explicit confirm step** (it mutates `main` of a public repo), then documents the two post-merge manual steps from PR #3's `SECURITY-REVIEW.md`: (1) set the `CLAUDE_API_KEY` repo secret, (2) register the `Claude security review` branch-protection required check. Do NOT author a competing `security-review.yml`.
  - **[REVERSED 2026-06-02]** PR #3 was merged (squash `692dc52`) then reverted off `main` (`23de0da`): `claude-code-security-review` only accepts an Anthropic API key, which conflicts with invisible's no-API-key (Claude Code CLI) design. The `CLAUDE_API_KEY` / required-check steps are VOID; semantic security review now runs locally via the `claude` CLI. `ci.yml` is keyless and unaffected.

### Branch protection
- **D-07:** Making `ci.yml` a required check on `main` (ROADMAP success criterion 5) is recorded as a **documented manual step** — the automation/owner may lack branch-protection permissions. The plan records the exact `gh api .../branches/main/protection` invocation and the job/check names, but does not assume it can execute it.

### Claude's Discretion
- Exact ruff rule selection within the "lenient, passes existing code" constraint.
- Single Python 3.11 vs a version matrix (single is fine; matrix optional).
- pip caching via `actions/setup-python` cache (nice-to-have, not required).
- Exact README badge markdown + placement.
- Whether pytest config sits in `pyproject.toml` vs `pytest.ini` (both acceptable).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase spec & fences
- `.planning/workstreams/ci-and-onboarding/ROADMAP.md` — Phase 1 success criteria (5) + plan breakdown (01-01, 01-02).
- `START_HERE.md` — files this workstream OWNS / EDITS LIGHTLY / MUST NOT TOUCH.

### Import-smoke targets (the `api` package lives under `lib/`; no `lib/__init__.py`)
- `lib/api/__init__.py` — package init; imports `projects, chat, tree_local, tree_vps, tree_repo`; defines `ROUTES`. (Contains two concatenated module docstrings from prior 4-way merges — harmless no-op.)
- `lib/api/{projects,chat,tree_local,tree_vps,tree_repo}.py` — present submodules (pure stdlib).
- `bin/invisible-dashboard` (lines 56–64) — canonical `sys.path.insert(0, str(HERE.parent / "lib"))` then `from api import ...`. CI mirrors this with `PYTHONPATH=lib`.

### Existing tests to wire
- `tests/test_api_projects.py` (+ `tests/__init__.py`) — hermetic; self-inserts `lib/` on path.
- `lib/api/test_chat.py` — test colocated with source; needs `testpaths` to include `lib/api/`.

### Security-review (merge, don't rewrite)
- PR #3 `chore/add-security-review-action` — `.github/workflows/security-review.yml` (SHA-pinned `anthropics/claude-code-security-review`) + `.github/SECURITY-REVIEW.md` runbook with the post-merge setup sequence.
</canonical_refs>

<specifics>
## Specific Ideas

- Local verification (ROADMAP): `gh workflow list`, `gh workflow run ci.yml`, `gh run watch`. CI can only be exercised once `ci.yml` is on a branch GitHub can see (push `ws/ci-and-onboarding`).
- Before trusting CI, run the import-smoke + pytest **locally** first (`PYTHONPATH=lib`) to catch anything env-specific — already done for the import-smoke (passes).
- The pre-push hook regenerates `CHANGELOG.md` and blocks stale pushes; CI itself does not push, so no interaction, but commits in this phase must keep the changelog current.
- Dev toolchain: python 3.11.4, node v22.14, `gh` CLI authed (from `.planning/CONTEXT.md`).
</specifics>

<deferred>
## Deferred Ideas

- Phase 2 (first-run wizard) — blocked on PR #7; not planned here.
- Phase 3 (`invisible-doctor` rewrite with `--json`) — separate plan.
- Tightening the ruff ruleset beyond "passes existing code."
- Promoting `api.analytics` to a hard import — auto-activates when PR #8 merges; revisit then.
- Retroactive security scan of already-merged M1 PRs (#1,#2,#4,#5,#6) via `workflow_dispatch` — noted in PR #3's runbook.
</deferred>

---

*Phase: INV-01-github-actions-ci*
*Context gathered: 2026-06-01 via recon (research disabled in config)*
