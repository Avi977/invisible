---
phase: INV-01-vite-migration-of-frontend
workstream: tauri-shell
plan: 01
status: complete
checkpoint: ~
completed_tasks: [1, 2, 3, 4, 5]
pending_tasks: []
subsystem: frontend-build-pipeline
tags:
  - vite
  - react-18
  - esm-migration
  - babel-standalone-removal
  - tauri-prep
requires:
  - frontend/ (legacy source, read-only)
  - Node >= 18
  - pnpm (provisioned via corepack)
provides:
  - frontend-vite/ — Vite 5 + React 18 project, dev on :5173, build to dist/
  - dist/ — Tauri Phase 2 will consume via `frontendDist: ../frontend-vite/dist`
affects:
  - frontend/ — UNTOUCHED (legacy 8090 still works)
  - bin/, lib/ — UNTOUCHED (sibling-workstream territory)
tech-stack:
  added:
    - vite@5.4.21
    - "@vitejs/plugin-react-swc@3.11.0"
    - react@18.3.1
    - react-dom@18.3.1
  patterns:
    - ES modules (import/export) replace window.* globals
    - Named hook imports (`useState` from 'react') replace `React.useState` destructure aliases
key-files:
  created:
    - frontend-vite/.gitignore
    - frontend-vite/package.json
    - frontend-vite/pnpm-lock.yaml
    - frontend-vite/pnpm-workspace.yaml
    - frontend-vite/vite.config.js
    - frontend-vite/index.html
    - frontend-vite/README.md
    - frontend-vite/src/main.jsx
    - frontend-vite/src/styles.css
    - frontend-vite/src/Icons.jsx
    - frontend-vite/src/Data.jsx
    - frontend-vite/src/AiChat.jsx
    - frontend-vite/src/TweaksPanel.jsx
    - frontend-vite/src/App.jsx
    - frontend-vite/src/pages/Dashboard.jsx
    - frontend-vite/src/pages/Focus.jsx
    - frontend-vite/src/pages/Folders.jsx
    - frontend-vite/src/pages/Relations.jsx
    - frontend-vite/src/pages/Terminals.jsx
    - frontend-vite/src/pages/Tools.jsx
    - frontend-vite/src/pages/Calendar.jsx
    - frontend-vite/src/pages/Analytics.jsx
  modified: []
decisions:
  - "pnpm-workspace.yaml allowBuilds: @swc/core + esbuild — pnpm 11 moved this config out of package.json; without it `pnpm dev` fails on first run because postinstall scripts are ignored by default."
  - "Exported 5 named consts from Data.jsx (DATA_SETS, FOLDERS, TOOL_WORKFLOWS, TERM_CONTEXT, ANALYTICS) instead of just DATA_SETS — pages depend on all 5 because the legacy script-tag model leaked all top-level consts to the global scope."
  - "AiChat.jsx feature-detects `window.claude.complete` and surfaces the identical legacy fallback string `(couldn't reach the model — try again)` when the global is absent (dev mode without Claude Design host)."
  - "Used PascalCase filenames under src/pages/ (Dashboard.jsx not dashboard.jsx) to match App.jsx imports and stay safe on case-sensitive Linux/Windows targets the Tauri bundle will eventually ship to."
metrics:
  duration_minutes: ~
  completed_date: 2026-05-26
  dist_size_kb: 296
  dist_js_kb: 250
  dist_js_gzip_kb: 77
  dist_css_kb: 44
  dist_css_gzip_kb: 8.2
  vite_modules_transformed: 43
  vite_build_ms: 444
---

# Phase INV-01 Plan 01: Vite migration of frontend — Summary

Replaced the in-browser Babel-standalone React build at `frontend/` with a production Vite 5 + React 18.3.1 pipeline at `frontend-vite/`. Same components, same styles, ESM imports instead of `window.X = X` globals, dev server with HMR on :5173, Tauri-ready `dist/` produced via `pnpm build`.

**Status:** All 5 tasks complete. Operator approved visual parity at the Task 4 human-verify checkpoint (1200×800). Production build verified Tauri-ready in Task 5 — `dist/` ships with relative `./assets/` paths. Phase 2 (Tauri shell) is unblocked.

## What's done (Tasks 1-3)

### Task 1 — Bootstrap scaffold (commit `d9dc93f`)

- `frontend-vite/` created with `package.json`, `vite.config.js` (`base: './'`, port 5173), `index.html` (`<script type="module" src="/src/main.jsx">`), `.gitignore`, one-screen `README.md`.
- `src/styles.css` copied byte-for-byte from `frontend/styles.css` (56497 bytes).
- `src/main.jsx` mounts a placeholder; smoke-tested via `pnpm dev`.
- `pnpm install` produced a deterministic `pnpm-lock.yaml`.

### Task 2 — Shared modules ported (commit `f57b943`)

5 shared modules converted from `window.X = X` globals to ES module exports:

| Source                          | Destination                            | Export form                                |
| ------------------------------- | -------------------------------------- | ------------------------------------------ |
| `frontend/icons.jsx`            | `frontend-vite/src/Icons.jsx`          | `export const I`                           |
| `frontend/data.jsx`             | `frontend-vite/src/Data.jsx`           | 5 named: DATA_SETS, FOLDERS, TOOL_WORKFLOWS, TERM_CONTEXT, ANALYTICS |
| `frontend/ai-chat.jsx`          | `frontend-vite/src/AiChat.jsx`         | `export default AIBubble`                  |
| `frontend/tweaks-panel.jsx`     | `frontend-vite/src/TweaksPanel.jsx`    | `export { useTweaks, TweaksPanel, ... }` (12 names) |
| `frontend/app.jsx`              | `frontend-vite/src/App.jsx`            | `export default App`                       |

`main.jsx` updated to mount `<App/>` via `createRoot` + `StrictMode`. EDITMODE markers around `DEFAULTS` in App.jsx preserved verbatim. AiChat preserves the legacy fallback string `(couldn't reach the model — try again)` byte-for-byte.

### Task 3 — Pages ported (commit `25248ff`)

All 8 page modules converted with PascalCase filenames:

| Source                              | Destination                              | Data imports needed     |
| ----------------------------------- | ---------------------------------------- | ----------------------- |
| `frontend/pages/dashboard.jsx`      | `frontend-vite/src/pages/Dashboard.jsx`  | (Icons only)            |
| `frontend/pages/focus.jsx`          | `frontend-vite/src/pages/Focus.jsx`      | (Icons only)            |
| `frontend/pages/folders.jsx`        | `frontend-vite/src/pages/Folders.jsx`    | Icons, FOLDERS          |
| `frontend/pages/relations.jsx`      | `frontend-vite/src/pages/Relations.jsx`  | (Icons only)            |
| `frontend/pages/terminals.jsx`      | `frontend-vite/src/pages/Terminals.jsx`  | Icons, TERM_CONTEXT     |
| `frontend/pages/tools.jsx`          | `frontend-vite/src/pages/Tools.jsx`      | Icons, TOOL_WORKFLOWS   |
| `frontend/pages/calendar.jsx`       | `frontend-vite/src/pages/Calendar.jsx`   | (Icons only)            |
| `frontend/pages/analytics.jsx`      | `frontend-vite/src/pages/Analytics.jsx`  | Icons, ANALYTICS        |

Smoke-tested: `pnpm dev` boots cleanly on :5173, all 12 source modules (5 shared + 8 pages, fetched as `/src/*.jsx`) compile and return HTTP 200 from the Vite transform pipeline. No `Failed to resolve import` errors in the dev log.

## Files created (with byte counts)

| Path                                       | Size (bytes) |
| ------------------------------------------ | -----------: |
| `frontend-vite/package.json`               |          374 |
| `frontend-vite/vite.config.js`             |          245 |
| `frontend-vite/index.html`                 |          559 |
| `frontend-vite/src/main.jsx`               |          233 |
| `frontend-vite/src/styles.css`             |       56,497 |
| `frontend-vite/src/Icons.jsx`              |        6,046 |
| `frontend-vite/src/Data.jsx`               |       25,382 |
| `frontend-vite/src/AiChat.jsx`             |        3,509 |
| `frontend-vite/src/TweaksPanel.jsx`        |       23,844 |
| `frontend-vite/src/App.jsx`                |        9,552 |
| `frontend-vite/src/pages/Dashboard.jsx`    |        6,539 |
| `frontend-vite/src/pages/Focus.jsx`        |       26,650 |
| `frontend-vite/src/pages/Folders.jsx`      |        3,879 |
| `frontend-vite/src/pages/Relations.jsx`    |        7,630 |
| `frontend-vite/src/pages/Terminals.jsx`    |       11,108 |
| `frontend-vite/src/pages/Tools.jsx`        |       12,730 |
| `frontend-vite/src/pages/Calendar.jsx`     |        8,521 |
| `frontend-vite/src/pages/Analytics.jsx`    |       14,170 |
| **Total source**                           | **217,468**  |

Plus `pnpm-lock.yaml` (~auto-generated), `pnpm-workspace.yaml`, `.gitignore`, `README.md`, and `node_modules/`.

## Resolved dependency versions (from pnpm-lock.yaml)

| Package                    | Spec       | Resolved version |
| -------------------------- | ---------- | ---------------- |
| react                      | 18.3.1     | 18.3.1           |
| react-dom                  | 18.3.1     | 18.3.1           |
| vite                       | ^5.4.0     | 5.4.21           |
| @vitejs/plugin-react-swc   | ^3.7.0     | 3.11.0           |

Lockfile is committed; future installs are reproducible.

## Deviations from Plan

### Auto-fixed (Rules 1-3)

1. **[Rule 3 — blocking issue] pnpm 11 build-script approval.**
   - **Found during:** Task 1, first `pnpm install` succeeded but `pnpm dev` failed with `[ERR_PNPM_IGNORED_BUILDS]`. pnpm 11 introduced strict ignored-builds behavior — `pnpm dev` re-runs `pnpm install` as a pre-check and bails if `@swc/core` / `esbuild` postinstall scripts are ignored.
   - **Fix:** Added `frontend-vite/pnpm-workspace.yaml` with `allowBuilds: { '@swc/core': true, esbuild: true }`. PLAN.md mentioned `pnpm-lock.yaml` in `files_modified` but not `pnpm-workspace.yaml` — this is a pnpm-11-specific addition.
   - **Files modified:** `frontend-vite/pnpm-workspace.yaml` (new, 56 bytes).
   - **Commit:** `d9dc93f` (Task 1).

2. **[Rule 2 — auto-add critical functionality] Exported 4 additional Data.jsx consts.**
   - **Found during:** Task 2, while reading `frontend/data.jsx`. The plan specified only `DATA_SETS` but the legacy file declares 5 top-level consts: `DATA_SETS`, `FOLDERS`, `TOOL_WORKFLOWS`, `TERM_CONTEXT`, `ANALYTICS`. Under the legacy script-tag model, all 5 leaked to the global scope; in ESM each needs an explicit export or the pages can't see them.
   - **Affected pages:** Folders (`FOLDERS`), Terminals (`TERM_CONTEXT`), Tools (`TOOL_WORKFLOWS`), Analytics (`ANALYTICS`).
   - **Fix:** Promoted all 5 to `export const`. Without this, 4 of the 8 pages would silently render with `undefined` data.
   - **Files modified:** `frontend-vite/src/Data.jsx`.
   - **Commit:** `f57b943` (Task 2).

3. **[Rule 1 — bug avoidance] EDITMODE markers in tweaks-panel.jsx are inside a doc-comment, not source.**
   - **Found during:** Task 2, plan said tweaks-panel.jsx has EDITMODE markers around `TWEAK_DEFAULTS`. Source inspection showed those markers only exist inside a `//` doc-comment example block (no `TWEAK_DEFAULTS` const exists in the file). The comment was preserved verbatim — no source removal.
   - **Action:** None required; documented for transparency. The only real EDITMODE markers are in App.jsx around `DEFAULTS`, which were preserved exactly.

### Auth gates encountered

None. No external accounts touched.

## Verification at the checkpoint

### Static-source gates (all green)

```
$ grep -REn '^window\.|^Object\.assign\(window' frontend-vite/src | grep -v '^#'
# (no matches — 0 window globals leaked into the port)

$ grep -REn '@babel/standalone|text/babel' frontend-vite/src frontend-vite/index.html
# (no matches — Babel-standalone fully removed)

$ for p in Dashboard Focus Folders Relations Terminals Tools Calendar Analytics; do
    grep -q "^export default $p" "frontend-vite/src/pages/$p.jsx" || echo "FAIL: $p"
  done
# (no FAIL output — all 8 default-exports present)
```

### Dev-server gate (green)

```
$ cd frontend-vite && pnpm dev
  VITE v5.4.21  ready in 224 ms
  ➜  Local:   http://localhost:5173/

$ curl -fsS -o /dev/null -w '%{http_code}\n' http://localhost:5173/
200

$ for f in pages/Dashboard pages/Focus pages/Folders pages/Relations pages/Terminals pages/Tools pages/Calendar pages/Analytics Data Icons TweaksPanel AiChat App; do
    curl -fsS -o /dev/null -w "%{http_code} $f.jsx\n" http://localhost:5173/src/$f.jsx
  done
# 200 for all 13 modules
```

### Legacy untouched (green)

```
$ git status --porcelain frontend/
# (no output — frontend/ unchanged across Tasks 1-3)
```

## Self-Check

| Claim                                                         | Verification                                                | Status  |
| ------------------------------------------------------------- | ----------------------------------------------------------- | ------- |
| `frontend-vite/package.json` exists with react 18.3.1         | `test -f && grep '"react": "18.3.1"'`                       | FOUND   |
| `frontend-vite/vite.config.js` has `base: './'`               | `grep "base: './'"`                                         | FOUND   |
| `frontend-vite/index.html` loads `/src/main.jsx`              | `grep 'src="/src/main.jsx"'`                                | FOUND   |
| All 8 page files exist with `export default PageName`         | shell loop above                                            | FOUND   |
| Zero `window.X` references in `frontend-vite/src`             | `grep -REn` returns no matches                              | FOUND   |
| Zero `React.useState` direct refs                             | `grep -REn 'React\.(useState\|useEffect\|useRef\|useMemo)'` | FOUND   |
| Commit `d9dc93f` (Task 1) in git log                          | `git log --all                                             \| grep d9dc93f`            | FOUND |
| Commit `f57b943` (Task 2) in git log                          | `git log --all                                             \| grep f57b943`            | FOUND |
| Commit `25248ff` (Task 3) in git log                          | `git log --all                                             \| grep 25248ff`            | FOUND |
| Commit `a14832e` (Task 4 checkpoint summary) in git log       | `git log --all                                             \| grep a14832e`            | FOUND |
| Commit `f0d692b` (Task 5 build verification) in git log       | `git log --all                                             \| grep f0d692b`            | FOUND |
| `frontend-vite/dist/index.html` exists post-build             | `test -f frontend-vite/dist/index.html`                     | FOUND   |
| `frontend-vite/dist/assets/index-*.js` exists                 | `ls frontend-vite/dist/assets/index-*.js`                   | FOUND   |
| `frontend-vite/dist/assets/index-*.css` exists                | `ls frontend-vite/dist/assets/index-*.css`                  | FOUND   |
| dist/index.html uses relative `./assets/` paths               | `grep './assets/' frontend-vite/dist/index.html`            | FOUND   |
| Legacy `frontend/` untouched                                  | `git status --porcelain frontend/` empty                    | FOUND   |

**Self-Check: PASSED**

## Task 4 — Visual parity checkpoint (APPROVED)

Operator-approved at 2026-05-26. Both servers were left running for the static-serve comparison in Task 5:

| Port | Source              | Process                                            | Verdict at checkpoint |
| ---- | ------------------- | -------------------------------------------------- | --------------------- |
| 8090 | `frontend/`         | `python3 -m http.server 8090 -d frontend` (legacy) | Pixel-identical       |
| 5173 | `frontend-vite/`    | `pnpm dev` (Vite + HMR)                            | Pixel-identical       |

All 8 sidebar pages, every Tweaks axis (Accent, Density, Sidebar, Dashboard Layout, Mock data), HMR sanity, AI bubble fallback string, and clean DevTools console were confirmed at 1200×800 before Task 5 proceeded.

## Task 5 — Production build + static-serve verification (commit `f0d692b`)

```
$ cd frontend-vite && pnpm build
> vite build
vite v5.4.21 building for production...
transforming...
✓ 43 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.66 kB │ gzip:  0.37 kB
dist/assets/index-CPENLnjb.css   44.06 kB │ gzip:  8.20 kB
dist/assets/index-Bgrs6aKr.js   250.23 kB │ gzip: 77.06 kB
✓ built in 444ms
```

### Gate checks (all green)

| Gate                                              | Command                                                       | Result    |
| ------------------------------------------------- | ------------------------------------------------------------- | --------- |
| dist/index.html exists                            | `test -f dist/index.html`                                     | PASS      |
| hashed JS chunk exists                            | `ls dist/assets/index-*.js` → `index-Bgrs6aKr.js` (250 KB)    | PASS      |
| hashed CSS chunk exists                           | `ls dist/assets/index-*.css` → `index-CPENLnjb.css` (44 KB)   | PASS      |
| POSITIVE: dist/index.html contains `./assets/`    | `grep -q './assets/' dist/index.html`                         | PASS      |
| NEGATIVE: no absolute `/assets/` paths            | `! grep -qE '"/assets/' dist/index.html`                      | PASS      |
| Static serve over port 5174                       | `python3 -m http.server 5174 -d dist` then `curl /`           | HTTP 200  |
| Served HTML contains `<div id="root">`            | `curl /` then `grep -q '<div id="root">'`                     | PASS      |
| Hashed JS asset reachable over 5174               | `curl /assets/index-Bgrs6aKr.js`                              | HTTP 200, 250,496 B |
| Hashed CSS asset reachable over 5174              | `curl /assets/index-CPENLnjb.css`                             | HTTP 200, 44,063 B  |
| No `@babel/standalone` / `text/babel` anywhere    | `grep -REn` excluding `node_modules`, `pnpm-lock.yaml`, `dist/` | PASS    |
| No `window.X` / `Object.assign(window)` in src/   | `grep -REn '^window\.|^Object\.assign\(window' src`           | PASS      |
| Legacy `frontend/`, `bin/`, `lib/` untouched      | `git status --porcelain frontend/ bin/ lib/`                  | empty     |
| 5174 temporary server killed                      | `pkill -f "http.server 5174"`                                 | PASS      |
| 5173 (Vite dev) still alive after Task 5          | `curl http://localhost:5173/`                                 | HTTP 200  |
| 8090 (legacy) still alive after Task 5            | `curl http://localhost:8090/`                                 | HTTP 200  |

### dist/ summary

| Path                                       | Size      | Gzip      |
| ------------------------------------------ | --------: | --------: |
| `frontend-vite/dist/index.html`            |   657 B   |   376 B   |
| `frontend-vite/dist/assets/index-Bgrs6aKr.js` | 250,496 B | 77,066 B  |
| `frontend-vite/dist/assets/index-CPENLnjb.css` | 44,063 B |  8,191 B  |
| **Total `dist/`**                          | **296 KB** | n/a       |

`dist/` is gitignored per `frontend-vite/.gitignore`; the build is fully reproducible from the committed `pnpm-lock.yaml` via:

```bash
cd frontend-vite && pnpm install --frozen-lockfile && pnpm build
```

The Task 5 commit is `--allow-empty` because it records a verification milestone — no source files changed (build output is gitignored).

### Tauri-ready confirmation

`dist/index.html` ships with relative asset paths:

```html
<script type="module" crossorigin src="./assets/index-Bgrs6aKr.js"></script>
<link rel="stylesheet" crossorigin href="./assets/index-CPENLnjb.css">
<body>
  <div id="root"></div>
```

The `./assets/...` prefix (from `base: './'` in `vite.config.js`) means Tauri's resource loader resolves assets relative to wherever the embedded `index.html` lives in the bundled app — exactly what Phase 2 needs.

## ROADMAP success criteria (all 4 satisfied)

| # | Criterion                                                                       | Proof                                                                                |
| - | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| 1 | `frontend-vite/` is a Vite + React 18 (TypeScript-optional) project             | `frontend-vite/package.json` (react 18.3.1, vite 5.4.21), `frontend-vite/vite.config.js` |
| 2 | Every file in `frontend/` has a Vite-compatible equivalent under `frontend-vite/src/` | `src/{main,App,Icons,Data,AiChat,TweaksPanel,styles.css}` + `src/pages/{Dashboard,Focus,Folders,Relations,Terminals,Tools,Calendar,Analytics}.jsx` |
| 3 | `pnpm dev` on :5173 with HMR; 8 pages identical to :8090                        | Operator-approved at Task 4 human-verify checkpoint (2026-05-26)                     |
| 4 | `pnpm build` produces static `dist/` Tauri can bundle                           | `dist/index.html` references `./assets/...` (relative); standalone served on :5174 returns HTTP 200 with `<div id="root">` |

## Next-phase note (Phase 2 — Tauri shell)

Phase 2 is unblocked. The Tauri config will be:

```jsonc
// src-tauri/tauri.conf.json
{
  "build": {
    "frontendDist": "../frontend-vite/dist",
    "devUrl":       "http://localhost:5173"
  }
}
```

`base: './'` in `vite.config.js` guarantees the eventual `dist/index.html` ships relative asset paths so Tauri's resource loader picks them up unchanged from any embedded location.
