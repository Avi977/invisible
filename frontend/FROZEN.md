# FROZEN — do not add features here

**As of 2026-08-15, `frontend/` (Babel-standalone + React UMD) is frozen.**
`frontend-vite/` is the canonical frontend and ships inside the Tauri shell.

## Why

The two trees forked hard: `Tools`/`Terminals`/`Relations` diverged by 700+
lines each, and the vite side is the one wired to the live backend
(`/api/v1/integrations`, `/api/v1/runs`, `/api/v1/memory/*`,
`/api/v1/handoff/*` via `frontend-vite/src/lib/api.js`). Every feature
landed here has to be ported or thrown away.

## Rules

- Bug fixes only, and only if the same bug exists in `frontend-vite/` —
  fix it there first.
- New pages, endpoints, or styling go to `frontend-vite/` exclusively.
- `bin/invisible-frontend` (:8090) keeps serving this tree as a fallback
  until the Tauri shell is the daily driver, then this directory is deleted.

## Not yet ported (decide before deletion)

- `nerd-mode.jsx` (746 lines) — in-browser JSX IDE, landed in c5ababa
- `galaxy-data.jsx` (197 lines) — galaxy visualization data
