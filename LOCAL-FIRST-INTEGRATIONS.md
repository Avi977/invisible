# Envy Local-First Integrations

This project keeps the new graph, AI, handoff, and voice path free by default.

## Sources

- Graphify: `https://github.com/safishamsi/graphify`
  - Package: `graphifyy`
  - CLI: `graphify`
  - License: MIT
  - Envy integration: optional local CLI wrapper under `/api/v1/graphify/*`
- OpenWhispr: `https://github.com/OpenWhispr/openwhispr.git`
  - Vendored as a Git submodule at `vendor/openwhispr`
  - Pinned commit: `01f8557b0cce141afa3a607a65bd5195ea8fa40c`
  - License: MIT
- Ollama: local runtime at `http://127.0.0.1:11434`
  - Envy defaults: `qwen3:14b`, fallback `qwen3:4b`
  - Cost: free local inference

## Cost Guardrails

The new Envy endpoints use localhost services only:

- `GET /api/v1/ai/models`
- `POST /api/v1/ai/chat`
- `POST /api/v1/handoff/draft`
- `POST /api/v1/handoff/save`
- `GET /api/v1/voice/status`
- `POST /api/v1/voice/transcribe`
- `GET /api/v1/graphify/status`
- `POST /api/v1/graphify/run`

No OpenAI, Anthropic, OpenWhispr cloud, hosted transcription, or hosted model
API is called by these paths. If a cloud/BYOK path is added later, it should
be opt-in, visibly labeled as paid/optional, and disabled by default.
