---
phase: INV-01-api-v1-chat-end-to-end
workstream: ai-bubble
status: deferred-from-phase-1
created: 2026-05-26
---

# Phase 1 Follow-ups

Code is committed and shipped. These items were knowingly deferred when the phase closed; user said "move on, keep a tab on it." Pick this back up before declaring the workstream done.

## 1. Predicted CORS bug (HIGH — blocks browser smoke test)

**Status:** unverified but likely. Backend executor confirmed dashboard daemon does NOT emit `Access-Control-Allow-Origin` and returns HTTP 501 on OPTIONS preflight.

**Symptom (predicted):** Browser at `http://127.0.0.1:8090/` calling `POST http://127.0.0.1:8765/api/v1/chat` is blocked by CORS preflight (triggered by `content-type: application/json`). Bubble renders `"Backend unreachable — is invisible-dashboard running on 127.0.0.1:8765?"` even though `curl` works fine.

**Why it's deferred:** Fixing this requires editing `bin/invisible-dashboard` to add an `OPTIONS` handler + `Access-Control-Allow-Origin` headers. This phase's workstream boundary explicitly forbade silent CORS edits — the constraint came from the planning artifact, not an arbitrary choice. Sibling workstreams (especially `dashboard-wiring`) may have an opinion on the policy.

**To resolve:** Open a follow-up phase (likely belongs in `dashboard-wiring` workstream, not `ai-bubble`). Spec:
- Add `do_OPTIONS` to `DashboardHandler` returning 204 + `Access-Control-Allow-Origin: http://127.0.0.1:8090` + `Access-Control-Allow-Methods: POST, GET, OPTIONS` + `Access-Control-Allow-Headers: content-type`
- Add `Access-Control-Allow-Origin` header to `do_POST` + `do_GET` responses
- Coordinate with `dashboard-wiring` workstream so two workstreams don't both edit `bin/invisible-dashboard` at the same time

## 2. Untested manual UAT (6 browser checks)

These were the human-verify task (`01-02-PLAN.md` Task 2, gate=blocking). Skipped per user instruction; must be run before `/gsd:ship`.

Open `http://127.0.0.1:8090/` and run in order:

| # | Check | Expected | Notes |
|---|-------|----------|-------|
| 1 | Send `reply with exactly the word: pong` | Reply contains "pong" in <60s | Likely fails on CORS — see item 1 |
| 2 | Without reload, send `what did I just ask you to say?` | Both prior turns visible above | Verifies in-memory `msgs` state |
| 3 | `mv ~/.claude/.credentials.json{,.bak}` then send any message | `"Claude CLI not signed in. {hint}"` | **Restore the credentials file afterward** |
| 4 | `pkill -f invisible-dashboard` then send | `"Backend unreachable — is invisible-dashboard running on 127.0.0.1:8765?"` | Restart: `cd ~/.invisible-ws/ai-bubble && nohup ./bin/invisible-dashboard --no-auth >/tmp/inv-dash-0102.log 2>&1 &` |
| 5 | Paste >8000-char string and send | Local `"Message too long (max 8000 characters)."`, NO network request in devtools | Client-side guard |
| 6 | Send a message, immediately press Enter again | Second Enter is a no-op (no duplicate user message) | Thinking-state guard |

## 3. Logical phase completion gate

Don't run `/gsd:ship` for this workstream until:
- [ ] CORS follow-up phase planned + executed (item 1)
- [ ] All 6 manual UAT checks pass (item 2)
- [ ] If any of the 6 reveal unexpected failures, file a debug session before shipping

## Resume command

```bash
cd ~/.invisible-ws/ai-bubble
gsd-sdk query workstream.set ai-bubble --raw --cwd .
# then in Claude:
# Pick up Phase 1 followups; read .planning/workstreams/ai-bubble/phases/INV-01-api-v1-chat-end-to-end/FOLLOWUPS.md
```
