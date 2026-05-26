# Workstream: ai-bubble (Phase 2 of M1)

> Sister-workstreams: dashboard-wiring, folders-3source, terminals-pty,
> analytics-aggregator, tauri-shell. All independent —
> see `.planning/ROADMAP.md` for the file overlap map.

## Phases

- [ ] **Phase 1: `/api/v1/chat` end-to-end** — Claude CLI proxy + bubble wired

## Phase Details

### Phase 1: /api/v1/chat end-to-end
**Goal**: The floating AI chat bubble (`frontend/ai-chat.jsx`, present on every page) actually talks to Claude. Today it's a mock that shows canned responses.

**Depends on**: Nothing. Pure parallel.

**Requirements**: REQ-02 (see `.planning/REQUIREMENTS.md`)

**Success Criteria** (what must be TRUE):
  1. `POST /api/v1/chat` with `{message, page_context, project_id?}` invokes `claude -p --output-format json` and returns the parsed reply (text + usage + cost).
  2. The bubble sends each user message to the endpoint and renders the response inline.
  3. Conversation history persists for the page session (in-memory list; no Postgres required).
  4. Failure modes have readable UI states: 401 (auth) / 429 (rate-limit) / 5xx (network) / timeout.
  5. `claude auth status` failure is surfaced to the user with a remediation hint.

**Plans**: 2 plans
- [ ] 02-01: Backend — `lib/api/chat.py` shells out to `claude -p --output-format json`; streams partial output via SSE if practical (otherwise simple POST→JSON works)
- [ ] 02-02: Frontend — `frontend/ai-chat.jsx` posts to `/api/v1/chat`, manages local message list, surfaces errors

## Files this workstream OWNS

- `lib/api/chat.py` (new)
- `frontend/ai-chat.jsx` (edit)

## Files this workstream EDITS LIGHTLY

- `lib/api/__init__.py` (add `from . import chat`)
- `bin/invisible-dashboard` (route binding)

## Files this workstream MUST NOT TOUCH

- `frontend/pages/*.jsx` — owned by sibling workstreams.
- `frontend-vite/`, `src-tauri/` — owned by WS-6.

## Verify locally

```bash
curl -s -X POST http://127.0.0.1:8765/api/v1/chat \
  -H 'content-type: application/json' \
  -d '{"message":"hello","page_context":"dashboard"}' | python3 -m json.tool
```

## Resume in a fresh Claude session

```bash
cd /Users/ace/.invisible
gsd-sdk query workstream.set ai-bubble --raw --cwd .
# then in Claude:
/gsd:plan-phase 1
```
