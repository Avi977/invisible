"""SQLite-backed state store for the VPS daemon.

One process writes (the daemon); HTTP handler threads read. SQLite in WAL
mode is fine for this — readers don't block the writer, the writer doesn't
block readers, and there's only ever one writer.

Schema:

  projects (
    machine TEXT, project TEXT,
    json_state TEXT,        -- the full checkpoint dict as JSON
    updated_at TEXT,        -- ISO 8601 (from the checkpoint's own field)
    PRIMARY KEY (machine, project)
  )

  events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine TEXT, project TEXT,
    kind TEXT,              -- 'checkpoint', 'note', etc.
    payload TEXT,           -- arbitrary JSON
    created_at TEXT
  )

The `events` table is append-only and pruned to the last N rows on a
schedule (default keeps the most recent 5000). It exists so SSE clients
can replay missed events on reconnect via Last-Event-ID — handy when the
laptop goes through a coffee-shop wifi.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False because BaseHTTPRequestHandler spawns a thread
        # per request and we serve reads from those threads. The lock below
        # serializes writes; SQLite handles concurrent reads in WAL.
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False,
                                     isolation_level=None)  # autocommit
        self._conn.row_factory = sqlite3.Row
        self._write_lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._write_lock:
            cur = self._conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                  machine    TEXT NOT NULL,
                  project    TEXT NOT NULL,
                  json_state TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  PRIMARY KEY (machine, project)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS events (
                  id         INTEGER PRIMARY KEY AUTOINCREMENT,
                  machine    TEXT NOT NULL,
                  project    TEXT NOT NULL,
                  kind       TEXT NOT NULL,
                  payload    TEXT NOT NULL,
                  created_at TEXT NOT NULL
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_updated "
                        "ON projects(updated_at DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_events_created "
                        "ON events(created_at DESC)")

    # ── Writes ──────────────────────────────────────────────────────────

    def ingest_checkpoint(self, machine: str, project: str,
                          state: dict[str, Any]) -> int:
        """Upsert a project's full state. Returns the new events.id row.

        Deduplicates: if the incoming state matches what's already stored,
        no event is recorded (avoids fan-out spam during a no-op save)."""
        body = json.dumps(state, sort_keys=True)
        updated_at = state.get("updated_at") or _now_iso()
        with self._write_lock:
            cur = self._conn.cursor()
            row = cur.execute(
                "SELECT json_state FROM projects WHERE machine=? AND project=?",
                (machine, project),
            ).fetchone()
            if row and row["json_state"] == body:
                return 0  # no-op
            cur.execute("""
                INSERT INTO projects (machine, project, json_state, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (machine, project) DO UPDATE SET
                  json_state=excluded.json_state,
                  updated_at=excluded.updated_at
            """, (machine, project, body, updated_at))
            cur.execute("""
                INSERT INTO events (machine, project, kind, payload, created_at)
                VALUES (?, ?, 'checkpoint', ?, ?)
            """, (machine, project, body, _now_iso()))
            return int(cur.lastrowid or 0)

    def prune_events(self, keep: int = 5000) -> int:
        """Trim the events table to the most recent `keep` rows. Returns the
        number of rows deleted."""
        with self._write_lock:
            cur = self._conn.cursor()
            cur.execute("""
                DELETE FROM events WHERE id NOT IN (
                  SELECT id FROM events ORDER BY id DESC LIMIT ?
                )
            """, (keep,))
            return cur.rowcount

    # ── Reads ───────────────────────────────────────────────────────────

    def list_projects(self) -> list[dict]:
        """All known (machine, project) rows, decoded."""
        cur = self._conn.cursor()
        rows = cur.execute(
            "SELECT machine, project, json_state, updated_at "
            "FROM projects ORDER BY updated_at DESC"
        ).fetchall()
        out = []
        for r in rows:
            try:
                state = json.loads(r["json_state"])
            except json.JSONDecodeError:
                continue
            out.append({
                "machine": r["machine"],
                "project": r["project"],
                "updated_at": r["updated_at"],
                "state": state,
            })
        return out

    def get_project(self, project: str, machine: str | None = None) -> dict | None:
        """Look up the most recent state for a project across machines, or
        for a specific machine. Returns dict {machine, project, state} or
        None."""
        cur = self._conn.cursor()
        if machine:
            row = cur.execute(
                "SELECT machine, project, json_state, updated_at "
                "FROM projects WHERE machine=? AND project=?",
                (machine, project),
            ).fetchone()
        else:
            row = cur.execute(
                "SELECT machine, project, json_state, updated_at "
                "FROM projects WHERE project=? "
                "ORDER BY updated_at DESC LIMIT 1",
                (project,),
            ).fetchone()
        if not row:
            return None
        try:
            return {
                "machine": row["machine"],
                "project": row["project"],
                "updated_at": row["updated_at"],
                "state": json.loads(row["json_state"]),
            }
        except json.JSONDecodeError:
            return None

    def events_since(self, last_id: int = 0, limit: int = 100) -> list[dict]:
        """Events with id > last_id, oldest-first (so SSE can replay in order)."""
        cur = self._conn.cursor()
        rows = cur.execute(
            "SELECT id, machine, project, kind, payload, created_at "
            "FROM events WHERE id > ? ORDER BY id ASC LIMIT ?",
            (last_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def latest_event_id(self) -> int:
        cur = self._conn.cursor()
        row = cur.execute("SELECT MAX(id) AS m FROM events").fetchone()
        return int(row["m"] or 0)

    def close(self) -> None:
        with self._write_lock:
            self._conn.close()
