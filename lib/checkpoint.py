"""Orchestrator checkpoint — the cursor that lets a run resume on any machine.

Lives in the feature worktree as `.invisible-checkpoint.json` so `git pull` on the
VPS brings it along. Also mirrored to Notion (via the orchestrator) so you can
inspect state without cloning.

Schema:
  {
    "version": 1,
    "project": "api-rewrite",
    "task": "switch auth from JWT to PASETO",
    "iteration": 3,
    "max_iters": 8,
    "feedback_history": ["...", "..."],
    "last_sha": "abc1234",
    "last_verdict": "changes",
    "last_summary": "JWT path still reachable in /admin",
    "notion_project_id": "...",
    "started_at": "2026-05-12T08:13:22Z",
    "updated_at": "2026-05-12T08:42:10Z",
    "host": "abhishek-mbp",
    "context_chars_used": 128430
  }
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CHECKPOINT_FILE = ".invisible-checkpoint.json"


def _push_to_server(state: dict) -> None:
    """Best-effort POST to the VPS daemon. Fire-and-forget — short timeout,
    no exceptions propagate. Triggered when both INVISIBLE_SERVER_URL and
    INVISIBLE_SERVER_TOKEN are set. The daemon dedupes by content hash, so
    spurious posts during no-op saves are harmless."""
    url = (os.environ.get("INVISIBLE_SERVER_URL") or "").rstrip("/")
    token = os.environ.get("INVISIBLE_SERVER_TOKEN") or ""
    if not url or not token:
        return
    project = state.get("project")
    if not project:
        return
    payload = json.dumps({
        "machine": socket.gethostname(),
        "project": project,
        "state":   state,
    }).encode()
    req = urllib.request.Request(
        f"{url}/api/events",
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        data=payload,
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            r.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        # Log to stderr but never raise; the orchestrator must not die
        # because the VPS is unreachable.
        sys.stderr.write(f"[checkpoint] push to {url} failed: {e}\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def path_for(feature_worktree: Path) -> Path:
    return feature_worktree / CHECKPOINT_FILE


def load(feature_worktree: Path) -> dict | None:
    p = path_for(feature_worktree)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def save(feature_worktree: Path, state: dict) -> None:
    state = {**state}
    state["updated_at"] = _now()
    state.setdefault("started_at", state["updated_at"])
    state.setdefault("host", socket.gethostname())
    state.setdefault("version", 1)
    path_for(feature_worktree).write_text(json.dumps(state, indent=2))
    # Best-effort sync to the VPS daemon. Threaded so a slow server can't
    # stall a checkpoint write. No-op if INVISIBLE_SERVER_URL/TOKEN unset.
    if os.environ.get("INVISIBLE_SERVER_URL"):
        threading.Thread(target=_push_to_server, args=(state,),
                         daemon=True, name="checkpoint-push").start()


def new(project: str, task: str, max_iters: int,
        notion_project_id: str | None = None) -> dict:
    return {
        "version": 1,
        "project": project,
        "task": task,
        "iteration": 0,
        "max_iters": max_iters,
        "feedback_history": [],
        "last_sha": "",
        "last_verdict": "",
        "last_summary": "",
        "notion_project_id": notion_project_id or "",
        "started_at": _now(),
        "updated_at": _now(),
        "host": socket.gethostname(),
        "context_chars_used": 0,
        # Cumulative claude usage across all iterations. Populated by the
        # orchestrator from runners.AgentResult.usage. Codex token usage
        # isn't tracked because the codex CLI doesn't surface it.
        "usage_total": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_input_tokens": 0,
            "cost_usd": 0.0,
        },
        # Per-iteration claude usage in the same shape — useful for spotting
        # an iteration that suddenly blew up.
        "usage_per_iter": [],
    }
