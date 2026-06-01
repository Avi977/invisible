---
phase: INV-01-vite-migration-of-frontend
workstream: tauri-shell
status: complete
verified_date: 2026-05-26
verifier: executor (auto) + operator at human-verify checkpoint
---

# Phase INV-01 — Vite migration of frontend: ROADMAP verification

Walks through each of the 4 ROADMAP success criteria and shows the artifact or command that proves it.

## 1. `frontend-vite/` is Vite + React 18 + TypeScript-optional

**Proof: `frontend-vite/package.json` + `frontend-vite/vite.config.js`**

```bash
$ grep -E '"react"|"vite"|"@vitejs' frontend-vite/package.json
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "vite": "^5.4.0",
    "@vitejs/plugin-react-swc": "^3.7.0"

$ grep -E "from '@vitejs|base:|port:" frontend-vite/vite.config.js
import react from '@vitejs/plugin-react-swc';
  base: './',
    port: 5173,
```

Resolved versions in `pnpm-lock.yaml`: react 18.3.1, react-dom 18.3.1, vite 5.4.21, @vitejs/plugin-react-swc 3.11.0. TypeScript was deliberately NOT introduced per CONTEXT.md — JSX only, matching the legacy stack.

## 2. Every `frontend/` file has a Vite-compatible equivalent under `frontend-vite/src/`

**Proof: `frontend-vite/src/` tree (15 source files)**

```
frontend-vite/src/
├── main.jsx          (createRoot mount of <App/> + styles.css import)
├── App.jsx           (port of frontend/app.jsx — sidebar, router, Tweaks)
├── Icons.jsx         (port of frontend/icons.jsx — `export const I`)
├── Data.jsx          (port of frontend/data.jsx — 5 named exports)
├── AiChat.jsx        (port of frontend/ai-chat.jsx — `export default AIBubble`)
├── TweaksPanel.jsx   (port of frontend/tweaks-panel.jsx — 12 named exports)
├── styles.css        (byte-identical copy of frontend/styles.css)
└── pages/
    ├── Dashboard.jsx   (port of frontend/pages/dashboard.jsx)
    ├── Focus.jsx       (port of frontend/pages/focus.jsx)
    ├── Folders.jsx     (port of frontend/pages/folders.jsx)
    ├── Relations.jsx   (port of frontend/pages/relations.jsx)
    ├── Terminals.jsx   (port of frontend/pages/terminals.jsx)
    ├── Tools.jsx       (port of frontend/pages/tools.jsx)
    ├── Calendar.jsx    (port of frontend/pages/calendar.jsx)
    └── Analytics.jsx   (port of frontend/pages/analytics.jsx)
```

All `window.X = X` globals were replaced with ESM exports. Verified by:

```bash
$ grep -REn '^window\.|^Object\.assign\(window' frontend-vite/src
# (no matches — 0 leaked globals)
```

Plus `frontend-vite/index.html` (the Vite entry), `frontend-vite/vite.config.js`, `frontend-vite/package.json`, `frontend-vite/pnpm-lock.yaml`, `frontend-vite/pnpm-workspace.yaml`, `frontend-vite/.gitignore`, `frontend-vite/README.md`.

## 3. `pnpm dev` on :5173, all 8 pages identical to :8090

**Proof: operator-approved at the human-verify checkpoint on 2026-05-26**

The Task 4 `checkpoint:human-verify` gate required side-by-side comparison at 1200×800 across:
- All 8 sidebar pages (Dashboard, Focus, Folders, Relations, Terminals, Tools, Calendar, Analytics).
- Every Tweaks axis: Accent (Per page / Amber / Cyan), Density (compact / comfy / spacious), Sidebar (expanded / collapsed), Dashboard Layout (bento / grid / kanban / list), Mock data (default / client).
- AI bubble fallback string match (`(couldn't reach the model — try again)` byte-identical in both apps).
- HMR sanity on `Dashboard.jsx`.
- Clean DevTools console on :5173 (React 18 StrictMode warnings excepted).

Operator reply: `approved`.

Dev-server smoke (automated):
```bash
$ curl -fsS -o /dev/null -w '%{http_code}\n' http://localhost:5173/
200
$ curl http://localhost:5173/ | grep '/src/main.jsx'
<script type="module" src="/src/main.jsx"></script>
```

## 4. `pnpm build` produces static `dist/` Tauri can bundle

**Proof: `frontend-vite/dist/index.html` with `./assets/` paths + static-serve smoke on :5174**

```bash
$ cd frontend-vite && pnpm build
✓ 43 modules transformed.
dist/index.html                   0.66 kB │ gzip:  0.37 kB
dist/assets/index-CPENLnjb.css   44.06 kB │ gzip:  8.20 kB
dist/assets/index-Bgrs6aKr.js   250.23 kB │ gzip: 77.06 kB
✓ built in 444ms

$ cat dist/index.html | grep -E 'script|link rel="stylesheet"'
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?..." rel="stylesheet"/>
<script type="module" crossorigin src="./assets/index-Bgrs6aKr.js"></script>
<link rel="stylesheet" crossorigin href="./assets/index-CPENLnjb.css">

$ grep -q './assets/' dist/index.html && echo "POSITIVE PASS"
POSITIVE PASS
$ ! grep -qE '"/assets/' dist/index.html && echo "NEGATIVE PASS"
NEGATIVE PASS

$ python3 -m http.server 5174 -d dist &
$ curl -fsS http://localhost:5174/ | grep -q '<div id="root">' && echo "STATIC-SERVE PASS"
STATIC-SERVE PASS
$ curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:5174/assets/index-Bgrs6aKr.js
200
$ curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:5174/assets/index-CPENLnjb.css
200
```

The `./assets/...` prefix (driven by `base: './'` in `vite.config.js`) is the Tauri-readiness gate — Tauri's resource loader resolves assets relative to the embedded `index.html` location. Phase 2 Tauri config:

```jsonc
// src-tauri/tauri.conf.json (Phase 2 will wire this)
{
  "build": {
    "frontendDist": "../frontend-vite/dist",
    "devUrl":       "http://localhost:5173"
  }
}
```

---

## Commit trail

| Commit    | Task                                                       |
| --------- | ---------------------------------------------------------- |
| `d9dc93f` | Task 1 — bootstrap Vite scaffold                            |
| `f57b943` | Task 2 — port 5 shared modules to ESM                       |
| `25248ff` | Task 3 — port 8 page modules to ESM (PascalCase filenames)  |
| `a14832e` | Summary @ Task 4 human-verify checkpoint                    |
| `f0d692b` | Task 5 — production dist/ verified Tauri-ready              |

All 4 ROADMAP success criteria for Phase 1 (Vite migration of frontend) are satisfied. Phase 2 (Tauri shell) is unblocked.
