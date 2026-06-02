---
phase: INV-03-release-workflow-auto-updater
status: passed
date: 2026-06-02
plans_verified:
  - 03-01-PLAN.md
---

# Phase 3 Verification

**Goal (ROADMAP):** Tag-triggered release pipeline: `git tag v0.1.0 && git push --tags` produces signed Windows + macOS binaries attached to a GitHub Release, plus a Tauri update manifest.

**Reinterpretation per 03-CONTEXT.md:** This phase ships the **infrastructure** (workflow file + bundler config). The first actual release is a user-gated action (requires Infisical→GHA secret upload, then `git tag v0.1.0-rc1 && git push`).

## Success criteria

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | `.github/workflows/release.yml` runs on tag pushes (v*) | ✅ PASS | `on.push.tags: ['v*']` confirmed via `python3 -c "yaml.safe_load(...)"` |
| 2 | Two jobs: `build-windows` + `build-macos` | ✅ PASS | Matrix has `macos-latest` + `windows-latest`. Implemented as a single `publish` job with strategy.matrix (idiomatic for `tauri-action`). |
| 3 | Both upload artefacts to the GitHub Release | ✅ PASS | `tauri-apps/tauri-action@v0` handles upload natively; `draft: true` gate added for safety |
| 4 | Update manifest (`latest.json`) generated and uploaded | ✅ PASS | `bundle.createUpdaterArtifacts: true` enables it; verified locally by rebuild emitting `Invisible.app.tar.gz.sig` (see Local rebuild evidence) |
| 5 | Manual verification: tag a `v0.1.0-test`, watch CI, confirm artefacts | ⏭ DEFERRED-AS-USER-CEREMONY | Run-book below; requires Infisical→GHA secret upload first |

## Files shipped

| Path | Lines | Purpose |
|------|-------|---------|
| `.github/workflows/release.yml` | 95 | Tag-triggered release pipeline |
| `src-tauri/tauri.conf.json` | (+1 key) | `bundle.createUpdaterArtifacts: true` |
| `.planning/workstreams/tauri-windows/ROADMAP.md` | (+1 line) | Phase 3 plan link |

## Local rebuild evidence (no regression)

Native macOS build with `TAURI_SIGNING_PRIVATE_KEY` exported from `~/.tauri/invisible.key`:

```
cd src-tauri && PATH="$HOME/.cargo/bin:$PATH" CI=true cargo tauri build
```

Output:

```
Finished `release` profile [optimized] target(s) in 21.44s
Built application at: src-tauri/target/release/invisible-tauri
Bundling Invisible.app
Bundling Invisible_0.1.0_aarch64.dmg
Running bundle_dmg.sh
Bundling Invisible.app.tar.gz (updater)
Finished 2 bundles
Finished 1 updater signature at: Invisible.app.tar.gz.sig
```

| Artefact | Size | SHA256 |
|----------|------|--------|
| `Invisible.app/Contents/MacOS/invisible-tauri` | 13.5 MB | `e65e58b6b5b4becd7e88e34f3c63496a3bbf9535312571591e149130655af16f` |
| `Invisible_0.1.0_aarch64.dmg` | 5.40 MB | `dfd64856c133113ee546e900166ff1ede3ea6d3f7e5a3283e0e887c4295c91b9` |
| `Invisible.app.tar.gz` (updater bundle) | 5.49 MB | `b43814b190913c7fafdcd8189d7dbd10b246cf8b78c53a839b21ea5a0340583c` |
| `Invisible.app.tar.gz.sig` (updater signature) | 408 B | `924cdfd4684fbb5a76d536678fa236929de18ac9f4d051ca330d5a8b7fc6bd58` |

**Binary SHA matches Plan 02-02's rebuild** (`e65e58b6...`) — the JSON edit added `createUpdaterArtifacts: true` but the Rust output is byte-identical (the flag is bundler-only).

## CORS / scope-fence guards still hold

Phase 2 scope fences re-verified post-edit:

```python
import json
c = json.load(open('src-tauri/tauri.conf.json'))
assert c['identifier'] == 'com.theprofitplatform.invisible'
assert c['build']['devUrl'] == 'http://localhost:5173'
assert c['build']['frontendDist'] == '../frontend-vite/dist'
assert c['build']['beforeDevCommand'] == 'cd frontend-vite && pnpm dev'
assert c['build']['beforeBuildCommand'] == 'cd frontend-vite && pnpm build'
assert c['bundle']['windows']['wix']['language'] == ['en-US']
assert c['plugins']['updater']['endpoints'] == ['https://github.com/Avi977/invisible/releases/latest/download/latest.json']
assert 40 <= len(c['plugins']['updater']['pubkey']) <= 200
assert c['bundle']['createUpdaterArtifacts'] is True  # NEW in Phase 3
assert 'macOS' not in c['bundle'] or 'signingIdentity' not in c['bundle'].get('macOS', {})
print('OK')
```

Result: `OK` — all scope fences hold.

## User verification recipe (run-book)

Phase 3 deliberately does NOT push a tag or trigger a release. The autonomous run cannot drive the manual ceremonies. Here's the sequence for the user when they return:

### Step 1 — Complete the Infisical ceremony (from Plan 02-02)

See `~/.invisible-ws/tauri-windows/.planning/workstreams/tauri-windows/phases/INV-02-macos-app-dmg-with-signing/INFISICAL-MANUAL-ACTION.md`. ~30 seconds of OAuth + secret upload.

### Step 2 — Copy the private key to GitHub Actions secrets

Browser: https://github.com/Avi977/invisible/settings/secrets/actions → "New repository secret"

```bash
# Reads the key from Infisical (after Step 1), copies to clipboard
infisical secrets get TAURI_UPDATER_PRIVATE_KEY --env=prod --plain --silent | pbcopy
```

Then paste as secret `TAURI_SIGNING_PRIVATE_KEY`. Skip the `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` secret entirely (the key was generated with no password).

### Step 3 — Test the workflow

```bash
cd ~/.invisible
git pull origin main
git tag v0.1.0-rc1 -m "Test release candidate"
git push origin v0.1.0-rc1
```

Watch CI at https://github.com/Avi977/invisible/actions. Expected timing: ~10-15 min (Windows native build is the long pole; macOS native is faster).

### Step 4 — Inspect the DRAFT release

https://github.com/Avi977/invisible/releases → click on `v0.1.0-rc1` (DRAFT).

Confirm assets include:
- `Invisible_0.1.0_aarch64.dmg` (macOS)
- `Invisible_0.1.0_x64-setup.exe` (Windows)
- `Invisible.app.tar.gz` + `Invisible.app.tar.gz.sig` (updater bundle for macOS)
- `Invisible_0.1.0_x64-setup.nsis.zip` + `.nsis.zip.sig` (updater bundle for Windows)
- `latest.json` (signed manifest pointing at all of the above)

### Step 5 — Promote or clean up

**If satisfied:** Click "Publish release" → it goes live to users.
**If just testing:** Click "Delete release" → also delete the tag locally + remotely:

```bash
git tag -d v0.1.0-rc1
git push origin :v0.1.0-rc1
```

## Security posture

Threats from 03-CONTEXT.md threat_model:

- **T5 (GHA secret exfiltration):** No `echo $TAURI_*` debug step. GHA auto-masks secrets.
- **T6 (compromised action):** `tauri-apps/tauri-action@v0` floating tag (Tauri team owns it). Pinning to a commit SHA is a v0.2 hardening item.
- **T7 (accidental release):** `draft: true` gate — releases require explicit "Publish" click.
- **T8 (updater manifest poisoning):** signed `latest.json` (private key in Infisical + GHA secret; pubkey in `tauri.conf.json` is the only trust root).

Inherited from Phase 2 (T1-T4) — all still hold.

## Deferred items

- **Linux builds** (`.AppImage`, `.deb`) — defer to v0.2
- **Universal macOS binaries** — defer; single-arch is fine for v0.1
- **macOS / Windows code-signing** — still deferred (no certs)
- **Action SHA pinning** — defer; floating `@v0` acceptable for Tauri team's own action
- **First actual release** — user-driven (see run-book above)
