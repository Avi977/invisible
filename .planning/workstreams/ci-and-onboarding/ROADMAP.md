# Workstream: ci-and-onboarding (M2 — production readiness)

> Sister-workstreams: tauri-windows, vps-connection, tools-page,
> relations-page, calendar-events. Mostly isolated — new directories
> (.github/workflows/, frontend/onboarding/), one README edit.

## Phases

- [ ] **Phase 1: GitHub Actions CI** — lint + test + import-smoke on push/PR
- [ ] **Phase 2: First-run wizard** — Tauri-side onboarding (Infisical creds, VPS host, first project)
- [ ] **Phase 3: `invisible-doctor` polish** — fresh-machine setup story

### Phase 1: GitHub Actions CI

**Goal:** Every push and PR runs lint + tests + an import-smoke. PR #3
(claude-code-security-review) merges in or is replaced by an equivalent
job.

**Success criteria:**
1. `.github/workflows/ci.yml` exists.
2. Three jobs:
   - **lint**: `ruff check lib/ bin/` (or `pylint` if you prefer)
   - **test**: `pytest tests/` (existing tests/ dir; run what's there)
   - **import-smoke**: `python -c "import api.projects, api.chat, api.tree_local, api.tree_vps, api.tree_repo, api.analytics"` plus a similar smoke for `bin/invisible-*` scripts being executable
3. All three pass on a fresh clone.
4. Workflow runs on `push` (any branch) and `pull_request` targeting `main`.
5. Required-check on the `main` branch in GitHub branch-protection (you may not have permissions; document the manual setting).

**Plans:** 2 plans
- [ ] 01-01-PLAN.md — Create `.github/workflows/ci.yml` (lint + test + import-smoke jobs), `ruff.toml`, and pytest config (`pyproject.toml`). Covers D-01..D-05.
- [ ] 01-02-PLAN.md — Verify all 3 jobs green on GitHub, add README CI badge, document branch-protection (BRANCH-PROTECTION.md), and merge PR #3 behind a confirm. Covers D-03, D-06, D-07.

### Phase 2: First-run wizard

**Goal:** A new user running the Tauri app for the first time gets a
guided setup: Infisical creds, VPS host (optional), first project, then
lands on the Dashboard.

**Success criteria:**
1. On Tauri launch, if `~/.invisible/.env` does not exist OR the
   Infisical bootstrap creds are missing, show a first-run wizard
   instead of the main UI.
2. Wizard steps: (a) Welcome + explain what invisible is, (b) Infisical
   project + client creds (with link to Infisical docs), (c) Optional
   VPS host, (d) First project — pick a local directory or skip, (e)
   "doctor" check, (f) Done → write `.env` + `invisible.toml`, restart.
3. Wizard works in both pywebview AND Tauri (or document Tauri-only).
4. Step (e) actually invokes `invisible-doctor` and renders its output
   in the wizard.

**Plans:** 2 plans
- [ ] 02-01: Wizard React component(s) under `frontend/onboarding/`
- [ ] 02-02: Tauri-side bridge: detect missing config, route to wizard, write files on completion

### Phase 3: invisible-doctor polish

**Goal:** A fresh-machine clone + `./scripts/install-hooks.sh` + run
`invisible-doctor` should clearly tell the user what's missing and how
to fix it.

**Success criteria:**
1. Doctor checks every dependency: node, pnpm, rust, cargo-tauri,
   codex CLI, claude CLI, gh CLI, Python deps, Infisical reachability,
   Notion API, VPS SSH (if configured).
2. Each failed check has a one-line remediation (`run: brew install X`
   or similar).
3. Exit code reflects severity: 0 = all green, 1 = warnings only, 2 = blockers.
4. `--json` flag for CI/scripting.

**Plans:** 1 plan
- [ ] 03-01: Doctor rewrite — extract individual checks into testable functions; add remediation hints

## Files this workstream OWNS

- `.github/workflows/ci.yml` (new)
- `.github/workflows/security-review.yml` (new — replacement for PR #3 if you choose not to merge it)
- `frontend/onboarding/*.jsx` (new directory)
- `bin/invisible-doctor` — REWRITE (this is yours; do NOT do hot fixes elsewhere)
- `pyproject.toml` or `ruff.toml` (if needed)

## Files this workstream EDITS LIGHTLY

- `README.md` — first-run section + CI badge
- `frontend/app.jsx` — ONE conditional render: if wizard-needed, render `<OnboardingWizard/>`. ~5 lines.

## Files this workstream MUST NOT TOUCH

- Any `lib/api/*` (siblings' domain)
- Any other `frontend/pages/*.jsx` or `frontend/ai-chat.jsx`
- `bin/invisible-*` other than `invisible-doctor`
- `src-tauri/src/` other than light frontend-bridge additions if Phase 2 requires
- `.github/workflows/release.yml` — owned by `tauri-windows`

## Verify locally

```bash
# Phase 1
gh workflow list
gh workflow run ci.yml
gh run watch

# Phase 2
# Wipe .env to trigger wizard
mv ~/.invisible/.env ~/.invisible/.env.bak
cargo tauri dev   # should land on the wizard
mv ~/.invisible/.env.bak ~/.invisible/.env

# Phase 3
invisible-doctor                 # plain
invisible-doctor --json | jq .   # structured
```

## Resume

```bash
cd ~/.invisible-ws/ci-and-onboarding
gsd-sdk query workstream.set ci-and-onboarding --raw --cwd .
/gsd:plan-phase 1
```
