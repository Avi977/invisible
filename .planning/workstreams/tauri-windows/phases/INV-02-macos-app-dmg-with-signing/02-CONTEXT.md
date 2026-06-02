# Phase 2: macOS .app + .dmg with signing - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning
**Source:** Inline seed (user is not paying for Apple Developer Program)

<domain>
## Phase Boundary

This phase produces a working **unsigned** macOS `.app` and `.dmg` from `cargo tauri build` on this Mac, with a documented user-facing workaround for Gatekeeper. It also generates the **Tauri auto-updater keypair** (separate from Apple signing) so Phase 3 can wire up signed update manifests.

**In scope:**
- `cargo tauri build` (no target → native macOS) produces `.app` + `.dmg`
- Tauri updater public/private keypair generation + storage
- `tauri.conf.json` updater config (pubkey + endpoint placeholder)
- README "Download" section with right-click → Open instructions

**Out of scope (deferred):**
- Apple Developer ID signing (`codesign`)
- Notarisation (`notarytool`)
- Universal binary (arm64 + x86_64) — single-arch native is fine for v0.1
</domain>

<decisions>
## Implementation Decisions

### Apple Developer Program / Signing
- **LOCKED: Ship UNSIGNED.** User declined the $99/year Apple Developer Program for this open-source side project.
- **LOCKED:** No `codesign` invocation. No notarisation. No `spctl` verification.
- **LOCKED:** `tauri.conf.json` `bundle.macOS.signingIdentity` is **omitted** (null/absent) — do not stub it with a placeholder.
- **LOCKED:** Success criteria #1 and #3 from ROADMAP are reinterpreted as: "documented unsigned build + user workaround" instead of "Dev ID cert + codesign --verify".

### Gatekeeper workaround (user-facing)
- **LOCKED:** README documents two unblock paths users can pick from:
  1. Right-click `.app` → Open → confirm in dialog (one-time, macOS remembers)
  2. Terminal: `xattr -dr com.apple.quarantine /Applications/Invisible.app`
- **LOCKED:** Workaround lives in a new `## Installation (macOS)` section of the root `README.md` next to the existing "Download" link.

### Tauri auto-updater keypair (separate from Apple signing)
- **LOCKED:** Generated locally via `tauri signer generate -w ~/.tauri/invisible.key` (or `npx @tauri-apps/cli signer generate`).
- **LOCKED:** **Private key → Infisical.** Project: reuse the existing `invisible` project if one exists, else create new project `invisible-tauri`. Env: `prod`. Key name: `TAURI_UPDATER_PRIVATE_KEY`. Password (if set): `TAURI_UPDATER_KEY_PASSWORD`.
- **LOCKED:** **Public key → inline in `tauri.conf.json`** under `plugins.updater.pubkey` (Tauri 2.x schema).
- **LOCKED:** Updater endpoint URL is a placeholder in this phase: `"endpoints": ["https://github.com/Avi977/invisible/releases/latest/download/latest.json"]`. Phase 3 will produce the actual `latest.json`.

### Build pipeline
- **LOCKED:** Build command is `cargo tauri build` (no `--target` flag — native macOS only).
- **LOCKED:** Output paths to capture in `PHASE-VERIFICATION.md`:
  - `.app`: `src-tauri/target/release/bundle/macos/Invisible.app`
  - `.dmg`: `src-tauri/target/release/bundle/dmg/Invisible_0.1.0_<arch>.dmg`
- **LOCKED:** SHA256 of both artefacts captured in verification doc.
- **LOCKED:** No CI in this phase — Phase 3 (`release.yml`) does CI. This phase verifies local build only.

### Claude's Discretion
- Whether the `.app` needs `LSUIElement`/`NSHighResolutionCapable` plist tweaks (apply if the build needs them, otherwise leave defaults)
- Whether to add a `cargo tauri build --bundles dmg` invocation alongside the default (only if default already produces both)
- Exact wording of the README workaround section (keep it short, link to Apple's docs)
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Tauri docs
- Tauri 2.x updater plugin: https://v2.tauri.app/plugin/updater/
- Tauri 2.x signing/codesign config: https://v2.tauri.app/distribute/sign/macos/ (use only the sections about unsigned distribution + the updater keypair — skip Apple Developer ID sections)
- `tauri signer` CLI: https://v2.tauri.app/reference/cli/#signer

### Infisical (project memory)
- See `[[infisical_vault]]` memory — vault at `vault.theprofitplatform.com.au`, backend on `127.0.0.1:8222`
- Existing pattern for storing app secrets (e.g. `[[vbk_crypt_secret]]` rclone passphrase) — follow the same project/env/key naming hygiene

### Sibling workstream files this phase OWNS
- `src-tauri/tauri.conf.json` — adds `plugins.updater` block; does NOT touch `identifier`, `devUrl`, `frontendDist`, `beforeDevCommand`
- `README.md` — adds `## Installation (macOS)` section near the Download link

### Files this phase MUST NOT touch
- `.github/workflows/*` — Phase 3 territory
- Any sibling-workstream paths (vps-connection, tools-page, relations-page, calendar-events, ci-and-onboarding)
</canonical_refs>

<specifics>
## Specific Ideas

- Use `tauri signer generate` (built into Tauri CLI) — not OpenSSL, not custom — to keep the keypair format aligned with what the Tauri updater expects.
- When storing the private key in Infisical, paste the full key including the `untrusted comment:` header line — Tauri's signer reads the whole file.
- Run `cargo tauri build` once with no `--target` to confirm Phase 1's `cargo xwin` config didn't break native macOS build path. (Phase 1 added cross-compile machinery; this phase verifies native still works.)
- Verification should screenshot or `file Invisible.app/Contents/MacOS/Invisible` to confirm Mach-O native binary, not something cross-compiled.
</specifics>

<deferred>
## Deferred Ideas

- **Apple Developer ID signing + notarisation** — defer until user decides $99/year is worth it. Can be added as a Phase 2.x slot later without replanning Phase 2.
- **Universal binary** (arm64 + x86_64 combined) — single-arch is fine for v0.1; revisit if Intel-Mac users complain.
- **Auto-update manifest generation** — Phase 3 territory.
- **`spctl --add` / Gatekeeper allow rule** — not applicable to unsigned distribution.
</deferred>

---

*Phase: INV-02-macos-app-dmg-with-signing*
*Context seeded inline: 2026-06-02 (no discuss-phase run — single locked decision, no design questions remaining)*
