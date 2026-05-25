"""Logseq-compatible markdown vault writer.

Logseq treats a directory of markdown files as a knowledge graph. Each file
is a page; wikilinks ([[Page]]) are edges; YAML frontmatter is queryable
metadata; tags drive graph-view coloring.

This module writes one markdown file per "entity" — client, project, run,
review iteration, GSD session, daily standup — with frontmatter and
wikilinks. Open the same directory in Logseq and the graph view fills in
automatically.

Logseq namespace convention used here:
    file:   pages/projects___vbk.md
    page:   projects/vbk
    link:   [[projects/vbk]]
The `___` (three underscores) in the filename becomes `/` in the page
name. Logseq groups namespaces in the graph automatically.

Writer is a no-op when $INVISIBLE_VAULT is unset, so this is safe to call
from every hook unconditionally.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


def _log(msg: str) -> None:
    sys.stderr.write(f"[vault] {msg}\n")


def vault_path() -> Path | None:
    """The configured vault root, or None if not set."""
    v = os.environ.get("INVISIBLE_VAULT", "").strip()
    if not v:
        return None
    return Path(os.path.expanduser(v))


def _slug(s: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "").lower()).strip("-")
    return (s or "untitled")[:maxlen]


def _filename(*parts: str) -> str:
    """Build a Logseq filename from namespace parts. `('projects', 'vbk')`
    becomes `projects___vbk.md`."""
    cleaned = [p.replace("/", "-").replace("___", "-") for p in parts if p]
    return "___".join(cleaned) + ".md"


def _pagename(*parts: str) -> str:
    """Logseq page name = parts joined by '/'. Used inside wikilinks."""
    return "/".join(p for p in parts if p)


def _wikilink(*parts: str) -> str:
    return f"[[{_pagename(*parts)}]]"


def _yaml_scalar(v: Any) -> str:
    """Conservatively format a scalar value for YAML frontmatter.
    Strings get JSON-quoted (a JSON-quoted string is valid YAML).
    Numbers/bools pass through. None becomes empty."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    # If it's a plain alphanumeric token, no quoting needed.
    if re.fullmatch(r"[A-Za-z0-9_\-./:+]+", s):
        return s
    return json.dumps(s, ensure_ascii=False)


def _frontmatter(props: dict[str, Any]) -> str:
    """Build a YAML frontmatter block. Skips keys whose value is None or
    empty string."""
    lines = ["---"]
    for k, v in props.items():
        if v is None or v == "":
            continue
        if isinstance(v, list):
            if not v:
                continue
            joined = ", ".join(_yaml_scalar(x) for x in v)
            lines.append(f"{k}: [{joined}]")
        else:
            lines.append(f"{k}: {_yaml_scalar(v)}")
    lines.append("---")
    lines.append("")  # blank line after frontmatter
    return "\n".join(lines)


def _write_atomic(path: Path, body: str) -> None:
    """Write `body` to `path` via a tmp + rename so concurrent reads from
    Logseq never see a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(body)
    tmp.replace(path)


# ── Public API ──────────────────────────────────────────────────────────

class VaultWriter:
    """One per process. All methods are best-effort: errors are logged and
    swallowed. Caller never has to wrap in try/except."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or vault_path()
        self.enabled = self.root is not None
        if self.enabled:
            try:
                (self.root / "pages").mkdir(parents=True, exist_ok=True)
            except OSError as e:
                _log(f"vault root not writable ({self.root}): {e}")
                self.enabled = False

    # ── primitives ──
    def _write_page(self, path_parts: tuple[str, ...], front: dict[str, Any],
                    body: str) -> Path | None:
        if not self.enabled:
            return None
        try:
            p = self.root / "pages" / _filename(*path_parts)  # type: ignore[union-attr]
            content = _frontmatter(front) + body.rstrip() + "\n"
            _write_atomic(p, content)
            return p
        except OSError as e:
            _log(f"write {path_parts} failed: {e}")
            return None

    # ── seed entities (idempotent ensure_*) ──
    def ensure_client(self, name: str) -> None:
        if not self.enabled:
            return
        path = self.root / "pages" / _filename("clients", _slug(name))  # type: ignore[union-attr]
        if path.exists():
            return
        front = {"type": "client", "name": name,
                 "tags": ["client"]}
        body = f"# {name}\n\nClient.\n\n#client\n"
        self._write_page(("clients", _slug(name)), front, body)

    def ensure_project(self, project: str, client: str = "",
                       repo_path: str = "") -> None:
        if not self.enabled:
            return
        path = self.root / "pages" / _filename("projects", _slug(project))  # type: ignore[union-attr]
        if path.exists():
            return  # don't clobber: project notes may have user edits
        if client:
            self.ensure_client(client)
        front = {
            "type": "project",
            "name": project,
            "client": client or None,
            "repo_path": repo_path or None,
            "tags": ["project", "project/active"],
        }
        body_lines = [f"# {project}", ""]
        if client:
            body_lines.append(f"Client: {_wikilink('clients', _slug(client))}")
        if repo_path:
            body_lines.append(f"Repo: `{repo_path}`")
        body_lines += ["", "#project", ""]
        self._write_page(("projects", _slug(project)), front,
                         "\n".join(body_lines))

    # ── one-off events ──
    def write_run(self, *, project: str, started_iso: str, task: str,
                  client: str = "") -> str:
        """Create (or update if it exists) a run note. Returns the run id
        so iterations can wikilink back to it."""
        run_id = f"{started_iso[:10]}-{_slug(project)}-{_slug(task, maxlen=30)}"
        if not self.enabled:
            return run_id
        self.ensure_project(project, client)
        front = {
            "type": "run",
            "project": project,
            "task": task[:200],
            "started": started_iso,
            "tags": ["run", "run/in-progress"],
        }
        body = (
            f"# Run · {project}\n\n"
            f"Project: {_wikilink('projects', _slug(project))}\n"
            f"Started: {started_iso}\n\n"
            f"## Task\n\n{task.strip()}\n\n"
            f"## Iterations\n\n"
            f"<!-- iterations link here automatically via backlinks -->\n\n"
            f"#run\n"
        )
        self._write_page(("runs", run_id), front, body)
        return run_id

    def finalize_run(self, *, run_id: str, project: str, verdict: str,
                     iterations: int, last_sha: str, summary: str,
                     cost_usd: float) -> None:
        if not self.enabled:
            return
        verdict_tag = f"run/{verdict or 'unknown'}"
        front = {
            "type": "run",
            "project": project,
            "verdict": verdict,
            "iterations": iterations,
            "last_sha": last_sha,
            "cost_usd": round(cost_usd, 4),
            "tags": ["run", verdict_tag],
        }
        body = (
            f"# Run · {project} · {verdict}\n\n"
            f"Project: {_wikilink('projects', _slug(project))}\n"
            f"Iterations: {iterations}\n"
            f"Last SHA: `{last_sha}`\n"
            f"Cost: ${cost_usd:.4f}\n\n"
            f"## Outcome\n\n{(summary or '').strip()}\n\n"
            f"#run #{verdict_tag}\n"
        )
        self._write_page(("runs", run_id), front, body)

    def write_review(self, *, run_id: str, project: str, iter_n: int,
                     verdict: str, summary: str, body_md: str,
                     sha: str, agent: str = "Claude",
                     cost_usd: float = 0.0, input_tokens: int = 0,
                     output_tokens: int = 0) -> None:
        if not self.enabled:
            return
        # Page name like  reviews/2026-05-20-vbk-iter-2
        today = dt.date.today().isoformat()
        slug_proj = _slug(project)
        page_parts = ("reviews", f"{today}-{slug_proj}-iter-{iter_n}")
        prev_link = ""
        if iter_n > 1:
            prev_link = _wikilink("reviews",
                                  f"{today}-{slug_proj}-iter-{iter_n-1}")
        verdict_tag = f"review/{verdict or 'unknown'}"
        front = {
            "type": "review",
            "project": project,
            "iter": iter_n,
            "verdict": verdict,
            "agent": agent,
            "sha": sha,
            "cost_usd": round(float(cost_usd), 4),
            "input_tokens": int(input_tokens or 0),
            "output_tokens": int(output_tokens or 0),
            "created": dt.datetime.now(dt.timezone.utc).isoformat(),
            "tags": ["review", verdict_tag, f"review/agent/{agent.lower()}"],
        }
        body = (
            f"# {project} · iter {iter_n} · {verdict}\n\n"
            f"Project: {_wikilink('projects', slug_proj)}  ·  "
            f"Run: {_wikilink('runs', run_id)}\n"
        )
        if prev_link:
            body += f"Previous: {prev_link}\n"
        body += (
            f"\n## Summary\n\n{(summary or '').strip()}\n\n"
            f"## Body\n\n{(body_md or '').strip()}\n\n"
            f"#review #{verdict_tag}\n"
        )
        self._write_page(page_parts, front, body)

    def write_session(self, *, project: str, task: str, started_iso: str,
                      duration_min: int, outcome: str, notes: str,
                      client: str = "") -> None:
        if not self.enabled:
            return
        self.ensure_project(project, client)
        # 2026-05-20-1430-vbk
        when = dt.datetime.fromisoformat(started_iso.replace("Z", "+00:00"))
        stamp = when.strftime("%Y-%m-%d-%H%M")
        page_parts = ("gsd-sessions", f"{stamp}-{_slug(project)}")
        outcome_tag = f"session/{(outcome or 'unknown').lower().replace(' ', '-')}"
        front = {
            "type": "gsd-session",
            "project": project,
            "task": task[:200],
            "started": started_iso,
            "duration_min": duration_min,
            "outcome": outcome,
            "tags": ["gsd-session", outcome_tag],
        }
        body = (
            f"# GSD · {project} · {duration_min}m · {outcome}\n\n"
            f"Project: {_wikilink('projects', _slug(project))}\n"
            f"Started: {started_iso}\n"
            f"Duration: {duration_min} min\n"
            f"Outcome: **{outcome}**\n\n"
            f"## Task\n\n{task.strip()}\n\n"
            f"## Notes\n\n{(notes or '').strip()}\n\n"
            f"#gsd-session #{outcome_tag}\n"
        )
        self._write_page(page_parts, front, body)

    def write_standup(self, *, date_str: str, yesterday: str, today: str,
                      blockers: str, project_names: list[str]) -> None:
        if not self.enabled:
            return
        proj_links = " · ".join(
            _wikilink("projects", _slug(p)) for p in project_names
        ) or "_(none)_"
        front = {
            "type": "standup",
            "date": date_str,
            "active_projects": project_names,
            "tags": ["standup"],
        }
        body = (
            f"# Standup · {date_str}\n\n"
            f"Active: {proj_links}\n\n"
            f"## Yesterday\n\n{yesterday.strip() or '_(nothing logged)_'}\n\n"
            f"## Today\n\n{today.strip() or '_(no plan set)_'}\n\n"
            f"## Blockers\n\n{blockers.strip() or '_(none)_'}\n\n"
            f"#standup\n"
        )
        self._write_page(("standups", date_str), front, body)

    def write_home_if_missing(self) -> None:
        if not self.enabled:
            return
        path = self.root / "pages" / "Home.md"  # type: ignore[union-attr]
        if path.exists():
            return
        body = (
            "---\n"
            "type: home\n"
            "tags: [home]\n"
            "---\n\n"
            "# Invisible\n\n"
            "Open the **Graph view** (left sidebar → graph icon) to see "
            "projects, runs, reviews and sessions wired together.\n\n"
            "## Hubs\n\n"
            "- Filter by tag in graph view to color-group:\n"
            "    - `#project` — projects you've scaffolded\n"
            "    - `#run/approve` / `#run/changes` / `#run/block` — orchestrator outcomes\n"
            "    - `#review` — every claude review iteration\n"
            "    - `#gsd-session/shipped` / `#gsd-session/aborted` — focus blocks\n"
            "    - `#standup` — daily briefs\n\n"
            "## Logseq tips\n\n"
            "- Set `Settings → Editor → Preferred format: Markdown` if you want flat markdown rather than outliner mode\n"
            "- Right-click a node in graph view → set color per group\n"
            "- Open `Local Graph` from any page to see just that page's neighborhood\n"
        )
        try:
            _write_atomic(path, body)
        except OSError as e:
            _log(f"home page write failed: {e}")


# Module-level convenience: a default writer that reads env each call. The
# hook sites use this so they don't need to thread a config around.
def writer() -> VaultWriter:
    return VaultWriter()
