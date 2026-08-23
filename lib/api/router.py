"""Local-first query router: local model answers or escalates to Claude.

POST /api/v1/router/ask
    {
        "message":     <str, required>,
        "project_id":  <str, optional slug>,
        "history":     <list, optional — forwarded to the answering model>,
        "force":       <"local"|"claude"|"session", optional — skip classify>,
        "humor_level": <int 0..3, optional>
    }

Flow: qwen3:4b classifies the route (strict JSON, thinking disabled), then:
  local   -> api.ai.chat_handler with the best installed answer model
  claude  -> api.chat.chat_handler (`claude -p` headless)
  session -> writes a handoff packet file and returns its path + a launch hint

Memory: top hermes memory hits are injected into the prompt for every route.
Hermes being down is never fatal. A classify failure falls back to "local" —
the router brain must never block a query.

Security: inherits chat.py's contract — user input never enters argv, project
slugs are validated, packet filenames are server-generated.
"""

from __future__ import annotations

import json
import re
import urllib.error
from datetime import datetime, timezone
from typing import Any

import config
from api import ai
from api import chat

ROUTE_MODEL = "qwen3:4b"
# 30b-a3b needs 14.6GB VRAM — can't stay resident beside the 4b router on a
# 16GB card (every classify forces a model swap). 14b + 4b co-reside fully.
# 30b remains available via an explicit {"model": ...} override.
ANSWER_MODELS = ("qwen3:14b",)
ROUTES = ("local", "claude", "session")
# chat.py (claude route) caps at 8000; leave room for the injected memory block
MAX_MESSAGE_CHARS = 6_000
MEMORY_LIMIT = 5
CLASSIFY_TIMEOUT_S = 20
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

_CLASSIFY_SYSTEM = (
    "You route queries for a developer named Ace. Reply with JSON only.\n"
    'Schema: {"route": "local"|"claude"|"session", "confidence": 0.0-1.0}\n'
    "Routes:\n"
    "- local: quick questions, explanations, drafts, summaries, small code "
    "snippets, brainstorming. Anything a capable 30B local model handles.\n"
    "- claude: hard reasoning, multi-file coding questions, anything needing "
    "web/current information, tool use, or deep knowledge of Ace's repos.\n"
    "- session: a request to actually DO work on a project — build, fix, "
    "refactor, deploy. Needs an interactive coding session.\n"
    "When unsure between local and claude, pick local."
)

_CLASSIFY_FORMAT = {
    "type": "object",
    "properties": {
        "route": {"type": "string", "enum": list(ROUTES)},
        "confidence": {"type": "number"},
    },
    "required": ["route", "confidence"],
}


def _classify(message: str) -> tuple[str, float]:
    """Route a message with the small model. Falls back to ("local", 0.0)."""
    try:
        out = ai._ollama_json(
            "/api/chat",
            {
                "model": ROUTE_MODEL,
                "messages": [
                    {"role": "system", "content": _CLASSIFY_SYSTEM},
                    {"role": "user", "content": message[:2000]},
                ],
                "stream": False,
                "think": False,
                "format": _CLASSIFY_FORMAT,
                "keep_alive": -1,
                "options": {"temperature": 0, "num_predict": 80},
            },
            timeout=CLASSIFY_TIMEOUT_S,
        )
        parsed = json.loads(((out.get("message") or {}).get("content") or "{}"))
        route = parsed.get("route")
        confidence = float(parsed.get("confidence", 0.0))
        if route in ROUTES:
            return route, max(0.0, min(1.0, confidence))
    except (OSError, urllib.error.URLError, TimeoutError, ValueError,
            TypeError, AttributeError, KeyError, json.JSONDecodeError):
        pass
    return "local", 0.0


def _memory_block(message: str, project_id: str | None) -> str:
    """Top hermes memory hits as a prompt section. Empty string on any failure."""
    try:
        from hermes_bridge import bridge

        hits = bridge().search_memory(message, project_id=project_id,
                                      limit=MEMORY_LIMIT) or []
    except Exception:  # noqa: BLE001 — memory is best-effort, never fatal
        return ""
    lines = []
    for hit in hits:
        if isinstance(hit, dict):
            content = (hit.get("content") or "").strip()
            if content:
                lines.append(f"- {content[:300]}")
    if not lines:
        return ""
    return "Relevant memory:\n" + "\n".join(lines[:MEMORY_LIMIT])


def _answer_model() -> str | None:
    status, body = ai.list_models()
    if status != 200:
        return None
    names = {m["name"] for m in body.get("models", [])}
    return next((m for m in ANSWER_MODELS if m in names), None)


def _history_block(history: Any) -> str:
    """Compact recent turns for the stateless claude escalation. '' if none."""
    if not isinstance(history, list) or not history:
        return ""
    lines = []
    for item in history[-6:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content") or item.get("text")
        if role in ("user", "assistant") and isinstance(content, str) and content:
            lines.append(f"{role}: {content[:500]}")
    if not lines:
        return ""
    return "Recent conversation:\n" + "\n".join(lines) + "\n\n"


def _packet(message: str, project_id: str | None, memory: str) -> str:
    created = datetime.now(timezone.utc).isoformat()
    parts = [
        "# Handoff",
        f"Created: {created}",
        f"Project: {project_id or '(none)'}",
        "",
        "## Question",
        message,
    ]
    if memory:
        parts += ["", "## Memory context", memory]
    return "\n".join(parts) + "\n"


def _save_session_packet(message: str, project_id: str | None,
                         memory: str) -> str:
    slug = project_id if (isinstance(project_id, str)
                          and _SLUG_RE.fullmatch(project_id)) else "_global"
    directory = config.home() / "handoffs" / slug
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S-%fZ")
    path = directory / f"router-{stamp}.md"
    path.write_text(_packet(message, project_id, memory), encoding="utf-8")
    return str(path)


def ask_handler(body: Any) -> tuple[int, dict]:
    if not isinstance(body, dict):
        return 400, {"error": "bad_request", "hint": "body must be a JSON object"}
    message = body.get("message")
    if not isinstance(message, str) or not message.strip():
        return 400, {"error": "bad_request", "hint": "field 'message' is required"}
    if len(message) > MAX_MESSAGE_CHARS:
        return 413, {"error": "message_too_large",
                     "hint": f"max {MAX_MESSAGE_CHARS} chars"}
    message = message.strip()
    project_id = body.get("project_id") if isinstance(body.get("project_id"), str) else None

    force = body.get("force")
    if force in ROUTES:
        route, confidence = force, 1.0
    else:
        route, confidence = _classify(message)

    memory = _memory_block(message, project_id)

    if route == "session":
        try:
            path = _save_session_packet(message, project_id, memory)
        except OSError:
            return 500, {"error": "internal error"}
        return 200, {
            "route": "session",
            "confidence": confidence,
            "text": "Handoff packet saved. Launch a Claude Code session with it.",
            "packet_path": path,
            "launch_hint": "claude \"$(Get-Content -Raw '" + path + "')\"",
            "provider": "local",
            "cost": 0,
            "memory_used": bool(memory),
        }

    prompt = f"{memory}\n\n{message}" if memory else message

    if route == "claude":
        history_block = _history_block(body.get("history"))
        status, resp = chat.chat_handler({
            "message": f"{history_block}{prompt}"[:7900],
            "page_context": "router",
            "project_id": project_id,
        })
        if status != 200:
            return status, resp
        resp.update({"route": "claude", "confidence": confidence,
                     "provider": "claude", "memory_used": bool(memory)})
        return 200, resp

    # local
    payload = {
        "message": prompt,
        "page_context": "router",
        "project_id": project_id,
        "history": body.get("history") or [],
        "humor_level": body.get("humor_level"),
    }
    model = _answer_model()
    if model:
        payload["model"] = model
    status, resp = ai.chat_handler(payload)
    if status != 200:
        return status, resp
    resp.update({"route": "local", "confidence": confidence,
                 "memory_used": bool(memory)})
    return 200, resp
