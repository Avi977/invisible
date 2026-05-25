"""Codex ↔ Claude turn-taking loop with continuity, context budgeting,
auto-retries, Telegram alerts, and VPS handoff.

Design tenets (per the user spec):
- "The work must not stop." Failures are retried with backoff; unrecoverable
  errors notify Telegram, save checkpoint, and exit cleanly so a watcher can
  resume.
- "Context clears at 70%." We estimate cumulative prompt size; when the next
  prompt would push past CONTEXT_BUDGET * 0.7, we compress feedback_history
  via a quick claude summarizer pass before continuing. Each subprocess
  invocation is otherwise stateless (fresh claude/codex CLI per turn), so
  this is the only place context can grow.
- "Resumable on VPS." Every turn writes .invisible-checkpoint.json to the
  feature worktree. `invisible-review <project> --resume` rebuilds the loop
  from that file. `invisible-vps-handoff <project>` pushes + ssh's the same
  resume.
"""

from __future__ import annotations

import argparse
import logging
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import checkpoint  # noqa: E402
import markdown_vault  # noqa: E402
import notion  # noqa: E402
import telegram  # noqa: E402
from config import home, load_env, load_toml  # noqa: E402
from runners import (  # noqa: E402
    git_commit_all, git_diff, git_sha,
    run_claude_review, run_codex,
)

# ── Context budgeting ────────────────────────────────────────────────────
DEFAULT_CONTEXT_BUDGET_TOKENS = 150_000
CHARS_PER_TOKEN_APPROX = 4   # conservative; real ratio ~3.5
CONTEXT_THRESHOLD = 0.70     # compress at 70%

# ── Retry policy ─────────────────────────────────────────────────────────
MAX_RETRIES_PER_TURN = 3
RETRY_BACKOFF_BASE_S = 30

# ── Stop signaling ───────────────────────────────────────────────────────
# Set by SIGTERM handler so the loop exits cleanly between iterations
# instead of in the middle of a codex/claude turn.
_STOP_REQUESTED = False


def _pidfile_path(project: str) -> Path:
    d = home() / "run"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{project}.pid"


def _write_pidfile(project: str) -> Path:
    p = _pidfile_path(project)
    p.write_text(str(os.getpid()))
    return p


def _clear_pidfile(project: str) -> None:
    try:
        _pidfile_path(project).unlink()
    except FileNotFoundError:
        pass


def _read_pidfile(project: str) -> int | None:
    p = _pidfile_path(project)
    if not p.exists():
        return None
    try:
        return int(p.read_text().strip())
    except (OSError, ValueError):
        return None


def _is_running(project: str) -> bool:
    pid = _read_pidfile(project)
    if not pid:
        return False
    try:
        os.kill(pid, 0)  # signal 0 = existence probe
        return True
    except (OSError, ProcessLookupError):
        return False


def _handle_term(signum, frame):  # noqa: ARG001
    global _STOP_REQUESTED
    _STOP_REQUESTED = True


def setup_logging() -> logging.Logger:
    """Rotating file handler: 10 MB per file, 5 backups. Long --continuous
    runs no longer grow orchestrator.log unbounded."""
    from logging.handlers import RotatingFileHandler
    log_dir = home() / "logs"; log_dir.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("orchestrator")
    log.setLevel(logging.INFO)
    if not log.handlers:
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        fh = RotatingFileHandler(
            log_dir / "orchestrator.log",
            maxBytes=10 * 1024 * 1024, backupCount=5,
        )
        fh.setFormatter(fmt); log.addHandler(fh)
        sh = logging.StreamHandler(sys.stdout); sh.setFormatter(fmt); log.addHandler(sh)
    return log


def read_prompt(name: str) -> str:
    p = home() / "prompts" / name
    return p.read_text() if p.exists() else ""


# Cap on per-file research content; well below review_diff_cap_chars so the
# research blob never crowds out the diff in claude's context.
RESEARCH_FILE_CAP_CHARS = 8_000


def read_research_notes(research_worktree: Path) -> str:
    """Pull all *.md files under the research worktree into a single blob.

    The convention is: do exploratory research/note-taking in the research/
    worktree, then run the review loop. Anything committed (or just sitting)
    as markdown in research/ is treated as background context for codex.

    Files are sorted by mtime ascending so newer notes appear last and tend
    to dominate the model's attention. Each file is capped individually to
    keep one long file from starving the rest.
    """
    if not research_worktree.exists():
        return ""
    md_files: list[Path] = []
    for p in research_worktree.rglob("*.md"):
        # Skip anything inside .git (worktrees have a .git file, but rglob
        # follows directories that contain config-managed files anyway).
        if ".git" in p.parts:
            continue
        md_files.append(p)
    if not md_files:
        return ""
    md_files.sort(key=lambda x: x.stat().st_mtime)
    chunks: list[str] = []
    for f in md_files:
        try:
            text = f.read_text(errors="replace")
        except OSError:
            continue
        if not text.strip():
            continue
        rel = f.relative_to(research_worktree)
        if len(text) > RESEARCH_FILE_CAP_CHARS:
            text = text[:RESEARCH_FILE_CAP_CHARS] + f"\n\n[truncated — {len(text)} chars total]"
        chunks.append(f"### research/{rel}\n\n{text}")
    return "\n\n---\n\n".join(chunks)


def context_budget_chars() -> int:
    tokens = int(os.environ.get("INVISIBLE_CONTEXT_BUDGET", DEFAULT_CONTEXT_BUDGET_TOKENS))
    return tokens * CHARS_PER_TOKEN_APPROX


def approx_chars(*parts: str) -> int:
    return sum(len(p or "") for p in parts)


def sync_review_worktree(review: Path, sha: str, log: logging.Logger) -> None:
    """Advance the review worktree's detached HEAD to `sha` (the SHA codex
    just committed in the feature worktree)."""
    if not sha:
        log.warning("sync_review_worktree called without SHA; skipping")
        return
    r = subprocess.run(["git", "checkout", "--detach", sha],
                       cwd=str(review), capture_output=True, text=True, check=False)
    if r.returncode != 0:
        log.warning("review checkout %s failed: %s", sha, r.stderr.strip())


def compress_feedback(history: list[str], log: logging.Logger) -> list[str]:
    """Use claude -p to summarize older feedback into a single bullet list."""
    if len(history) <= 2:
        return history
    old, recent = history[:-1], history[-1:]
    prompt = (
        "Summarize the following review-feedback items into <=8 short bullets that "
        "capture every must-fix. No prose around it. One bullet per line.\n\n"
        + "\n---\n".join(old)
    )
    try:
        r = subprocess.run(["claude", "-p", prompt], capture_output=True,
                           text=True, timeout=180, check=False)
        if r.returncode == 0 and r.stdout.strip():
            summary = r.stdout.strip()
            log.info("compressed %d feedback items into %d chars",
                     len(old), len(summary))
            return [summary] + recent
    except Exception as e:
        log.warning("feedback compression failed: %s", e)
    # On failure, drop the oldest two entries — graceful degradation
    return history[2:]


def maybe_compress(state: dict, codex_sys: str, claude_sys: str, task: str,
                   log: logging.Logger) -> None:
    """If the next codex+claude round would push past 70% budget, compress."""
    feedback_blob = "\n".join(state["feedback_history"])
    projected = approx_chars(codex_sys, task, feedback_blob,
                             claude_sys, "diff placeholder " * 5000)
    state["context_chars_used"] = projected
    budget = context_budget_chars()
    if projected > budget * CONTEXT_THRESHOLD:
        log.warning("context at %.0f%% of budget (%d / %d chars) — compressing",
                    100 * projected / budget, projected, budget)
        telegram.notify(
            f"Context at {100 * projected / budget:.0f}% — compressing feedback for "
            f"`{state['project']}` (iter {state['iteration']+1}).",
            level="warn", source="invisible-orchestrator",
        )
        state["feedback_history"] = compress_feedback(state["feedback_history"], log)


def run_codex_with_retries(task_blob: str, feature: Path, system: str,
                           log: logging.Logger):
    for attempt in range(1, MAX_RETRIES_PER_TURN + 1):
        r = run_codex(task_blob, feature, system)
        if r.ok:
            return r
        log.warning("codex turn failed (attempt %d/%d): %s",
                    attempt, MAX_RETRIES_PER_TURN, r.stderr[:300])
        if attempt < MAX_RETRIES_PER_TURN:
            time.sleep(RETRY_BACKOFF_BASE_S * attempt)
    telegram.notify(
        f"Codex failed {MAX_RETRIES_PER_TURN}× in {feature.name}. Last err:\n"
        f"```\n{r.stderr[-1000:]}\n```",
        level="error", source="invisible-orchestrator",
    )
    return r


def run_claude_with_retries(diff: str, task: str, review: Path, system: str,
                            log: logging.Logger):
    for attempt in range(1, MAX_RETRIES_PER_TURN + 1):
        r = run_claude_review(diff, task, review, system)
        if r.parsed:
            return r
        log.warning("claude returned unparseable JSON (attempt %d/%d)",
                    attempt, MAX_RETRIES_PER_TURN)
        if attempt < MAX_RETRIES_PER_TURN:
            time.sleep(RETRY_BACKOFF_BASE_S * attempt)
    telegram.notify(
        f"Claude review returned unparseable JSON {MAX_RETRIES_PER_TURN}× in "
        f"{review.name}.", level="error", source="invisible-orchestrator",
    )
    return r


def preflight(project: str, feature: Path, review: Path,
              codex_sys: str, claude_sys: str) -> list[str]:
    """Return a list of failure strings; empty list = all good.

    Catches the things that would otherwise burn tokens or worse:
      - codex/claude binaries missing from PATH
      - system prompts missing (would silently send "" as the role spec)
      - feature worktree isn't on a real branch (detached HEAD → can't commit)
      - feature worktree has uncommitted changes (codex would scoop them up)
    """
    fails: list[str] = []

    for bin_name in ("codex", "claude"):
        if not shutil.which(bin_name):
            fails.append(f"{bin_name} CLI not on PATH (run invisible-doctor)")

    if not codex_sys:
        fails.append("prompts/codex_task.md is missing or empty")
    if not claude_sys:
        fails.append("prompts/claude_review.md is missing or empty")

    if not feature.exists():
        fails.append(f"feature worktree missing at {feature}")
    else:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(feature), capture_output=True, text=True, check=False,
        )
        branch = r.stdout.strip()
        if not branch or branch == "HEAD":
            fails.append(f"feature worktree is detached (no branch); "
                         f"orchestrator commits would have no branch to land on")

        # Uncommitted work is dangerous — codex's commit would sweep it up.
        # Ignore orchestrator-managed artifacts that invisible-new writes
        # (task.md) and the orchestrator itself writes (the checkpoint).
        IGNORED = {"task.md", ".invisible-checkpoint.json"}
        d = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(feature), capture_output=True, text=True, check=False,
        )
        offending = [ln for ln in d.stdout.splitlines() if ln[3:].strip() not in IGNORED]
        if offending:
            files = [ln[3:] for ln in offending[:5]]
            more = "" if len(offending) <= 5 else f" (+{len(offending) - 5} more)"
            fails.append(
                f"feature worktree has uncommitted changes — commit or stash "
                f"first. Files: {', '.join(files)}{more}"
            )

    if not review.exists():
        fails.append(f"review worktree missing at {review}")

    return fails


def run_loop(*, project: str, task: str, project_notion_id: str | None,
             max_iters: int, continuous: bool, resume: bool) -> int:
    log = setup_logging()
    load_env()

    proj_root = home() / "worktrees" / project
    feature = proj_root / "feature"; review = proj_root / "review"
    research = proj_root / "research"
    if not feature.exists() or not review.exists():
        log.error("worktrees missing for %s; run invisible-new first", project)
        return 1

    codex_sys  = read_prompt("codex_task.md")
    claude_sys = read_prompt("claude_review.md")

    fails = preflight(project, feature, review, codex_sys, claude_sys)
    if fails:
        log.error("pre-flight failed for %s:", project)
        for f in fails:
            log.error("  ✗ %s", f)
        telegram.notify(
            f"❌ `{project}` pre-flight failed:\n" +
            "\n".join(f"  - {f}" for f in fails),
            level="error", source="invisible-orchestrator",
        )
        return 5

    research_blob = read_research_notes(research)
    if research_blob:
        log.info("research notes loaded (%d chars from research/)", len(research_blob))

    state = checkpoint.load(feature) if resume else None
    vault = markdown_vault.writer()
    if state is None:
        state = checkpoint.new(project, task, max_iters, project_notion_id)
        checkpoint.save(feature, state)
        log.info("new orchestrator run — project=%s, max_iters=%d, continuous=%s",
                 project, max_iters, continuous)
        telegram.notify(f"Starting orchestrator on `{project}`: {task[:200]}",
                        level="info", source="invisible-orchestrator")
        # Seed Logseq vault: client+project notes, run note. Run ID is
        # deterministic from project + started_at, so subsequent iter
        # writes can wikilink back to it. Stored on state for resumption.
        state["vault_run_id"] = vault.write_run(
            project=project, started_iso=state["started_at"], task=task,
        )
    else:
        log.info("resuming run — iter %d/%d, last verdict=%s, host=%s",
                 state["iteration"], state.get("max_iters"),
                 state["last_verdict"], state.get("host"))
        telegram.notify(
            f"Resuming `{project}` from iter {state['iteration']} on this host.",
            level="info", source="invisible-orchestrator",
        )
        task = state.get("task") or task
        # CLI is authoritative for operational settings on resume.
        # If the operator passes --max-iters higher than what's stored, they're
        # extending the budget; lower means they want a tighter cap.
        state["max_iters"] = max_iters

    hard_cap = 999 if continuous else max_iters

    while state["iteration"] < hard_cap:
        if _STOP_REQUESTED:
            log.info("stop requested — exiting cleanly after %d iterations",
                     state["iteration"])
            telegram.notify(
                f"🛑 `{project}` stopped by operator at iter {state['iteration']}.",
                level="warn", source="invisible-orchestrator",
            )
            checkpoint.save(feature, state)
            return 0
        state["iteration"] += 1
        log.info("=== iteration %d / %s ===",
                 state["iteration"], "∞" if continuous else hard_cap)

        maybe_compress(state, codex_sys, claude_sys, task, log)
        checkpoint.save(feature, state)

        # Research notes only get attached on the first turn — once codex has
        # seen them they're in the commit history / its memory of the task,
        # and re-sending costs tokens for no signal gain.
        research_section = ""
        if research_blob and state["iteration"] == 1 and not state["feedback_history"]:
            research_section = (
                "\n\nBACKGROUND RESEARCH (from the research/ worktree — read for "
                "context; do not modify these files):\n\n" + research_blob + "\n"
            )

        feedback_blob = ""
        if state["feedback_history"]:
            feedback_blob = (
                "\n\nPREVIOUS REVIEW FEEDBACK "
                "(address every MUST FIX; SUGGESTIONS are nice-to-have):\n\n"
            )
            for i, entry in enumerate(state["feedback_history"], start=1):
                feedback_blob += f"### Iter {i}\n{entry}\n\n"
        codex_input = task + research_section + feedback_blob

        # ── Codex ──
        cr = run_codex_with_retries(codex_input, feature, codex_sys, log)
        if not cr.ok:
            notion.log_review(project_id=project_notion_id,
                              iteration=state["iteration"], agent="Codex",
                              verdict="Blocked", summary="codex failed after retries",
                              body_md=f"```\n{cr.stderr[-3000:]}\n```")
            checkpoint.save(feature, state)
            return 1

        git_commit_all(feature, f"iter {state['iteration']}: codex pass")
        sha = git_sha(feature)
        diff = git_diff(feature, "HEAD~1")
        state["last_sha"] = sha

        notion.log_review(project_id=project_notion_id, iteration=state["iteration"],
                          agent="Codex", verdict="Comment",
                          summary=f"codex committed {sha}",
                          body_md=f"### Codex output\n\n```\n{cr.stdout[:6000]}\n```",
                          diff_sha=sha)

        # ── Claude ──
        sync_review_worktree(review, sha, log)
        rr = run_claude_with_retries(diff, task, review, claude_sys, log)
        if not rr.parsed:
            notion.log_review(project_id=project_notion_id,
                              iteration=state["iteration"], agent="Claude",
                              verdict="Blocked", summary="claude unparseable",
                              body_md=f"```\n{rr.stdout[:3000]}\n```", diff_sha=sha)
            checkpoint.save(feature, state)
            return 1

        verdict = rr.parsed.get("verdict", "changes")
        summary = rr.parsed.get("summary", "")
        issues = rr.parsed.get("issues", []) or []
        sugg = rr.parsed.get("suggestions", []) or []
        body_md = rr.parsed.get("body_md", "") or summary

        # Accumulate claude usage telemetry. (Codex doesn't surface tokens.)
        if rr.usage:
            state.setdefault("usage_total", {
                "input_tokens": 0, "output_tokens": 0,
                "cache_read_input_tokens": 0, "cost_usd": 0.0,
            })
            for k in ("input_tokens", "output_tokens", "cache_read_input_tokens"):
                state["usage_total"][k] = state["usage_total"].get(k, 0) + rr.usage.get(k, 0)
            state["usage_total"]["cost_usd"] = (
                state["usage_total"].get("cost_usd", 0.0) + rr.usage.get("cost_usd", 0.0)
            )
            state.setdefault("usage_per_iter", []).append({
                "iter": state["iteration"], **rr.usage,
            })
            log.info("claude usage: %s in / %s out / $%.4f (cumulative $%.4f)",
                     rr.usage.get("input_tokens"), rr.usage.get("output_tokens"),
                     rr.usage.get("cost_usd"), state["usage_total"]["cost_usd"])

        verdict_map = {"approve": "Approved", "changes": "Changes requested", "block": "Blocked"}
        notion.log_review(project_id=project_notion_id, iteration=state["iteration"],
                          agent="Claude", verdict=verdict_map.get(verdict, "Comment"),
                          summary=summary, body_md=body_md, diff_sha=sha)

        # Mirror review to Logseq vault for the graph view. Fire-and-forget;
        # vault writer no-ops when $INVISIBLE_VAULT is unset.
        vault.write_review(
            run_id=state.get("vault_run_id", ""), project=project,
            iter_n=state["iteration"], verdict=verdict, summary=summary,
            body_md=body_md, sha=sha,
            cost_usd=(rr.usage or {}).get("cost_usd", 0.0),
            input_tokens=(rr.usage or {}).get("input_tokens", 0),
            output_tokens=(rr.usage or {}).get("output_tokens", 0),
        )

        state["last_verdict"] = verdict
        state["last_summary"] = summary

        if verdict == "approve":
            checkpoint.save(feature, state)
            log.info("APPROVED at iter %d (sha=%s)", state["iteration"], sha)
            telegram.notify(
                f"✅ `{project}` approved at iter {state['iteration']} "
                f"(sha {sha}).\n\n{summary}",
                level="info", source="invisible-orchestrator",
            )
            # Finalize the run note with the approve verdict
            vault.finalize_run(
                run_id=state.get("vault_run_id", ""), project=project,
                verdict="approve", iterations=state["iteration"],
                last_sha=sha, summary=summary,
                cost_usd=(state.get("usage_total") or {}).get("cost_usd", 0.0),
            )
            print(f"\n✅ approved at iter {state['iteration']}, sha={sha}\n{summary}")
            return 0

        # Preserve the issues-vs-suggestions split so codex sees which are
        # must-fix vs nice-to-have on the next pass. Stored as a structured
        # markdown string (rather than a dict) so old checkpoints keep loading.
        parts: list[str] = []
        if issues:
            parts.append("MUST FIX:\n" + "\n".join(f"- {x}" for x in issues))
        if sugg:
            parts.append("SUGGESTIONS:\n" + "\n".join(f"- {x}" for x in sugg))
        state["feedback_history"].append(
            "\n\n".join(parts) if parts else (summary or "(no specific feedback)")
        )
        checkpoint.save(feature, state)

    log.warning("hit hard cap (%d) without approval", hard_cap)
    telegram.notify(
        f"⚠️  `{project}` hit {hard_cap} iterations without approval. "
        f"Last verdict: {state['last_verdict']}.",
        level="warn", source="invisible-orchestrator",
    )
    vault.finalize_run(
        run_id=state.get("vault_run_id", ""), project=project,
        verdict=state.get("last_verdict") or "cap",
        iterations=state["iteration"],
        last_sha=state.get("last_sha", ""),
        summary=f"Hit iteration cap ({hard_cap}) without approval. "
                f"Last summary: {state.get('last_summary','')}",
        cost_usd=(state.get("usage_total") or {}).get("cost_usd", 0.0),
    )
    print(f"\n⚠️  hit cap; last sha={state['last_sha']}, last verdict={state['last_verdict']}")
    return 0


def dry_run(*, project: str, task: str) -> int:
    """Print what iter 1 would send to codex — system prompt, task, research
    blob. No subprocess calls, no commits, no Notion writes."""
    proj_root = home() / "worktrees" / project
    feature = proj_root / "feature"
    research = proj_root / "research"
    codex_sys = read_prompt("codex_task.md")
    claude_sys = read_prompt("claude_review.md")

    print("=" * 72)
    print(f"  DRY-RUN — invisible-review {project}")
    print("=" * 72)

    fails = preflight(project, feature, proj_root / "review", codex_sys, claude_sys)
    print(f"\n[preflight] {'PASS' if not fails else 'FAIL'}")
    for f in fails:
        print(f"  ✗ {f}")

    research_blob = read_research_notes(research)
    feedback_blob = ""  # iter 1 has no prior feedback

    print(f"\n[system prompt — {len(codex_sys):,} chars from prompts/codex_task.md]")
    print(codex_sys.rstrip())

    print(f"\n[user task — {len(task):,} chars]")
    print(task.rstrip())

    if research_blob:
        print(f"\n[research blob — {len(research_blob):,} chars, "
              "attached to iter 1 only]")
        print(research_blob[:2000] + ("\n... [snipped]" if len(research_blob) > 2000 else ""))
    else:
        print("\n[research blob] (empty — no *.md files in research/)")

    full_prompt_size = len(codex_sys) + len(task) + len(research_blob) + len(feedback_blob)
    approx_tokens = full_prompt_size // 4
    print(f"\n[total iter-1 prompt size] {full_prompt_size:,} chars "
          f"(~{approx_tokens:,} tokens)")
    print(f"[claude review prompt cap] {os.environ.get('INVISIBLE_REVIEW_DIFF_CAP', '60000')} chars on the diff")
    return 0 if not fails else 1


def _stop_running(project: str) -> int:
    """Send SIGTERM to the orchestrator named in the pidfile. Returns 0 if
    a signal was sent (or no run was active), 1 on error."""
    pid = _read_pidfile(project)
    if pid is None:
        print(f"[stop] no pidfile for {project} (not running)")
        return 0
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        print(f"[stop] stale pidfile for {project} (pid {pid} dead); cleaning up")
        _clear_pidfile(project)
        return 0
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"[stop] SIGTERM sent to pid {pid} for {project}")
        return 0
    except OSError as e:
        print(f"[stop] failed to signal pid {pid}: {e}", file=sys.stderr)
        return 1


def main() -> int:
    ap = argparse.ArgumentParser(prog="invisible-review")
    ap.add_argument("project")
    ap.add_argument("--task", help="defaults to feature/task.md")
    # default=None so we can distinguish "user passed --max-iters" from
    # "user wants the configured default". Resolved below in this order:
    #   1. CLI flag, if given
    #   2. [[projects]].<project>.max_iters
    #   3. [orchestrator].default_max_iters
    #   4. hardcoded fallback 4
    ap.add_argument("--max-iters", type=int, default=None)
    ap.add_argument("--continuous", action="store_true",
                    help="ignore --max-iters; loop until approval or operator stop")
    ap.add_argument("--resume", action="store_true",
                    help="resume from .invisible-checkpoint.json in feature worktree")
    ap.add_argument("--stop", action="store_true",
                    help="signal the running orchestrator for <project> to exit cleanly")
    ap.add_argument("--force", action="store_true",
                    help="start even if a pidfile says another run is active")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the codex prompt that iter 1 would send, then exit "
                         "(no API calls, no commits)")
    args = ap.parse_args()

    if args.stop:
        return _stop_running(args.project)

    load_env()
    if args.dry_run:
        task_dr = args.task
        if not task_dr:
            tf = home() / "worktrees" / args.project / "feature" / "task.md"
            if tf.exists():
                task_dr = tf.read_text()
        return dry_run(project=args.project, task=task_dr or "")


    cfg = load_toml()
    proj = next((p for p in cfg.get("projects", []) if p.get("name") == args.project), {})
    project_notion_id = proj.get("notion_id")

    max_iters = (
        args.max_iters
        if args.max_iters is not None
        else proj.get("max_iters")
        or (cfg.get("orchestrator") or {}).get("default_max_iters")
        or 4
    )

    task = args.task
    if not task and not args.resume:
        tf = home() / "worktrees" / args.project / "feature" / "task.md"
        if tf.exists():
            task = tf.read_text()
        else:
            print("--task required (or --resume, or create feature/task.md)",
                  file=sys.stderr)
            return 2

    if _is_running(args.project) and not args.force:
        pid = _read_pidfile(args.project)
        print(f"[orchestrator] {args.project} already running as pid {pid}. "
              f"Use --force to start anyway, or --stop to halt it.",
              file=sys.stderr)
        return 4

    # SIGTERM = clean stop (from invisible-review --stop or `kill <pid>`).
    # KeyboardInterrupt still works for Ctrl-C; SIGTERM path saves state.
    signal.signal(signal.SIGTERM, _handle_term)
    _write_pidfile(args.project)

    try:
        return run_loop(project=args.project, task=task or "",
                        project_notion_id=project_notion_id,
                        max_iters=max_iters,
                        continuous=args.continuous, resume=args.resume)
    except KeyboardInterrupt:
        telegram.notify(f"Orchestrator on `{args.project}` interrupted by operator.",
                        level="warn", source="invisible-orchestrator")
        return 130
    except Exception as e:
        telegram.notify_error(e, source="invisible-orchestrator")
        traceback.print_exc()
        return 1
    finally:
        _clear_pidfile(args.project)


if __name__ == "__main__":
    raise SystemExit(main())
