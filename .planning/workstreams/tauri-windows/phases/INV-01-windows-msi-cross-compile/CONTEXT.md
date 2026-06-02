# Phase 1: Windows .msi cross-compile — CONTEXT

## Goal (verbatim from workstream ROADMAP)

`cargo tauri build --target x86_64-pc-windows-msvc` produces a working
`.msi` from this Mac. Installable on a fresh Windows 11 box; launches
the app, connects to a configured `INVISIBLE_SERVER_URL`, file dashboard
works.

## Approach

Use `cargo xwin` — a thin wrapper around `xwin` that downloads Microsoft's
MSVC headers + libraries on demand, runs cargo with the right linker
configuration. This avoids needing a Windows VM or WSL.

`cargo tauri build --target x86_64-pc-windows-msvc` from macOS will
internally invoke `cargo xwin build --target x86_64-pc-windows-msvc`
through Tauri's build pipeline (Tauri 2.11 auto-detects when running on a
non-Windows host with `cargo-xwin` available).

## Inputs — what exists today

- `src-tauri/Cargo.toml` (from PR #7, on `ws/tauri-shell` — this branch is
  rebased on top, so present here)
- `src-tauri/tauri.conf.json` (from PR #7)
  - `identifier: com.theprofitplatform.invisible`
  - `bundle.targets: ["app", "dmg"]` — **need to add `"msi"`**
  - `bundle.icon` includes `icons/icon.ico` (Windows)
- `src-tauri/build.rs` (from PR #7)
- `frontend-vite/dist/` will be re-built by `beforeBuildCommand: "cd frontend-vite && pnpm build"`

## Constraints

- **PR #7 stacking:** This workstream's branch sits on top of `ws/tauri-shell`
  (PR #7). The PR for this workstream targets `ws/tauri-shell` for review,
  auto-converts to `main` when PR #7 merges. Do NOT rebase onto `main`
  until PR #7 lands.
- **No code signing in this phase.** Phase 2 handles signing for both
  platforms. Phase 1 produces an unsigned `.msi` — note this in the README
  and the verification doc.
- **No upgrade code yet.** Tauri auto-generates an UpgradeCode UUID per
  Identifier at build time. For Phase 1 we let it auto-gen; Phase 2 / 3
  lock it into `tauri.conf.json` for stable upgrade semantics.
- **Frontend build:** the bundler will run `pnpm build` in `frontend-vite/`
  before the Rust build. Ensure pnpm is on PATH for the Tauri build process.

## Toolchain state (verified 2026-06-02)

| Tool | State |
|------|-------|
| rustc 1.95.0 | ✓ installed |
| cargo 1.95.0 | ✓ installed |
| cargo-tauri 2.11.2 | ✓ installed |
| cargo-xwin | **NOT installed** — Task 1 installs |
| rustup target `x86_64-pc-windows-msvc` | **NOT installed** — Task 1 installs |
| node 22.14 | ✓ |
| pnpm | ✓ via corepack |

## Success criteria (verbatim from ROADMAP)

1. `cargo xwin --version` resolves; `cargo install cargo-xwin` adds it.
2. `src-tauri/tauri.conf.json` `bundle.targets` includes `"msi"`.
3. `src-tauri/tauri.conf.json` has a `bundle.windows.wix` block with productName, manufacturer (likely "Ace" or "The Profit Platform"), and `language: ["en-US"]`.
4. `cargo tauri build --target x86_64-pc-windows-msvc` succeeds; output at `src-tauri/target/x86_64-pc-windows-msvc/release/bundle/msi/Invisible_0.1.0_x64_en-US.msi`.
5. SHA256 of the `.msi` captured in `PHASE-VERIFICATION.md`.
6. The `.msi` file size is in a sane range (15-40 MB for a Tauri shell + Vite-built React frontend).

## Files this phase WRITES

- `src-tauri/tauri.conf.json` — add `bundle.windows.wix` block + add `"msi"` to `bundle.targets`
- `.planning/workstreams/tauri-windows/phases/INV-01-windows-msi-cross-compile/CONTEXT.md` (this file)
- `.planning/workstreams/tauri-windows/phases/INV-01-windows-msi-cross-compile/PLAN.md` (planner output)
- `.planning/workstreams/tauri-windows/phases/INV-01-windows-msi-cross-compile/PHASE-VERIFICATION.md` (post-build, with SHA256)

## Files this phase MUST NOT TOUCH

- `frontend/` and `frontend-vite/src/` — locked.
- `src-tauri/Cargo.toml` other than potentially adding a `[profile.release]` block (already standard; may not be needed).
- `src-tauri/src/*.rs` — locked from PR #7.
- `bin/invisible-*`, `lib/*.py` — siblings.
- `.github/workflows/release.yml` — that's Phase 3 of this workstream.

## Failure modes to handle

1. **First `cargo xwin` invocation downloads ~700 MB MSVC headers** — slow but expected. Don't time out the verify gate; allow 30 min for the first run.
2. **WiX template missing** — Tauri ships a default WiX template; no setup needed. If the build complains about WiX, install `wix` via Homebrew (`brew install wixtools`).
3. **Symlink resolution on cross-compile** — cargo-xwin sometimes confuses path canonicalisation. If the build fails with linker errors mentioning `\\?\` prefixes, that's the known issue; document in PHASE-VERIFICATION but it should resolve on retry.
4. **`bundle.windows.wix` upgradeCode auto-gen** — Tauri 2.11 auto-gens an UpgradeCode from the identifier each build. For Phase 1 we accept this (per "Constraints" above). Phase 2 will lock it.

## Verification plan

1. `cargo install cargo-xwin` succeeds.
2. `rustup target add x86_64-pc-windows-msvc` succeeds.
3. Edit `src-tauri/tauri.conf.json` (small additive change to `bundle.targets` + new `bundle.windows.wix` block).
4. `cargo tauri build --target x86_64-pc-windows-msvc` succeeds (allow 30 min for cold compile).
5. `ls src-tauri/target/x86_64-pc-windows-msvc/release/bundle/msi/*.msi` finds the file.
6. `shasum -a 256 <msi>` recorded in PHASE-VERIFICATION.md.
7. `file <msi>` reports "MSI Installer".
8. The file size is between 15 and 40 MB.

A Windows VM smoke-test is a Phase 2 / 3 concern; Phase 1 only proves the build pipeline produces a structurally valid MSI artefact.

## Out of scope for this phase

- Code signing (Phase 2)
- macOS .app/.dmg (Phase 2)
- Tauri auto-updater wiring (Phase 3)
- GitHub Actions release workflow (Phase 3)
- Live Windows VM smoke-test (Phase 2 or post-Phase-3 when signing exists)
