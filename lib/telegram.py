"""Telegram bot notifier. Stdlib only. Never raises.

Setup once:
  1. Create a bot via @BotFather, copy the token.
  2. Send the bot any message from your account; then call:
        curl https://api.telegram.org/bot<TOKEN>/getUpdates
     and copy the `chat.id` from the response.
  3. Put TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID into ~/.invisible/.env.

All invisible scripts call `notify(...)` on errors and milestones. If the env
vars aren't set, calls are no-ops — useful for local dev.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
import urllib.request
import urllib.error
from typing import Any


def _token() -> str | None: return os.environ.get("TELEGRAM_BOT_TOKEN")
def _chat()  -> str | None: return os.environ.get("TELEGRAM_CHAT_ID")


def _send(payload: dict) -> bool:
    tok, chat = _token(), _chat()
    if not tok or not chat:
        return False
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    payload.setdefault("chat_id", chat)
    payload.setdefault("disable_web_page_preview", True)
    req = urllib.request.Request(
        url, method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload).encode(),
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=10):
                return True
        except (urllib.error.URLError, socket.timeout):
            time.sleep(1.5 ** attempt)
        except Exception as e:
            print(f"[telegram] {e}", file=sys.stderr)
            return False
    return False


def notify(text: str, *, level: str = "info", source: str = "invisible") -> bool:
    """Send a telegram message. level ∈ {info, warn, error}."""
    icon = {"info": "ℹ️", "warn": "⚠️", "error": "🚨"}.get(level, "•")
    host = socket.gethostname()
    body = f"{icon} *{source}* on `{host}`\n\n{text[:3500]}"
    return _send({"text": body, "parse_mode": "Markdown"})


def notify_error(exc: BaseException, *, source: str = "invisible") -> bool:
    import traceback
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return notify(f"```\n{tb[-2000:]}\n```", level="error", source=source)


def heartbeat(source: str = "invisible") -> bool:
    return notify(f"alive at {time.strftime('%Y-%m-%d %H:%M:%S')}",
                  level="info", source=source)
