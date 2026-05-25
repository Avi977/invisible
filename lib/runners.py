"""Headless invocation of `codex` and `claude` CLIs.

Both CLIs evolve fast; the exact flag names are version-pinned in CONFIG below
so you only need to edit one place when they change.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG = {
    "codex_cmd": ["codex", "exec", "--skip-git-repo-check"],
    "claude_cmd": ["claude", "-p", "--output-format", "json"],
    "codex_timeout_s": 900,
    "claude_timeout_s": 600,
    # Hard cap on diff size sent to claude. Set well below the context budget
    # so the orchestrator's compression heuristic still has room for feedback
    # history. Override with INVISIBLE_REVIEW_DIFF_CAP env var (chars).
    "review_diff_cap_chars": 60_000,
}


@dataclass
class AgentResult:
    ok: bool
    stdout: str
    stderr: str
    parsed: dict | None = None
    # Populated for claude calls when the --output-format json envelope
    # carries usage/cost info. None for codex (no token reporting).
    usage: dict | None = None


def _run(cmd: list[str], cwd: Path, stdin: str, timeout: int) -> AgentResult:
    try:
        p = subprocess.run(
            cmd, cwd=str(cwd), input=stdin, capture_output=True,
            text=True, timeout=timeout, check=False,
        )
        return AgentResult(ok=p.returncode == 0, stdout=p.stdout, stderr=p.stderr)
    except subprocess.TimeoutExpired as e:
        return AgentResult(ok=False, stdout="", stderr=f"timeout after {timeout}s")
    except FileNotFoundError as e:
        return AgentResult(ok=False, stdout="", stderr=f"binary not found: {cmd[0]}")


def run_codex(task: str, worktree: Path, system_prompt: str = "") -> AgentResult:
    """Ask Codex to perform `task` inside `worktree`. Returns its stdout."""
    prompt = f"{system_prompt}\n\nTASK:\n{task}" if system_prompt else task
    return _run(CONFIG["codex_cmd"], worktree, prompt, CONFIG["codex_timeout_s"])


def _truncate_diff(diff: str, cap: int) -> str:
    """Truncate a diff at `cap` chars with a sentinel claude can see and react to.
    Keeps the head (where most diffs put hunk-context information about which
    files changed) — claude will treat unseen content as untested."""
    if len(diff) <= cap:
        return diff
    omitted = len(diff) - cap
    marker = f"\n\n... [diff truncated: {omitted} chars omitted of {len(diff)} total] ...\n"
    return diff[:cap] + marker


def run_claude_review(diff: str, task: str, worktree: Path,
                      system_prompt: str) -> AgentResult:
    """Send `diff` to Claude for review. Expects JSON verdict back."""
    cap = int(os.environ.get("INVISIBLE_REVIEW_DIFF_CAP",
                             CONFIG["review_diff_cap_chars"]))
    clamped = _truncate_diff(diff, cap)
    prompt = (
        f"{system_prompt}\n\n"
        f"ORIGINAL TASK:\n{task}\n\n"
        f"DIFF UNDER REVIEW:\n```diff\n{clamped}\n```\n\n"
        "Respond ONLY with a single JSON object matching this schema:\n"
        '{"verdict": "approve|changes|block", "summary": "<one line>", '
        '"issues": ["..."], "suggestions": ["..."], "body_md": "<full markdown review>"}'
    )
    result = _run(CONFIG["claude_cmd"], worktree, prompt, CONFIG["claude_timeout_s"])
    result.parsed = _parse_claude_json(result.stdout)
    result.usage = _extract_claude_usage(result.stdout)
    return result


def _extract_claude_usage(raw: str) -> dict | None:
    """Pluck token/cost telemetry from claude's --output-format json envelope.
    Returns None if the envelope isn't shaped as expected (e.g. claude was
    stubbed in tests, or future versions drop the field)."""
    try:
        env = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(env, dict):
        return None
    u = env.get("usage") or {}
    return {
        "input_tokens": int(u.get("input_tokens", 0) or 0),
        "output_tokens": int(u.get("output_tokens", 0) or 0),
        "cache_read_input_tokens": int(u.get("cache_read_input_tokens", 0) or 0),
        "cache_creation_input_tokens": int(u.get("cache_creation_input_tokens", 0) or 0),
        "cost_usd": float(env.get("total_cost_usd", 0) or 0),
        "duration_ms": int(env.get("duration_ms", 0) or 0),
    }


def _parse_claude_json(raw: str) -> dict | None:
    """Claude's --output-format json wraps the actual content under 'result'.
    We then parse the inner content as JSON. Falls back to regex extraction."""
    try:
        envelope = json.loads(raw)
        inner = envelope.get("result", raw) if isinstance(envelope, dict) else raw
    except json.JSONDecodeError:
        inner = raw
    try:
        return json.loads(inner)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", inner, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    print("[runners] could not parse Claude JSON verdict", file=sys.stderr)
    return None


def git_diff(worktree: Path, base: str = "HEAD~1") -> str:
    """Diff of the most recent commit.

    Order of attempts:
      1. `git diff <base> HEAD` (default base=HEAD~1) — normal case after >1 commit.
      2. `git show --format= HEAD` — works for the very first commit on the
         branch (no parent), and is also a safe fallback when HEAD~1 is missing.
      3. `git diff` — unstaged working-tree changes (only matters if codex
         somehow didn't commit; the orchestrator commits after each turn, so
         this should be empty in practice).
    """
    if base:
        r = subprocess.run(
            ["git", "diff", base, "HEAD"],
            cwd=str(worktree), capture_output=True, text=True, check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    r = subprocess.run(
        ["git", "show", "--format=", "HEAD"],
        cwd=str(worktree), capture_output=True, text=True, check=False,
    )
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout
    r = subprocess.run(
        ["git", "diff"], cwd=str(worktree),
        capture_output=True, text=True, check=False,
    )
    return r.stdout


def git_sha(worktree: Path) -> str:
    r = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=str(worktree), capture_output=True, text=True, check=False,
    )
    return r.stdout.strip()


def git_commit_all(worktree: Path, message: str) -> bool:
    subprocess.run(["git", "add", "-A"], cwd=str(worktree), check=False)
    r = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=str(worktree), capture_output=True, text=True, check=False,
    )
    return r.returncode == 0
