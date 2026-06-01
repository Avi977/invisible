# invisible — frontend-vite

Vite 5 + React 18.3.1 port of the legacy `frontend/` Babel-standalone React app. Same components, same styles, production build pipeline.

## Develop

```bash
pnpm install
pnpm dev
```

Opens on http://localhost:5173/ with HMR.

## Build

```bash
pnpm build
```

Writes a static `dist/` with **relative** asset paths (`./assets/...`) so the bundle can be opened from any directory — including being embedded by Tauri.

## Preview the build locally

```bash
pnpm preview
```

Serves the build on http://localhost:5174/.

## Used by Tauri (Phase 2)

`src-tauri/tauri.conf.json` will set:

```jsonc
{
  "build": {
    "frontendDist": "../frontend-vite/dist",
    "devUrl": "http://localhost:5173"
  }
}
```

The Tauri shell consumes the same `dist/` produced here.

## Migration note

The legacy frontend lives at `../frontend/` and is served on port 8090 via `bin/invisible-frontend`. It uses Babel-standalone to compile JSX in the browser at load time. This directory is the production-build Vite port. Both render the same UI; the legacy build is kept as a fallback during Phase 1 / Phase 2 development.
