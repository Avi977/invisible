---
phase: INV-02-tauri-shell
workstream: tauri-shell
plan: 01
type: execute
wave: 1
depends_on:
  - INV-01-vite-migration-of-frontend
files_modified:
  # src-tauri tree (all new)
  - src-tauri/.gitignore
  - src-tauri/Cargo.toml
  - src-tauri/build.rs
  - src-tauri/tauri.conf.json
  - src-tauri/capabilities/default.json
  - src-tauri/icons/icon.png
  - src-tauri/icons/32x32.png
  - src-tauri/icons/128x128.png
  - src-tauri/icons/128x128@2x.png
  - src-tauri/icons/icon.icns
  - src-tauri/icons/icon.ico
  - src-tauri/icons/tray-icon.png
  - src-tauri/src/main.rs
  - src-tauri/src/lib.rs
  - src-tauri/src/commands.rs
  - src-tauri/src/sse.rs
  # frontend-vite touches (additive only — NO .jsx files modified)
  - frontend-vite/package.json
  - frontend-vite/pnpm-lock.yaml
  - frontend-vite/src/lib/tauri.js
  # docs
  - README.md
  - CHANGELOG.md
autonomous: false   # Task 5 is a checkpoint:human-verify for the 8-step verification plan
requirements:
  - REQ-06
user_setup: []      # cargo-tauri already installed; no external accounts; everything runs locally
must_haves:
  truths:
    - "`cd src-tauri && cargo tauri dev` opens a native window that loads the Vite dev server on 5173 with HMR working (edit a .jsx file → window reloads)"
    - "All 5 Tauri commands invoke from the DevTools console and return the documented shape: `list_projects` returns a JSON array, `status` returns a JSON object, `tail_log(project, lines)` returns a string (empty string for missing logs, not an error), `run_orchestrator(project, task?)` returns `{pid, project}`, `kill_run(project)` returns null/ok"
    - "System tray icon is visible in the macOS menubar with Open / Hide / Quit menu items, and each item performs its action correctly"
    - "Closing the main window (red dot / Cmd-W) hides the window — the app stays alive in the tray; clicking 'Open' from the tray restores the window"
    - "SSE bridge subscribes to `${INVISIBLE_SERVER_URL or http://127.0.0.1:8765}/api/stream`; if the endpoint returns 404 (current `invisible-dashboard` behavior) the bridge transparently falls back to polling `/api/projects` every 5s; either way the frontend receives `dashboard:event` events on the Tauri event bus"
    - "The Tauri app launches and renders the UI even with `invisible-dashboard` not running; SSE/polling failures retry with exponential backoff (1s → 2s → 5s → 10s capped) and never crash the window"
    - "Capability allow-list in `src-tauri/capabilities/default.json` restricts shell execution to exactly the 5 `invisible-*` binaries — `invisible-status`, `invisible-review`, `invisible-ps`, `invisible-log`, plus the absolute-path read of `~/.invisible/logs/*.log`"
    - "`tauri.conf.json` identifier is `com.theprofitplatform.invisible`, `frontendDist` is `../frontend-vite/dist`, `devUrl` is `http://localhost:5173`"
    - "All cross-platform path handling goes through `tauri::AppHandle::path()` or `dirs::home_dir()` — no hardcoded `/Users/ace/...` strings anywhere in `src-tauri/src/`"
    - "Phase 1 deliverable `frontend-vite/dist/` is consumed unchanged (no Vite config reopened); `frontend-vite/src/*.jsx` files are NOT modified by this phase"
    - "`bin/invisible-app` (pywebview) is unchanged and continues to function as the fallback shell"
  artifacts:
    - path: "src-tauri/Cargo.toml"
      provides: "Tauri 2.x Rust deps: tauri@2, tauri-plugin-shell@2, tauri-build@2; plus reqwest (rustls), tokio (rt-multi-thread+macros), futures-util, eventsource-stream, serde, serde_json, dirs, anyhow"
      contains: "tauri = "
    - path: "src-tauri/tauri.conf.json"
      provides: "Tauri 2.x config: productName=Invisible, identifier=com.theprofitplatform.invisible, build.devUrl, build.frontendDist=../frontend-vite/dist, build.beforeDevCommand, app.windows[0]"
      contains: "com.theprofitplatform.invisible"
    - path: "src-tauri/capabilities/default.json"
      provides: "Tauri 2 capability set: core perms + shell:allow-execute scoped to the 5 invisible-* binaries; fs:allow-read scoped to ~/.invisible/logs/"
      contains: "shell:allow-execute"
    - path: "src-tauri/build.rs"
      provides: "Standard Tauri 2 build script invoking tauri_build::build()"
      contains: "tauri_build::build"
    - path: "src-tauri/src/main.rs"
      provides: "Binary entrypoint — calls into invisible_tauri::run() from lib.rs; sets up tracing/log subscriber"
      contains: "fn main"
    - path: "src-tauri/src/lib.rs"
      provides: "pub fn run(): tauri::Builder, plugin(shell), invoke_handler!(5 commands), setup() registers tray + spawns SSE task, on_window_event hides on close"
      contains: "tauri::generate_handler"
    - path: "src-tauri/src/commands.rs"
      provides: "5 #[tauri::command] async fns: list_projects, run_orchestrator, kill_run, tail_log, status. Return Result<T, String>."
      contains: "#[tauri::command]"
    - path: "src-tauri/src/sse.rs"
      provides: "SSE bridge: tokio task subscribing to /api/stream with eventsource-stream; falls back to polling /api/projects on 404 or connect failure; exponential backoff; emits dashboard:event on the Tauri event bus"
      contains: "dashboard:event"
    - path: "src-tauri/icons/tray-icon.png"
      provides: "32x32 dark-circle 'i' glyph PNG for the system tray (template image)"
      contains: ""
    - path: "frontend-vite/src/lib/tauri.js"
      provides: "Thin ESM wrapper: invoke() proxy, subscribeDashboard(cb) using @tauri-apps/api/event listen('dashboard:event'), isTauri() runtime guard. No JSX files modified."
      contains: "dashboard:event"
    - path: "frontend-vite/package.json"
      provides: "Adds @tauri-apps/api@^2 as a dependency (additive); no script changes, no other deps touched"
      contains: "@tauri-apps/api"
  key_links:
    - from: "src-tauri/tauri.conf.json"
      to: "frontend-vite/dist/index.html"
      via: '"frontendDist": "../frontend-vite/dist"'
      pattern: '"frontendDist":\s*"\.\./frontend-vite/dist"'
    - from: "src-tauri/tauri.conf.json"
      to: "http://localhost:5173"
      via: '"devUrl": "http://localhost:5173"'
      pattern: '"devUrl":\s*"http://localhost:5173"'
    - from: "src-tauri/src/lib.rs"
      to: "src-tauri/src/commands.rs"
      via: "tauri::generate_handler![commands::list_projects, commands::run_orchestrator, commands::kill_run, commands::tail_log, commands::status]"
      pattern: "generate_handler!\\["
    - from: "src-tauri/src/lib.rs"
      to: "src-tauri/src/sse.rs"
      via: "tauri::async_runtime::spawn(sse::run_bridge(app.handle().clone()))"
      pattern: "sse::run_bridge"
    - from: "src-tauri/src/sse.rs"
      to: "frontend-vite (Tauri event bus)"
      via: "app_handle.emit(\"dashboard:event\", payload)"
      pattern: 'emit\(\s*"dashboard:event"'
    - from: "frontend-vite/src/lib/tauri.js"
      to: "src-tauri (Tauri event bus)"
      via: "import { listen } from '@tauri-apps/api/event'; listen('dashboard:event', cb)"
      pattern: "listen\\(\\s*['\"]dashboard:event"
    - from: "src-tauri/capabilities/default.json"
      to: "src-tauri/src/commands.rs (shell.command(...))"
      via: '"shell:allow-execute" scope entries enumerate invisible-status, invisible-review, invisible-ps, invisible-log'
      pattern: '"shell:allow-execute"'
---

<objective>
Phase 2 of the `tauri-shell` workstream: stand up a Tauri 2.x native shell that loads the Vite-bundled frontend produced in Phase 1, exposes the 5 CLI commands as `#[tauri::command]`s, parks in the system tray with Open / Hide / Quit, and bridges the `invisible-dashboard` event stream onto the Tauri event bus.

Purpose: Replace `bin/invisible-app` (pywebview) for the primary developer experience. Tauri gives us a ~10 MB binary, native Windows packaging in Phase 3, code-signing in Phase 3, and an auto-updater in Phase 3. This phase builds the shell only — packaging, signing, and updater are Phase 3 work.

Output: A working `src-tauri/` Rust project where `cargo tauri dev` launches a native window, loads `http://localhost:5173/` (the Vite dev server already produced by Phase 1), invokes the 5 commands successfully, shows a tray icon with a 3-item menu, hides-on-close, and emits `dashboard:event` to the frontend whether or not the dashboard daemon is reachable. `bin/invisible-app`, `bin/invisible-*` scripts, `frontend/`, and `frontend-vite/src/*.jsx` files are not modified.

Phase 3 (Windows `.msi` cross-compile, code-signing, Tauri auto-updater, macOS notarization, pywebview deletion) is explicitly OUT OF SCOPE — it gets its own PLAN.md after this one ships.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/REQUIREMENTS.md
@.planning/workstreams/tauri-shell/ROADMAP.md
@.planning/workstreams/tauri-shell/phases/INV-02-tauri-shell/CONTEXT.md
@.planning/workstreams/tauri-shell/phases/INV-01-vite-migration-of-frontend/INV-01-01-SUMMARY.md

# Phase 1 outputs we consume (read-only references — DO NOT modify)
@frontend-vite/package.json
@frontend-vite/vite.config.js
@frontend-vite/src/main.jsx
@frontend-vite/src/App.jsx

# Existing patterns to mirror (read-only)
@bin/invisible-app
@bin/invisible-dashboard
@bin/invisible-server

<interfaces>
<!-- Contracts the executor needs. Extracted from the existing repo + the
     canonical Tauri 2 docs (verified via v2.tauri.app + docs.rs/tauri/2). -->

### Tauri 2.x APIs the executor will use (cite-once, use everywhere)

```rust
// Commands (src/commands.rs)
#[tauri::command]
async fn list_projects() -> Result<Vec<ProjectMeta>, String> { ... }

// Registration (src/lib.rs)
tauri::Builder::default()
    .plugin(tauri_plugin_shell::init())
    .invoke_handler(tauri::generate_handler![
        commands::list_projects,
        commands::run_orchestrator,
        commands::kill_run,
        commands::tail_log,
        commands::status,
    ])
    .setup(|app| { /* tray + SSE spawn */ Ok(()) })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");

// Tray (in setup closure)
use tauri::{menu::{Menu, MenuItem}, tray::TrayIconBuilder};
let open_i = MenuItem::with_id(app, "open", "Open", true, None::<&str>)?;
let hide_i = MenuItem::with_id(app, "hide", "Hide", true, None::<&str>)?;
let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
let menu  = Menu::with_items(app, &[&open_i, &hide_i, &quit_i])?;
let _tray = TrayIconBuilder::with_id("main")
    .icon(app.default_window_icon().unwrap().clone())
    .menu(&menu)
    .show_menu_on_left_click(true)
    .on_menu_event(|app, event| match event.id.as_ref() {
        "open" => { if let Some(w) = app.get_webview_window("main") { let _ = w.show(); let _ = w.set_focus(); } }
        "hide" => { if let Some(w) = app.get_webview_window("main") { let _ = w.hide(); } }
        "quit" => app.exit(0),
        _ => {}
    })
    .build(app)?;

// Hide-on-close (on the main window obtained via app.get_webview_window("main"))
use tauri::WindowEvent;
window.on_window_event(move |event| {
    if let WindowEvent::CloseRequested { api, .. } = event {
        let _ = window_handle.hide();
        api.prevent_close();
    }
});

// Event emit (Rust → frontend)
use tauri::Emitter;
app_handle.emit("dashboard:event", payload)?;
```

### JS-side (frontend-vite/src/lib/tauri.js)
```js
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
export const isTauri = () => typeof window !== 'undefined' && '__TAURI__' in window;
export async function tauriInvoke(cmd, args) { return invoke(cmd, args); }
export async function subscribeDashboard(cb) {
  return listen('dashboard:event', e => cb(e.payload));
}
```

### Cargo deps (verified versions; pin with caret unless noted)
```toml
[build-dependencies]
tauri-build = { version = "2", features = [] }

[dependencies]
tauri               = { version = "2", features = ["tray-icon"] }
tauri-plugin-shell  = "2"
serde               = { version = "1", features = ["derive"] }
serde_json          = "1"
tokio               = { version = "1", features = ["rt-multi-thread", "macros", "sync", "time", "process"] }
reqwest             = { version = "0.12", default-features = false, features = ["rustls-tls", "stream", "json"] }
futures-util        = "0.3"
eventsource-stream  = "0.2"
dirs                = "5"
anyhow              = "1"
tracing             = "0.1"
tracing-subscriber  = { version = "0.3", features = ["env-filter"] }
```

### `invisible-dashboard` (the local daemon at 127.0.0.1:8765 — what CONTEXT specifies)
Verified from `bin/invisible-dashboard` lines 266–315 in this worktree:
  - GET /healthz            — no-auth probe
  - GET /                   — HTML (token-gated)
  - GET /p/<project>        — HTML (token-gated)
  - GET /api/projects       — JSON list (token-gated)
  - GET /api/p/<project>    — JSON detail (token-gated)
  - GET /api/reviews        — JSON Notion review tail (token-gated)
  - **NO /api/stream** — this daemon does not implement SSE.

Auth: Bearer token from $INVISIBLE_DASHBOARD_TOKEN (also accepted as `?token=...`).

### `invisible-server` (the VPS daemon — uses $INVISIBLE_SERVER_URL)
Verified from `bin/invisible-server` lines 21, 326, 341, 364, 377, 413:
  - GET /api/stream         — SSE: `data: {...}\n\n` per event
  - POST /api/events        — ingest (not consumed by Tauri)
  - GET /api/projects       — JSON list
  - + the same HTML routes as the local dashboard
  - Auth: $INVISIBLE_SERVER_TOKEN.

**Implication for the SSE bridge:** When `$INVISIBLE_SERVER_URL` is set, prefer that base URL (the VPS daemon DOES expose SSE). When it's unset, fall back to `http://127.0.0.1:8765` (the local dashboard — which does NOT expose SSE today). The bridge must detect a 404 on `/api/stream` and gracefully degrade to polling `/api/projects` on a fixed cadence. Same auth pattern: read `$INVISIBLE_SERVER_TOKEN` or `$INVISIBLE_DASHBOARD_TOKEN` depending on which URL is in use. Mirror the URL/token resolution in `bin/invisible-app:80-101` (the existing pywebview wrapper).

### The 5 commands' expected shapes (canonical, from CONTEXT)

```rust
// src/commands.rs (sketch — actual file is the executor's deliverable)
#[derive(serde::Serialize)]
pub struct ProjectMeta { pub project: String, pub state: String, pub age: String,
    pub iter: i32, pub max_iters: i32, pub verdict: String, pub summary: String,
    pub cost_usd: f64, pub host: String, pub updated_at: String }

#[derive(serde::Serialize)]
pub struct RunHandle { pub pid: u32, pub project: String }

#[derive(serde::Serialize)]
pub struct StatusReport { pub projects: Vec<ProjectMeta>, pub fetched_at: String,
    pub source: String /* "invisible-status" | "fallback:invisible-ps" */ }
```

`list_projects`  : shell out `invisible-status --json` (preferred); on non-zero exit or parse error, scan `~/.invisible/worktrees/*/feature/.invisible-checkpoint.json` directly (mirror `bin/invisible-dashboard:84-116`).
`run_orchestrator(project, task?)`: spawn `invisible-review <project> [--task "..."]` via `tauri-plugin-shell` Command; return the spawned PID + project. Do NOT block on stdout — pipe output to a tauri event channel keyed by project.
`kill_run(project)`: spawn `invisible-review <project> --stop`; await exit; return `()`. If exit code != 0, surface stderr as `Err(String)`.
`tail_log(project, lines)`: read last `lines` lines of `~/.invisible/logs/<project>.log` (resolve via `dirs::home_dir()` joined with `.invisible/logs/<project>.log`). If the file doesn't exist, return `Ok("")` — DO NOT return Err. Lines arg is `u32`; clamp to [1, 10_000] to avoid OOM on a foot-gun.
`status`: shell out `invisible-status --json`; on failure, fall back to `invisible-ps` and synthesise a minimal `StatusReport`. The `source` field records which path was used so the frontend can show a degraded-state indicator.

### Cross-platform path helper

```rust
// src/commands.rs
fn invisible_home() -> std::path::PathBuf {
    if let Ok(env_home) = std::env::var("INVISIBLE_HOME") {
        return std::path::PathBuf::from(env_home);
    }
    dirs::home_dir()
        .map(|h| h.join(".invisible"))
        .expect("home_dir() must resolve on macOS/Linux/Windows")
}
```

Use this everywhere — never hardcode `/Users/ace/.invisible`. The Windows binary in Phase 3 will resolve `%USERPROFILE%\.invisible` via the same `dirs` crate.

### Capability allow-list (src-tauri/capabilities/default.json — Tauri 2 schema)

```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "default",
  "description": "Default capability set for Invisible desktop shell",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "core:event:default",
    "core:window:allow-show",
    "core:window:allow-hide",
    "core:window:allow-set-focus",
    "core:window:allow-close",
    "shell:default",
    {
      "identifier": "shell:allow-execute",
      "allow": [
        { "name": "invisible-status",  "cmd": "invisible-status",  "args": true, "sidecar": false },
        { "name": "invisible-review",  "cmd": "invisible-review",  "args": true, "sidecar": false },
        { "name": "invisible-ps",      "cmd": "invisible-ps",      "args": true, "sidecar": false },
        { "name": "invisible-log",     "cmd": "invisible-log",     "args": true, "sidecar": false }
      ]
    }
  ]
}
```

This shape was verified against Tauri 2.11.2's generated `gen/schemas/desktop-schema.json` via a throwaway `cargo tauri init` + `cargo add tauri-plugin-shell` + `cargo build` in `/tmp` on 2026-05-26. Key facts confirmed by the schema:
- `ShellScopeEntry` requires `name` + `sidecar`, with optional `cmd` (string) and `args`.
- `cmd` is a **plain string** (not an object with `program`); the literal command name resolved on `PATH`. The path can start with a `$HOME` etc. variable but does not need to.
- `args` is `bool | [string | {validator: regex}]`. `args: true` permits any arguments — required for `run_orchestrator` whose `--task` payload routinely contains whitespace. The earlier `[{ "validator": "\\S+" }]` form silently rejected multi-word task strings.
- `shell:default` is required so the plugin's IPC commands (execute, kill, spawn, open) are registered at all. Without it, `shell:allow-execute` is a no-op.
- The `args: true` form is broader than ideal but functionally correct for Phase 2. Phase 3 hardening item: tighten via either a custom permission TOML in `src-tauri/permissions/` or per-command argument validators.

Do NOT add any additional permissions beyond `shell:default` + the scoped `shell:allow-execute` — the threat model below depends on this set being minimal.

### Tauri identifier rules

`identifier` must be reverse-DNS, lowercase ASCII, no hyphens in segments after the first. `com.theprofitplatform.invisible` is valid. Do not change it.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Scaffold src-tauri/ deterministically (Cargo.toml + tauri.conf.json + entry skeletons + icons + capabilities + .gitignore)</name>
  <files>
    src-tauri/.gitignore,
    src-tauri/Cargo.toml,
    src-tauri/build.rs,
    src-tauri/tauri.conf.json,
    src-tauri/capabilities/default.json,
    src-tauri/icons/icon.png,
    src-tauri/icons/32x32.png,
    src-tauri/icons/128x128.png,
    src-tauri/icons/128x128@2x.png,
    src-tauri/icons/icon.icns,
    src-tauri/icons/icon.ico,
    src-tauri/icons/tray-icon.png,
    src-tauri/src/main.rs,
    src-tauri/src/lib.rs
  </files>
  <action>
Stand up the `src-tauri/` tree by hand (not via `cargo tauri init` — that prompts interactively and produces non-deterministic output). Every file is written from the executor; nothing is left to the scaffold to guess.

Step 1 — Toolchain preflight (cargo is on `~/.cargo/bin` which is NOT in non-login shell PATH by default):
  - `source "$HOME/.cargo/env" || true`
  - `cargo --version` must report 1.95.0+ and `cargo tauri --version` must report `tauri-cli 2.11.x`. If either is missing, stop and surface a clear error — do NOT auto-install.
  - `rustc --version` must report 1.95.0+.
  - Confirm `frontend-vite/dist/index.html` exists; this phase consumes it.

Step 2 — Create `src-tauri/.gitignore`:
  - `target/`
  - `WixTools/`
  - `gen/`
  (Note: `Cargo.lock` is INTENTIONALLY committed for the binary crate — Rust convention for binaries. Phase 3's signed/notarised macOS build needs reproducible deps. Do NOT add `Cargo.lock` to this file.)

Step 3 — Create `src-tauri/Cargo.toml`:
  - `[package]`: `name = "invisible-tauri"`, `version = "0.1.0"`, `edition = "2021"`, `description = "Invisible desktop shell"`, `default-run = "invisible-tauri"`.
  - `[lib]`: `name = "invisible_tauri"`, `crate-type = ["staticlib", "cdylib", "rlib"]` (required by Tauri 2 for mobile + desktop targets).
  - `[[bin]]`: `name = "invisible-tauri"`, `path = "src/main.rs"`.
  - `[build-dependencies]`: `tauri-build = { version = "2", features = [] }`.
  - `[dependencies]`: paste the exact block under <interfaces> "Cargo deps" — pinning `tauri = { version = "2", features = ["tray-icon"] }`, `tauri-plugin-shell = "2"`, plus reqwest/eventsource-stream/tokio/futures-util/dirs/anyhow/serde/serde_json/tracing/tracing-subscriber. Do NOT add any other deps in this task.

Step 4 — Create `src-tauri/build.rs`:
```rust
fn main() {
    tauri_build::build()
}
```

Step 5 — Create `src-tauri/tauri.conf.json`. Use Tauri 2 schema (NOT Tauri 1's `tauri.allowlist`):
```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "Invisible",
  "version": "0.1.0",
  "identifier": "com.theprofitplatform.invisible",
  "build": {
    "devUrl": "http://localhost:5173",
    "frontendDist": "../frontend-vite/dist",
    "beforeDevCommand": "cd ../frontend-vite && pnpm dev",
    "beforeBuildCommand": "cd ../frontend-vite && pnpm build"
  },
  "app": {
    "withGlobalTauri": true,
    "windows": [
      {
        "label": "main",
        "title": "Invisible",
        "width": 1200,
        "height": 800,
        "minWidth": 700,
        "minHeight": 500,
        "resizable": true,
        "fullscreen": false,
        "decorations": true,
        "transparent": false,
        "visible": true,
        "backgroundColor": "#0d0f12"
      }
    ],
    "security": {
      "csp": null
    }
  },
  "bundle": {
    "active": true,
    "targets": ["app", "dmg"],
    "icon": ["icons/32x32.png", "icons/128x128.png", "icons/128x128@2x.png", "icons/icon.icns", "icons/icon.ico"],
    "category": "DeveloperTool",
    "shortDescription": "Personal multi-agent dev cockpit",
    "longDescription": "Native Tauri shell for the invisible cockpit. Loads the Vite-bundled React UI; bridges the invisible-dashboard event stream to the frontend."
  }
}
```
Notes:
  - `withGlobalTauri: true` is on intentionally — the success criteria in CONTEXT include verifying `window.__TAURI__.core.invoke('list_projects')` from the DevTools console. Phase 3 may turn this off and rewrite the verification.
  - `beforeDevCommand` uses `pnpm --filter ./frontend-vite` so it works whether or not the dev runs `cargo tauri dev` from `src-tauri/` or the repo root. If pnpm filters fail on macOS (they should not), fall back to `cd ../frontend-vite && pnpm dev` — document the deviation in SUMMARY.
  - `bundle.targets` is `["app", "dmg"]` for Phase 2; Phase 3 adds `["msi", "nsis"]` after Windows cross-compile is wired.
  - No `bundle.macOS.signingIdentity` — Phase 3 work.

Step 6 — Create `src-tauri/icons/`:
  - Generate a placeholder 512×512 PNG from Python (Pillow already used by `bin/invisible-app` to draw its tray glyph — same pattern). Write a one-shot inline script to `/tmp/gen-icon.py` (do NOT commit that file; only the resulting PNGs) that creates a dark circle on transparent background with a small white "i" glyph, matching `bin/invisible-app:216-231`. Save as `src-tauri/icons/icon.png` (512×512).
  - Run `cd src-tauri && cargo tauri icon icons/icon.png` to generate all required resolutions and the platform-specific `.icns`/`.ico`/`.png` variants under `icons/`.
  - Verify the following files now exist: `32x32.png`, `128x128.png`, `128x128@2x.png`, `icon.icns`, `icon.ico`, `icon.png`. The Tauri config above references each of these — they MUST be present before `cargo tauri dev` is run.
  - Also create `src-tauri/icons/tray-icon.png` (32×32, generated with the same script — the smaller resolution makes the menubar template image legible). This is referenced from `src/lib.rs` when wiring the tray in Task 3; create it here so the file exists before the tray code compiles.

Step 7 — Create `src-tauri/capabilities/default.json`. Paste the JSON from <interfaces> "Capability allow-list" verbatim. Do NOT add any extra `permissions` entries beyond what's listed there.

Step 8 — Create `src-tauri/src/main.rs` (binary entry):
```rust
fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env()
            .add_directive("invisible_tauri=info".parse().unwrap()))
        .init();
    invisible_tauri::run();
}
```

Step 9 — Create `src-tauri/src/lib.rs` with a STUB `run()` for now (Tasks 2-4 expand it):
```rust
//! Invisible Tauri shell — entrypoint and builder. Tray + commands + SSE
//! bridge are wired in subsequent tasks.

pub mod commands;
pub mod sse;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```
Also create EMPTY-BUT-COMPILABLE stubs at `src-tauri/src/commands.rs` and `src-tauri/src/sse.rs` so the build succeeds:
```rust
// src/commands.rs (stub — populated in Task 2)
#![allow(dead_code)]
```
```rust
// src/sse.rs (stub — populated in Task 4)
#![allow(dead_code)]
```

Step 10 — Build + smoke-launch:
  - `cd src-tauri && cargo build` (no `--release`) — first build pulls ~300 MB of crates and takes 2-5 minutes on this Mac. EXPECT success; any error here means a dep version is wrong or rustc is too old. Surface the first error verbatim.
  - Start the Vite dev server in the background: `(cd frontend-vite && pnpm dev > /tmp/vite-dev.log 2>&1 &)`; wait up to 6 seconds for "Local: http://localhost:5173/" to appear in `/tmp/vite-dev.log`.
  - `(cd src-tauri && cargo tauri dev > /tmp/tauri-dev.log 2>&1 &)`; wait up to 30 seconds. The window should appear and load 5173. If it does, kill both processes (`pkill -f "cargo tauri dev" ; pkill -f "vite"`) and proceed.
  - At this point the window will be blank-with-stub-commands (the 5 commands and the tray come in Tasks 2-3) — that is acceptable for Task 1. What matters is: `cargo build` succeeds, the window opens, and it loads the Vite dev server.

Do NOT touch `frontend-vite/src/*.jsx`, `frontend/`, `bin/`, `lib/` in this task.
  </action>
  <verify>
    <automated>source "$HOME/.cargo/env" 2>/dev/null || true && cd src-tauri && test -f Cargo.toml && test -f build.rs && test -f tauri.conf.json && test -f capabilities/default.json && test -f src/main.rs && test -f src/lib.rs && test -f src/commands.rs && test -f src/sse.rs && test -f icons/icon.png && test -f icons/32x32.png && test -f icons/128x128.png && test -f icons/128x128@2x.png && test -f icons/icon.icns && test -f icons/icon.ico && test -f icons/tray-icon.png && grep -q '"identifier": "com.theprofitplatform.invisible"' tauri.conf.json && grep -q '"frontendDist": "../frontend-vite/dist"' tauri.conf.json && grep -q '"devUrl": "http://localhost:5173"' tauri.conf.json && grep -q 'tauri = { version = "2"' Cargo.toml && grep -q 'tauri-plugin-shell' Cargo.toml && grep -q 'eventsource-stream' Cargo.toml && cargo build 2>&1 | tail -5 && test -f target/debug/invisible-tauri</automated>
  </verify>
  <done>
    `src-tauri/` exists with Cargo.toml (Tauri 2.x deps), tauri.conf.json (identifier=com.theprofitplatform.invisible, frontendDist=../frontend-vite/dist, devUrl=http://localhost:5173), 6 icon files generated by `cargo tauri icon`, the tray-icon PNG, the capability allow-list, and stub `main.rs`/`lib.rs`/`commands.rs`/`sse.rs`. `cargo build` succeeds and produces `target/debug/invisible-tauri`. `frontend-vite/src/*.jsx`, `frontend/`, `bin/`, and `lib/` are unchanged.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: The 5 Tauri commands — list_projects, run_orchestrator, kill_run, tail_log, status</name>
  <files>
    src-tauri/src/commands.rs,
    src-tauri/src/lib.rs
  </files>
  <behavior>
    Each command is a `#[tauri::command] async fn` returning `Result<T, String>`. All five are registered via `tauri::generate_handler!`. Capability allow-list (already written in Task 1) restricts shell execution to the 4 `invisible-*` binaries. Specifically:
    - `list_projects()` → `Vec<ProjectMeta>`. Source order: (1) shell `invisible-status --json` and parse; (2) on failure, walk `${INVISIBLE_HOME or ~/.invisible}/worktrees/*/feature/.invisible-checkpoint.json` and synthesise (mirror `bin/invisible-dashboard:84-116`). Returns `Ok([])` if no projects exist — never `Err` for empty.
    - `run_orchestrator(project: String, task: Option<String>)` → `RunHandle`. Spawns `invisible-review <project> [--task "..."]` via `tauri-plugin-shell` Command::spawn(). Returns `{pid, project}` immediately; the spawned process keeps running. stdout/stderr lines are emitted on the Tauri event bus as `run:stdout` / `run:stderr` with `{project, line}` payloads — this is best-effort; if event-channel wiring breaks, the spawn still succeeds.
    - `kill_run(project: String)` → `()`. Shells `invisible-review <project> --stop` synchronously (`.output().await`). Returns `Ok(())` on exit 0; `Err(stderr_string)` otherwise.
    - `tail_log(project: String, lines: u32)` → `String`. Reads the last `lines` lines (clamped to [1, 10_000]) of `${INVISIBLE_HOME or ~/.invisible}/logs/<project>.log`. Returns `Ok("")` if the file does not exist (CONTEXT.md verification step 5 requires this — must not throw).
    - `status()` → `StatusReport`. Shells `invisible-status --json`; on non-zero exit OR parse failure, falls back to shelling `invisible-ps` and synthesising a minimal report. The `source` field on the response records `"invisible-status"` or `"fallback:invisible-ps"`.

    Test cases (compile-time + runtime, validated in <verify>):
    - `tail_log("nonexistent-project", 10)` returns `Ok("")` (not Err).
    - `tail_log("any", 99_999_999)` clamps internally and returns within 1s (no OOM, no panic).
    - `list_projects()` invoked when `~/.invisible/worktrees/` does NOT exist returns `Ok([])` (synthesised path).
    - `status()` invoked when `invisible-status` is not on PATH returns the fallback synthesised report with `source = "fallback:invisible-ps"`; if that ALSO fails, returns `Err(...)`. Both paths are testable by toggling PATH in the test harness.
  </behavior>
  <action>
Open `src-tauri/src/commands.rs` (the stub from Task 1) and write the full module. Then update `src-tauri/src/lib.rs` to register the 5 handlers.

Step 1 — Add the types at the top of `commands.rs`:
```rust
use std::path::PathBuf;
use serde::{Serialize, Deserialize};
use tauri::AppHandle;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandEvent;

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ProjectMeta {
    pub project: String,
    pub state: String,        // "RUN" | "idle" | "stale"
    pub iter: i32,
    pub max_iters: i32,
    pub verdict: String,
    pub summary: String,
    pub host: String,
    pub updated_at: String,
    pub started_at: String,
    pub age: String,
    pub cost_usd: f64,
    pub task_first: String,
}

#[derive(Serialize, Debug, Clone)]
pub struct RunHandle { pub pid: u32, pub project: String }

#[derive(Serialize, Debug, Clone)]
pub struct StatusReport {
    pub projects: Vec<ProjectMeta>,
    pub fetched_at: String,
    pub source: String,
}
```

Step 2 — Add the cross-platform helper (paste from <interfaces>):
```rust
pub(crate) fn invisible_home() -> PathBuf {
    if let Ok(env_home) = std::env::var("INVISIBLE_HOME") {
        return PathBuf::from(env_home);
    }
    dirs::home_dir()
        .map(|h| h.join(".invisible"))
        .expect("home_dir() must resolve on macOS/Linux/Windows")
}
```

Step 3 — Implement `list_projects`:
  - Try shell first: `app.shell().command("invisible-status").args(["--json"]).output().await`. If exit code 0 and stdout parses to `Vec<ProjectMeta>`, return it.
  - Else, scan `invisible_home().join("worktrees")`. For each `*/feature/.invisible-checkpoint.json`, parse JSON, synthesise `ProjectMeta` using the same field-extraction logic as `bin/invisible-dashboard:84-116` (state via PID check, age via `humanize_age` — implement a 3-line local helper that diffs the ISO-8601 `updated_at` against `chrono::Utc::now()` and formats `"3m ago" / "1h ago" / "yesterday"`. If pulling chrono is a hassle, use `std::time::SystemTime` + manual format — see <interfaces>; the exact string format isn't load-bearing as long as it's a short human-readable hint).
  - If the worktrees dir doesn't exist, return `Ok(vec![])` — do not error.
  - Sort: active runs first (`state == "RUN"`), then by `updated_at` descending. Mirror `bin/invisible-dashboard:111-115`.

Step 4 — Implement `run_orchestrator(project, task)`. The closure capture is non-trivial; follow this skeleton exactly (paste-ready, compile-clean):

```rust
#[tauri::command]
pub async fn run_orchestrator(
    app: AppHandle,
    project: String,
    task: Option<String>,
) -> Result<RunHandle, String> {
    // Clone owned data into the async task BEFORE consuming `project` for the
    // RunHandle. The async block must own its `project` copy for emit payloads,
    // and the app handle must be cloneable too.
    let project_for_task = project.clone();
    let app_handle = app.clone();

    let mut args: Vec<String> = vec![project.clone()];
    if let Some(t) = task {
        args.push("--task".into());
        args.push(t);
    }

    let (mut rx, child) = app
        .shell()
        .command("invisible-review")
        .args(&args)
        .spawn()
        .map_err(|e| e.to_string())?;

    let pid = child.pid();

    tauri::async_runtime::spawn(async move {
        let project = project_for_task; // owned by this task
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    let _ = app_handle.emit("run:stdout", serde_json::json!({
                        "project": project,
                        "line": String::from_utf8_lossy(&line),
                    }));
                }
                CommandEvent::Stderr(line) => {
                    let _ = app_handle.emit("run:stderr", serde_json::json!({
                        "project": project,
                        "line": String::from_utf8_lossy(&line),
                    }));
                }
                CommandEvent::Terminated(payload) => {
                    let _ = app_handle.emit("run:exit", serde_json::json!({
                        "project": project,
                        "code": payload.code,
                    }));
                    break;
                }
                _ => {}
            }
        }
    });

    Ok(RunHandle { pid, project })
}
```

Required imports at the top of `commands.rs` for this function: `use tauri::{AppHandle, Emitter}; use tauri_plugin_shell::{ShellExt, process::CommandEvent};`. The async spawn outlives the function call; that's intentional — it's how stdout/stderr stream to the frontend until the child process terminates.

Step 5 — Implement `kill_run(project)`:
  - `let out = app.shell().command("invisible-review").args([&project, "--stop"]).output().await.map_err(|e| e.to_string())?;`
  - If `out.status.success()` return `Ok(())`. Else, return `Err(String::from_utf8_lossy(&out.stderr).into_owned())`.

Step 6 — Implement `tail_log(project, lines)`. **Path-traversal sanitisation is mandatory** — see threat T-INV02-02. The webview can pass arbitrary `project` strings; without sanitisation `project = "../../etc/passwd"` would escape `~/.invisible/logs/`. Use `PathBuf::file_name()` to strip every `/`, `\\`, and `..` segment, then reject empty/dot results:

```rust
#[tauri::command]
pub async fn tail_log(project: String, lines: u32) -> Result<String, String> {
    // Clamp the requested line count to a sane ceiling.
    let lines = lines.clamp(1, 10_000) as usize;

    // SECURITY: sanitise `project` to its last path component only.
    // `Path::new("../etc/passwd").file_name()` → Some("passwd"), eliminating
    // every traversal segment. Empty/dot inputs are rejected.
    let safe_project = std::path::Path::new(&project)
        .file_name()
        .and_then(|s| s.to_str())
        .ok_or_else(|| "invalid project name".to_string())?;
    if safe_project.is_empty() || safe_project.starts_with('.') {
        return Err("invalid project name".to_string());
    }

    let path = invisible_home()
        .join("logs")
        .join(format!("{}.log", safe_project));

    if !path.exists() {
        return Ok(String::new());
    }

    // For files larger than 10 MB, use std::io::BufReader + a ring buffer of
    // `lines` capacity to avoid pulling the whole file into memory.
    let body = std::fs::read_to_string(&path).map_err(|e| e.to_string())?;
    let kept: Vec<&str> = body.lines().rev().take(lines).collect();
    Ok(kept.into_iter().rev().collect::<Vec<_>>().join("\n"))
}
```

Step 7 — Implement `status()`:
  - Try `app.shell().command("invisible-status").args(["--json"]).output().await`. If success + parses to `Vec<ProjectMeta>`, build `StatusReport { projects, fetched_at: <now ISO-8601>, source: "invisible-status".to_string() }`.
  - On any failure (spawn error, non-zero exit, JSON parse error), try `invisible-ps`. Take its plain-text output, run `list_projects()` again as a deep fallback, and return `StatusReport { ..., source: "fallback:invisible-ps".to_string() }`.
  - If both fail, return `Err(format!("status: both invisible-status and invisible-ps failed: {}", error_summary))`.

Step 8 — Mark each command with `#[tauri::command]`. Each takes `app: AppHandle` as the first parameter for the shell handle. Example:
```rust
#[tauri::command]
pub async fn tail_log(app: AppHandle, project: String, lines: u32) -> Result<String, String> { ... }
```

Step 9 — Update `src-tauri/src/lib.rs` to register the handlers (replace the stub `run` body):
```rust
pub mod commands;
pub mod sse;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            commands::list_projects,
            commands::run_orchestrator,
            commands::kill_run,
            commands::tail_log,
            commands::status,
        ])
        // Tray and SSE bridge added in Tasks 3 + 4 via .setup(...).
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

Step 10 — Compile + smoke:
  - `cd src-tauri && cargo build` — must succeed. The first compile after adding reqwest+eventsource-stream will take 2-3 more minutes.
  - Re-run `cargo tauri dev` (Vite dev server still needs to be running). Open the DevTools console (Cmd+Opt+I on macOS) and run:
    ```js
    await window.__TAURI__.core.invoke('tail_log', { project: 'nonexistent', lines: 10 })   // should be ""
    await window.__TAURI__.core.invoke('list_projects')                                      // should be an array (possibly empty)
    ```
    Both must succeed (not throw). The `list_projects` array may be empty on a fresh checkout — that's expected.
  - Kill the dev runtime.

Do NOT touch `frontend-vite/src/*.jsx`, `frontend/`, `bin/`, `lib/`.
  </action>
  <verify>
    <automated>source "$HOME/.cargo/env" 2>/dev/null || true && cd src-tauri && grep -q "#\[tauri::command\]" src/commands.rs && grep -c "pub async fn" src/commands.rs | awk '{ exit ($1 >= 5) ? 0 : 1 }' && grep -q "list_projects" src/lib.rs && grep -q "run_orchestrator" src/lib.rs && grep -q "kill_run" src/lib.rs && grep -q "tail_log" src/lib.rs && grep -q "status" src/lib.rs && grep -q "generate_handler!" src/lib.rs && grep -q "invisible_home" src/commands.rs && grep -q "file_name()" src/commands.rs && ! grep -RnE '"/Users/ace/\\.invisible|/Users/[a-z]+/\\.invisible' src/ && cargo build 2>&1 | tail -3 && cargo check --message-format=short 2>&1 | grep -E "^error" | wc -l | awk '{ exit ($1 == 0) ? 0 : 1 }'</automated>
  </verify>
  <done>
    `commands.rs` declares 5 `#[tauri::command] pub async fn`s with `Result<T, String>` signatures (list_projects, run_orchestrator, kill_run, tail_log, status); all use `invisible_home()` for path resolution and never hardcode `/Users/ace`; `lib.rs` registers all 5 in `generate_handler!`. `cargo build` succeeds with zero errors. Invoking `tail_log` on a nonexistent project from DevTools returns `""` (not Err). `frontend-vite/src/*.jsx`, `frontend/`, `bin/`, `lib/` unchanged.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: System tray (Open / Hide / Quit) + close-to-hide window event</name>
  <files>
    src-tauri/src/lib.rs
  </files>
  <action>
Wire the system tray and the close-to-hide behavior in the `.setup()` closure of the Tauri builder in `src/lib.rs`. The tray icon image was already generated as `icons/tray-icon.png` in Task 1.

Step 1 — Add imports at the top of `lib.rs`:
```rust
use tauri::{Manager, Emitter, WindowEvent};
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
```

Step 2 — Add a `.setup()` closure to the builder in `pub fn run()`. Inside it:
  a) Build the menu (paste verbatim — the API is single-quotation-mark sensitive on enabled/accelerator args):
```rust
let open_i = MenuItem::with_id(app, "open", "Open", true, None::<&str>)?;
let hide_i = MenuItem::with_id(app, "hide", "Hide", true, None::<&str>)?;
let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
let menu = Menu::with_items(app, &[&open_i, &hide_i, &quit_i])?;
```
  b) Build the tray:
```rust
let _tray = TrayIconBuilder::with_id("main")
    .icon(app.default_window_icon().unwrap().clone())
    .tooltip("Invisible")
    .menu(&menu)
    .show_menu_on_left_click(true)
    .on_menu_event(|app, event| match event.id.as_ref() {
        "open" => {
            if let Some(win) = app.get_webview_window("main") {
                let _ = win.show();
                let _ = win.unminimize();
                let _ = win.set_focus();
            }
        }
        "hide" => {
            if let Some(win) = app.get_webview_window("main") {
                let _ = win.hide();
            }
        }
        "quit" => {
            // Phase 2: clean exit. Phase 3 polish may kill running orchestrators first.
            app.exit(0);
        }
        _ => {}
    })
    .build(app)?;
```
Note: `app.default_window_icon()` returns the icon Tauri configured via `bundle.icon` — the dark-circle 'i' PNG generated in Task 1. Using `tray-icon.png` directly would require `Image::from_path()`; reusing the default keeps the menubar appearance consistent with the dock icon.

  c) Register the close-to-hide handler on the main window:
```rust
let main_window = app.get_webview_window("main").expect("main window must exist");
let window_for_close = main_window.clone();
main_window.on_window_event(move |event| {
    if let WindowEvent::CloseRequested { api, .. } = event {
        let _ = window_for_close.hide();
        api.prevent_close();
    }
});
```
This mirrors `bin/invisible-app:264-271` (the pywebview `_on_window_closing` that returns False to prevent the destroy and calls `self.window.hide()` instead). The Tauri 2 API uses `api.prevent_close()` and a clone of the window handle for the closure capture.

Step 3 — Make sure the setup closure returns `Ok(())`. Final shape of `.setup()`:
```rust
.setup(|app| {
    // tray
    let open_i = MenuItem::with_id(app, "open", "Open", true, None::<&str>)?;
    // ... (rest of menu + tray)
    let _tray = TrayIconBuilder::with_id("main")...build(app)?;

    // close-to-hide
    let main_window = app.get_webview_window("main").expect("main window must exist");
    let window_for_close = main_window.clone();
    main_window.on_window_event(move |event| {
        if let WindowEvent::CloseRequested { api, .. } = event {
            let _ = window_for_close.hide();
            api.prevent_close();
        }
    });

    // SSE bridge spawn — added in Task 4
    Ok(())
})
```

Step 4 — Compile + manual smoke (we can't fully automate the tray click; the checkpoint in Task 5 covers it):
  - `cd src-tauri && cargo build` — must succeed.
  - `cargo tauri dev` (with Vite still on 5173). Confirm the tray icon appears in the menubar within 5 seconds of launch. Click the main window's red close dot — the window must disappear, the dock icon may remain, the tray icon stays visible. Click "Open" in the tray menu — the window must reappear. Click "Hide" — it hides again. Click "Quit" — the app exits and the tray icon disappears.
  - Note any anomalies in the SUMMARY (e.g. macOS shows the dock icon as bouncing on `app.exit()` — that's expected; Phase 3 polish may add NSAccessoryActivationPolicy).

Do NOT modify `frontend-vite/src/*.jsx`, `frontend/`, `bin/`, `lib/`.
  </action>
  <verify>
    <automated>source "$HOME/.cargo/env" 2>/dev/null || true && cd src-tauri && grep -q "use tauri::menu" src/lib.rs && grep -q "use tauri::tray::TrayIconBuilder" src/lib.rs && grep -q 'MenuItem::with_id(app, "open"' src/lib.rs && grep -q 'MenuItem::with_id(app, "hide"' src/lib.rs && grep -q 'MenuItem::with_id(app, "quit"' src/lib.rs && grep -q "on_menu_event" src/lib.rs && grep -q "WindowEvent::CloseRequested" src/lib.rs && grep -q "api.prevent_close()" src/lib.rs && grep -q "\.hide()" src/lib.rs && grep -q ".setup(" src/lib.rs && cargo build 2>&1 | tail -3 && cargo check --message-format=short 2>&1 | grep -E "^error" | wc -l | awk '{ exit ($1 == 0) ? 0 : 1 }'</automated>
  </verify>
  <done>
    `src/lib.rs` `.setup()` closure builds a `TrayIconBuilder::with_id("main")` with Open/Hide/Quit `MenuItem`s and an `on_menu_event` handler that shows/hides/exits respectively. A `WindowEvent::CloseRequested` handler on the main window calls `api.prevent_close()` and `window.hide()`. `cargo build` succeeds. (Visual confirmation of the tray and close-to-hide deferred to the Task 5 checkpoint.)
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: SSE bridge with polling fallback + `frontend-vite/src/lib/tauri.js`</name>
  <files>
    src-tauri/src/sse.rs,
    src-tauri/src/lib.rs,
    frontend-vite/src/lib/tauri.js,
    frontend-vite/package.json,
    frontend-vite/pnpm-lock.yaml
  </files>
  <behavior>
    A long-lived background task subscribes to the `invisible-dashboard` event source and re-emits each event onto the Tauri event bus as `dashboard:event`. Specifically:
    - Resolve base URL: `$INVISIBLE_SERVER_URL` if set, else `http://127.0.0.1:8765`. Resolve token similarly (`$INVISIBLE_SERVER_TOKEN` xor `$INVISIBLE_DASHBOARD_TOKEN`), Bearer in `Authorization`.
    - Attempt 1: `GET {base}/api/stream` with `Accept: text/event-stream`. If the response is 200 with `Content-Type: text/event-stream`, parse `data:` frames via `eventsource-stream`; for each event, emit `dashboard:event` with `{source: "sse", payload: <parsed-json-or-string>}`.
    - Attempt 2 (fallback): if the SSE endpoint returns 404 OR the connection cannot be established, poll `GET {base}/api/projects` every 5 seconds. Compute a stable hash of the response body and emit `dashboard:event` with `{source: "poll", projects: <json>}` ONLY when the hash changes. This avoids spamming the frontend with no-op events.
    - Exponential backoff between attempts when both fail: 1s → 2s → 5s → 10s capped (matches CONTEXT.md). Reset to 1s on a successful connect.
    - Never panics. Any error is logged via `tracing::warn!` and the loop continues.

    Frontend side (frontend-vite/src/lib/tauri.js):
    - Exports `isTauri()`, `tauriInvoke(cmd, args)`, `subscribeDashboard(cb)`. The hook returns an unsubscribe function from `@tauri-apps/api/event.listen`. Outside the Tauri runtime (e.g. plain browser dev), `subscribeDashboard` becomes a no-op that returns a no-op unsubscriber. No existing `frontend-vite/src/*.jsx` files are modified — the lib is additive and lazy.

    Test cases:
    - With dashboard daemon NOT running: SSE bridge logs reconnect attempts and exponential backoff; no panic; Tauri app stays usable.
    - With dashboard daemon running (local, no SSE): bridge gets 404 on /api/stream, falls back to polling /api/projects every 5s; emits `dashboard:event` only when the JSON body changes.
    - With $INVISIBLE_SERVER_URL pointed at `invisible-server` (the VPS daemon that DOES expose SSE): bridge consumes the SSE stream directly and emits per-event.
  </behavior>
  <action>
Step 1 — Add `@tauri-apps/api` to `frontend-vite/package.json`:
  - In `dependencies`, add `"@tauri-apps/api": "^2"`. Do not touch any other field.
  - Run `cd frontend-vite && pnpm install` — this updates `pnpm-lock.yaml`. Verify the install completes within 60s.

Step 2 — Create `frontend-vite/src/lib/tauri.js`:
```js
// Tauri runtime bridge — used by future pages to talk to the Rust backend.
// Safe to import in plain-browser dev: helpers no-op when window.__TAURI__ is absent.

export const isTauri = () => typeof window !== 'undefined' && '__TAURI__' in window;

export async function tauriInvoke(cmd, args = undefined) {
  if (!isTauri()) {
    throw new Error(`tauriInvoke('${cmd}'): not running under Tauri`);
  }
  const { invoke } = await import('@tauri-apps/api/core');
  return invoke(cmd, args);
}

// subscribeDashboard(cb) → Promise<() => void>
// Listens for `dashboard:event` and forwards e.payload to cb.
// In a plain browser, returns a no-op unsubscribe so callers don't have
// to branch on isTauri() at every call-site.
export async function subscribeDashboard(cb) {
  if (!isTauri()) {
    return () => {};
  }
  const { listen } = await import('@tauri-apps/api/event');
  const unlisten = await listen('dashboard:event', e => {
    try { cb(e.payload); } catch (err) { console.error('dashboard:event handler threw:', err); }
  });
  return unlisten;
}
```
Note: this file is purely additive. Existing `.jsx` files (App.jsx, pages/*.jsx) are NOT modified. Phase 3 or a future M1 wiring task will import from this lib to actually consume events; for Phase 2, the lib's existence + DevTools console testing is sufficient.

Step 3 — Implement `src-tauri/src/sse.rs`:
```rust
//! Bridge: invisible-dashboard event stream → Tauri event bus.
//! Tries SSE first; falls back to polling /api/projects when SSE is absent.

use std::time::Duration;
use tauri::{AppHandle, Emitter};
use futures_util::StreamExt;
use eventsource_stream::Eventsource;
use serde_json::Value;
use tracing::{info, warn};

const POLL_INTERVAL: Duration = Duration::from_secs(5);
const BACKOFF_STEPS: &[Duration] = &[
    Duration::from_secs(1), Duration::from_secs(2),
    Duration::from_secs(5), Duration::from_secs(10),
];

fn dashboard_url() -> String {
    std::env::var("INVISIBLE_SERVER_URL")
        .ok()
        .unwrap_or_else(|| "http://127.0.0.1:8765".to_string())
        .trim_end_matches('/')
        .to_string()
}

fn dashboard_token() -> String {
    if std::env::var("INVISIBLE_SERVER_URL").is_ok() {
        std::env::var("INVISIBLE_SERVER_TOKEN").unwrap_or_default()
    } else {
        std::env::var("INVISIBLE_DASHBOARD_TOKEN").unwrap_or_default()
    }
}

pub async fn run_bridge(app: AppHandle) {
    let mut backoff_idx: usize = 0;
    let mut prefer_polling = false;

    loop {
        let base = dashboard_url();
        let token = dashboard_token();

        let result = if prefer_polling {
            poll_loop(&app, &base, &token).await
        } else {
            sse_loop(&app, &base, &token).await
        };

        match result {
            Ok(()) => {
                // Either path returned cleanly (shouldn't normally happen).
                backoff_idx = 0;
            }
            Err(BridgeError::SseNotSupported) => {
                if !prefer_polling {
                    info!("invisible-dashboard does not expose /api/stream (404); falling back to polling");
                }
                prefer_polling = true;
                backoff_idx = 0; // immediate switch to polling, no backoff
                continue;
            }
            Err(BridgeError::Transient(msg)) => {
                let wait = BACKOFF_STEPS[backoff_idx.min(BACKOFF_STEPS.len() - 1)];
                warn!("dashboard bridge: {msg}; retry in {:?}", wait);
                tokio::time::sleep(wait).await;
                backoff_idx = backoff_idx.saturating_add(1).min(BACKOFF_STEPS.len() - 1);
            }
        }
    }
}

enum BridgeError {
    SseNotSupported,            // 404 on /api/stream → switch to polling
    Transient(String),          // any other failure → backoff + retry
}

async fn sse_loop(app: &AppHandle, base: &str, token: &str) -> Result<(), BridgeError> {
    let url = format!("{base}/api/stream");
    let client = reqwest::Client::builder()
        .build()
        .map_err(|e| BridgeError::Transient(format!("client build: {e}")))?;

    let mut req = client.get(&url).header("Accept", "text/event-stream");
    if !token.is_empty() { req = req.header("Authorization", format!("Bearer {token}")); }

    let resp = req.send().await
        .map_err(|e| BridgeError::Transient(format!("sse connect: {e}")))?;

    if resp.status().as_u16() == 404 {
        return Err(BridgeError::SseNotSupported);
    }
    if !resp.status().is_success() {
        return Err(BridgeError::Transient(format!("sse http {}", resp.status())));
    }

    let mut stream = resp.bytes_stream().eventsource();
    while let Some(event) = stream.next().await {
        match event {
            Ok(ev) => {
                let payload: Value = serde_json::from_str(&ev.data).unwrap_or(Value::String(ev.data.clone()));
                let _ = app.emit("dashboard:event", serde_json::json!({
                    "source": "sse",
                    "event":  ev.event,
                    "id":     ev.id,
                    "payload": payload,
                }));
            }
            Err(e) => return Err(BridgeError::Transient(format!("sse parse: {e}"))),
        }
    }
    Err(BridgeError::Transient("sse stream ended".into()))
}

async fn poll_loop(app: &AppHandle, base: &str, token: &str) -> Result<(), BridgeError> {
    let url = format!("{base}/api/projects");
    let client = reqwest::Client::new();
    let mut last_hash: Option<u64> = None;
    loop {
        let mut req = client.get(&url);
        if !token.is_empty() { req = req.header("Authorization", format!("Bearer {token}")); }
        match req.send().await {
            Ok(resp) if resp.status().is_success() => {
                let body = resp.text().await.unwrap_or_default();
                let h = hash_str(&body);
                if Some(h) != last_hash {
                    let payload: Value = serde_json::from_str(&body).unwrap_or(Value::String(body));
                    let _ = app.emit("dashboard:event", serde_json::json!({
                        "source":   "poll",
                        "endpoint": "/api/projects",
                        "payload":  payload,
                    }));
                    last_hash = Some(h);
                }
            }
            Ok(resp) => {
                warn!("poll {} → {}", url, resp.status());
            }
            Err(e) => {
                warn!("poll {}: {}", url, e);
                return Err(BridgeError::Transient("poll error".into()));
            }
        }
        tokio::time::sleep(POLL_INTERVAL).await;
    }
}

fn hash_str(s: &str) -> u64 {
    use std::hash::{Hasher, BuildHasher};
    let mut h = std::collections::hash_map::DefaultHasher::new();
    std::hash::Hasher::write(&mut h, s.as_bytes());
    h.finish()
}
```
Notes on this implementation:
  - `DefaultHasher::write` is sufficient — we're not cryptographically hashing, just comparing for change-detection within one process.
  - The polling path emits ONLY on body change (`Some(h) != last_hash`); this prevents the frontend from being woken every 5s with the same payload.
  - The SSE path emits per-event regardless of payload — that's the whole point of SSE.
  - All errors are tracing::warn!'d; nothing panics.

Step 4 — Wire the bridge spawn into `src-tauri/src/lib.rs` `.setup()` closure (after the tray + close-to-hide blocks from Task 3):
```rust
let app_handle = app.handle().clone();
tauri::async_runtime::spawn(async move {
    crate::sse::run_bridge(app_handle).await;
});
```
The `run_bridge` future is `loop { ... }` — it never returns. `tauri::async_runtime::spawn` returns a JoinHandle we deliberately drop; the task lives until the app exits.

Step 5 — Compile + manual smoke:
  - `cd src-tauri && cargo build` — must succeed.
  - Start Vite + Tauri dev. With `invisible-dashboard` NOT running, open the Tauri DevTools console:
    ```js
    const unl = await window.__TAURI__.event.listen('dashboard:event', e => console.log('rx:', e.payload));
    ```
    The console should remain quiet (no errors, no spam). After 1-10 seconds, Rust logs should show "dashboard bridge: ... retry in ..." messages in the `/tmp/tauri-dev.log` file (or stderr, depending on how `cargo tauri dev` was invoked). The Tauri window remains usable.
  - In another terminal, start the dashboard daemon: `INVISIBLE_DASHBOARD_TOKEN=devtoken bin/invisible-dashboard --no-auth &`. Within ~10s, Rust logs should report 404 on `/api/stream` (it's not implemented) and switch to polling. Within ~15s, the DevTools console should log a `dashboard:event` payload with `source: "poll"` and an `/api/projects` JSON body.
  - Run `unl();` in the DevTools console to detach the listener (sanity-check `subscribeDashboard`'s unsubscribe shape works the same way Phase 2's lib uses it).
  - Stop the dashboard daemon. Within one poll cycle, the Rust logs should show poll errors; the Tauri window remains usable.

Do NOT modify any `.jsx` file in `frontend-vite/src/` or any file in `frontend/`, `bin/`, `lib/`. The only frontend-vite changes are: `package.json` (one dep added), `pnpm-lock.yaml` (re-generated), and the NEW file `src/lib/tauri.js`.
  </action>
  <verify>
    <automated>source "$HOME/.cargo/env" 2>/dev/null || true && cd /Users/ace/.invisible-ws/tauri-shell && grep -q '"@tauri-apps/api"' frontend-vite/package.json && test -f frontend-vite/src/lib/tauri.js && grep -q "dashboard:event" frontend-vite/src/lib/tauri.js && grep -q "subscribeDashboard" frontend-vite/src/lib/tauri.js && grep -q "isTauri" frontend-vite/src/lib/tauri.js && test "$(git status --porcelain frontend-vite/src/ | grep -E '\\.jsx$' | wc -l | tr -d ' ')" = "0" && cd src-tauri && grep -q "pub async fn run_bridge" src/sse.rs && grep -q "Eventsource" src/sse.rs && grep -q "dashboard:event" src/sse.rs && grep -q "INVISIBLE_SERVER_URL" src/sse.rs && grep -q "127.0.0.1:8765" src/sse.rs && grep -q "BridgeError::SseNotSupported" src/sse.rs && grep -q "/api/projects" src/sse.rs && grep -q "tauri::async_runtime::spawn" src/lib.rs && grep -q "sse::run_bridge" src/lib.rs && cargo build 2>&1 | tail -3 && cargo check --message-format=short 2>&1 | grep -E "^error" | wc -l | awk '{ exit ($1 == 0) ? 0 : 1 }'</automated>
  </verify>
  <done>
    `src-tauri/src/sse.rs` implements `run_bridge(AppHandle)` with SSE-first / poll-fallback behavior, exponential backoff capped at 10s, and emits `dashboard:event` on the Tauri event bus. `src-tauri/src/lib.rs` spawns the bridge in `.setup()`. `frontend-vite/src/lib/tauri.js` exports `isTauri`, `tauriInvoke`, `subscribeDashboard` — no `.jsx` files modified. `frontend-vite/package.json` adds `@tauri-apps/api@^2`. `cargo build` succeeds. With the dashboard daemon down, the app stays usable and logs reconnect attempts; with it running, the bridge auto-falls back to polling and emits events on `/api/projects` changes.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 5: 8-criterion verification (the exact CONTEXT.md verification plan)</name>
  <what-built>
Tasks 1–4 stood up the Tauri 2.x shell: the `src-tauri/` crate compiles and launches, all 5 commands are registered and callable from the DevTools console, the tray + close-to-hide are wired, and the SSE bridge runs in a tokio task with polling fallback. Before declaring Phase 2 done, the user must walk through the canonical 8-step verification from CONTEXT.md and confirm each passes.
  </what-built>
  <how-to-verify>
Run each step in order. Start in `/Users/ace/.invisible-ws/tauri-shell/` with `source "$HOME/.cargo/env"` already done in the shell.

**Step 1 — `cargo tauri dev` launches with HMR.**
  - Terminal A: `cd frontend-vite && pnpm dev` — wait for `Local: http://localhost:5173/`.
  - Terminal B: `cd src-tauri && cargo tauri dev` — within ~10s a native window opens showing the React UI sidebar + first page.
  - Sidebar: all 8 pages (Dashboard, Focus, Folders, Relations, Terminals, Tools, Calendar, Analytics) appear, click each — they render.

**Step 2 — HMR works.**
  - Edit `frontend-vite/src/pages/Dashboard.jsx`: add `console.log('hmr-test');` near the top of the default export. Save.
  - The Tauri window's Dashboard tab reloads its module without a full window reload. The DevTools console (Cmd+Opt+I) prints `hmr-test`. Revert the edit.

**Step 3 — `list_projects` invokes successfully.**
  - In DevTools console: `await window.__TAURI__.core.invoke('list_projects')`.
  - Returns an array (may be empty on a fresh worktree; that's fine). MUST not throw.

**Step 4 — `status` invokes successfully.**
  - In DevTools console: `await window.__TAURI__.core.invoke('status')`.
  - Returns a `{projects, fetched_at, source}` object. `source` is either `"invisible-status"` (if that CLI exists and ran) or `"fallback:invisible-ps"`.

**Step 5 — `tail_log` is defensive.**
  - In DevTools: `await window.__TAURI__.core.invoke('tail_log', { project: 'nonexistent-xyz', lines: 10 })`.
  - Returns `""` (empty string). Does NOT throw. This is the canary that confirms the cross-platform path resolution + missing-file handling work.

**Step 6 — Close-to-hide + tray.**
  - Click the main window's red close dot (or Cmd-W). The window disappears.
  - The tray icon (a small 'i' glyph) is visible in the macOS menubar.
  - Click the tray icon. The menu shows: Open, Hide, Quit.
  - Click "Open" — the window reappears in the same position.
  - Click "Hide" via the tray — window hides again.
  - Click "Quit" — the app exits, tray icon disappears, Cargo dev process terminates.

**Step 7 — SSE/poll bridge emits events.**
  - Restart `cargo tauri dev`. Wait for the window.
  - Terminal C: `INVISIBLE_DASHBOARD_TOKEN=devtoken bin/invisible-dashboard --no-auth &` (the daemon serves on 127.0.0.1:8765 without auth in this mode).
  - In the Tauri DevTools console:
    ```js
    window.__TAURI__.event.listen('dashboard:event', e => console.log('rx:', e.source ?? e.payload?.source, e.payload));
    ```
  - Within ~15s, the first `dashboard:event` appears. Check `/tmp/tauri-dev.log` (or wherever the Rust logs go); it should contain the line "invisible-dashboard does not expose /api/stream (404); falling back to polling".
  - Optional: trigger a state change. Easiest: `touch ~/.invisible/worktrees/jobslayer/feature/.invisible-checkpoint.json` (if that project exists) or just hit `curl -s http://127.0.0.1:8765/api/projects > /dev/null`. The next polling tick (≤5s) should fire ANOTHER `dashboard:event` with `source: "poll"`.

**Step 8 — Resilience when the daemon is down.**
  - Kill `invisible-dashboard` (`pkill -f invisible-dashboard`).
  - The Tauri window stays open; no error dialog; no crash. The console may log poll-error warnings but the UI remains interactive (try clicking sidebar items — they switch pages normally).
  - The Rust logs should show backoff messages (`retry in 1s`, then `2s`, then `5s`, then `10s` caps).

**Pass criteria for this checkpoint:** all 8 steps above succeed exactly. Capture any anomalies — even if the criterion passes — for the SUMMARY (e.g. "Step 6: dock icon stayed bouncing after Quit; macOS behavior").
  </how-to-verify>
  <resume-signal>Type "approved" if all 8 verification steps from CONTEXT.md pass; otherwise list the specific step + observed behavior + screenshot/log excerpt and the executor will fix and re-run this checkpoint.</resume-signal>
</task>

<task type="auto" tdd="false">
  <name>Task 6: Docs + commits (README section, CHANGELOG regenerate, git commit)</name>
  <files>
    README.md,
    CHANGELOG.md
  </files>
  <action>
After Task 5 passes, finalise the docs and commit the phase.

Step 1 — Add a new section to `README.md` after the "Surfaces" list (where `invisible-app` is described). Title it "Tauri shell (Phase 2)". Two short paragraphs:
  - Paragraph 1: Where the code lives (`src-tauri/`), how to develop (`cd src-tauri && cargo tauri dev`, requires the Vite dev server on 5173 — covered by `beforeDevCommand`), how to build a local `.app` (`cargo tauri build` — produces `target/release/bundle/macos/Invisible.app`).
  - Paragraph 2: Status caveats. The Tauri shell is in "preview" — `bin/invisible-app` (pywebview) is still the default for now and remains functional. Phase 3 will produce signed `.msi` for Windows, code-sign macOS, and wire the auto-updater. Mention that the Tauri shell exposes the same 5 CLI commands plus an SSE bridge that polls `/api/projects` when `/api/stream` is unavailable.
  - Do NOT mark `invisible-app` deprecated yet — that's a Phase 3 step per the workstream ROADMAP. Keep the existing pywebview description intact and add the Tauri section after it.

Step 2 — Verify the CHANGELOG generator picks up the new commits. The script is `scripts/update-changelog.py` (verified read-only earlier). Run it:
  ```bash
  cd /Users/ace/.invisible-ws/tauri-shell && python3 scripts/update-changelog.py
  ```
  This rewrites the block between `<!-- BEGIN AUTOGENERATED -->` and `<!-- END AUTOGENERATED -->` in `CHANGELOG.md` based on conventional-commits parsed from `git log`. The commits made during Tasks 1-5 should produce entries under "Unreleased" → "Features" / "Build" sections. If no commits exist yet (because the executor batched into one big commit at the end), this script will simply re-emit whatever's there — that's fine; commit messages from Step 4 below will be picked up when re-run.

Step 3 — Sanity gates before commit:
  - `git status` — list the touched files. Expected: src-tauri/* (all new), frontend-vite/package.json + pnpm-lock.yaml + src/lib/tauri.js, README.md, CHANGELOG.md. NOT expected: anything under `frontend/`, `bin/`, `lib/`, `frontend-vite/src/*.jsx`. If anything outside the allowed set is staged, revert it.
  - `git diff --stat frontend-vite/src/*.jsx 2>&1 | tail -1` — must report no files (no .jsx changes).
  - `cd src-tauri && cargo build` once more — must succeed; warnings are fine.

Step 4 — Commit (Conventional Commits, scope = the workstream phase identifier):
  ```bash
  cd /Users/ace/.invisible-ws/tauri-shell
  git add src-tauri/ \
          frontend-vite/package.json \
          frontend-vite/pnpm-lock.yaml \
          frontend-vite/src/lib/tauri.js \
          README.md \
          CHANGELOG.md
  git commit -m "feat(INV-02): tauri shell — commands, tray, close-to-hide, sse bridge

  Standup of the Tauri 2.x native shell loading frontend-vite/dist/.

  - 5 Tauri commands: list_projects, run_orchestrator, kill_run, tail_log, status
  - System tray (Open / Hide / Quit) with template image
  - WindowEvent::CloseRequested → window.hide() + api.prevent_close()
  - SSE bridge tries /api/stream first, falls back to polling /api/projects
    on 404 with exponential backoff (1s → 10s cap)
  - Capability allow-list restricts shell execution to the 4 invisible-* CLIs
  - identifier: com.theprofitplatform.invisible
  - frontendDist: ../frontend-vite/dist; devUrl: http://localhost:5173

  Phase 3 (msi cross-compile, code-signing, auto-updater, pywebview
  deprecation) is its own PLAN."
  ```
  Do NOT push (the user pushes when ready). Do NOT use --no-verify (the pre-push hook in `.githooks/` is intentional).

Step 5 — Re-run the changelog generator one more time so it captures the commit just made, then amend the CHANGELOG into a separate follow-up commit so the feat commit stays focused:
  ```bash
  python3 scripts/update-changelog.py
  git status --porcelain CHANGELOG.md
  ```
  If CHANGELOG.md is modified, `git add CHANGELOG.md && git commit -m "docs(INV-02): regenerate CHANGELOG"`. If not, skip.

Step 6 — Print a one-screen completion summary to stdout listing:
  - Files created (count + total size of src-tauri/src/).
  - The exact `cargo --version`, `cargo tauri --version`, `tauri = ...` Cargo dep version resolved in `Cargo.lock`.
  - Any deltas observed during Task 5 verification (steps 1-8).
  - That Phase 3 is unblocked.
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/tauri-shell && grep -qi "tauri shell" README.md && grep -q "src-tauri" README.md && grep -q "cargo tauri dev" README.md && test -f src-tauri/target/debug/invisible-tauri && test "$(git status --porcelain frontend/ 2>/dev/null | wc -l | tr -d ' ')" = "0" && test "$(git status --porcelain bin/ lib/ 2>/dev/null | wc -l | tr -d ' ')" = "0" && test "$(git diff HEAD~3..HEAD --name-only -- 'frontend-vite/src/*.jsx' 2>/dev/null | wc -l | tr -d ' ')" = "0" && git log --oneline -5 | grep -qE "INV-02|tauri shell"</automated>
  </verify>
  <done>
    `README.md` has a "Tauri shell (Phase 2)" section with the dev/build incantations and a Phase 3 status note; `CHANGELOG.md` regenerated via `scripts/update-changelog.py`; commit `feat(INV-02): tauri shell ...` exists; `frontend/`, `bin/`, `lib/`, `frontend-vite/src/*.jsx` are unchanged across this phase's commits. The 4 ROADMAP success criteria for Phase 2 are demonstrably true (Task 5 checkpoint confirmed each one).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| cargo / crates.io → src-tauri/target | Third-party Rust code compiled and linked into the local binary; transitive deps run at compile time |
| Tauri webview (WKWebView on macOS) → Rust core | The frontend invokes Rust commands via `invoke('cmd', args)`; user-controlled args reach the shell plugin and the filesystem |
| Tauri shell plugin → `invisible-*` binaries | Rust shells out to four CLI tools on the user's PATH; if PATH is hostile, lookup hits attacker-controlled binaries |
| invisible-dashboard daemon (HTTP) → Tauri SSE bridge | Untrusted-by-default JSON payloads parsed by serde_json and re-emitted on the Tauri event bus to the React app |
| Filesystem → `tail_log` | Reads `~/.invisible/logs/*.log`; the path is user-controlled (the `project` arg) — naïve interpolation would allow path traversal |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-INV02-01 | **Tampering** | The 5 Tauri commands shelling out to `invisible-*` binaries (`run_orchestrator`, `kill_run`, `list_projects`, `status`) | **mitigate** | Capability allow-list in `src-tauri/capabilities/default.json` enumerates exactly `invisible-status`, `invisible-review`, `invisible-ps`, `invisible-log` — no wildcards, no `shell:allow-spawn` for arbitrary commands. The `args[].validator: "\\S+"` regex blocks empty/whitespace args; further argument validation (e.g. rejecting `..` in `project`) happens in Task 2's tail_log implementation, which uses `PathBuf::file_name()` to strip directory components before joining onto `~/.invisible/logs/`. |
| T-INV02-02 | **Information disclosure** | `tail_log(project, lines)` path traversal | mitigate | The command joins `${INVISIBLE_HOME}/logs/<project>.log` directly; the executor in Task 2 MUST sanitise `project` by extracting only the last path component (`PathBuf::file_name()`) and forbidding empty/dot strings. Bug: if not done, `tail_log("../../etc/passwd", 10)` would read outside the logs dir. This mitigation is part of the Task 2 acceptance — verify in the SUMMARY. |
| T-INV02-03 | **Denial of service** | `tail_log` with `lines = u32::MAX` | mitigate | `lines` is clamped to `[1, 10_000]` inside the command before any allocation; explicitly listed in the Task 2 `<behavior>` test cases. |
| T-INV02-04 | **Elevation of privilege** | `withGlobalTauri: true` exposes `window.__TAURI__.core.invoke` to ALL frame contexts in the webview | accept | The webview only loads `localhost:5173` (dev) or `tauri://localhost` (prod, from the bundled dist). Both are first-party origins. No external URLs are navigated to from `App.jsx`. Phase 3 will revisit this flag and consider switching to import-only access. |
| T-INV02-05 | **Tampering** | invisible-dashboard / invisible-server SSE payloads parsed by `eventsource-stream` + `serde_json` and re-emitted on the Tauri event bus | mitigate | Both daemons bind to 127.0.0.1 by default (verified in `bin/invisible-dashboard:344` and `bin/invisible-server` defaults); when `$INVISIBLE_SERVER_URL` points to a remote daemon, the bridge sends the bearer token from `$INVISIBLE_SERVER_TOKEN` over HTTPS (assumed; TLS termination is the VPS sysadmin's responsibility — Phase 3 may add a strict-TLS toggle). Parse failures (`serde_json::from_str`) fall back to `Value::String(raw)` so a malformed payload cannot crash the bridge; nothing in the payload is evaluated as code on the Rust side. |
| T-INV02-06 | **Repudiation** | Spawned `invisible-review` processes outlive the Tauri app (started by `run_orchestrator`) | accept | This is the existing design: orchestrator runs are long-lived and survive UI restarts. The Tauri app does not promise to manage their lifecycle beyond `kill_run`. Phase 3 may add a "kill all on quit" tray option. |
| T-INV02-07 | **Spoofing** | A user setting `$PATH` to include a hostile directory before `invisible-*` could intercept the shell-out | accept | This is the standard CLI threat model and applies equally to `bin/invisible-app` today. Mitigation requires absolute paths to the binaries (e.g. `/usr/local/bin/invisible-review`), which conflicts with development workflows (the user runs from a venv / homebrew / a checkout). Phase 3 may add an absolute-path configuration in `tauri.conf.json`. |
| T-INV02-SC | **Tampering** | crates.io installs: tauri, tauri-plugin-shell, tauri-build, reqwest, eventsource-stream, tokio, serde, serde_json, futures-util, dirs, anyhow, tracing, tracing-subscriber | mitigate | Package legitimacy audit (cargo / crates.io): tauri + tauri-build + tauri-plugin-shell published by tauri-apps org (10M+ DL each); reqwest + tokio + futures-util + serde + serde_json by seanmonstar / Tokio team / dtolnay (the canonical async-ecosystem packages — billions of downloads); eventsource-stream by jpopesculian, 1M+ DL, used by reqwest-eventsource downstream; dirs by soc, 200M+ DL; anyhow + tracing by dtolnay / tokio-rs. All canonical, no `[ASSUMED]` or `[SUS]`. `Cargo.lock` is gitignored (matches `.gitignore` line "src-tauri/Cargo.lock") so the lockfile is per-checkout — Phase 3 may revisit this for reproducibility. No human-verify checkpoint required for the `cargo add` step. |
</threat_model>

<verification>
Full-phase verification (run from `/Users/ace/.invisible-ws/tauri-shell/`):

```bash
# 0. Toolchain
source "$HOME/.cargo/env" || true
cargo --version | grep -q "1\\.95\\|1\\.9[6-9]\\|2\\." \
  && cargo tauri --version | grep -q "tauri-cli 2\\." \
  || { echo "toolchain check failed"; exit 1; }

# 1. src-tauri tree exists with the required files
test -f src-tauri/Cargo.toml \
  && test -f src-tauri/build.rs \
  && test -f src-tauri/tauri.conf.json \
  && test -f src-tauri/capabilities/default.json \
  && test -f src-tauri/src/main.rs \
  && test -f src-tauri/src/lib.rs \
  && test -f src-tauri/src/commands.rs \
  && test -f src-tauri/src/sse.rs \
  && ls src-tauri/icons/*.png src-tauri/icons/*.ico src-tauri/icons/*.icns >/dev/null

# 2. Config locked to Phase 2 values
grep -q '"identifier": "com.theprofitplatform.invisible"' src-tauri/tauri.conf.json
grep -q '"frontendDist": "../frontend-vite/dist"' src-tauri/tauri.conf.json
grep -q '"devUrl": "http://localhost:5173"' src-tauri/tauri.conf.json

# 3. The 5 commands are declared + registered
test "$(grep -c '#\\[tauri::command\\]' src-tauri/src/commands.rs)" -ge 5
for cmd in list_projects run_orchestrator kill_run tail_log status; do
  grep -q "pub async fn $cmd" src-tauri/src/commands.rs || { echo "MISSING $cmd"; exit 1; }
  grep -q "commands::$cmd" src-tauri/src/lib.rs           || { echo "$cmd NOT registered"; exit 1; }
done

# 4. Tray + close-to-hide wired
grep -q "TrayIconBuilder::with_id" src-tauri/src/lib.rs
grep -q "WindowEvent::CloseRequested" src-tauri/src/lib.rs
grep -q "api.prevent_close()" src-tauri/src/lib.rs

# 5. SSE bridge with polling fallback
grep -q "pub async fn run_bridge" src-tauri/src/sse.rs
grep -q "Eventsource" src-tauri/src/sse.rs
grep -q "/api/stream" src-tauri/src/sse.rs
grep -q "/api/projects" src-tauri/src/sse.rs
grep -q "BridgeError::SseNotSupported" src-tauri/src/sse.rs
grep -q "tauri::async_runtime::spawn" src-tauri/src/lib.rs

# 6. Capability allow-list restricts shell scope
grep -q "shell:allow-execute" src-tauri/capabilities/default.json
grep -q "invisible-status" src-tauri/capabilities/default.json
grep -q "invisible-review" src-tauri/capabilities/default.json
grep -q "invisible-ps"     src-tauri/capabilities/default.json
grep -q "invisible-log"    src-tauri/capabilities/default.json

# 7. Cross-platform path handling — no hardcoded /Users/...
test "$(grep -REn '/Users/[a-z]+/' src-tauri/src 2>/dev/null | grep -v '^#' | wc -l | tr -d ' ')" = "0"

# 8. Frontend additive-only
test -f frontend-vite/src/lib/tauri.js
grep -q '"@tauri-apps/api"' frontend-vite/package.json
test "$(git status --porcelain frontend-vite/src/ | grep -E '\\.jsx$' | wc -l | tr -d ' ')" = "0"

# 9. Compile + smoke
(cd src-tauri && cargo build) | tail -3

# 10. No-touch zones
test "$(git status --porcelain frontend/ bin/ lib/ 2>/dev/null | wc -l | tr -d ' ')" = "0"
```

Manual (covered by Task 5 checkpoint): the 8-step verification from CONTEXT.md (dev launch, HMR, all 5 commands invoked, tray Open/Hide/Quit, close-to-hide, SSE→poll fallback with dashboard up, graceful degradation with dashboard down).
</verification>

<success_criteria>
All four ROADMAP success criteria for Phase 2 satisfied:

1. ✓ `cd src-tauri && cargo tauri dev` launches the app, loads the Vite dev server (5173) into a native window, hot-reload works (Task 5 steps 1+2).
2. ✓ The 5 Tauri commands exist and are invokable from the DevTools console: `list_projects`, `run_orchestrator(project, task?)`, `kill_run(project)`, `tail_log(project, lines)`, `status` (Task 5 steps 3-5).
3. ✓ System tray with Open / Hide / Quit menu items; closing the main window hides it (Task 5 step 6).
4. ✓ SSE bridge from `invisible-dashboard` (or `invisible-server` when $INVISIBLE_SERVER_URL is set) to the Tauri event bus, with graceful polling fallback when `/api/stream` returns 404 and exponential-backoff resilience when the daemon is down (Task 5 steps 7-8).

Plus:
- ✓ `frontend/`, `bin/`, `lib/`, `bin/invisible-app` all unchanged.
- ✓ `frontend-vite/src/*.jsx` files unchanged — Tauri integration is in the NEW lib at `frontend-vite/src/lib/tauri.js`.
- ✓ Identifier is `com.theprofitplatform.invisible`; `frontendDist: ../frontend-vite/dist`; `devUrl: http://localhost:5173`.
- ✓ Capability allow-list restricts shell execution to the 4 enumerated `invisible-*` binaries — no broader scope.
- ✓ All paths cross-platform via `dirs::home_dir()` or `$INVISIBLE_HOME` — no `/Users/ace` strings in `src-tauri/src/`.
- ✓ No backend daemon coupling: app launches and renders even with `invisible-dashboard` not running; backoff retries with no crash dialog.

Phase 3 (`.msi` cross-compile, code-signing, auto-updater, pywebview deprecation) is intentionally NOT in scope here — it gets its own PLAN.md after this phase ships.
</success_criteria>

<output>
Create `.planning/workstreams/tauri-shell/phases/INV-02-tauri-shell/INV-02-01-SUMMARY.md` when done. Include:
- Final list of files created under `src-tauri/` (with byte counts for sanity) + the 3 frontend-vite touches + README/CHANGELOG.
- The exact `tauri`, `tauri-plugin-shell`, `tauri-build`, `reqwest`, `eventsource-stream` versions resolved in `src-tauri/Cargo.lock` (paste from `cargo tree --depth 0` output).
- Any deviations from the plan (e.g. if the capability schema needed adjustment because Tauri 2.11 expects a different `cmd` shape — paste the corrected JSON if so).
- Per-step notes from the Task 5 verification: which of the 8 criteria passed cleanly, which had observations (e.g. "step 6 — dock icon stays bouncing after Quit; cosmetic; Phase 3 to address").
- The DevTools console outputs for `list_projects`, `status`, and `tail_log('nonexistent', 10)` (paste verbatim).
- One paragraph confirming Phase 3 is unblocked: the `src-tauri/` tree is ready for `cargo tauri build --target x86_64-pc-windows-msvc` (after Phase 3 wires the cross-compile prerequisites).
</output>
