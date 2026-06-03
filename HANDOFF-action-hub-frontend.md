# HANDOFF — action hub frontend (resume after `/clear`)

**Date:** 2026-06-02 evening
**Session that produced this:** ~6 hours of autonomous + interactive work
**Status:** ✅ **FRONTEND SHIPPED** (commit `c2e0910`, pushed to main 2026-06-02).
The whole "click-to-act dashboard" feature is now live end-to-end.

## ✅ SHIPPED — what got built (next session can ignore the plan below)

All four pieces + the launcher tweak are done, verified in-browser (Playwright),
and pushed:
- **dashboard.jsx** — each card fetches `/api/v1/projects/<id>/brief` and renders
  up to 5 risk-colored suggestion chips (low=green / medium=amber / high=red),
  `why`+command as tooltip. Bounded poll (6×/~90s, cached) so chips appear as
  background briefs land. Verified: jobslayer card shows its 5 chips.
- **app.jsx** — `navTo(id, projectId, options)` 3rd arg carries
  `{projectId, command, token}`; passed to `<Terminals>` as
  `pendingCommand`/`setPendingCommand`.
- **terminals.jsx** — the focused project pane queues the command and writes it
  to its PTY WebSocket once OPEN, **without a trailing newline** (pre-typed, not
  executed). Verified: click chip → Terminals focuses `local·jobslayer`, command
  sits at the prompt unexecuted, Enter then runs it.
- **bin/invisible-launch** — `--brief/--no-brief` (default on) regenerates briefs
  in the background at startup so chips are warm by first click.
- **Envy branding** (same commit): sidebar eye mark + ENVY wordmark, favicon,
  title. Assets in `frontend/assets/`.

## ✅ ALSO SHIPPED THIS SESSION — design import (commit `c5ababa`, pushed)

Implemented the Claude Design handoff (`design/h/DqXut…`) into the real app:

- **Galaxy relations** (`frontend/galaxy-data.jsx` + rewritten
  `frontend/pages/relations.jsx`): replaced the 3d-force-graph page with the
  design's canvas "app galaxy", wired to the LIVE `/api/v1/relations` graph.
  `window.buildGalaxy(data)` groups real nodes by project into glowing cluster
  cores (invisible 167 + jobslayer 36), turns modules/docs/endpoints into child
  stars over a procedural starfield, samples noisy grep links (~140 cap).
  Drag-orbit / scroll-dive / click-to-fly-in / focused-app isolation all work.
- **Nerd Mode** (`frontend/nerd-mode.jsx`): live-source IDE overlay — file tree,
  syntax highlighting, CSS hot-apply, JSX→localStorage+reload. Opened via the
  header `{ } nerd mode` pill / sidebar `{}` / `Ctrl·Cmd+\``.
- **VFS bootstrap** (`frontend/index.html`): the app now boots by fetching every
  source file as text, applying localStorage overrides, and Babel-transforming
  in ONE shared lexical scope (required for Nerd Mode live-edit). Has a
  top-level error guard. ⚠️ **Because all files share one scope, every new
  top-level identifier in `frontend/**.jsx` must be globally unique** — this
  session had to dedupe `API_BASE`/`getToken`/`fmtH` collisions the old
  static-`<script>` loader had hidden.

All verified in Playwright: clean boot (0 console errors), all 8 pages render,
galaxy + nerd mode + action-hub chips + Envy branding all working together.

Everything below is the ORIGINAL plan, kept for reference only.

---

**Status (original):** backend half of the "click-to-act dashboard" feature is **shipped**; frontend half is the only thing left.

## What you're walking into

The user wants the Dashboard to be the entry point for daily work. Each project card should show 3–5 AI-suggested actions; clicking an action routes to that project's terminal pane with the command **pre-typed but unexecuted**. The user reviews + presses Enter.

The backend ships this entirely — there is a working `/api/v1/projects/<id>/brief` endpoint that returns suggestions, and the per-project storage / CLI / claude-driven generator are all in place. The frontend just needs to consume the API and wire the click.

## The arc of tonight's session (so you understand what's already there)

Earlier in the night (different sessions/commits):
- 8 PRs merged to `main` (#7–#14): M2 backend workstreams (analytics, calendar, tools, relations, vps-connection) + tauri-shell + tauri-windows + ci-and-onboarding.
- Two CORS / data-jsx merge bugs from the integration were found + fixed by driving every page in Playwright.
- `bin/invisible-launch` + `bin/invisible-quit` shipped as the daily-use entry point.
- The Tauri shell (Invisible.app) was honestly flagged as still showing mocks because frontend-vite/ was never migrated by any M1/M2 workstream — that's M3 work, **not in scope tonight**.

Earlier in **this** session (last hour or so):
- Added a `motorcycle-tyres` project (nopCommerce on srv982719:/home/avi/motorcycle_tyres). Dashboard "Terminal" button on its card → SSH lands in the project dir on the VPS. Pattern: `~/.ssh/config` Host alias with `RemoteCommand cd … && exec $SHELL -l`, plus `[[terminals]]` block in `invisible.toml`, plus a `project_id` on the matching `PTY_PANES` row in `frontend/pages/terminals.jsx`.
- Made the Relations graph 3D via `3d-force-graph@1.73.4` from unpkg (bundles three.js). All interactions work: drag = orbit, scroll = zoom, click node = camera-fly-to, hover = dim non-neighbours.
- Fixed jobslayer Terminal button → opens a local shell `cd`'d into `~/Projects/jobslayer` via a new `[[terminals]]` block with `kind = "bash"`, `cwd = "~/Projects/jobslayer"`.
- **Shipped the entire backend of the action hub feature** — that's this handoff.

Commits to know about (newest first):
- `d48be7e` feat(brief): per-project storage + claude-driven action suggestions API ← **read this commit message in full, it documents the backend**
- `783d0b4` fix(terminals): jobslayer pane spawns a shell in ~/Projects/jobslayer
- `1a06cfb` feat(relations): 3D force-directed graph
- `f921ffc` docs: invisible.toml.example pattern doc
- `310af96` feat: motorcycle-tyres project click→SSH
- `61113e3` feat: bin/invisible-launch + bin/invisible-quit
- `cc2f168` fix: 2 bugs from M2 merge conflicts (ANALYTICS undef, SSE CORS)

## What's already shipped — the backend you'll consume

### Storage (working)

`~/.invisible/projects/<slug>/`:
- `context.md` — cumulative project understanding (long-lived, you edit it manually OR claude refreshes it nightly when that's wired)
- `log/YYYY-MM-DD.md` — daily activity log (append-only)
- `backups/context-<ts>.md` — snapshots before context rewrites
- `suggestions.json` — current AI-suggested action list

Helper: `lib/project_store.py` — all read/write/append API, atomic writes, slug validated against `^[a-z0-9_-]{1,64}$`.

### CLI (working)

```bash
bin/invisible-brief                       # all projects, parallel
bin/invisible-brief --project jobslayer   # one project
bin/invisible-brief --model claude-haiku-4-5 --timeout 30
```

For each project: gathers `context.md` + last 7 days of logs + last 20 git commits + `git status` → builds a structured prompt → calls `claude -p --model claude-sonnet-4-6 --output-format json` → parses the JSON array out of the reply (tolerates ```json fences) → writes `suggestions.json` atomically.

Already-tested output for jobslayer (from `suggestions.json`):

```json
[
  {"title": "Read the pause-work notes for the exact blocker",
   "command": "cat ~/Projects/jobslayer/.planning/phases/01/PAUSE.md",
   "why": "The last commit says 'blocked on Infisical admin auth' — reading the pause notes surfaces the exact step needed to unblock.",
   "risk": "low"},
  {"title": "Push 61 local commits to remote backup",
   "command": "git -C ~/Projects/jobslayer push origin main",
   "why": "61 commits exist only locally; a disk failure loses all of Phase 1 work. Push before doing anything else.",
   "risk": "medium"},
  ...
]
```

### API endpoints (working — wired into `bin/invisible-dashboard`)

**`GET /api/v1/projects/<id>/brief`** — returns:

```json
{
  "project": "jobslayer",
  "context": "<4KiB tail of context.md or ''>",
  "context_chars": 12345,
  "today_log": "<today's log or ''>",
  "recent_log": "<4KiB tail of last 7 days concatenated>",
  "recent_log_chars": 4567,
  "suggestions": [{"title", "command", "why", "risk"}, ...],
  "generated_at": "2026-06-03T03:42:34Z"  // or null if never briefed
}
```

**`POST /api/v1/projects/<id>/log`** — body `{entry: str, source: "user"|"claude"|"system"}` — appends timestamped section to today's log. 8 KiB cap.

Both endpoints verified live with `python3 -c "urllib.request..."` — see commit `d48be7e` message.

Path-param dispatch lives in `bin/invisible-dashboard` (`do_GET` for `/brief`, `do_POST` for `/log`). Not in the `ROUTES` dict (exact-match only). `lib/api/brief.py` exposes `handle_brief_get(handler, project_id)` and `handle_log_post(handler, project_id, payload)`.

## The frontend work to do (~1.5 hours, 3 files)

### Goal

1. Each project card on Dashboard shows the suggestion chips
2. Clicking a chip routes to Terminals page **AND** pre-types that chip's `command` into the project's focused PTY
3. **No auto-Enter** — the command shows up at the prompt unexecuted; user reads + presses Return manually (this is the explicit UX choice the user made when I asked)
4. `bin/invisible-launch` runs `bin/invisible-brief` in the background at startup so chips are populated by the time the user clicks around

### File 1 — `frontend/pages/dashboard.jsx`

Current state (read first):
- Per-project card renders project name, status, summary, todos, progress bar
- Action button row at the bottom: `Tools / Terminal / Focus` — these call `navTo("tools", p.id)` / `navTo("terminals", p.id)` / `navTo("focus", p.id)`
- `navTo` is passed in as a prop from `frontend/app.jsx`

What to add:
- After the action button row, render a chip list of suggestions fetched from `/api/v1/projects/<p.id>/brief`. Match the existing chip aesthetic (see `.chip` class in `styles.css` if it exists; or model it on the legend-row pattern used in `frontend/pages/relations.jsx`).
- On mount per card: `fetch("/api/v1/projects/" + p.id + "/brief")` → set state to the suggestions array. Handle loading + empty (no chips shown) + error (also no chips, log error to console). Use `RELATIONS_API_BASE`-style constant `BRIEF_API_BASE = "http://127.0.0.1:8765"`.
- Cache per-card: don't re-fetch on every Dashboard re-render. Use a ref or useState initialized to null + fetch only when null.
- Each chip is a button:
  - Visual: small rounded pill with `title`, color-coded by `risk` (low=green-ish, medium=amber, high=red — match existing color palette). Tooltip shows `why`.
  - Click handler: `navTo("terminals", p.id, { pendingCommand: chip.command })` ← note the 3rd argument; `navTo` currently takes 2.

### File 2 — `frontend/app.jsx`

Extend `navTo` (currently `(id, projectId = null)`) to accept a third options object:

```jsx
const [pendingCommand, setPendingCommand] = useStateApp(null);

const navTo = (id, projectId = null, options = null) => {
  setPageId(id);
  if (projectId) setSelectedProject(projectId);
  if (options?.pendingCommand) {
    setPendingCommand({
      projectId,
      command: options.pendingCommand,
      // Generate a unique token so the Terminals page can detect "this
      // is a new request" even if the same chip is clicked twice.
      token: Date.now() + Math.random(),
    });
  }
};
```

Pass `pendingCommand` + `setPendingCommand` as props to the Terminals page (around line 159, where `<Terminals>` is rendered).

### File 3 — `frontend/pages/terminals.jsx`

The page already has `PTY_PANES` with `project_id` linkage and `findIndex(p => p.project_id === selectedProject)` for auto-focus (lines 220-227). The PTY connection happens via WebSocket in `TerminalPane` (line 88).

What to add:
- New prop `pendingCommand` (the `{projectId, command, token}` object) + `setPendingCommand` (so the page can clear it after consuming).
- A useEffect inside Terminals (NOT inside TerminalPane — the page coordinates which pane should consume the command) that:
  - When `pendingCommand` changes AND has a non-null `command` AND `pendingCommand.projectId === selectedProject` (or null if generic) AND the focused pane matches → send the command via that pane's WebSocket as input bytes.
  - Then clear: `setPendingCommand(null)`.
- The WS-write happens in TerminalPane. Easiest pattern: lift a `commandToInject` prop on each TerminalPane. When the focused pane's `commandToInject` becomes non-null, its useEffect on `commandToInject` writes the bytes to its WebSocket (`socketRef.current?.send(command)`) **without** appending `\n` or `\r` so the shell doesn't execute it.
- Read the existing PTY WS code in `frontend/pages/terminals.jsx` first — there's already a `socketRef` or equivalent that handles xterm input.

### File 4 — `bin/invisible-launch`

Add a line that runs `bin/invisible-brief` in the background after the 3 daemons bind:

```bash
# After the 3 wait_for_port checks succeed:
echo "▶ Generating per-project briefs in background…"
"$ROOT/bin/invisible-brief" --quiet > "$LOGDIR/brief.log" 2>&1 &
BRIEF_PID=$!
```

Don't wait for it (briefs take 30-90s per project; the user shouldn't be blocked). Add `--brief / --no-brief` flag or default to running it; the user's choice — default to running.

The cleanup trap should NOT kill `BRIEF_PID` since brief is a one-shot script that exits on its own. (Or do kill it on exit — your call. Killing is safer if launcher exits mid-brief.)

## Verification recipe

```bash
# 1. Generate fresh suggestions (~45s/project)
cd ~/.invisible
INVISIBLE_HOME=$(pwd) ./bin/invisible-brief --project jobslayer

# 2. Confirm the API returns them
curl -s http://127.0.0.1:8765/api/v1/projects/jobslayer/brief | python3 -m json.tool | head -30

# 3. Restart daemons via launcher
./bin/invisible-quit
./bin/invisible-launch --no-browser &

# 4. Drive in Playwright (kill stale chrome first: pkill -f ms-playwright)
#    Navigate to http://127.0.0.1:8090/
#    Confirm Dashboard renders chip list under each card
#    Click a chip → routes to Terminals + the command shows up at the prompt
#    Verify shell hasn't executed it (no output from the command)
#    Press Enter manually → command runs
```

## Open design choices to remember

- **No auto-Enter.** The user explicitly chose "pre-type, don't auto-execute" when I asked. The pre-typed text shows at the prompt; user reviews + presses Return.
- **Model = claude-sonnet-4-6.** The user picked it over Haiku/Opus. Already wired as the default in `bin/invisible-brief --model`.
- **Suggestions cap = 5.** Hard-coded in the prompt ("3-5 concrete next actions"). The frontend should be defensive against more or fewer (render whatever the API returns).
- **Risk color coding** — pick a scheme that matches the rest of the UI. Project colors come from a 6-element deterministic palette in `lib/api/projects.py::_color_for`; risk colors don't need to overlap.

## Stuff explicitly **not** in scope for the next session

- Nightly context refresh (cron / launchd). The backend has `bin/invisible-brief` ready to be cron'd; user can do it themselves with `launchctl` later, or you can wire a plist if they ask.
- Claude auto-updating `context.md` mid-session. Too risky without a more thought-out design. The `POST /api/v1/projects/<id>/log` endpoint exists for ad-hoc entries.
- Backups beyond what's already there (context.md gets backed up on every `write_context` with `backup=True`, which is the default).
- The frontend-vite / Tauri migration. Still M3 work.

## Daemons running right now

The launcher is alive in the background (PIDs `77013` dashboard, `77014` frontend, `77015` pty). They'll get killed on system reboot or if the launcher is killed. To stop manually:

```bash
cd ~/.invisible && ./bin/invisible-quit
```

## Key files for your fresh-context reading list

```
~/.invisible/HANDOFF-action-hub-frontend.md    ← this file
~/.invisible/lib/project_store.py              ← storage helper
~/.invisible/bin/invisible-brief               ← claude-driven generator
~/.invisible/lib/api/brief.py                  ← API endpoint impls
~/.invisible/bin/invisible-dashboard           ← path-param dispatch (look at do_GET around line 405, do_POST around line 492)
~/.invisible/frontend/pages/dashboard.jsx      ← add chip rendering here
~/.invisible/frontend/app.jsx                  ← extend navTo here
~/.invisible/frontend/pages/terminals.jsx      ← pre-type into focused pane here
~/.invisible/bin/invisible-launch              ← background brief invocation here
```

Read in that order. The first three are already-written; the last four are what you'll touch.
