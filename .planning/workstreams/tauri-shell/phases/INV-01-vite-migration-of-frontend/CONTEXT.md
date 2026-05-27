# Phase 1: Vite migration of frontend — CONTEXT

## Goal (verbatim from ROADMAP)

Move the JSX from `frontend/*.jsx` (Babel-standalone) into a `frontend-vite/`
Vite project. Same components, same styles, same visual — production build
pipeline replaces in-browser compilation.

## Success criteria (verbatim from ROADMAP)

1. `frontend-vite/` is a Vite + React 18 + TypeScript-optional project.
2. Every file in `frontend/` has a Vite-compatible equivalent under `frontend-vite/src/`.
3. `pnpm dev` (in `frontend-vite/`) launches the dev server on 5173 with hot reload; all 8 pages render identically to the Babel-standalone version on 8090.
4. `pnpm build` produces a static `dist/` that Tauri can bundle.

## Inputs — what exists today

`frontend/` is a static React app served by `bin/invisible-frontend` at
`http://127.0.0.1:8090/`. It uses:

- React 18.3.1 + ReactDOM (UMD from unpkg)
- `@babel/standalone` 7.29.0 to compile JSX in-browser
- Geist + Geist Mono fonts from Google Fonts
- Single `styles.css` (~56 KB) with CSS custom properties for theming
- Files (each is `text/babel` script-tag included by `index.html`):
  - `index.html` — entry shell
  - `tweaks-panel.jsx` — config panel + global state hook
  - `icons.jsx` — icon library
  - `data.jsx` — mock data sets (DATA_SETS) + ~28 KB
  - `ai-chat.jsx` — floating chat bubble UI
  - `app.jsx` — sidebar + router + main shell
  - `pages/dashboard.jsx`, `pages/focus.jsx`, `pages/folders.jsx`,
    `pages/relations.jsx`, `pages/terminals.jsx`, `pages/tools.jsx`,
    `pages/calendar.jsx`, `pages/analytics.jsx`

Each page-component exposes itself on `window` (e.g. `window.Dashboard = Dashboard`)
because the script-tag concatenation model has no module system. The Vite
migration replaces that with explicit ES module imports/exports.

There are exactly two `/*EDITMODE-BEGIN*/.../*EDITMODE-END*/` markers in
`app.jsx` (DEFAULTS object) and in `tweaks-panel.jsx`. These are Claude
Design's live-editing markers; safe to leave as plain comments.

## Toolchain prereqs

| Tool | State | Action |
|------|-------|--------|
| node | v22.14 ✓ | none |
| pnpm | missing | `npm i -g pnpm` OR `corepack enable && corepack prepare pnpm@latest --activate` |
| rustc | missing | NOT needed for Phase 1. Phase 2 installs via rustup. |
| cargo tauri | missing | NOT needed for Phase 1. |

## Constraints

- **Visual parity is non-negotiable.** Open `http://127.0.0.1:8090/` and `http://127.0.0.1:5173/` side-by-side; they should be pixel-identical across all 8 pages.
- **Same styles.css.** Don't refactor it. Drop the existing file verbatim into the Vite project; only fix import paths.
- **Same component logic.** Port JSX → JSX without behavior changes. Adding TypeScript is permitted but optional — start with JSX, migrate later.
- **No build-time JSX compilation in the legacy frontend.** Don't touch `frontend/`. The Vite project lives at `frontend-vite/` only.
- **Tauri-ready output.** `pnpm build` must produce a static `dist/` with relative asset paths (Vite's `base: './'` config) so Tauri's bundler can pick it up unchanged in Phase 2.
- **Production stack picks:**
  - Vite 5.x
  - React 18.3.1 (exact match to current frontend)
  - vite-plugin-react (SWC) for fast HMR
  - No router yet (current frontend uses internal page state in `app.jsx`)
  - No state lib yet (current frontend uses `useState` hooks)

## Module-system migration map

The legacy frontend exposes globals on `window`. The migration must:

1. Convert each `window.Foo = Foo` (e.g. `window.App = App`) to `export default Foo`.
2. Replace each script-tag include in `index.html` with `import` in the corresponding consumer file.
3. Lift the singleton React-hook globals (`useState as useStateApp` aliases) — they were workarounds for global scope, no longer needed.
4. The Babel-standalone tag in `index.html` goes away entirely.

## Files this phase WRITES

- `frontend-vite/package.json` (new)
- `frontend-vite/pnpm-lock.yaml` (generated)
- `frontend-vite/vite.config.js` (new)
- `frontend-vite/index.html` (new — Vite entry)
- `frontend-vite/src/main.jsx` (new — mounts `<App/>`)
- `frontend-vite/src/App.jsx` (port from `frontend/app.jsx`)
- `frontend-vite/src/Icons.jsx` (port from `frontend/icons.jsx`)
- `frontend-vite/src/Data.jsx` (port from `frontend/data.jsx`)
- `frontend-vite/src/AiChat.jsx` (port from `frontend/ai-chat.jsx`)
- `frontend-vite/src/TweaksPanel.jsx` (port from `frontend/tweaks-panel.jsx`)
- `frontend-vite/src/pages/Dashboard.jsx` (port)
- `frontend-vite/src/pages/Focus.jsx` (port)
- `frontend-vite/src/pages/Folders.jsx` (port)
- `frontend-vite/src/pages/Relations.jsx` (port)
- `frontend-vite/src/pages/Terminals.jsx` (port)
- `frontend-vite/src/pages/Tools.jsx` (port)
- `frontend-vite/src/pages/Calendar.jsx` (port)
- `frontend-vite/src/pages/Analytics.jsx` (port)
- `frontend-vite/src/styles.css` (copied verbatim from `frontend/styles.css`)
- `frontend-vite/.gitignore` (node_modules/, dist/)
- `frontend-vite/README.md` (one-screen: dev/build/integrate-with-tauri)

## Files this phase MUST NOT TOUCH

- `frontend/` — the legacy frontend keeps serving on 8090.
- `bin/invisible-frontend`, `bin/invisible-app`, `bin/invisible-dashboard` — daemons unaffected.
- Anything under `lib/`, `prompts/`, `completions/`.

## Verification plan

1. `cd frontend-vite && pnpm install` succeeds.
2. `pnpm dev` starts; visit `http://localhost:5173/` — all 8 pages render.
3. Visual diff vs `http://localhost:8090/` — pixel-identical at 1200×800 (the pywebview window size).
4. Click through each sidebar entry; check the Tweaks panel still works.
5. `pnpm build` produces `dist/` with `index.html`, hashed JS chunks, hashed CSS, fonts inlined.
6. `python3 -m http.server 5174 -d dist` then visit `http://localhost:5174/` — production bundle renders identically.

## Out of scope (for this phase)

- Tauri shell — Phase 2.
- TypeScript migration — leave for a later refactor.
- Replacing CSS custom properties with Tailwind / CSS modules — leave as-is.
- Code-splitting / route-level lazy-loading — let Vite default behavior win.
- Service-worker / PWA — not needed inside Tauri.
