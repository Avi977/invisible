# invisible

A personal multi-agent cockpit. Orchestrates Codex and Claude in turn-taking
loops against your projects, with checkpoints, context budgeting, VPS handoff,
Notion sync, Infisical-backed secrets, Telegram alerts, and a tmux-based
6-pane terminal cockpit.

> Status: **pre-1.0, scaffolding stage.** The CLI surface is built out; the
> first orchestrator run, the Tauri UI shell, and the unified file dashboard
> are tracked in [ROADMAP.md](./ROADMAP.md).

---

## What it does

**Orchestrator loop.** Codex writes, Claude reviews. The loop continues until
the reviewer approves, the iteration cap is hit, or the context budget
crosses 70% — at which point feedback history is compressed before the next
turn. Every turn writes a `.invisible-checkpoint.json` to the feature
worktree so a run can resume on another machine.

**VPS handoff.** A long-running task can be pushed to your VPS mid-flight:
`invisible-vps-handoff <project>` pushes the branch, ssh's into the box, and
resumes the loop from the checkpoint. The 6-pane cockpit keeps a live mosh
session to the same host.

**Secrets via Infisical.** A tiny `.env` holds only the three Infisical
bootstrap creds; everything else is fetched from the vault at startup so the
same code runs identically on every machine.

**Surfaces.**
- `invisible` — 6-pane tmux cockpit (logs, orchestrator, ssh, dashboard, GSD, watch)
- `invisible-app` — native desktop wrapper (currently pywebview + pystray; migrating to Tauri)
- `invisible-dashboard` — local HTML dashboard on `127.0.0.1:8765`
- `invisible-server` — VPS-side daemon serving the same dashboard remotely

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Desktop shell (Tauri — planned; pywebview today)               │
│  ┌─────────────┐  ┌──────────────────┐  ┌─────────────────────┐ │
│  │ File panel  │  │ Dashboard (HTML) │  │ 6 xterm.js terminals│ │
│  │ Local·GH·VPS│  │ runs · projects  │  │ logs · ssh · etc.   │ │
│  └─────────────┘  └──────────────────┘  └─────────────────────┘ │
└────────────────────────┬────────────────────────────────────────┘
                         │  HTTP + SSE  (bearer auth)
┌────────────────────────▼────────────────────────────────────────┐
│  invisible-dashboard  (local, 127.0.0.1:8765)                   │
│  invisible-server     (VPS, https://invisible.your-domain)      │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  Orchestrator (lib/orchestrator.py)                             │
│    Codex turn ──▶ git diff ──▶ Claude review ──▶ approve/retry  │
│         ▲                                          │             │
│         └──────────  checkpoint.json  ◀────────────┘             │
└─────┬──────────┬──────────┬──────────┬──────────┬───────────────┘
      │          │          │          │          │
   Infisical  Notion    Telegram   Git/worktrees  Logseq vault
```

`lib/` modules: `orchestrator`, `runners` (subprocess wrappers for codex/claude),
`worktree`, `checkpoint`, `config`, `infisical`, `notion`, `markdown_vault`,
`telegram`, `dashboard_render`, `server_store`.

`bin/` CLI tools (28): `invisible`, `invisible-app`, `invisible-bootstrap-notion`,
`invisible-cleanup`, `invisible-dashboard`, `invisible-doctor`, `invisible-gsd`,
`invisible-health`, `invisible-history`, `invisible-log`, `invisible-new`,
`invisible-ps`, `invisible-recent`, `invisible-review`, `invisible-secrets`,
`invisible-server`, `invisible-ship`, `invisible-standup`, `invisible-status`,
`invisible-update`, `invisible-vps-handoff`, `invisible-watch`.

---

## Setup

**1. Clone into `~/.invisible`:**

```bash
git clone https://github.com/<you>/invisible.git ~/.invisible
cd ~/.invisible
```

**2. Copy the config templates and fill them in:**

```bash
cp .env.example .env
cp invisible.toml.example invisible.toml
$EDITOR .env             # paste your Infisical bootstrap creds
$EDITOR invisible.toml   # add your VPS host + projects
```

**3. Install Python deps:**

```bash
python3 -m pip install --user pywebview pystray Pillow tomli
# (tomli only needed on Python < 3.11)
```

**4. Install git hooks (auto-regenerates CHANGELOG on commit):**

```bash
./scripts/install-hooks.sh
```

**5. Put `bin/` on your PATH:**

```bash
echo 'export PATH="$HOME/.invisible/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**6. Verify:**

```bash
invisible-doctor   # checks Python deps, Infisical reachability, git, tmux
```

---

## Usage

**Open the cockpit:**

```bash
invisible                       # 6-pane tmux session
invisible --project jobslayer   # pre-fills panes with project paths
invisible kill                  # tear down
```

**Run an orchestration loop:**

```bash
invisible-review <project>          # codex ↔ claude until approved
invisible-review <project> --resume # resume from checkpoint
invisible-vps-handoff <project>     # push + resume on VPS
```

**Inspect state:**

```bash
invisible-status        # what's running, where, how many iters left
invisible-history       # past runs across projects
invisible-recent        # recent commits across all configured projects
invisible-log <project> # tail the orchestrator log
```

---

## Commit conventions

This repo uses **Conventional Commits**. The pre-push hook regenerates
`CHANGELOG.md` from git history and blocks the push if it's stale.

```
feat:     a new user-visible feature
fix:      a bug fix
docs:     documentation only
refactor: code change that neither fixes a bug nor adds a feature
perf:     performance improvement
test:     adding or fixing tests
chore:    build/tooling/deps; nothing user-facing
```

To regenerate the changelog manually:

```bash
./scripts/update-changelog.py
```

---

## Roadmap

See [ROADMAP.md](./ROADMAP.md) for the path from "scaffolding" to "shipped
Windows app". Headline next phases:

1. **First operational run** — execute the orchestrator end-to-end against `jobslayer`
2. **Tauri shell** — replace pywebview wrapper with a Tauri (Rust + web) app
3. **Three-source file dashboard** — unified tree across local · GitHub · VPS
4. **Embedded 6 terminals** — xterm.js panes inside the Tauri window
5. **Windows packaging** — signed `.msi` via Tauri bundler

---

## Changelog

See [CHANGELOG.md](./CHANGELOG.md). It is auto-generated from
Conventional Commits.

---

## License

Personal project. No license declared — all rights reserved by the author
until decided otherwise.
