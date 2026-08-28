"""Envy/Hermes memory endpoints."""

from __future__ import annotations

import urllib.parse
from typing import Any

from hermes_bridge import MEMORY_CATEGORIES, bridge


def search_handler(body: Any) -> tuple[int, dict]:
    if not isinstance(body, dict):
        return 400, {"error": "bad_request", "hint": "body must be a JSON object"}
    query = body.get("q") or body.get("query") or ""
    if not isinstance(query, str):
        return 400, {"error": "bad_request", "hint": "q must be a string"}
    project_id = body.get("project_id") if isinstance(body.get("project_id"), str) else None
    try:
        limit = int(body.get("limit", 20))
    except (TypeError, ValueError):
        limit = 20
    results = bridge().search_memory(query, project_id=project_id, limit=limit)
    return 200, {"results": results, "local_only": True}


def write_handler(body: Any) -> tuple[int, dict]:
    if not isinstance(body, dict):
        return 400, {"error": "bad_request", "hint": "body must be a JSON object"}
    category = body.get("category")
    content = body.get("content")
    if category not in MEMORY_CATEGORIES:
        return 400, {"error": "bad_request", "hint": "invalid category"}
    if not isinstance(content, str) or not content.strip():
        return 400, {"error": "bad_request", "hint": "content is required"}
    project_id = body.get("project_id") if isinstance(body.get("project_id"), str) else None
    source = body.get("source") if isinstance(body.get("source"), str) else "envy"
    try:
        memory = bridge().write_memory(
            category=category,
            content=content,
            project_id=project_id,
            source=source,
            promote=body.get("promote") is True,
            metadata=body.get("metadata") if isinstance(body.get("metadata"), dict) else {},
        )
    except ValueError as exc:
        return 400, {"error": "bad_request", "hint": str(exc)}
    return 200, {"memory": memory, "local_only": True}


def handle_search(handler: Any) -> None:
    q = urllib.parse.parse_qs(urllib.parse.urlparse(handler.path).query)
    status, body = search_handler(
        {
            "q": q.get("q", [""])[0],
            "project_id": q.get("project_id", [None])[0],
            "limit": q.get("limit", [20])[0],
        }
    )
    handler._send_json(body, status)
