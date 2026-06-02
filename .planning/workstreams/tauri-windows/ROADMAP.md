# Workstream: tauri-windows (M2 — production Tauri builds)

> Sister-workstreams: vps-connection, tools-page, relations-page,
> calendar-events, ci-and-onboarding. Fully isolated — operates inside
> `src-tauri/` only, plus one new GitHub Actions workflow.

## Prerequisite

**PR #7 must merge first** (lands `src-tauri/` in main). This workstream
extends what PR #7 brings. If PR #7 isn't merged when you start, your
first action is to wait — `/gsd:plan-phase 1` should error out cleanly
if `src-tauri/` isn't on `main`.

## Phases

- [ ] **Phase 1: Windows `.msi` cross-compile** — `cargo xwin` or NSIS bundler from macOS
- [ ] **Phase 2: macOS `.app` + `.dmg` with signing** — Developer ID Application cert
- [ ] **Phase 3: GitHub Actions `release.yml` + auto-updater** — tag-triggered builds + signed update manifest

## Phase 1 Details — Windows .msi cross-compile

**Goal:** `cargo tauri build --target x86_64-pc-windows-msvc` produces a working `.msi` from this Mac. Installable on a fresh Windows 11 box; launches the app, connects to a configured `INVISIBLE_SERVER_URL`, file dashboard works.

**Approach:** Use `cargo xwin` (cross-compile via Microsoft's MSVC stub) — avoids needing a Windows VM. Tauri 2.x's WiX-based bundler runs on macOS for the .msi step.

**Success criteria:**
1. `cargo xwin --version` resolves; `cargo install cargo-xwin` adds it.
2. `src-tauri/tauri.conf.json` `bundle.targets` includes `"msi"` (already there from PR #7).
3. `src-tauri/tauri.conf.json` has a `bundle.windows.wix` block with productName, manufacturer, upgradeCode (uuidgen'd once and locked).
4. `cargo tauri build --target x86_64-pc-windows-msvc` succeeds; output at `src-tauri/target/x86_64-pc-windows-msvc/release/bundle/msi/Invisible_0.1.0_x64_en-US.msi` (or similar).
5. SHA256 of the .msi captured in `PHASE-VERIFICATION.md`.

**Plans:** 2 plans
- [ ] 01-01: Install `cargo xwin`, configure WiX block in tauri.conf.json, first successful Windows build
- [ ] 01-02: Smoke-test the .msi (manually on a Windows VM, or via documented checklist if no VM available)

## Phase 2 Details — macOS .app + .dmg with signing

**Goal:** Signed + notarised `.app` and `.dmg` so users get no Gatekeeper warning.

**Success criteria:**
1. Developer ID Application certificate is documented (probably ask the user — they may not have one yet; if so, defer notarisation and ship unsigned with a documented "right-click → Open" workaround).
2. `cargo tauri build` (no target = current macOS) produces `.app` and `.dmg`.
3. If signing is configured: `codesign --verify --verbose` returns 0; `spctl -a -t exec` reports accepted.
4. Tauri auto-updater config has the public key + endpoint URL placeholders ready (filled in Phase 3).

**Plans:** 2 plans
- [ ] 02-01: macOS build pipeline (with or without signing, per cert availability)
- [ ] 02-02: Auto-updater public key + signing key pair generated, stored in Infisical, referenced from tauri.conf.json

## Phase 3 Details — GitHub Actions `release.yml`

**Goal:** Tag-triggered release pipeline: `git tag v0.1.0 && git push --tags` produces signed Windows + macOS binaries attached to a GitHub Release, plus a Tauri update manifest.

**Success criteria:**
1. `.github/workflows/release.yml` runs on tag pushes.
2. Two jobs: `build-windows` (cross-compile from ubuntu-latest or macOS-latest with cargo xwin) and `build-macos` (native).
3. Both upload artefacts to the GitHub Release.
4. Update manifest (`latest.json`) generated and uploaded.
5. Manual verification: tag a `v0.1.0-test`, watch CI, confirm artefacts appear on the release page.

**Plans:** 1 plan (split if needed)
- [ ] 03-01: Workflow file + secret wiring (signing certs as GitHub Actions secrets)

## Files this workstream OWNS

- `src-tauri/tauri.conf.json` — `bundle.windows.wix.*` and `bundle.macOS.signingIdentity` additions only (do NOT touch identifier, devUrl, frontendDist, beforeDevCommand)
- `src-tauri/Cargo.toml` — may add `[target.'cfg(windows)'.dependencies]` if needed
- `.github/workflows/release.yml` — new file

## Files this workstream EDITS LIGHTLY

- `README.md` — add a "Download" section with link to Releases page
- `ROADMAP.md` (project-level) — tick Phase 3 sub-items as they complete

## Files this workstream MUST NOT TOUCH

- `frontend/` and `frontend-vite/` — locked.
- `bin/invisible-*`, `lib/*.py` — sibling workstreams own these.
- `src-tauri/src/*.rs` — locked from PR #7.
- `.github/workflows/ci.yml`, `.github/workflows/security-review.yml` — owned by `ci-and-onboarding`.

## Verify locally

```bash
source "$HOME/.cargo/env"
cd src-tauri

# Phase 1
cargo install cargo-xwin
cargo tauri build --target x86_64-pc-windows-msvc
ls target/x86_64-pc-windows-msvc/release/bundle/msi/*.msi

# Phase 2 (signing optional)
cargo tauri build
ls target/release/bundle/dmg/*.dmg
codesign --verify --verbose target/release/bundle/macos/Invisible.app

# Phase 3
gh workflow run release.yml -f tag=v0.1.0-test
gh run watch
```

## Resume in a fresh Claude session

```bash
cd ~/.invisible-ws/tauri-windows
gsd-sdk query workstream.set tauri-windows --raw --cwd .
# then in Claude:
/gsd:plan-phase 1
```
