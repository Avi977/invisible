# Envy Implementation TODO

Use this file as the source checklist before starting implementation work.
Before beginning a task, review this file and mark the active item as in progress.
After completing a task, update the item with the result, verification, and any follow-up.

## Status Legend

- [ ] Not started
- [~] In progress
- [x] Done
- [!] Blocked

## Ground Rules

- Default to free and open-source local components.
- Treat "API" as a local Envy/Ollama/OpenWhispr endpoint unless a paid cloud option is explicitly requested.
- Do not use OpenAI, Anthropic, OpenWhispr Cloud, hosted Graphify semantic extraction, or other paid APIs by default.
- Keep graph integrations behind Envy's own API surfaces so the frontend does not depend directly on third-party internals.
- Update this checklist before and after implementation work.

## TODO

- [x] Verify external licenses and sources.
  - Graphify: `https://github.com/safishamsi/graphify`, package `graphifyy`, MIT.
  - Ollama: local service at `127.0.0.1:11434`, open source, no usage cost.
  - Qwen local models: use installed Ollama models, primary `qwen3:14b`, fallback `qwen3:4b`.
  - OpenWhispr: `https://github.com/OpenWhispr/openwhispr`, MIT, local mode only.
  - 2026-07-03 verification: Graphify GitHub/site and package name confirmed, OpenWhispr GitHub license confirmed MIT, Ollama GitHub license confirmed MIT, Qwen3 14B/4B confirmed open-weight Apache 2.0 from Qwen model notes.

- [x] Establish a runnable baseline.
  - Install missing dev dependencies if needed.
  - Run Python tests.
  - Run frontend build.
  - Start dashboard/frontend locally and note current breakage.
  - 2026-07-03 result: installed frontend deps with `corepack pnpm install` after enabling Node system CA; installed Python test tooling with `py -3.14 -m pip install --user pytest ruff`.
  - Verification: `py -3.14 -m pytest -q` => 52 passed, 5 live VPS tests skipped; `corepack pnpm build` => success.
  - Local smoke: dashboard API running at `http://127.0.0.1:8765` with `--no-auth`; Vite preview running at `http://127.0.0.1:5174`.

- [x] Add Graphify backend integration.
  - Add a local wrapper for running Graphify against configured project folders.
  - Store Graphify outputs under `$INVISIBLE_HOME/graphify/<project>/`.
  - Normalize Graphify output through Envy's `/api/v1/relations` shape.
  - 2026-07-03 result: added `/api/v1/graphify/status`, `/api/v1/graphify/run`, Graphify output loading, and Relations normalization fallback.
  - Verification: status endpoint reports local-only metadata and clean `graphify_missing` when the `graphify` CLI is not installed.
  - 2026-07-03 finish: Graphify now detects both the `graphify` console script and `python -m graphify`, runs `graphify extract` with `--backend ollama --model qwen3:4b --max-concurrency 1 --out <Envy graph dir>`, imports `graphify-out/graph.json`, and clears the Relations cache after import.
  - Verification: `GET /api/v1/graphify/status?project=invisible` reports installed via `python.exe -m graphify`; tiny real Graphify CLI smoke wrote `graphify-out/graph.json` with 2 nodes and 1 edge.

- [x] Wire Relations UI to live graph data.
  - Replace static mock graph rendering with `/api/v1/relations`.
  - Keep mock data only as an unavailable-backend fallback.
  - Show live node/edge counts.
  - 2026-07-03 result: Vite Relations page loads `/api/v1/relations`, supports Graphify run trigger, and displays live counts/status.
  - Verification: `GET /api/v1/relations?project=invisible` returned 177 nodes and 468 edges through the running dashboard.

- [x] Wire Tools UI to persisted workflow data.
  - Use `GET /api/v1/tools?project=<slug>`.
  - Save edits with `PUT /api/v1/tools?project=<slug>`.
  - Keep static sample workflows only as seed/fallback data.
  - 2026-07-03 result: Vite Tools page reads and debounced-saves project workflows through the existing local Tools API.
  - Verification: runtime PUT/GET smoke preserved a node and returned `updated_at`.

- [x] Add local Ollama AI backend.
  - Add model discovery endpoint.
  - Add chat endpoint using local Ollama only.
  - Default to `qwen3:14b`, fallback to `qwen3:4b`.
  - Return useful status/errors when Ollama is not running.
  - 2026-07-03 result: added `/api/v1/ai/models` and `/api/v1/ai/chat`.
  - Verification: model discovery returned local `qwen3:14b` and `qwen3:4b`; chat smoke with `qwen3:4b` returned local-only response.

- [x] Replace the current AI bubble with a custom Envy AI console.
  - Include model selector, project selector, chat thread, prompt box, voice button, handoff button, and local-provider status.
  - Do not depend on `window.claude`.
  - 2026-07-03 result: Vite AI bubble now uses Envy API helper, Ollama model selector, project selector, voice transcript insertion, handoff draft/save controls, and no `window.claude` dependency.

- [x] Add handoff system v1.
  - Generate compact handoffs from project state, graph neighbors, logs/checkpoints, and user prompt.
  - Store handoffs under `$INVISIBLE_HOME/handoffs/<project>/<timestamp>.json`.
  - Support review/copy/save in the UI.
  - 2026-07-03 result: added `/api/v1/handoff/draft` and `/api/v1/handoff/save`, backed by local Ollama and `$INVISIBLE_HOME/handoffs/<project>/`.
  - Verification: draft smoke generated markdown with `qwen3:4b`; save smoke wrote a JSON handoff successfully.

- [x] Vendor or connect OpenWhispr for local voice-to-prompt.
  - Vendor source from GitHub if that remains the chosen approach.
  - Add local voice status/transcription bridge.
  - Insert transcript into the prompt box for user review before sending.
  - Clearly report when OpenWhispr is not installed/running.
  - 2026-07-03 result: added OpenWhispr Git submodule metadata, local status endpoint, and transcript-text bridge used by the AI console.
  - 2026-07-03 finish: `/api/v1/voice/transcribe` now reads OpenWhispr's local CLI bridge file at `~/.openwhispr/cli-bridge.json`, calls its localhost `/v1/transcriptions/list` or `/v1/transcriptions/<id>` endpoints, and returns latest runtime transcript text when the desktop app is running. Manual transcript text remains as an offline fallback.
  - Verification: unit tests cover manual text, bridge transcript, and bridge-unavailable paths; runtime status reports vendored source present and bridge not running, and runtime POST degrades with `openwhispr_bridge_unavailable` until OpenWhispr starts.

- [x] Verification pass.
  - Run API tests.
  - Run frontend build.
  - Verify Relations live graph.
  - Verify Tools persistence after refresh.
  - Verify Ollama chat and handoff generation offline.
  - Verify voice UI degrades cleanly if OpenWhispr is unavailable.
  - 2026-07-03 completed: API tests, frontend build, endpoint smoke for Relations, Tools, Ollama chat, handoff draft/save, voice transcript bridge, Graphify missing-state fallback.
  - 2026-07-03 finish verification: `py -3.14 -m pytest -q` => 56 passed, 5 skipped; changed-file `ruff` => passed; `corepack pnpm build` => passed; Graphify tiny real CLI smoke => passed; dashboard runtime status endpoints => passed; OpenWhispr unavailable bridge and manual fallback POST paths => passed.
  - Note: `py -3.14 -m ruff check .` still fails because Ruff tries to parse pre-existing extensionless shell scripts in `bin/` as Python.

- [x] Critique and follow-up list.
  - Record runtime issues.
  - Record UX friction.
  - Record performance/token-saving observations.
  - Record next recommended implementation slice.
  - Runtime issue: OpenWhispr desktop app is not currently running, so Envy can only prove bridge-unavailable degradation and manual transcript fallback in this session; the bridge-backed code path is covered by unit tests against the documented local bridge contract.
  - UX friction: the AI console still falls back to `window.prompt` for manual transcript paste; a small modal or inline transcript picker would be cleaner.
  - Performance/token note: Graphify full-project runs are now pinned to local Ollama and single concurrency; use `no_cluster: true` by default to keep the first pass cheaper/faster, then run a clustered pass explicitly when needed.
  - Next slice: start OpenWhispr locally and smoke a real microphone transcript through `~/.openwhispr/cli-bridge.json`; then run full-project `POST /api/v1/graphify/run` when the machine can spend the local Ollama time.
