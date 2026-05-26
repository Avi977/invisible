---
phase: INV-01-vite-migration-of-frontend
workstream: tauri-shell
plan: 01
status: in-progress
checkpoint: task-4-human-verify
completed_tasks: [1, 2, 3]
pending_tasks: [4, 5]
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
  duration_minutes: 0  # checkpoint: Task 4 still pending
  completed_date: ~
---

# Phase INV-01 Plan 01: Vite migration of frontend — Summary (CHECKPOINT)

Replaced the in-browser Babel-standalone React build at `frontend/` with a production Vite 5 + React 18.3.1 pipeline at `frontend-vite/`. Same components, same styles, ESM imports instead of `window.X = X` globals, dev server with HMR on :5173, Tauri-ready `dist/` ready to bake in Phase 2.

**Status:** Tasks 1-3 complete. Task 4 is a `checkpoint:human-verify` — the orchestrator is awaiting human visual-parity approval at 1200×800 before Task 5 (production build) runs.

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
| Legacy `frontend/` untouched                                  | `git status --porcelain frontend/` empty                    | FOUND   |

**Self-Check: PASSED**

## Background server status (for human verification)

Two HTTP servers are running for the operator to compare side-by-side:

| Port | Source              | Process                                            | Status |
| ---- | ------------------- | -------------------------------------------------- | ------ |
| 8090 | `frontend/`         | `python3 -m http.server 8090 -d frontend` (legacy) | UP     |
| 5173 | `frontend-vite/`    | `pnpm dev` (Vite + HMR)                            | UP     |

## Operator: Task 4 verification checklist

Resize both browser windows to **1200 × 800**. Place side-by-side.

For EACH of the 8 sidebar pages, confirm visual identity between :5173 and :8090:

- [ ] Dashboard — sidebar entries, page header, project cards, layout-switching
- [ ] Focus — single-project view, tasklist, terminal, browser preview
- [ ] Folders — three-source columns (Local / VPS / GitHub), tree expand/collapse
- [ ] Relations — Obsidian graph, node drag, filter legend
- [ ] Terminals — 1 large + 5 small, collapsible project headers
- [ ] Tools — n8n-style node graph + palette
- [ ] Calendar — mini-cal + week view + event blocks
- [ ] Analytics — token + time charts, tool breakdown, top actions

For the Tweaks panel (open via the floating chrome on either build), cycle each axis and confirm both apps respond identically:

- [ ] Accent: Per page / Amber / Cyan
- [ ] Density: compact / comfy / spacious
- [ ] Sidebar: expanded / collapsed
- [ ] Dashboard Layout: bento / grid / kanban / list
- [ ] Mock data: Personal projects / Client work (Dashboard project cards must change in BOTH apps)

Finally:

- [ ] AI bubble (bottom-right) opens; type any message → the fallback string `(couldn't reach the model — try again)` appears in BOTH apps (no Claude host present locally).
- [ ] HMR sanity: edit a trivial `console.log` in `frontend-vite/src/pages/Dashboard.jsx`. The Vite tab module-reloads without a full refresh. Revert.
- [ ] Browser DevTools console on :5173 — no red errors, no missing-module warnings. (React 18 StrictMode double-invoke warnings are expected and fine.)

If anything diverges, list page + control + observed delta and the executor will fix on resume. If pixel-identical, reply `approved`.

## Task 5 (NOT YET RUN)

Production build (`pnpm build` → `dist/index.html` + hashed assets with relative paths) is **PENDING the human checkpoint**. The orchestrator will re-spawn this executor with `approved` to run Task 5.

## Next-phase note (Phase 2 — Tauri shell)

Phase 2 is unblocked the moment Task 5 succeeds. The Tauri config will be:

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
