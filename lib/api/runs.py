"""Long-running Envy run records and handoff transitions."""

from __future__ import annotations

from typing import Any

import envy_db

RUN_OWNERS = {"envy", "hermes", "codex", "claude_code", "vps_worker", "human"}


def start_handler(body: Any) -> tuple[int, dict]:
    if not isinstance(body, dict):
        return 400, {"error": "bad_request", "hint": "body must be a JSON object"}
    goal = body.get("goal") or body.get("task")
    if not isinstance(goal, str) or not goal.strip():
        return 400, {"error": "bad_request", "hint": "goal is required"}
    owner = body.get("owner") if isinstance(body.get("owner"), str) else "envy"
    if owner not in RUN_OWNERS:
        return 400, {"error": "bad_request", "hint": "invalid owner"}
    project_id = body.get("project_id") if isinstance(body.get("project_id"), str) else None
    run = envy_db.create_run(goal.strip(), project_id=project_id, owner=owner)
    return 200, {"run": run, "local_only": True}


def get_handler(run_id: str) -> tuple[int, dict]:
    run = envy_db.get_run(run_id)
    if run is None:
        return 404, {"error": "not_found"}
    calls = envy_db.fetch_tool_calls(task_id=run.get("task_id")) if run.get("task_id") else []
    return 200, {"run": run, "tool_calls": calls, "local_only": True}


def handoff_handler(run_id: str, body: Any) -> tuple[int, dict]:
    if not isinstance(body, dict):
        return 400, {"error": "bad_request", "hint": "body must be a JSON object"}
    target = body.get("target") if isinstance(body.get("target"), str) else ""
    if target not in RUN_OWNERS:
        return 400, {"error": "bad_request", "hint": "invalid target"}
    run = envy_db.update_run(
        run_id,
        owner=target,
        status="handoff_waiting" if target == "human" else "queued",
        metadata={"handoff_target": target},
    )
    if run is None:
        return 404, {"error": "not_found"}
    return 200, {"run": run, "local_only": True}
