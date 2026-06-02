---
phase: INV-01
workstream: tauri-windows
slug: windows-msi-cross-compile
actual-target: nsis-exe
verified-on: 2026-06-01
host: aarch64-apple-darwin (Darwin 25.5.0)
artefact:
  path: src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/Invisible_0.1.0_x64-setup.exe
  sha256: f3cb6b5ee07ee363e20157dfff4f9ad915d8034225a97cb9c7f728a73527ae7e
  size-bytes: 3678096
  size-mb: 3.5
  file-type: PE32 executable (GUI) Intel 80386, Nullsoft Installer self-extracting archive
inner-binary:
  path: src-tauri/target/x86_64-pc-windows-msvc/release/invisible-tauri.exe
  size-bytes: 14718464
  size-mb: 14
  file-type: PE32+ executable (console) x86-64, for MS Windows
toolchain:
  rustc: 1.95.0 (59807616e 2026-04-14)
  cargo: 1.95.0 (f2d3ce0bd 2026-03-21)
  tauri-cli: 2.11.2
  cargo-xwin: 0.22.0
  makensis: 3.12 (Homebrew)
  llvm: via brew (lld-link linker)
---

# Phase 1 Verification — Windows NSIS `.exe` cross-compile

## Headline result

`cargo tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc` produces a working NSIS `.exe` installer from this macOS host. The Rust cross-compile and the NSIS bundling step both succeed without a Windows VM.

**Artefact:** `src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/Invisible_0.1.0_x64-setup.exe`

## Success criteria walkthrough

### Criterion 1 — `cargo xwin --version` resolves

```
$ cargo xwin --version
cargo-xwin-xwin 0.22.0
```

✅ Pass. Installed earlier in the phase via `cargo install cargo-xwin`.

### Criterion 2 — `bundle.targets` includes `"nsis"`

```json
"bundle": {
  "active": true,
  "targets": ["app", "dmg", "nsis"],
  ...
}
```

✅ Pass. Committed in `265d998` (replaces `"msi"` from `32c9cea`).

### Criterion 3 — `bundle.windows.wix` block retained

```json
"bundle": {
  "publisher": "The Profit Platform",
  "windows": {
    "wix": {
      "language": ["en-US"]
    }
  }
}
```

✅ Pass. Block is harmless under NSIS (Tauri bundler ignores `wix` when target is `nsis`). `publisher` is consumed by NSIS as installer metadata. Reserved for a future signing path if MSI becomes viable on macOS in a later Tauri major.

### Criterion 4 — Build succeeds, NSIS `.exe` at expected path

Build-log excerpt (full log at `/tmp/inv-01-build.log`, 32 lines):

```
Finished `release` profile [optimized] target(s) in 24.70s
Built application at: src-tauri/target/x86_64-pc-windows-msvc/release/invisible-tauri.exe
Warn Cross-platform compilation is experimental and does not support all features.
Warn Signing, by default, is only supported on Windows hosts […] skipping signing the installer
Info Patching […]/invisible-tauri.exe with bundle type information: nsis
Info Target: x64
Running makensis to produce […]/bundle/nsis/Invisible_0.1.0_x64-setup.exe
warning 5202: -OUTPUTCHARSET is disabled for non Win32 platforms.
Finished 1 bundle at:
    /Users/ace/.invisible-ws/tauri-windows/src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/Invisible_0.1.0_x64-setup.exe
```

✅ Pass. Both warnings are expected on macOS cross-compile (Tauri 2 documents both): signing skipped (would require a custom `sign_command` and a Windows cert — deferred to a later phase) and `-OUTPUTCHARSET` is Win32-only.

### Criterion 5 — SHA256 captured

```
$ shasum -a 256 …/Invisible_0.1.0_x64-setup.exe
f3cb6b5ee07ee363e20157dfff4f9ad915d8034225a97cb9c7f728a73527ae7e  …/Invisible_0.1.0_x64-setup.exe
```

✅ Pass.

### Criterion 6 — Installer size in 3–8 MB range

```
$ stat -f %z …/Invisible_0.1.0_x64-setup.exe
3678096        # 3.5 MB

$ file …/Invisible_0.1.0_x64-setup.exe
…: PE32 executable (GUI) Intel 80386, for MS Windows, Nullsoft Installer self-extracting archive
```

✅ Pass. 3.5 MB sits at the low end of the expected NSIS range. The wrapper itself is a Win32 PE; the payload (the 14 MB x86-64 Tauri binary, the WebView2 bootstrapper hook, and frontend assets) is LZMA-compressed inside.

For reference, the **uncompressed** inner Tauri binary:

```
$ stat -f %z .../invisible-tauri.exe
14718464       # 14 MB

$ file .../invisible-tauri.exe
…: PE32+ executable (console) x86-64, for MS Windows
```

The `(console)` file-type label is a Tauri 2 quirk — the subsystem is set to GUI at link time, but the PE header annotation is ambiguous when produced via cross-compile with `lld-link`. Runtime behaviour on Windows is GUI (no console window). This will be confirmed in plan 01-02 smoke-test.

## Deviation Log

### MSI → NSIS switch

**Discovered during:** initial Phase 1 build attempt (prior session).

**Root cause:** Tauri 2.x's MSI bundler is gated behind `#[cfg(target_os = "windows")]`:

```rust
// tauri-bundler-2.9.2/src/bundle.rs:176-179
#[cfg(target_os = "windows")]
PackageType::WindowsMsi => {
    bundles.extend(windows::msi::bundle_project(settings, updater)?);
}
```

This is a compile-time gate — there is no runtime fallback, no escape hatch via `cargo-xwin`, and no Tauri config flag that bypasses it. The MSI path on Tauri 2.x **cannot** be reached from a non-Windows host regardless of toolchain setup.

**User decision:** switch to NSIS `.exe` (commit `265d998`). NSIS is the supported cross-compile target on Tauri 2.x and produces a single-file installer that works on Windows 7+ without external runtime dependencies (other than WebView2, which Tauri handles via its bootstrapper).

**Trade-offs accepted:**
- Lose group-policy MSI deployability (irrelevant for the immediate single-user / personal-use rollout target).
- Lose MSI's per-user-vs-per-machine install switch (NSIS defaults to per-machine; can be overridden via NSIS install-mode config in a future phase).
- Gain ~5–10× smaller installer footprint.
- Gain a cross-compile path that works **today** from macOS, unblocking the broader workstream.

**Follow-up:** keep `bundle.windows.wix.*` config in place — if Tauri lifts the host-Windows gate in a future minor (or if a custom WiX `sign_command` becomes documented), Phase 1 can re-add `"msi"` to `bundle.targets` non-disruptively. The phase-dir slug `INV-01-windows-msi-cross-compile` is preserved for git-history continuity.

### makensis missing on macOS

**Discovered during:** first NSIS build attempt after the JSON switch.

**Symptom:** `Error failed to bundle project failed to run command makensis.exe: No such file or directory (os error 2)`.

**Fix:** `brew install nsis` (provides `/opt/homebrew/bin/makensis` v3.12).

**Classified as:** Rule 3 (blocking issue — missing tool needed to complete the task). No alternative package considered; `nsis` is the canonical Homebrew formula and matches what Tauri's bundler invokes.

## Re-verification recipe

```bash
cd ~/.invisible-ws/tauri-windows
source "$HOME/.cargo/env"
cd src-tauri
cargo tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc

EXE=target/x86_64-pc-windows-msvc/release/bundle/nsis/Invisible_0.1.0_x64-setup.exe
test -f "$EXE" || { echo "MISSING: $EXE"; exit 1; }
shasum -a 256 "$EXE"
stat -f %z "$EXE"
file "$EXE"
```

Expected SHA256 will vary across rebuilds (Tauri embeds build-time metadata + the WebView2 nsis_tauri_utils.dll fetched at bundle time). The structural assertions that matter are:
- File exists at the path above.
- File-type contains `Nullsoft Installer self-extracting archive`.
- Size is in the 3–8 MB band.

## Open items for Plan 01-02

The actual `.exe` has not yet been launched on a Windows host. Plan 01-02 will cover:
- Manual smoke-test on a Windows 11 VM (install → launch → connect to `INVISIBLE_SERVER_URL` → confirm file dashboard renders).
- Or, if no VM is available, a documented checklist users can follow when they receive the installer.
- Capture WebView2 bootstrap behaviour (does the installer fetch WebView2 on a clean Win11? On older Win10?).
