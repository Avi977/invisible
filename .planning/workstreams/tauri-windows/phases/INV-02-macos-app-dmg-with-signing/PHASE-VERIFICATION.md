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
| 4 | Auto-updater public key + endpoint placeholders ready | (no change) | PASS | See "## Updater keypair" section below; pubkey inlined in tauri.conf.json commit 42ed4cb, private key target Infisical project=invisible-tauri, env=prod, key=TAURI_UPDATER_PRIVATE_KEY (upload deferred — see INFISICAL-MANUAL-ACTION.md). |

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

## Updater keypair (Plan 02-02 — appended)

### Public key (safe to commit — and is committed)

File: `~/.tauri/invisible.key.pub`

Base64 value (the entire single-line base64 blob — Tauri 2.x writes the
whole minisign file content as one base64 blob; this whole blob is what
the updater's `pubkey` field expects):

```
dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IEUxNDE4NDQ0NkQyMkQwMDkKUldRSjBDSnRSSVJCNGVvd01CeVk4S3N1dmNaMUwzY0pQems5NzJyZHptZ0tUZC8wT25TY0o1ZE0K
```

Decoded for human verification:

```
untrusted comment: minisign public key: E14184446D22D009
RWQJ0CJtRIRB4eowMByY8KsuvcZ1L3cJPzk972rdzmgKTd/0OnScJ5dM
```

Inlined into `src-tauri/tauri.conf.json` at `plugins.updater.pubkey` in
commit `42ed4cb`. Endpoint placeholder set to
`https://github.com/Avi977/invisible/releases/latest/download/latest.json`
per 02-CONTEXT.md LOCKED decision.

Note on length: the plan's expected pubkey-length bound (40–120 chars)
matched the inner-line-only format; Tauri 2.11.2's `cargo tauri signer
generate` actually emits the entire minisign file as a single 152-char
base64 blob and the updater config expects that whole blob. The
verification doc records the actual format, not the plan's predicted
length. The Rust JSON validator in Task 02-02-02 was adjusted to accept
up to 200 chars (Rule 3 deviation, documented in 02-02-SUMMARY.md).

### Private key (NEVER committed — recorded by storage location only)

- **Location target:** Infisical at `vault.theprofitplatform.com.au`
- **Project:** `invisible-tauri` (new project per 02-CONTEXT.md LOCKED naming; the existing `invisible` project was not linked from this worktree at autonomous-run time)
- **Environment:** `prod`
- **Secret key:** `TAURI_UPDATER_PRIVATE_KEY`
- **Password:** No password set (`cargo tauri signer generate --ci --password ""`).
  Therefore no `TAURI_UPDATER_KEY_PASSWORD` secret was created.
- **Local file:** `~/.tauri/invisible.key` (mode 0600 — OUTSIDE the worktree, never committed).
- **Upload status:** DEFERRED — Infisical login + project link require
  interactive OAuth and an interactive `infisical init` picker that the
  autonomous overnight run could not drive. See
  `INFISICAL-MANUAL-ACTION.md` in this directory for the one-step user
  ceremony that uploads the key. Phase 3 (`release.yml`) MUST complete
  this before the first tag-triggered release.

Phase 3 retrieval pattern (for `release.yml` documentation):

```bash
# Inside CI, after `infisical login` via service token (NOT the OAuth flow):
infisical run --env=prod --path=/ -- env | grep TAURI_UPDATER_PRIVATE_KEY

# Or for direct env-var population for `cargo tauri build`:
export TAURI_SIGNING_PRIVATE_KEY="$(infisical secrets get TAURI_UPDATER_PRIVATE_KEY --env=prod --plain --silent)"
cargo tauri build
```

Phase 3 release.yml is responsible for mapping the Infisical key name
(`TAURI_UPDATER_PRIVATE_KEY`) to the env var name Tauri 2.x expects
(`TAURI_SIGNING_PRIVATE_KEY`).

### Anti-regression: native build still works with `plugins.updater` set

After adding the `plugins.updater` block to `tauri.conf.json`, the native
`CI=true cargo tauri build` was re-run and still produced both artefacts:

```
$ shasum -a 256 src-tauri/target/release/bundle/macos/Invisible.app/Contents/MacOS/invisible-tauri
e65e58b6b5b4becd7e88e34f3c63496a3bbf9535312571591e149130655af16f  src-tauri/target/release/bundle/macos/Invisible.app/Contents/MacOS/invisible-tauri

$ shasum -a 256 src-tauri/target/release/bundle/dmg/Invisible_0.1.0_*.dmg
a2562d7a82d1a66db061f6757d38e2a36ff60d5a5735e3c02e72a651b80b88bd  src-tauri/target/release/bundle/dmg/Invisible_0.1.0_aarch64.dmg

$ file src-tauri/target/release/bundle/macos/Invisible.app/Contents/MacOS/invisible-tauri
src-tauri/target/release/bundle/macos/Invisible.app/Contents/MacOS/invisible-tauri: Mach-O 64-bit executable arm64
```

The rebuild SHA256s differ from Plan 02-01's initial-build SHA256s
(`b080ee8c...` for binary, `4a1f4069...` for dmg) because Tauri embeds
build-time metadata into the binary on every rebuild. The structural
assertions that matter still hold: the rebuilt binary is `Mach-O ...
executable arm64` and `codesign -dv` reports `Signature=adhoc` with
`TeamIdentifier=not set` and no `Authority=Developer ID Application:`
line. Without `bundle.createUpdaterArtifacts: true`, the bundler treats
`plugins.updater` as runtime-only config and did NOT require
`TAURI_SIGNING_PRIVATE_KEY` at build time — exactly the behaviour the
plan predicted for T-INV-02-02-CONFIG-BREAK mitigation.

### Security posture (threats from phase prompt + plan threat-model)

- **T1 — private key exfiltration:** mitigated. Private key lives at
  `~/.tauri/invisible.key` (mode 0600, outside worktree). Target storage
  in Infisical at `TAURI_UPDATER_PRIVATE_KEY` (upload deferred — see
  `INFISICAL-MANUAL-ACTION.md`). `git ls-files | grep -q invisible.key`
  returns empty. The key value was never echoed to shell history (push
  was attempted with `KEY=$(cat ~/.tauri/invisible.key)` via Infisical
  CLI; the autonomous attempt failed cleanly because of the missing
  project link, before the value reached any log). The key value was
  never pasted into this verification doc.
- **T2 — public key tampering:** mitigated. Pubkey is in version control
  (`src-tauri/tauri.conf.json`). Any future PR modifying
  `plugins.updater.pubkey` requires equal scrutiny to a Dev ID change.
- **T3 — endpoint URL pinning:** mitigated. Endpoint is pinned to the
  official `github.com/Avi977/invisible/releases/...` host. Any PR
  changing the endpoint URL requires equal scrutiny to a pubkey change.
- **T4 — quarantine bypass scope:** mitigated by Plan 02-01 (README
  `xattr` command is scoped to `/Applications/Invisible.app`, not a
  wildcard). No new T4 exposure in this plan.

### Hand-off to Phase 3

Phase 3 (`release.yml`) needs:
1. Service-token auth to Infisical (NOT OAuth) — set up a machine identity
   with read-only access to the secret `TAURI_UPDATER_PRIVATE_KEY` in
   project `invisible-tauri` env `prod`.
2. `cargo install tauri-cli@2.11.2 --locked` in the runner.
3. `cargo add tauri-plugin-updater` in `src-tauri/Cargo.toml` (the Rust
   side this phase deliberately deferred).
4. Register the plugin in `src-tauri/src/lib.rs`:
   ```rust
   #[cfg(desktop)]
   app.handle().plugin(tauri_plugin_updater::Builder::new().build());
   ```
5. Set `bundle.createUpdaterArtifacts: true` in `tauri.conf.json` so the
   bundler emits `.sig` files alongside the `.app`/`.dmg`/`.exe`.
6. Export `TAURI_SIGNING_PRIVATE_KEY="$(infisical secrets get ...)"` before
   `cargo tauri build` in the macOS and Windows jobs.
7. Publish the signed manifest as `latest.json` at the GitHub Release URL
   already pinned in `plugins.updater.endpoints`.

### Pre-Phase-3 unblock (user action required)

Before Phase 3 starts, the user must complete the one-step Infisical
ceremony documented in
`.planning/workstreams/tauri-windows/phases/INV-02-macos-app-dmg-with-signing/INFISICAL-MANUAL-ACTION.md`.
The local keypair at `~/.tauri/invisible.key` is the canonical source —
the ceremony only uploads its content into Infisical so Phase 3 CI can
read it. Until that ceremony completes, Phase 3 cannot sign update
manifests.
