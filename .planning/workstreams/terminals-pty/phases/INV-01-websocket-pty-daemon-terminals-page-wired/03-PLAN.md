---
phase: 01-websocket-pty-daemon-terminals-page-wired
plan: 03
type: execute
wave: 2
depends_on: ["01"]
files_modified:
  - frontend/pages/terminals.jsx
  - frontend/index.html
  - README.md
autonomous: false
requirements: [REQ-04]
must_haves:
  truths:
    - "`frontend/index.html` loads xterm.js core (`xterm@5`), xterm.css, and xterm-addon-fit from unpkg CDN — matching the React/Babel-standalone loading idiom already used for react.development.js."
    - "`frontend/pages/terminals.jsx` no longer references the `TERM_PRESETS` mock array as the source of pane content. The 6 panes are driven by a `PTY_PANES` array of `{id, title, project_color, project_id?}` and each pane mounts a real xterm.js Terminal connected to `ws://127.0.0.1:8091/pty/{id}`."
    - "Typing in a focused pane sends keystrokes over the WebSocket; PTY output streams back and renders in the xterm view in realtime."
    - "Reloading the page reconnects to the same pane ids; the user sees the latest output backlog from the daemon (Plan 02 backlog replay), confirming sessions survive page reload."
    - "Each pane's collapsible context header merges `{goal, activity, next}` from `GET http://127.0.0.1:8091/context/{pane_id}` over the local `PTY_PANES` entry's visual identity (`project`, `color`). When the endpoint returns `{}` the header collapses to the visual identity only — no fake mock content."
    - "WebSocket connect failures (daemon down, refused) surface a one-line in-pane error like `[disconnected — invisible-pty not running on :8091]` rather than a silent black pane."
    - "The page's `Terminals` component still exports `window.Terminals` so `frontend/app.jsx` continues to mount it without changes."
  artifacts:
    - path: frontend/pages/terminals.jsx
      provides: "Rewritten Terminals page that mounts 6 xterm.js panes over WebSocket, with checkpoint-driven context headers"
      contains: "new Terminal(", "addons.fit.FitAddon", "ws://127.0.0.1:8091/pty/", "fetch(`http://127.0.0.1:8091/context/${"
    - path: frontend/index.html
      provides: "xterm.js + addon-fit + xterm.css loaded from unpkg before pages/terminals.jsx"
      contains: "xterm@5", "xterm-addon-fit", "xterm/css/xterm.css"
    - path: README.md
      provides: "One-line Surfaces entry for invisible-pty"
      contains: "invisible-pty"
  key_links:
    - from: frontend/pages/terminals.jsx
      to: "ws://127.0.0.1:8091/pty/{id}"
      via: "new WebSocket(`ws://127.0.0.1:8091/pty/${pane.id}`) inside useEffect on Terminal component mount"
      pattern: "new WebSocket\\(.+8091/pty/"
    - from: frontend/pages/terminals.jsx
      to: "http://127.0.0.1:8091/context/{id}"
      via: "fetch on Terminal mount to populate the ContextHeader's goal/activity/next from real checkpoint data"
      pattern: "fetch\\(.+8091/context/"
    - from: frontend/pages/terminals.jsx
      to: "xterm.js + FitAddon globals"
      via: "window.Terminal / window.FitAddon (UMD globals from unpkg, matching React UMD pattern)"
      pattern: "window\\.Terminal|new Terminal\\("
    - from: frontend/index.html
      to: frontend/pages/terminals.jsx
      via: "<link> + <script> tags loaded BEFORE the type=text/babel terminals.jsx script tag"
      pattern: "xterm@5.*\\.js"
---

<objective>
Wire the Terminals page to the live PTY daemon: replace the hardcoded
`TERM_PRESETS` mock with xterm.js panes connected to `ws://127.0.0.1:8091/pty/{id}`,
load xterm.js from unpkg matching the existing Babel-standalone CDN pattern,
populate each pane's collapsible context header from the daemon's
`/context/{id}` endpoint (which reads the orchestrator's checkpoint store),
and add a one-line README entry for the new daemon.

This is the last plan in the phase. It depends on Plan 01 (the daemon must
exist for any WS connection to succeed) and benefits from Plan 02
(reload-survives-disconnect needs Plan 02's grace window), but does NOT
hard-block on Plan 02 — a Plan 03 build is verifiable against Plan 01 alone,
with reload-persistence becoming true once Plan 02 lands.

Purpose: Delivers Success Criteria #2, #5, #6 (and visibly demonstrates #3
once Plan 02 is in).

Output: A live Terminals page where typing `pwd` shows the user's actual cwd,
not the mocked `~/code/echo/ios` string.
</objective>

<scope_note>
Per START_HERE.md's fence list, `frontend/index.html` is not in the explicit
OWNS or EDITS LIGHTLY set for this workstream (it is also not in MUST NOT
TOUCH). For this plan only, treat `frontend/index.html` as an EDITS LIGHTLY
surface restricted to the xterm.js CDN insertion: three `<script>` / `<link>`
tags inside `<head>` (xterm.js core, xterm.css, xterm-addon-fit) and nothing
else. No other markup, no body changes, no script reordering beyond placing
the new tags before `pages/terminals.jsx`.
</scope_note>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/REQUIREMENTS.md
@.planning/workstreams/terminals-pty/ROADMAP.md
@.planning/workstreams/terminals-pty/phases/INV-01-websocket-pty-daemon-terminals-page-wired/01-01-SUMMARY.md
@.planning/workstreams/terminals-pty/phases/INV-01-websocket-pty-daemon-terminals-page-wired/01-02-SUMMARY.md
@START_HERE.md

@frontend/pages/terminals.jsx
@frontend/index.html
@frontend/data.jsx
@README.md

<interfaces>
<!-- Stable contracts you consume. -->

Daemon endpoints (Plan 01 + 02):
- WebSocket: `ws://127.0.0.1:8091/pty/{pane_id}` where pane_id matches `^[a-z0-9_-]{1,32}$`
  Client → daemon: send utf-8 strings of keystrokes (xterm.js onData callback emits these)
  Daemon → client: text frames of utf-8 PTY output (terminal.write(...) accepts these directly)
  Origin header MUST be `http://127.0.0.1:8090` — the browser sets this automatically when the page is served from invisible-frontend on 8090. Foreign origins are rejected with HTTP 403 pre-upgrade.
- HTTP: `GET http://127.0.0.1:8091/context/{pane_id}` → JSON `{goal, activity, next}` or `{}`
  goal: string (orchestrator task); activity: list[{c, k}]; next: list[string]

Existing frontend conventions (read but DO NOT modify the structure):
- frontend/data.jsx exposes `TERM_CONTEXT` keyed by pane title. The new page does NOT depend on this — it fetches /context/{id} instead. data.jsx STAYS UNCHANGED.
- The Terminals component receives `{projects, selectedProject, setSelectedProject}` from frontend/app.jsx. Same signature must be kept.
- React 18 UMD is already loaded (window.React, window.ReactDOM).
- xterm.js distributes a UMD build that registers `window.Terminal`. xterm-addon-fit registers `window.FitAddon`.

Files this plan must NOT modify:
- frontend/data.jsx (DATA_SETS / TERM_CONTEXT mock — used by other pages; leave in place even though terminals.jsx stops referencing it)
- frontend/app.jsx, frontend/ai-chat.jsx, frontend/styles.css unless absolutely required (styles.css gets a tiny xterm container CSS rule — see Task 2; this is a controlled exception)
- bin/invisible-dashboard, lib/api/, lib/pty_server.py, bin/invisible-pty
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Load xterm.js from unpkg in frontend/index.html and rewrite terminals.jsx</name>
  <files>frontend/index.html, frontend/pages/terminals.jsx</files>
  <read_first>
    - frontend/index.html (full file — script tag order matters; xterm must load BEFORE pages/terminals.jsx)
    - frontend/pages/terminals.jsx (full file — preserve Terminals export signature + ContextHeader / focusIdx layout AND note the existing `ContextHeader` prop shape: it reads `ctx.color`, `ctx.project`, `ctx.goal`, `ctx.activity`, `ctx.next` from a single merged object)
    - frontend/data.jsx lines 254-358 (TERM_CONTEXT shape — confirms goal/activity/next field names the rewritten header still uses, but now sourced from /context/{id})
  </read_first>
  <action>
    Edit `frontend/index.html`:

    Inside `<head>` (after the Geist fonts stylesheet, before the babel script
    tag), add three new tags loading xterm.js + its CSS + the fit addon from
    unpkg. Use pinned versions:
      - `<link rel="stylesheet" href="https://unpkg.com/xterm@5.3.0/css/xterm.css"/>`
      - `<script src="https://unpkg.com/xterm@5.3.0/lib/xterm.js" crossorigin="anonymous"></script>`
      - `<script src="https://unpkg.com/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js" crossorigin="anonymous"></script>`

    These MUST load before `pages/terminals.jsx`. Do not add `defer` / `async`;
    the existing react UMD scripts also load synchronously.

    Do NOT add `integrity=` hashes — the rest of the page's CDN scripts use
    them but pinning the version + crossorigin attribute is sufficient for now
    (matches the babel script's anonymous crossorigin pattern). Leave a code
    comment `<!-- xterm.js CDN; integrity hashes deferred — pinned version is sufficient for local-only frontend -->` above the new tags.

    Rewrite `frontend/pages/terminals.jsx` entirely. Preserve:
      - The `Terminals` component signature: `function Terminals({ projects, selectedProject, setSelectedProject })`.
      - The `window.Terminals = Terminals` export line at the bottom.
      - The collapsible context header behavior (one expanded, others collapsed; expanding focused header on focus change). The existing `ContextHeader` component's CSS classnames (`term-ctx`, `term-ctx-toggle`, `term-ctx-dot`, `term-ctx-name`, `term-ctx-goal`, `term-ctx-chev`, `term-ctx-body`, `term-ctx-section`, `term-ctx-label`, `term-ctx-text`, `term-ctx-cols`, `term-ctx-list`, `term-ctx-ok/warn/err`) MUST be reused — keep the existing styles.css working untouched.

    Replace:
      - The `TERM_PRESETS` array → a new top-level `PTY_PANES` array of 6
        entries with shape `{id, title, project_color, project_id?}`:
        ```
        { id: "local-1", title: "local · zsh",     project_color: "#5cc8ff", project_id: null     },
        { id: "local-2", title: "local · build",   project_color: "#b794ff", project_id: null     },
        { id: "local-3", title: "local · scratch", project_color: "#f5b343", project_id: null     },
        { id: "vps-srv", title: "vps · srv982719", project_color: "#4ade80", project_id: null     },
        { id: "vps-log", title: "vps · logs",      project_color: "#5ee0c8", project_id: null     },
        { id: "vps-k3s", title: "vps · k3s",       project_color: "#f56fb1", project_id: null     },
        ```
        Pane ids match the daemon's PANE_ID_RE. Title is for display only.
        Whether a given id resolves to bash or ssh is decided server-side
        by `invisible.toml`'s `[[terminals]]` blocks (Plan 02). Document this
        in a comment.

      - The `Terminal` component's mock command-handling switch (`if lower.startsWith("ls")` etc) → a real xterm.js panel:
        - On mount: instantiate `new window.Terminal({ fontSize: 12, fontFamily: 'Geist Mono, ui-monospace, monospace', theme: { background: 'transparent', foreground: '#e5e7eb' }, cursorBlink: true, allowTransparency: true, scrollback: 5000 })` and a `new window.FitAddon.FitAddon()`. `term.loadAddon(fit); term.open(containerRef.current); fit.fit();`
        - Connect WebSocket: `const ws = new WebSocket(\`ws://127.0.0.1:8091/pty/${pane.id}\`)`. On open: `ws.binaryType = 'arraybuffer'` and set a state flag `connected = true`. On message (event.data is string per Plan 01's text frames): `term.write(event.data)`. On close: write a single line `\r\n\x1b[31m[disconnected — invisible-pty not running on :8091]\x1b[0m\r\n` to the terminal. On error: same disconnected message.
        - Forward keystrokes: `term.onData(data => { if (ws.readyState === WebSocket.OPEN) ws.send(data); })`.
        - Resize: on window resize call `fit.fit()`. On unmount close the WS and call `term.dispose()`.

      - The hardcoded `TERM_CONTEXT[preset.title]` lookup → a fetch in
        useEffect on mount: `fetch(\`http://127.0.0.1:8091/context/${pane.id}\`)
        .then(r => r.json()).then(setCtxRaw).catch(() => setCtxRaw(null))`.

        EXPLICIT MERGE STEP (this is the contract bridge between the daemon's
        live fields and the local visual identity):

        When the fetch resolves with non-empty data, build the header context
        as `{ ...response, project: pane.title, color: pane.project_color }`
        before passing to `ContextHeader`. The daemon owns the live fields
        (`goal` / `activity` / `next`); the local `PTY_PANES` entry owns the
        visual identity (`project`, `color`). Concretely:

        ```
        const ctx = (ctxRaw && Object.keys(ctxRaw).length > 0)
          ? { ...ctxRaw, project: pane.title, color: pane.project_color }
          : null;
        ```

        If `ctxRaw` is null (fetch failed) OR `{}` (no checkpoint exists for
        that pane), the header still renders with the `PTY_PANES` identity
        fallback (collapsed mode) — pass `{project: pane.title, color: pane.project_color, goal: '', activity: [], next: []}`
        so the existing `ContextHeader` collapsed-row keeps rendering the dot
        + title, but the expanded body shows no fake mock content. No
        `TERM_CONTEXT` lookup, no synthetic goal/activity/next strings.

    The 1 large + 5 small focused-pane layout (`focusIdx`, `order`, CSS
    classes `term-pane focused / small`, `term-layout`) is preserved. The
    chip-row at the top (`6 sessions · zsh`, project chip, numbered focus
    buttons) is preserved with `PTY_PANES` substituted for `TERM_PRESETS`.

    Drop the `TERM_CONTEXT` import-by-side-effect from data.jsx — data.jsx
    will still export it for other pages, but terminals.jsx no longer reads
    it.

    Per START_HERE.md the daemon must be running on 127.0.0.1:8091 for the
    page to be functional. Document this dependency in a JSX comment block at
    the top of the file:
    `// Requires bin/invisible-pty running on 127.0.0.1:8091. See START_HERE.md.`

    DO NOT touch any of the MUST NOT TOUCH files. DO NOT modify
    `frontend/data.jsx`. Adding a single rule for the xterm host element to
    `frontend/styles.css` is permitted if absolutely needed for layout (set
    `.term-xterm-host { width: 100%; height: 100%; }` and reference it as the
    container className) — keep this rule under 5 lines and add a
    `/* terminals-pty */` comment.
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/terminals-pty &amp;&amp; grep -q 'unpkg.com/xterm@5' frontend/index.html &amp;&amp; grep -q 'unpkg.com/xterm-addon-fit@' frontend/index.html &amp;&amp; grep -q 'xterm/css/xterm.css' frontend/index.html &amp;&amp; grep -q 'PTY_PANES' frontend/pages/terminals.jsx &amp;&amp; ! grep -q '^const TERM_PRESETS = \[' frontend/pages/terminals.jsx &amp;&amp; grep -q 'ws://127.0.0.1:8091/pty/' frontend/pages/terminals.jsx &amp;&amp; grep -q '8091/context/' frontend/pages/terminals.jsx &amp;&amp; grep -q 'window.Terminals = Terminals' frontend/pages/terminals.jsx &amp;&amp; node --check frontend/pages/terminals.jsx 2>/dev/null; SYNTAX_RC=$?; if [ $SYNTAX_RC -ne 0 ]; then python3 -c "import re; src=open('frontend/pages/terminals.jsx').read(); m=re.search(r'window\\.Terminals\\s*=\\s*Terminals', src); assert m, 'no window.Terminals export'; print('JSX sanity OK (node --check declined JSX, sentinel check passed)')"; fi &amp;&amp; echo "all grep gates passed"</automated>
  </verify>
  <done>
    `frontend/index.html` loads xterm + addon-fit + xterm.css from unpkg
    before `pages/terminals.jsx`. The terminals.jsx file no longer declares
    `const TERM_PRESETS = [` (mock array gone), declares `PTY_PANES`,
    contains the `ws://127.0.0.1:8091/pty/` and `8091/context/` URLs,
    preserves the `window.Terminals = Terminals` export, and keeps the
    existing CSS classnames.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add invisible-pty surface line to README and document the page dependency</name>
  <files>README.md</files>
  <read_first>
    - README.md lines 1-80 (the Surfaces section bullet list, line 31 onward)
  </read_first>
  <action>
    Edit `README.md`. Inside the `**Surfaces.**` bullet list (currently 5
    bullets starting at line 32), insert a sixth bullet IMMEDIATELY AFTER the
    `invisible-frontend` bullet:

    `- \`invisible-pty\` — WebSocket PTY daemon on \`127.0.0.1:8091\`. Serves \`ws://127.0.0.1:8091/pty/{id}\` (live bash / ssh shells) + \`GET /context/{id}\` (per-pane checkpoint summary). The React Terminals page connects here.`

    Keep formatting consistent with the surrounding bullets (same backtick +
    em-dash style). Do NOT alter any other bullet. Do NOT add a section
    heading.

    No code, no version, no port-table additions beyond this line. Anything
    more belongs in a separate docs phase.
  </action>
  <verify>
    <automated>cd /Users/ace/.invisible-ws/terminals-pty &amp;&amp; grep -c 'invisible-pty' README.md | awk '{if($1&gt;=1) exit 0; else exit 1}' &amp;&amp; awk '/\*\*Surfaces\.\*\*/,/^---$/{print}' README.md | grep -q 'invisible-pty.*127\.0\.0\.1:8091' &amp;&amp; echo "README surface line OK"</automated>
  </verify>
  <done>
    `README.md` contains exactly one new line about `invisible-pty` inside
    the Surfaces section, mentioning port 8091. No other README sections
    modified.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Manual UAT — Terminals page hosts 6 real shells</name>
  <what-built>
    Frontend Terminals page rewritten to mount 6 xterm.js panes over
    WebSocket. Daemon (`bin/invisible-pty`) ships from Plans 01 + 02 and is
    started by you for this UAT. Pane ids (`local-1` … `vps-k3s`) match the
    daemon's PANE_ID_RE; if no `[[terminals]]` config block exists in your
    `invisible.toml` for an id, the daemon falls back to a default
    plain-bash pane.
  </what-built>
  <how-to-verify>
    1. In one terminal: `cd ~/.invisible-ws/terminals-pty &amp;&amp; bin/invisible-pty
       --port 8091`. Confirm `[invisible-pty] listening on ws://127.0.0.1:8091`.
    2. In a second terminal (or your normal flow): `bin/invisible-frontend`
       and open `http://127.0.0.1:8090/` in the desktop app (or browser).
    3. Click the Terminals tab. You should see 6 xterm.js panes (1 large, 5
       small). Black/transparent terminal background, blinking cursor in the
       focused pane.
    4. In the focused pane, type `pwd` + Enter. The output MUST be your real
       working directory (something like `/Users/ace` or
       `/Users/ace/.invisible-ws/terminals-pty`), NOT the old mock string
       `~/code/echo/ios`.
    5. Type `echo hello_$$` + Enter. The output must include `hello_` + a
       real PID number (proves it's a real shell).
    6. Click a different pane (one of the 5 small ones). It becomes large.
       Type `pwd` there too — also a real path.
    7. Reload the page (Cmd-R / Ctrl-R). The 6 panes reconnect. In the same
       focused pane type `echo $$` — the PID should still match what you
       saw before reload (proves Plan 02's session persistence holds across
       page reload).
    8. Stop the daemon (Ctrl-C in terminal 1). One pane should show the
       red disconnected line: `[disconnected — invisible-pty not running on :8091]`.
       The other panes should also show it.
    9. Verify the context header: click the title/chevron of a focused
       pane's header to expand it. If you have an active worktree with a
       `.invisible-checkpoint.json` matching the pane id's worktree path,
       the goal/activity/next fields should populate. If empty (no
       checkpoint exists), the header may be minimal — that's expected.

    KNOWN LIMITATION TO ACKNOWLEDGE (not a failure):
    The orchestrator checkpoint schema (`lib/checkpoint.py`) does not contain
    literal `current_goal` / `recent_activity` / `next_steps` keys. Plan 01's
    `load_pane_context` maps existing fields (`task` → goal, `feedback_history`
    → activity entries, `last_summary` when verdict is "changes" → next).
    This is the agreed mapping. If you want different mappings, surface that
    as a follow-up — do not block this UAT on it.

    SSH variant check (optional, only if you have srv982719 reachable):
    Add to your `invisible.toml`:
      [[terminals]]
      id = "vps-srv"
      kind = "ssh"
      host = "srv982719"
    Restart the daemon with `--config ~/.invisible/invisible.toml`. Click
    the `vps · srv982719` pane and confirm it drops you into an ssh shell.
  </how-to-verify>
  <resume-signal>Type "approved" once the 6 panes are alive and `pwd` returns a real path, or describe what failed.</resume-signal>
</task>

</tasks>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser → daemon | The Terminals page (served from `http://127.0.0.1:8090`) opens WebSocket + HTTP connections to `127.0.0.1:8091`. The browser provides the `Origin: http://127.0.0.1:8090` header automatically — relied on by Plan 01's check_origin. |
| user-typed keystrokes → PTY | Anything typed in xterm flows verbatim to the shell. This is the entire feature. |
| daemon HTTP `/context/{id}` → page | Cross-origin GET from page (8090) to daemon (8091). CORS allows the page's origin only (Plan 01's HTTP route sets `Access-Control-Allow-Origin: http://127.0.0.1:8090`). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-01 | Spoofing | Page origin from a malicious local site | mitigate | Plan 01's `check_origin` rejects WS upgrades from origins outside `{http://127.0.0.1:8090, http://localhost:8090}`. Plan 03's WS connect URL relies on the browser to send the correct Origin (it does automatically). Verified by Plan 01 Task 3 (c). |
| T-03-02 | Information Disclosure | Untrusted CDN script substitution (xterm.js from unpkg) | mitigate (partial) | xterm version is pinned (`xterm@5.3.0`, `xterm-addon-fit@0.8.0`). `crossorigin="anonymous"` is set on script tags. SRI hashes are explicitly deferred (commented in HTML). Acceptable for a local-only frontend that already loads react + babel without SRI under the same pattern; revisit when the Vite + Tauri migration replaces CDN loading. |
| T-03-03 | Tampering | Pane id from URL query / user-controlled state | mitigate | Pane ids in `PTY_PANES` are a fixed const array; users cannot inject new ids through the page UI in this plan (no "add pane" wiring beyond the existing static `+` button which is non-functional today). The daemon revalidates anyway via PANE_ID_RE. |
| T-03-04 | Denial of Service | Reload storms repeatedly spawning PTYs | mitigate | Plan 02's reconnect path reuses the existing PTY for the same pane id within the grace window; MAX_CONCURRENT_PTYS (32) caps total. 6 panes × N reloads stays well under the cap. |
| T-03-05 | Information Disclosure | Context endpoint exposing checkpoint contents | mitigate | The context route only returns goal/activity/next derived from the local-only worktree's checkpoint. The daemon is bound to 127.0.0.1 (Plan 01 T-01-03), so the only requester is the local user's own browser. |

</threat_model>

<verification>

```bash
# Frontend wiring shape — Task 1's grep gates.
cd /Users/ace/.invisible-ws/terminals-pty
grep -q 'unpkg.com/xterm@5' frontend/index.html
grep -q 'PTY_PANES' frontend/pages/terminals.jsx
grep -v '^//' frontend/pages/terminals.jsx | grep -c 'ws://127.0.0.1:8091/pty/' | awk '{if($1>=1) exit 0; else exit 1}'
grep -q 'window.Terminals = Terminals' frontend/pages/terminals.jsx

# README updated
awk '/\*\*Surfaces\.\*\*/,/^---$/{print}' README.md | grep -q 'invisible-pty.*8091'

# Daemon still functional (Plan 01 + 02 carry the load):
bin/invisible-pty --port 8091 &
PID=$!; sleep 1.5
lsof -nP -iTCP:8091 -sTCP:LISTEN
kill $PID; wait $PID 2>/dev/null
```

Plus the manual checkpoint above. The phase is shippable when the UAT signal is "approved".

</verification>

<success_criteria>

- 6 xterm.js panes mount on the Terminals page and render real bash output.
- Reload reattaches to the same PTYs (requires Plan 02 deployed).
- Daemon-down state shows the in-pane disconnected message, not a silent
  black pane.
- README Surfaces section names `invisible-pty` and port 8091.
- All Plan 01 + Plan 02 verification logs still pass — this plan adds zero
  changes to `lib/pty_server.py` or `bin/invisible-pty`.

</success_criteria>

<output>
Create `.planning/workstreams/terminals-pty/phases/INV-01-websocket-pty-daemon-terminals-page-wired/01-03-SUMMARY.md` when done.
</output>
