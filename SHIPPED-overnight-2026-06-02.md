# SHIPPED — overnight autonomous run, 2026-06-02

**TL;DR:** All 8 outstanding PRs merged to `main`. The `invisible` desktop app **builds end-to-end** from `main` — `.app` + `.dmg` + signed `Invisible.app.tar.gz.sig` updater bundle. The app **launches cleanly** (smoke-tested). Three short user ceremonies remain before you can ship a public release (~3 minutes total — list at the bottom).

Run window: ~2026-06-02 00:50 → 01:30 PDT (~40 min). One Mac, one autonomous Claude session.

## What was completed tonight

### Eight PRs merged

| PR | Title | Workstream | Result |
|----|-------|-----------|--------|
| [#7](https://github.com/Avi977/invisible/pull/7) | feat(INV-02): land Tauri Phase 2 — tray + 5 commands + SSE bridge | tauri-shell | ✅ merged |
| [#8](https://github.com/Avi977/invisible/pull/8) | feat(INV-01): Analytics aggregator — /api/v1/analytics + Analytics page wired (REQ-05) | analytics-aggregator | ✅ merged (after conflict resolution) |
| [#9](https://github.com/Avi977/invisible/pull/9) | Phase 1: /api/v1/calendar + Calendar page wired (calendar-events M2) | calendar-events | ✅ merged (after conflict resolution) |
| [#10](https://github.com/Avi977/invisible/pull/10) | feat(INV-01): /api/v1/tools CRUD + Tools page wired (M2 tools-page) | tools-page | ✅ merged (after conflict resolution) |
| [#11](https://github.com/Avi977/invisible/pull/11) | Phase 1: /api/v1/relations + Relations page wired (relations-page M2) | relations-page | ✅ merged (clean) |
| [#12](https://github.com/Avi977/invisible/pull/12) | vps-connection Phase 1: SSH ControlMaster + tree_vps verify-and-harden | vps-connection | ✅ merged (clean) |
| [#13](https://github.com/Avi977/invisible/pull/13) | feat(INV): tauri-windows workstream — Phase 1+2+3 | **tauri-windows** | ✅ merged (created tonight) |
| [#14](https://github.com/Avi977/invisible/pull/14) | feat(INV): ci-and-onboarding workstream — Phase 1 (GitHub Actions CI) | ci-and-onboarding | ✅ merged (created tonight) |

Zero open PRs as of write-time. Final main commit: `9bc21f4`.

### tauri-windows phases — completed in tonight's run

This is the workstream we picked up mid-flight. Phase 1 was already done by an earlier session; Phase 2 + Phase 3 were planned + executed tonight.

#### Phase 2 — macOS .app + .dmg with updater keypair (4 commits)

**Plan 02-01** — native build verification + Gatekeeper workaround:
- `cargo tauri build` (native arm64) produces `.app` + `.dmg`
- `README.md` added `## Installation (macOS)` with two unblock paths (right-click → Open, scoped `xattr -dr com.apple.quarantine /Applications/Invisible.app`)
- Documented one deviation: first build failed at the DMG-bundling step with an AppleScript timeout (`-1712`) — fixed by `CI=true` env to skip the cosmetic Finder window layout. Documented in `PHASE-VERIFICATION.md`. **GitHub Actions sets `CI=true` automatically, so Phase 3 release.yml needs no special handling.**

**Plan 02-02** — Tauri updater keypair:
- Generated locally via `cargo tauri signer generate --ci --password ""`
- **Private key:** `~/.tauri/invisible.key` (mode 0600, NEVER committed)
- **Public key:** inlined into `src-tauri/tauri.conf.json` under `plugins.updater.pubkey`
- Endpoint pinned to `https://github.com/Avi977/invisible/releases/latest/download/latest.json`
- **Infisical upload deferred** to a ~30-second user ceremony (couldn't drive OAuth from autonomous run) — see `INFISICAL-MANUAL-ACTION.md` in the phase dir

**Locked decisions (all still honored):**
- No Apple Developer Program ($99/yr declined)
- No `codesign`, no `notarytool`, no `bundle.macOS.signingIdentity`
- README workaround replaces Dev ID signing for v0.1

#### Phase 3 — release.yml + auto-updater (NEW tonight, planned + executed inline)

**Plan 03-01** — `.github/workflows/release.yml`:
- Tag-triggered (`v*`) release pipeline
- 2-platform matrix: `macos-latest` (`--target aarch64-apple-darwin`) + `windows-latest` (native — no `cargo xwin` from macOS for CI; that was Phase 1's local-only optimization)
- `tauri-apps/tauri-action@v0` handles build, package, upload, and `latest.json` generation
- Releases created as **DRAFT** for your review before publishing (safety gate against accidental tag pushes)
- `src-tauri/tauri.conf.json` got one new key: `bundle.createUpdaterArtifacts: true`
- **`.gitignore` fix**: bare `workflows/` pattern was unintentionally matching `.github/workflows/` (intended only for the daemon's per-machine `<repo>/workflows/` state). Anchored to `/workflows/` so the release workflow file can actually be committed. Tested via `git check-ignore`.

**Locally verified end-to-end** (line in build log: `Finished 1 updater signature at: Invisible.app.tar.gz.sig`) — the toolchain is proven; CI just needs the GHA secret to do the same.

### Final build evidence (from `main` post-merge)

```
cd ~/.invisible/src-tauri
PATH="$HOME/.cargo/bin:$PATH" CI=true cargo tauri build
```

Result: `Finished 2 bundles` + `Finished 1 updater signature`. App was launched in background, PID 93072, ran cleanly, killed.

| Artefact | SHA256 | Size |
|----------|--------|------|
| `Invisible.app/Contents/MacOS/invisible-tauri` (Mach-O 64-bit arm64) | `3a0a1114dbf4f68c1cd8161e4304de3aad95059b2deb2913b8a118f8b0b2acab` | 13.5 MB |
| `Invisible_0.1.0_aarch64.dmg` | `6f835de10834b23fa56c81d0dab82cb0505453be3d14d4ea936c13c3176da5ec` | 5.40 MB |
| `Invisible.app.tar.gz` (updater bundle) | `081908b9a912e1e2f8fa061ac88dd7154a2474f53565515af0cb2dc0a6131a75` | 5.49 MB |
| `Invisible.app.tar.gz.sig` (updater signature) | `325e77f4b0cc6ed0ceeb130760a0c4a5df4f15c1829d1a6f64089b6b5d98f33e` | 408 B |

Different SHAs vs the earlier in-worktree build — `main` had merge commits + slight diffs that produced a different binary. Same .gitignore + same Rust deps, same shape.

### Python API state (post-merge)

```python
from api import projects, chat, tree_local, tree_vps, tree_repo, analytics, relations, calendar, tools
# All import cleanly. ROUTES = ['/api/v1/projects', '/api/v1/relations', '/api/v1/calendar']
# analytics + tools dispatched inline in invisible-dashboard.do_GET (not via ROUTES dict)
```

### Conflict resolution choices (worth knowing about)

Most PR merges had only CHANGELOG.md conflicts (auto-regenerated via `scripts/update-changelog.py`). Three notable manual choices:

1. **PR #8 (analytics) and PR #9 (calendar): kept main's `*` ACAO + TODO note for follow-up tightening.** The analytics branch had partial loopback-echo CORS; main had permissive `*`. Combining them produced duplicate ACAO headers (browsers reject per CORS spec). Took main's simpler approach + added `TODO(post-merge): tighten end_headers() to loopback-echo only` comments.

2. **PR #10 (tools-page) flipped the CORS story** — the tools-page branch had the PROPER single-source loopback-only fix (`_cors_headers()` helper called from `_send_json`/`_send_text` BEFORE bare `end_headers()`). Took its approach and let it supersede main's `*`. End result: the daemon now has correct single-source loopback CORS in `bin/invisible-dashboard`. The TODO comments from #8/#9 are now stale but harmless — clean them up in a follow-up.

3. **lib/notion.py** in PR #9: kept BOTH `query_calendar_db()` (calendar branch) and `query_reviews_since()` (analytics branch via main) — additive helpers, no conflict in intent.

## What you need to do (three ceremonies, ~3 minutes total)

### 1. Infisical upload (Plan 02-02 deferred work) — ~30 seconds

```bash
cd ~/.invisible-ws/tauri-windows
infisical login          # opens browser OAuth flow
infisical init           # pick (or create) project "invisible-tauri" → env prod
infisical secrets set TAURI_UPDATER_PRIVATE_KEY="$(cat ~/.tauri/invisible.key)" --env=prod --path=/
```

Verification:
```bash
infisical secrets get TAURI_UPDATER_PRIVATE_KEY --env=prod --plain --silent | head -1
# Should print: untrusted comment: minisign secret key encrypted with...
```

Full doc: `~/.invisible-ws/tauri-windows/.planning/workstreams/tauri-windows/phases/INV-02-macos-app-dmg-with-signing/INFISICAL-MANUAL-ACTION.md`

### 2. Copy private key to GitHub Actions secrets — ~1 minute

Browser: https://github.com/Avi977/invisible/settings/secrets/actions → "New repository secret"

```bash
# Copies key to clipboard (after step 1)
infisical secrets get TAURI_UPDATER_PRIVATE_KEY --env=prod --plain --silent | pbcopy
```

Paste as secret `TAURI_SIGNING_PRIVATE_KEY`. Skip the `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` secret entirely (the key was generated with no password).

### 3. Test the release pipeline — ~10 minutes (mostly waiting on CI)

```bash
cd ~/.invisible
git pull origin main         # if needed
git tag v0.1.0-rc1 -m "Test release candidate"
git push origin v0.1.0-rc1
```

Watch CI at https://github.com/Avi977/invisible/actions. Expected ~10-15 min (Windows native build is the long pole).

DRAFT release appears at https://github.com/Avi977/invisible/releases — confirm assets include:
- `Invisible_0.1.0_aarch64.dmg` (macOS)
- `Invisible_0.1.0_x64-setup.exe` (Windows)
- `Invisible.app.tar.gz` + `.sig` (macOS updater bundle)
- `Invisible_0.1.0_x64-setup.nsis.zip` + `.sig` (Windows updater bundle)
- `latest.json` (signed manifest)

**If satisfied:** Click "Publish release". If just testing: Delete release + delete tag (`git push origin :v0.1.0-rc1`).

## Known issues / deferred items

### Hard blockers for actual release (the three ceremonies above)
- Infisical upload of `TAURI_UPDATER_PRIVATE_KEY` (Step 1)
- GHA secret copy (Step 2)
- First tag push to verify CI end-to-end (Step 3)

### Code quality follow-ups (not blocking)
- Stale `TODO(post-merge): tighten end_headers()...` comments in `bin/invisible-dashboard` (from PR #8 + #9 merge resolutions) are now wrong — PR #10's CORS fix made `_cors_headers()` the single source. Worth a 1-min cleanup PR.
- Pin `tauri-apps/tauri-action@v0` to a commit SHA (T6 from Phase 3 threat model). Acceptable as floating tag for v0.1.

### Future work (deferred per ROADMAP / CONTEXT decisions)
- **Linux builds** (`.AppImage`, `.deb`) — v0.2
- **Universal macOS binaries** (arm64 + x86_64) — v0.2; single-arch is fine for v0.1
- **macOS Dev ID signing + notarisation** — gated on $99/yr Apple Developer Program decision
- **Windows code-signing** — gated on cert purchase
- **`ci-and-onboarding` Phase 2** (first-run wizard) + **Phase 3** (invisible-doctor polish)
- **Tauri-windows tagged release** (after the three ceremonies)

## How to test locally tomorrow morning (sanity check before doing the ceremonies)

```bash
# 1. Confirm main builds from scratch
cd ~/.invisible
git pull
cd src-tauri
PATH="$HOME/.cargo/bin:$PATH" CI=true cargo tauri build   # ~5-15 min if cache warm; ~30 if cold

# 2. Launch the .app and click around
open src-tauri/target/release/bundle/macos/Invisible.app

# 3. Optional: install the .dmg and unblock per README
open src-tauri/target/release/bundle/dmg/Invisible_0.1.0_aarch64.dmg
# Drag Invisible.app to Applications, then:
#   xattr -dr com.apple.quarantine /Applications/Invisible.app
#   open /Applications/Invisible.app

# 4. Run the dashboard + frontend daemons to test the wired pages
INVISIBLE_HOME=$(pwd) ./bin/invisible-dashboard --no-auth &
INVISIBLE_HOME=$(pwd) ./bin/invisible-frontend --port 8090 &
# Then open http://127.0.0.1:8090 in your browser; click through all 8 pages
# (Dashboard, Folders, Terminals, Analytics, Calendar, Tools, Relations, Focus)
```

## Files of interest left behind

- `~/.tauri/invisible.key` — Tauri updater private key (LOCAL, 0600, source of truth until Infisical upload)
- `~/.tauri/invisible.key.pub` — Tauri updater public key (already inlined in tauri.conf.json; safe to share)
- `/tmp/invisible-pre-pull-backup/` — backup of pre-merge `.planning/workstreams/*` leftovers (from earlier sessions; safe to delete after you verify main is good)

## Memories I'd update tomorrow (if you want me to)

- `invisible_workstreams.md` → update: "5 of 6 M1 workstreams merged" → "all 6 M1 + 6 M2 + tauri-windows + ci-and-onboarding merged as of 2026-06-02"
- `invisible_terminals_pty_shipped.md` → still accurate; M2 picture above supersedes
- New memory worth writing: `invisible_release_pipeline` — the three-ceremony pattern for first release

---

🤖 Generated end-of-run. Started at 00:50 PDT, finished at 01:30 PDT. Eight PRs merged, two phases planned + executed, one workflow file shipped, one app built. The desktop app is functional locally; the public release is one user-driven tag push away.
