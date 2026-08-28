"""Local-only AI endpoints backed by Ollama.

GET  /api/v1/ai/models  -> installed Ollama models
POST /api/v1/ai/chat    -> local chat completion through 127.0.0.1:11434

No cloud model APIs are used here. The only network target is loopback.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

OLLAMA_BASE = "http://127.0.0.1:11434"
DEFAULT_MODELS = ("qwen3:14b", "qwen3:4b")
MAX_MESSAGE_CHARS = 12_000
TIMEOUT_S = 180
HUMOR_LEVELS = {
    0: "Humor off: stay direct and professional.",
    1: "Humor low: a rare dry aside is fine, but only when it helps momentum.",
    2: "Humor medium: occasional sassy one-liners are welcome after useful substance.",
    3: "Humor high: be playfully sassy, but never at the cost of accuracy, kindness, or speed.",
}


def _ollama_json(path: str, payload: dict | None = None, timeout: int = 10) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_BASE}{path}",
        data=data,
        method="GET" if payload is None else "POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def list_models() -> tuple[int, dict]:
    try:
        body = _ollama_json("/api/tags", timeout=5)
    except (OSError, urllib.error.URLError, TimeoutError):
        return 503, {
            "provider": "ollama",
            "local_only": True,
            "models": [],
            "default": DEFAULT_MODELS[0],
            "error": "ollama_unavailable",
            "hint": "start Ollama locally; expected http://127.0.0.1:11434",
        }
    models = []
    for item in body.get("models", []) or []:
        name = item.get("name")
        if name:
            models.append({
                "name": name,
                "size": item.get("size"),
                "modified_at": item.get("modified_at"),
            })
    names = {m["name"] for m in models}
    default = next((m for m in DEFAULT_MODELS if m in names), models[0]["name"] if models else DEFAULT_MODELS[0])
    return 200, {
        "provider": "ollama",
        "local_only": True,
        "models": models,
        "default": default,
        "cost": "free_local_inference",
    }


def _humor_level(raw: Any) -> int:
    try:
        level = int(raw)
    except (TypeError, ValueError):
        return 1
    return max(0, min(3, level))


def build_system_prompt(page_context: str, project_id: str | None, humor_level: int) -> str:
    system = (
        "You are Envy, an ambitious female local AI assistant running through Ollama for Ace. "
        "Ace is a computer science major who wants daily execution help, practical automation, "
        "workflow acceleration, and cleaner project handoffs. "
        "Your job is to reduce friction: turn vague intent into next actions, scripts, checks, "
        "PowerShell-friendly commands on Windows, and concise plans. "
        "You have a sharp, confident voice and can make sassy jokes when the humor setting allows it. "
        "Always be useful first: ask only when blocked, call out risky assumptions, and keep answers concise. "
        "Prefer local-first tools and never claim to use paid cloud APIs from these endpoints. "
        "When giving terminal commands for Ace's machine, use Windows PowerShell syntax by default. "
        f"{HUMOR_LEVELS.get(humor_level, HUMOR_LEVELS[1])}"
    )
    if project_id:
        system += f" Current project: {project_id}."
    system += f" Current page: {page_context}."
    return system


def _validate_chat(body: Any) -> tuple[str, str, str | None, list[dict], int]:
    if not isinstance(body, dict):
        raise ValueError("body must be a JSON object")
    message = body.get("message")
    page_context = body.get("page_context") or "Envy"
    project_id = body.get("project_id")
    history = body.get("history") or []
    if not isinstance(message, str) or not message.strip():
        raise ValueError("field 'message' is required")
    if len(message) > MAX_MESSAGE_CHARS:
        raise OverflowError(f"max {MAX_MESSAGE_CHARS} chars")
    if not isinstance(page_context, str):
        raise ValueError("field 'page_context' must be a string")
    if project_id is not None and not isinstance(project_id, str):
        raise ValueError("field 'project_id' must be a string")
    if not isinstance(history, list):
        history = []
    return message.strip(), page_context.strip() or "Envy", project_id, history[-12:], _humor_level(body.get("humor_level"))


def chat_handler(body: Any) -> tuple[int, dict]:
    try:
        message, page_context, project_id, history, humor_level = _validate_chat(body)
    except OverflowError as exc:
        return 413, {"error": "message_too_large", "hint": str(exc)}
    except ValueError as exc:
        return 400, {"error": "bad_request", "hint": str(exc)}

    status, models_body = list_models()
    if status != 200:
        return status, models_body
    available = {m["name"] for m in models_body.get("models", [])}
    requested = body.get("model") if isinstance(body, dict) else None
    if isinstance(requested, str) and requested in available:
        model = requested
    else:
        model = next((m for m in DEFAULT_MODELS if m in available), models_body["default"])

    system = build_system_prompt(page_context, project_id, humor_level)

    messages = [{"role": "system", "content": system}]
    for item in history:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content") or item.get("text")
        if role in ("user", "assistant") and isinstance(content, str) and content:
            messages.append({"role": role, "content": content[:4000]})
    messages.append({"role": "user", "content": message})

    try:
        out = _ollama_json(
            "/api/chat",
            {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.2 + (0.08 * humor_level)},
            },
            timeout=TIMEOUT_S,
        )
    except urllib.error.HTTPError as exc:
        return 502, {"error": "ollama_failed", "hint": f"ollama HTTP {exc.code}"}
    except (OSError, urllib.error.URLError, TimeoutError):
        return 503, {"error": "ollama_unavailable", "hint": "Ollama localhost did not respond"}

    reply = ((out.get("message") or {}).get("content") or "").strip()
    usage = {
        "input_tokens": int(out.get("prompt_eval_count", 0) or 0),
        "output_tokens": int(out.get("eval_count", 0) or 0),
        "duration_ms": int((out.get("total_duration", 0) or 0) / 1_000_000),
    }
    return 200, {
        "text": reply,
        "model": model,
        "provider": "ollama",
        "local_only": True,
        "cost": 0,
        "usage": usage,
        "assistant": {"name": "Envy", "humor_level": humor_level},
    }


def handle_models(handler: Any) -> None:
    status, body = list_models()
    handler._send_json(body, status)
