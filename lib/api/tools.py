"""Per-project Tools workflow CRUD — GET/PUT/DELETE /api/v1/tools.

Backs the Tools page (n8n-style node canvas) with a tiny JSON blob per
project on disk, replacing the static TOOL_WORKFLOWS frontend mock. There
is no database: each project's graph lives at one file and writes are
atomic and lock-free single-writer.

Data flow:
  GET    /api/v1/tools?project=<slug> ──→ read  config.home()/workflows/<slug>.json
  PUT    /api/v1/tools?project=<slug> ──→ write config.home()/workflows/<slug>.json (atomic)
  DELETE /api/v1/tools?project=<slug> ──→ unlink config.home()/workflows/<slug>.json

The on-disk shape is {"nodes": [...], "edges": [...], "updated_at": "<ISO>"}.
The backend is intentionally a dumb blob store: it only validates the
top-level {nodes: list, edges: list} envelope and stamps updated_at; the
canvas owns the internal node/edge shape.

Security notes:
  - [TRUST BOUNDARY] The `project` query param is attacker-controlled. It is
    validated against a strict slug regex (^[a-z0-9][a-z0-9_-]{0,63}$) BEFORE
    any Path is constructed, so "", ".", "..", strings containing "/" or "%",
    uppercase, and over-length values are all rejected with HTTP 400. No value
    can traverse outside config.home()/workflows/.
  - Writes are atomic: serialize to a temp file in the SAME directory then
    os.replace() onto the target (atomic rename on one filesystem). A reader
    therefore never observes a torn file. Multi-writer concurrency is out of
    scope (lock-free single-writer per project is the chosen model).
  - Every handler wraps its IO in try/except and returns a generic
    {"error": "internal error"} 500 — never a filesystem path or traceback.
    Only type(exc).__name__ is logged to stderr.
  - The root is derived from config.home() (resolves $INVISIBLE_HOME), never a
    hardcoded home directory literal.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# lib/ is on sys.path via bin/invisible-dashboard, so this import works from
# both the daemon and the test harness.
import config

# Strict slug for the project query param. Lowercase alnum start, then up to 63
# of lowercase-alnum / underscore / hyphen (64 chars max). Anchored at both
# ends so no embedded slash, dot, percent, or uppercase can slip through. This
# is applied BEFORE any path construction — the trust boundary for D-03.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


# ────────────────────────────────────────────────────────────────────────
# helpers
# ────────────────────────────────────────────────────────────────────────


def _project_param(handler: Any) -> str | None:
    """Pull the `project` query param off handler.path.

    Returns None when the param is absent or empty (parse_qs drops empty
    values by default), which the slug gate then rejects with 400.
    """
    q = urllib.parse.parse_qs(urllib.parse.urlparse(handler.path).query)
    return q.get("project", [None])[0]


def _valid_slug(project: str | None) -> bool:
    """True only for a non-None string matching the strict slug regex.

    Must run BEFORE constructing any Path so a malicious value can never reach
    the filesystem layer.
    """
    return isinstance(project, str) and bool(_SLUG_RE.match(project))


def _target_for(project: str) -> Path:
    """Resolve the workflow file path for a (pre-validated) slug.

    NEVER hardcodes a home-directory literal — the root comes from
    config.home(), which resolves $INVISIBLE_HOME at call time (D-01).
    """
    return config.home() / "workflows" / f"{project}.json"


def _write_atomic(target: Path, obj: dict) -> None:
    """Atomically write `obj` as JSON to `target`.

    Creates the workflows/ dir on first write (D-02), serializes to a temp file
    in the SAME directory, fsyncs, then os.replace()s onto the target so a
    reader never sees a partially written file. The tmp file is cleaned up on
    any failure before re-raising.
    """
    target.parent.mkdir(parents=True, exist_ok=True)  # D-02 first-write mkdir
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)  # atomic rename, same filesystem
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _fail_500(handler: Any, exc: Exception) -> None:
    """Emit a generic 500 with no path/traceback leak; log only the type name."""
    try:
        sys.stderr.write(f"[api/tools] internal error: {type(exc).__name__}\n")
    except Exception:  # noqa: BLE001
        pass
    try:
        handler._send_json({"error": "internal error"}, status=500)
    except Exception:  # noqa: BLE001
        pass


# ────────────────────────────────────────────────────────────────────────
# public API — transport-agnostic handlers (mirror lib/api/projects.py shape)
# ────────────────────────────────────────────────────────────────────────


def handle_get(handler: Any) -> None:
    """GET /api/v1/tools?project=<slug>.

    Returns {nodes, edges, updated_at} from the file when present. A missing
    file returns 200 {"nodes":[],"edges":[],"updated_at":null} (empty workflow,
    NOT 404) so the canvas loads cleanly for never-saved projects (D-05). An
    invalid/missing project → 400.
    """
    project = _project_param(handler)
    if not _valid_slug(project):
        handler._send_json({"error": "bad_request"}, status=400)
        return
    try:
        target = _target_for(project)
        if not target.exists():
            handler._send_json(
                {"nodes": [], "edges": [], "updated_at": None}, status=200
            )
            return
        with open(target, encoding="utf-8") as f:
            data = json.load(f)
        handler._send_json(
            {
                "nodes": data.get("nodes", []),
                "edges": data.get("edges", []),
                "updated_at": data.get("updated_at"),
            },
            status=200,
        )
    except Exception as exc:  # noqa: BLE001 — generic 500 path
        _fail_500(handler, exc)


def handle_put(handler: Any) -> None:
    """PUT /api/v1/tools?project=<slug>.

    Reads the already-parsed JSON body from handler._json_body (the daemon's
    do_PUT parses the request body and stashes it under that exact attribute —
    keep the name in sync). Validates that nodes and edges are both lists
    (else 400), stamps a server-side ISO-8601 UTC updated_at, writes
    atomically, and returns {"updated_at": <value>} (D-06).
    """
    project = _project_param(handler)
    if not _valid_slug(project):
        handler._send_json({"error": "bad_request"}, status=400)
        return
    try:
        # Body contract: do_PUT stashes the parsed payload on handler._json_body.
        payload = getattr(handler, "_json_body", None) or {}
        nodes = payload.get("nodes") if isinstance(payload, dict) else None
        edges = payload.get("edges") if isinstance(payload, dict) else None
        if not isinstance(nodes, list) or not isinstance(edges, list):
            handler._send_json({"error": "bad_request"}, status=400)
            return
        updated_at = datetime.now(timezone.utc).isoformat()
        _write_atomic(
            _target_for(project),
            {"nodes": nodes, "edges": edges, "updated_at": updated_at},
        )
        handler._send_json({"updated_at": updated_at}, status=200)
    except Exception as exc:  # noqa: BLE001 — generic 500 path
        _fail_500(handler, exc)


def handle_delete(handler: Any) -> None:
    """DELETE /api/v1/tools?project=<slug>.

    Removes the workflow file and returns 200 {"deleted":true}; a missing file
    returns 404 (D-07).
    """
    project = _project_param(handler)
    if not _valid_slug(project):
        handler._send_json({"error": "bad_request"}, status=400)
        return
    try:
        try:
            _target_for(project).unlink()
        except FileNotFoundError:
            handler._send_json({"error": "not found"}, status=404)
            return
        handler._send_json({"deleted": True}, status=200)
    except Exception as exc:  # noqa: BLE001 — generic 500 path
        _fail_500(handler, exc)
