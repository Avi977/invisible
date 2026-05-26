# Workstream: terminals-pty (Phase 4 of M1)

> Sister-workstreams: dashboard-wiring, ai-bubble, folders-3source,
> analytics-aggregator, tauri-shell. Fully isolated — new daemon + new
> port + no overlap with `bin/invisible-dashboard`.

## Phases

- [ ] **Phase 1: WebSocket PTY daemon + Terminals page wired**

## Phase Details

### Phase 1: WebSocket PTY daemon + Terminals page wired
**Goal**: The Terminals page hosts 6 real PTYs (local bash shells + ssh-to-VPS variants) over WebSocket. The hardcoded `TERM_PRESETS` const in `terminals.jsx` is replaced by live shells.

**Depends on**: Nothing. Pure parallel. New daemon on port 8091. Zero overlap with other workstreams.

**Requirements**: REQ-04 (see `.planning/REQUIREMENTS.md`)

**Success Criteria** (what must be TRUE):
  1. `bin/invisible-pty` daemon starts on 127.0.0.1:8091, listens for WebSocket connections.
  2. `ws://127.0.0.1:8091/pty/{id}` opens a real bash shell for the given pane id. Typing in the page reaches the shell; output streams back in realtime.
  3. PTY sessions persist across page reload — same pane id reconnects to the existing PTY.
  4. SSH variant: panes can be configured (in `invisible.toml` or via UI) to launch `ssh <host>` inside the PTY on first start.
  5. The project context header per terminal reads `current_goal` / `recent_activity` / `next_steps` from the orchestrator's checkpoint store (`.invisible-checkpoint.json` in each worktree).
  6. `frontend/pages/terminals.jsx` uses xterm.js for rendering (loaded from unpkg, matching the Babel-standalone pattern of the rest of the frontend).

**Plans**: 3 plans
- [ ] 04-01: PTY daemon — `bin/invisible-pty` + `lib/pty_server.py` (Python `websockets` + `ptyprocess`)
- [ ] 04-02: Persistent session store — in-memory dict keyed by pane id; survives reconnects; daemon restart clears
- [ ] 04-03: Frontend wiring — `frontend/pages/terminals.jsx` swaps `TERM_PRESETS` for xterm.js panes connected over WebSocket

## Files this workstream OWNS

- `bin/invisible-pty` (new)
- `lib/pty_server.py` (new)
- `frontend/pages/terminals.jsx` (edit)

## Files this workstream EDITS LIGHTLY

- `README.md` (add a line about `invisible-pty` to the Surfaces section)
- `invisible.toml.example` (optional: add `[[terminals]]` pane definitions)

## Files this workstream MUST NOT TOUCH

- `bin/invisible-dashboard`, `lib/api/`, other pages — none of which this phase needs.

## Verify locally

```bash
invisible-pty --port 8091 &
# In the running app, open Terminals. Type `pwd` in any pane — should
# return your actual cwd, not the mock output.

# Headless smoke:
python3 -c "
import asyncio, websockets
async def t():
    async with websockets.connect('ws://127.0.0.1:8091/pty/test') as ws:
        await ws.send('pwd\n')
        print(await ws.recv())
asyncio.run(t())
"
```

## Resume in a fresh Claude session

```bash
cd /Users/ace/.invisible
gsd-sdk query workstream.set terminals-pty --raw --cwd .
# then in Claude:
/gsd:plan-phase 1
```
