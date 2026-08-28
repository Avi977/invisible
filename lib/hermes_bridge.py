"""Invisible-owned facade for embedded Hermes runtime state.

The real Hermes package is intentionally kept behind this bridge. Envy stores
Hermes-compatible memory, skill, session, and schedule files under
$INVISIBLE_HOME/hermes so no global ~/.hermes state is touched unless the user
explicitly points the bridge elsewhere later.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import config
import envy_db

MEMORY_CATEGORIES = {
    "user_preference",
    "project_fact",
    "workflow_pattern",
    "credential_location",
    "environment_fact",
    "recurring_task",
}

_SLUG_RE = re.compile(r"[^a-z0-9_-]+")
_SECRET_VALUE_RE = re.compile(
    r"(ghp_[a-z0-9_]{20,}|sk-[a-z0-9_-]{20,}|xox[baprs]-[a-z0-9-]{20,}|[a-z0-9+/]{32,}={0,2})",
    re.IGNORECASE,
)


def _slug(value: str) -> str:
    return _SLUG_RE.sub("-", value.lower()).strip("-")[:80] or "item"


class HermesBridge:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or (config.home() / "hermes")).resolve()
        self.memories_dir = self.root / "memories"
        self.skills_dir = self.root / "skills"
        self.sessions_dir = self.root / "sessions"
        self.schedules_dir = self.root / "schedules"
        self.user_model_dir = self.root / "user-model"
        self.vendor_path = self._vendor_path()
        self.ensure_layout()

    def _vendor_path(self) -> Path | None:
        repo_vendor = Path(__file__).resolve().parent.parent / "vendor" / "hermes-agent"
        if repo_vendor.exists():
            return repo_vendor.resolve()
        configured = os.environ.get("HERMES_AGENT_PATH", "").strip()
        if configured:
            path = Path(os.path.expanduser(configured)).resolve()
            if path.exists():
                return path
        local = Path.home() / "AppData" / "Local" / "hermes" / "hermes-agent"
        if local.exists():
            return local.resolve()
        return None

    def ensure_layout(self) -> None:
        for path in (
            self.root,
            self.memories_dir,
            self.skills_dir,
            self.sessions_dir,
            self.schedules_dir,
            self.user_model_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def status(self) -> dict:
        return {
            "root": str(self.root),
            "memories": str(self.memories_dir),
            "skills": str(self.skills_dir),
            "sessions": str(self.sessions_dir),
            "schedules": str(self.schedules_dir),
            "user_model": str(self.user_model_dir),
            "vendor_path": str(self.vendor_path) if self.vendor_path else None,
            "embedded": bool(self.vendor_path),
        }

    def search_memory(self, query: str, project_id: str | None = None, limit: int = 20) -> list[dict]:
        return envy_db.search_memories(query, limit=limit, project_id=project_id)

    def write_memory(
        self,
        *,
        category: str,
        content: str,
        project_id: str | None = None,
        source: str | None = None,
        promote: bool = False,
        metadata: dict | None = None,
    ) -> dict:
        if category not in MEMORY_CATEGORIES:
            raise ValueError("invalid memory category")
        text = content.strip()
        if not text:
            raise ValueError("content is required")
        if _SECRET_VALUE_RE.search(text):
            raise ValueError("memory content appears to contain a secret value")
        status = "promoted" if promote or category == "user_preference" else "pending"
        memory = envy_db.write_memory(
            category=category,
            content=text,
            status=status,
            source=source,
            project_id=project_id,
            metadata=metadata or {},
        )
        path = self.memories_dir / f"{memory['id']}.json"
        path.write_text(json.dumps(memory, indent=2), encoding="utf-8")
        memory["path"] = str(path)
        return memory

    def search_sessions(self, query: str, limit: int = 20) -> list[dict]:
        matches = []
        needle = query.lower().strip()
        for path in sorted(self.sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            blob = json.dumps(data).lower()
            if not needle or needle in blob:
                data["path"] = str(path)
                matches.append(data)
            if len(matches) >= limit:
                break
        return matches

    def create_skill_from_handoff(self, handoff: dict) -> dict:
        project = str(handoff.get("project") or "project")
        goal = str(handoff.get("goal") or "handoff")
        skill_id = _slug(f"{project}-{goal}")
        skill_dir = self.skills_dir / skill_id
        skill_dir.mkdir(parents=True, exist_ok=True)
        path = skill_dir / "SKILL.md"
        markdown = handoff.get("markdown") or json.dumps(handoff.get("packet") or handoff, indent=2)
        path.write_text(f"# {goal}\n\n{markdown}\n", encoding="utf-8")
        return {"id": skill_id, "path": str(path)}

    def run_skill(self, skill_id: str, args: dict | None = None) -> dict:
        path = self.skills_dir / _slug(skill_id) / "SKILL.md"
        if not path.exists():
            return {"ok": False, "error": "skill_not_found"}
        return {
            "ok": True,
            "skill_id": _slug(skill_id),
            "instructions": path.read_text(encoding="utf-8"),
            "args": args or {},
        }

    def schedule_task(self, task: str, cron: str | None = None, metadata: dict | None = None) -> dict:
        if not task.strip():
            raise ValueError("task is required")
        schedule = {
            "task": task.strip(),
            "cron": cron,
            "enabled": True,
            "metadata": metadata or {},
        }
        path = self.schedules_dir / f"{_slug(task)}.json"
        path.write_text(json.dumps(schedule, indent=2), encoding="utf-8")
        return {**schedule, "path": str(path)}


def bridge() -> HermesBridge:
    return HermesBridge()
