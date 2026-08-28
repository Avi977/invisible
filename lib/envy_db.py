"""SQLite runtime store for Envy.

New local-first agent state lives in $INVISIBLE_HOME/envy.db. Legacy JSON
files remain readable by their existing modules, but new runtime records are
captured here so tool calls, memories, handoffs, and runs can be searched and
audited consistently.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def db_path() -> Path:
    return config.home() / "envy.db"


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _row_dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS sessions (
      id TEXT PRIMARY KEY,
      project_id TEXT,
      title TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      metadata_json TEXT NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
      id TEXT PRIMARY KEY,
      session_id TEXT,
      role TEXT NOT NULL,
      content TEXT NOT NULL,
      created_at TEXT NOT NULL,
      metadata_json TEXT NOT NULL DEFAULT '{}',
      FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tasks (
      id TEXT PRIMARY KEY,
      project_id TEXT,
      goal TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      metadata_json TEXT NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS runs (
      id TEXT PRIMARY KEY,
      task_id TEXT,
      owner TEXT NOT NULL,
      status TEXT NOT NULL,
      goal TEXT,
      project_id TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      logs_json TEXT NOT NULL DEFAULT '[]',
      metadata_json TEXT NOT NULL DEFAULT '{}',
      FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tool_catalog (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      category TEXT NOT NULL,
      risk_level TEXT NOT NULL,
      input_schema_json TEXT NOT NULL DEFAULT '{}',
      requires_approval INTEGER NOT NULL DEFAULT 0,
      runner TEXT NOT NULL,
      credential_keys_json TEXT NOT NULL DEFAULT '[]',
      enabled INTEGER NOT NULL DEFAULT 1,
      description TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tool_calls (
      id TEXT PRIMARY KEY,
      tool_id TEXT NOT NULL,
      task_id TEXT,
      run_id TEXT,
      risk_level TEXT,
      args_json TEXT NOT NULL DEFAULT '{}',
      result_json TEXT NOT NULL DEFAULT '{}',
      approved INTEGER NOT NULL DEFAULT 0,
      status TEXT NOT NULL,
      started_at TEXT NOT NULL,
      finished_at TEXT,
      elapsed_ms INTEGER,
      error TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS approvals (
      id TEXT PRIMARY KEY,
      tool_call_id TEXT,
      risk_level TEXT NOT NULL,
      status TEXT NOT NULL,
      requested_at TEXT NOT NULL,
      resolved_at TEXT,
      scope TEXT,
      reason TEXT,
      FOREIGN KEY(tool_call_id) REFERENCES tool_calls(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS memories (
      id TEXT PRIMARY KEY,
      category TEXT NOT NULL,
      content TEXT NOT NULL,
      status TEXT NOT NULL,
      source TEXT,
      project_id TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      metadata_json TEXT NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS handoffs (
      id TEXT PRIMARY KEY,
      project TEXT NOT NULL,
      target TEXT NOT NULL,
      goal TEXT,
      packet_json TEXT NOT NULL,
      created_at TEXT NOT NULL,
      saved_path TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS connections (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL UNIQUE,
      kind TEXT NOT NULL,
      base_url TEXT,
      secret_keys_json TEXT NOT NULL DEFAULT '[]',
      enabled INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      metadata_json TEXT NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS schedules (
      id TEXT PRIMARY KEY,
      task TEXT NOT NULL,
      cron TEXT,
      enabled INTEGER NOT NULL DEFAULT 1,
      next_run_at TEXT,
      metadata_json TEXT NOT NULL DEFAULT '{}'
    )
    """,
)


def migrate() -> None:
    with connect() as conn:
        for statement in SCHEMA:
            conn.execute(statement)
        conn.commit()


def upsert_tool_catalog(tools: list[dict]) -> None:
    migrate()
    stamp = now_iso()
    with connect() as conn:
        for tool in tools:
            conn.execute(
                """
                INSERT INTO tool_catalog (
                  id, name, category, risk_level, input_schema_json,
                  requires_approval, runner, credential_keys_json, enabled,
                  description, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  name = excluded.name,
                  category = excluded.category,
                  risk_level = excluded.risk_level,
                  input_schema_json = excluded.input_schema_json,
                  requires_approval = excluded.requires_approval,
                  runner = excluded.runner,
                  credential_keys_json = excluded.credential_keys_json,
                  enabled = excluded.enabled,
                  description = excluded.description,
                  updated_at = excluded.updated_at
                """,
                (
                    tool["id"],
                    tool["name"],
                    tool["category"],
                    tool["risk_level"],
                    _json(tool.get("input_schema") or {}),
                    1 if tool.get("requires_approval") else 0,
                    tool.get("runner") or "native",
                    _json(tool.get("credential_keys") or []),
                    1 if tool.get("enabled", True) else 0,
                    tool.get("description") or "",
                    stamp,
                ),
            )
        conn.commit()


def log_tool_call(
    *,
    tool_id: str,
    args: dict,
    result: dict,
    risk_level: str | None,
    approved: bool,
    status: str,
    task_id: str | None = None,
    run_id: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    elapsed_ms: int | None = None,
    error: str | None = None,
) -> str:
    migrate()
    call_id = uuid.uuid4().hex
    started = started_at or now_iso()
    finished = finished_at or now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO tool_calls (
              id, tool_id, task_id, run_id, risk_level, args_json,
              result_json, approved, status, started_at, finished_at,
              elapsed_ms, error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                call_id,
                tool_id,
                task_id,
                run_id,
                risk_level,
                _json(args),
                _json(result),
                1 if approved else 0,
                status,
                started,
                finished,
                elapsed_ms,
                error,
            ),
        )
        conn.commit()
    return call_id


def fetch_tool_calls(limit: int = 50, task_id: str | None = None) -> list[dict]:
    migrate()
    limit = max(1, min(int(limit), 200))
    sql = "SELECT * FROM tool_calls"
    params: list[Any] = []
    if task_id:
        sql += " WHERE task_id = ?"
        params.append(task_id)
    sql += " ORDER BY started_at DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_dict(row) for row in rows]


def write_memory(
    *,
    category: str,
    content: str,
    status: str,
    source: str | None = None,
    project_id: str | None = None,
    metadata: dict | None = None,
) -> dict:
    migrate()
    stamp = now_iso()
    memory_id = uuid.uuid4().hex
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO memories (
              id, category, content, status, source, project_id,
              created_at, updated_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                category,
                content,
                status,
                source,
                project_id,
                stamp,
                stamp,
                _json(metadata or {}),
            ),
        )
        conn.commit()
    return {
        "id": memory_id,
        "category": category,
        "content": content,
        "status": status,
        "source": source,
        "project_id": project_id,
        "created_at": stamp,
        "updated_at": stamp,
        "metadata": metadata or {},
    }


def search_memories(query: str, limit: int = 20, project_id: str | None = None) -> list[dict]:
    migrate()
    limit = max(1, min(int(limit), 100))
    needle = f"%{query.strip()}%" if query.strip() else "%"
    params: list[Any] = [needle, needle]
    where = "(content LIKE ? OR category LIKE ?)"
    if project_id:
        where += " AND (project_id = ? OR project_id IS NULL)"
        params.append(project_id)
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM memories
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    results = []
    for row in rows:
        item = _row_dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
        results.append(item)
    return results


def save_handoff(
    *,
    project: str,
    target: str,
    goal: str,
    packet: dict,
    created_at: str | None = None,
    saved_path: str | None = None,
) -> str:
    migrate()
    handoff_id = uuid.uuid4().hex
    stamp = created_at or now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO handoffs (id, project, target, goal, packet_json, created_at, saved_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (handoff_id, project, target, goal, _json(packet), stamp, saved_path),
        )
        conn.commit()
    return handoff_id


def create_run(goal: str, project_id: str | None = None, owner: str = "envy") -> dict:
    migrate()
    stamp = now_iso()
    run_id = uuid.uuid4().hex
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO runs (
              id, owner, status, goal, project_id, created_at, updated_at,
              logs_json, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, '[]', '{}')
            """,
            (run_id, owner, "queued", goal, project_id, stamp, stamp),
        )
        conn.commit()
    return {
        "id": run_id,
        "owner": owner,
        "status": "queued",
        "goal": goal,
        "project_id": project_id,
        "created_at": stamp,
        "updated_at": stamp,
        "logs": [],
        "metadata": {},
    }


def get_run(run_id: str) -> dict | None:
    migrate()
    with connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    item = _row_dict(row)
    item["logs"] = json.loads(item.pop("logs_json") or "[]")
    item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
    return item


def update_run(run_id: str, *, owner: str | None = None, status: str | None = None, metadata: dict | None = None) -> dict | None:
    current = get_run(run_id)
    if current is None:
        return None
    new_owner = owner or current["owner"]
    new_status = status or current["status"]
    new_metadata = {**current.get("metadata", {}), **(metadata or {})}
    stamp = now_iso()
    with connect() as conn:
        conn.execute(
            """
            UPDATE runs
            SET owner = ?, status = ?, updated_at = ?, metadata_json = ?
            WHERE id = ?
            """,
            (new_owner, new_status, stamp, _json(new_metadata), run_id),
        )
        conn.commit()
    return get_run(run_id)
