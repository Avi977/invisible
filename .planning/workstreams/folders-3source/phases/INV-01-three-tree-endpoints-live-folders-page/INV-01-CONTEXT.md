---
phase: INV-01-three-tree-endpoints-live-folders-page
workstream: folders-3source
project: invisible
status: shipped
shipped_at: 2026-05-26
merged_at: 2026-05-27
merge_commit: 62a3f40
pr: https://github.com/Avi977/invisible/pull/2
plans: 3
verification: passed (6/6 must-haves)
---

# Phase INV-01 — Three tree endpoints + live Folders page

Context dump for future contributors / future-me. Captures the non-obvious
parts of what was built, the decisions behind the implementation, the
surprises encountered during the parallel-workstream sprint, and the
follow-ups that were intentionally deferred.

## What shipped

A live Folders page (`/folders`) that renders three file trees side-by-side,
replacing the static `FOLDERS` mock in `frontend/data.jsx`:

- **Local** — recursive walk of every `[[projects]]` path in `invisible.toml`,
  with an SSE diff stream so file changes propagate within ~5s
- **VPS** — SSH `find` driven by a ControlMaster-multiplexed channel; graceful
  503 with `{"error":"vps.host not configured"}` when `vps.host=""`
- **GitHub** — `gh api repos/<owner>/<repo>/git/trees/HEAD?recursive=1` with a
  60-second in-process cache

REQ-03 satisfied in full (see `.planning/REQUIREMENTS.md` for the full
acceptance criteria).

## File map

| Layer | Path | Purpose |
|---|---|---|
| Walkers | `lib/api/tree_local.py` (555L) | filesystem walk + SSE diff stream + watchdog/polling fallback |
| Walkers | `lib/api/tree_repo.py` (317L) | gh-CLI subprocess + 60s TTL cache + owner/repo derivation |
| Walkers | `lib/api/tree_vps.py` (410L) | SSH+ControlMaster `find` + 503 graceful degradation |
| Package | `lib/api/__init__.py` | re-exports all 4 submodules (chat from ai-bubble + 3 trees) |
| HTTP | `bin/invisible-dashboard` (513L) | 3 new GET routes + SSE branch + CORS handled globally |
| UI | `frontend/pages/folders.jsx` (252L) | fetch + EventSource + 3-error reconnect ceiling |

## Architecture notes

### CORS posture (frozen for M1)

After the post-ship merge with `ai-bubble`, CORS is **emitted globally** by
the dashboard handler's `end_headers()` override (not per-route). Every
response automatically carries:

- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Methods: GET, POST, OPTIONS`
- `Access-Control-Allow-Headers: Authorization, Content-Type`

The `do_OPTIONS` preflight returns `204 No Content` and additionally adds
`Access-Control-Max-Age: 600` for `/api/v1/tree/*` paths (the tree endpoints
get polled / re-subscribed frequently, so caching the preflight matters).

**Do NOT add explicit CORS headers in route handlers or response helpers
(`_send_json`, `_send_text`, `stream_diffs`)** — duplicate `ACAO` headers
are rejected by the CORS spec and break cross-origin fetches silently.
This is the trap that almost shipped twice during the merge resolution.

### VPS empty-host contract

`tree_vps.walk_all()` returns `tuple[list[dict], int]`. When `vps.host=""`
the tuple is `([VPS_NOT_CONFIGURED], 503)` — the error wrapped in a list
for return-type uniformity.

The route handler in `bin/invisible-dashboard` **unwraps the array to a
bare object** on non-200 status: `_send_json(payload[0], status=status)`.
This delivers the REQ-03-spec-compliant body `{"error": "vps.host not
configured"}` (object, not array) to the browser while keeping the
walker's signature consistent.

### Cross-walker BLOCKER #2 contract

All three walkers MUST return an empty container — never `[None]` — for
an unknown project:

```python
tree_local.walk_all(project='__unknown__') == []
tree_repo.walk_all(project='__unknown__') == []
tree_vps.walk_all(project='__unknown__') == ([], 200)
```

Frontend renderers iterate the result and read `node.name` on each
element. A `[None]` slips past the length check and crashes with
`Cannot read properties of null (reading 'name')`. This was caught
during plan review and is asserted in each walker's verify block;
preserve the assertion when refactoring.

In `tree_vps`, the unknown-project filter runs **before** the empty-host
check so this contract holds regardless of `vps.host` state.

### SSE auth (EventSource gotcha)

`EventSource` has no API to set custom request headers, so it cannot
send `Authorization: Bearer <token>`. The dashboard's
`_token_from_request()` accepts `?token=<T>` as a fallback (preexisting
pattern for HTML pages that you bookmark with the token in the URL).

The frontend builds the SSE URL with `&token=<encoded>` for this reason.
Do not switch to header-based SSE auth without changing the EventSource
client at the same time.

### EventSource error ceiling

`folders.jsx` tracks `consecutiveErrorCount` via `useRef` (not `useState` —
refs avoid a re-render feedback loop). The counter resets on any
successful `snapshot` or `diff` event; after 3 consecutive errors with no
intervening success, the local column flips to `"Local stream
disconnected — check daemon"`.

Without this ceiling, `EventSource` auto-reconnects forever and a dead
daemon looks identical to a healthy daemon with no activity.

Verified at 6036ms after SIGKILL during the puppeteer verification —
that's roughly 3 retry windows at the browser's ~2s default backoff.

### Watchdog is optional

`watchdog` is imported under `try / except ImportError`. When it's
unavailable the daemon falls back to a 2s polling loop (capped at 200
events per cycle to bound storms). This avoids forcing a new pip
dependency on a project with no `pyproject.toml` / `requirements.txt`
yet. If/when a manifest lands, add `watchdog` as a soft dependency and
keep the fallback for portability.

### Input validation is defense-in-depth

Every subprocess/SSH call uses an **argv list** (never `shell=True`,
never f-string interpolation into a command string). On top of that,
inputs are validated **before** the call:

- `tree_repo`: owner/repo against `^[A-Za-z0-9][A-Za-z0-9._-]*$`
- `tree_vps`: host against a hostname regex, paths against an absolute-path
  regex with explicit `..` rejection
- `tree_local`: `repo_path` resolved via `_safe_resolve()` which refuses
  `/`, `$HOME`, and any path that escapes its declared root

This is intentional belt-and-suspenders — argv-based exec already
prevents shell injection, but the regex layer catches malformed config
before it can confuse anything downstream.

## Post-merge integration with ai-bubble

PR #1 (ai-bubble) merged first and added two pieces this branch had to
absorb during the merge:

1. **Global `end_headers()` CORS override** — replaced my per-helper
   explicit CORS. See "CORS posture" above.
2. **POST routing + `do_POST`** — for `/api/v1/chat`. Coexists with my
   GET routes; the only shared surface is the `_send_json` helper and
   the `_auth_ok()` gate, both already designed for multiple consumers.

The merge resolution is captured in commit `3635673`. Three files
conflicted: `bin/invisible-dashboard`, `lib/api/__init__.py`,
`.planning/STATE.md`.

## Operational notes

### Running the daemons against this workstream's code

```bash
# Dashboard — workstream code, real config
INVISIBLE_HOME=/Users/ace/.invisible \
  /Users/ace/.invisible/bin/invisible-dashboard \
  --host 127.0.0.1 --port 8765

# Frontend
INVISIBLE_HOME=/Users/ace/.invisible \
  /Users/ace/.invisible/bin/invisible-frontend \
  --host 127.0.0.1 --port 8090
```

The `bin/invisible-dashboard` script imports `lib/` from its own parent
directory regardless of `INVISIBLE_HOME`, so running the script from a
worktree imports that worktree's `lib/`. `INVISIBLE_HOME` controls where
`invisible.toml`, `run/`, and `.env` are read from.

**Watch out:** if you run a worktree's dashboard with `INVISIBLE_HOME`
pointing at the worktree itself (which has no `invisible.toml`), the
projects list is empty and `/api/v1/tree/local` returns `[]`. Point
`INVISIBLE_HOME` at `~/.invisible` (the canonical config home) when
testing in a worktree.

### Port conflicts during parallel-workstream sprint

The 6-workstream setup means 6 simultaneous Claude sessions, all of
which may try to bind 8765 (dashboard) and 8090 (frontend) for
verification. There is already a long-running main daemon on 8765 in the
typical setup. Pick non-default ports for verification (we used 18765 /
18090 during this work) — note that the `API_BASE` in `folders.jsx` is
hardcoded to 8765, so a port change requires a temp edit (and revert)
to that constant. The REQ-06 Vite/Tauri shell will move this to
build-time env injection.

### Browser MCP contention

Both `chrome-devtools-mcp` and `playwright-mcp` use a single Chrome
profile per MCP server. With 6 parallel sessions, the profile is locked
by whichever session grabbed it first. The fallback used here:
`puppeteer-core` against the system Chrome with a fresh user-data-dir
under `/tmp/`. See `/tmp/inv-verify/render_check.mjs` for the pattern.

### Verification scripts

The two scripts driven during ship sit at `/tmp/inv-verify/`:

- `verify_folders.py` — backend-only browser-equivalent checks (cross-origin
  fetch via Python `http.client`, SSE via raw socket). 18 assertions.
- `render_check.mjs` — headless Chrome render check via puppeteer-core.
  10 visual / DOM / network / console checks.

Both expect the dashboard on `:18765` (or whatever port you started it
on). Keep them around — they make regression checks for any
folders-3source follow-up basically free.

## Known carry-forwards (intentionally deferred)

| Item | Where | Why deferred |
|---|---|---|
| Search input wiring | `folders.jsx` (`q` state) | Visual only for M1; filtering belongs in a follow-up. Marked `// TODO(REQ-03, future)`. |
| Diff-event debounce | `folders.jsx` SSE handler | Each diff re-fetches the full local tree. A `git checkout` in a watched project produces hundreds of diffs / hundreds of fetches. ~5 lines of `setTimeout` would fix it. |
| `watchdog` as a formal dep | `pyproject.toml` (doesn't exist yet) | No project manifest exists. When one lands, add `watchdog>=3.0` and keep the try/except fallback for portability. |
| `API_BASE` hardcode | `folders.jsx:14` | Will move to build-time env injection in the REQ-06 Vite shell. |
| VALIDATION.md (Nyquist dim 8) | phase dir | Workstream config has `research: false`. If/when research is re-enabled, run `/gsd:plan-phase 1 --research` to materialize a validation strategy. |
| Per-workstream `START_HERE.md` cleanup | repo root | Multiple workstreams committed their `START_HERE.md` to `main` (tauri-shell's landed in PR #4). These are scaffolding artifacts and probably belong in `.gitignore`. Mine is preserved locally as `START_HERE.folders-3source.local.md`. |

## Quick-reference: where things live in the merged tree

```
~/.invisible/                                  # main repo
├── bin/invisible-dashboard                    # routes + CORS + do_OPTIONS
├── lib/api/
│   ├── __init__.py                            # re-exports chat + tree_*
│   ├── chat.py                                # ai-bubble (sibling)
│   ├── tree_local.py                          # this phase
│   ├── tree_repo.py                           # this phase
│   └── tree_vps.py                            # this phase
├── frontend/pages/folders.jsx                 # rewritten this phase
└── .planning/workstreams/folders-3source/
    ├── ROADMAP.md
    ├── STATE.md
    └── phases/INV-01-three-tree-endpoints-live-folders-page/
        ├── INV-01-01-local-walker-and-watcher-PLAN.md
        ├── INV-01-01-local-walker-and-watcher-SUMMARY.md
        ├── INV-01-02-vps-and-github-walkers-PLAN.md
        ├── INV-01-02-vps-and-github-walkers-SUMMARY.md
        ├── INV-01-03-frontend-wiring-and-routes-PLAN.md
        ├── INV-01-03-frontend-wiring-and-routes-SUMMARY.md
        ├── INV-01-VERIFICATION.md             # 6/6 must-haves verified
        └── INV-01-CONTEXT.md                  # this file
```

## Phase metrics

- Plans: 3 (one per Wave 1 parallel + one Wave 2 sequential)
- Tasks: 8 total (2 + 2 + 4)
- Files created: 4 (`tree_local.py`, `tree_repo.py`, `tree_vps.py`, `lib/api/__init__.py`)
- Files modified: 2 (`bin/invisible-dashboard`, `frontend/pages/folders.jsx`)
- Lines added: ~2,047 across implementation files; +3,770/-67 in the PR diff
- Commits on the PR: 14
- Plan review cycles: 2 (blocked + warning fixes, then PASSED)
- Verification: PASSED (6/6 must-haves, all REQ-03 acceptance bullets)
- Sibling-boundary violations: 0
