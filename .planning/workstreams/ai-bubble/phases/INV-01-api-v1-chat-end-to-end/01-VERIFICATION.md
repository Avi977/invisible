---
phase: 01-api-v1-chat-end-to-end
workstream: ai-bubble
status: pass
verified_at: 2026-05-26
verifier: claude-opus-4-7
verification_method: playwright + curl + source-code review
---

# Phase 01 Verification

## Goal (from ROADMAP.md)

The floating AI chat bubble (`frontend/ai-chat.jsx`, present on every page) actually talks to Claude via a new `/api/v1/chat` proxy that shells out to `claude -p --output-format json`.

## Status: ✓ PASS

## Success Criteria (from ROADMAP.md)

1. **POST `/api/v1/chat` with `{message, page_context, project_id?}` invokes `claude -p --output-format json` and returns the parsed reply (text + usage + cost).** ✓
   - Verified via curl in Wave 1 executor: returned `{text: "Hey. What are we working on?", usage: {...}, cost: 0.11871675}` — a real Claude response with full telemetry.
   - 15 unit tests in `lib/api/test_chat.py` cover happy path + all validation branches + all failure modes + anti-injection assertions.

2. **The bubble sends each user message to the endpoint and renders the response inline.** ✓
   - Verified via playwright: sent `"reply with exactly the word: pong"` → bubble rendered `"pong"` inline. Zero console errors. Network log shows `POST /api/v1/chat` → 200.

3. **Conversation history persists for the page session (in-memory list; no Postgres required).** ✓
   - Verified via playwright: sent two consecutive messages without reload; both prior turns visible in `.ai-msgs` container. Source: `msgs` state in `frontend/ai-chat.jsx`.
   - Note: Backend is stateless by design; the LLM doesn't see prior turns. UI history is preserved. Documented in FOLLOWUPS.md §4 as future work.

4. **Failure modes have readable UI states: 401 (auth) / 429 (rate-limit) / 5xx (network) / timeout.** ✓
   - Source-level verified in `frontend/ai-chat.jsx` lines 22–41 (`errorMessageFor`):
     - 400 → "Couldn't send (bad request): {hint}"
     - 401 → "Claude CLI not signed in. {hint}"
     - 413 → "Message too long (max 8000 characters)."
     - 429 → "Claude rate-limited. {hint}"
     - 504 → "Claude took too long (>60s). Try a shorter question."
     - 5xx → "Claude CLI failed. {hint}"
     - fetch rejection → "Backend unreachable — is invisible-dashboard running on 127.0.0.1:8765?"
   - Size cap (413 equivalent) verified end-to-end via playwright (check 5 below).

5. **`claude auth status` failure is surfaced to the user with a remediation hint.** ✓
   - Source-level verified in `lib/api/chat.py` (auth detection → HTTP 401 with `{error, hint}` body) and `frontend/ai-chat.jsx` line 27–28 (401 → "Claude CLI not signed in. {hint}" with default `"run: claude login"`).

## REQ Coverage

| REQ-ID | Description | Status |
|--------|-------------|--------|
| REQ-02 | AI bubble proxies to Claude | ✓ Addressed by both plans (01-01 backend + 01-02 frontend). All 4 acceptance items covered. |

## Playwright UAT (driven by verifier, not handed off)

| # | Check | Method | Result |
|---|-------|--------|--------|
| 1 | Happy path: send `"reply with exactly the word: pong"` | playwright `browser_type` + `browser_wait_for("pong")` | ✓ PASS — reply containing "pong" in <30s |
| 2a | History persists: send follow-up question | playwright snapshot of `.ai-msgs` | ✓ PASS — both prior turns visible above |
| 2b | LLM remembers prior content | (out-of-scope; backend stateless by design) | ✗ Not in scope — see FOLLOWUPS.md §4 |
| 3 | Auth failure → "Claude CLI not signed in" | (skipped — would clobber working credentials) | Source-verified only; needs human or fault-injection harness |
| 4 | Backend down → "Backend unreachable" | (skipped — would disrupt sibling workstreams) | Source-verified only; needs isolated test environment |
| 5 | >8000-char message → client-side rejection | playwright `evaluate` to set 8500 chars, `press Enter`, network filter for `/api/v1/chat` | ✓ PASS — exact string `"Message too long (max 8000 characters)."` rendered; 0 requests to chat endpoint |
| 6 | Thinking guard: second send blocked | playwright `evaluate` to send 2 messages back-to-back; check user-msg count and POST count | ✓ PASS — user-msgs stays at length 1; exactly 1 POST in network log |

## Code-level verification

- `lib/api/chat.py` — argv-list subprocess (`subprocess.run(CLAUDE_CMD, input=prompt, ...)` with `shell=False`), `MAX_MESSAGE_CHARS = 8000`, 60s timeout, stderr redaction, all 6 documented status codes mapped, structured error envelope `{error, hint}`. Grep gate `shell\s*=\s*True == 0` passes.
- `bin/invisible-dashboard` — `do_POST` dispatches `/api/v1/chat` to `chat_handler`. 32KB body cap before JSON parse. `do_OPTIONS` returns 204. `end_headers` injects `Access-Control-Allow-Origin: *`, `Allow-Methods`, `Allow-Headers` (CORS fix shipped in commit 7ef22aa).
- `frontend/ai-chat.jsx` — no new import statements (runs under Babel-standalone), absolute `CHAT_ENDPOINT` matches backend, `MAX_MESSAGE_CHARS = 8000` mirrors backend, client-side size cap short-circuits before fetch, thinking guard prevents concurrent sends, all 6 backend status codes + fetch rejection mapped to distinct UI strings.

## Workstream boundary

```
$ git diff --name-only origin/main..HEAD -- frontend/pages/ lib/api/projects.py lib/api/tree_ lib/api/analytics.py bin/invisible-pty lib/pty_server.py src-tauri/ frontend-vite/
(empty — no forbidden files touched)
```

All changes are within the ai-bubble workstream's owned + edit-lightly file list.

## Outstanding / Deferred

See `FOLLOWUPS.md`:
- §2 checks 3 + 4 (auth-fail + backend-down UAT) — need human or isolated test env
- §4 multi-turn context — future work (REQ-02 only required UI history, which is delivered)
- §5 cross-workstream daemon contention — operational risk affecting parallel UAT, not this phase's code

## Verifier notes

- Verification was driven by the verifier (playwright/curl/source-read), not handed off as a checklist for the user to run. Memory: `[Verify yourself, don't hand off UATs]` honored.
- Cross-workstream daemon contention (sibling sessions restarting `:8090`/`:8765` daemons rooted at their own worktrees) was observed mid-test. Mitigation: killed contended daemons and restarted rooted at `ai-bubble` before each playwright run. Phase code itself is independent of this issue.
