"""Local PTY daemon control for the Terminals page."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import config

HOST = "127.0.0.1"
PORT = 8091


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _is_listening(host: str = HOST, port: int = PORT, timeout_s: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def _python_command() -> list[str]:
    if os.name == "nt":
        py_launcher = shutil.which("py")
        if py_launcher:
            return [py_launcher]
        python = shutil.which("python")
        if python:
            return [python]
    return [sys.executable]


def _start_process() -> int | None:
    script = _repo_root() / "bin" / "invisible-pty"
    if not script.exists():
        return None
    run_dir = config.home() / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    stdout = (run_dir / "invisible-pty.out.log").open("ab")
    stderr = (run_dir / "invisible-pty.err.log").open("ab")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        [
            *_python_command(),
            str(script),
            "--host",
            HOST,
            "--port",
            str(PORT),
            "--config",
            str(config.home() / "invisible.toml"),
        ],
        cwd=str(_repo_root()),
        stdout=stdout,
        stderr=stderr,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=os.name != "nt",
    )
    return int(proc.pid)


def status_body() -> dict[str, Any]:
    return {
        "host": HOST,
        "port": PORT,
        "running": _is_listening(),
        "ws_base": f"ws://{HOST}:{PORT}",
        "local_only": True,
    }


def start_handler(_body: Any) -> tuple[int, dict]:
    if _is_listening():
        return 200, {**status_body(), "started": False}
    pid = _start_process()
    if pid is None:
        return 500, {"error": "pty_script_missing", "running": False, "local_only": True}
    deadline = time.time() + 5
    while time.time() < deadline:
        if _is_listening():
            return 200, {**status_body(), "started": True, "pid": pid}
        time.sleep(0.1)
    return 503, {
        "error": "pty_start_timeout",
        "running": False,
        "pid": pid,
        "local_only": True,
    }


def handle_status(handler: Any) -> None:
    handler._send_json(status_body())
