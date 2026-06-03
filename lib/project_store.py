"""Per-project storage at ~/.invisible/projects/<name>/.

Layout:
  ~/.invisible/projects/<name>/
    context.md                       — cumulative project context (long-lived)
    log/YYYY-MM-DD.md                — daily activity log (one file/day)
    backups/context-YYYY-MM-DD-HHMMSS.md
                                     — snapshots of context.md before rewrites
    suggestions.json                 — current AI-suggested actions
                                       [{title, command, why, risk}, ...]

All operations are stdlib-only and write to disk via atomic-replace (write
to temp + os.replace) so a crash mid-write never leaves a half-written
file. The directory layout is the single source of truth — no SQLite, no
indexes, no caching layer. Pure files mean an SSH-from-VPS or `cat` can
read the same data the dashboard does.

Used by:
  bin/invisible-brief        — writes context, suggestions
  lib/api/brief.py           — reads context + log + suggestions; appends log
  (planned) cron/launchd     — nightly context refresh
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Slug validation ─────────────────────────────────────────────────────
# Project names go directly into directory paths, so they MUST be
# constrained to a safe character set. Mirrors the validation rules used
# elsewhere in the codebase (lib/api/relations.py slug regex, pty PANE_ID_RE).
import re

_PROJECT_SLUG_RE = re.compile(r"^[a-z0-9_-]{1,64}$")


def _validate_slug(project: str) -> str:
    if not isinstance(project, str) or not _PROJECT_SLUG_RE.match(project):
        raise ValueError(
            f"project name {project!r} must match {_PROJECT_SLUG_RE.pattern}"
        )
    return project


# ── Root resolution ────────────────────────────────────────────────────


def _invisible_home() -> Path:
    """Resolve the INVISIBLE_HOME directory (defaults to ~/.invisible).

    Same precedence as bin/invisible-dashboard and bin/invisible-pty:
    explicit env var beats ~/.invisible. We don't import lib.config here
    to keep this module zero-dep (lib.config pulls in tomllib + others).
    """
    env_home = os.environ.get("INVISIBLE_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return Path("~/.invisible").expanduser().resolve()


def project_dir(project: str) -> Path:
    """Return ~/.invisible/projects/<project>/, creating it on first use.

    Also creates the `log/` and `backups/` subdirectories so callers can
    write into them without a separate mkdir.
    """
    _validate_slug(project)
    root = _invisible_home() / "projects" / project
    (root / "log").mkdir(parents=True, exist_ok=True)
    (root / "backups").mkdir(parents=True, exist_ok=True)
    return root


# ── Atomic write helper ────────────────────────────────────────────────


def _atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically.

    Writes to a sibling temp file in the same directory, then os.replace
    (which is atomic on POSIX). A crash before replace leaves the original
    intact; a crash after leaves the new content intact.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except Exception:
        # Best-effort cleanup if replace failed
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ── Context ────────────────────────────────────────────────────────────


def read_context(project: str) -> str:
    """Return the contents of context.md, or "" if missing."""
    p = project_dir(project) / "context.md"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def write_context(project: str, content: str, *, backup: bool = True) -> Path:
    """Write content to context.md atomically.

    If `backup` and a prior context.md exists, snapshot it into backups/
    first. Returns the path to the (new) context.md file.
    """
    root = project_dir(project)
    target = root / "context.md"
    if backup and target.exists():
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        backup_path = root / "backups" / f"context-{ts}.md"
        backup_path.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
    _atomic_write(target, content)
    return target


# ── Daily logs ─────────────────────────────────────────────────────────


def _today_log_path(root: Path) -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return root / "log" / f"{today}.md"


def append_log(project: str, entry: str, *, source: str = "user") -> Path:
    """Append a timestamped entry to today's log; create the file if needed.

    `source` distinguishes "user" entries (manual), "claude" entries
    (Claude-authored mid-session updates), and "system" (cron, lifecycle
    events). The entry header looks like:

        ## 2026-06-02 18:42:11 UTC — claude
        <entry text>

    Returns the path to the log file written to.
    """
    root = project_dir(project)
    log_path = _today_log_path(root)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = f"\n## {ts} — {source}\n"
    body = entry.rstrip() + "\n"
    # Append (not atomic-replace; daily logs are small and grow-only).
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(header + body)
    return log_path


def read_recent_logs(project: str, *, days: int = 7) -> str:
    """Return concatenated log content for the last `days` days, oldest first.

    Missing log files are silently skipped. Used to feed the brief generator.
    """
    root = project_dir(project)
    log_dir = root / "log"
    if not log_dir.exists():
        return ""
    files = sorted(log_dir.glob("*.md"))[-days:]
    parts: list[str] = []
    for f in files:
        try:
            parts.append(f"# {f.stem}\n\n" + f.read_text(encoding="utf-8"))
        except OSError:
            continue
    return "\n\n".join(parts)


def read_today_log(project: str) -> str:
    """Return today's log file content, or "" if not started today."""
    p = _today_log_path(project_dir(project))
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


# ── Suggestions ────────────────────────────────────────────────────────


def read_suggestions(project: str) -> list[dict[str, Any]]:
    """Return the current suggestions list, or [] if not generated yet.

    The JSON file is treated as untrusted (bin/invisible-brief writes it
    but a bug or edit could leave malformed content). Any parse error
    returns [] silently — the UI just shows no chips.
    """
    p = project_dir(project) / "suggestions.json"
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(raw, list):
        return []
    # Coerce each entry to a normalized shape so the API contract is stable
    # even if the brief generator emits extra fields.
    out: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title", "")).strip()
        command = str(entry.get("command", "")).strip()
        if not title or not command:
            continue
        out.append({
            "title": title[:80],
            "command": command,
            "why": str(entry.get("why", ""))[:280],
            "risk": str(entry.get("risk", "")).lower()[:10] or "low",
        })
    return out


def write_suggestions(project: str, suggestions: list[dict[str, Any]]) -> Path:
    """Write the suggestions list atomically. Returns the file path."""
    p = project_dir(project) / "suggestions.json"
    _atomic_write(p, json.dumps(suggestions, indent=2) + "\n")
    return p


# ── Brief assembly ─────────────────────────────────────────────────────


def assemble_brief(project: str) -> dict[str, Any]:
    """Return the API-shaped brief for /api/v1/projects/<id>/brief.

    Shape:
      {
        "project": "<slug>",
        "context": "<context.md content or ''>",
        "context_chars": <int>,
        "today_log": "<today's log or ''>",
        "recent_log": "<last 7 days concatenated or ''>",
        "recent_log_chars": <int>,
        "suggestions": [{title, command, why, risk}, ...],
        "generated_at": "<ISO-8601 UTC of suggestions.json mtime, or null>"
      }
    """
    _validate_slug(project)
    p = project_dir(project)
    sug_path = p / "suggestions.json"
    generated_at = None
    if sug_path.exists():
        generated_at = datetime.fromtimestamp(
            sug_path.stat().st_mtime, tz=timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
    context = read_context(project)
    recent = read_recent_logs(project)
    return {
        "project": project,
        "context": context,
        "context_chars": len(context),
        "today_log": read_today_log(project),
        "recent_log": recent,
        "recent_log_chars": len(recent),
        "suggestions": read_suggestions(project),
        "generated_at": generated_at,
    }


# ── Smoke test (run module directly to verify the layout writes/reads) ─


if __name__ == "__main__":
    proj = "_smoke_test"
    try:
        root = project_dir(proj)
        print(f"root: {root}")
        write_context(proj, "# Test project context\n\nHello, world.\n")
        append_log(proj, "Started smoke test.", source="system")
        write_suggestions(proj, [
            {"title": "Run tests", "command": "pytest", "why": "Verify nothing broke.", "risk": "low"},
            {"title": "Push to main", "command": "git push origin main", "why": "Land recent work.", "risk": "medium"},
        ])
        brief = assemble_brief(proj)
        import pprint
        pprint.pprint(brief, width=100)
        print(f"OK; suggestions saved to {root / 'suggestions.json'}")
    finally:
        # Don't leave smoke test data around
        import shutil
        try:
            shutil.rmtree(project_dir(proj))
            print(f"cleaned up {proj}")
        except OSError:
            pass
