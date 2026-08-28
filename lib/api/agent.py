"""Local Envy agent endpoints.

This module turns the Ollama chat endpoint into a small tool-using agent.
The agent is intentionally local-first: reasoning goes through Ollama on
127.0.0.1, tools operate inside an Envy sandbox by default, and MCP/plugin
support starts with local inventory discovery instead of remote mutation.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import base64
import ctypes
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

import config
import tool_gateway
from api import ai

MAX_MESSAGE_CHARS = 12_000
MAX_TOOL_STEPS = 8
MAX_TOOL_CALLS_PER_STEP = 4
MAX_FILE_BYTES = 96_000
MAX_WRITE_BYTES = 96_000
MAX_SHELL_OUTPUT_CHARS = 12_000
DEFAULT_SHELL_TIMEOUT_S = 30
MAX_SHELL_TIMEOUT_S = 90
MAX_SCREEN_IMAGE_BYTES = 3_500_000
VISION_REQUEST_RE = re.compile(r"\b(screen|screenshot|cursor|pointing|see|look at|visible|copy this text|ocr)\b", re.IGNORECASE)

_SLUG_RE = re.compile(r"[^a-zA-Z0-9_.-]+")
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_BLOCKED_SHELL_PATTERNS = (
    re.compile(r"\bformat-volume\b", re.IGNORECASE),
    re.compile(r"\bdiskpart\b", re.IGNORECASE),
    re.compile(r"\bshutdown\b", re.IGNORECASE),
    re.compile(r"\brestart-computer\b", re.IGNORECASE),
    re.compile(r"\bstop-computer\b", re.IGNORECASE),
    re.compile(r"\bset-executionpolicy\b", re.IGNORECASE),
    re.compile(r"\bremove-item\s+[^;\n]*(?:[a-z]:\\|/)\s*(?:-recurse|-r)\b", re.IGNORECASE),
)


def _slug(value: str | None) -> str:
    raw = (value or "default").strip() or "default"
    safe = _SLUG_RE.sub("_", raw).strip("._-")
    return (safe or "default")[:64].lower()


def sandbox_root(project_id: str | None) -> Path:
    return (config.home() / "sandbox" / _slug(project_id)).resolve()


def personal_assistant_enabled() -> bool:
    raw = os.environ.get("ENVY_PERSONAL_ASSISTANT_MODE", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _safe_join(root: Path, rel_path: str | None) -> Path:
    rel = (rel_path or ".").strip() or "."
    candidate = (root / rel).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("path escapes sandbox")
    return candidate


def _resolve_system_path(raw_path: str | None, *, default: Path | None = None) -> Path:
    raw = (raw_path or "").strip()
    if not raw:
        return (default or Path.home()).resolve()
    return Path(os.path.expandvars(os.path.expanduser(raw))).resolve()


def _project_root(project_id: str | None) -> Path | None:
    if not project_id:
        return None
    meta = config.project_meta(project_id)
    repo = meta.get("repo_path")
    if not isinstance(repo, str) or not repo.strip():
        return None
    try:
        return Path(os.path.expanduser(repo)).resolve()
    except OSError:
        return None


def _truncate(text: str, limit: int = MAX_SHELL_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"


def _tool_specs() -> list[dict]:
    tools = [
        {
            "name": "sandbox_shell",
            "description": "Run a PowerShell command in the project sandbox working directory.",
            "args": {"command": "string", "timeout_s": "optional integer <= 90"},
        },
        {
            "name": "sandbox_list",
            "description": "List files under the project sandbox.",
            "args": {"path": "optional relative path"},
        },
        {
            "name": "sandbox_read_file",
            "description": "Read a UTF-8 text file from the project sandbox.",
            "args": {"path": "relative path"},
        },
        {
            "name": "sandbox_write_file",
            "description": "Write a UTF-8 text file inside the project sandbox.",
            "args": {"path": "relative path", "content": "string"},
        },
        {
            "name": "project_status",
            "description": "Return local project metadata and configured repository path.",
            "args": {},
        },
        {
            "name": "mcp_inventory",
            "description": "List configured Codex MCP servers from ~/.codex/config.toml.",
            "args": {},
        },
        {
            "name": "plugin_inventory",
            "description": "List installed Codex plugin cache entries.",
            "args": {},
        },
    ]
    if personal_assistant_enabled():
        tools.extend([
            {
                "name": "system_shell",
                "description": "Run a PowerShell command on the user's machine from a chosen cwd. Obvious destructive system commands are blocked.",
                "args": {"command": "string", "cwd": "optional absolute path or ~ path", "timeout_s": "optional integer <= 90"},
            },
            {
                "name": "system_list",
                "description": "List files from any local folder the Envy process can access.",
                "args": {"path": "optional absolute path or ~ path"},
            },
            {
                "name": "system_read_file",
                "description": "Read a UTF-8 text file from anywhere the Envy process can access.",
                "args": {"path": "absolute path or ~ path"},
            },
            {
                "name": "system_write_file",
                "description": "Write a UTF-8 text file anywhere the Envy process can access.",
                "args": {"path": "absolute path or ~ path", "content": "string"},
            },
            {
                "name": "clipboard_get",
                "description": "Read the current Windows clipboard text.",
                "args": {},
            },
            {
                "name": "clipboard_set",
                "description": "Set the Windows clipboard text.",
                "args": {"text": "string"},
            },
            {
                "name": "screen_snapshot",
                "description": "Capture the current screen, cursor position, and active window. Use include_image=true for visual questions such as what is on screen or what the cursor points at.",
                "args": {"include_image": "optional boolean", "all_screens": "optional boolean"},
            },
        ])
    return tool_gateway.enrich_specs(tools)


def tool_catalog() -> dict:
    return {
        "agent": "Envy",
        "mode": "local_ollama_tool_agent",
        "access": {
            "personal_assistant_mode": personal_assistant_enabled(),
            "system_tools": personal_assistant_enabled(),
            "screen_capture": personal_assistant_enabled(),
            "clipboard": personal_assistant_enabled(),
            "dangerous_shell_patterns_blocked": True,
        },
        "tools": _tool_specs(),
        "gateway": {
            "schema": "envy.tool_gateway.v1",
            "progressive_disclosure": True,
            "public_tools": ["search_tools", "describe_tool", "execute_tool"],
            "risk_levels": sorted(tool_gateway.RISK_LEVELS),
        },
        "limits": {
            "max_tool_steps": MAX_TOOL_STEPS,
            "max_tool_calls_per_step": MAX_TOOL_CALLS_PER_STEP,
            "shell_timeout_s": MAX_SHELL_TIMEOUT_S,
            "file_bytes": MAX_FILE_BYTES,
        },
    }


def _tool_sandbox_shell(args: dict, root: Path) -> dict:
    command = args.get("command")
    if not isinstance(command, str) or not command.strip():
        return {"ok": False, "error": "command is required"}
    if len(command) > 4000:
        return {"ok": False, "error": "command too large"}
    for pattern in _BLOCKED_SHELL_PATTERNS:
        if pattern.search(command):
            return {"ok": False, "error": "blocked dangerous shell pattern"}

    root.mkdir(parents=True, exist_ok=True)
    timeout_s = args.get("timeout_s", DEFAULT_SHELL_TIMEOUT_S)
    try:
        timeout_s = int(timeout_s)
    except (TypeError, ValueError):
        timeout_s = DEFAULT_SHELL_TIMEOUT_S
    timeout_s = max(1, min(timeout_s, MAX_SHELL_TIMEOUT_S))

    env = {
        **os.environ,
        "ENVY_SANDBOX_ROOT": str(root),
        "ENVY_AGENT": "1",
    }
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "timeout_s": timeout_s}
    except FileNotFoundError:
        return {"ok": False, "error": "powershell not found"}
    except OSError as exc:
        return {"ok": False, "error": type(exc).__name__}

    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": _truncate(proc.stdout or ""),
        "stderr": _truncate(proc.stderr or ""),
        "cwd": str(root),
    }


def _normalize_timeout(raw: Any) -> int:
    try:
        timeout_s = int(raw)
    except (TypeError, ValueError):
        timeout_s = DEFAULT_SHELL_TIMEOUT_S
    return max(1, min(timeout_s, MAX_SHELL_TIMEOUT_S))


def _shell_block_reason(command: str) -> str | None:
    for pattern in _BLOCKED_SHELL_PATTERNS:
        if pattern.search(command):
            return "blocked dangerous shell pattern"
    return None


def _tool_system_shell(args: dict, project_id: str | None) -> dict:
    if not personal_assistant_enabled():
        return {"ok": False, "error": "personal assistant mode disabled"}
    command = args.get("command")
    if not isinstance(command, str) or not command.strip():
        return {"ok": False, "error": "command is required"}
    if len(command) > 4000:
        return {"ok": False, "error": "command too large"}
    blocked = _shell_block_reason(command)
    if blocked:
        return {"ok": False, "error": blocked}

    default_cwd = _project_root(project_id) or Path.home()
    cwd = _resolve_system_path(args.get("cwd"), default=default_cwd)
    if not cwd.exists() or not cwd.is_dir():
        return {"ok": False, "error": "cwd not found or not a directory", "cwd": str(cwd)}

    timeout_s = _normalize_timeout(args.get("timeout_s"))
    env = {
        **os.environ,
        "ENVY_AGENT": "1",
        "ENVY_PERSONAL_ASSISTANT_MODE": "1",
    }
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "timeout_s": timeout_s, "cwd": str(cwd)}
    except FileNotFoundError:
        return {"ok": False, "error": "powershell not found"}
    except OSError as exc:
        return {"ok": False, "error": type(exc).__name__, "cwd": str(cwd)}

    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": _truncate(proc.stdout or ""),
        "stderr": _truncate(proc.stderr or ""),
        "cwd": str(cwd),
    }


def _tool_system_list(args: dict) -> dict:
    if not personal_assistant_enabled():
        return {"ok": False, "error": "personal assistant mode disabled"}
    target = _resolve_system_path(args.get("path"))
    if not target.exists():
        return {"ok": False, "error": "not found", "path": str(target)}
    if not target.is_dir():
        return {"ok": False, "error": "not a directory", "path": str(target)}
    rows = []
    try:
        for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:300]:
            rows.append({
                "name": item.name,
                "path": str(item),
                "type": "dir" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
            })
    except OSError as exc:
        return {"ok": False, "error": type(exc).__name__, "path": str(target)}
    return {"ok": True, "path": str(target), "items": rows}


def _tool_system_read_file(args: dict) -> dict:
    if not personal_assistant_enabled():
        return {"ok": False, "error": "personal assistant mode disabled"}
    path = args.get("path")
    if not isinstance(path, str) or not path.strip():
        return {"ok": False, "error": "path is required"}
    target = _resolve_system_path(path)
    if not target.exists() or not target.is_file():
        return {"ok": False, "error": "not found", "path": str(target)}
    try:
        size = target.stat().st_size
        if size > MAX_FILE_BYTES:
            return {"ok": False, "error": "file too large", "size": size, "path": str(target)}
        return {"ok": True, "path": str(target), "content": target.read_text(encoding="utf-8")}
    except UnicodeDecodeError:
        return {"ok": False, "error": "file is not utf-8 text", "path": str(target)}
    except OSError as exc:
        return {"ok": False, "error": type(exc).__name__, "path": str(target)}


def _tool_system_write_file(args: dict) -> dict:
    if not personal_assistant_enabled():
        return {"ok": False, "error": "personal assistant mode disabled"}
    path = args.get("path")
    content = args.get("content")
    if not isinstance(path, str) or not path.strip():
        return {"ok": False, "error": "path is required"}
    if not isinstance(content, str):
        return {"ok": False, "error": "content must be a string"}
    if len(content.encode("utf-8")) > MAX_WRITE_BYTES:
        return {"ok": False, "error": "content too large"}
    target = _resolve_system_path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(target), "bytes": len(content.encode("utf-8"))}
    except OSError as exc:
        return {"ok": False, "error": type(exc).__name__, "path": str(target)}


def _clipboard_text_windows(value: str | None = None) -> str:
    try:
        import win32clipboard  # type: ignore
        import win32con  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pywin32 clipboard support unavailable") from exc

    win32clipboard.OpenClipboard()
    try:
        if value is None:
            try:
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            except TypeError:
                return ""
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, value)
        return value
    finally:
        win32clipboard.CloseClipboard()


def _tool_clipboard_get() -> dict:
    if not personal_assistant_enabled():
        return {"ok": False, "error": "personal assistant mode disabled"}
    try:
        return {"ok": True, "text": _clipboard_text_windows()}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "hint": str(exc)}


def _tool_clipboard_set(args: dict) -> dict:
    if not personal_assistant_enabled():
        return {"ok": False, "error": "personal assistant mode disabled"}
    text = args.get("text")
    if not isinstance(text, str):
        return {"ok": False, "error": "text must be a string"}
    try:
        _clipboard_text_windows(text)
        return {"ok": True, "chars": len(text)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "hint": str(exc)}


def _cursor_position() -> dict:
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    pt = POINT()
    if os.name == "nt" and ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):  # type: ignore[attr-defined]
        return {"x": int(pt.x), "y": int(pt.y)}
    return {"x": None, "y": None}


def _active_window_title() -> str:
    try:
        import win32gui  # type: ignore
        hwnd = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(hwnd) if hwnd else ""
    except Exception:  # noqa: BLE001
        return ""


def _tool_screen_snapshot(args: dict) -> dict:
    if not personal_assistant_enabled():
        return {"ok": False, "error": "personal assistant mode disabled"}
    try:
        from PIL import ImageGrab  # type: ignore
    except ImportError:
        return {"ok": False, "error": "pillow not installed"}

    include_image = args.get("include_image") is True
    all_screens = args.get("all_screens", True) is not False
    out_dir = config.home() / "screen"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"screen-{int(time.time() * 1000)}.png"
    try:
        image = ImageGrab.grab(all_screens=all_screens)
        image.save(path)
        size = path.stat().st_size
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "hint": str(exc)}

    result = {
        "ok": True,
        "path": str(path),
        "width": int(image.width),
        "height": int(image.height),
        "bytes": int(size),
        "cursor": _cursor_position(),
        "active_window_title": _active_window_title(),
        "vision_hint": "Use a local vision-capable Ollama model to describe image contents.",
    }
    if include_image and size <= MAX_SCREEN_IMAGE_BYTES:
        result["image_base64"] = base64.b64encode(path.read_bytes()).decode("ascii")
    elif include_image:
        result["image_omitted"] = f"image is {size} bytes, over {MAX_SCREEN_IMAGE_BYTES}"
    return result


def _tool_sandbox_list(args: dict, root: Path) -> dict:
    try:
        target = _safe_join(root, args.get("path"))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    target.mkdir(parents=True, exist_ok=True) if target == root else None
    if not target.exists():
        return {"ok": False, "error": "not found"}
    if not target.is_dir():
        return {"ok": False, "error": "not a directory"}
    rows = []
    try:
        for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:200]:
            rows.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
            })
    except OSError as exc:
        return {"ok": False, "error": type(exc).__name__}
    return {"ok": True, "path": str(target.relative_to(root) if target != root else "."), "items": rows}


def _tool_sandbox_read_file(args: dict, root: Path) -> dict:
    try:
        target = _safe_join(root, args.get("path"))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    if not target.exists() or not target.is_file():
        return {"ok": False, "error": "not found"}
    try:
        size = target.stat().st_size
        if size > MAX_FILE_BYTES:
            return {"ok": False, "error": "file too large", "size": size}
        return {"ok": True, "path": str(target.relative_to(root)), "content": target.read_text(encoding="utf-8")}
    except UnicodeDecodeError:
        return {"ok": False, "error": "file is not utf-8 text"}
    except OSError as exc:
        return {"ok": False, "error": type(exc).__name__}


def _tool_sandbox_write_file(args: dict, root: Path) -> dict:
    path = args.get("path")
    content = args.get("content")
    if not isinstance(path, str) or not path.strip():
        return {"ok": False, "error": "path is required"}
    if not isinstance(content, str):
        return {"ok": False, "error": "content must be a string"}
    if len(content.encode("utf-8")) > MAX_WRITE_BYTES:
        return {"ok": False, "error": "content too large"}
    try:
        target = _safe_join(root, path)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(target.relative_to(root)), "bytes": len(content.encode("utf-8"))}
    except OSError as exc:
        return {"ok": False, "error": type(exc).__name__}


def _tool_project_status(project_id: str | None, root: Path) -> dict:
    repo = _project_root(project_id)
    return {
        "ok": True,
        "project": project_id or "default",
        "sandbox_root": str(root),
        "repo_path": str(repo) if repo else None,
        "repo_exists": bool(repo and repo.exists()),
    }


def _tool_mcp_inventory() -> dict:
    cfg_path = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"
    if not cfg_path.exists():
        return {"ok": False, "error": "codex config not found"}
    try:
        cfg = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return {"ok": False, "error": type(exc).__name__}
    servers = []
    for name, value in sorted((cfg.get("mcp_servers") or {}).items()):
        if not isinstance(value, dict):
            continue
        servers.append({
            "name": name,
            "command": value.get("command"),
            "args": value.get("args") or [],
            "has_env": bool(value.get("env")),
            "startup_timeout_sec": value.get("startup_timeout_sec"),
        })
    return {"ok": True, "config": str(cfg_path), "servers": servers}


def _tool_plugin_inventory() -> dict:
    root = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "plugins" / "cache"
    if not root.exists():
        return {"ok": True, "plugins": []}
    rows = []
    try:
        for marketplace in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if not marketplace.is_dir():
                continue
            for plugin in sorted(marketplace.iterdir(), key=lambda p: p.name.lower()):
                if plugin.is_dir():
                    rows.append({"marketplace": marketplace.name, "plugin": plugin.name})
    except OSError as exc:
        return {"ok": False, "error": type(exc).__name__}
    return {"ok": True, "plugins": rows[:200]}


def _execute_tool(
    name: str,
    args: Any,
    project_id: str | None,
    *,
    task_id: str | None = None,
    run_id: str | None = None,
    approval_mode: str | None = "agent",
) -> dict:
    root = sandbox_root(project_id)
    clean_args = args if isinstance(args, dict) else {}
    tool = tool_gateway.get_tool(_tool_specs(), name)
    if tool is None:
        result = {"ok": False, "error": "unknown tool"}
        tool_gateway.audit_tool_call(
            tool_id=name,
            args=clean_args,
            result=result,
            tool=None,
            approved=False,
            task_id=task_id,
            run_id=run_id,
        )
        return result
    if tool_gateway.approval_required(tool, approval_mode):
        result = {
            "ok": False,
            "error": "approval_required",
            "tool_id": tool["id"],
            "risk_level": tool["risk_level"],
            "requires_approval": True,
        }
        tool_gateway.audit_tool_call(
            tool_id=tool["id"],
            args=clean_args,
            result=result,
            tool=tool,
            approved=False,
            task_id=task_id,
            run_id=run_id,
        )
        return result
    started = time.time()
    if name == "sandbox_shell":
        result = _tool_sandbox_shell(clean_args, root)
    elif name == "sandbox_list":
        result = _tool_sandbox_list(clean_args, root)
    elif name == "sandbox_read_file":
        result = _tool_sandbox_read_file(clean_args, root)
    elif name == "sandbox_write_file":
        result = _tool_sandbox_write_file(clean_args, root)
    elif name == "project_status":
        result = _tool_project_status(project_id, root)
    elif name == "mcp_inventory":
        result = _tool_mcp_inventory()
    elif name == "plugin_inventory":
        result = _tool_plugin_inventory()
    elif name == "system_shell":
        result = _tool_system_shell(clean_args, project_id)
    elif name == "system_list":
        result = _tool_system_list(clean_args)
    elif name == "system_read_file":
        result = _tool_system_read_file(clean_args)
    elif name == "system_write_file":
        result = _tool_system_write_file(clean_args)
    elif name == "clipboard_get":
        result = _tool_clipboard_get()
    elif name == "clipboard_set":
        result = _tool_clipboard_set(clean_args)
    elif name == "screen_snapshot":
        result = _tool_screen_snapshot(clean_args)
    else:
        result = {"ok": False, "error": "unknown tool"}
    result["elapsed_ms"] = int((time.time() - started) * 1000)
    tool_gateway.audit_tool_call(
        tool_id=tool["id"],
        args=clean_args,
        result=result,
        tool=tool,
        approved=not tool_gateway.approval_required(tool, approval_mode),
        task_id=task_id,
        run_id=run_id,
    )
    return result


def _validate(body: Any) -> tuple[str, str, str | None, list[dict], int, str | None, bool, int, str | None, str | None, str | None, str | None]:
    if not isinstance(body, dict):
        raise ValueError("body must be a JSON object")
    message = body.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("field 'message' is required")
    if len(message) > MAX_MESSAGE_CHARS:
        raise OverflowError(f"max {MAX_MESSAGE_CHARS} chars")
    page_context = body.get("page_context") or "Envy"
    project_id = body.get("project_id")
    history = body.get("history") or []
    if not isinstance(page_context, str):
        raise ValueError("field 'page_context' must be a string")
    if project_id is not None and not isinstance(project_id, str):
        raise ValueError("field 'project_id' must be a string")
    if not isinstance(history, list):
        history = []
    model = body.get("model")
    tools_enabled = body.get("tools_enabled", True) is not False
    session_id = body.get("session_id") if isinstance(body.get("session_id"), str) else None
    task_id = body.get("task_id") if isinstance(body.get("task_id"), str) else None
    approval_mode = body.get("approval_mode") if isinstance(body.get("approval_mode"), str) else "agent"
    handoff_target = body.get("handoff_target") if isinstance(body.get("handoff_target"), str) else None
    try:
        max_steps = int(body.get("max_steps", 5))
    except (TypeError, ValueError):
        max_steps = 5
    return (
        message.strip(),
        page_context.strip() or "Envy",
        project_id,
        history[-10:],
        ai._humor_level(body.get("humor_level")),
        model if isinstance(model, str) else None,
        tools_enabled,
        max(0, min(max_steps, MAX_TOOL_STEPS)),
        session_id,
        task_id,
        approval_mode,
        handoff_target,
    )


def _system_prompt(page_context: str, project_id: str | None, humor_level: int, tools_enabled: bool) -> str:
    base = ai.build_system_prompt(page_context, project_id, humor_level)
    if not tools_enabled:
        return base + " Tools are disabled for this request; answer normally."
    return (
        base
        + "\nYou are now running as a local tool-using agent. Sandbox tools are constrained to Envy's sandbox. "
        + "System, screen, and clipboard tools are available only when personal assistant mode is enabled; use them for Ace's local-machine requests. "
        + "For screen questions, call screen_snapshot with include_image=true, then describe what the vision model can see; if the selected model cannot see images, say that plainly and report the captured path, cursor, and active window. "
        + "Use tools when they materially help. Keep tool calls small and verify important results. "
        + "Respond with exactly one JSON object, no markdown fences. Schema: "
        + '{"thought":"short private plan","tool_calls":[{"tool":"tool_name","args":{}}],"final":null} '
        + "or "
        + '{"thought":"done","tool_calls":[],"final":"concise answer for the user"}. '
        + "Available tools: "
        + json.dumps(_tool_specs(), separators=(",", ":"))
    )


def _model_accepts_images(model: str) -> bool:
    name = model.lower()
    return any(marker in name for marker in ("llava", "vision", "qwen2-vl", "qwen2.5-vl", "minicpm-v", "bakllava", "moondream", "gemma3"))


def _public_tool_result(result: dict) -> dict:
    if "image_base64" not in result:
        return result
    clean = dict(result)
    clean.pop("image_base64", None)
    clean["image_attached_to_model"] = True
    return clean


def _select_model(requested: str | None, *, prefer_vision: bool = False) -> tuple[int, dict, str | None]:
    status, models_body = ai.list_models()
    if status != 200:
        return status, models_body, None
    available = {m["name"] for m in models_body.get("models", [])}
    if prefer_vision:
        vision_model = next((m for m in available if _model_accepts_images(m)), None)
        if vision_model:
            return 200, models_body, vision_model
    if requested and requested in available:
        return 200, models_body, requested
    model = next((m for m in ai.DEFAULT_MODELS if m in available), models_body["default"])
    return 200, models_body, model


def _ollama_chat(model: str, messages: list[dict], humor_level: int) -> tuple[int, dict]:
    try:
        out = ai._ollama_json(
            "/api/chat",
            {
                "model": model,
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1 + (0.04 * humor_level)},
            },
            timeout=ai.TIMEOUT_S,
        )
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, TimeoutError):
            return 503, {"error": "ollama_unavailable", "hint": "Ollama localhost did not respond"}
        return 503, {"error": "ollama_unavailable", "hint": type(exc).__name__}
    return 200, out


def _parse_agent_json(text: str) -> dict | None:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        match = _JSON_RE.search(text)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


def chat_handler(body: Any) -> tuple[int, dict]:
    try:
        (
            message,
            page_context,
            project_id,
            history,
            humor_level,
            requested_model,
            tools_enabled,
            max_steps,
            session_id,
            task_id,
            approval_mode,
            handoff_target,
        ) = _validate(body)
    except OverflowError as exc:
        return 413, {"error": "message_too_large", "hint": str(exc)}
    except ValueError as exc:
        return 400, {"error": "bad_request", "hint": str(exc)}

    status, models_body, model = _select_model(
        requested_model,
        prefer_vision=bool(VISION_REQUEST_RE.search(message)),
    )
    if status != 200 or not model:
        return status, models_body

    messages = [{"role": "system", "content": _system_prompt(page_context, project_id, humor_level, tools_enabled)}]
    for item in history:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content") or item.get("text")
        if role in ("user", "assistant") and isinstance(content, str) and content:
            messages.append({"role": role, "content": content[:4000]})
    messages.append({"role": "user", "content": message})

    trace = []
    final = ""
    usage = {"input_tokens": 0, "output_tokens": 0, "duration_ms": 0}
    steps_used = 0

    for step in range(max_steps + 1):
        steps_used = step
        chat_status, out = _ollama_chat(model, messages, humor_level)
        if chat_status != 200:
            return chat_status, out
        usage["input_tokens"] += int(out.get("prompt_eval_count", 0) or 0)
        usage["output_tokens"] += int(out.get("eval_count", 0) or 0)
        usage["duration_ms"] += int((out.get("total_duration", 0) or 0) / 1_000_000)
        raw = ((out.get("message") or {}).get("content") or "").strip()

        if not tools_enabled:
            final = raw
            break

        parsed = _parse_agent_json(raw)
        if not parsed:
            final = raw or "The local model did not return a usable agent response."
            break

        tool_calls = parsed.get("tool_calls") or []
        if parsed.get("final") and not tool_calls:
            final = str(parsed.get("final") or "").strip()
            break
        if not isinstance(tool_calls, list) or not tool_calls or step >= max_steps:
            final = str(parsed.get("final") or "").strip() or "I stopped after the current agent step."
            break

        tool_results = []
        image_payloads = []
        for call in tool_calls[:MAX_TOOL_CALLS_PER_STEP]:
            if not isinstance(call, dict):
                continue
            name = call.get("tool")
            args = call.get("args") or {}
            if not isinstance(name, str):
                continue
            result = _execute_tool(name, args, project_id, task_id=task_id, approval_mode=approval_mode)
            if isinstance(result.get("image_base64"), str):
                image_payloads.append(result["image_base64"])
            entry = {
                "tool": name,
                "args": args if isinstance(args, dict) else {},
                "result": _public_tool_result(result),
            }
            trace.append(entry)
            tool_results.append(entry)

        messages.append({"role": "assistant", "content": raw})
        tool_message = {
            "role": "user",
            "content": "Tool results:\n" + json.dumps(tool_results, ensure_ascii=False) + "\nContinue. Return final if done.",
        }
        if image_payloads and _model_accepts_images(model):
            tool_message["images"] = image_payloads[:1]
        elif image_payloads:
            tool_message["content"] += "\nA screenshot was captured, but the selected model may not support image input."
        messages.append(tool_message)

    if not final:
        final = "I used the available local tools but did not get a final response from Ollama."

    return 200, {
        "text": final,
        "model": model,
        "provider": "ollama",
        "agent_mode": tools_enabled,
        "assistant": {"name": "Envy", "humor_level": humor_level},
        "sandbox": {"root": str(sandbox_root(project_id)), "project": _slug(project_id)},
        "tools": trace,
        "steps": steps_used,
        "session_id": session_id,
        "task_id": task_id,
        "approval_mode": approval_mode,
        "handoff_target": handoff_target,
        "usage": usage,
        "cost": 0,
        "local_only": True,
        "mcp": _tool_mcp_inventory(),
        "plugins": _tool_plugin_inventory(),
    }


def handle_tools(handler: Any) -> None:
    handler._send_json(tool_catalog(), 200)


def search_tools_handler(body: Any) -> tuple[int, dict]:
    if not isinstance(body, dict):
        return 400, {"error": "bad_request", "hint": "body must be a JSON object"}
    query = body.get("query")
    if not isinstance(query, str):
        return 400, {"error": "bad_request", "hint": "query is required"}
    category = body.get("category") if isinstance(body.get("category"), str) else None
    try:
        limit = int(body.get("limit", 12))
    except (TypeError, ValueError):
        limit = 12
    return 200, {
        "tools": tool_gateway.search(_tool_specs(), query, category=category, limit=limit),
        "local_only": True,
        "progressive_disclosure": True,
    }


def describe_tool_handler(body: Any) -> tuple[int, dict]:
    if not isinstance(body, dict):
        return 400, {"error": "bad_request", "hint": "body must be a JSON object"}
    tool_id = body.get("tool_id") or body.get("id")
    if not isinstance(tool_id, str) or not tool_id.strip():
        return 400, {"error": "bad_request", "hint": "tool_id is required"}
    tool = tool_gateway.get_tool(_tool_specs(), tool_id)
    if tool is None:
        return 404, {"error": "not_found"}
    return 200, {"tool": tool, "local_only": True}


def execute_tool_handler(body: Any) -> tuple[int, dict]:
    if not isinstance(body, dict):
        return 400, {"error": "bad_request", "hint": "body must be a JSON object"}
    tool_id = body.get("tool_id")
    if not isinstance(tool_id, str) or not tool_id.strip():
        return 400, {"error": "bad_request", "hint": "tool_id is required"}
    args = body.get("args") if isinstance(body.get("args"), dict) else {}
    project_id = body.get("project_id") if isinstance(body.get("project_id"), str) else None
    task_id = body.get("task_id") if isinstance(body.get("task_id"), str) else None
    run_id = body.get("run_id") if isinstance(body.get("run_id"), str) else None
    approval_mode = body.get("approval_mode") if isinstance(body.get("approval_mode"), str) else "default"
    result = _execute_tool(
        tool_id,
        args,
        project_id,
        task_id=task_id,
        run_id=run_id,
        approval_mode=approval_mode,
    )
    status = 200
    body = {"result": _public_tool_result(result), "local_only": True}
    if result.get("error") == "approval_required":
        status = 403
        body["error"] = "approval_required"
        body["risk_level"] = result.get("risk_level")
        body["tool_id"] = result.get("tool_id")
    elif result.get("error") == "unknown tool":
        status = 404
        body["error"] = "not_found"
    return status, body
