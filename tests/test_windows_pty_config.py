from __future__ import annotations

import os
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
LIB = HERE.parent / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))


def test_pty_defaults_to_powershell_on_windows(monkeypatch):
    import pty_server

    monkeypatch.setattr(pty_server, "IS_WINDOWS", True)
    with patch("pty_server.shutil.which", return_value="C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"):
        assert pty_server.default_shell_kind() == "powershell"
        assert pty_server.resolve_command({})[:4] == [
            "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
            "-NoLogo",
            "-NoExit",
            "-ExecutionPolicy",
        ]


def test_user_config_contains_repos_as_powershell_projects(monkeypatch):
    import config
    import pty_server

    monkeypatch.delenv("INVISIBLE_HOME", raising=False)
    cfg = config.load_toml()
    repo_root = Path(os.path.expanduser("~/repos"))
    repos = {p.name.lower().replace(".", "-"): str(p) for p in repo_root.iterdir() if p.is_dir()}
    projects = {p["name"]: p["repo_path"] for p in cfg.get("projects", [])}
    terminals = {t["id"]: t for t in cfg.get("terminals", [])}

    for name, path in repos.items():
        assert projects[name] == path
        assert terminals[name]["kind"] == "powershell"
        assert terminals[name]["cwd"] == path

    loaded = pty_server.load_pane_configs(config.home() / "invisible.toml")
    assert all(entry["kind"] == "powershell" for entry in loaded.values())


def test_pty_api_start_is_idempotent_when_daemon_running():
    from api import pty

    with (
        patch("api.pty._is_listening", return_value=True),
        patch("api.pty._start_process") as start_process,
    ):
        status, body = pty.start_handler({})

    assert status == 200
    assert body["running"] is True
    assert body["started"] is False
    start_process.assert_not_called()


def test_pty_api_start_launches_when_daemon_missing():
    from api import pty

    with (
        patch("api.pty._is_listening", side_effect=[False, True, True]),
        patch("api.pty._start_process", return_value=1234) as start_process,
    ):
        status, body = pty.start_handler({})

    assert status == 200
    assert body["running"] is True
    assert body["started"] is True
    assert body["pid"] == 1234
    start_process.assert_called_once()


def test_pty_api_prefers_real_python_launcher_on_windows(monkeypatch):
    from api import pty

    monkeypatch.setattr(pty.os, "name", "nt")
    with patch("api.pty.shutil.which", side_effect=lambda name: "C:\\Windows\\py.exe" if name == "py" else None):
        assert pty._python_command() == ["C:\\Windows\\py.exe"]


def test_tabbed_pty_ids_reuse_base_pane_config():
    import pty_server

    base = {"kind": "powershell", "cwd": "C:\\Users\\mahar\\repos\\invisible"}
    server = pty_server.PTYServer(pane_configs={"invisible": base})

    assert server._config_for_pane("invisible-2") == base
    assert server._config_for_pane("invisible") == base
    assert server._config_for_pane("unknown-2") == {}


def test_envy_launcher_dispatches_bundled_pty_script(tmp_path):
    launcher_path = HERE.parent / "scripts" / "envy_desktop_launcher.py"
    spec = importlib.util.spec_from_file_location("envy_desktop_launcher_test", launcher_path)
    launcher = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(launcher)

    script = tmp_path / "invisible-pty"
    script.write_text("print('pty')\n", encoding="utf-8")
    old_argv = sys.argv[:]
    with patch.object(launcher.runpy, "run_path") as run_path:
        handled = launcher.dispatch_embedded_script(["Envy.exe", str(script), "--host", "127.0.0.1"])

    assert handled is True
    run_path.assert_called_once_with(str(script), run_name="__main__")
    assert sys.argv == old_argv
