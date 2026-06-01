---
phase: INV-01-vite-migration-of-frontend
workstream: tauri-shell
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend-vite/package.json
  - frontend-vite/pnpm-lock.yaml
  - frontend-vite/vite.config.js
  - frontend-vite/index.html
  - frontend-vite/.gitignore
  - frontend-vite/README.md
  - frontend-vite/src/main.jsx
  - frontend-vite/src/App.jsx
  - frontend-vite/src/Icons.jsx
  - frontend-vite/src/Data.jsx
  - frontend-vite/src/AiChat.jsx
  - frontend-vite/src/TweaksPanel.jsx
  - frontend-vite/src/styles.css
  - frontend-vite/src/pages/Dashboard.jsx
  - frontend-vite/src/pages/Focus.jsx
  - frontend-vite/src/pages/Folders.jsx
  - frontend-vite/src/pages/Relations.jsx
  - frontend-vite/src/pages/Terminals.jsx
  - frontend-vite/src/pages/Tools.jsx
  - frontend-vite/src/pages/Calendar.jsx
  - frontend-vite/src/pages/Analytics.jsx
autonomous: false   # plan 04 has a checkpoint:human-verify for visual parity
requirements:
  - REQ-06
user_setup: []      # no external accounts; pnpm install is local
must_haves:
  truths:
    - "`pnpm dev` (run inside frontend-vite/) serves the React app on http://localhost:5173/ with HMR"
    - "All 8 sidebar pages (dashboard, focus, folders, relations, terminals, tools, calendar, analytics) render in the Vite build"
    - "The Tweaks panel opens, Accent / Density / Sidebar / Layout / Mock data controls all mutate the UI exactly like the legacy 8090 build"
    - "Switching `Mock data` between `default` and `client` in the Tweaks panel swaps Dashboard projects (proves Data.jsx ESM export works)"
    - "At 1200x800 the Vite dev server (5173) is visually identical to the legacy frontend (8090) across every page and every Tweak combination"
    - "`pnpm build` succeeds and emits frontend-vite/dist/ with index.html + hashed JS + hashed CSS; relative paths so it can be opened from any directory"
    - "Serving dist/ over a static file server renders identically to the dev server"
    - "frontend/ remains untouched and continues to serve on 8090 (legacy fallback)"
  artifacts:
    - path: "frontend-vite/package.json"
      provides: "Vite 5 + React 18.3.1 + @vitejs/plugin-react-swc dependencies; dev/build/preview scripts"
      contains: "react\": \"18.3.1\""
    - path: "frontend-vite/vite.config.js"
      provides: "Vite config: react-swc plugin, base './', dev server on port 5173"
      contains: "base: './'"
    - path: "frontend-vite/index.html"
      provides: "Vite entry HTML; loads Geist fonts; mounts /src/main.jsx; no Babel-standalone, no React UMD"
      contains: "src=\"/src/main.jsx\""
    - path: "frontend-vite/src/main.jsx"
      provides: "createRoot mount of <App/> with React 18 createRoot API"
      contains: "createRoot"
    - path: "frontend-vite/src/App.jsx"
      provides: "App shell port — sidebar + page router + Tweaks panel, with explicit ESM imports of pages and Icons/Data/AiChat/TweaksPanel"
      contains: "export default function App"
    - path: "frontend-vite/src/Icons.jsx"
      provides: "Icon library (`I`) ESM export"
      contains: "export const I"
    - path: "frontend-vite/src/Data.jsx"
      provides: "DATA_SETS mock data ESM export (no window globals)"
      contains: "export const DATA_SETS"
    - path: "frontend-vite/src/AiChat.jsx"
      provides: "AIBubble component default export"
      contains: "export default function AIBubble"
    - path: "frontend-vite/src/TweaksPanel.jsx"
      provides: "useTweaks hook + TweaksPanel/TweakSection/TweakRadio/TweakSelect/TweakRow/TweakSlider/TweakToggle/TweakText/TweakNumber/TweakColor/TweakButton named exports"
      contains: "export function useTweaks"
    - path: "frontend-vite/src/pages/Dashboard.jsx"
      provides: "Dashboard page default export"
      contains: "export default function Dashboard"
    - path: "frontend-vite/src/pages/Focus.jsx"
      provides: "Focus page default export"
      contains: "export default function Focus"
    - path: "frontend-vite/src/pages/Folders.jsx"
      provides: "Folders page default export"
      contains: "export default function Folders"
    - path: "frontend-vite/src/pages/Relations.jsx"
      provides: "Relations page default export"
      contains: "export default function Relations"
    - path: "frontend-vite/src/pages/Terminals.jsx"
      provides: "Terminals page default export"
      contains: "export default function Terminals"
    - path: "frontend-vite/src/pages/Tools.jsx"
      provides: "Tools page default export"
      contains: "export default function Tools"
    - path: "frontend-vite/src/pages/Calendar.jsx"
      provides: "Calendar page default export"
      contains: "export default function Calendar"
    - path: "frontend-vite/src/pages/Analytics.jsx"
      provides: "Analytics page default export"
      contains: "export default function Analytics"
    - path: "frontend-vite/src/styles.css"
      provides: "Same ~56 KB stylesheet, copied verbatim from frontend/styles.css"
      contains: "--accent"
    - path: "frontend-vite/.gitignore"
      provides: "Ignores node_modules/ and dist/"
      contains: "node_modules"
    - path: "frontend-vite/README.md"
      provides: "Single-screen README: pnpm install / dev / build / how Tauri will consume dist/"
      contains: "pnpm dev"
  key_links:
    - from: "frontend-vite/index.html"
      to: "frontend-vite/src/main.jsx"
      via: "<script type=\"module\" src=\"/src/main.jsx\">"
      pattern: "src=\"/src/main.jsx\""
    - from: "frontend-vite/src/main.jsx"
      to: "frontend-vite/src/App.jsx"
      via: "import App from './App.jsx'"
      pattern: "from ['\"]\\./App"
    - from: "frontend-vite/src/App.jsx"
      to: "frontend-vite/src/pages/*.jsx"
      via: "import Dashboard from './pages/Dashboard.jsx' (etc.)"
      pattern: "from ['\"]\\./pages/"
    - from: "frontend-vite/src/App.jsx"
      to: "frontend-vite/src/Data.jsx"
      via: "import { DATA_SETS } from './Data.jsx' (NOT window.DATA_SETS)"
      pattern: "import \\{ DATA_SETS \\}"
    - from: "frontend-vite/src/App.jsx"
      to: "frontend-vite/src/Icons.jsx"
      via: "import { I } from './Icons.jsx'"
      pattern: "import \\{ I \\}"
    - from: "frontend-vite/src/App.jsx"
      to: "frontend-vite/src/TweaksPanel.jsx"
      via: "import { useTweaks, TweaksPanel, TweakSection, TweakRadio, TweakSelect } from './TweaksPanel.jsx'"
      pattern: "from ['\"]\\./TweaksPanel"
    - from: "frontend-vite/src/App.jsx"
      to: "frontend-vite/src/AiChat.jsx"
      via: "import AIBubble from './AiChat.jsx'"
      pattern: "from ['\"]\\./AiChat"
    - from: "frontend-vite/src/main.jsx"
      to: "frontend-vite/src/styles.css"
      via: "import './styles.css'"
      pattern: "import ['\"]\\./styles\\.css['\"]"
---

<objective>
Phase 1 of the `tauri-shell` workstream: migrate the Babel-standalone React frontend at `frontend/` into a Vite-bundled project at `frontend-vite/`. Same components, same styles, same visual — production build pipeline replaces in-browser JSX compilation.

Purpose: Phase 2 (Tauri shell) needs a `dist/` folder with relative-path assets to bundle into a native binary. Babel-standalone cannot produce that. This phase swaps the build pipeline without changing UX.

Output: A new `frontend-vite/` directory containing a working Vite 5 + React 18.3.1 project that:
  1. Runs on http://localhost:5173/ via `pnpm dev` with HMR.
  2. Pixel-matches the legacy frontend on http://localhost:8090/ across all 8 pages and every Tweaks combination.
  3. Builds to `dist/` via `pnpm build` with relative asset paths (Tauri-ready).

The legacy `frontend/` directory is untouched throughout this phase.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/REQUIREMENTS.md
@.planning/workstreams/tauri-shell/ROADMAP.md
@.planning/workstreams/tauri-shell/phases/INV-01-vite-migration-of-frontend/CONTEXT.md

# Source files being ported (read-only references — DO NOT modify these)
@frontend/index.html
@frontend/styles.css
@frontend/app.jsx
@frontend/icons.jsx
@frontend/data.jsx
@frontend/ai-chat.jsx
@frontend/tweaks-panel.jsx
@frontend/pages/dashboard.jsx
@frontend/pages/focus.jsx
@frontend/pages/folders.jsx
@frontend/pages/relations.jsx
@frontend/pages/terminals.jsx
@frontend/pages/tools.jsx
@frontend/pages/calendar.jsx
@frontend/pages/analytics.jsx

<interfaces>
<!-- The globals to convert. Each `window.X = X` becomes an ES module export. -->

Globals exported via `window.*` in the legacy frontend (from grep across frontend/):

  frontend/icons.jsx         : Object.assign(window, { I })
  frontend/data.jsx          : const DATA_SETS = { default: {...}, client: {...} }   // implicit global (top-level `const`)
  frontend/tweaks-panel.jsx  : Object.assign(window, { useTweaks, TweaksPanel, TweakSection, TweakRow,
                                                       TweakSlider, TweakToggle, TweakRadio, TweakSelect,
                                                       TweakText, TweakNumber, TweakColor, TweakButton })
  frontend/ai-chat.jsx       : window.AIBubble = AIBubble
  frontend/app.jsx           : window.App = App
  frontend/pages/dashboard.jsx  : window.Dashboard = Dashboard
  frontend/pages/focus.jsx      : window.Focus = Focus
  frontend/pages/folders.jsx    : window.Folders = Folders
  frontend/pages/relations.jsx  : window.Relations = Relations
  frontend/pages/terminals.jsx  : window.Terminals = Terminals
  frontend/pages/tools.jsx      : window.Tools = Tools
  frontend/pages/calendar.jsx   : window.Calendar = Calendar
  frontend/pages/analytics.jsx  : window.Analytics = Analytics

React-hook destructure aliases at the top of each file (line numbers from grep):

  ai-chat.jsx:4       const { useState: useStateAI, useRef: useRefAI, useEffect: useEffectAI } = React;
  app.jsx:3           const { useState: useStateApp, useEffect: useEffectApp } = React;
  pages/dashboard.jsx:3   const { useState } = React;
  pages/focus.jsx:4       const { useState: useStateFC, useEffect: useEffectFC, useRef: useRefFC } = React;
  pages/folders.jsx:4     const { useState: useStateF } = React;
  pages/relations.jsx:4   const { useState: useStateG, useRef: useRefG, useEffect: useEffectG } = React;
  pages/terminals.jsx:4   const { useState: useStateT, useRef: useRefT, useEffect: useEffectT } = React;
  pages/tools.jsx:4       const { useState: useStateTL, useRef: useRefTL, useEffect: useEffectTL, useMemo: useMemoTL } = React;
  pages/calendar.jsx:3    const { useState: useStateC, useMemo: useMemoC } = React;
  pages/analytics.jsx:4   const { useState: useStateA, useMemo: useMemoA } = React;

These suffixed aliases were workarounds for a single shared global scope. In ESM each file has its own scope, so during the port:
  - Replace `const { useState: useStateX, useEffect: useEffectX, ... } = React;`
  - With `import { useState, useEffect, useRef, useMemo } from 'react';`
  - And rename every call site inside the file (`useStateApp(...)` -> `useState(...)`, etc.). Search/replace within the single file only.

App.jsx specifically consumes these names from other modules — its import list must read:

  import { useState, useEffect } from 'react';
  import { I } from './Icons.jsx';
  import { DATA_SETS } from './Data.jsx';
  import { useTweaks, TweaksPanel, TweakSection, TweakRadio, TweakSelect } from './TweaksPanel.jsx';
  import AIBubble from './AiChat.jsx';
  import Dashboard from './pages/Dashboard.jsx';
  import Focus from './pages/Focus.jsx';
  import Folders from './pages/Folders.jsx';
  import Relations from './pages/Relations.jsx';
  import Terminals from './pages/Terminals.jsx';
  import Tools from './pages/Tools.jsx';
  import Calendar from './pages/Calendar.jsx';
  import Analytics from './pages/Analytics.jsx';

The two `/*EDITMODE-BEGIN*/.../*EDITMODE-END*/` markers in `app.jsx` and `tweaks-panel.jsx` are Claude Design's live-editing markers — keep them as plain comments; do not remove or alter the values they wrap.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Bootstrap frontend-vite scaffold (pnpm + Vite 5 + React 18.3.1)</name>
  <files>
    frontend-vite/package.json,
    frontend-vite/pnpm-lock.yaml,
    frontend-vite/vite.config.js,
    frontend-vite/index.html,
    frontend-vite/.gitignore,
    frontend-vite/README.md,
    frontend-vite/src/main.jsx,
    frontend-vite/src/styles.css
  </files>
  <action>
Ensure pnpm is available, then scaffold a minimal Vite + React project at `frontend-vite/`. Do NOT use `pnpm create vite` (it's interactive); write the files directly so the result is deterministic and matches the legacy stack exactly.

Step 1 — Toolchain preflight.
  (a) Node version: `node -v | awk -F. '{ exit ($1+0 >= 18) ? 0 : 1 }' || { echo "Node 18+ required (Vite 5 minimum); current: $(node -v)"; exit 1; }`. Vite 5.4 will fail with cryptic errors on Node <18.
  (b) pnpm: `command -v pnpm` first. If absent, run `corepack enable && corepack prepare pnpm@latest --activate`. If corepack is also unavailable, fall back to `npm i -g pnpm`. Verify with `pnpm --version`.

Step 2 — Create `frontend-vite/.gitignore` with two lines: `node_modules` and `dist`.

Step 3 — Create `frontend-vite/package.json`. Fields:
  - `"name": "invisible-frontend-vite"`, `"private": true`, `"version": "0.0.0"`, `"type": "module"`.
  - `scripts`: `"dev": "vite"`, `"build": "vite build"`, `"preview": "vite preview --port 5174"`.
  - `dependencies`: `"react": "18.3.1"`, `"react-dom": "18.3.1"` (exact, no caret — match the legacy UMD version).
  - `devDependencies`: `"vite": "^5.4.0"`, `"@vitejs/plugin-react-swc": "^3.7.0"`.

Step 4 — Create `frontend-vite/vite.config.js`:
  - `import { defineConfig } from 'vite'` and `import react from '@vitejs/plugin-react-swc'`.
  - Export: `plugins: [react()]`, `base: './'` (so dist assets use relative paths for Tauri), `server: { port: 5173, strictPort: true }`, `build: { outDir: 'dist' }`.

Step 5 — Create `frontend-vite/index.html`:
  - `<!doctype html>` + `<html lang="en">`.
  - `<head>`: meta charset + viewport, `<title>invisible</title>`, the same two `<link rel="preconnect">` tags and the `<link href="https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet"/>` copied verbatim from `frontend/index.html`.
  - NO `<link rel="stylesheet" href="styles.css"/>` in HTML — the stylesheet will be imported from `src/main.jsx` so Vite hashes it.
  - NO React UMD scripts, NO Babel-standalone script.
  - `<body>`: `<div id="root"></div>` then `<script type="module" src="/src/main.jsx"></script>`.

Step 6 — Create `frontend-vite/src/styles.css` by copying `frontend/styles.css` byte-for-byte (use `cp frontend/styles.css frontend-vite/src/styles.css`). Do not refactor.

Step 7 — Create `frontend-vite/src/main.jsx` (minimal stub; App is ported in Task 2):
  - `import { StrictMode } from 'react'`
  - `import { createRoot } from 'react-dom/client'`
  - `import './styles.css'`
  - For now, render a placeholder: `createRoot(document.getElementById('root')).render(<StrictMode><div style={{padding:24,color:'#fff'}}>frontend-vite scaffold OK</div></StrictMode>)`. Task 2 will swap in `<App/>`.

Step 8 — Create `frontend-vite/README.md` (one screen). Sections:
  - Title and one-sentence purpose.
  - "Develop" — `pnpm install`, `pnpm dev`, then visit http://localhost:5173/.
  - "Build" — `pnpm build` writes to `dist/` with relative asset paths.
  - "Used by Tauri (Phase 2)" — note that `src-tauri/tauri.conf.json` will point `frontendDist` at `../frontend-vite/dist` and `devUrl` at `http://localhost:5173`.
  - "Migration note" — one paragraph: legacy frontend lives at `frontend/` served on 8090; this directory is the Vite port. They render the same UI.

Step 9 — Run `cd frontend-vite && pnpm install` to generate `pnpm-lock.yaml` and populate `node_modules/`. Then run `pnpm dev` in the background (`pnpm dev > /tmp/vite-dev.log 2>&1 &`), wait for the "Local: http://localhost:5173/" line to appear in the log, curl `http://localhost:5173/` and confirm a 200 response with the placeholder text. Kill the dev server when done.

Do NOT touch `frontend/`, `bin/`, `lib/`, or sibling workstreams' files.
  </action>
  <verify>
    <automated>cd frontend-vite && test -f package.json && test -f vite.config.js && test -f index.html && test -f src/main.jsx && test -f src/styles.css && test -f .gitignore && test -f README.md && grep -q '"react": "18.3.1"' package.json && grep -q "base: './'" vite.config.js && grep -q 'src="/src/main.jsx"' index.html && grep -q -- "--accent" src/styles.css && pnpm install --frozen-lockfile=false >/dev/null 2>&1 && (pnpm dev > /tmp/vite-dev.log 2>&1 &) && sleep 4 && curl -fsS http://localhost:5173/ | grep -q "frontend-vite scaffold OK" && pkill -f "vite" || true</automated>
  </verify>
  <done>
    `frontend-vite/` exists with package.json (react 18.3.1, vite ^5.4.0), vite.config.js (`base: './'`, port 5173), an HTML entry that loads `/src/main.jsx`, the unmodified styles.css copy, and a one-screen README. `pnpm install` succeeded, `pnpm dev` served the placeholder on 5173. Legacy `frontend/` is unchanged.
  </done>
</task>

<task type="auto">
  <name>Task 2: Port shared modules (Icons, Data, AiChat, TweaksPanel, App) and wire main.jsx</name>
  <files>
    frontend-vite/src/Icons.jsx,
    frontend-vite/src/Data.jsx,
    frontend-vite/src/AiChat.jsx,
    frontend-vite/src/TweaksPanel.jsx,
    frontend-vite/src/App.jsx,
    frontend-vite/src/main.jsx
  </files>
  <action>
Port the 5 shared `frontend/*.jsx` files to `frontend-vite/src/` as ES modules. Behavior changes are forbidden — this is a global-to-ESM mechanical rewrite. The page files (Dashboard, Focus, etc.) are ported separately in Task 3; for now they are referenced as imports in `App.jsx`.

General rules applied to every file in this task:
  1. Replace the `const { useState: useStateX, useEffect: useEffectX, useRef: useRefX, useMemo: useMemoX } = React;` line with a single `import { useState, useEffect, useRef, useMemo } from 'react';` (only the hooks actually used in that file).
  2. Inside the file, rename every aliased hook back to its base name. Example in `App.jsx`: `useStateApp` -> `useState`, `useEffectApp` -> `useEffect`. The alias was a global-scope workaround; in ESM each module has its own scope.
  3. Replace any `window.X = X` (or `Object.assign(window, { ... })`) at the bottom of the file with proper ESM exports (see per-file mapping below).
  4. Preserve the two `/*EDITMODE-BEGIN*/.../*EDITMODE-END*/` markers in `App.jsx` (around DEFAULTS) and `TweaksPanel.jsx` (around TWEAK_DEFAULTS) verbatim — they're Claude Design's live-edit anchors.
  5. Do not change component logic, JSX trees, or CSS class names. Behavior parity is non-negotiable.

Per-file porting (source -> destination):

`frontend/icons.jsx` -> `frontend-vite/src/Icons.jsx`
  - Body unchanged: `Ico` helper, the `I = { ... }` icon map.
  - Bottom: replace `Object.assign(window, { I });` with `export const I = { ... }` (or keep `const I = { ... }` and add `export { I };` at the bottom). No React-hook imports needed here.

`frontend/data.jsx` -> `frontend-vite/src/Data.jsx`
  - Currently the file is `const DATA_SETS = { default: {...}, client: {...} };` with no explicit window assignment — but the legacy script-tag model leaks the top-level `const` to the global scope. Make this explicit: change the declaration to `export const DATA_SETS = { ... };`. This satisfies CONTEXT.md's requirement to remove the `window.DATA_SETS` global pattern.

`frontend/ai-chat.jsx` -> `frontend-vite/src/AiChat.jsx`
  - Replace the React hook destructure line with `import { useState, useRef, useEffect } from 'react';` and rename `useStateAI`/`useRefAI`/`useEffectAI` back to `useState`/`useRef`/`useEffect` everywhere inside this file.
  - The file references `window.claude.complete` (per the header comment). That global does not exist in browsers — it was Claude Design's design-mode stub. The legacy `ai-chat.jsx:25-42` already wraps the call in try/catch and surfaces `"(couldn't reach the model — try again)"` to the user on failure; the port must preserve that exact string. Wrap the call in `if (typeof window.claude?.complete === 'function') { ... } else { return "(couldn't reach the model — try again)"; }` so dev-mode (where the global is absent) shows the same fallback as legacy. **Visual-parity check**: at Task 4 Step 5, open the AI bubble on any page and send a test message; the fallback string must match between 5173 and 8090.
  - Bottom: replace `window.AIBubble = AIBubble;` with `export default AIBubble;`.

`frontend/tweaks-panel.jsx` -> `frontend-vite/src/TweaksPanel.jsx`
  - Add `import { useState, useEffect, useRef } from 'react';` at the top (preserve whichever hooks the file actually destructures from React — inspect the source).
  - Bottom: replace `Object.assign(window, { useTweaks, TweaksPanel, TweakSection, TweakRow, TweakSlider, TweakToggle, TweakRadio, TweakSelect, TweakText, TweakNumber, TweakColor, TweakButton });` with a single explicit export block: `export { useTweaks, TweaksPanel, TweakSection, TweakRow, TweakSlider, TweakToggle, TweakRadio, TweakSelect, TweakText, TweakNumber, TweakColor, TweakButton };`.
  - Keep the `/*EDITMODE-BEGIN*/.../*EDITMODE-END*/` markers around TWEAK_DEFAULTS untouched.

`frontend/app.jsx` -> `frontend-vite/src/App.jsx`
  - At the top, replace `const { useState: useStateApp, useEffect: useEffectApp } = React;` with `import { useState, useEffect } from 'react';`.
  - Add the import block listed under "<interfaces>" above (Icons, Data, TweaksPanel, AIBubble, and the 8 page components).
  - Rename every `useStateApp` -> `useState` and `useEffectApp` -> `useEffect` inside the file.
  - At the bottom, replace `window.App = App;` with `export default App;`.
  - Preserve the `/*EDITMODE-BEGIN*/.../*EDITMODE-END*/` markers around `DEFAULTS`.

After porting, update `frontend-vite/src/main.jsx` to mount the real App:
  - Imports: `StrictMode` from 'react', `createRoot` from 'react-dom/client', `./styles.css`, `App from './App.jsx'`.
  - Replace the placeholder render with `createRoot(document.getElementById('root')).render(<StrictMode><App/></StrictMode>);`.

Task 3 ports the page files; until Task 3 runs, `pnpm dev` will fail with "Cannot find module './pages/Dashboard.jsx'". That is the expected intermediate state — proceed to Task 3 before running the dev server.

After porting, sanity-check with grep gates (lines starting with `#` excluded so this doc doesn't self-invalidate when committed alongside the code):
  - `grep -RnE "^window\\.|^Object\\.assign\\(window" frontend-vite/src | grep -v '^#' | wc -l` MUST be 0.
  - `grep -RnE "useStateApp|useEffectApp|useStateAI|useRefAI|useEffectAI|\\buseStateF\\b|useStateFC|useEffectFC|useRefFC|\\buseStateG\\b|\\buseRefG\\b|\\buseEffectG\\b|\\buseStateT\\b|\\buseRefT\\b|\\buseEffectT\\b|useStateTL|useRefTL|useEffectTL|useMemoTL|\\buseStateC\\b|\\buseMemoC\\b|\\buseStateA\\b|\\buseMemoA\\b" frontend-vite/src | grep -v '^#' | wc -l` MUST be 0.
    (Word-boundary-anchored on macOS BSD `grep -E`; no Perl-lookahead — there is no `useStateType` token in source.)
  - `grep -RnE "^import (\\{[^}]+\\}|[A-Za-z_]+) from ['\"]react" frontend-vite/src | wc -l` MUST be >= 4 (at least App, AiChat, TweaksPanel, main all import from 'react').
  </action>
  <verify>
    <automated>cd frontend-vite && grep -q "^export const I" src/Icons.jsx && grep -q "^export const DATA_SETS" src/Data.jsx && grep -q "^export default" src/AiChat.jsx && grep -qE "^export \\{ useTweaks" src/TweaksPanel.jsx && grep -q "^export default App" src/App.jsx && grep -q "import App from './App.jsx'" src/main.jsx && grep -q "createRoot" src/main.jsx && test "$(grep -REn '^window\\.|^Object\\.assign\\(window' src 2>/dev/null | grep -v '^#' | wc -l | tr -d ' ')" = "0"</automated>
  </verify>
  <done>
    Five shared modules ported with ESM exports, no `window.*` globals remain in `frontend-vite/src/`, React hooks imported from 'react' (no `React.useState` destructure pattern), `App.jsx` imports all the page components it references, `main.jsx` mounts `<App/>` via `createRoot`, EDITMODE markers preserved.
  </done>
</task>

<task type="auto">
  <name>Task 3: Port the 8 page modules (Dashboard, Focus, Folders, Relations, Terminals, Tools, Calendar, Analytics)</name>
  <files>
    frontend-vite/src/pages/Dashboard.jsx,
    frontend-vite/src/pages/Focus.jsx,
    frontend-vite/src/pages/Folders.jsx,
    frontend-vite/src/pages/Relations.jsx,
    frontend-vite/src/pages/Terminals.jsx,
    frontend-vite/src/pages/Tools.jsx,
    frontend-vite/src/pages/Calendar.jsx,
    frontend-vite/src/pages/Analytics.jsx
  </files>
  <action>
Port each of the 8 page files under `frontend/pages/` to `frontend-vite/src/pages/` (capitalised filename). Apply the same global-to-ESM rules as Task 2.

For EACH page file:
  1. Replace the `const { useState: useStateX, useMemo: useMemoX, useRef: useRefX, useEffect: useEffectX } = React;` line at the top with `import { useState, useMemo, useRef, useEffect } from 'react';` — keep only the hooks the file actually uses (see line-mapping under <interfaces> for which hooks each file imports).
  2. Rename every aliased hook call back to its base name within that file only. `useStateA` -> `useState`, `useMemoA` -> `useMemo`, etc.
  3. If the file uses the `I.*` icon namespace, add `import { I } from '../Icons.jsx';` at the top.
  4. If the file references `DATA_SETS` directly (rare — usually only `App.jsx` does), add `import { DATA_SETS } from '../Data.jsx';`. If a page only receives `projects` as a prop, no Data import is needed.
  5. At the bottom, replace `window.PageName = PageName;` with `export default PageName;`.
  6. Do NOT alter component logic, JSX, or styles. This is a mechanical port.

Source -> destination map (the source line where `window.X = X` lives, for context):
  - `frontend/pages/dashboard.jsx:176`  -> `frontend-vite/src/pages/Dashboard.jsx`  (export default Dashboard)
  - `frontend/pages/focus.jsx:599`      -> `frontend-vite/src/pages/Focus.jsx`      (export default Focus)
  - `frontend/pages/folders.jsx:102`    -> `frontend-vite/src/pages/Folders.jsx`    (export default Folders)
  - `frontend/pages/relations.jsx:172`  -> `frontend-vite/src/pages/Relations.jsx`  (export default Relations)
  - `frontend/pages/terminals.jsx:289`  -> `frontend-vite/src/pages/Terminals.jsx` (export default Terminals)
  - `frontend/pages/tools.jsx:305`      -> `frontend-vite/src/pages/Tools.jsx`      (export default Tools)
  - `frontend/pages/calendar.jsx:195`   -> `frontend-vite/src/pages/Calendar.jsx`  (export default Calendar)
  - `frontend/pages/analytics.jsx:365`  -> `frontend-vite/src/pages/Analytics.jsx` (export default Analytics)

Note on filename casing: the legacy files are lowercase (`dashboard.jsx`), the Vite ports are PascalCase (`Dashboard.jsx`) to match the import statements emitted in App.jsx. macOS HFS+/APFS is case-insensitive by default, but the import strings ARE case-sensitive at module-resolution time on Vite + on the eventual Linux/Windows targets — match exactly.

After porting all 8 files, run a smoke build:
  1. `cd frontend-vite && pnpm dev > /tmp/vite-dev.log 2>&1 &` — start the dev server in the background.
  2. Wait up to 6 seconds for the "Local: http://localhost:5173/" line in the log.
  3. `curl -fsS http://localhost:5173/` — must return 200 with the HTML containing `<div id="root">` and a `<script type="module" src="/src/main.jsx">` tag.
  4. Open the log; there must be NO `[plugin:vite:import-analysis]` errors and NO "Failed to resolve import" lines.
  5. Kill the dev server (`pkill -f "vite"` or store the PID and `kill $PID`).

If any page emits a "Failed to resolve" error, the corresponding import path in `App.jsx` is wrong (likely a casing mismatch) — fix that import and re-test before declaring done.
  </action>
  <verify>
    <automated>cd frontend-vite && for p in Dashboard Focus Folders Relations Terminals Tools Calendar Analytics; do test -f "src/pages/$p.jsx" || { echo "MISSING src/pages/$p.jsx"; exit 1; }; grep -q "^export default $p" "src/pages/$p.jsx" || { echo "no default export in $p.jsx"; exit 1; }; done && test "$(grep -REn '^window\\.|^Object\\.assign\\(window' src/pages 2>/dev/null | grep -v '^#' | wc -l | tr -d ' ')" = "0" && (pnpm dev > /tmp/vite-dev.log 2>&1 &) && sleep 5 && curl -fsS http://localhost:5173/ | grep -q '/src/main.jsx' && ! grep -E "Failed to resolve|plugin:vite:import-analysis" /tmp/vite-dev.log && pkill -f vite || true</automated>
  </verify>
  <done>
    All 8 page files exist under `frontend-vite/src/pages/` with PascalCase filenames and `export default PageName`; no `window.*` globals remain anywhere in `frontend-vite/src/`; `pnpm dev` starts cleanly with no import-resolution errors; the dev server returns 200 on http://localhost:5173/.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 4: Visual parity verification — 5173 vs 8090 side by side</name>
  <what-built>
Tasks 1-3 produced a Vite-bundled React app at `frontend-vite/` that mirrors the legacy `frontend/` build. Before the production build (Task 5), the user must confirm visual parity at the resolution Tauri will use (1200x800, per CONTEXT.md).
  </what-built>
  <how-to-verify>
1. In one terminal, start the legacy frontend (if not already running):
   - `cd /Users/ace/.invisible-ws/tauri-shell && python3 -m http.server 8090 -d frontend > /tmp/frontend-legacy.log 2>&1 &`
   - Open http://localhost:8090/ — confirm it loads.

2. In a second terminal, start the Vite dev server:
   - `cd /Users/ace/.invisible-ws/tauri-shell/frontend-vite && pnpm dev > /tmp/vite-dev.log 2>&1 &`
   - Open http://localhost:5173/.

3. Resize each window to 1200x800 (matches the pywebview default). Place them side-by-side.

4. For EACH of the 8 sidebar pages — Dashboard, Focus, Folders, Relations, Terminals, Tools, Calendar, Analytics — confirm:
   - Sidebar entries look identical (label, icon, badge, color stripe on hover).
   - Page header (title, subtitle, online chip, search/bell/settings icons) matches.
   - Main page body matches: cards, lists, layouts, colors, spacing, font weights.
   - Hover and focus states match on at least 2 interactive elements per page.

5. Open the Tweaks panel (the slide-out drawer; trigger is usually a corner button — same in both builds). Cycle through each control and confirm both apps respond identically:
   - Accent: Per page / Amber / Cyan.
   - Density: compact / comfy / spacious.
   - Sidebar: expanded / collapsed.
   - Dashboard Layout: bento / grid / kanban / list.
   - Mock data: Personal projects / Client work — Dashboard project cards must change in both apps in the same way.

6. Confirm HMR by editing one trivial cosmetic value (e.g. change a console.log) in `frontend-vite/src/pages/Dashboard.jsx`; the Vite tab should reload its module without a full page reload. Revert the change.

7. Confirm in the browser devtools console of the Vite tab that there are NO red errors and NO warnings about missing modules. (StrictMode double-invoke warnings from React 18 are fine.)

If anything diverges visually or behaviorally, list the specific page + control + observed delta; the executor will fix and re-run this checkpoint.
  </how-to-verify>
  <resume-signal>Type "approved" if all 8 pages and the Tweaks panel are pixel-identical at 1200x800; otherwise describe the deltas page-by-page.</resume-signal>
</task>

<task type="auto">
  <name>Task 5: Production build + static-serve verification (Tauri-ready dist/)</name>
  <files>
    frontend-vite/dist/   (generated by Vite)
  </files>
  <action>
Produce the production bundle and confirm it renders identically when served as static files (the way Tauri will load it in Phase 2).

Step 1 — Kill any running dev server (`pkill -f vite || true`).

Step 2 — From `frontend-vite/`, run `pnpm build`. Expectations:
  - Exit code 0.
  - Output shows a Vite "rendering chunks" summary with at least one JS chunk and one CSS chunk.
  - `frontend-vite/dist/index.html` exists.
  - `frontend-vite/dist/assets/` contains at least one `index-*.js` and one `index-*.css`.
  - The generated `dist/index.html` references those assets with `./assets/...` (relative paths, NOT `/assets/...`). This is what `base: './'` in `vite.config.js` enforces. If the paths start with `/assets/...`, the Vite config is wrong — fix and rebuild.

Step 3 — Serve `dist/` standalone and verify it renders:
  - `cd frontend-vite && python3 -m http.server 5174 -d dist > /tmp/vite-dist.log 2>&1 &`
  - `curl -fsS http://localhost:5174/` returns 200 with the bundled HTML.
  - Open http://localhost:5174/ in a browser; navigate through all 8 sidebar pages and exercise the Tweaks panel. It must render identically to the dev server (5173) and to the legacy frontend (8090). No console errors.
  - Stop the server (`pkill -f "http.server 5174" || true`).

Step 4 — Run a final source-hygiene sweep on the committed source tree (NOT `node_modules/` or `dist/`):
  - `grep -REn '^window\\.|^Object\\.assign\\(window' frontend-vite/src | grep -v '^#'` -> must be empty (no globals leaked).
  - `grep -REn '@babel/standalone|text/babel' frontend-vite` -> must be empty (no Babel-standalone leftovers).
  - `git status frontend/` (run from repo root) -> must show no changes (legacy untouched). If anything is staged or modified under `frontend/`, revert it with `git checkout -- frontend/`.

Step 5 — Confirm Phase 1 success criteria from ROADMAP.md:
  1. `frontend-vite/` is a Vite + React 18 project — yes.
  2. Every file in `frontend/` has a Vite-compatible equivalent under `frontend-vite/src/` — verify by listing both and confirming the 15 expected source files (1 shell + 5 shared + 8 pages + main.jsx + styles.css) are present.
  3. `pnpm dev` runs on 5173 with HMR; all 8 pages render identically — confirmed in Task 4.
  4. `pnpm build` produces a static `dist/` Tauri can bundle — confirmed this task.
  </action>
  <verify>
    <automated>cd frontend-vite && pnpm build > /tmp/vite-build.log 2>&1 && test -f dist/index.html && ls dist/assets/index-*.js >/dev/null && ls dist/assets/index-*.css >/dev/null && grep -q './assets/' dist/index.html && ! grep -qE '"/assets/' dist/index.html && test "$(grep -REn '^window\\.|^Object\\.assign\\(window' src 2>/dev/null | grep -v '^#' | wc -l | tr -d ' ')" = "0" && test "$(grep -REn '@babel/standalone|text/babel' . 2>/dev/null | grep -v node_modules | grep -v '/dist/' | grep -v '^#' | wc -l | tr -d ' ')" = "0" && (python3 -m http.server 5174 -d dist > /tmp/vite-dist.log 2>&1 &) && sleep 2 && curl -fsS http://localhost:5174/ | grep -q '<div id="root">' && pkill -f "http.server 5174" || true</automated>
  </verify>
  <done>
    `pnpm build` exits 0; `frontend-vite/dist/` contains `index.html` plus hashed `assets/index-*.js` and `assets/index-*.css`; HTML uses relative `./assets/` paths; serving dist on 5174 renders identically to 5173 and 8090; no `window.*` globals or Babel-standalone references remain in source; `frontend/` is untouched in `git status`. All four ROADMAP success criteria for Phase 1 satisfied.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| npm registry → local node_modules | Untrusted upstream code installs locally; transitive deps run at build time |
| browser → dev server | Vite dev server binds 127.0.0.1:5173; no external network exposure |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-INV01-01 | Tampering | npm install of `react`, `react-dom`, `vite`, `@vitejs/plugin-react-swc` | mitigate | These are first-party, widely-used packages (React/Vite teams). Verified via direct npm registry pages; lockfile (`pnpm-lock.yaml`) commits exact resolved versions so future installs are reproducible. |
| T-INV01-02 | Information disclosure | dev server on 5173 | accept | Bound to localhost only; serves only mock data; same posture as legacy 8090 server |
| T-INV01-03 | Tampering | EDITMODE markers in App.jsx / TweaksPanel.jsx | mitigate | Plan explicitly preserves the `/*EDITMODE-BEGIN*/.../*EDITMODE-END*/` comments verbatim so Claude Design's live-editor remains usable on the ported files |
| T-INV01-04 | Repudiation | legacy `frontend/` accidentally edited | mitigate | Each task ends with `git status frontend/` gate; any drift is reverted before the task is marked done |
| T-INV01-SC | Tampering | npm/pnpm installs of `react`, `react-dom`, `vite`, `@vitejs/plugin-react-swc` | mitigate | Package legitimacy audit: react (Meta, 50M+ DL/wk), react-dom (Meta, paired with react), vite (vitejs/Evan You, 20M+ DL/wk), @vitejs/plugin-react-swc (vitejs org, official Vite plugin). All four are canonical packages — no `[ASSUMED]` or `[SUS]` entries. No human-verify checkpoint required for the install step. |
</threat_model>

<verification>
Full-phase verification (run from `/Users/ace/.invisible-ws/tauri-shell/`):

```bash
# 1. Scaffold and dependencies in place
test -f frontend-vite/package.json && \
test -f frontend-vite/vite.config.js && \
test -d frontend-vite/node_modules && \
test -f frontend-vite/pnpm-lock.yaml

# 2. All 15 source files exist
ls frontend-vite/src/main.jsx \
   frontend-vite/src/App.jsx \
   frontend-vite/src/Icons.jsx \
   frontend-vite/src/Data.jsx \
   frontend-vite/src/AiChat.jsx \
   frontend-vite/src/TweaksPanel.jsx \
   frontend-vite/src/styles.css \
   frontend-vite/src/pages/{Dashboard,Focus,Folders,Relations,Terminals,Tools,Calendar,Analytics}.jsx

# 3. No window globals leaked into the port
test "$(grep -REn '^window\.|^Object\.assign\(window' frontend-vite/src 2>/dev/null | grep -v '^#' | wc -l | tr -d ' ')" = "0"

# 4. No Babel-standalone references
test "$(grep -REn '@babel/standalone|text/babel' frontend-vite/src frontend-vite/index.html 2>/dev/null | wc -l | tr -d ' ')" = "0"

# 5. Dev server smoke
(cd frontend-vite && pnpm dev > /tmp/vite-dev.log 2>&1 &) && sleep 5 && \
  curl -fsS http://localhost:5173/ | grep -q '/src/main.jsx' && \
  ! grep -E 'Failed to resolve|plugin:vite:import-analysis' /tmp/vite-dev.log && \
  pkill -f vite

# 6. Production build smoke
(cd frontend-vite && pnpm build) && \
  test -f frontend-vite/dist/index.html && \
  ls frontend-vite/dist/assets/index-*.js >/dev/null && \
  ls frontend-vite/dist/assets/index-*.css >/dev/null && \
  grep -q './assets/' frontend-vite/dist/index.html

# 7. Static-serve parity
(cd frontend-vite && python3 -m http.server 5174 -d dist > /tmp/vite-dist.log 2>&1 &) && sleep 2 && \
  curl -fsS http://localhost:5174/ | grep -q '<div id="root">' && \
  pkill -f "http.server 5174"

# 8. Legacy untouched
test -z "$(git status --porcelain frontend/)"
```

Manual (covered by Task 4 checkpoint): visual parity at 1200x800 across all 8 pages and every Tweaks combination.
</verification>

<success_criteria>
All four ROADMAP success criteria satisfied:

1. ✓ `frontend-vite/` is a Vite + React 18 + TypeScript-optional project (TypeScript NOT introduced per CONTEXT — JSX only).
2. ✓ Every file in `frontend/` has a Vite-compatible equivalent under `frontend-vite/src/` (5 shared modules + 8 pages + styles.css + main.jsx + index.html + vite.config.js + package.json).
3. ✓ `pnpm dev` launches on 5173 with HMR; all 8 pages render identically to 8090 (verified at the Task 4 checkpoint).
4. ✓ `pnpm build` produces `dist/` with relative-path assets, ready for Tauri Phase 2 to consume via `frontendDist: ../frontend-vite/dist`.

Plus:
- ✓ `frontend/` untouched (git status clean).
- ✓ `bin/`, `lib/` untouched (sibling-workstream territory).
- ✓ No `window.*` globals or Babel-standalone references in the port.
- ✓ EDITMODE markers preserved in App.jsx and TweaksPanel.jsx.
</success_criteria>

<output>
Create `.planning/workstreams/tauri-shell/phases/INV-01-vite-migration-of-frontend/INV-01-01-SUMMARY.md` when done. Include:
- Final list of files created (with byte counts for sanity).
- The exact Vite + react-dom versions resolved in `pnpm-lock.yaml`.
- Any deviations from the plan (e.g., if an extra dev dep was needed).
- A note that Phase 2 (Tauri shell) is unblocked and can be started with `frontendDist: ../frontend-vite/dist` and `devUrl: http://localhost:5173` in the Tauri config.
</output>
