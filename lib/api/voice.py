"""Local voice-to-prompt bridge.

OpenWhispr is treated as a vendored/local tool. This module never calls a
hosted transcription API. It can read the local OpenWhispr CLI bridge when the
desktop app is running, and it still accepts explicit transcript text as a
manual/offline fallback for the AI prompt box.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_URL = "https://github.com/OpenWhispr/openwhispr.git"
LICENSE = "MIT"
BRIDGE_FILE_VERSION = 1
BRIDGE_TIMEOUT_S = 2


def _vendor_dir() -> Path:
    # lib/api/voice.py -> repo root is parents[2].
    return Path(__file__).resolve().parents[2] / "vendor" / "openwhispr"


def _bridge_file() -> Path:
    override = os.environ.get("OPENWHISPR_BRIDGE_FILE")
    if override:
        return Path(os.path.expanduser(override))
    return Path.home() / ".openwhispr" / "cli-bridge.json"


def _load_bridge_config() -> dict | None:
    path = _bridge_file()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("version") != BRIDGE_FILE_VERSION:
        return None
    port = data.get("port")
    token = data.get("token")
    if not isinstance(port, int) or not (1 <= port <= 65535):
        return None
    if not isinstance(token, str) or not token:
        return None
    return {"port": port, "token": token}


def _bridge_request(path: str) -> dict:
    cfg = _load_bridge_config()
    if cfg is None:
        raise RuntimeError("bridge_missing")
    url = f"http://127.0.0.1:{cfg['port']}{path}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {cfg['token']}"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=BRIDGE_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _bridge_health() -> dict:
    try:
        payload = _bridge_request("/v1/health")
    except (OSError, RuntimeError, urllib.error.URLError, json.JSONDecodeError):
        return {"bridge_present": _load_bridge_config() is not None, "bridge_ready": False}
    return {
        "bridge_present": True,
        "bridge_ready": bool(payload.get("data", {}).get("ok")),
        "bridge_version": payload.get("data", {}).get("version"),
    }


def _extract_transcription_text(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    for key in ("text", "raw_text", "transcript"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _transcription_from_bridge(body: dict) -> tuple[int, dict]:
    try:
        if body.get("transcription_id") is not None:
            tid = int(body.get("transcription_id"))
            payload = _bridge_request(f"/v1/transcriptions/{tid}")
            item = payload.get("data")
        else:
            payload = _bridge_request("/v1/transcriptions/list?limit=1")
            items = payload.get("data") if isinstance(payload, dict) else None
            item = items[0] if isinstance(items, list) and items else None
    except (TypeError, ValueError):
        return 400, {"error": "bad_request", "hint": "transcription_id must be an integer"}
    except (OSError, RuntimeError, urllib.error.URLError, json.JSONDecodeError):
        return 503, {
            "error": "openwhispr_bridge_unavailable",
            "hint": "Start the local OpenWhispr desktop app so its CLI bridge is available.",
            **status_body(),
        }

    text = _extract_transcription_text(item)
    if not text:
        return 404, {
            "error": "openwhispr_transcript_not_found",
            "hint": "No completed local OpenWhispr transcript was available.",
            **status_body(),
        }
    return 200, {
        "text": text,
        "provider": "openwhispr",
        "source": "cli_bridge",
        "transcription_id": item.get("id") if isinstance(item, dict) else None,
        "created_at": item.get("created_at") if isinstance(item, dict) else None,
        "local_only": True,
        "cost": 0,
    }


def status_body() -> dict:
    vendor = _vendor_dir()
    bridge = _bridge_health()
    return {
        "provider": "openwhispr",
        "repo": REPO_URL,
        "license": LICENSE,
        "local_only": True,
        "cost": 0,
        "vendor_path": str(vendor),
        "vendor_present": vendor.exists(),
        "bridge_file": str(_bridge_file()),
        **bridge,
        "cloud_disabled_by_default": True,
        "ready": vendor.exists() and bool(bridge.get("bridge_ready")),
        "hint": "Start local OpenWhispr to expose its localhost CLI bridge; paid/cloud transcription is not used by Envy.",
    }


def handle_status(handler: Any) -> None:
    handler._send_json(status_body())


def transcribe_handler(body: Any) -> tuple[int, dict]:
    if not isinstance(body, dict):
        return 400, {"error": "bad_request", "hint": "body must be a JSON object"}
    transcript = body.get("transcript") or body.get("text")
    if isinstance(transcript, str) and transcript.strip():
        return 200, {
            "text": transcript.strip(),
            "provider": "openwhispr",
            "source": "manual_transcript",
            "local_only": True,
            "cost": 0,
        }
    return _transcription_from_bridge(body)
