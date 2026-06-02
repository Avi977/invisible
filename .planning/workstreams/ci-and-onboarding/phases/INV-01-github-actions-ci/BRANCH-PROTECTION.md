# Branch Protection & Security-Review Runbook — `main` (Avi977/invisible)

> ⚠️ **SUPERSEDED (2026-06-02):** PR #3 / the `claude-code-security-review` action was **merged then reverted off `main`** (revert commit `23de0da`). That action only accepts an **Anthropic API key** (`claude-api-key`; no OAuth/subscription input — that's the *separate* `anthropics/claude-code-action`), which conflicts with `invisible`'s design: a **Claude Code CLI wrapper** on Max-plan subscription auth, **no API keys**. Therefore:
> - **D-06 is VOID** — do NOT set `CLAUDE_API_KEY`, do NOT register a `Claude security review` check. The action no longer exists on `main`.
> - **D-07 still applies**, but the required contexts are **only** `lint`, `test`, `import-smoke` — drop every `Claude security review` reference below.
> - Semantic security review now runs **locally via the `claude` CLI** (`/gsd:secure-phase`, `/security-review`) — free under Max, same auth as the rest of the app.
>
> The security-review sections below are retained for history only.

**Status:** DOCUMENTED, NOT EXECUTED.
**Why this file exists:** Phase 1 (INV-01-github-actions-ci) delivers a green CI
pipeline (`ci.yml` — jobs `lint`, `test`, `import-smoke`) and resolves the
security-review track (PR #3). Two classes of action **must not** be performed
silently by the automation, so they are recorded here as manual owner-permission
steps:

1. **Branch protection on `main`** — making CI / the security check *required*
   (decision **D-07**). Changing protection on the default branch of a **public**
   repo is an owner-scope, high-impact operation; the automation/owner may lack
   the `administration` permission. The plan records the exact invocation but does
   **not** run it.
2. **PR #3 post-merge setup** — the `CLAUDE_API_KEY` secret and registering the
   `Claude security review` required check (decision **D-06**), copied verbatim
   from PR #3's own `.github/SECURITY-REVIEW.md` so this runbook is self-contained.

> Run these from a shell with `gh` authenticated as a repo admin
> (`gh auth status` → account `Avi977`). Each `gh api` call below mutates GitHub
> server-side state on the **public** repo `Avi977/invisible`; review before running.

---

## D-07 — Make CI a required check on `main` (documented, not executed)

Once `ci.yml` has completed at least one successful run on `main` (so the check
contexts `lint` / `test` / `import-smoke` are registered and visible to the
protection API), make all three CI jobs **plus** the security-review check
required before any PR can merge into `main`:

```bash
# DOCUMENTED MANUAL STEP (D-07) — owner may lack branch-protection permission.
# Makes the three ci.yml jobs AND the security-review check required on main.
gh api -X PUT repos/Avi977/invisible/branches/main/protection \
  -F required_status_checks[strict]=true \
  -f required_status_checks[contexts][]="lint" \
  -f required_status_checks[contexts][]="test" \
  -f required_status_checks[contexts][]="import-smoke" \
  -f required_status_checks[contexts][]="Claude security review" \
  -F enforce_admins=false \
  -f required_pull_request_reviews=null \
  -f restrictions=null
```

Notes:
- **Context names = job names.** The CI contexts are the three `ci.yml` job
  names exactly: `lint`, `test`, `import-smoke`. The security context is the
  job `name:` field from PR #3's `security-review.yml`, i.e. `Claude security review`.
- `required_status_checks[strict]=true` forces a PR branch to be up-to-date with
  `main` before merge; drop to `false` if it gets annoying during the
  multi-workstream merge dance.
- `enforce_admins=false` lets the repo owner emergency-merge past the checks;
  flip to `true` for hard self-enforcement.
- **`Claude security review` only becomes registrable AFTER PR #3 is merged and
  its workflow has run once** (see step 3 below). If you run the protection call
  before that check exists, GitHub rejects the unknown context — register CI
  first, then re-run this with the security context added once it's live.
- PR #3's own `.github/SECURITY-REVIEW.md` contains a **sibling** `gh api`
  snippet that sets protection for just the `Claude security review` check; this
  file's call is the superset (CI jobs + security check together).

**Permission caveat (the reason this is documented-not-executed):** if the
authenticated user lacks the `administration` permission on the repo, this call
returns `403`. That is expected and acceptable per D-07 — record that the step is
pending an admin, do not attempt to work around it.

---

## D-06 — PR #3 (security-review) post-merge steps

PR #3 (`chore: add claude-code-security-review as required PR check`) adds
`.github/workflows/security-review.yml` (action pinned to the full SHA
`anthropics/claude-code-security-review@0c6a49f1fa56a1d472575da86a94dbc1edb78eda`)
and `.github/SECURITY-REVIEW.md`. It is merged **only behind explicit human
approval** (the blocking checkpoint in plan 01-02 / Task 3) because it writes to
`main` of a public repo. The merge itself is `gh pr merge 3 --squash`.

After the merge lands, complete these two REQUIRED manual steps (verbatim from
PR #3's `SECURITY-REVIEW.md` — half-set-up is worse than nothing):

### 1. Set the `CLAUDE_API_KEY` repo secret

```bash
gh secret set CLAUDE_API_KEY --body "$ANTHROPIC_API_KEY" --repo Avi977/invisible
```

Or via UI: **Settings → Secrets and variables → Actions → New repository secret**.

- This secret is consumed by **PR #3's `security-review.yml`** to authenticate the
  `claude-code-security-review` action. **`ci.yml` itself reads NO secrets** — the
  CI pipeline is pure read-only static analysis + tests.
- Without it, every security-review run fails loudly at the
  `Run claude-code-security-review` step (by design — no silent skips).
- **Never** echo, log, or commit the key; it must stay inside the GitHub/Anthropic
  trust boundary (threat T-01-08).

### 2. Register the `Claude security review` required check on `main`

GitHub only exposes the check name `Claude security review` after the
security-review workflow has **completed at least once**. Trigger a first run
(push any commit to an open PR, or `gh workflow run security-review.yml --repo
Avi977/invisible --ref main`), then add it as a required check:

```bash
# Just the security check (PR #3's own snippet). Prefer the D-07 superset above
# when registering CI + security together.
gh api repos/Avi977/invisible/branches/main/protection \
  --method PUT \
  -f required_status_checks[strict]=true \
  -f required_status_checks[contexts][]="Claude security review" \
  -F enforce_admins=false \
  -f required_pull_request_reviews=null \
  -f restrictions=null
```

---

## Verification checklist (after the manual steps are done)

```bash
# CI is green on the branch under test (already true at end of plan 01-02 Task 1):
gh run list --workflow ci.yml --branch ws/ci-and-onboarding --limit 1 \
  --json status,conclusion   # → status=completed, conclusion=success

# Required checks are wired on main:
gh api repos/Avi977/invisible/branches/main/protection/required_status_checks \
  --jq '.contexts'           # → ["lint","test","import-smoke","Claude security review"]

# The secret exists (value never printed):
gh secret list --repo Avi977/invisible | grep CLAUDE_API_KEY
```

---

## Threat notes (cross-ref 01-02-PLAN.md `<threat_model>`)

| Threat | Disposition | This runbook's role |
|--------|-------------|---------------------|
| T-01-06 — `gh pr merge 3` writes to public `main` | mitigate | Merge is human-gated (Task 3 blocking checkpoint); never auto-merged. |
| T-01-07 — `claude-code-security-review` action ref | mitigate | Keep the full-SHA pin `@0c6a49f1fa56a1d472575da86a94dbc1edb78eda`; reject the merge if it was changed to `@main`/a tag. |
| T-01-08 — `CLAUDE_API_KEY` handling | mitigate | Documented as a manual `gh secret set`; never echoed/committed; `ci.yml` never reads it. |
| T-01-09 — branch-protection API on `main` | accept (document-only) | This file IS the documented step; D-07 — recorded, not executed. |

---

*Phase: INV-01-github-actions-ci — Plan 01-02, Task 2*
*Decisions: D-06 (merge PR #3 + post-merge steps), D-07 (documented branch protection)*
*Generated: 2026-06-01*
