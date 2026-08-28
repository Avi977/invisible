from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HERE = Path(__file__).resolve().parent
LIB = HERE.parent / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))


class FakeHandler:
    def __init__(self, path: str = "/"):
        self.path = path
        self.sent_obj = None
        self.sent_status = None

    def _send_json(self, obj, status=200):
        self.sent_obj = obj
        self.sent_status = status


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("INVISIBLE_HOME", str(tmp_path))
    for mod in list(sys.modules):
        if mod == "config" or mod.startswith("api"):
            del sys.modules[mod]
    return tmp_path


def test_ai_models_unavailable_is_local_only_503(isolated_home):
    from api import ai

    with patch("api.ai.urllib.request.urlopen", side_effect=OSError("offline")):
        status, body = ai.list_models()

    assert status == 503
    assert body["provider"] == "ollama"
    assert body["local_only"] is True
    assert body["models"] == []


def test_ai_chat_rejects_oversized_message_without_network(isolated_home):
    from api import ai

    with patch("api.ai.urllib.request.urlopen") as mocked:
        status, body = ai.chat_handler({
            "message": "x" * (ai.MAX_MESSAGE_CHARS + 1),
            "page_context": "tests",
        })

    assert status == 413
    assert body["error"] == "message_too_large"
    mocked.assert_not_called()


def test_agent_rejects_oversized_message_without_network(isolated_home):
    from api import agent

    with patch("api.ai.urllib.request.urlopen") as mocked:
        status, body = agent.chat_handler({
            "message": "x" * (agent.MAX_MESSAGE_CHARS + 1),
            "page_context": "tests",
        })

    assert status == 413
    assert body["error"] == "message_too_large"
    mocked.assert_not_called()


def test_agent_catalog_exposes_sandbox_and_mcp_tools(isolated_home):
    from api import agent

    names = {tool["name"] for tool in agent.tool_catalog()["tools"]}

    assert "sandbox_shell" in names
    assert "sandbox_write_file" in names
    assert "mcp_inventory" in names
    assert "plugin_inventory" in names
    assert "system_shell" in names
    assert "screen_snapshot" in names
    assert "clipboard_get" in names
    assert agent.tool_catalog()["access"]["personal_assistant_mode"] is True


def test_agent_catalog_can_disable_personal_assistant_tools(isolated_home, monkeypatch):
    monkeypatch.setenv("ENVY_PERSONAL_ASSISTANT_MODE", "0")
    from api import agent

    names = {tool["name"] for tool in agent.tool_catalog()["tools"]}

    assert "sandbox_shell" in names
    assert "system_shell" not in names
    assert "screen_snapshot" not in names
    assert agent.tool_catalog()["access"]["personal_assistant_mode"] is False


def test_agent_sandbox_file_tools_stay_under_project_sandbox(isolated_home):
    from api import agent

    root = agent.sandbox_root("Invisible")
    write = agent._execute_tool(
        "sandbox_write_file",
        {"path": "notes/plan.txt", "content": "ship envy"},
        "Invisible",
    )
    read = agent._execute_tool("sandbox_read_file", {"path": "notes/plan.txt"}, "Invisible")
    escape = agent._execute_tool("sandbox_read_file", {"path": "../secret.txt"}, "Invisible")

    assert write["ok"] is True
    assert read["ok"] is True
    assert read["content"] == "ship envy"
    assert Path(write["path"]).as_posix() == "notes/plan.txt"
    assert root.exists()
    assert escape["ok"] is False


def test_agent_shell_runs_in_sandbox_with_timeout_and_env(isolated_home):
    from api import agent

    def fake_run(cmd, **kwargs):
        assert cmd[:3] == ["powershell", "-NoProfile", "-NonInteractive"]
        assert Path(kwargs["cwd"]) == agent.sandbox_root("invisible")
        assert kwargs["env"]["ENVY_AGENT"] == "1"
        return subprocess.CompletedProcess(cmd, 0, "done", "")

    with patch("api.agent.subprocess.run", side_effect=fake_run):
        result = agent._execute_tool("sandbox_shell", {"command": "Write-Output done"}, "invisible")

    assert result["ok"] is True
    assert result["stdout"] == "done"


def test_agent_shell_blocks_obvious_destructive_commands(isolated_home):
    from api import agent

    result = agent._execute_tool(
        "sandbox_shell",
        {"command": "Remove-Item C:\\ -Recurse -Force"},
        "invisible",
    )

    assert result["ok"] is False
    assert "blocked" in result["error"]


def test_agent_system_shell_uses_project_repo_when_enabled(isolated_home):
    repo = isolated_home / "repos" / "invisible"
    repo.mkdir(parents=True)
    (isolated_home / "invisible.toml").write_text(
        "\n".join([
            "[[projects]]",
            'name = "invisible"',
            f'repo_path = "{repo.as_posix()}"',
        ]),
        encoding="utf-8",
    )

    from api import agent

    def fake_run(cmd, **kwargs):
        assert Path(kwargs["cwd"]) == repo.resolve()
        assert kwargs["env"]["ENVY_PERSONAL_ASSISTANT_MODE"] == "1"
        return subprocess.CompletedProcess(cmd, 0, "system-ok", "")

    with patch("api.agent.subprocess.run", side_effect=fake_run):
        result = agent._execute_tool("system_shell", {"command": "Write-Output system-ok"}, "invisible")

    assert result["ok"] is True
    assert result["stdout"] == "system-ok"


def test_agent_prefers_vision_model_for_screen_requests(isolated_home):
    from api import agent

    with patch("api.ai.list_models", return_value=(200, {
        "models": [{"name": "qwen3:14b"}, {"name": "llava:latest"}],
        "default": "qwen3:14b",
    })):
        status, _body, model = agent._select_model("qwen3:14b", prefer_vision=True)

    assert status == 200
    assert model == "llava:latest"


def test_agent_mcp_inventory_lists_servers_without_env_values(isolated_home, monkeypatch):
    codex_home = isolated_home / ".codex"
    codex_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    (codex_home / "config.toml").write_text(
        "\n".join([
            "[mcp_servers.example]",
            'command = "bunx"',
            'args = ["example-mcp"]',
            "startup_timeout_sec = 30",
            "[mcp_servers.example.env]",
            'SECRET_TOKEN = "do-not-leak"',
        ]),
        encoding="utf-8",
    )

    from api import agent

    result = agent._execute_tool("mcp_inventory", {}, "invisible")

    assert result["ok"] is True
    assert result["servers"] == [{
        "name": "example",
        "command": "bunx",
        "args": ["example-mcp"],
        "has_env": True,
        "startup_timeout_sec": 30,
    }]
    assert "do-not-leak" not in json.dumps(result)


def test_ai_system_prompt_defines_envy_for_ace_and_powershell(isolated_home):
    from api import ai

    prompt = ai.build_system_prompt("Terminals", "invisible", 3)

    assert "You are Envy" in prompt
    assert "Ace is a computer science major" in prompt
    assert "PowerShell" in prompt
    assert "sassy" in prompt
    assert "Current project: invisible" in prompt


def test_voice_transcribe_accepts_local_openwhispr_text(isolated_home):
    from api import voice

    status, body = voice.transcribe_handler({"transcript": "ship the graph"})

    assert status == 200
    assert body["text"] == "ship the graph"
    assert body["source"] == "manual_transcript"
    assert body["local_only"] is True
    assert body["cost"] == 0


def test_voice_transcribe_reads_latest_openwhispr_bridge_transcript(isolated_home):
    from api import voice

    with patch("api.voice._bridge_request") as bridge:
        bridge.return_value = {
            "data": [
                {
                    "id": 7,
                    "text": "runtime audio transcript",
                    "created_at": "2026-07-03 12:00:00",
                }
            ]
        }
        status, body = voice.transcribe_handler({"latest": True})

    assert status == 200
    assert body["text"] == "runtime audio transcript"
    assert body["source"] == "cli_bridge"
    assert body["transcription_id"] == 7
    assert body["local_only"] is True


def test_voice_transcribe_reports_bridge_unavailable(isolated_home):
    from api import voice

    with patch("api.voice._bridge_request", side_effect=RuntimeError("bridge_missing")):
        status, body = voice.transcribe_handler({"latest": True})

    assert status == 503
    assert body["error"] == "openwhispr_bridge_unavailable"
    assert body["local_only"] is True


def test_graphify_status_uses_python_module_fallback(isolated_home):
    from api import graphify_local

    with (
        patch("api.graphify_local.shutil.which", return_value=None),
        patch("api.graphify_local.find_spec", return_value=object()),
    ):
        body = graphify_local.status("invisible")

    assert body["installed"] is True
    assert body["command"] == [sys.executable, "-m", "graphify"]
    assert body["backend"] == "ollama"


def test_graphify_invisible_uses_configured_repo_path_before_home(isolated_home):
    repo = isolated_home / "repos" / "graphify-invisible"
    repo.mkdir(parents=True)
    (isolated_home / "invisible.toml").write_text(
        "\n".join([
            "[[projects]]",
            'name = "invisible"',
            f'repo_path = "{repo.as_posix()}"',
        ]),
        encoding="utf-8",
    )

    from api import graphify_local

    assert graphify_local.project_root("invisible") == repo.resolve()
    assert graphify_local.project_root("invisible") != isolated_home.resolve()


def test_relations_invisible_uses_configured_repo_path_before_home(isolated_home):
    repo = isolated_home / "repos" / "relations-invisible"
    repo.mkdir(parents=True)
    (isolated_home / "invisible.toml").write_text(
        "\n".join([
            "[[projects]]",
            'name = "invisible"',
            f'repo_path = "{repo.as_posix()}"',
        ]),
        encoding="utf-8",
    )

    from api import relations

    assert relations._project_root("invisible") == repo.resolve()
    assert relations._project_root("invisible") != isolated_home.resolve()


def test_graphify_run_imports_graphify_out_json(isolated_home):
    from api import graphify_local

    def fake_run(cmd, **_kwargs):
        out_dir = Path(cmd[cmd.index("--out") + 1])
        graphify_out = out_dir / "graphify-out"
        graphify_out.mkdir(parents=True, exist_ok=True)
        (graphify_out / "graph.json").write_text(
            json.dumps({
                "nodes": [
                    {"id": "a", "label": "sample.py", "file_type": "code"},
                    {"id": "b", "label": "hello()", "file_type": "code"},
                ],
                "edges": [{"source": "a", "target": "b", "relation": "contains"}],
            }),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, "ok", "")

    with (
        patch("api.graphify_local._graphify_command", return_value=["py", "-m", "graphify"]),
        patch("api.graphify_local.subprocess.run", side_effect=fake_run),
    ):
        status, body = graphify_local.run_handler({"project": "invisible", "timeout_s": 1, "semantic": True})

    assert status == 200
    assert body["graph_present"] is True
    assert body["backend"] == "ollama"
    graph = graphify_local.load_graph("invisible")
    assert graph["nodes"][0]["id"] == "a"
    normalized = graphify_local.normalize_graph(graph, "invisible")
    assert normalized["nodes"][0]["type"] == "module"
    assert normalized["edges"][0]["kind"] == "contains"


def test_graphify_run_reports_empty_output(isolated_home):
    from api import graphify_local

    def fake_run(cmd, **_kwargs):
        out_dir = Path(cmd[cmd.index("--out") + 1])
        graphify_out = out_dir / "graphify-out"
        graphify_out.mkdir(parents=True, exist_ok=True)
        (graphify_out / "graph.json").write_text(
            json.dumps({"nodes": [], "edges": []}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, "ok", "")

    with (
        patch("api.graphify_local._graphify_command", return_value=["py", "-m", "graphify"]),
        patch("api.graphify_local.subprocess.run", side_effect=fake_run),
    ):
        status, body = graphify_local.run_handler({"project": "invisible", "timeout_s": 1, "semantic": True})

    assert status == 502
    assert body["error"] == "graphify_empty"
    assert body["node_count"] == 0


def test_graphify_fast_update_imports_and_cleans_repo_graphify_out(isolated_home):
    from api import graphify_local

    repo = isolated_home / "repos" / "invisible"
    repo.mkdir(parents=True)
    (isolated_home / "invisible.toml").write_text(
        "\n".join([
            "[[projects]]",
            'name = "invisible"',
            f'repo_path = "{repo.as_posix()}"',
        ]),
        encoding="utf-8",
    )

    def fake_run(cmd, **_kwargs):
        graphify_out = repo / "graphify-out"
        graphify_out.mkdir(parents=True, exist_ok=True)
        (graphify_out / "graph.json").write_text(
            json.dumps({
                "nodes": [{"id": "fast", "label": "fast.py", "file_type": "code"}],
                "edges": [],
            }),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, "updated", "")

    with (
        patch("api.graphify_local._graphify_command", return_value=["py", "-m", "graphify"]),
        patch("api.graphify_local.subprocess.run", side_effect=fake_run),
    ):
        status, body = graphify_local.run_handler({"project": "invisible", "timeout_s": 1})

    assert status == 200
    assert body["semantic"] is False
    assert body["node_count"] == 1
    assert not (repo / "graphify-out").exists()
    assert graphify_local.load_graph("invisible")["nodes"][0]["id"] == "fast"


def test_relations_falls_back_when_graphify_graph_is_empty(isolated_home):
    repo = isolated_home / "repos" / "invisible"
    (repo / "lib").mkdir(parents=True)
    (repo / "lib" / "sample.py").write_text("import os\nVALUE = 1\n", encoding="utf-8")
    (isolated_home / "invisible.toml").write_text(
        "\n".join([
            "[[projects]]",
            'name = "invisible"',
            f'repo_path = "{repo.as_posix()}"',
        ]),
        encoding="utf-8",
    )
    graph_dir = isolated_home / "graphify" / "invisible"
    graph_dir.mkdir(parents=True)
    (graph_dir / "graph.json").write_text(
        json.dumps({"nodes": [], "edges": []}),
        encoding="utf-8",
    )

    from api import relations

    relations.clear_cache()
    graph = relations.build_graph("invisible")

    assert graph["nodes"]
    assert graph.get("source") != "graphify"


def test_handoff_save_writes_under_invisible_home(isolated_home):
    from api import handoff

    handoff_obj = {
        "project": "jobslayer",
        "created_at": "2026-07-03T12:00:00+00:00",
        "markdown": "# Handoff",
    }
    status, body = handoff.save_handler({"handoff": handoff_obj})

    assert status == 200
    path = Path(body["path"])
    assert path.exists()
    assert isolated_home in path.parents
    assert json.loads(path.read_text())["markdown"] == "# Handoff"


def test_integrations_status_masks_infisical_secret_values(isolated_home):
    from api import integrations

    class FakeClient:
        def list_secrets(self, workspace_id, environment, secret_path="/"):
            return {"GITHUB_TOKEN": "ghp_1234567890", "NOTION_TOKEN": "secret_abcdef"}

    with (
        patch("api.integrations.infisical.configured", return_value=True),
        patch("api.integrations.infisical.make_client", return_value=FakeClient()),
        patch("api.integrations.infisical._env", return_value=("https://vault.example", "cid", "secret", "pid123456", "dev", "/")),
    ):
        body = integrations.status_body()

    dumped = json.dumps(body)
    assert body["infisical"]["reachable"] is True
    assert body["infisical"]["secret_count"] == 2
    assert "ghp_1234567890" not in dumped
    assert "secret_abcdef" not in dumped


def test_integrations_upsert_secret_writes_to_infisical(isolated_home):
    from api import integrations

    class FakeClient:
        def upsert_secret(self, workspace_id, environment, key, value, secret_path="/"):
            assert workspace_id == "pid"
            assert environment == "dev"
            assert secret_path == "/"
            assert key == "GITHUB_TOKEN"
            assert value == "token-value"
            return True

    with (
        patch("api.integrations.infisical.configured", return_value=True),
        patch("api.integrations.infisical.make_client", return_value=FakeClient()),
        patch("api.integrations.infisical._env", return_value=("https://vault.example", "cid", "secret", "pid", "dev", "/")),
    ):
        status, body = integrations.upsert_secret_handler({"key": "GITHUB_TOKEN", "value": "token-value"})

    assert status == 200
    assert body["stored"] == "infisical"
    assert os.environ["GITHUB_TOKEN"] == "token-value"


def test_integrations_connection_metadata_stays_local(isolated_home):
    from api import integrations

    status, body = integrations.upsert_connection_handler({
        "name": "github",
        "kind": "api",
        "base_url": "https://api.github.com",
        "secret_keys": ["GITHUB_TOKEN"],
    })

    assert status == 200
    assert body["connection"]["name"] == "github"
    assert (isolated_home / "integrations.json").exists()
    assert integrations.status_body()["connections"][0]["secret_keys"] == ["GITHUB_TOKEN"]


def test_integrations_append_new_mcp_server_without_secret_values(isolated_home, monkeypatch):
    codex_home = isolated_home / ".codex"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    from api import integrations

    status, body = integrations.upsert_mcp_handler({
        "name": "github",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env_keys": ["GITHUB_TOKEN"],
    })

    cfg = (codex_home / "config.toml").read_text(encoding="utf-8")
    assert status == 200
    assert body["server"]["name"] == "github"
    assert "[mcp_servers.github]" in cfg
    assert 'GITHUB_TOKEN = "${GITHUB_TOKEN}"' in cfg
    assert "token-value" not in cfg
