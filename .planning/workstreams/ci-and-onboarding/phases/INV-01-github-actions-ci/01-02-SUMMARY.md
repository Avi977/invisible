---
phase: INV-01-github-actions-ci
plan: 02
subsystem: infra
tags: [github-actions, ci, badge, branch-protection, security-review, pr-merge]

# Dependency graph
requires:
  - phase: INV-01 / plan 01
    provides: .github/workflows/ci.yml + ruff.toml + pyproject.toml (the three CI config files this plan pushes and proves green on GitHub)
provides:
  - Verified green CI run on GitHub for ws/ci-and-onboarding — all three jobs (lint, test, import-smoke) conclusion=success (D-03)
  - README CI status badge under the # invisible title (light edit)
  - BRANCH-PROTECTION.md runbook — documented D-07 required-check gh api call (contexts lint/test/import-smoke + "Claude security review") and D-06 PR #3 post-merge steps (CLAUDE_API_KEY secret, register check)
affects: [Phase-2 first-run-wizard (CI now gates its PRs once protection is set), PR #3 merge (MERGED — squash 692dc52, human-approved), branch-protection-on-main (documented manual step, owner-gated)]

# Tech tracking
tech-stack:
  added: []  # no new tooling — ci.yml/ruff/pytest pins all landed in 01-01; this plan pushes + verifies + documents
  patterns: ["local-first verification (run ruff+pytest+import-smoke in a throwaway venv before the CI round-trip)", "gh run watch --exit-status as the green-gate", "irreversible main-mutations (PR merge, branch protection) gated behind a blocking human-verify checkpoint", "secrets + owner-scope GitHub config recorded as documented-not-executed manual steps"]

key-files:
  created: [".planning/workstreams/ci-and-onboarding/phases/INV-01-github-actions-ci/BRANCH-PROTECTION.md"]
  modified: ["README.md"]

key-decisions:
  - "Verified the SAME pinned tools CI uses (ruff==0.15.15, pytest==9.0.3) locally in a THROWAWAY venv in $TMPDIR — never installed into the system or the repo (respects the venv rule); deleted after the run."
  - "Pushed twice and confirmed green twice: SHA 7c573f9 (run 26798406044) after the initial push, then SHA dec86a2 (run 26798471337) after the Task-2 README/runbook commit — the badge reflects the latest pushed SHA green."
  - "Node.js 20 deprecation warnings on actions/checkout@v4 + actions/setup-python@v5 are annotations, not failures; major-tag pinning is this phase's agreed bar (D-01) and silencing them would mean editing action pins — left untouched, logged to deferred-items."
  - "Task 3 (gh pr merge 3) STOPPED at the blocking checkpoint — never auto-merged (D-06 + always_confirm_destructive); PR #3 SHA pin re-confirmed intact before handing the decision to the human."

patterns-established:
  - "Green-gate: `gh run list --workflow ci.yml --branch <b> --limit 1 --json status,conclusion` must read completed/success AND every per-job conclusion must be success before a plan calls CI green."
  - "Public-main mutations (PR merge, branch-protection PUT) are blocking-human-verify checkpoints; the executor re-verifies the third-party action SHA pin and presents the decision rather than acting."

requirements-completed: []

# Metrics
duration: ~12min
completed: 2026-06-01
---

# Phase INV-01 Plan 02: Verify CI Green on GitHub + Badge + Branch-Protection Runbook Summary

**All three CI jobs (lint, test, import-smoke) confirmed green on GitHub for ws/ci-and-onboarding (verified locally first in a throwaway venv, then via `gh run watch` on two pushed SHAs), the README CI badge added under the title, and a BRANCH-PROTECTION.md runbook written documenting the D-07 required-check `gh api` call and PR #3's D-06 post-merge steps — with the gated PR #3 merge STOPPED at a blocking human-verify checkpoint (not merged).**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-02T04:27:24Z
- **Completed:** 2026-06-01 (Tasks 1-2; Task 3 paused at checkpoint)
- **Tasks:** 3 of 3 complete (Task 3 — PR #3 merge approved by the human; executed by the orchestrator)
- **Files modified:** 2 (1 created, 1 light-edited)

## Accomplishments
- **Task 1 — CI green on GitHub (D-03):** Ran `ruff check lib/ bin/` (exit 0, "All checks passed!"), `PYTHONPATH=lib pytest -q` (22 passed), and the import-smoke logic (5 hard `api.*` imports OK, `api.analytics` soft-skipped, 21 Python bin scripts py_compiled / 2 bash skipped) **locally first** using the exact CI pins in a throwaway venv. Pushed `ws/ci-and-onboarding`; the pre-push hook ran clean (CHANGELOG already current). Watched run **26798406044** (SHA `7c573f9`) → `completed/success`, all three jobs green. After the Task-2 commit, the follow-up run **26798471337** (SHA `dec86a2`) is also `completed/success` (lint, test, import-smoke each `success`) — so the badge resolves green on the latest pushed SHA.
- **Task 2 — badge + runbook (D-06, D-07):** Added `![ci](https://github.com/Avi977/invisible/actions/workflows/ci.yml/badge.svg)` on README line 3, directly under `# invisible` (pure +2-line addition, no other section touched). Wrote `BRANCH-PROTECTION.md` in the phase dir with the exact `gh api -X PUT .../branches/main/protection` call (contexts `lint`, `test`, `import-smoke`, `Claude security review`), PR #3's two post-merge steps (set `CLAUDE_API_KEY`; register the `Claude security review` check), and an explicit "documented-not-executed / owner may lack permission" statement.
- **Task 3 — gated merge STOPPED (not executed):** Re-confirmed PR #3 is OPEN, `MERGEABLE`/`CLEAN`, adds exactly the 2 security-review files, and is still SHA-pinned to `anthropics/claude-code-security-review@0c6a49f1fa56a1d472575da86a94dbc1edb78eda` (not `@main`/a tag). Did **not** run `gh pr merge 3` — returned a blocking checkpoint for human approval.

## Task Commits

1. **Task 1: Push branch, confirm all three CI jobs green on GitHub** — no source-file commit (local verify + `git push` only, per the plan's `<files>`); the branch was already at the right SHA from 01-01. CI run 26798406044 = success.
2. **Task 2: Add README CI badge + write BRANCH-PROTECTION.md runbook** — `dec86a2` (docs)
3. **Task 3: Gated merge of PR #3** — NOT executed; blocking `checkpoint:human-verify` returned to the orchestrator.

**Plan metadata:** this SUMMARY commit (docs) — STATE.md / ROADMAP.md intentionally NOT updated (orchestrator owns those writes).

## Files Created/Modified
- `README.md` — added the CI status badge on line 3, under the `# invisible` title (light edit, +2 lines, 0 deletions).
- `.planning/workstreams/ci-and-onboarding/phases/INV-01-github-actions-ci/BRANCH-PROTECTION.md` (151 lines) — D-07 branch-protection `gh api` runbook (contexts = lint/test/import-smoke + "Claude security review") + D-06 PR #3 post-merge steps (CLAUDE_API_KEY secret, register check), both flagged documented-not-executed; threat cross-ref table (T-01-06/07/08/09).

## Decisions Made
- **Local-first with CI-identical pins:** verified ruff==0.15.15 + pytest==9.0.3 in a throwaway venv under `$TMPDIR` (never the system, never inside the repo — honors the venv rule), then deleted it. All three checks passed locally before any push, so the GitHub round-trip was a confirmation, not a discovery.
- **Two green confirmations:** the initial push (SHA `7c573f9`) and the Task-2 commit push (SHA `dec86a2`) each produced a fully-green run; the README badge therefore reflects a green latest-SHA, not a stale one.
- **PR #3 left OPEN by design:** merging mutates `main` of a public repo (T-01-06) — gated behind the Task-3 blocking checkpoint per D-06 and the project's confirm-before-irreversible policy. The SHA pin was re-verified intact so the human can approve safely.

## Deviations from Plan

None — plan executed exactly as written for Tasks 1-2. No deviation rules (1-3) were triggered: all three CI jobs were green on the first GitHub run with no config fixes required (the 01-01 ruff/pytest config absorbed everything), so no MUST-NOT-TOUCH file was approached. Task 3 is intentionally paused at its blocking checkpoint, not a deviation.

## Issues Encountered
- **Node.js 20 deprecation annotations** on `actions/checkout@v4` and `actions/setup-python@v5` (GitHub forces Node 24 from 2026-06-16). These are **warnings, not failures** — every job still concluded `success`. Major-tag pinning is this phase's agreed security bar (D-01); silencing the warning would require editing the action pins (a hardening task, not in this plan's scope). Logged to `deferred-items.md`; not fixed here.

## Deferred Issues
- Node 20 → Node 24 action runtime: bump `actions/checkout` / `actions/setup-python` (and/or set `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true`) before GitHub's 2026-06-16 default flip. Tracked in `deferred-items.md`. Out of scope for plan 01-02.

## User Setup Required
**Two GitHub-side manual steps remain (documented, NOT executed by this plan)** — see [BRANCH-PROTECTION.md](./BRANCH-PROTECTION.md):
1. **After PR #3 is merged (Task 3 approval):** `gh secret set CLAUDE_API_KEY --body "$ANTHROPIC_API_KEY" --repo Avi977/invisible`, then trigger the security-review workflow once and register the `Claude security review` required check (D-06).
2. **Branch protection (D-07):** `gh api -X PUT repos/Avi977/invisible/branches/main/protection` with contexts `lint`, `test`, `import-smoke`, `Claude security review` — owner may lack `administration` permission; recorded, not run.

## Task 3 — PR #3 MERGED then REVERTED off main

> **2026-06-02 update:** PR #3 was reverted off `main` (revert commit `23de0da`). `claude-code-security-review` only accepts an Anthropic **API key**, which conflicts with `invisible`'s no-API-key (Claude Code CLI) design — so it was removed at the user's direction immediately after merge. Semantic security review now runs locally via the `claude` CLI. The merge record below is retained for history.

- **Decision:** the human approved the merge at the blocking checkpoint ("Merge PR #3 now (squash)").
- **Executed by the orchestrator** (the `SendMessage` resume path was unavailable): re-verified the action SHA pin intact one final time (`@0c6a49f1fa56a1d472575da86a94dbc1edb78eda`, not `@main`/a tag) with PR #3 `OPEN`/`MERGEABLE`/`CLEAN`, then ran `gh pr merge 3 --squash`.
- **Result:** PR #3 → state `MERGED` at `2026-06-02T04:35:41Z`; squash commit `692dc52199a7971c65b25fb99b916ff40159fc00`; `.github/workflows/security-review.yml` confirmed present on `main` via `gh api`.
- **No competing `security-review.yml` was authored** — PR #3 remained the single source of truth (D-06).
- **Still owner-gated (documented, NOT executed):** set the `CLAUDE_API_KEY` secret, register the `Claude security review` required check, and apply branch protection — all in BRANCH-PROTECTION.md. Until the secret is set, the security-review check will error (non-blocking) on PRs into `main`.

## Next Phase Readiness
- CI is proven green on GitHub for ws/ci-and-onboarding; the badge is live; the branch-protection + PR #3 runbook is in place. Once the human approves the Task-3 merge and the two BRANCH-PROTECTION.md steps are done, Phase 1's success criteria (incl. criterion 5 / D-07) are fully satisfied.
- No MUST-NOT-TOUCH file was modified (`lib/`, other `bin/`, `frontend/`, `release.yml`, PR #3's `security-review.yml` all untouched). STATE.md / ROADMAP.md left for the orchestrator.

## Self-Check: PASSED

- FOUND: `README.md` (contains `actions/workflows/ci.yml/badge.svg`)
- FOUND: `.planning/workstreams/ci-and-onboarding/phases/INV-01-github-actions-ci/BRANCH-PROTECTION.md`
- FOUND: `.planning/workstreams/ci-and-onboarding/phases/INV-01-github-actions-ci/01-02-SUMMARY.md`
- FOUND: `.planning/workstreams/ci-and-onboarding/phases/INV-01-github-actions-ci/deferred-items.md`
- FOUND commit: `dec86a2` (Task 2)
- VERIFIED on GitHub: ci.yml run 26798471337 (SHA dec86a2) → status=completed, conclusion=success (lint, test, import-smoke all green)

---
*Phase: INV-01-github-actions-ci*
*Completed: 2026-06-01 (Tasks 1-2); Task 3 (PR #3 merge) human-approved + merged 2026-06-02 (squash 692dc52)*
