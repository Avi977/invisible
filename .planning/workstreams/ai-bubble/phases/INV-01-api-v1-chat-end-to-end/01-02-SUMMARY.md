---
phase: 01-api-v1-chat-end-to-end
plan: 02
subsystem: frontend / ai-bubble
tags:
  - workstream:ai-bubble
  - frontend
  - bubble-ui
dependency_graph:
  requires:
    - "Plan 01-01 (POST /api/v1/chat backend proxy, commits ac39358 + 4fbc0e8 + bc58eed)"
    - "invisible-dashboard daemon on 127.0.0.1:8765 (started by bin/invisible-dashboard --no-auth)"
    - "invisible-frontend daemon on 127.0.0.1:8090 (already running)"
  provides:
    - "Bubble UI that POSTs user messages to /api/v1/chat and renders real assistant replies inline"
    - "Distinct error UI strings for each documented backend failure mode (400/401/413/429/5xx/504) plus a fetch-rejection 'backend unreachable' state"
  affects:
    - "frontend/ai-chat.jsx — send() rewritten; mock removed; two new module constants"
tech_stack:
  added: []   # zero new dependencies; runs under Babel-standalone with React/I as globals
  patterns:
    - "Constant-indirected absolute URL (CHAT_ENDPOINT) — frontend is on :8090, backend on :8765, cross-origin in dev"
    - "Client-side size cap (MAX_MESSAGE_CHARS=8000) — defense in depth mirroring backend HTTP 413"
    - "errorMessageFor(status, body) — table-driven error-string map, prefers backend body.hint when present"
    - "Network-down distinct from server-error — catch on fetch rejection renders a separate UI string than any 5xx"
key_files:
  created: []
  modified:
    - frontend/ai-chat.jsx
decisions:
  - "Constant indirection for CHAT_ENDPOINT — improves readability and lets the absolute URL be tweaked in one place; the plan's `<verify>` grep `fetch\\([^)]*api/v1/chat` does not match this factoring, but the plan's own `<acceptance_criteria>` mandates `grep -c 'CHAT_ENDPOINT' >= 2`, which IS satisfied. The single-line grep is inconsistent with the constant pattern the plan prescribes — spirit of the check is honored (fetch + url are line-locally provable)."
  - "No new component props — kept `function AIBubble({ pageContext })` exactly. The plan signals `projectId` is a future-phase concern; today the bubble omits `project_id` from the request body (backend treats it as optional per 01-01 contract)."
  - "Client-side 413 short-circuit appends BOTH the user-message AND the local error reply in a single setMsgs call to avoid an interim flicker where a too-long bubble sits alone for one render."
  - "fetch() catch branch handles network down, CORS-preflight failures, DNS fail — all surface as 'Backend unreachable' (the same UI string). Distinguishing them in-bubble would require platform-specific error introspection that does not survive across browsers; one user-actionable string is the right tradeoff."
metrics:
  duration_seconds: 600   # approximate — read time + implementation + verification + pre-checkpoint daemon probe
  task_count: 1   # task 2 is the human-verify checkpoint (gate)
  files_modified: 1
  files_created: 0
completed_implementation: 2026-05-26
completed_verification: pending   # filled by human at checkpoint resume
---

# Phase 01 Plan 02: AI Chat Bubble — Frontend Wiring Summary

`frontend/ai-chat.jsx` now POSTs each user message to `POST /api/v1/chat` (the Plan 01-01 backend proxy) and renders the real Claude reply inline. The mock `window.claude.complete` call is removed. Six documented failure modes map to distinct, actionable UI strings.

## What Was Built

### `frontend/ai-chat.jsx` — modifications (one file, no new files)

**Module-level additions (top of file, above `SUGGESTIONS`):**

- `const CHAT_ENDPOINT = "http://127.0.0.1:8765/api/v1/chat";` — absolute URL because the bubble's host page is served by `invisible-frontend` on `:8090`, while the dashboard daemon answers `:8765` (different origins).
- `const MAX_MESSAGE_CHARS = 8000;` — mirrors `lib/api/chat.py` MAX_MESSAGE_CHARS. Client-side defense in depth so the user gets instant feedback for oversize input instead of paying a network round-trip to receive HTTP 413.
- `function errorMessageFor(status, body)` — pure helper that maps backend HTTP codes to UI strings, preferring `body.hint` when present. Table:

  | Status | UI string |
  | ------ | --------- |
  | 400 | "Couldn't send (bad request): {hint or 'check input'}" |
  | 401 | "Claude CLI not signed in. {hint or 'run: claude login'}" |
  | 413 | "Message too long (max 8000 characters)." |
  | 429 | "Claude rate-limited. {hint or 'wait a moment and try again'}" |
  | 504 | "Claude took too long (>60s). Try a shorter question." |
  | other ≥500 | "Claude CLI failed. {hint or 'HTTP {n}'}" |
  | other <500 | "Unexpected error (HTTP {n})." |

**`send(text)` rewritten:**

- Preserves the existing `thinking` guard, `setInput("")`, and the in-flight indicator.
- Adds a client-side size pre-check: `text.length > MAX_MESSAGE_CHARS` short-circuits with a local 413-equivalent message, no fetch issued.
- `fetch(CHAT_ENDPOINT, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ message: text, page_context: pageContext }) })`. No `project_id` (out of scope this phase — prop signature unchanged).
- Defensive `body = await res.json()` wrapped in its own try/catch so non-JSON error bodies don't break the error path.
- On `res.ok && typeof body.text === "string"` → append `{role:'ai', text: body.text}`.
- Otherwise → append `{role:'ai', text: errorMessageFor(res.status, body), error: true}`.
- Outer `catch` (fetch rejection — backend not running, CORS blocked, DNS fail) → "Backend unreachable — is invisible-dashboard running on 127.0.0.1:8765?".
- `setThinking(false)` moved into a real `finally` block (was a bare trailing statement before).

**Removed:**

- `const sys = "...";` (system-prompt construction — now lives in `lib/api/chat.py`)
- The `await window.claude.complete({...})` call and its surrounding try/catch.

**Byte-for-byte unchanged** (audited):

- The prop signature `function AIBubble({ pageContext })`.
- The entire JSX render block (bubble icon, panel, head, msgs map, suggestions block, input wrap).
- The `SUGGESTIONS` array.
- The `useStateAI` / `useRefAI` / `useEffectAI` aliases.
- The `useEffectAI` scroll-to-bottom hook.
- The `window.AIBubble = AIBubble;` export at the bottom.

## Verification Results

### Acceptance criteria (from plan)

| Check | Expected | Actual | Pass |
| ----- | -------- | ------ | ---- |
| Brace/paren balance | balanced | balanced | ✓ |
| Mock removed | 0 occurrences of `window.claude.complete` | 0 | ✓ |
| Fetch wired to `/api/v1/chat` | constant references the URL | `CHAT_ENDPOINT` defined as the URL, used in `fetch()` | ✓ (factored through constant — see Deviations) |
| Error-status map ≥ 3 of (401, 413, 429, 504) | ≥3 | 4 | ✓ |
| `CHAT_ENDPOINT` count ≥2 | ≥2 | 2 | ✓ |
| `MAX_MESSAGE_CHARS` count ≥2 | ≥2 | 5 | ✓ |
| `window.AIBubble = AIBubble` count == 1 | 1 | 1 | ✓ |
| Prop signature `function AIBubble({ pageContext })` == 1 | 1 | 1 | ✓ |
| No new imports | 0 | 0 | ✓ |
| Boundary check (frontend/pages/, frontend-vite/, src-tauri/, lib/, bin/) | 0 violations | 0 | ✓ |

### Backend pre-checkpoint smoke (executor ran before stopping)

```
GET  /healthz                                → "ok"
POST /api/v1/chat {"message":"reply with exactly the word: pong",...}
  → 200; text="pong"; cost=0.1187; usage tokens=6/6   (~30s wall time)
```

Backend is alive and serves real Claude replies on the wire. The frontend code is wired to consume this exact shape.

### CORS posture probe (executor ran before stopping — material risk surfaced)

```
OPTIONS /api/v1/chat
  Origin: http://127.0.0.1:8090
  → HTTP/1.0 501 Unsupported method ('OPTIONS')   ← preflight will FAIL

POST /api/v1/chat
  Origin: http://127.0.0.1:8090
  → HTTP 200 with usable JSON, but NO Access-Control-Allow-Origin header
```

**Implication:** When the browser at `http://127.0.0.1:8090/` fetches `http://127.0.0.1:8765/api/v1/chat` with `content-type: application/json`, the browser issues a **CORS preflight** (because `application/json` is not a CORS-safe request header value). The dashboard returns 501 on `OPTIONS`. The browser will block the actual POST. Result: the bubble will render **"Backend unreachable — is invisible-dashboard running on 127.0.0.1:8765?"** even though the daemon is healthy.

This is a known and explicitly anticipated risk — the plan's `<interfaces>` section says:

> "If CORS becomes an actual blocker during the human-verify step, render the failure clearly in the bubble (network state) and raise a checker note for a follow-up CORS plan. Do NOT silently work around it by changing backend headers in this plan."

The executor did NOT modify the dashboard. The frontend correctly renders the failure as a network-down state. A follow-up plan (suggested name: `01-03-dashboard-cors-headers.md`) should add `Access-Control-Allow-Origin: http://127.0.0.1:8090` and an `OPTIONS` handler to `bin/invisible-dashboard`. That work is out of scope for the ai-bubble workstream proper — it's a dashboard-daemon concern.

**Alternative path that bypasses CORS:** if the bubble is rendered inside a `pywebview` shell (same-origin) or the user serves both daemons through a reverse proxy on a single origin, CORS does not apply and the wire works as-is. The human-verify checkpoint should empirically confirm which posture is in effect.

## Deviations from Plan

### Auto-fixed Issues

None — no Rule 1/2/3 issues encountered during implementation.

### Documentation discrepancy noted (not a deviation, recorded for posterity)

**The plan's `<verify>` automated grep `fetch\([^)]*api/v1/chat` does not match the implemented code**, because the executor factored the URL into a named constant (`CHAT_ENDPOINT`) and the grep expects the literal URL inline as the first argument to `fetch(`. The plan's `<acceptance_criteria>` block, however, explicitly mandates `grep -c 'CHAT_ENDPOINT' >= 2`, which IS satisfied (2 occurrences). The two checks are mutually inconsistent — the executor honored the more specific acceptance criterion. Both halves of the fetch wiring (the URL definition and the `fetch(CHAT_ENDPOINT, …)` call) are line-locally provable with `grep -n 'CHAT_ENDPOINT' frontend/ai-chat.jsx`.

**Recommendation for future plans:** when prescribing a constant pattern in acceptance criteria, write the automated grep to match the constant (e.g., `fetch\(CHAT_ENDPOINT`), not the literal URL.

## Known Stubs

None. All success-path UI text is sourced from the live `body.text` field of the backend response (verified by the executor's `curl` smoke returning real Claude prose). All error-path strings are sourced from `body.hint` (where present) plus the status-code-keyed defaults in `errorMessageFor`. No placeholder copy anywhere.

## Threat Model Compliance

| Threat ID | Disposition | Status |
| --------- | ----------- | ------ |
| T-01-09 (XSS via error renderer) | mitigate | ✓ All response strings rendered through React text children (`{m.text}`). No `dangerouslySetInnerHTML`. Confirmed: `grep -c dangerouslySetInnerHTML frontend/ai-chat.jsx` = 0. |
| T-01-10 (DoS via input) | mitigate | ✓ Client-side `MAX_MESSAGE_CHARS = 8000` short-circuits before fetch. |
| T-01-11 (info disclosure via error UI) | mitigate | ✓ Only `body.hint` (already redacted in `lib/api/chat.py:_redact`) is interpolated. No `console.log` of credentials. |
| T-01-12 (repudiation — no audit) | accept | History is intentionally in-memory only per REQ-02. |
| T-01-13 (npm/pip install tampering) | mitigate | ✓ Zero new dependencies. `grep -c '^import ' frontend/ai-chat.jsx` = 0. |
| T-01-14 (client bypass of backend validation) | accept | Client-side cap is defense in depth; backend independently enforces 8000-char + JSON shape. |

## Boundary Compliance

```bash
$ git diff --name-only HEAD~1 HEAD
frontend/ai-chat.jsx

$ git diff --name-only HEAD~1 HEAD -- 'frontend/pages/' 'frontend-vite/' 'src-tauri/' 'lib/' 'bin/'
# (no output — 0 forbidden files touched)
```

Files modified this plan (whitelist of one):

- `frontend/ai-chat.jsx` (edited — `send` body + two module constants + helper function)

Phase-wide cross-check (both plans combined):

```bash
$ git diff --name-only 3b706cb..HEAD | grep -E -v '^(frontend/ai-chat\.jsx)$'
# (executor expects exactly one file changed in plan 02; phase-wide list from 01-01 is the existing
#  lib/api/*.py + bin/invisible-dashboard + .planning/* set documented in 01-01-SUMMARY.md)
```

## Commits

| # | Hash    | Type | Message |
| - | ------- | ---- | ------- |
| 1 | 9f47c44 | feat | wire ai-chat bubble to POST /api/v1/chat |

(A second commit will append this SUMMARY.md + STATE.md updates after the human-verify checkpoint resolves.)

## Human Verification — required next step (Task 2 of plan 01-02)

The implementation is wired. Task 2 of the plan is `type: checkpoint, gate: blocking, kind: human-verify` and must be exercised by a person in a real browser. The executor has prepared the environment:

- `invisible-dashboard --no-auth` is RUNNING on `:8765` (PID survives this checkpoint; killed only by the human's step 4 below).
- `invisible-frontend` is RUNNING on `:8090` (status: HTTP 200 on `/`).
- `/api/v1/chat` smoke from the executor's `curl` returned `text: "pong"` with `cost ≈ $0.12`.

### What to do (six checks, in order)

1. **Happy path.** Open <http://127.0.0.1:8090/> in a browser. Click the sparkles bubble (bottom-right). Type `reply with exactly the word: pong` and press Enter. Expected: a real assistant reply appears in <60s, the text contains the word "pong". → Confirm.

2. **History persists in-session.** Without reloading, send a second message: `what did I just ask you to say?`. Expected: the assistant responds AND both prior turns (the original prompt + the pong reply) remain visible. → Confirm.

3. **Auth failure surfaces.** Move credentials aside: `mv ~/.claude/.credentials.json ~/.claude/.credentials.json.bak` (or use `claude logout`). Send a message. Expected: "Claude CLI not signed in. {hint mentioning `claude login`}". **Restore** with `mv ~/.claude/.credentials.json.bak ~/.claude/.credentials.json` (or `claude login`). → Confirm.

4. **Backend-down state.** `pkill -f invisible-dashboard`. Send a message. Expected: "Backend unreachable — is invisible-dashboard running on 127.0.0.1:8765?". Restart: `cd /Users/ace/.invisible-ws/ai-bubble && nohup ./bin/invisible-dashboard --no-auth >/tmp/inv-dash-0102.log 2>&1 &`. → Confirm.

5. **Size cap.** Paste a >8000-char string into the input and press Enter. Expected: a local "Message too long (max 8000 characters)." reply, NO network request to the backend (check the browser devtools Network tab). → Confirm.

6. **Thinking guard.** Send a message. Before the reply arrives, press Enter again. Expected: second Enter is a no-op — no duplicate user-message added, no second outbound request. → Confirm.

### Failure mode that is LIKELY (executor pre-warning)

Step 1 (happy path) may render **"Backend unreachable …"** in the bubble even though the daemon is healthy. **This means CORS is blocking the browser fetch** — the executor's probe (documented above) showed:

- `OPTIONS /api/v1/chat` → HTTP 501 (no preflight handler)
- No `Access-Control-Allow-Origin` header on POST responses

If step 1 fails this way, open the browser devtools console — you should see a "CORS policy" error. **Do not retry; this is a known scoping decision**, not a regression. Report the failure with the console error text. A follow-up plan (`01-03-dashboard-cors-headers.md` or equivalent) must add `Access-Control-Allow-Origin: http://127.0.0.1:8090` and an `OPTIONS` handler to `bin/invisible-dashboard`. That work belongs to whoever owns the dashboard daemon, **not** the ai-bubble workstream.

If step 1 happens to succeed (e.g., the bubble runs inside a `pywebview` shell that proxies both daemons through one origin), proceed with steps 2-6 normally.

### Resume signal

After verifying, return one of:

- `approved — all 6 checks passed` (or list which passed if some were skipped due to CORS blocking step 1).
- `CORS confirmed — step 1 fails with "Backend unreachable"; console shows CORS error: <paste>` → executor will be re-spawned to add the deviation note + close-out commit; a follow-up plan is needed to add CORS headers to `bin/invisible-dashboard`.
- A description of any other failure (which check, what was seen).

## Self-Check: PASSED

- ✓ FOUND: frontend/ai-chat.jsx (modified — `git diff --name-only HEAD~1 HEAD` returns exactly this file)
- ✓ FOUND commit: 9f47c44 (`git log --oneline -1` matches)
- ✓ FOUND constant: `CHAT_ENDPOINT = "http://127.0.0.1:8765/api/v1/chat"` (line 10)
- ✓ FOUND constant: `MAX_MESSAGE_CHARS = 8000` (line 14)
- ✓ FOUND helper: `function errorMessageFor(status, body)` (line 22)
- ✓ FOUND fetch call: `await fetch(CHAT_ENDPOINT, ...)` (line 74)
- ✓ Mock REMOVED: `grep -c 'window\.claude\.complete' frontend/ai-chat.jsx` = 0
- ✓ Prop signature UNCHANGED: `grep -c 'function AIBubble({ pageContext })' frontend/ai-chat.jsx` = 1
- ✓ Export PRESERVED: `grep -c 'window.AIBubble = AIBubble' frontend/ai-chat.jsx` = 1
- ✓ Zero new imports: `grep -c '^import ' frontend/ai-chat.jsx` = 0
- ✓ Boundary clean: zero files outside `frontend/ai-chat.jsx` modified by this plan
- ✓ Brace/paren balance verified
- ✓ Backend healthcheck passed; live `/api/v1/chat` returns real Claude reply
- ⏸ Step 2 (human-verify) — PENDING (CHECKPOINT)
