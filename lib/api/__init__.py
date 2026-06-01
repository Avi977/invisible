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
