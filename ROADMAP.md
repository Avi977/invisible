# Roadmap

The phased plan to move `invisible` from "rich CLI scaffolding" to "shipped
Windows desktop app with a unified VPS connection". Each phase ends with a
concrete shippable artifact and an updated `CHANGELOG.md`.

---

## Phase 0 — Repo bootstrap [in progress]

- [x] `git init`, public GitHub repo
- [x] `.gitignore`, `.env.example`, `invisible.toml.example`
- [x] `README.md` + `CHANGELOG.md` + `ROADMAP.md`
- [x] Conventional-commits changelog generator + pre-push hook
- [ ] CI: lint + import-smoke on push (GitHub Actions)
- [ ] `invisible-doctor` green on a fresh clone

**Exit criteria:** a teammate (or a fresh laptop) can `git clone` and reach a
working `invisible-doctor` in under 5 minutes.

---

## Milestone M1 — Frontend wiring (6 parallel workstreams)

The Claude Design React frontend landed 2026-05-26 with eight working pages
running on mock data. Milestone M1 wires five of those pages to real backend
data and migrates the desktop shell to Tauri. The work is split into **6
parallel workstreams** under `.planning/workstreams/`, designed so six Claude
sessions can ship them in parallel with one trivial merge:

| WS | Owns | Wires |
|----|------|-------|
| `dashboard-wiring`     | `lib/api/projects.py`                   | Dashboard page → real projects |
| `ai-bubble`            | `lib/api/chat.py`                       | AI bubble → `claude -p` proxy |
| `folders-3source`      | `lib/api/tree_{local,vps,repo}.py`      | Folders → live 3-source trees |
| `terminals-pty`        | `bin/invisible-pty`, `lib/pty_server.py`| Terminals → 6 real PTYs over WebSocket |
| `analytics-aggregator` | `lib/api/analytics.py`                  | Analytics → real Notion review data |
| `tauri-shell`          | `src-tauri/`, `frontend-vite/`          | Production Tauri shell + Vite bundle |

The Tools / Relations / Calendar pages stay on mock data through M1 and
are wired in M2.

Run `gsd-sdk query workstream.list --raw --cwd .` from `~/.invisible` to
see status. Each workstream has its own `ROADMAP.md` under
`.planning/workstreams/<name>/`.

---

## Phase 1 — Operational baseline

Prove the existing scaffolding actually runs end-to-end.

- [ ] First orchestrator run: `invisible-review jobslayer` until approved
- [ ] Checkpoint round-trip: run, kill mid-iteration, `--resume` cleanly
- [ ] Notion sync writes a real run row
- [ ] Telegram alerts fire on cap-hit + approval
- [ ] Logs land in `~/.invisible/logs/` (currently 0 bytes)

**Exit criteria:** one complete loop end-to-end, with artifacts visible in
Notion + Telegram + git history of the target repo.

---

## Phase 2 — VPS connection hardening

The VPS link is the keystone. Today `invisible.toml` has `vps.host = ""`.

- [ ] Wire `srv982719` into `invisible.toml`
- [ ] `invisible-server` running as a systemd service on the VPS
- [ ] HTTPS via the existing wildcard cert at `theprofitplatform.com.au`
- [ ] Bearer-token auth (`INVISIBLE_SERVER_TOKEN`) stored in Infisical
- [ ] SSH ControlMaster multiplex so 6 cockpit panes reuse one connection
- [ ] Mosh fallback for flaky links (config toggle already exists)
- [ ] `invisible-vps-handoff` proven on a real running loop

**Exit criteria:** a loop started on Mac finishes on the VPS without
human intervention; the desktop dashboard reflects VPS state in real time.

---

## Phase 3 — Tauri shell + Vite (React)

Replace the `pywebview + pystray` desktop wrapper (`bin/invisible-app`) with
a **Tauri** application loading a **Vite-bundled React 18** frontend. Tauri
gives us a small native binary (~10 MB), a Rust core, and `frontend/` has
already been seeded by the Claude Design handoff — Phase 3 just productionises
it.

- [ ] `frontend-vite/` — port `frontend/*.jsx` (Babel-standalone) to Vite + React 18
- [ ] Scaffold `src-tauri/` with `cargo tauri init`
- [ ] Tauri commands that wrap the existing CLI:
      `run_orchestrator`, `kill_run`, `list_projects`, `tail_log`, `status`
- [ ] System tray with Open / Hide / Quit (parity with pystray today)
- [ ] SSE bridge from `invisible-server` → frontend store
- [ ] Auto-update via Tauri updater (signed manifests)

**Exit criteria:** Tauri app launches, shows the dashboard, and can start /
stop / observe an orchestration loop on Mac. `bin/invisible-app` is then
marked deprecated.

> Phase 3 ships as workstream **`tauri-shell`** in `.planning/workstreams/`.

---

## Phase 4 — File dashboard (three-source tree)

The defining feature of the new UI: a single sorted file panel that fuses
**local**, **GitHub**, and **VPS** filesystems.

```
┌── invisible · file panel ──────────────────────────────────────┐
│ Source ▾  Sort ▾  Filter ▾                                     │
│                                                                │
│  📁 jobslayer                                                  │
│     ├─ 📄 README.md            local · ahead 2 commits         │
│     ├─ 📄 src/main.py          github + local (same)           │
│     ├─ 📄 logs/error.log       vps only · 2.3 MB · 12m ago     │
│     ├─ 📄 .env                 local · gitignored              │
│     └─ 📁 worktrees/feat-x     local · 4 files                 │
└────────────────────────────────────────────────────────────────┘
```

- [ ] **Local indexer:** walks configured project paths, watches via fsnotify
- [ ] **GitHub indexer:** `gh api repos/<org>/<repo>/git/trees/HEAD?recursive=1` per project, cached
- [ ] **VPS indexer:** `find` over rsync-mirrored paths, served by `invisible-server`
- [ ] Merge engine: dedupes by relative path, annotates each entry with its source set
- [ ] Sort modes: name · size · mtime · diff-status · source
- [ ] Filter chips: `local-only` · `vps-only` · `out-of-sync` · `gitignored`
- [ ] Click → open in default editor (local), GitHub web URL (GH), `less` over ssh (VPS)
- [ ] Realtime: SSE-driven diffs so the tree updates without polling

**Exit criteria:** for any configured project, opening the file panel shows
the merged view from all three sources within 1 second, and edits on any
side update the panel within 5 seconds.

---

## Phase 5 — Embedded 6 terminals

The tmux cockpit becomes a first-class pane group inside the Tauri window.

- [ ] xterm.js × 6 panes inside the app (CSS grid layout matching today's tmux)
- [ ] Each pane spawns a backend pty via a Tauri command (or remote via ssh)
- [ ] Pane roles mirror the current cockpit:
  1. `logs`     — `invisible-log` tail
  2. `orch`     — orchestrator REPL
  3. `vps`      — ssh/mosh to `srv982719`
  4. `dashboard`— HTTP client view of `invisible-server`
  5. `gsd`      — `invisible-gsd` picker
  6. `watch`    — `invisible-watch` (project diffs)
- [ ] Resize / drag / fullscreen any pane
- [ ] Session persistence: panes survive app restart (named tmux server backend)
- [ ] Copy-on-select, OSC52 paste

**Exit criteria:** `invisible` (the tmux cockpit command) becomes a fallback
for headless use; the Tauri window is the default surface.

---

## Phase 6 — Windows packaging

Make it a real Windows app, not "WSL with extra steps".

- [ ] Cross-compile Tauri for Windows (`cargo tauri build --target x86_64-pc-windows-msvc`)
- [ ] Code-sign the `.msi` (EV cert decision required)
- [ ] OpenSSH client detection (Win10+ ships it; instruct otherwise)
- [ ] Path normalisation everywhere — replace `~` / `/` assumptions in `lib/config.py`
- [ ] Replace tmux-only paths with cross-platform fallback (or remove tmux dependency from the GUI flow)
- [ ] Tauri auto-updater on a Windows install
- [ ] Smoke test on a clean Windows 11 VM

**Exit criteria:** `invisible.msi` installs cleanly on a fresh Windows 11 box,
launches, connects to the VPS, and the file dashboard works.

---

## Phase 7 — Polish & v1.0

- [ ] First-run wizard (Infisical creds, VPS host, first project)
- [ ] Crash reporting (Sentry or self-hosted)
- [ ] Telemetry opt-in for usage stats
- [ ] Public landing page on `theprofitplatform.com.au/invisible`
- [ ] Demo video

**Exit criteria:** tag `v1.0.0`, publish release with `.msi` + `.dmg` + `.AppImage`.

---

## Out of scope (for now)

- Linux `.deb` / `.rpm` — AppImage only until demand
- Mobile companion app
- Multi-user / team mode (this is a single-operator tool)
- LLM provider abstraction beyond Codex + Claude
