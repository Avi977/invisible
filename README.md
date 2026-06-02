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
- `invisible-frontend` — React UI on `127.0.0.1:8090` (Dashboard, Focus, Folders, Relations, Terminals, Tools, Calendar, Analytics + AI bubble + Tweaks). Source in `frontend/`, dropped from Claude Design 2026-05-26.
- `invisible-pty` — WebSocket PTY daemon on `127.0.0.1:8091`. Serves `ws://127.0.0.1:8091/pty/{id}` (live bash / ssh shells) + `GET /context/{id}` (per-pane checkpoint summary). The React Terminals page connects here.
- `invisible-dashboard` — server-rendered HTML + JSON API on `127.0.0.1:8765` (the React frontend's data backend)
- `invisible-server` — VPS-side daemon mirroring the dashboard remotely

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

### VPS connection setup

The Folders page, Terminals ssh panes, and `invisible-vps-handoff` all reach
the VPS through a single SSH alias `srv982719`. ControlMaster multiplexing
means the 6 panes share one TCP/TLS connection — once the master is up, every
additional `ssh srv982719` reuses it in under 200ms.

**1. Generate a key (skip if you already have `~/.ssh/id_ed25519`):**

```bash
test -f ~/.ssh/id_ed25519 || ssh-keygen -t ed25519 -C "$(whoami)@$(hostname) — invisible vps" -f ~/.ssh/id_ed25519 -N ""
```

The `-N ""` empty-passphrase choice is required for ControlMaster reuse from
non-interactive subprocesses like `lib/api/tree_vps.py`. If you want a
passphrase-protected key, load it via `ssh-agent` once per login session
instead — see `man ssh-agent`.

**2. Add the `Host srv982719` block to `~/.ssh/config`:**

Paste the following manually into `~/.ssh/config` (create it if missing with
`mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/config && chmod 600 ~/.ssh/config`):

```
Host srv982719
  HostName 31.97.222.218
  User avi
  IdentityFile ~/.ssh/id_ed25519
  ControlMaster auto
  ControlPath ~/.ssh/cm-%r@%h:%p
  ControlPersist 10m
```

- `HostName` is the VPS IP; if it changes, only this line moves.
- `IdentityFile` — adjust if your key is at a different path.
- `ControlPath ~/.ssh/cm-...` — make sure `~/.ssh/` exists and is mode 700
  (`mkdir -p ~/.ssh && chmod 700 ~/.ssh` if it doesn't). Do NOT pre-create the
  `cm-*` socket itself — OpenSSH does that on first connection.
- `ControlPersist 10m` — keeps the master open 10 minutes after last use.
  10m is generous enough that 6 panes won't churn the connection; tighten if
  you ssh from untrusted networks.

(You probably already have a `Host vps` block pointing at the same IP — leave
it alone. The new `srv982719` block is in addition to it.)

**3. Copy your public key to the VPS (one-time bootstrap):**

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub srv982719
```

This is the only step that REQUIRES you to type your VPS password — once it
finishes, ControlMaster + key auth handle everything else.

If `ssh-copy-id` is missing (rare on macOS, common on stripped-down servers):

```bash
cat ~/.ssh/id_ed25519.pub | ssh avi@31.97.222.218 'mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
```

**4. Verify:**

```bash
ssh srv982719 echo ok            # should print 'ok' with no password prompt
time ssh srv982719 echo ok       # second invocation: real time under 200ms (ControlMaster reuse)
invisible-doctor                 # [ssh] section: PASS  ssh: srv982719   non-interactive auth works · master=cached
grep '^host =' ~/.invisible/invisible.toml   # after copying .example → invisible.toml and editing: host = "srv982719"
```

**What success looks like (Phase 1 success criteria):**

1. `~/.ssh/config` has a `Host srv982719` block with `ControlMaster auto`,
   `ControlPath ~/.ssh/cm-%r@%h:%p`, `ControlPersist 10m`.
2. `invisible.toml` `vps.host = "srv982719"` and
   `vps.identity = "~/.ssh/id_ed25519"` (or similar).
3. From a fresh shell, `ssh srv982719 echo ok` succeeds without password
   prompt (key-based auth).
4. A second `ssh srv982719 echo ok` runs in under 200ms (reuses the master
   connection).

**Out of repo, by design.** Both `~/.ssh/config` and `~/.invisible/invisible.toml`
(and `~/.invisible/.env`) live OUTSIDE the repo. The repo only ships
`invisible.toml.example` (no secrets), the Setup docs (this section), and the
`bin/invisible-doctor` self-check. Your actual SSH config, real `host` value,
and key material never reach git.

**Two ControlMaster layers (intentional).** The user-shell layer above uses
`ControlPath ~/.ssh/cm-%r@%h:%p` + `ControlPersist 10m` — that socket is for
your interactive `ssh srv982719` from any terminal. Separately,
`lib/api/tree_vps.py` (the dashboard daemon's VPS tree walker) uses
`ControlPath=$INVISIBLE_HOME/run/ssh-cm-%r@%h:%p` + `ControlPersist=60s` for
its subprocess walks. These are DIFFERENT sockets on purpose: if they shared
one, closing your shell would tear down a socket the dashboard is still
holding open. Do NOT "simplify" by collapsing them — both layers must coexist.

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
