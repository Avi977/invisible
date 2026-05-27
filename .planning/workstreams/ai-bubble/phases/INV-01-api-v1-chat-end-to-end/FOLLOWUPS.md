---
phase: INV-01-api-v1-chat-end-to-end
workstream: ai-bubble
status: deferred-from-phase-1
created: 2026-05-26
---

# Phase 1 Follow-ups

Code is committed and shipped. Items were originally deferred when the phase closed ("move on, keep a tab on it"); user then asked for a real browser test which uncovered a serve-from-wrong-directory issue plus the predicted CORS bug. Both are now resolved. What remains is the bulk of the manual UAT (checks 3–6) plus one new minor follow-up.

## ✓ 1. CORS bug — RESOLVED (2026-05-26)

**Original prediction confirmed.** Playwright reproduced the exact CORS preflight failure:
```
Access to fetch at 'http://127.0.0.1:8765/api/v1/chat' from origin 'http://127.0.0.1:8090' has been blocked by CORS policy: Response to preflight request doesn't pass access control check: No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

**Fix shipped** in `bin/invisible-dashboard`:
- Override `end_headers()` to inject `Access-Control-Allow-Origin: *`, `Allow-Methods`, `Allow-Headers` on every response (matches `invisible-frontend`'s pattern)
- Add `do_OPTIONS()` returning 204 for preflight (unauthenticated by spec — preflight cannot carry the Authorization header)

Localhost-only invariant preserved: `*` is safe because (a) we never set `Access-Control-Allow-Credentials`, (b) `--no-auth` is pinned to `127.0.0.1`, (c) cross-origin reach from outside localhost still requires the bearer token.

Decision: kept the fix in `ai-bubble` workstream rather than punting to `dashboard-wiring`. The edit was small (~20 lines), the workstream already owns the dashboard's POST route via Wave 1, and the alternative (every sibling workstream blocked on a CORS fix) was worse.

## Serve-from-wrong-directory (operational gotcha — fixed in-session, but worth knowing)

`bin/invisible-frontend` defaults `INVISIBLE_HOME=~/.invisible` (main checkout), NOT the workstream worktree. If you start it bare in a workstream worktree, the browser shows the **main checkout's** files, not the workstream's edits. Symptom: bubble showed the OLD mock's `"couldn't reach the model — try again"` even though the new code was on disk.

**Always start the frontend daemon explicitly rooted at the workstream:**
```bash
cd ~/.invisible-ws/<workstream>
INVISIBLE_HOME=$(pwd) ./bin/invisible-frontend --port 8090
```
Same applies to `invisible-dashboard` (it reads `INVISIBLE_HOME` for its data layer too).

This is a sibling-workstream-wide gotcha; consider documenting in the project's top-level README or each workstream's START_HERE.md. Not blocking the phase.

## 2. Untested manual UAT (6 browser checks)

These were the human-verify task (`01-02-PLAN.md` Task 2, gate=blocking). Skipped per user instruction; must be run before `/gsd:ship`.

Open `http://127.0.0.1:8090/` and run in order:

| # | Check | Expected | Status |
|---|-------|----------|--------|
| 1 | Send `reply with exactly the word: pong` | Reply contains "pong" in <60s | ✓ PASSED via playwright 2026-05-26 |
| 2a | Without reload, send `what did I just ask you to say?` | Both prior turns visible above | ✓ PASSED — `msgs` array preserves history |
| 2b | (implicit) Does Claude remember the previous question content? | (acceptance is silent on this) | ✗ No — backend is stateless by design; each POST is a fresh `claude -p` invocation. The assistant replied "You didn't ask me to say anything yet — this is your first message". This was the planned scope: history persists in the UI, multi-turn context to the LLM is future work. See item 4. |
| 3 | `mv ~/.claude/.credentials.json{,.bak}` then send any message | `"Claude CLI not signed in. {hint}"` | UNTESTED — needs a human (don't want to break user's working credentials) |
| 4 | `pkill -f invisible-dashboard` then send | `"Backend unreachable — is invisible-dashboard running on 127.0.0.1:8765?"` | UNTESTED — needs a human (would interrupt the running setup); restart with: `cd ~/.invisible-ws/ai-bubble && INVISIBLE_HOME=$(pwd) nohup ./bin/invisible-dashboard --no-auth >/tmp/inv-dash-cors.log 2>&1 &` |
| 5 | Paste >8000-char string and send | Local `"Message too long (max 8000 characters)."`, NO network request in devtools | UNTESTED — easy to script in playwright; not done in this session |
| 6 | Send a message, immediately press Enter again | Second Enter is a no-op (no duplicate user message) | UNTESTED — easy to script in playwright; not done in this session |

## 3. Logical phase completion gate

Don't run `/gsd:ship` for this workstream until:
- [x] CORS fix shipped (item 1 — done in this session)
- [x] Happy path + history-persistence UI verified (checks 1 + 2a)
- [ ] Failure-mode UAT checks 3, 4, 5, 6 run (item 2 above). 5 and 6 can be playwright-scripted; 3 and 4 are best done by a human.

## 4. Multi-turn context (FUTURE — not blocking ship)

Surfaced by check 2b: the backend doesn't pass conversation history to `claude -p`, so each turn is an independent invocation. REQ-02's acceptance only requires history to "persist for the page session" (in-memory), which the UI does — but a user who reads their own prior turn on screen will naturally expect the assistant to also remember it.

**To resolve (when scoped):** Either (a) forward `msgs[]` to the backend and assemble a multi-turn `claude -p` invocation (claude CLI supports message threading via `--continue` / `--resume`), or (b) maintain a session ID per page-load and let the backend stash the thread. (b) is more durable but introduces server-side state that REQ-02 explicitly punted on.

## Resume command

```bash
cd ~/.invisible-ws/ai-bubble
gsd-sdk query workstream.set ai-bubble --raw --cwd .
# then in Claude:
# Pick up Phase 1 followups; read .planning/workstreams/ai-bubble/phases/INV-01-api-v1-chat-end-to-end/FOLLOWUPS.md
```
