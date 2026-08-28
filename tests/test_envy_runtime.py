from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HERE = Path(__file__).resolve().parent
LIB = HERE.parent / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("INVISIBLE_HOME", str(tmp_path))
    for mod in list(sys.modules):
        if mod == "config" or mod.startswith("api") or mod in {"envy_db", "hermes_bridge", "tool_gateway"}:
            del sys.modules[mod]
    return tmp_path


def test_envy_db_migrations_create_all_tables_idempotently(isolated_home):
    import envy_db

    envy_db.migrate()
    envy_db.migrate()

    conn = sqlite3.connect(isolated_home / "envy.db")
    try:
        rows = conn.execute(
            "select name from sqlite_master where type = 'table'"
        ).fetchall()
    finally:
        conn.close()

    names = {row[0] for row in rows}
    assert {
        "sessions",
        "messages",
        "tasks",
        "runs",
        "tool_catalog",
        "tool_calls",
        "approvals",
        "memories",
        "handoffs",
        "connections",
        "schedules",
    }.issubset(names)


def test_tool_search_returns_summaries_without_credential_values(isolated_home, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret_value")
    from api import agent

    status, body = agent.search_tools_handler({"query": "github token mcp"})

    dumped = json.dumps(body)
    assert status == 200
    assert body["tools"]
    assert "ghp_secret_value" not in dumped
    assert all("input_schema" not in item for item in body["tools"])


def test_direct_tool_execute_blocks_risky_write_without_approval(isolated_home):
    from api import agent

    status, body = agent.execute_tool_handler({
        "tool_id": "system_write_file",
        "args": {"path": str(isolated_home / "outside.txt"), "content": "nope"},
    })

    assert status == 403
    assert body["error"] == "approval_required"
    assert not (isolated_home / "outside.txt").exists()


def test_direct_tool_execute_logs_allowed_safe_read(isolated_home):
    from api import agent

    status, body = agent.execute_tool_handler({
        "tool_id": "sandbox_list",
        "args": {},
        "project_id": "invisible",
    })

    assert status == 200
    assert body["result"]["ok"] is True

    import envy_db

    rows = envy_db.fetch_tool_calls()
    assert len(rows) == 1
    assert rows[0]["tool_id"] == "sandbox_list"
    assert rows[0]["status"] == "ok"


def test_hermes_bridge_uses_invisible_home_runtime_paths(isolated_home):
    from hermes_bridge import HermesBridge

    bridge = HermesBridge()
    paths = bridge.status()

    assert Path(paths["root"]) == isolated_home / "hermes"
    assert Path(paths["memories"]) == isolated_home / "hermes" / "memories"
    assert Path(paths["skills"]) == isolated_home / "hermes" / "skills"
    assert Path(paths["root"]).exists()


def test_memory_write_pending_and_search(isolated_home):
    from api import memory

    status, body = memory.write_handler({
        "category": "project_fact",
        "content": "Invisible stores Envy runtime state in SQLite.",
        "project_id": "invisible",
    })

    assert status == 200
    assert body["memory"]["status"] == "pending"

    search_status, search_body = memory.search_handler({"q": "SQLite"})
    assert search_status == 200
    assert search_body["results"]
    assert search_body["results"][0]["content"] == "Invisible stores Envy runtime state in SQLite."


def test_handoff_draft_includes_resume_packet_fields(isolated_home):
    from api import handoff

    with patch("api.ai.chat_handler", return_value=(200, {"text": "handoff md", "model": "qwen"})):
        status, body = handoff.draft_handler({
            "project": "invisible",
            "goal": "continue runtime integration",
            "handoff_target": "codex",
        })

    packet = body["handoff"]["packet"]
    assert status == 200
    assert packet["target"] == "codex"
    assert packet["goal"] == "continue runtime integration"
    assert "repo_path" in packet
    assert "tool_trace" in packet
    assert "memory_refs" in packet
    assert packet["resume_command"]
