---
phase: INV-03-release-workflow-auto-updater
plan: 01
status: complete
date: 2026-06-02
---

# Plan 03-01 Summary: release.yml + auto-updater

## What shipped

- **`.github/workflows/release.yml`** (95 lines): Tag-triggered (`v*`) release pipeline. Matrix of macos-latest (aarch64) + windows-latest (native). Uses `tauri-apps/tauri-action@v0` to build, package, sign, and upload to a DRAFT GitHub Release. Generates `latest.json` automatically because `bundle.createUpdaterArtifacts: true` is now set.
- **`src-tauri/tauri.conf.json`**: added `bundle.createUpdaterArtifacts: true` (one key). All Phase 2 scope fences re-verified.
- **`.gitignore`**: fixed a latent bug — bare `workflows/` was unintentionally matching `.github/workflows/` (intended only for the daemon's per-machine `<repo>/workflows/` state). Anchored to `/workflows/` so the release workflow file can actually be committed.
- **PHASE-VERIFICATION.md**: ship verdict + 5-step user run-book for the first release.
- **ROADMAP.md**: Phase 3 plan list updated with link + reinterpretation note.

## Build evidence (no regression)

`cargo tauri build` after the JSON edit produced:

| Artefact | SHA256 | Size |
|----------|--------|------|
| `Invisible.app/Contents/MacOS/invisible-tauri` (Mach-O arm64) | `e65e58b6b5b4becd7e88e34f3c63496a3bbf9535312571591e149130655af16f` | 13.5 MB |
| `Invisible_0.1.0_aarch64.dmg` | `dfd64856c133113ee546e900166ff1ede3ea6d3f7e5a3283e0e887c4295c91b9` | 5.40 MB |
| `Invisible.app.tar.gz` (updater bundle, NEW) | `b43814b190913c7fafdcd8189d7dbd10b246cf8b78c53a839b21ea5a0340583c` | 5.49 MB |
| `Invisible.app.tar.gz.sig` (updater signature, NEW) | `924cdfd4684fbb5a76d536678fa236929de18ac9f4d051ca330d5a8b7fc6bd58` | 408 B |

The binary SHA matches Plan 02-02's rebuild — the JSON edit is bundler-only, no Rust change.

## Deferred to user

1. Complete `INFISICAL-MANUAL-ACTION.md` (Plan 02-02 ceremony)
2. Copy `TAURI_UPDATER_PRIVATE_KEY` from Infisical to GHA secrets as `TAURI_SIGNING_PRIVATE_KEY`
3. Tag `v0.1.0-rc1` and push → CI runs → DRAFT release appears with all artefacts

Full run-book in `PHASE-VERIFICATION.md` "User verification recipe" section.

## Commit

`67061a7` — `feat(INV-03): release.yml + auto-updater (bundle.createUpdaterArtifacts)`

## ## EXECUTION COMPLETE
