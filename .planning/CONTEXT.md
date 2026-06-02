# Project context — handoff for future sessions

_Generated 2026-06-01 after Milestone M1 partial ship._

## What `invisible` is

A personal multi-agent developer cockpit. Codex + Claude orchestration loop
(`lib/orchestrator.py`) drives project work on local + GitHub + VPS, with
checkpoints, context budgeting, Notion sync, Infisical secrets, Telegram
alerts. The React frontend (eight pages: Dashboard, Focus, Folders,
Relations, Terminals, Tools, Calendar, Analytics) was dropped from Claude
Design 2026-05-26. M1 wired five of those pages to real backend data via
six parallel workstreams.

Repo: `https://github.com/Avi977/invisible` (public). Working dir: `~/.invisible`.

## M1 ship status — what's in `main` today (2026-06-01)

| Workstream | PR | Merged | What it brought |
|---|---|---|---|
| `ai-bubble`          | #1 | ✅ | `lib/api/chat.py`, `/api/v1/chat` proxy → `claude -p`; wired `frontend/ai-chat.jsx` |
| `folders-3source`    | #2 | ✅ | `lib/api/tree_{local,vps,repo}.py`, `/api/v1/tree/{local,vps,repo}`, SSE watcher; wired `frontend/pages/folders.jsx` |
| `tauri-shell`        | #4 | ⚠️ **partial** | Only `frontend-vite/` + planning docs. `src-tauri/` did NOT land — see "Gap 1" below. |
| `terminals-pty`      | #5 | ✅ | `bin/invisible-pty` daemon on `:8091`, `lib/pty_server.py`, xterm.js in `frontend/pages/terminals.jsx` |
| `dashboard-wiring`   | #6 | ✅ | `lib/api/projects.py`, `/api/v1/projects` adapter; wired `frontend/pages/dashboard.jsx` |
| `analytics-aggregator` | — | ❌ **not shipped** | Workstream completed locally but no PR opened — see "Gap 2" below. |

Plus open PR **#3**: `chore: add claude-code-security-review as required PR check` (not blocking).

## M2 ship status — open PRs (started 2026-06-02)

M2 wires the three deferred pages (Tools, Relations, Calendar) plus Tauri Phase 3 / VPS host wiring / CI scaffolding. Six parallel workstreams in `~/.invisible-ws/<name>/` — same pattern as M1.

| Workstream | PR | Merged | What it brings |
|---|---|---|---|
| `calendar-events` | [#9](https://github.com/Avi977/invisible/pull/9) | ⏳ open | `lib/api/calendar.py` (777 lines, stdlib-only) — Notion + iCal + `~/.invisible/events.json` sources, `(title.lower(), start)` dedupe with notion priority, 60s single-flight cache (`threading.Lock`), SSRF/path-traversal/info-disclosure mitigations (ASVS L1). Frontend `calendar.jsx` rewrite — real-data fetch, RFC3339→decimal-hours transform, MiniCal `eventDaysSet` (replacing the `c.d % 3` mock), loading/empty/error states, ESC-dismiss popover, preserved `.week-now` line. Plus a CORS dedupe bugfix in `bin/invisible-dashboard::_send_json` (latent Wave 1 bug surfaced by Wave 2 smoke; benefits all `/api/v1/*` sister routes). gsd-verifier: PASS (8/8 success criteria, 14/14 STRIDE entries mitigated, workstream isolation clean — 9 files changed, all in OWNS / EDITS LIGHTLY / additive scope). |
| `tools-page` | — | ⌛ in flight | n8n-style canvas page |
| `relations-page` | — | ⌛ in flight | Obsidian-style graph page |
| `tauri-windows` | — | ⌛ in flight | Windows `.msi` cross-compile (Tauri Phase 3) |
| `vps-connection` | — | ⌛ in flight | `srv982719` host wiring + systemd `invisible-server` |
| `ci-and-onboarding` | — | ⌛ in flight | Onboarding doc + CI scaffold |

**M2 setup notes** (from `calendar-events` Phase 1 retro):
- Sibling workstream ROADMAPs need `### Phase N:` detail headers (else `gsd-sdk query roadmap.get-phase` returns `malformed_roadmap`). Calendar-events fixed this at planning time; other workstreams may need the same edit before their first `/gsd:plan-phase` succeeds.
- `ci-and-onboarding` was missing STATE.md (auto-created by `state.begin-phase` query if absent; otherwise a minimal one keyed `status: ready_to_execute` works).
- Config has `research: false` and `auto_advance: true` — both apply at workstream level. The plan-phase UI gate also blocks unless `--skip-ui` is passed or UI-SPEC.md exists. For wiring-only phases (M1/M2 pattern), skipping is the right call — sibling shipped workstreams confirm.

## Gap 1 — Tauri Phase 2 (`src-tauri/`) stranded on `ws/tauri-shell`

PR #4's merge commit (`bc23655`) was created at `a6e4007`, the **planning commit** for Phase 2 — _before_ the implementation commits landed. The 10 commits that built the actual Tauri shell are still on `origin/ws/tauri-shell` and never reached main.

Stranded commits (`git log origin/main..origin/ws/tauri-shell --oneline`):

```
4a9e3c5  docs: update CHANGELOG
0c25136  docs(INV-02): record Task 6 self-check in SUMMARY
1e1891f  docs: update CHANGELOG
b6551d0  feat(INV-02): tauri shell with tray + 5 commands + SSE bridge
eb39d5f  fix(tauri): also update tauri.conf.json
0d56203  fix(tauri): beforeDevCommand cwd is project root, not src-tauri/
83d9683  feat(INV-02): SSE bridge with polling fallback + frontend-vite/src/lib/tauri.js
688ad19  feat(INV-02): system tray and close-to-hide window event
016821e  feat(INV-02): five Tauri commands wrapping CLI surface
1b4742a  feat(INV-02): scaffold src-tauri/ Tauri 2.x project
```

63 `src-tauri/` files (Cargo.toml/Cargo.lock, build.rs, tauri.conf.json, capabilities/default.json, icons/, src/{main,lib,commands,sse}.rs) are committed but not in main.

**To recover:**

```bash
gh pr create --base main --head ws/tauri-shell \
  --title "feat(INV-02): Tauri 2.x shell — tray + 5 commands + SSE bridge" \
  --body "Implementation of Phase 2 missed PR #4 (which only included the planning commit at a6e4007)."
```

Verification status before this was stranded was **PASS** (see `.planning/workstreams/tauri-shell/phases/INV-02-tauri-shell/PHASE-VERIFICATION.md` on the branch).

## Gap 2 — `analytics-aggregator` never pushed

The workstream has 5 commits on the **local** `ws/analytics-aggregator` branch (worktree at `~/.invisible-ws/analytics-aggregator`). The implementation is complete and locally verified — but no remote branch exists, no PR was opened.

```
1698c15  docs(INV-01): phase verification PASS — REQ-05 complete
fb20625  docs(INV-01-02): summary — frontend wiring + live UAT + CORS fix complete
aaf14f8  fix(INV-01-02): add CORS header to dashboard JSON/text responses
82138b5  feat(INV-01-02): remove ANALYTICS mock from data.jsx
9d0135d  feat(INV-01-02): wire analytics.jsx to GET /api/v1/analytics with 30s polling
```

**To recover:**

```bash
cd ~/.invisible-ws/analytics-aggregator
git push -u origin ws/analytics-aggregator
gh pr create --base main --title "feat(INV-01): Analytics aggregator — /api/v1/analytics + Analytics page wired"
```

## Local worktrees still alive

```
~/.invisible                            main             (working dir)
~/.invisible-ws/ai-bubble               ws/ai-bubble                (merged, branch deletable)
~/.invisible-ws/analytics-aggregator    ws/analytics-aggregator     ← STRANDED (Gap 2)
~/.invisible-ws/chore-security-review   chore/add-security-review-action (open PR #3)
~/.invisible-ws/dashboard-wiring        ws/dashboard-wiring         (merged, branch deletable)
~/.invisible-ws/folders-3source         ws/folders-3source          (merged, branch deletable)
~/.invisible-ws/tauri-shell             ws/tauri-shell              ← STRANDED (Gap 1)
~/.invisible-ws/terminals-pty           ws/terminals-pty            (merged, branch deletable)
```

The "SHIPPED.md" pattern (e.g. `terminals-pty/SHIPPED.md`) is your convention for marking a workstream as merged. Apply the same to the four merged ones.

**To clean up the merged worktrees:**

```bash
for ws in ai-bubble dashboard-wiring folders-3source terminals-pty; do
  git worktree remove ~/.invisible-ws/$ws
  git branch -D ws/$ws 2>/dev/null
done
```

(Don't run on `tauri-shell` or `analytics-aggregator` until the gaps above are resolved.)

## How to run the app today (from main)

Four daemons + the frontend. All listen on `127.0.0.1`.

```bash
cd ~/.invisible

# 1. dashboard (JSON API for projects / tree / chat / analytics)
./bin/invisible-dashboard --no-auth &              # :8765

# 2. PTY daemon (terminals page WebSockets)
./bin/invisible-pty --port 8091 &                  # :8091

# 3. legacy frontend (Babel-standalone React from `frontend/`)
./bin/invisible-frontend --port 8090 &             # :8090

# Or: the Vite-built React (production) from `frontend-vite/dist/`
cd frontend-vite && pnpm install && pnpm build
python3 -m http.server 8091 -d dist &              # OR Vite preview

# 4. desktop wrapper (pywebview — Tauri shell not yet in main; see Gap 1)
./bin/invisible-app                                # opens native window pointing at :8090
```

Open `http://127.0.0.1:8090/` (legacy) or `http://127.0.0.1:5173/` (Vite dev, if you `pnpm dev` in `frontend-vite/`).

**Stop everything:**

```bash
pkill -f "invisible-dashboard|invisible-pty|invisible-frontend|invisible-app"
```

## Toolchain installed in this environment

| Tool | Version | Installed during |
|------|---------|------------------|
| node | v22.14 | already |
| pnpm | latest (via corepack) | M1 Tauri shell Phase 1 |
| rustc | 1.95.0 | M1 Tauri shell Phase 2 (`rustup`) |
| cargo-tauri | 2.11.2 | M1 Tauri shell Phase 2 |
| codex CLI | 0.130.0 | already; logged in via ChatGPT |
| claude CLI | 2.1.150 | already; logged in via claude.ai (max plan) |
| gh CLI | latest | already; HTTPS auth via stored token |

Run `./bin/invisible-doctor` for live verification of the above.

## Key conventions

- **Conventional Commits**, every commit. Pre-push hook (`.githooks/pre-push`) regenerates `CHANGELOG.md` from history and blocks pushes if it's stale. Run `./scripts/update-changelog.py` if blocked.
- **Self-update commits** are filtered (`scripts/update-changelog.py:SELF_UPDATE_RE`) so the changelog doesn't recursively chase its own updates.
- **Secrets**: `.env` gitignored (bootstrap Infisical creds only). Everything else comes from Infisical at `vault.theprofitplatform.com.au`. Real prod secrets must NEVER reach the repo.
- **GSD workstream pattern**: `.planning/workstreams/<name>/{ROADMAP.md,STATE.md,phases/INV-NN-.../{CONTEXT,PLAN,SUMMARY,VERIFICATION}.md}`. Active workstream tracked in `.planning/active-workstream` (gitignored — per-worktree).
- **Browser automation for UI verification**: drive with Playwright / chrome-devtools-mcp / firecrawl-instruct. Don't hand back manual checklists for things that can be automated. See `~/.claude/projects/-Users-ace/memory/feedback_verify_yourself.md`.

## Where to pick up next

The two gaps above are the obvious resume points. After that:

1. **Tauri Phase 3** — Windows `.msi` cross-compile. Plan lives at `.planning/workstreams/tauri-shell/ROADMAP.md` (Phase 3 not yet planned). Needs `cargo xwin` or a Windows VM.
2. **VPS host wiring** — `invisible.toml` still has `vps.host = ""`. Add `srv982719`, point `invisible-vps-handoff` at it, set up the systemd service for `invisible-server`. Folders/VPS column on the live frontend currently returns 503 with `vps.host not configured`.
3. **M2 — deferred pages** — Tools (n8n canvas), Relations (Obsidian graph), Calendar (✓ PR [#9](https://github.com/Avi977/invisible/pull/9) open as of 2026-06-02 — awaiting merge). Each follows the same workstream pattern; see "M2 ship status" table above for live state.
4. **Operational baseline** — Phase 1 of the user-facing ROADMAP.md ("First operational run against jobslayer") was attempted earlier; the orchestrator ran but the sandbox + auth bugs surfaced. Both fixed, but the run never produced a real commit to jobslayer. Worth re-running.

## Quick orientation for a fresh Claude session

If you're cold-loading this project:

1. Read `.planning/PROJECT.md` for the project's `What This Is` / `Core Value` / requirements.
2. Read `.planning/ROADMAP.md` for the M1 phase plan.
3. Read THIS file (CONTEXT.md) for current state + gaps.
4. Read `.planning/STATE.md` for active milestone position.
5. Check `git log --oneline -20` for recent work.
6. Run `./bin/invisible-doctor` to confirm tooling.

Sibling memories worth reading first if available:
- `feedback_verify_yourself.md` — drive verification with browser automation
- `invisible_app.md` — high-level project memory
- `invisible_workstreams.md` — workstream-pattern memory
