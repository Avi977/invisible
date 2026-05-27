# START HERE — workstream: tauri-shell

You are one of **6 parallel Claude sessions** working on the `invisible`
app. Your scope is bounded — but the GOOD news is **this workstream is
fully isolated**: new directories (`src-tauri/`, `frontend-vite/`), no
edits to existing files. Zero merge conflicts.

## Your phase (3 sub-phases — biggest workstream)

**Migrate the frontend from Babel-standalone to a production Vite build,
then wrap it in a Tauri 2.x shell, then cross-compile a Windows `.msi`.**

The existing `frontend/` and `bin/invisible-app` (pywebview) stay working
until the cutover at the END of your phase 3.

Full spec: [`.planning/workstreams/tauri-shell/ROADMAP.md`](.planning/workstreams/tauri-shell/ROADMAP.md)

## World state you can assume

- **Main repo:** `~/.invisible` on `main`. This worktree: `ws/tauri-shell`.
- **Current frontend (your starting point):** `frontend/*.jsx` — Babel-standalone, serving on `http://127.0.0.1:8090/` via `invisible-frontend`.
- **Don't break the existing frontend.** Keep `frontend/` operational until your Phase 3 cutover. Build the new pipeline in `frontend-vite/` and `src-tauri/`.
- **Rust toolchain:** check with `rustc --version`. If not installed: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
- **Tauri prereqs (macOS):** Xcode CLT (`xcode-select --install`). Tauri 2.x: `cargo install tauri-cli --version "^2.0"`
- **Node:** `node --version` (≥18). If needed: `nvm use 22` (you already have nvm).
- **pnpm:** `pnpm --version`. If missing: `npm i -g pnpm`
- **GSD active workstream:** `tauri-shell`

## Required reads

1. `.planning/PROJECT.md`
2. `.planning/REQUIREMENTS.md` — REQ-06 is yours
3. `.planning/workstreams/tauri-shell/ROADMAP.md` — has THREE sub-phases
4. `frontend/index.html`, `frontend/app.jsx`, `frontend/data.jsx`, `frontend/styles.css` — the source you're porting
5. `frontend/pages/*.jsx` — eight pages to bring over identically
6. `bin/invisible-app` — pywebview wrapper (the thing you're replacing)

## Files you OWN

- `src-tauri/` — new Rust + Tauri project (you create)
- `frontend-vite/` — new Vite + React 18 project (you create)

## Files you EDIT LIGHTLY (only at end of Phase 3)

- `README.md` (mark pywebview deprecated; add Tauri install/build instructions)
- `ROADMAP.md` (project-level) — tick Phase 3
- `.gitignore` — verify `src-tauri/target/`, `frontend-vite/node_modules/`, `frontend-vite/dist/` covered

## Files you MUST NOT TOUCH

- `frontend/` — current frontend must keep working until cutover at end of your Phase 3.
- `bin/invisible-app` — keep operational; mark deprecated only in README.
- Any `lib/*.py`, `bin/invisible-*` other than the README edit. Sibling workstreams own all those.

## First action

```
/gsd:plan-phase 1
```

## Verify each sub-phase

```bash
# Phase 1: Vite migration done
cd frontend-vite && pnpm dev   # http://localhost:5173 should match 8090

# Phase 2: Tauri shell done
cd src-tauri && cargo tauri dev

# Phase 3: Cross-compile + package done
cd src-tauri && cargo tauri build --target x86_64-pc-windows-msvc
ls src-tauri/target/release/bundle/msi/*.msi
```

## When done

```
/gsd:ship
```
