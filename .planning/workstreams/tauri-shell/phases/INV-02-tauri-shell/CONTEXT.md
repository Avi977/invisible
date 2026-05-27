# Phase 2: Tauri shell — CONTEXT

## Goal (verbatim from workstream ROADMAP)

Native Tauri 2.x shell loading the Vite-bundled frontend. Tray with Open /
Hide / Quit (parity with pystray today).

## Success criteria (verbatim from ROADMAP)

1. `cd src-tauri && cargo tauri dev` launches the app, loads the Vite dev server, hot-reload works.
2. Tauri commands exist for the existing CLI surface: `run_orchestrator(project, task?)`, `kill_run(project)`, `list_projects()`, `tail_log(project, lines)`, `status()`.
3. System tray with Open / Hide / Quit menu items.
4. SSE bridge from `invisible-dashboard` (8765) → Tauri event bus → frontend store (so the React app gets push updates).

## Inputs — what exists today

### Phase 1 outputs (lock-in dependencies for Phase 2)

- **`frontend-vite/`** (~16 files, 8 pages working) — `pnpm dev` on **`http://localhost:5173/`** with HMR; `pnpm build` produces **`frontend-vite/dist/`** (296 KB, hashed assets, relative `./assets/` paths — confirmed Tauri-ready).
- `pnpm-lock.yaml` deterministic.
- `vite.config.js` has `base: './'` so static assets resolve under any Tauri webview root.

### Existing CLI surface to wrap (read-only — Phase 2 invokes; does NOT modify)

- `bin/invisible-review <project> [--task "..."] [--max-iters N] [--resume] [--stop]` → orchestrator loop (`lib/orchestrator.py`)
- `bin/invisible-status` → lists running orchestrator runs across projects
- `bin/invisible-ps` → process-table view of orchestrator pids
- `bin/invisible-log <project>` → tails `~/.invisible/logs/<project>.log`
- `bin/invisible-history` → past runs
- `bin/invisible-doctor` → health check
- `bin/invisible-dashboard` daemon on **`http://127.0.0.1:8765/`** serves:
  - `/api/projects` (JSON list)
  - `/api/p/<project>` (JSON detail)
  - `/api/reviews` (JSON Notion review feed)
  - SSE endpoint TBD by sibling workstream `dashboard-wiring` — Phase 2 must NOT block on it; subscribe defensively (reconnect-with-backoff if 404/connection drops).

### Toolchain state (just installed)

| Tool | Version | Status |
|------|---------|--------|
| node | v22.14 | ✓ |
| pnpm | latest via corepack | ✓ |
| rustc | 1.95.0 | ✓ (installed via rustup default toolchain stable, profile default) |
| cargo | 1.95.0 | ✓ |
| cargo-tauri | 2.11.2 | ✓ (`cargo install tauri-cli --version "^2.0" --locked`) |
| Xcode CLT | preinstalled | ✓ (`xcode-select -p` → /Applications/Xcode.app/Contents/Developer or /Library/Developer/CommandLineTools) |

### Target Tauri version

**Tauri 2.x** (cargo-tauri 2.11.2 installed). Use Tauri 2 plugin packages (`tauri-plugin-shell`, `tauri-plugin-fs`, `tauri-plugin-process`, `tauri-plugin-os`) where needed. Avoid Tauri 1.x docs — APIs are not compatible.

## Five Tauri commands to expose (success criterion #2)

Each must be a `#[tauri::command] async fn` returning `Result<T, String>`, registered in `tauri::Builder::invoke_handler(tauri::generate_handler![...])`.

| Command | Backing CLI | Sync/Async | Returns |
|---------|------------|------------|---------|
| `list_projects` | reads `~/.invisible/invisible.toml` (or shells to `invisible-status --json`) | sync (file IO) | `Vec<ProjectMeta>` |
| `run_orchestrator(project: String, task: Option<String>)` | spawns `invisible-review <project> [--task "..."]` non-blocking; pipes stdout to a tauri event channel | async (spawn) | `RunHandle { pid, project }` |
| `kill_run(project: String)` | shells to `invisible-review <project> --stop` | async | `()` |
| `tail_log(project: String, lines: u32)` | reads last N lines of `~/.invisible/logs/<project>.log` | sync | `String` |
| `status()` | shells to `invisible-status --json` (fallback: `invisible-ps`) | async | `StatusReport` |

Use `tauri-plugin-shell` for `Command::new(...).args(...).spawn()`. Keep all CLI invocations sandboxed via the plugin's allow-list in `tauri.conf.json`.

## System tray (success criterion #3)

Tauri 2 tray API: `TrayIconBuilder::with_id("main").icon(app.default_window_icon().unwrap().clone()).menu(...)` with three menu items:

- **Open** — shows the main window (`window.show()` + `window.set_focus()`)
- **Hide** — `window.hide()`
- **Quit** — `app.exit(0)` after killing any running orchestrators (optional cleanup, leave for Phase 3 polish)

Tray icon: drop a 32×32 PNG at `src-tauri/icons/tray-icon.png` (or reuse `icon.png` from the Tauri scaffold).

Closing the window must **hide** the window (not quit the app). Override `WindowEvent::CloseRequested`:
```rust
window.on_window_event(|event| match event {
    WindowEvent::CloseRequested { api, .. } => { window.hide(); api.prevent_close(); }
    _ => {}
});
```

This mirrors `bin/invisible-app`'s pywebview "hide on close, quit via tray" pattern.

## SSE bridge (success criterion #4)

Frontend already has a fetch + EventSource path conceptually. The bridge:

1. **Rust side:** spawn a long-lived `tokio::spawn` task at app startup that opens `http://127.0.0.1:8765/api/stream` (or whatever path the dashboard daemon exposes — verify in `bin/invisible-dashboard` and `lib/dashboard_render.py`; fall back to polling `/api/projects` every 5s if SSE not implemented). Parse each event and emit on the Tauri event bus: `app.emit("dashboard:event", payload)`.
2. **Frontend side:** a small hook in `frontend-vite/src/lib/tauri.js` (new file) wraps `@tauri-apps/api/event.listen("dashboard:event", cb)`. The hook re-emits to whatever store the React app uses (currently `useState` in `App.jsx` — keep additive, don't introduce Redux).

**Defensive design:** the bridge MUST tolerate `invisible-dashboard` being down. Reconnect with exponential backoff (1s → 2s → 5s → 10s capped). The app stays usable; events just stop until reconnect.

## Files this phase WRITES

- `src-tauri/Cargo.toml` (new)
- `src-tauri/Cargo.lock` (generated)
- `src-tauri/tauri.conf.json` (new — `frontendDist: ../frontend-vite/dist`, `devUrl: http://localhost:5173`)
- `src-tauri/build.rs` (new — Tauri scaffold)
- `src-tauri/src/main.rs` (new — entry, sets up logger, runs `app::run()`)
- `src-tauri/src/lib.rs` (new — `pub fn run()` builder, command registry, tray setup, SSE bridge)
- `src-tauri/src/commands.rs` (new — the 5 `#[tauri::command]` functions)
- `src-tauri/src/sse.rs` (new — SSE client + event-bus emitter)
- `src-tauri/icons/` (new — 32×32, 128×128, 128×128@2x, icon.icns, icon.ico, icon.png) — generated via `cargo tauri icon` from a source PNG (use a placeholder for now — a solid color with "i" glyph; Phase 3 polishes)
- `src-tauri/capabilities/default.json` (new — Tauri 2's capability model; allow window-show/hide, event-listen, shell-execute for the 5 CLI commands only)
- `frontend-vite/src/lib/tauri.js` (new — small wrapper around `@tauri-apps/api/event.listen` + `invoke`)
- `frontend-vite/package.json` — add `@tauri-apps/api` as a dep (additive only)

## Files this phase MUST NOT TOUCH

- `frontend/` — legacy, frozen.
- `frontend-vite/src/*.jsx` — Phase 1 already locked these. Tauri integration goes in NEW file `frontend-vite/src/lib/tauri.js`; existing pages stay untouched (they'll consume the new lib via additive imports, but the lib's hooks are no-ops outside Tauri runtime).
- `bin/invisible-*` scripts — Tauri shells out to them; doesn't modify them.
- `lib/*.py` — sibling workstreams own these.
- `bin/invisible-app` (pywebview) — keep operational; deprecation only at end of Phase 3.

## Constraints

- **Tauri 2.x only.** Don't generate Tauri 1.x code (different config schema, different APIs).
- **Cross-platform from day one.** All path handling via Rust `PathBuf`; no hardcoded `/Users/ace/...`. Use `dirs` crate or `tauri::AppHandle::path()`.
- **No backend daemon coupling.** The Tauri app must launch and render the UI even if `invisible-dashboard` is down. SSE bridge backs off gracefully.
- **Don't modify the Vite build.** Phase 2 consumes `frontend-vite/dist` as-is; if a Vite config change is needed (e.g. adding `define` for a Tauri env flag), that's a Vite-side change requiring Phase 1 reopening. Try to avoid it.
- **Identifier:** Tauri's `tauri.conf.json` `identifier` must be a reverse-DNS string. Use `com.theprofitplatform.invisible`.

## Verification plan

1. `cd src-tauri && cargo tauri dev` (with Vite still running on 5173) — app window opens, loads the React UI, sidebar + 8 pages render.
2. Edit a `console.log` in `frontend-vite/src/pages/Dashboard.jsx`; the Tauri window hot-reloads.
3. In DevTools console (Tauri 2: right-click → Inspect, or `Cmd+Option+I`): run
   ```js
   await window.__TAURI__.core.invoke('list_projects')
   ```
   Returns the project list from `invisible.toml`.
4. Run `await window.__TAURI__.core.invoke('status')` — returns a status snapshot.
5. Run `await window.__TAURI__.core.invoke('tail_log', { project: 'jobslayer', lines: 10 })` — returns last 10 lines (or empty string if log doesn't exist yet — must not throw).
6. Click the close button (red dot) → window hides, app stays alive in tray. Click tray icon → menu shows Open / Hide / Quit. Click Open → window restores.
7. Start `invisible-dashboard --no-auth` on 8765, then in DevTools console:
   ```js
   window.__TAURI__.event.listen('dashboard:event', e => console.log('rx:', e.payload))
   ```
   Trigger a state change (run `invisible-review` against a project; or hit `/api/projects` via curl — the dashboard will tick). Console logs the event.
8. Stop `invisible-dashboard`. Confirm Tauri app stays open and usable; no crash, no error dialog. Console shows reconnect attempts with backoff.

## Out of scope (for this phase)

- Windows cross-compile — Phase 3.
- Code-signing — Phase 3.
- Auto-updater — Phase 3.
- Multi-window UX — main window only.
- Native menu bar (`tauri::MenuBuilder`) — tray is the focus; main menu defaults are fine.
- DMG branding / dock icon polish — Phase 3.
