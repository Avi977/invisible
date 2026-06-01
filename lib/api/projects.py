"""Build the /api/v1/projects response from invisible.toml + git + checkpoints.

The DATA_SETS.default.projects[] shape (frontend/data.jsx) is the contract:
13 keys per project, exact types, color from a fixed 6-element palette.

Data flow:
  invisible.toml ──┐
                   ├──→ build_projects() ──→ list[dict] (shape per DATA_SETS)
  git -C repo ─────┤
  checkpoint.json ─┘

Security notes:
  - All git subprocess calls use the list-form of subprocess.run (no shell=True)
    with a 2-second timeout. Path traversal via repo_path is rejected by
    _safe_path() — only paths inside the user's $HOME or $INVISIBLE_HOME are
    allowed.
  - handle_projects() wraps build_projects() in try/except and returns a
    generic 500 body on any failure. No traceback, no filesystem paths.
  - All public callables avoid printing or returning absolute paths.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# lib/ is on sys.path via bin/invisible-dashboard, so these imports work from
# both the daemon and the test harness.
import checkpoint
import config
from dashboard_render import humanize_age


# Stable, deterministic 6-color palette. Order matters — index is derived from
# md5(name) % 6. Matches the colors used in DATA_SETS.default.projects[].
PALETTE: list[str] = [
    "#f5b343",
    "#5cc8ff",
    "#b794ff",
    "#4ade80",
    "#f56fb1",
    "#5ee0c8",
]


# ────────────────────────────────────────────────────────────────────────
# helpers
# ────────────────────────────────────────────────────────────────────────


def _color_for(name: str) -> str:
    """Deterministic palette lookup keyed on project name.

    Uses md5 (not Python's built-in hash()) because hash() is salted per-run
    and would produce different colors on each daemon restart — bad UX.
    """
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()
    return PALETTE[int(digest, 16) % len(PALETTE)]


def _code_for(name: str) -> str:
    """Two-letter uppercase code derived from the project name.

    Multi-word names use the first letter of each of the first two words
    (e.g. "northwind retail" → "NR"); single-word names use the first two
    letters (e.g. "echo" → "EC").
    """
    if not name:
        return "??"
    words = name.split()
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    return name[:2].upper()


def _safe_path(p: str) -> Path | None:
    """Resolve `p` and confirm it is inside $HOME or $INVISIBLE_HOME.

    Returns None for empty strings, paths that escape the trust boundary, or
    paths that raise during resolution. Returning None is treated by callers
    as "repo missing" — matching the planning-row UX in the mock.
    """
    if not p:
        return None
    try:
        resolved = Path(os.path.expanduser(p)).resolve()
    except (OSError, RuntimeError):
        return None
    home_dir = Path(os.path.expanduser("~")).resolve()
    invisible_root = config.home().resolve()
    try:
        # Both is_relative_to checks are Path methods (py3.9+). Either one
        # being true means the path is inside a trusted root.
        if resolved.is_relative_to(home_dir):
            return resolved
        if resolved.is_relative_to(invisible_root):
            return resolved
    except (AttributeError, ValueError):
        pass
    return None


def _run_git(args: list[str], cwd: Path) -> str | None:
    """Run a git command with a 2s timeout. Returns stdout (stripped) or None.

    Failure modes that yield None:
      - cwd does not exist
      - git not on PATH
      - git returned non-zero
      - the call timed out (corrupt or hung repo)
    Errors are swallowed — never propagate to the HTTP handler so a single
    bad repo can't poison the whole response.
    """
    if not cwd.exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), *args],
            shell=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _branch_and_last_commit(repo_path: Path | None) -> tuple[str, str]:
    """Return (branch, humanized lastCommit) for repo_path.

    On any failure (path missing, not a git repo, no commits, timeout) returns
    ("—", "—") — matching the mock's planning-row presentation.
    """
    if repo_path is None:
        return ("—", "—")
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_path)
    if not branch:
        return ("—", "—")
    iso = _run_git(["log", "-1", "--format=%cI"], repo_path)
    if not iso:
        return (branch, "—")
    age = humanize_age(iso)
    if age == "?":
        return (branch, "—")
    return (branch, f"{age} ago")


def _status_for(cp: dict | None, repo_exists: bool) -> str:
    """Deterministic status derivation (per plan <interfaces>).

    Rules:
      - no checkpoint → "planning" (regardless of repo)
      - approve verdict at max iters → "shipped"
      - changes verdict with no progress in 24h → "blocked"
      - otherwise → "in-progress"
    """
    if not cp:
        return "planning"
    verdict = cp.get("last_verdict") or ""
    iteration = int(cp.get("iteration") or 0)
    max_iters = int(cp.get("max_iters") or 0)
    if verdict == "approve" and max_iters > 0 and iteration >= max_iters:
        return "shipped"
    if verdict == "changes":
        # "no progress in 24h" — if updated_at is older than a day, blocked.
        # We compare via humanize_age's normalized output: anything ending in
        # "d" (days) or "?" (unparseable) qualifies as stale.
        age = humanize_age(cp.get("updated_at") or "")
        if age.endswith("d"):
            return "blocked"
    return "in-progress"


def _todos_for(cp: dict | None) -> list[dict]:
    """Convert checkpoint feedback_history into the todos[] shape.

    Up to last 4 entries become {t: <80-char truncation>, done: False}. When
    the last verdict is "approve", the most-recent entry flips done=True
    (the user fixed the prior round of feedback).
    """
    if not cp:
        return []
    history = cp.get("feedback_history") or []
    if not isinstance(history, list):
        return []
    recent = history[-4:]
    todos: list[dict] = []
    for entry in recent:
        text = str(entry).strip().splitlines()[0] if entry else ""
        todos.append({"t": text[:80], "done": False})
    if todos and (cp.get("last_verdict") or "") == "approve":
        todos[-1]["done"] = True
    return todos


def _progress_for(cp: dict | None) -> int:
    """Compute a 0..100 progress integer from iteration / max_iters."""
    if not cp:
        return 0
    iteration = int(cp.get("iteration") or 0)
    max_iters = int(cp.get("max_iters") or 0)
    if max_iters <= 0:
        return 0
    verdict = cp.get("last_verdict") or ""
    if verdict == "approve" and iteration >= max_iters:
        return 100
    pct = int(round((iteration / max_iters) * 100))
    return max(0, min(100, pct))


def _id_for(name: str) -> str:
    """Stable slug for a project name (lowercase, hyphenated)."""
    return name.lower().strip().replace(" ", "-").replace("_", "-")


# ────────────────────────────────────────────────────────────────────────
# public API
# ────────────────────────────────────────────────────────────────────────


def build_projects() -> list[dict]:
    """Assemble the /api/v1/projects response body.

    Returns a list of dicts shaped exactly like DATA_SETS.default.projects[]
    in frontend/data.jsx — 13 keys per element, in stable order.

    Sources, per project:
      - name, stack, summary, repo_path → invisible.toml [[projects]]
      - branch, lastCommit              → git -C <repo_path> ...
      - status, progress, todos, note   → orchestrator checkpoint store
      - color, code, id                 → derived deterministically from name

    Never raises. On any unrecoverable read failure, returns whatever rows
    were assembled before the failure (callers can also wrap this in
    handle_projects() for a clean 500).
    """
    try:
        cfg = config.load_toml()
    except Exception:  # noqa: BLE001 — defensive; never crash the daemon
        return []

    rows: list[dict] = []
    for proj in cfg.get("projects", []) or []:
        name = (proj.get("name") or "").strip()
        if not name:
            continue

        repo_raw = proj.get("repo_path") or ""
        repo_path = _safe_path(repo_raw) if repo_raw else None
        repo_exists = repo_path is not None and repo_path.exists()

        worktree = config.home() / "worktrees" / name / "feature"
        try:
            cp = checkpoint.load(worktree)
        except Exception:  # noqa: BLE001
            cp = None

        branch, last_commit = _branch_and_last_commit(repo_path)

        # Build summary preference order: toml summary → checkpoint task → "".
        # We strip any newlines and clamp length so it never overflows the card.
        summary = (proj.get("summary") or "").strip()
        if not summary and cp:
            task = (cp.get("task") or "").strip()
            summary = task.splitlines()[0][:200] if task else ""

        # note = checkpoint.last_summary; safe fallback to empty string.
        note = ""
        if cp:
            note = (cp.get("last_summary") or "").strip()

        # stack list from toml; default empty list to match the planning-row mock.
        stack_raw = proj.get("stack") or []
        stack = [str(s) for s in stack_raw if isinstance(s, (str, int, float))]

        rows.append({
            "id": _id_for(name),
            "code": _code_for(name),
            "name": name,
            "color": _color_for(name),
            "status": _status_for(cp, repo_exists),
            "branch": branch,
            "lastCommit": last_commit,
            "summary": summary,
            "progress": _progress_for(cp),
            "todos": _todos_for(cp),
            "note": note,
            "stack": stack,
            "nextEvent": "—",
        })
    return rows


def handle_projects(handler: Any) -> None:
    """HTTP handler entry point for GET /api/v1/projects.

    Wraps build_projects() in a defensive try/except. On any exception, sends
    a generic 500 with `{"error":"internal error"}` — never a traceback, never
    a filesystem path.
    """
    try:
        rows = build_projects()
        handler._send_json(rows)
    except Exception as exc:  # noqa: BLE001 — generic 500 path
        # Log to stderr (no paths, no traceback) — operator can grep for it.
        try:
            sys.stderr.write(f"[api/projects] internal error: {type(exc).__name__}\n")
        except Exception:  # noqa: BLE001
            pass
        try:
            handler._send_json({"error": "internal error"}, status=500)
        except Exception:  # noqa: BLE001
            pass
