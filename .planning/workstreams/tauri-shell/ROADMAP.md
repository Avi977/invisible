# Workstream: tauri-shell (Phase 6 of M1)

> Sister-workstreams: dashboard-wiring, ai-bubble, folders-3source,
> terminals-pty, analytics-aggregator. Fully isolated — new directories
> (`src-tauri/`, `frontend-vite/`); current `frontend/` and `bin/invisible-app`
> remain operational until the cutover.

## Phases

- [ ] **Phase 1: Vite migration of frontend** — same components, build pipeline
- [ ] **Phase 2: Tauri shell** — Rust shell + commands wrapping CLI surface
- [ ] **Phase 3: Cross-compile + package** — `.msi` for Windows; `.app` for macOS; tray + auto-update

## Phase Details

### Phase 1: Vite migration of frontend
**Goal**: Move the JSX from `frontend/*.jsx` (Babel-standalone) into a `frontend-vite/` Vite project. Same components, same styles, same visual — production build pipeline replaces in-browser compilation.

**Depends on**: Nothing. Operates entirely in new directories.

**Requirements**: REQ-06 (see `.planning/REQUIREMENTS.md`)

**Success Criteria** (what must be TRUE):
  1. `frontend-vite/` is a Vite + React 18 + TypeScript-optional project.
  2. Every file in `frontend/` has a Vite-compatible equivalent under `frontend-vite/src/`.
  3. `pnpm dev` (in `frontend-vite/`) launches the dev server on 5173 with hot reload; all 8 pages render identically to the Babel-standalone version on 8090.
  4. `pnpm build` produces a static `dist/` that Tauri can bundle.

### Phase 2: Tauri shell
**Goal**: Native Tauri 2.x shell loading the Vite-bundled frontend. Tray with Open / Hide / Quit (parity with pystray today).

**Depends on**: Phase 1 of this workstream.

**Success Criteria** (what must be TRUE):
  1. `cd src-tauri && cargo tauri dev` launches the app, loads the Vite dev server, hot-reload works.
  2. Tauri commands exist for the existing CLI surface: `run_orchestrator(project, task?)`, `kill_run(project)`, `list_projects()`, `tail_log(project, lines)`, `status()`.
  3. System tray with Open / Hide / Quit menu items.
  4. SSE bridge from `invisible-dashboard` (8765) → Tauri event bus → frontend store (so the React app gets push updates).

### Phase 3: Cross-compile + package for Windows
**Goal**: Produce a working `.msi` installable on a fresh Windows 11 box.

**Depends on**: Phase 2 of this workstream.

**Success Criteria** (what must be TRUE):
  1. `cargo tauri build --target x86_64-pc-windows-msvc` produces an `.msi`.
  2. Installed on a clean Windows 11 VM, the app launches, connects to the dashboard daemon (if reachable on `INVISIBLE_SERVER_URL`), and the file dashboard works.
  3. Tauri auto-updater configured against a self-hosted update manifest.
  4. macOS `.app` also produced (`cargo tauri build` on this Mac).
  5. `bin/invisible-app` (pywebview) marked deprecated in README — kept for one milestone before deletion.

## Files this workstream OWNS

- `src-tauri/` (new tree)
- `frontend-vite/` (new tree)

## Files this workstream EDITS LIGHTLY

- `README.md` (mark pywebview deprecated; add Tauri install/build instructions)
- `ROADMAP.md` (project-level) — mark Phase 3 as done once shipped
- `.gitignore` — verify `src-tauri/target/`, `frontend-vite/node_modules/`, `frontend-vite/dist/` are covered

## Files this workstream MUST NOT TOUCH

- `frontend/` — keep operational as the fallback until cutover.
- `bin/invisible-app` — keep functional until deprecation milestone passes.
- Any `lib/api/*` or `bin/invisible-*` script — owned by sibling workstreams.

## Verify locally

```bash
# Phase 1 done
cd frontend-vite && pnpm dev   # http://localhost:5173 should match 8090

# Phase 2 done
cd src-tauri && cargo tauri dev

# Phase 3 done
cd src-tauri && cargo tauri build --target x86_64-pc-windows-msvc
ls src-tauri/target/release/bundle/msi/*.msi
```

## Resume in a fresh Claude session

```bash
cd /Users/ace/.invisible
gsd-sdk query workstream.set tauri-shell --raw --cwd .
# then in Claude:
/gsd:plan-phase 1
```
