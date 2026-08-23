"""HTTP API route registry for the invisible dashboard daemon.

The dashboard's BaseHTTPRequestHandler.do_GET dispatches into ROUTES for any
path under /api/v1/. Sister workstreams (ai-bubble, folders-3source,
analytics-aggregator, relations-page, calendar-events, tools-page) extend
this registry by adding one import line and one ROUTES entry each — the
conflict surface is intentionally tiny to make N-way merges trivial.

Contract:
  ROUTES: dict[str, Callable[[BaseHTTPRequestHandler], None]]

  Each handler receives the live handler instance and is expected to call
  handler._send_json(...) (or _send_text/_send_html) to produce the response.
  Handlers MUST NOT leak filesystem paths into error responses — wrap any
  IO in try/except and return generic {"error": "internal error"} on failure.
"""

from __future__ import annotations

from . import projects
from . import chat        # noqa: F401  (ai-bubble: POST /api/v1/chat)
from . import tree_local  # noqa: F401  (folders: GET /api/v1/tree/local + SSE)
from . import tree_vps    # noqa: F401  (folders: GET /api/v1/tree/vps)
from . import tree_repo   # noqa: F401  (folders: GET /api/v1/tree/repo)
from . import analytics   # noqa: F401  (analytics: GET /api/v1/analytics)
from . import relations   # noqa: F401  (relations: GET /api/v1/relations)
from . import calendar    # noqa: F401  (calendar: GET /api/v1/calendar)
from . import tools       # noqa: F401  (tools: GET/PUT/DELETE /api/v1/tools — dispatched per-method by invisible-dashboard)
from . import brief       # noqa: F401  (brief: GET /api/v1/projects/<id>/brief, POST /api/v1/projects/<id>/log — path-param dispatch in invisible-dashboard)
from . import ai          # noqa: F401  (local Ollama: GET /api/v1/ai/models, POST /api/v1/ai/chat)
from . import agent       # noqa: F401  (local Envy tool agent)
from . import voice       # noqa: F401  (local OpenWhispr bridge)
from . import graphify_local  # noqa: F401  (local Graphify wrapper)
from . import pty         # noqa: F401  (local PTY daemon control)
from . import integrations  # noqa: F401  (MCP/app connections + Infisical-backed credentials)
from . import memory      # noqa: F401  (Envy/Hermes memory search)
from . import runs        # noqa: F401  (long-running Envy runs)
from . import router      # noqa: F401  (local-first router: POST /api/v1/router/ask)

# Path → handler callable. Sister workstreams add their entries below this line.
ROUTES: dict = {
    "/api/v1/projects": projects.handle_projects,
    "/api/v1/relations": relations.handle_relations,
    "/api/v1/calendar": calendar.handle_calendar,
    "/api/v1/ai/models": ai.handle_models,
    "/api/v1/agent/tools": agent.handle_tools,
    "/api/v1/voice/status": voice.handle_status,
    "/api/v1/graphify/status": graphify_local.handle_status,
    "/api/v1/pty/status": pty.handle_status,
    "/api/v1/integrations": integrations.handle_status,
    "/api/v1/memory/search": memory.handle_search,
}

__all__ = ["ROUTES", "projects", "chat", "tree_local", "tree_vps", "tree_repo", "analytics", "relations", "calendar", "tools", "brief", "ai", "agent", "voice", "graphify_local", "pty", "integrations", "memory", "runs", "router"]
