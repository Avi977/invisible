---
phase: 01-api-v1-chat-end-to-end
plan: 01
subsystem: backend / chat-proxy
tags:
  - workstream:ai-bubble
  - backend
  - claude-cli-proxy
dependency_graph:
  requires:
    - bin/invisible-dashboard (existing daemon — BaseHTTPRequestHandler)
    - lib/runners.py (canonical claude CLI invocation pattern — mirrored, not imported)
    - claude CLI on PATH, authenticated via `claude login`
  provides:
    - POST http://127.0.0.1:8765/api/v1/chat → {text, usage, cost} (consumed by Wave 2 frontend/ai-chat.jsx)
    - lib.api.chat_handler(request_body) -> (status, body) — pure-function, no side effects beyond subprocess
  affects:
    - bin/invisible-dashboard (added do_POST + one route binding)
tech_stack:
  added: []  # stdlib only — no new deps
  patterns:
    - argv-only subprocess invocation (anti shell-injection)
    - STDIN-fed prompts (user input never enters argv)
    - HTTP error-mapping table on top of one subprocess.run call
key_files:
  created:
    - lib/api/__init__.py
    - lib/api/chat.py
    - lib/api/test_chat.py
  modified:
    - bin/invisible-dashboard
decisions:
  - "Don't import from lib/runners.py: keeps chat module standalone-testable, avoids dragging the orchestrator graph into a unit-test surface."
  - "60s timeout (vs runners.py's 600s for code review): chat is interactive; long stalls are worse UX than a clean 504."
  - "8000-char message cap at handler + 32 KiB body cap at dashboard: defense in depth."
  - "Top-level `cost` field is a duplicate of `usage.cost_usd`: convenience for the bubble's footer; removes one JSON traversal step in the frontend."
  - "Stateless backend: page-session history lives in the frontend (per REQ-02 scope). Backend restart-safety > server-side conversation store."
metrics:
  duration_seconds: 230
  task_count: 2
  test_count: 15
  files_created: 3
  files_modified: 1
completed: 2026-05-26
---

# Phase 01 Plan 01: AI Chat Bubble — Backend Proxy Summary

POST /api/v1/chat on the existing `invisible-dashboard` daemon now shells out to `claude -p --output-format json` (argv-only, STDIN-fed) and returns the parsed reply with token + cost telemetry to any caller.

## What Was Built

**`lib/api/chat.py`** — pure function `chat_handler(request_body: dict) -> tuple[int, dict]`:
- Validates body shape (400 on missing/non-string/empty `message` or `page_context`, 413 on >8000-char message).
- Builds a prompt string with `page_context` (and optional `project_id`) interpolated into the SYSTEM prefix, plus `User: {message}`.
- Invokes claude via `subprocess.run([*CLAUDE_CMD], input=prompt, ..., timeout=60, check=False)`. No `shell=True`, ever. User input never enters argv.
- Maps failures: `TimeoutExpired` → 504, `FileNotFoundError` → 502, non-zero exit with stderr matching "not logged in"/"not authenticated"/"authentication" → 401, "rate limit"/"429"/"too many requests" → 429, anything else → 502.
- Parses claude's `--output-format json` envelope and pulls `result` (free-text reply) + `usage{input/output/cache tokens}` + `total_cost_usd` + `duration_ms`. Unparseable stdout → 502 with `hint` mentioning `parse`.
- Redacts absolute paths from stderr before placing it into any `hint` (regex `/[^\s'"<>]+` → `<path>`, truncated to 200 chars).

**`lib/api/__init__.py`** — package marker (`from . import chat`).

**`lib/api/test_chat.py`** — 15 unit tests with mocked `subprocess.run`. All pass.

**`bin/invisible-dashboard`** — added `do_POST` (auth gate identical to `do_GET`, 32 KiB body cap, JSON parse, dispatch `/api/v1/chat` → `chat_handler`, any other POST → 404, last-resort `except` → 500 with stderr-only stack trace). One new import line: `from api.chat import chat_handler`. **No other changes** — `do_GET` is untouched.

## Wire Contract (frontend Wave 2 — read this)

### Request

```http
POST /api/v1/chat HTTP/1.1
Content-Type: application/json

{
  "message":      "...",          // string, 1..8000 chars, REQUIRED
  "page_context": "dashboard",    // string, REQUIRED; opaque label
  "project_id":   "invisible"     // string, OPTIONAL; opaque label
}
```

### Success — HTTP 200

```json
{
  "text": "<assistant reply as plain prose>",
  "usage": {
    "input_tokens": 6,
    "output_tokens": 6,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": 38906,
    "cost_usd": 0.0001234,
    "duration_ms": 6828
  },
  "cost": 0.0001234
}
```

`cost` is a top-level convenience copy of `usage.cost_usd` for the bubble's footer.

### Errors — all share `{"error": <code>, "hint": <string>}`

| Status | `error` code              | When                                                              | Example `hint`                                |
| ------ | ------------------------- | ----------------------------------------------------------------- | --------------------------------------------- |
| 400    | `bad_request`             | Body not JSON, not an object, or missing/empty/non-string field   | `"field 'message' is required and must be a string"` |
| 401    | `claude_unauthenticated`  | claude CLI stderr contains "not logged in"/"authentication"       | `"run: claude login"`                         |
| 413    | `message_too_large`       | `message` > 8000 chars (or body > 32 KiB at dashboard layer)      | `"max 8000 chars"`                            |
| 429    | `rate_limited`            | claude CLI stderr contains "rate limit"/"429"/"too many requests" | `"claude API rate limit; wait a minute"`      |
| 500    | `server_error`            | Unexpected exception in dashboard POST dispatch                   | `"unexpected exception in POST dispatch"`     |
| 502    | `claude_cli_failed`       | binary missing, non-zero exit with no specific marker, or unparseable JSON | `"could not parse claude --output-format json envelope"` |
| 504    | `timeout`                 | claude subprocess exceeded 60s                                    | `"claude CLI exceeded 60s"`                   |

### Tunables (frontend should mirror these)

| Constant            | Value | Location              | Notes                                       |
| ------------------- | ----- | --------------------- | ------------------------------------------- |
| `MAX_MESSAGE_CHARS` | 8000  | `lib/api/chat.py`     | Frontend should pre-validate; backend enforces |
| `CLAUDE_TIMEOUT_S`  | 60    | `lib/api/chat.py`     | Frontend should show a spinner up to ~65s   |
| `_MAX_POST_BYTES`   | 32_768 | `bin/invisible-dashboard` | Coarser pre-parse cap on the daemon layer |

## Verification Results

End-to-end curls run against the live daemon:

```
GET  /healthz                           → HTTP 200  ("ok\n")
GET  /                                  → HTTP 200  (existing HTML)
GET  /api/projects                      → HTTP 200  (existing JSON)
POST /api/v1/chat   {happy path}        → HTTP 200  text="pong", usage populated, cost=0.243...
POST /api/v1/chat   {}                  → HTTP 400  bad_request
POST /api/v1/chat   not-json            → HTTP 400  bad_request
POST /api/v1/chat   {9000-char message} → HTTP 413  message_too_large
POST /api/v1/unknown                    → HTTP 404  not found
```

Unit tests:

```
lib/api/test_chat.py — Ran 15 tests in 0.003s — OK
  • happy path                     (1)
  • validation (missing/non-string/empty/non-dict/size)  (6)
  • failure modes (timeout/file-not-found/unauth/rate-limit/parse) (6)
  • injection prevention (argv shape, page_context isolation)      (2)
```

## TDD Gate Compliance

- RED: `test(01-01): add failing tests for chat_handler` (`ac39358`) — tests existed and failed because `lib/api/chat.py` did not.
- GREEN: `feat(01-01): implement chat_handler ...` (`4fbc0e8`) — all 15 tests pass.
- REFACTOR: skipped (no cleanup needed; code is purpose-shaped on first cut).

## Boundary Compliance

```bash
$ git diff --name-only HEAD~3 HEAD -- 'frontend/' 'lib/api/projects.py' \
    'lib/api/tree_' 'lib/api/analytics.py' 'bin/invisible-pty' \
    'lib/pty_server.py' 'src-tauri/' 'frontend-vite/'
# (no output — 0 forbidden files touched)
```

Files modified this plan (whitelist-only):
- `lib/api/__init__.py` (created)
- `lib/api/chat.py` (created)
- `lib/api/test_chat.py` (created)
- `bin/invisible-dashboard` (one import line + `do_POST` method)

Existing GET behavior (`/`, `/healthz`, `/api/projects`, `/api/p/*`, `/api/reviews`) confirmed unchanged.

## Threat Model Compliance

| Threat ID | Disposition | Status                                                                                                                                 |
| --------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| T-01-01   | mitigate    | ✓ Argv is module-level constant `CLAUDE_CMD`; user input passed via `input=` STDIN; grep gate `shell=True` count == 0 enforced.        |
| T-01-02   | mitigate    | ✓ 8000-char `message` cap → 413; 32_768-byte body cap at daemon → 413.                                                                  |
| T-01-03   | mitigate    | ✓ 60s wall-clock; `TimeoutExpired` → 504; subprocess child is killed by stdlib timeout handling.                                       |
| T-01-04   | mitigate    | ✓ `_redact()` strips abs paths from stderr; `hint` truncated to 200 chars; tracebacks go to stderr only via `traceback.print_exc()`.    |
| T-01-05   | mitigate    | ✓ `page_context` and `project_id` are interpolated into the prompt STRING only — never into argv or filesystem paths. Documented in module docstring. |
| T-01-06   | accept      | Existing daemon constraint (`--no-auth` requires `--host 127.0.0.1`) inherited; not re-checked in this phase.                          |
| T-01-07   | accept      | No per-request audit log (phase 1 demo scope).                                                                                          |
| T-01-08   | mitigate    | No new dependencies; stdlib only.                                                                                                       |

## Deviations from Plan

None. Plan executed as written. One small textual tweak: the literal phrase `shell=True` was removed from a docstring so that the acceptance-gate grep (`grep -c 'shell\s*=\s*True'` must equal 0) measured behavior rather than a self-referential mention. No semantic change.

## Known Stubs

None. Every success-path field returned from the handler is computed from real claude CLI output (verified by the happy-path curl returning real token counts and cost). No placeholder data anywhere in the wire response.

## Commits

| # | Hash    | Type | Message                                                       |
| - | ------- | ---- | ------------------------------------------------------------- |
| 1 | ac39358 | test | add failing tests for chat_handler                            |
| 2 | 4fbc0e8 | feat | implement chat_handler for /api/v1/chat proxy                 |
| 3 | bc58eed | feat | add POST /api/v1/chat route to dashboard daemon               |

## Self-Check: PASSED

- ✓ FOUND: lib/api/__init__.py
- ✓ FOUND: lib/api/chat.py
- ✓ FOUND: lib/api/test_chat.py
- ✓ FOUND commit: ac39358
- ✓ FOUND commit: 4fbc0e8
- ✓ FOUND commit: bc58eed
- ✓ All 15 unit tests pass
- ✓ End-to-end curl returns real claude reply with usage + cost
- ✓ No file outside the owned/edited-lightly list was modified
- ✓ Existing GET routes still respond 200
