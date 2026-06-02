# Manual Infisical Action Required (Plan 02-02)

The Tauri updater **private key** was generated at:
    `~/.tauri/invisible.key`     (mode 0600, NEVER commit)

The **public key** at `~/.tauri/invisible.key.pub` is already inlined
into `src-tauri/tauri.conf.json` as `plugins.updater.pubkey` and was
committed.

## What you need to do (one-time, ~30 seconds)

```bash
cd ~/.invisible-ws/tauri-windows
infisical login          # OAuth flow in browser
infisical init           # Pick (or create) project "invisible-tauri" → env prod
infisical secrets set TAURI_UPDATER_PRIVATE_KEY="$(cat ~/.tauri/invisible.key)" --env=prod --path=/
```

## Why this is deferred

`infisical login` opens a browser OAuth flow; `infisical init` is
interactive. The autonomous run done overnight couldn't drive either.
The keypair was generated, the pubkey was committed, the binary still
builds — only the Infisical upload is missing. Phase 3 (`release.yml`)
reads `TAURI_UPDATER_PRIVATE_KEY` from Infisical at CI time, so this
must be uploaded before the first tag-triggered release.

## Verification after upload

```bash
infisical secrets get TAURI_UPDATER_PRIVATE_KEY --env=prod --plain --silent | head -1
# Should print: untrusted comment: minisign secret key encrypted with...
```
