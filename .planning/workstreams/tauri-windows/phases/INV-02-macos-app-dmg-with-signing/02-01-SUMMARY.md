---
phase: INV-02-macos-app-dmg-with-signing
plan: 01
type: execute
wave: 1
verified-on: 2026-06-02
host: Darwin 25.5.0 arm64
status: complete
commits:
  - sha: 38feb03
    message: "docs(tauri-windows): add macOS Gatekeeper unblock section to README"
    files: [README.md]
  - sha: 039dc65
    message: "docs(INV-02): seed PHASE-VERIFICATION — unsigned .app/.dmg build"
    files: [".planning/workstreams/tauri-windows/phases/INV-02-macos-app-dmg-with-signing/PHASE-VERIFICATION.md"]
artefacts:
  app:
    path: src-tauri/target/release/bundle/macos/Invisible.app
    binary-sha256: b080ee8cdbfb8e11437e2e01429d2c5de336adaaf3d06c0ea8815268a0679d29
    binary-size-bytes: 14921712
    binary-size-mb: 14.23
    binary-file-type: Mach-O 64-bit executable arm64
  dmg:
    path: src-tauri/target/release/bundle/dmg/Invisible_0.1.0_aarch64.dmg
    sha256: 4a1f4069f20e2fd373d0770c739d820d9456efbfa48caa70e0721f55e4387a86
    size-bytes: 5667333
    size-mb: 5.40
    arch-suffix: aarch64
codesign-status: adhoc (Signature=adhoc, flags=0x20002(adhoc,linker-signed)) — NOT a Developer ID signature
deviations:
  - rule: 3
    type: blocking issue (auto-fix)
    description: "bundle_dmg.sh AppleScript-to-Finder timeout (-1712) on first cargo tauri build; resolved by re-running with CI=true so Tauri-bundler passes --skip-jenkins to bundle_dmg.sh, skipping the cosmetic Finder window-layout step. No tauri.conf.json change."
requirements-completed:
  - INV-02-SC2
  - INV-02-SC3-REINTERPRETED
hand-off:
  next-plan: 02-02-PLAN.md
  next-action: "Append 'Updater keypair' section to PHASE-VERIFICATION.md; add plugins.updater block (pubkey + endpoint placeholder) to src-tauri/tauri.conf.json; store private key in Infisical."
---

# Phase 2 Plan 01 Summary — Native macOS .app + .dmg verified, README Gatekeeper workaround landed

## One-liner

Verified the native `cargo tauri build` pipeline still produces a working
`.app` + `.dmg` on this Apple Silicon host after Phase 1's cargo-xwin
NSIS-cross-compile machinery landed, documented the Gatekeeper unblock
workflow in `README.md` (per 02-CONTEXT.md LOCKED ship-unsigned decision),
and seeded `PHASE-VERIFICATION.md` with the build evidence (SHA256, size,
`file` output, `codesign -dv` proof of no Dev ID).

## Tasks

| # | Task | Outcome |
|---|------|---------|
| 01 | Native macOS build + artefact capture | PASS — `.app` and `.dmg` produced at expected paths; binary is `Mach-O 64-bit executable arm64`; codesign reports `Signature=adhoc` with no Developer ID authority. No commit (artefacts are gitignored). |
| 02 | Add `## Installation (macOS)` to README.md | PASS — section inserted between `### Tauri shell` and `## Architecture`; both Path A (right-click -> Open) and Path B (`xattr -dr com.apple.quarantine /Applications/Invisible.app`) documented; xattr scoped (no wildcards / no `~`); user-warning sentence present. Commit `38feb03`. |
| 03 | Seed PHASE-VERIFICATION.md | PASS — all `{...}` placeholders replaced; rows 1-3 of criteria table non-PENDING; row 4 explicitly `PENDING — PLAN 02-02`; YAML frontmatter has full app + dmg + codesign + toolchain metadata. Commit `039dc65`. |

## Commits

```
039dc65 docs(INV-02): seed PHASE-VERIFICATION — unsigned .app/.dmg build
38feb03 docs(tauri-windows): add macOS Gatekeeper unblock section to README
```

Branch: `ws/tauri-windows`. Two atomic commits, one file each, both
Conventional Commits.

## Build artefacts (gitignored — recorded by SHA256 only)

| Artefact | Path | Size | SHA256 |
|----------|------|------|--------|
| `.app` inner binary | `src-tauri/target/release/bundle/macos/Invisible.app/Contents/MacOS/invisible-tauri` | 14.23 MB | `b080ee8cdbfb8e11437e2e01429d2c5de336adaaf3d06c0ea8815268a0679d29` |
| `.dmg` | `src-tauri/target/release/bundle/dmg/Invisible_0.1.0_aarch64.dmg` | 5.40 MB | `4a1f4069f20e2fd373d0770c739d820d9456efbfa48caa70e0721f55e4387a86` |

Arch suffix `aarch64` confirms Apple Silicon native build (cargo emits
`Mach-O 64-bit executable arm64` for the binary itself; the DMG filename
uses Tauri's `TAURI_ENV_ARCH` triple component, which is `aarch64`).

## Codesign status (unsigned proof)

```
$ codesign -dv src-tauri/target/release/bundle/macos/Invisible.app
...
CodeDirectory v=20400 size=115816 flags=0x20002(adhoc,linker-signed) hashes=3615+0 location=embedded
Signature=adhoc
TeamIdentifier=not set
```

`Signature=adhoc` + `flags=0x20002(adhoc,linker-signed)` is Tauri 2.x's
linker ad-hoc signature (required for Apple Silicon to even load the
Mach-O — it is **not** a code-signing trust signal). No
`Authority=Developer ID Application:` line appears anywhere in the
output, confirming the 02-CONTEXT.md "ship unsigned, no Apple Dev ID"
LOCKED decision held.

## Deviations

### Rule 3 (auto-fix blocking issue) — bundle_dmg.sh AppleScript timeout

**Discovered during:** Task 02-01-01, first `cargo tauri build` attempt.

**Issue:** Tauri's vendored `create-dmg` fork (`bundle_dmg.sh`)
successfully created the read-write scratch disk image and copied the
`.app` + Applications symlink into it, then attempted to run an
AppleScript that talks to Finder to set icon positions inside the DMG
window. The AppleScript hung waiting for Finder to respond and timed
out with:

```
osascript: execution error: Finder got an error: AppleEvent timed out. (-1712)
Failed running AppleScript
```

This is a well-known `create-dmg` failure mode in non-interactive shells
where the parent process has not been granted macOS Automation
permission for Finder. Tauri's bundler swallows the script's stdout/stderr
through `output_ok()` → `.context(...)` → returning only a generic
"failed to run bundle_dmg.sh" message. The real error surfaces only with
`cargo tauri build --verbose`.

**Fix:** `bundle_dmg.sh` supports `--skip-jenkins`, which bypasses the
cosmetic Finder window-layout AppleScript entirely. Tauri's bundler
passes this flag automatically when `CI=true` is set in the environment
(`tauri-bundler-2.9.2/src/bundle/macos/dmg/mod.rs:174-180`). Re-ran with
`CI=true cargo tauri build`. Result: identical `.app`, identical inner
Mach-O binary, valid UDZO `.dmg` of 5.40 MB. The only behavioural
difference is that the mounted DMG opens with default Finder layout
instead of a custom-positioned one — purely cosmetic, invisible to any
user who follows README Path A (drag `Invisible.app` to `/Applications`
without opening the DMG window in Finder first).

**Files changed by deviation:** none — `tauri.conf.json` was NOT
modified (Plan 02-02 owns that file). The deviation is documented in
`PHASE-VERIFICATION.md` "Build-environment note" section and the
re-verification recipe records the required `CI=true` env var for
local re-runs. GitHub Actions sets `CI=true` automatically, so this
costs Phase 3 (CI workflow) nothing.

## Verification gates (all PASS)

| Gate | Result |
|------|--------|
| `.app` directory + inner binary exist | PASS |
| `file <binary>` reports `Mach-O ... executable` | PASS |
| `.dmg` exists matching `Invisible_0.1.0_*.dmg` glob | PASS |
| `codesign -dv` does NOT report `Authority=Developer ID Application:` | PASS |
| `/tmp/inv-02-01-facts.txt` non-empty | PASS |
| `README.md` has `## Installation (macOS)` between `## What it does` and `## Architecture` | PASS |
| `xattr -dr com.apple.quarantine` scoped to `/Applications/Invisible.app` (no wildcard, no `~`) | PASS |
| "apps you downloaded yourself" warning sentence present | PASS |
| README code fences balanced (count is even) | PASS |
| `PHASE-VERIFICATION.md` has no `{...}` placeholders | PASS |
| `PHASE-VERIFICATION.md` rows 1-3 of criteria table are non-PENDING; row 4 is `PENDING — PLAN 02-02` | PASS |
| At least one 64-hex-char SHA256 string in `PHASE-VERIFICATION.md` | PASS |
| Both commits on `ws/tauri-windows` use Conventional Commit prefixes | PASS |

## Requirements satisfied

- **INV-02-SC2** — `cargo tauri build` (no `--target`) produces `.app` and `.dmg` on this macOS host. PHASE-VERIFICATION.md records both artefacts with SHA256.
- **INV-02-SC3-REINTERPRETED** — Ship-unsigned with documented README workaround. `codesign -dv` proves no Dev ID Application authority; README documents both unblock paths.

## Hand-off to Plan 02-02

Plan 02-02 generates the Tauri auto-updater keypair (`tauri signer generate`),
stores the private key in Infisical (project: `invisible-tauri` or reuse
`invisible`; env `prod`; key `TAURI_UPDATER_PRIVATE_KEY`), and adds the
`plugins.updater` block to `src-tauri/tauri.conf.json` with:

- `pubkey`: inline public key value (safe to commit)
- `endpoints`: `["https://github.com/Avi977/invisible/releases/latest/download/latest.json"]` (placeholder; Phase 3 produces the real `latest.json`)

After that plan completes, the appended "Updater keypair" section in
`PHASE-VERIFICATION.md` should also include a fresh `cargo tauri build`
run-log line proving the new config did not break the native macOS build
path that this plan verified — i.e., the DMG SHA will change (Tauri
embeds new metadata), but `file <binary>` must still report `Mach-O 64-bit
executable arm64` and `codesign -dv` must still report no Developer ID
authority. The PHASE-VERIFICATION.md structure (frontmatter + headline +
ROADMAP table + native-build proof + build-log excerpt + re-verification
recipe + hand-off) is intentionally additive so Plan 02-02 can append a
new section without touching the existing ones.

## Self-Check

`README.md` exists, contains `## Installation (macOS)`, both paths,
correctly-scoped xattr, warning sentence, balanced code fences.

`PHASE-VERIFICATION.md` exists at the expected path, contains no
`{...}` placeholders, has Mach-O proof, has the SHA256 of both artefacts,
rows 1-3 of the criteria table are non-PENDING, row 4 says
PENDING — PLAN 02-02.

Commits `38feb03` and `039dc65` are reachable from `HEAD` on branch
`ws/tauri-windows`.

`.app` and `.dmg` exist locally at the expected build-output paths
(verified via `test -d`/`test -f`; gitignored so they do not appear in
`git status`).

## Self-Check: PASSED
