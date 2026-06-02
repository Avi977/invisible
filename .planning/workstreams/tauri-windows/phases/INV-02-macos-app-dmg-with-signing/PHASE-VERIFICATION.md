---
phase: INV-02
workstream: tauri-windows
slug: macos-app-dmg-with-signing
actual-target: unsigned-app-dmg
verified-on: 2026-06-02
host: Darwin 25.5.0 arm64
signing-decision: ship-unsigned-no-apple-dev-id
signing-decision-source: .planning/workstreams/tauri-windows/phases/INV-02-macos-app-dmg-with-signing/02-CONTEXT.md
app:
  path: src-tauri/target/release/bundle/macos/Invisible.app
  binary-path: src-tauri/target/release/bundle/macos/Invisible.app/Contents/MacOS/invisible-tauri
  binary-sha256: b080ee8cdbfb8e11437e2e01429d2c5de336adaaf3d06c0ea8815268a0679d29
  binary-size-bytes: 14921712
  binary-file-type: invisible-tauri Mach-O 64-bit executable arm64
dmg:
  path: src-tauri/target/release/bundle/dmg/Invisible_0.1.0_aarch64.dmg
  sha256: 4a1f4069f20e2fd373d0770c739d820d9456efbfa48caa70e0721f55e4387a86
  size-bytes: 5667333
  size-mb: 5.40
  file-type: Invisible_0.1.0_aarch64.dmg zlib compressed data
codesign-status: adhoc (Signature=adhoc — Tauri linker ad-hoc, NOT a Dev ID signature)
codesign-raw: |
  Executable=/Users/ace/.invisible-ws/tauri-windows/src-tauri/target/release/bundle/macos/Invisible.app/Contents/MacOS/invisible-tauri
  Identifier=invisible_tauri-3fce7c9397b3d032
  Format=app bundle with Mach-O thin (arm64)
  CodeDirectory v=20400 size=115816 flags=0x20002(adhoc,linker-signed) hashes=3615+0 location=embedded
  Signature=adhoc
  Info.plist=not bound
  TeamIdentifier=not set
  Sealed Resources=none
  Internal requirements=none
toolchain:
  rustc: rustc 1.95.0 (59807616e 2026-04-14)
  cargo: cargo 1.95.0 (f2d3ce0bd 2026-03-21)
  tauri-cli: tauri-cli 2.11.2
---

# Phase 2 Verification — Native macOS .app + .dmg (UNSIGNED)

## Headline result

`cargo tauri build` (no `--target` flag) produces a native macOS `.app`
and `.dmg` from this host. The build is **unsigned** by design — see
`02-CONTEXT.md` for the LOCKED decision to ship without an Apple
Developer ID. Users unblock Gatekeeper via the workaround documented
in the new `## Installation (macOS)` section of the root `README.md`.

Plan 02-02 (next) adds the Tauri auto-updater public key + endpoint
placeholder to `tauri.conf.json`. That plan APPENDS its own section to
this file rather than overwriting; do not delete or restructure the
sections below.

## ROADMAP success criteria walkthrough (reinterpreted per 02-CONTEXT.md)

| # | Criterion (original) | Reinterpretation (per CONTEXT) | Status | Evidence |
|---|----------------------|--------------------------------|--------|----------|
| 1 | Developer ID Application certificate documented | DEFERRED — ship unsigned, README workaround documents the user-facing impact | DEFERRED-AS-LOCKED | `02-CONTEXT.md` "Apple Developer Program / Signing" LOCKED block; README `## Installation (macOS)` section (commit `38feb03` from Task 02-01-02) |
| 2 | `cargo tauri build` (no target) produces `.app` and `.dmg` | (no change) | PASS | This task. `.app` and `.dmg` SHA256s + sizes recorded above in YAML frontmatter. |
| 3 | `codesign --verify --verbose` returns 0; `spctl -a -t exec` reports accepted | DEFERRED — verify unsigned status instead | PASS-AS-REINTERPRETED | `codesign-status` field above proves no Dev ID Application authority is attached. |
| 4 | Auto-updater public key + endpoint placeholders ready | (no change — handled in Plan 02-02) | PENDING — PLAN 02-02 | Plan 02-02 appends an "Updater keypair" section to this file. |

## Native-build proof (anti-regression vs Phase 1)

Phase 1 added cargo-xwin machinery (`bundle.targets` includes `"nsis"`,
`bundle.windows.wix` block, brew `nsis`, cargo `xwin` toolchain). This
task proves none of those changes broke the native macOS build path.

### `.app` inner Mach-O binary

```
$ file src-tauri/target/release/bundle/macos/Invisible.app/Contents/MacOS/invisible-tauri
invisible-tauri: Mach-O 64-bit executable arm64
```

The output contains `Mach-O ... executable` — that is the native-build
proof. A cross-compile artefact would say `PE32` (Windows) or `ELF`
(Linux), not `Mach-O`. The arch field `arm64` matches this host
(`uname -m` reports `arm64`; Tauri writes `aarch64` in the DMG filename
because that is the `TAURI_ENV_ARCH` triple component) — proving the
build did NOT pick up Phase 1's `x86_64-pc-windows-msvc` target.

### Codesign status (unsigned proof, per 02-CONTEXT.md LOCKED decision)

```
$ codesign -dv src-tauri/target/release/bundle/macos/Invisible.app
Executable=/Users/ace/.invisible-ws/tauri-windows/src-tauri/target/release/bundle/macos/Invisible.app/Contents/MacOS/invisible-tauri
Identifier=invisible_tauri-3fce7c9397b3d032
Format=app bundle with Mach-O thin (arm64)
CodeDirectory v=20400 size=115816 flags=0x20002(adhoc,linker-signed) hashes=3615+0 location=embedded
Signature=adhoc
Info.plist=not bound
TeamIdentifier=not set
Sealed Resources=none
Internal requirements=none
```

`Signature=adhoc` + `flags=0x20002(adhoc,linker-signed)` is Tauri 2.x's
**linker ad-hoc signature** — the Rust linker stamps an ad-hoc signature
so macOS's loader will execute the binary at all on Apple Silicon. It is
NOT a Dev ID signature and grants NO Gatekeeper trust. `TeamIdentifier=not set`
and the absence of `Authority=Developer ID Application:` in the output are
the explicit proofs that the LOCKED ship-unsigned decision held.

The output MUST NOT contain `Authority=Developer ID Application:`. If
it does, an Apple Developer ID slipped into the build environment and
the LOCKED decision was violated — re-run after `xcrun simctl spawn ...`
etc. is cleaned up. Current output above is the proof that no Dev ID
was attached.

## Build-log excerpt

```
   Compiling invisible-tauri v0.1.0 (/Users/ace/.invisible-ws/tauri-windows/src-tauri)
    Finished `release` profile [optimized] target(s) in 23.60s
       Built application at: /Users/ace/.invisible-ws/tauri-windows/src-tauri/target/release/invisible-tauri
    Bundling Invisible.app (/Users/ace/.invisible-ws/tauri-windows/src-tauri/target/release/bundle/macos/Invisible.app)
    Bundling Invisible_0.1.0_aarch64.dmg (/Users/ace/.invisible-ws/tauri-windows/src-tauri/target/release/bundle/dmg/Invisible_0.1.0_aarch64.dmg)
     Running bundle_dmg.sh
    Finished 2 bundles at:
        /Users/ace/.invisible-ws/tauri-windows/src-tauri/target/release/bundle/macos/Invisible.app
        /Users/ace/.invisible-ws/tauri-windows/src-tauri/target/release/bundle/dmg/Invisible_0.1.0_aarch64.dmg
```

## Build-environment note (deviation Rule 3 — auto-fix)

The first `cargo tauri build` invocation succeeded through Rust
compilation and `.app` bundling, but the DMG bundling step
(`bundle_dmg.sh`, Tauri's vendored `create-dmg` fork) failed with:

```
osascript: execution error: Finder got an error: AppleEvent timed out. (-1712)
Failed running AppleScript
```

This is the well-documented `create-dmg` AppleScript-to-Finder timeout
that occurs in non-interactive / headless shell sessions where the
parent process has not been granted Automation permission for Finder.
The cosmetic AppleScript step only sets icon positions inside the DMG
window — it is not load-bearing for the artefact's correctness.

`bundle_dmg.sh` already supports skipping that step via `--skip-jenkins`,
which Tauri's bundler passes only when the `CI=true` environment variable
is set (`tauri-bundler-2.9.2/src/bundle/macos/dmg/mod.rs:174-180`). The
build was re-run with `CI=true cargo tauri build`. Result: identical
`.app`, identical inner Mach-O binary, and a 5.40 MB UDZO `.dmg` whose
window opens with default Finder layout instead of a custom-positioned
one — a purely cosmetic difference invisible to a user who drags the
`.app` straight to `/Applications` per `README.md` Path A.

No `tauri.conf.json` modification was made; the deviation is scoped to
the build invocation only. Re-runs from CI (where `CI=true` is already
set by GitHub Actions) need no special flag.

## Re-verification recipe

```bash
cd ~/.invisible-ws/tauri-windows
source "$HOME/.cargo/env"
cd src-tauri
CI=true cargo tauri build   # CI=true skips the Finder-prettify AppleScript that hangs in non-interactive shells
ls -la target/release/bundle/macos/Invisible.app
ls -la target/release/bundle/dmg/Invisible_0.1.0_*.dmg
shasum -a 256 target/release/bundle/macos/Invisible.app/Contents/MacOS/invisible-tauri
shasum -a 256 target/release/bundle/dmg/Invisible_0.1.0_*.dmg
file target/release/bundle/macos/Invisible.app/Contents/MacOS/invisible-tauri
codesign -dv target/release/bundle/macos/Invisible.app 2>&1 || true
```

The SHA256s will vary across rebuilds (Tauri embeds build metadata).
The structural assertions that matter are:
- `Mach-O ... executable` in the `file` output for the inner binary.
- No `Authority=Developer ID Application:` in `codesign -dv`.
- DMG file size in the 5–25 MB range (UDZO-compressed payload).

## Hand-off to Plan 02-02

Plan 02-02 generates the Tauri auto-updater keypair and adds the
`plugins.updater` block to `src-tauri/tauri.conf.json`. After that plan
completes, the appended "Updater keypair" section in this file will
document:
- The public-key value (safe to commit) inline in `tauri.conf.json`.
- The Infisical path of the private key (NOT the key value itself).
- A re-run of `cargo tauri build` proving the new config did not break
  the native macOS build path verified in this plan.
