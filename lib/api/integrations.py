"""MCP, app connection, and Infisical-backed credential endpoints."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

import config
import infisical

KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,127}$")
NAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")
MAX_SECRET_BYTES = 64_000


def _codex_config_path() -> Path:
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"


def _connections_path() -> Path:
    return config.home() / "integrations.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:3]}...{value[-4:]}"


def _load_connections() -> list[dict]:
    path = _connections_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = data.get("connections") if isinstance(data, dict) else None
    return rows if isinstance(rows, list) else []


def _save_connections(rows: list[dict]) -> None:
    path = _connections_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"connections": rows}, indent=2), encoding="utf-8")
    tmp.replace(path)


def _load_codex_config() -> dict:
    path = _codex_config_path()
    if not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _mcp_servers() -> list[dict]:
    cfg = _load_codex_config()
    rows = []
    for name, value in sorted((cfg.get("mcp_servers") or {}).items()):
        if not isinstance(value, dict):
            continue
        rows.append({
            "name": name,
            "command": value.get("command"),
            "args": value.get("args") or [],
            "env_keys": sorted((value.get("env") or {}).keys()) if isinstance(value.get("env"), dict) else [],
            "has_env": bool(value.get("env")),
            "startup_timeout_sec": value.get("startup_timeout_sec"),
        })
    return rows


def _infisical_env() -> dict:
    host, cid, csecret, pid, env, path = infisical._env()
    return {
        "host": host,
        "client_id_set": bool(cid),
        "client_secret_set": bool(csecret),
        "project_id_set": bool(pid),
        "project_id": _mask(pid or ""),
        "environment": env,
        "secret_path": path,
        "configured": bool(cid and csecret and pid),
    }


def _vault_status() -> dict:
    base = _infisical_env()
    if not base["configured"]:
        return {**base, "reachable": False, "secret_count": 0, "keys": []}
    try:
        client = infisical.make_client()
        if client is None:
            return {**base, "reachable": False, "secret_count": 0, "keys": []}
        _, _, _, pid, env, path = infisical._env()
        secrets = client.list_secrets(pid or "", env, path)
    except Exception as exc:  # noqa: BLE001
        return {**base, "reachable": False, "secret_count": 0, "keys": [], "error": type(exc).__name__}
    return {
        **base,
        "reachable": True,
        "secret_count": len(secrets),
        "keys": [
            {"key": key, "set": True, "length": len(value or ""), "preview": _mask(value or "")}
            for key, value in sorted(secrets.items())
        ],
    }


def status_body() -> dict:
    return {
        "infisical": _vault_status(),
        "mcp": {
            "config": str(_codex_config_path()),
            "servers": _mcp_servers(),
        },
        "connections": _load_connections(),
        "personal_assistant_mode": os.environ.get("ENVY_PERSONAL_ASSISTANT_MODE", "1").lower() not in {"0", "false", "no", "off"},
    }


def handle_status(handler: Any) -> None:
    handler._send_json(status_body())


def upsert_secret_handler(body: Any) -> tuple[int, dict]:
    if not isinstance(body, dict):
        return 400, {"error": "bad_request", "hint": "body must be a JSON object"}
    key = body.get("key")
    value = body.get("value")
    if not isinstance(key, str) or not KEY_RE.match(key):
        return 400, {"error": "bad_secret_key", "hint": "Use uppercase env style, for example GITHUB_TOKEN"}
    if not isinstance(value, str) or not value:
        return 400, {"error": "bad_secret_value", "hint": "value must be a non-empty string"}
    if len(value.encode("utf-8")) > MAX_SECRET_BYTES:
        return 413, {"error": "secret_too_large", "hint": f"max {MAX_SECRET_BYTES} bytes"}

    if not infisical.configured():
        return 503, {"error": "infisical_not_configured", "infisical": _infisical_env()}
    client = infisical.make_client()
    if client is None:
        return 503, {"error": "infisical_unreachable", "infisical": _infisical_env()}
    _, _, _, pid, env, path = infisical._env()
    ok = client.upsert_secret(pid or "", env, key, value, secret_path=path)
    if not ok:
        return 502, {"error": "infisical_write_failed"}
    os.environ[key] = value
    return 200, {"ok": True, "key": key, "stored": "infisical", "updated_at": _now()}


def upsert_connection_handler(body: Any) -> tuple[int, dict]:
    if not isinstance(body, dict):
        return 400, {"error": "bad_request", "hint": "body must be a JSON object"}
    name = body.get("name")
    kind = body.get("kind") or "api"
    if not isinstance(name, str) or not NAME_RE.match(name):
        return 400, {"error": "bad_name", "hint": "Use letters, numbers, dot, dash, or underscore"}
    if not isinstance(kind, str) or len(kind) > 40:
        return 400, {"error": "bad_kind"}
    secret_keys = body.get("secret_keys") or []
    if not isinstance(secret_keys, list) or not all(isinstance(k, str) and KEY_RE.match(k) for k in secret_keys):
        return 400, {"error": "bad_secret_keys"}
    connection = {
        "name": name,
        "kind": kind,
        "base_url": body.get("base_url") if isinstance(body.get("base_url"), str) else "",
        "auth": body.get("auth") if isinstance(body.get("auth"), str) else "api_key",
        "secret_keys": sorted(set(secret_keys)),
        "notes": body.get("notes") if isinstance(body.get("notes"), str) else "",
        "updated_at": _now(),
    }
    rows = [r for r in _load_connections() if r.get("name") != name]
    rows.append(connection)
    rows.sort(key=lambda r: str(r.get("name", "")).lower())
    try:
        _save_connections(rows)
    except OSError:
        return 500, {"error": "connection_save_failed"}
    return 200, {"ok": True, "connection": connection}


def _toml_string(value: str) -> str:
    return json.dumps(value)


def _toml_array(values: list[str]) -> str:
    return "[" + ", ".join(_toml_string(v) for v in values) + "]"


def upsert_mcp_handler(body: Any) -> tuple[int, dict]:
    if not isinstance(body, dict):
        return 400, {"error": "bad_request", "hint": "body must be a JSON object"}
    name = body.get("name")
    command = body.get("command")
    args = body.get("args") or []
    env_keys = body.get("env_keys") or []
    if not isinstance(name, str) or not NAME_RE.match(name):
        return 400, {"error": "bad_name", "hint": "Use letters, numbers, dot, dash, or underscore"}
    if not isinstance(command, str) or not command.strip():
        return 400, {"error": "bad_command"}
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        return 400, {"error": "bad_args"}
    if not isinstance(env_keys, list) or not all(isinstance(k, str) and KEY_RE.match(k) for k in env_keys):
        return 400, {"error": "bad_env_keys"}

    existing = {server["name"] for server in _mcp_servers()}
    if name in existing:
        return 409, {"error": "mcp_exists", "hint": "Existing MCP server edits are not overwritten automatically."}

    cfg_path = _codex_config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "",
        f"[mcp_servers.{name}]",
        f"command = {_toml_string(command.strip())}",
        f"args = {_toml_array(args)}",
    ]
    if env_keys:
        lines.append(f"[mcp_servers.{name}.env]")
        for key in sorted(set(env_keys)):
            lines.append(f"{key} = \"${{{key}}}\"")
    try:
        with cfg_path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        return 500, {"error": "mcp_save_failed"}
    return 200, {"ok": True, "server": {"name": name, "command": command, "args": args, "env_keys": sorted(set(env_keys))}}


def post_handler(path: str, body: Any) -> tuple[int, dict]:
    if path == "/api/v1/integrations/secret":
        return upsert_secret_handler(body)
    if path == "/api/v1/integrations/connection":
        return upsert_connection_handler(body)
    if path == "/api/v1/integrations/mcp":
        return upsert_mcp_handler(body)
    return 404, {"error": "not_found"}
