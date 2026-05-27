"""API submodules consumed by bin/invisible-dashboard.

Each submodule is responsible for a single data source. The dashboard's
do_GET wires them into HTTP routes; the submodules themselves are
transport-agnostic (with the documented exception of tree_local.stream_diffs,
which writes SSE chunks directly to the handler's wfile).
"""
from . import tree_local  # noqa: F401
from . import tree_vps    # noqa: F401
from . import tree_repo   # noqa: F401
