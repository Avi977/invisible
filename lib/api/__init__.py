"""HTTP API route registry for the invisible dashboard daemon.

The dashboard's BaseHTTPRequestHandler.do_GET dispatches into ROUTES for any
path under /api/v1/. Sister workstreams (ai-bubble, folders-3source,
analytics-aggregator) extend this registry by adding one import line and one
ROUTES entry each — the conflict surface is intentionally tiny to make 4-way
merges trivial.

Contract:
  ROUTES: dict[str, Callable[[BaseHTTPRequestHandler], None]]

  Each handler receives the live handler instance and is expected to call
  handler._send_json(...) (or _send_text/_send_html) to produce the response.
  Handlers MUST NOT leak filesystem paths into error responses — wrap any
  IO in try/except and return generic {"error": "internal error"} on failure.
"""

from __future__ import annotations

from . import projects
from . import calendar

# Path → handler callable. Sister workstreams add their entries below this line.
ROUTES: dict = {
    "/api/v1/projects": projects.handle_projects,
    "/api/v1/calendar": calendar.handle_calendar,
}

__all__ = ["ROUTES", "projects", "calendar"]
"""API submodules consumed by bin/invisible-dashboard.

Each submodule is responsible for a single data source / capability. The
dashboard's do_GET / do_POST wires them into HTTP routes; the submodules
themselves are transport-agnostic (with the documented exception of
tree_local.stream_diffs, which writes SSE chunks directly to the handler's
wfile).
"""
from . import chat        # noqa: F401  (ai-bubble: POST /api/v1/chat)
from . import tree_local  # noqa: F401  (folders: GET /api/v1/tree/local + SSE)
from . import tree_vps    # noqa: F401  (folders: GET /api/v1/tree/vps)
from . import tree_repo   # noqa: F401  (folders: GET /api/v1/tree/repo)
