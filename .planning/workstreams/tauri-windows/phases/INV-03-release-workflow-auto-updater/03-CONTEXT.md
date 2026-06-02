# Phase 3: GitHub Actions release.yml + auto-updater — Context

**Gathered:** 2026-06-02
**Status:** Ready for planning
**Source:** Inline seed (autonomous run; Phase 1 + 2 LOCKED decisions still apply)

<domain>
## Phase Boundary

This phase produces a **tag-triggered GitHub Actions workflow** that builds Windows + macOS Tauri binaries and publishes them — plus a Tauri auto-updater `latest.json` manifest — to a GitHub Release.

**In scope:**
- New file: `.github/workflows/release.yml`
- Update `src-tauri/tauri.conf.json` to add `bundle.createUpdaterArtifacts: true` so the bundler emits the `.sig` files the updater needs
- Document the manual user ceremony for adding `TAURI_SIGNING_PRIVATE_KEY` (and optional password) to GitHub Actions secrets — reading from Infisical (after the user completes `INFISICAL-MANUAL-ACTION.md` from Plan 02-02)
- Verification recipe — `tag v0.1.0-test → push → watch CI → confirm artefacts` — documented for the user; NOT executed by the autonomous run

**Out of scope (explicitly):**
- Linux builds (deferred to v0.2)
- Universal macOS binaries (single-arch per Phase 2 CONTEXT)
- macOS code-signing / notarisation (still deferred — Apple Dev ID NOT purchased per 02-CONTEXT)
- Windows code-signing (no cert; same trade-off as macOS)
- Triggering the first actual release (must be done manually by user; autonomous tag-push is too risky without verification)
</domain>

<decisions>
## Implementation Decisions

### CI runner strategy
- **LOCKED: Native runners per platform.** macOS-latest for `.app/.dmg`; windows-latest for `.exe`. **NOT** `cargo xwin` from macOS for CI (that was Phase 1's LOCAL-only optimization). Native runners are simpler, faster, and what `tauri-apps/tauri-action` was designed for.
- **LOCKED:** Phase 1's `cargo xwin` setup stays in place for the user's local Windows builds; only CI uses native windows-latest.

### Workflow trigger
- **LOCKED: Tag-push trigger.** `push.tags: ['v*']` (NOT `app-v*` from the Tauri docs example — `v*` matches our v0.1.0 versioning convention used by the auto-changelog).
- **LOCKED: NO** `workflow_dispatch` (manual trigger). Tag is the single source of truth for "this is a release".
- **LOCKED:** Releases are created in DRAFT mode (`draft: true`); user reviews and clicks "Publish" before they go live to users. Belt-and-suspenders against accidental tag pushes.

### Frontend build chain
- **LOCKED:** `pnpm install --frozen-lockfile` for reproducible installs (NOT `npm install`). Matches our local-dev pattern.
- **LOCKED:** Working directory: repo root (NOT inside `frontend-vite/` — the Tauri action's `pnpm tauri build` reads `tauri.conf.json` and runs `beforeBuildCommand` which `cd`s into `frontend-vite/` itself).

### Updater signing
- **LOCKED:** Env vars: `TAURI_SIGNING_PRIVATE_KEY` + `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` (canonical Tauri 2.x names per official docs).
- **LOCKED:** Both come from GitHub Actions secrets (NOT direct Infisical fetch). The user copies once from Infisical → GHA secrets; simpler than wiring Infisical machine identity. Documented in handoff.
- **LOCKED:** `bundle.createUpdaterArtifacts: true` added to `src-tauri/tauri.conf.json` so the bundler emits the `.sig` files the updater needs and tauri-action generates `latest.json`.

### Release content
- **LOCKED:** `tauri-apps/tauri-action@v0` action. It handles: builds, packaging, uploading to GitHub Release, generating `latest.json`.
- **LOCKED:** Release name: `v__VERSION__` (the action substitutes the version from `Cargo.toml` / `tauri.conf.json`).
- **LOCKED:** Release body includes a link to `INFISICAL-MANUAL-ACTION.md` (one-shot only on first release) so the user knows the post-tag ceremony.
- **LOCKED:** `prerelease: false` (the `draft: true` gate is enough; releases tagged with `-rc`, `-beta` suffixes can opt into prerelease via a future workflow_dispatch input if needed).

### Concurrency + permissions
- **LOCKED:** `permissions.contents: write` (only thing tauri-action needs).
- **LOCKED:** `concurrency.group: release-${{ github.ref }}` + `cancel-in-progress: false` (release builds must complete; no point cancelling halfway).
- **LOCKED:** No matrix `fail-fast: false` — if Windows build fails, still try to ship macOS (and vice versa). Better partial release than no release.

### Verification posture (NOT executed by autonomous run)
- **LOCKED:** Phase 3 ships **the workflow file**, not a successful release. The first real release is gated on user uploading the Infisical secret to GHA secrets — see deferred items.
- **LOCKED:** Phase 3 SUMMARY documents the user verification recipe (tag v0.1.0-test, watch CI, delete the test release after).

### Claude's Discretion
- Exact step ordering inside the workflow (setup-pnpm vs setup-node ordering, rust-cache key)
- Whether to add a `verify` job that runs `pnpm test` before publish (NICE-TO-HAVE; gated on whether the frontend has tests — verified inline at execution time)
- Whether to add `swatinem/rust-cache@v2` for Rust target caching (yes — meaningful CI speedup; tauri builds are slow)
</decisions>

<canonical_refs>
## Canonical References

### Tauri docs
- GitHub publishing pipeline: https://v2.tauri.app/distribute/pipelines/github/
- Updater plugin (env vars): https://v2.tauri.app/plugin/updater/
- tauri-apps/tauri-action README: https://github.com/tauri-apps/tauri-action

### Project memory
- `[[infisical_vault]]` — Infisical project location, key naming convention
- `INFISICAL-MANUAL-ACTION.md` (Phase 2) — the upstream ceremony Phase 3 depends on
- 02-CONTEXT.md "Tauri auto-updater keypair" LOCKED block
- 02-CONTEXT.md "Apple Developer Program / Signing" LOCKED block (still applies — no Dev ID for v0.1)

### Sibling workstream concerns
- Phase 3 owns `.github/workflows/release.yml` — NEW file, no conflicts
- Phase 3 lightly edits `src-tauri/tauri.conf.json` — only adds `bundle.createUpdaterArtifacts: true`; supersedes Phase 2's verify-time assertion that this key is absent (documented in SUMMARY)
- Phase 3 lightly edits `.planning/workstreams/tauri-windows/ROADMAP.md` — marks Phase 3 complete with plan link
</canonical_refs>

<specifics>
## Specific Ideas

- Use the exact tauri-action invocation from the official docs but with our env vars, pnpm, and `v__VERSION__` tag pattern.
- For the macOS step, set `args: '--target aarch64-apple-darwin'` because that matches what 02-01 verified. Skip x86_64 macOS (no demand for Intel Mac on a personal-cockpit app; reduces CI time by 50%).
- For Windows, no `args` needed — native windows-latest builds the default target.
- Drop a deliberately-empty `verify:` README-link in the release body the first time so the user has a clear "what next" pointer.
- Add a `release.yml` comment block at the top citing 03-CONTEXT.md as the source-of-truth for design decisions.

## Tauri-action handles latest.json automatically

Per official docs, when `bundle.createUpdaterArtifacts: true` is set, tauri-action automatically generates and uploads `latest.json` to the release. No custom step needed.
</specifics>

<deferred>
## Deferred Ideas

- **Linux builds** (`.AppImage`, `.deb`) — defer to v0.2 / when a Linux user asks
- **Universal macOS binaries** — defer; single-arch is fine
- **macOS / Windows code-signing** — still deferred (no certs)
- **Auto-tag from PR merge** — defer; manual tagging keeps the user in control
- **Discord / Telegram webhook on successful release** — nice-to-have; not blocking v0.1
- **PR check workflow** (lint, test on every PR) — different concern; `ci-and-onboarding` workstream owns CI hardening
- **Releasing the first actual binary tonight** — autonomous run does NOT push a tag. The user does that after uploading `TAURI_SIGNING_PRIVATE_KEY` to GitHub Actions secrets.
</deferred>

---

*Phase: INV-03-release-workflow-auto-updater*
*Context seeded inline: 2026-06-02 (autonomous run; single locked decision-set; no relitigation required)*
