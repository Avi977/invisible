"""Local project handoff drafts.

Handoffs are compact JSON/Markdown records stored under
$INVISIBLE_HOME/handoffs/<project>/. Drafting uses the local Ollama adapter.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config
import envy_db
from hermes_bridge import bridge
from api import ai

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _valid_slug(project: str | None) -> bool:
    return isinstance(project, str) and bool(_SLUG_RE.fullmatch(project))


def _handoff_dir(project: str) -> Path:
    return config.home() / "handoffs" / project


def _checkpoint(project: str) -> dict:
    path = config.home() / "worktrees" / project / "feature" / ".invisible-checkpoint.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


# Directories holding dependencies rather than the project's own code. This
# repo's graph is 151k nodes, 96% of them under vendor/ -- never the subject
# of a handoff, and they crowd out everything that is.
_VENDOR_PREFIXES = ("vendor/", "node_modules/", ".venv/", "venv/", "dist/",
                    "build/", "site-packages/", "third_party/")

_TERM_RE = re.compile(r"[a-z0-9]+")


def _node_path(node: dict) -> str:
    raw = node.get("file_path") or node.get("source_file") or ""
    return str(raw).replace("\\", "/").lstrip("./")


def _is_vendored(node: dict) -> bool:
    return _node_path(node).startswith(_VENDOR_PREFIXES)


def _terms(text: str | None) -> set[str]:
    """Lowercase word tokens worth matching on. Drops 1-2 char noise."""
    if not isinstance(text, str):
        return set()
    return {t for t in _TERM_RE.findall(text.lower()) if len(t) > 2}


def _node_score(node: dict, terms: set[str]) -> int:
    """2 per term hitting the node's label, 1 per term hitting its path."""
    label = _terms(str(node.get("label") or node.get("id") or ""))
    path = _terms(_node_path(node))
    return 2 * len(terms & label) + len(terms & path)


def _graph_excerpt(project: str, query: str | None = None,
                   limit: int = 40) -> dict:
    """Up to `limit` nodes plus the edges among them.

    Given a query, seeds the excerpt with the nodes matching it and expands to
    their direct neighbours, so the packet describes the code the request is
    actually about. Without one, falls back to walk order -- which is what
    every packet used to get regardless of what was asked.
    """
    try:
        from api import relations

        graph = relations.build_graph(project)
    except Exception:  # noqa: BLE001
        return {"nodes": [], "edges": []}
    candidates = [n for n in graph.get("nodes", [])
                  if isinstance(n, dict) and not _is_vendored(n)]
    raw_edges = [e for e in graph.get("edges", []) if isinstance(e, dict)]
    terms = _terms(query)
    seeds: list[dict] = []
    if terms:
        # -i keeps walk order stable among equal scores under reverse=True.
        ranked = sorted(
            ((_node_score(n, terms), -i, n) for i, n in enumerate(candidates)),
            key=lambda t: t[:2], reverse=True)
        seeds = [n for score, _, n in ranked if score > 0][:max(1, limit // 2)]
    if not seeds:
        seeds = candidates[:limit]
    picked = {n.get("id"): n for n in seeds if n.get("id")}
    if terms:
        by_id = {n.get("id"): n for n in candidates}
        for e in raw_edges:
            if len(picked) >= limit:
                break
            frm, to = e.get("from"), e.get("to")
            for near, other in ((frm, to), (to, frm)):
                if near in picked and other in by_id and other not in picked:
                    picked[other] = by_id[other]
                    break
    nodes = list(picked.values())[:limit]
    node_ids = {n.get("id") for n in nodes}
    edges = [e for e in raw_edges
             if e.get("from") in node_ids and e.get("to") in node_ids][:80]
    return {"nodes": nodes, "edges": edges}


def _repo_path(project: str) -> str | None:
    meta = config.project_meta(project)
    repo = meta.get("repo_path")
    if isinstance(repo, str) and repo.strip():
        return str(Path(repo).expanduser().resolve())
    return None


def _git_status(repo: str | None) -> dict:
    if not repo:
        return {"available": False, "summary": "repo path not configured"}
    root = Path(repo)
    if not root.exists():
        return {"available": False, "summary": "repo path not found"}
    try:
        proc = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False, "summary": "git status unavailable"}
    lines = [line for line in (proc.stdout or "").splitlines() if line.strip()]
    return {
        "available": proc.returncode == 0,
        "summary": "\n".join(lines[:40]),
        "dirty": any(line and not line.startswith("##") for line in lines),
    }


def _tool_trace(task_id: str | None) -> list[dict]:
    rows = envy_db.fetch_tool_calls(limit=20, task_id=task_id)
    trace = []
    for row in rows:
        trace.append(
            {
                "tool_id": row["tool_id"],
                "risk_level": row["risk_level"],
                "status": row["status"],
                "approved": bool(row["approved"]),
                "started_at": row["started_at"],
                "error": row["error"],
            }
        )
    return trace


def _build_packet(project: str, goal: str, target: str, checkpoint: dict, graph: dict, task_id: str | None) -> dict:
    repo = _repo_path(project)
    memories = bridge().search_memory(goal or project, project_id=project, limit=8)
    return {
        "schema": "envy.handoff.v1",
        "project": project,
        "target": target,
        "goal": goal,
        "current_state": checkpoint.get("last_summary") or "No checkpoint summary available.",
        "decisions": [],
        "open_blockers": [],
        "repo_path": repo,
        "git_status": _git_status(repo),
        "tool_trace": _tool_trace(task_id),
        "memory_refs": [
            {
                "id": item.get("id"),
                "category": item.get("category"),
                "status": item.get("status"),
                "content": item.get("content"),
            }
            for item in memories
        ],
        "graph_excerpt": graph,
        "next_owner_prompt": f"Continue the Envy task for {project}: {goal}".strip(),
        "resume_command": f"codex --cd {repo}" if target == "codex" and repo else "open Invisible and resume this handoff",
        "stop_condition": "Stop when the requested change is implemented, verified, and summarized.",
    }


def _build_prompt(project: str, user_goal: str, checkpoint: dict, graph: dict) -> str:
    state = {
        "project": project,
        "goal": user_goal,
        "checkpoint": {
            "iteration": checkpoint.get("iteration"),
            "max_iters": checkpoint.get("max_iters"),
            "last_verdict": checkpoint.get("last_verdict"),
            "last_summary": checkpoint.get("last_summary"),
            "last_sha": checkpoint.get("last_sha"),
            "task": checkpoint.get("task"),
            "usage_total": checkpoint.get("usage_total"),
        },
        "graph_excerpt": graph,
    }
    return (
        "Draft a concise project handoff for Envy. "
        "Include: current state, decisions, blockers, graph context, next commands, and next owner prompt. "
        "Use short markdown sections. Keep it under 800 words.\n\n"
        + json.dumps(state, indent=2)
    )


def draft_handler(body: Any) -> tuple[int, dict]:
    if not isinstance(body, dict):
        return 400, {"error": "bad_request", "hint": "body must be a JSON object"}
    project = body.get("project")
    if not _valid_slug(project):
        return 400, {"error": "bad_request", "hint": "valid project is required"}
    goal = body.get("goal") if isinstance(body.get("goal"), str) else ""
    target = body.get("handoff_target") if isinstance(body.get("handoff_target"), str) else body.get("target")
    if target not in {"human", "codex", "claude_code", "hermes", "vps_worker"}:
        target = "human"
    task_id = body.get("task_id") if isinstance(body.get("task_id"), str) else None
    checkpoint = _checkpoint(project)
    graph = _graph_excerpt(project, goal)
    packet = _build_packet(project, goal, target, checkpoint, graph, task_id)
    prompt = _build_prompt(project, goal, checkpoint, graph)
    status, response = ai.chat_handler({
        "message": prompt,
        "page_context": "handoff",
        "project_id": project,
        "model": body.get("model"),
    })
    if status != 200:
        return status, response

    created_at = datetime.now(timezone.utc).isoformat()
    handoff = {
        "project": project,
        "target": target,
        "goal": goal,
        "created_at": created_at,
        "model": response.get("model"),
        "provider": "ollama",
        "local_only": True,
        "cost": 0,
        "markdown": response.get("text", ""),
        "packet": packet,
        "checkpoint": checkpoint,
        "graph": graph,
    }
    handoff["id"] = envy_db.save_handoff(
        project=project,
        target=target,
        goal=goal,
        packet=packet,
        created_at=created_at,
    )
    return 200, {"handoff": handoff}


def save_handler(body: Any) -> tuple[int, dict]:
    handoff = body.get("handoff") if isinstance(body, dict) else None
    if not isinstance(handoff, dict):
        return 400, {"error": "bad_request", "hint": "handoff object is required"}
    project = handoff.get("project")
    if not _valid_slug(project):
        return 400, {"error": "bad_request", "hint": "valid handoff.project is required"}
    created = handoff.get("created_at") if isinstance(handoff.get("created_at"), str) else ""
    stamp = re.sub(r"[^0-9A-Za-z_-]+", "-", created).strip("-") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target_dir = _handoff_dir(project)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{stamp}.json"
    target.write_text(json.dumps(handoff, indent=2), encoding="utf-8")
    if isinstance(handoff.get("packet"), dict):
        envy_db.save_handoff(
            project=project,
            target=handoff.get("target") if isinstance(handoff.get("target"), str) else "human",
            goal=handoff.get("goal") if isinstance(handoff.get("goal"), str) else "",
            packet=handoff["packet"],
            created_at=created or None,
            saved_path=str(target),
        )
    return 200, {
        "saved": True,
        "path": str(target),
        "project": project,
        "local_only": True,
        "cost": 0,
    }
