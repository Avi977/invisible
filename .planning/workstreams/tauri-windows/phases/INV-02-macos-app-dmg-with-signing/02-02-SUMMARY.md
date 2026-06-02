---
phase: INV-02-macos-app-dmg-with-signing
plan: 02
type: execute
wave: 2
verified-on: 2026-06-02
host: Darwin 25.5.0 arm64
status: complete-with-deferred-infisical-upload
commits:
  - sha: 42ed4cb
    message: "feat(tauri-windows): add plugins.updater block with Tauri 2.x pubkey + endpoint placeholder"
    files: ["src-tauri/tauri.conf.json"]
  - sha: f58b67c
    message: "docs(INV-02): append updater-keypair verification — pubkey inline, private key local + Infisical upload deferred"
    files:
      - ".planning/workstreams/tauri-windows/phases/INV-02-macos-app-dmg-with-signing/PHASE-VERIFICATION.md"
      - ".planning/workstreams/tauri-windows/phases/INV-02-macos-app-dmg-with-signing/INFISICAL-MANUAL-ACTION.md"
infisical:
  project: invisible-tauri
  env: prod
  secret-key: TAURI_UPDATER_PRIVATE_KEY
  upload-status: DEFERRED
  defer-reason: "Infisical login + init are interactive (browser OAuth + picker); autonomous overnight run could not drive them. INFISICAL-MANUAL-ACTION.md contains the ~30-second user ceremony."
keypair:
  pubkey-base64-blob: "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IEUxNDE4NDQ0NkQyMkQwMDkKUldRSjBDSnRSSVJCNGVvd01CeVk4S3N1dmNaMUwzY0pQems5NzJyZHptZ0tUZC8wT25TY0o1ZE0K"
  pubkey-length: 152
  pubkey-decoded-comment: "minisign public key: E14184446D22D009"
  private-key-path: "~/.tauri/invisible.key (mode 0600, OUTSIDE worktree, NEVER committed)"
  password-set: false
rebuild-artefacts:
  binary-sha256: e65e58b6b5b4becd7e88e34f3c63496a3bbf9535312571591e149130655af16f
  binary-file-type: "Mach-O 64-bit executable arm64"
  dmg-sha256: a2562d7a82d1a66db061f6757d38e2a36ff60d5a5735e3c02e72a651b80b88bd
  dmg-path: src-tauri/target/release/bundle/dmg/Invisible_0.1.0_aarch64.dmg
  codesign-status: "Signature=adhoc (Tauri linker ad-hoc, NOT a Dev ID signature) — TeamIdentifier=not set, no Authority=Developer ID Application: line"
deviations:
  - rule: 1
    type: bug (plan's expected format string mismatched actual Tauri 2.11.2 output)
    description: "Plan B6 grep used `untrusted comment: minisign encrypted secret key` to scan the worktree for private-key leakage; Tauri 2.11.2's `cargo tauri signer generate` actually emits `untrusted comment: rsign encrypted secret key` (rsign = Rust minisign reimplementation). T1 mitigation grep was adjusted to look for the actual `rsign encrypted secret key` string, which returned empty (no leak). The plan file itself still contains the literal `minisign encrypted secret key` text as documentation reference; that is harmless because it is descriptive prose, not the key file's content."
  - rule: 3
    type: blocking issue (auto-fix) — plan's expected pubkey-length bound did not match the actual Tauri 2.11.2 format
    description: "Plan step 5 JSON validation asserted `40 <= len(pubkey) <= 120`. Tauri 2.11.2's `cargo tauri signer generate -w ~/.tauri/invisible.key` writes a 152-character single-line base64-blob `.pub` file (the whole minisign key file encoded as base64 for env-var transport). The 120-char ceiling came from the plan's `interfaces` section assuming the inner base64 line only. Upper bound was adjusted to 200 chars in the validator; the actual 152-char blob is exactly what the Tauri 2.x updater config expects under `plugins.updater.pubkey`. Verified by re-running `cargo tauri build` post-edit — the bundler accepted the config without complaint."
  - rule: 3
    type: blocking issue (auto-fix) — plan's `--no-password` flag does not exist in Tauri CLI 2.11.2
    description: "Plan B3 used `cargo tauri signer generate --no-password` per its expected CLI; `--help` reports no such flag. Equivalent intent was achieved with `cargo tauri signer generate --ci --password \"\"`. `--ci` skips interactive prompts; `--password \"\"` explicitly sets an empty password. Generated keypair works correctly (verified the pubkey decoded round-trips; rebuild produced same binary structure)."
  - rule: explicit deviation authorization in executor prompt
    type: deferred (not a fix — the orchestrator explicitly authorized this fallback)
    description: "Infisical upload was DEFERRED to user action. The executor was authorized to take the fallback path when Infisical operations fail (no login, no project link). Plan 02-02 envisioned `auto` task that calls `infisical secrets set` and the verification step does an Infisical round-trip read; both required a project link this worktree did not have. Per the deviation authorization, the keypair was generated locally and the pubkey was inlined into tauri.conf.json as planned; only the Infisical push step was deferred. INFISICAL-MANUAL-ACTION.md was created in the phase directory with the one-step user ceremony. The verify automated block was substituted: instead of `infisical secrets get ... | head -1`, the substitution was a check that INFISICAL-MANUAL-ACTION.md exists in the phase directory."
requirements-completed:
  - INV-02-SC4
infisical-manual-action-marker: .planning/workstreams/tauri-windows/phases/INV-02-macos-app-dmg-with-signing/INFISICAL-MANUAL-ACTION.md
hand-off:
  next-phase: INV-03 (release.yml)
  blocker-before-phase-3: "User must complete the Infisical ceremony in INFISICAL-MANUAL-ACTION.md (~30 seconds). Phase 3 release.yml reads TAURI_UPDATER_PRIVATE_KEY from Infisical to sign update manifests; until the upload happens, Phase 3 cannot sign."
---

# Phase 2 Plan 02 Summary — Tauri updater keypair generated, pubkey inlined, Infisical upload deferred

## One-liner

Generated a Tauri 2.x auto-updater keypair via `cargo tauri signer
generate`, inlined the 152-char base64-blob public key into
`src-tauri/tauri.conf.json` under `plugins.updater.pubkey` with the
pinned `github.com/Avi977/invisible/releases/latest/download/latest.json`
endpoint placeholder, and re-ran `CI=true cargo tauri build` to prove no
regression — the rebuild produced an identical-shaped Mach-O arm64
binary + UDZO DMG with no Dev ID signature. The Infisical upload of the
private key (`TAURI_UPDATER_PRIVATE_KEY` in project `invisible-tauri`,
env `prod`) was DEFERRED to a one-step user ceremony documented in
`INFISICAL-MANUAL-ACTION.md` because Infisical login + project link
require interactive OAuth that the autonomous overnight run could not
drive.

## Tasks

| # | Task | Outcome |
|---|------|---------|
| 02-02-01 | Infisical pre-flight + Tauri keypair generation | PARTIAL — Infisical pre-flight FAILED (no project link in this worktree, login state unverifiable in CLI v0.43.84) → fell back to the explicit deviation-authorization path. Keypair generation SUCCEEDED: `~/.tauri/invisible.key` (mode 0600, 348 B), `~/.tauri/invisible.key.pub` (mode 0644, 152 B). T1 grep confirmed no private-key header in worktree. Project name `invisible-tauri` stashed in `/tmp/inv-02-02-infi-project.txt`. No commit (no worktree files changed). |
| 02-02-02 | Inline pubkey into tauri.conf.json + verify build | PASS — `plugins.updater` block added with exact endpoint URL and 152-char base64-blob pubkey. JSON validator passed all scope-fence guards (identifier, devUrl, frontendDist, wix.language, no signingIdentity, no createUpdaterArtifacts). `CI=true cargo tauri build` re-ran successfully: Mach-O arm64 binary + UDZO DMG produced, `Signature=adhoc` with no Dev ID Authority. Commit `42ed4cb`. Infisical push attempted with 30s manual timeout; failed cleanly because no project linked → INFISICAL-MANUAL-ACTION.md created instead. |
| 02-02-03 | Append Updater keypair section to PHASE-VERIFICATION.md | PASS — Criterion #4 flipped from `PENDING — PLAN 02-02` to `PASS`. New `## Updater keypair (Plan 02-02 — appended)` section recorded pubkey value (safe), Infisical target path (DEFERRED status), rebuild SHA256s, T1-T4 security posture, full 7-step Phase 3 hand-off checklist, and the pre-Phase-3 unblock note pointing at INFISICAL-MANUAL-ACTION.md. No `{ALLCAPS}` placeholders, no PENDING criteria. Commit `f58b67c`. |

## Commits

```
f58b67c docs(INV-02): append updater-keypair verification — pubkey inline, private key local + Infisical upload deferred
42ed4cb feat(tauri-windows): add plugins.updater block with Tauri 2.x pubkey + endpoint placeholder
```

Branch: `ws/tauri-windows`. Two atomic commits, both Conventional Commits.

## Pubkey (safe to share — same value committed in tauri.conf.json + PHASE-VERIFICATION.md)

```
dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IEUxNDE4NDQ0NkQyMkQwMDkKUldRSjBDSnRSSVJCNGVvd01CeVk4S3N1dmNaMUwzY0pQems5NzJyZHptZ0tUZC8wT25TY0o1ZE0K
```

Length: 152 characters (the full base64-encoded `.pub` file content — Tauri 2.x writes the whole minisign file as one base64 blob).

Decoded (for human verification — does NOT need to be in the JSON):

```
untrusted comment: minisign public key: E14184446D22D009
RWQJ0CJtRIRB4eowMByY8KsuvcZ1L3cJPzk972rdzmgKTd/0OnScJ5dM
```

## Rebuild artefacts (gitignored — recorded by SHA256 only)

| Artefact | Path | SHA256 | Changed since 02-01? |
|----------|------|--------|----------------------|
| `.app` inner binary | `src-tauri/target/release/bundle/macos/Invisible.app/Contents/MacOS/invisible-tauri` | `e65e58b6b5b4becd7e88e34f3c63496a3bbf9535312571591e149130655af16f` | YES — Tauri embeds build-time metadata; this is expected |
| `.dmg` | `src-tauri/target/release/bundle/dmg/Invisible_0.1.0_aarch64.dmg` | `a2562d7a82d1a66db061f6757d38e2a36ff60d5a5735e3c02e72a651b80b88bd` | YES — same reason |

Plan 02-01 had `b080ee8c...` (binary) and `4a1f4069...` (dmg). The
structural assertions that matter still hold: `Mach-O 64-bit executable
arm64` for the binary and no `Authority=Developer ID Application:` in
`codesign -dv`.

## T1 (private key exfiltration) confirmation

```
$ git ls-files | grep invisible.key
(empty — no match)

$ ls -la ~/.tauri/invisible.key
-rw-------@ 1 ace  staff  348 Jun  2 01:04 /Users/ace/.tauri/invisible.key

$ grep -rl "untrusted comment: rsign encrypted secret key" \
    /Users/ace/.invisible-ws/tauri-windows \
    --exclude-dir=.git --exclude-dir=target 2>/dev/null
(empty — no match)
```

Private key is mode 0600, outside the worktree, NEVER staged/committed,
NEVER pasted into PHASE-VERIFICATION.md, NEVER mentioned in commit
messages, NEVER echoed to logs.

## Deviations from plan

### Rule 1 (auto-fix bug) — plan's expected `minisign encrypted secret key` header doesn't match Tauri 2.11.2's actual `rsign encrypted secret key`

**Discovered during:** Task 02-02-01 step B6, T1 leak-grep.

**Issue:** The plan's T1 mitigation grep scanned the worktree for
`untrusted comment: minisign encrypted secret key`. Tauri 2.11.2's
`cargo tauri signer generate` actually emits `untrusted comment: rsign
encrypted secret key` (rsign is the Rust implementation of minisign;
Tauri vendored it specifically to avoid an external libsodium dep).
Running the plan's literal grep would have returned EMPTY for the WRONG
reason — it would never have found a real leak because the file's
header doesn't match.

**Fix:** Ran the grep with the actual header `untrusted comment: rsign
encrypted secret key`. Result: EMPTY (no match in worktree). T1
mitigation holds with the corrected string. The plan file itself
contains the literal `minisign encrypted secret key` string in its
documentation prose; this is fine because the plan file is not the key
file content.

**Files modified:** None (this is a verification-step fix, not a code
fix). The actual produced files (`~/.tauri/invisible.key`,
`~/.tauri/invisible.key.pub`) are correct and Tauri-canonical.

### Rule 3 (auto-fix blocking issue) — plan's pubkey-length upper bound 120 < actual 152

**Discovered during:** Task 02-02-02 step 5 JSON validation.

**Issue:** Plan's validator asserted `40 <= len(pubkey) <= 120`.
Tauri 2.11.2's `.pub` file is a 152-character single-line base64 blob
(the whole minisign file encoded for env-var transport). Validation
would have failed and blocked the commit.

**Fix:** Upper bound widened to 200 chars in the in-line validator I
actually ran. The 152-char blob is exactly what Tauri 2.x's updater
config expects under `plugins.updater.pubkey` — verified by re-running
`CI=true cargo tauri build`, which accepted the config without
complaint and produced both artefacts.

**Files modified:** None — the validator was an inline `python3 -c
"..."` invocation, not a checked-in file.

### Rule 3 (auto-fix blocking issue) — `--no-password` flag does not exist in tauri-cli 2.11.2

**Discovered during:** Task 02-02-01 step B3.

**Issue:** Plan called `cargo tauri signer generate --no-password`.
`cargo tauri signer generate --help` shows no such flag; available flags
are `-p/--password`, `-w/--write-keys`, `-f/--force`, `--ci`.

**Fix:** Used `cargo tauri signer generate --ci --password ""` instead.
`--ci` skips interactive prompts; `--password ""` explicitly sets an
empty password. Same intent as the plan's text; different surface.
The generated keypair has no password (verified — Tauri's output
explicitly said `Your keypair was generated successfully:` with no
password-prompt cycle).

**Files modified:** None.

### Explicit deviation authorization — Infisical upload DEFERRED to user

**Discovered during:** Task 02-02-01 Part A (Infisical pre-flight).

**Issue:** Infisical login state is unverifiable in CLI v0.43.84 (the
plan's probe command `infisical user get domain --plain --silent` does
not work — `--plain` is not a recognised flag for the `user get`
subcommand in this CLI version). `.infisical.json` does not exist in
this worktree. Calling `infisical secrets set` returns "Please either
run infisical init to connect to a project or pass in project id with
--projectId flag." `infisical login` and `infisical init` are
interactive and the autonomous overnight run cannot drive them.

**Fix (per explicit deviation authorization in the executor prompt):**
1. Generated the keypair locally (Task 02-02-01 Part B) — succeeded.
2. Attempted the Infisical push with a manual 30-second timeout (no
   `timeout` binary on macOS — used a background-process + watchdog
   pattern). The push failed cleanly with the "no project linked" error.
3. Wrote `INFISICAL-MANUAL-ACTION.md` in the phase directory with the
   one-step user ceremony (~30 seconds: `infisical login`, `infisical
   init` pick `invisible-tauri`, `infisical secrets set ...`).
4. Continued with the rest of the plan (tauri.conf.json edit, rebuild,
   verification doc) as if the upload had succeeded — only the
   verification step that does a `infisical secrets get` round-trip
   was substituted: it became a check for the existence of
   `INFISICAL-MANUAL-ACTION.md`.
5. PHASE-VERIFICATION.md records the Infisical target path
   (`invisible-tauri` / `prod` / `TAURI_UPDATER_PRIVATE_KEY`) with the
   upload status marked DEFERRED, plus a "Pre-Phase-3 unblock" section
   warning that the ceremony must complete before Phase 3 starts.

**Files added/modified:**
- Created `INFISICAL-MANUAL-ACTION.md`.
- PHASE-VERIFICATION.md "Private key" subsection records upload-status
  as DEFERRED.
- `02-02-SUMMARY.md` (this file) flags the deferred item in the
  frontmatter `infisical.upload-status` field.

This is NOT a bug. The orchestrator explicitly authorized this fallback
path. The local keypair is the canonical source; the Infisical upload
is a one-step user ceremony before Phase 3 starts, not a re-do of any
work.

## Verification gates (all PASS — with one substitution)

| Gate | Result |
|------|--------|
| Plan 02-02 `<verification>` #1: git log shows two new commits since 02-01 | PASS — `42ed4cb` + `f58b67c` |
| Plan 02-02 `<verification>` #2: `jq '.plugins.updater'` returns exact endpoint + pubkey length | PASS — endpoint exact match, pubkey length 152 (within actual Tauri 2.x format range, exceeds plan's 40-120 only because plan's bound was wrong) |
| Plan 02-02 `<verification>` #3: `bundle.createUpdaterArtifacts` is NOT present | PASS — `'createUpdaterArtifacts' in c.get('bundle', {})` returns False |
| Plan 02-02 `<verification>` #4: `bundle.macOS.signingIdentity` is NOT present | PASS — `c['bundle'].get('macOS', {})` does not contain `signingIdentity` |
| Plan 02-02 `<verification>` #5: `infisical secrets get TAURI_UPDATER_PRIVATE_KEY` returns expected header | SUBSTITUTED per executor authorization — replaced with: `test -f INFISICAL-MANUAL-ACTION.md`. PASS. |
| Plan 02-02 `<verification>` #6: `! git ls-files \| grep -q invisible.key` | PASS — empty |
| Plan 02-02 `<verification>` #7: `~/.tauri/invisible.key` is mode 0600 | PASS — `stat -f %A ~/.tauri/invisible.key` returns `600` |
| Plan 02-02 `<verification>` #8: `^## Updater keypair` exists in PHASE-VERIFICATION.md | PASS — line 187 |
| Plan 02-02 `<verification>` #9: `.app` exists at expected path post-rebuild | PASS — `test -d` returns true |

## Phase 3 hand-off checklist (copy of PHASE-VERIFICATION.md section)

Phase 3 (`release.yml`) needs:
1. Service-token auth to Infisical (NOT OAuth) — set up a machine
   identity with read-only access to the secret
   `TAURI_UPDATER_PRIVATE_KEY` in project `invisible-tauri` env `prod`.
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
6. Export `TAURI_SIGNING_PRIVATE_KEY="$(infisical secrets get ...)"`
   before `cargo tauri build` in the macOS and Windows jobs.
7. Publish the signed manifest as `latest.json` at the GitHub Release
   URL already pinned in `plugins.updater.endpoints`.

## Deferred items

- **Infisical upload of TAURI_UPDATER_PRIVATE_KEY** — user must complete
  the ~30-second ceremony in
  `.planning/workstreams/tauri-windows/phases/INV-02-macos-app-dmg-with-signing/INFISICAL-MANUAL-ACTION.md`
  before Phase 3 release.yml can sign update manifests. The local
  keypair at `~/.tauri/invisible.key` is the canonical source; the
  ceremony just copies its content into Infisical.

## Self-Check

`src-tauri/tauri.conf.json` exists, parses as valid JSON, has the
`plugins.updater` block with the exact endpoint URL and a 152-char
base64 pubkey. Scope fences hold: identifier, build.devUrl,
build.frontendDist, bundle.windows.wix.language, app.security.csp
unchanged. `bundle.macOS.signingIdentity` is absent. `bundle.createUpdaterArtifacts` is absent.

`PHASE-VERIFICATION.md` exists, has no `{ALLCAPS}` placeholders, no
PENDING criteria rows, contains the `## Updater keypair (Plan 02-02 —
appended)` section, mentions `TAURI_UPDATER_PRIVATE_KEY`, pins the
endpoint URL, records 4 SHA256s, documents the 0600 mode of the local
key.

`INFISICAL-MANUAL-ACTION.md` exists in the phase directory with the
ceremony documented.

Commits `42ed4cb` and `f58b67c` are reachable from `HEAD` on branch
`ws/tauri-windows`.

`~/.tauri/invisible.key` exists outside the worktree at mode 0600.
`~/.tauri/invisible.key.pub` exists at mode 0644.

`git ls-files | grep -q invisible.key` returns empty (no key files in
version control — T1 mitigation holds).

`CI=true cargo tauri build` re-ran successfully after the config edit:
Mach-O arm64 binary + UDZO DMG produced, `Signature=adhoc` with no Dev
ID Authority line. No regression vs Plan 02-01.

## Self-Check: PASSED

## EXECUTION COMPLETE
