# Local Brain Router — Design

Date: 2026-08-23
Status: approved by Ace (chat), phase 1–2 in progress

## Goal

Make the local model (RTX 5070 Ti, Ollama) the zero-friction first tier of a
handoff system: every query lands on the local model first, which answers
itself, runs a local tool, or escalates to Claude with packaged context.
Shared memory between both brains.

## Decisions (locked with Ace)

- Entry surfaces: global hotkey overlay (Tauri), terminal `q` command, voice
  hotkey (OpenWhispr). All hit the same router endpoint.
- Handoff: router decides. Question → headless `claude -p` streamed back.
  Real task → Claude Code session with a handoff packet prefilled.
- Models: dual. `qwen3:4b` (warm-pinned, `keep_alive:-1`, `think:false`)
  classifies routes; `qwen3:30b-a3b` (fallback `qwen3:14b`) answers local
  queries.

## Architecture

New module `lib/api/router.py` in the invisible repo, wired into
`bin/invisible-dashboard` `do_POST` like every other endpoint.

```
POST /api/v1/router/ask
  {message, project_id?, history?, force?, humor_level?}
        │
        ▼
  qwen3:4b classify (strict JSON, think:false)   ← skipped when force set
        │
        ├─ local          → ai.chat_handler (answer model + memory hits)
        ├─ claude         → chat.chat_handler (`claude -p`, packet in prompt)
        ├─ session        → packet file under $INVISIBLE_HOME/handoffs/,
        │                    response carries path + launch command
        └─ classify fails → default local (never block on the router brain)
```

Response: `{route, confidence, text, model, provider, cost, usage, memory_used}`.

## Reused (not rebuilt)

- `lib/api/ai.py` — local Ollama chat (`/api/v1/ai/chat`)
- `lib/api/chat.py` — headless `claude -p` proxy with stdin anti-injection
- `lib/hermes_bridge.py` — memory search/write
- `lib/api/handoff.py` — packet building precedent
- `src-tauri/` shell — overlay host (phase 3)
- `vendor/openwhispr` — voice (phase 5)

## Memory

- Router injects top-5 hermes memory hits into every prompt (local and
  escalated). Failure to reach hermes is non-fatal.
- Phase 4: post-exchange one-line summary written back via `qwen3:4b`;
  Claude Code memory dirs indexed read-only into hermes search.

## Build order

1. Runtime: `ollama serve` headless (tray app has a startup icon bug),
   scheduled task autostart, warm-pin 4b, pull 30b-a3b.
2. `router.py` + dashboard wiring + `q` PowerShell function. Usable day 1.
3. Tauri global-shortcut overlay (Alt+Space) → router endpoint.
4. Memory write-back loop + Claude memory indexing.
5. Voice hotkey → OpenWhispr → router.

## Testing

`lib/api/test_router.py` mirroring `test_chat.py`: all subprocess/HTTP
mocked. Covers: force override, classify JSON parsing, classify-failure
fallback to local, escalation packet content, session packet path safety
(slug validation, no traversal).

## Security

- Router never puts user input into argv (inherits chat.py contract).
- Session packet filenames are server-generated (timestamp), project slug
  validated by `handoff._valid_slug` pattern.
- Loopback-only, existing dashboard auth applies.
