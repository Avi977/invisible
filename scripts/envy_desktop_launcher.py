"""Envy desktop launcher for PyInstaller builds.

Starts the local dashboard API, serves the Vite build, and opens a native
webview window when pywebview is available. Falls back to the default browser.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import runpy
import socket
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path


API_HOST = "127.0.0.1"
API_PORT = 8765
UI_HOST = "127.0.0.1"
UI_PORT = 8090


class QuietStaticHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[1]


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


def wait_for(url: str, timeout_s: float = 8.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as resp:
                return 200 <= resp.status < 500
        except OSError:
            time.sleep(0.15)
    return False


def start_dashboard(root: Path) -> None:
    if port_open(API_HOST, API_PORT):
        return
    script = root / "bin" / "invisible-dashboard"
    if not script.exists():
        raise FileNotFoundError(f"missing backend script: {script}")

    def run() -> None:
        old_argv = sys.argv[:]
        try:
            sys.argv = [
                str(script),
                "--host",
                API_HOST,
                "--port",
                str(API_PORT),
                "--no-auth",
            ]
            os.environ.setdefault("INVISIBLE_DESKTOP", "1")
            runpy.run_path(str(script), run_name="__main__")
        except SystemExit:
            return
        finally:
            sys.argv = old_argv

    threading.Thread(target=run, name="envy-dashboard", daemon=True).start()


def start_static_ui(root: Path) -> None:
    if port_open(UI_HOST, UI_PORT):
        return
    dist = root / "frontend-vite" / "dist"
    if not dist.exists():
        raise FileNotFoundError(f"missing frontend build: {dist}")

    handler = functools.partial(QuietStaticHandler, directory=str(dist))
    server = http.server.ThreadingHTTPServer((UI_HOST, UI_PORT), handler)
    threading.Thread(target=server.serve_forever, name="envy-ui", daemon=True).start()


def open_window(url: str, browser_only: bool) -> None:
    if browser_only:
        webbrowser.open(url)
        while True:
            time.sleep(3600)

    try:
        import webview  # type: ignore
    except ImportError:
        webbrowser.open(url)
        while True:
            time.sleep(3600)

    webview.create_window(
        "Envy",
        url,
        width=1200,
        height=800,
        min_size=(700, 500),
        background_color="#0d0f12",
    )
    webview.start()


def dispatch_embedded_script(argv: list[str]) -> bool:
    """Run bundled bin scripts when a frozen Envy exe is used as Python.

    PyInstaller sets sys.executable to Envy.exe. Backend helpers that launch
    `sys.executable bin/invisible-pty ...` therefore re-enter this launcher.
    Detect that shape and hand control to the requested bundled script.
    """
    if len(argv) < 2:
        return False
    script = Path(argv[1])
    if script.name not in {"invisible-dashboard", "invisible-pty"}:
        return False
    if not script.exists():
        return False

    old_argv = sys.argv[:]
    try:
        sys.argv = argv[1:]
        try:
            runpy.run_path(str(script), run_name="__main__")
        except BaseException:
            log_dir = Path(os.path.expanduser(os.environ.get("INVISIBLE_HOME", "~/.invisible"))) / "run"
            log_dir.mkdir(parents=True, exist_ok=True)
            with (log_dir / "envy-dispatch.err.log").open("a", encoding="utf-8") as fh:
                fh.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {' '.join(argv)}\n")
                traceback.print_exc(file=fh)
            raise
    finally:
        sys.argv = old_argv
    return True


def main() -> int:
    if dispatch_embedded_script(sys.argv):
        return 0

    parser = argparse.ArgumentParser(prog="Envy")
    parser.add_argument("--browser", action="store_true", help="open in the default browser instead of pywebview")
    parser.add_argument("--smoke-test", action="store_true", help="start services, verify local URLs, then exit")
    args = parser.parse_args()

    root = app_root()
    start_dashboard(root)
    start_static_ui(root)
    api_ok = wait_for(f"http://{API_HOST}:{API_PORT}/healthz")
    ui_ok = wait_for(f"http://{UI_HOST}:{UI_PORT}/")
    if args.smoke_test:
        if sys.stdout:
            print(json_status("api", api_ok))
            print(json_status("ui", ui_ok))
        return 0 if api_ok and ui_ok else 1
    open_window(f"http://{UI_HOST}:{UI_PORT}", args.browser)
    return 0


def json_status(name: str, ok: bool) -> str:
    return f"{name}={'ok' if ok else 'failed'}"


if __name__ == "__main__":
    raise SystemExit(main())
