"""Brief + log API for the invisible dashboard daemon.

Routes (path matched in bin/invisible-dashboard):
  GET  /api/v1/projects/<id>/brief  → handle_brief_get  (read brief + suggestions)
  POST /api/v1/projects/<id>/log    → handle_log_post   (append log entry)

Both are mounted manually in bin/invisible-dashboard.do_GET / do_POST
because they have path parameters (the <id>) and don't fit the
exact-match ROUTES dict in lib/api/__init__.py.

Security:
  • Project id MUST match _PROJECT_SLUG_RE (lib.project_store enforces).
    Anything else returns 400 to keep filesystem paths quarantined.
  • Log entry size capped at 8 KiB; oversize = 413.
  • No filesystem path is ever echoed in error bodies.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import project_store  # noqa: E402  — lib/ is on sys.path via bin/invisible-dashboard


_MAX_LOG_BYTES = 8 * 1024  # 8 KiB per entry


# ── GET /api/v1/projects/<id>/brief ─────────────────────────────────────


def handle_brief_get(handler: Any, project_id: str) -> None:
    """Return the per-project brief: context, recent log, current suggestions.

    Truncates context and recent_log to keep the response small for the
    frontend (the full files are still on disk; we just trim what we ship
    over the wire). 4 KiB caps on each — enough for the dashboard preview
    panel.
    """
    try:
        brief = project_store.assemble_brief(project_id)
    except ValueError:
        handler._send_json({"error": "invalid project id"}, 400)
        return
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(
            f"[brief] handle_brief_get({project_id!r}) failed: "
            f"{type(exc).__name__}: {exc}\n"
        )
        handler._send_json({"error": "internal error"}, 500)
        return

    # Trim heavy fields for the wire response. Frontend just needs a
    # preview, not the full long-lived context.
    brief["context"] = _tail(brief.get("context", ""), 4096)
    brief["today_log"] = _tail(brief.get("today_log", ""), 4096)
    brief["recent_log"] = _tail(brief.get("recent_log", ""), 4096)
    handler._send_json(brief)


# ── POST /api/v1/projects/<id>/log ──────────────────────────────────────


def handle_log_post(handler: Any, project_id: str, payload: dict) -> None:
    """Append an entry to today's log.

    Request body (already parsed by the daemon's POST router):
      {
        "entry": "free-form markdown text",
        "source": "user" | "claude" | "system"   (optional; default "user")
      }

    Response: {"ok": true, "log_path": "<path>"} on success.
    """
    if not isinstance(payload, dict):
        handler._send_json({"error": "body must be a JSON object"}, 400)
        return
    entry = payload.get("entry")
    source = payload.get("source", "user")
    if not isinstance(entry, str) or not entry.strip():
        handler._send_json({"error": "entry must be a non-empty string"}, 400)
        return
    if len(entry.encode("utf-8")) > _MAX_LOG_BYTES:
        handler._send_json({"error": f"entry exceeds {_MAX_LOG_BYTES} bytes"}, 413)
        return
    if source not in ("user", "claude", "system"):
        handler._send_json({"error": "source must be one of user|claude|system"}, 400)
        return
    try:
        log_path = project_store.append_log(project_id, entry, source=source)
    except ValueError:
        handler._send_json({"error": "invalid project id"}, 400)
        return
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(
            f"[brief] handle_log_post({project_id!r}) failed: "
            f"{type(exc).__name__}: {exc}\n"
        )
        handler._send_json({"error": "internal error"}, 500)
        return
    handler._send_json({"ok": True, "log_path": str(log_path.name)})


# ── Helpers ─────────────────────────────────────────────────────────────


def _tail(s: str, n: int) -> str:
    """Return the last `n` chars of `s`, with an elided marker if trimmed."""
    if len(s) <= n:
        return s
    return f"[…{len(s) - n} earlier chars omitted…]\n" + s[-n:]
