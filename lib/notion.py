"""Thin Notion API client for invisible.

Reads NOTION_TOKEN and the database IDs from environment variables. All writes
are idempotent-friendly (you pass an explicit external_id-style title when you
want dedup). Errors are non-fatal: they're logged to stderr and the function
returns None — invisible scripts should never crash because Notion blipped.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any

NOTION_VERSION = "2022-06-28"
BASE = "https://api.notion.com/v1"


def _token() -> str | None:
    return os.environ.get("NOTION_TOKEN")


def _db(name: str) -> str | None:
    return os.environ.get(f"NOTION_DB_{name.upper()}")


def _request(method: str, path: str, body: dict | None = None) -> dict | None:
    tok = _token()
    if not tok:
        print("[notion] NOTION_TOKEN unset — skipping write", file=sys.stderr)
        return None
    req = urllib.request.Request(
        f"{BASE}{path}",
        method=method,
        headers={
            "Authorization": f"Bearer {tok}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
        data=json.dumps(body).encode() if body else None,
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(1.5 ** attempt)
                continue
            print(f"[notion] HTTP {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"[notion] {e}", file=sys.stderr)
            return None
    return None


# ---------- property builders ----------

def _title(text: str) -> dict:
    return {"title": [{"type": "text", "text": {"content": text[:1900]}}]}


def _rich(text: str) -> dict:
    return {"rich_text": [{"type": "text", "text": {"content": text[:1900]}}]}


def _select(name: str) -> dict:
    return {"select": {"name": name}}


def _number(n: float | int) -> dict:
    return {"number": n}


def _date(iso: str) -> dict:
    return {"date": {"start": iso}}


def _relation(ids: list[str]) -> dict:
    return {"relation": [{"id": i} for i in ids]}


def _markdown_blocks(md: str) -> list[dict]:
    """Tiny markdown → Notion-blocks converter. Handles headings, code, and paragraphs."""
    blocks: list[dict] = []
    in_code = False
    code_buf: list[str] = []
    code_lang = "plain text"
    for line in md.splitlines():
        if line.startswith("```"):
            if in_code:
                blocks.append({
                    "object": "block", "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": "\n".join(code_buf)[:1900]}}],
                        "language": code_lang,
                    }
                })
                code_buf, in_code, code_lang = [], False, "plain text"
            else:
                in_code = True
                code_lang = line[3:].strip() or "plain text"
            continue
        if in_code:
            code_buf.append(line); continue
        if line.startswith("### "):
            blocks.append({"object": "block", "type": "heading_3",
                           "heading_3": {"rich_text": [{"type": "text", "text": {"content": line[4:][:1900]}}]}})
        elif line.startswith("## "):
            blocks.append({"object": "block", "type": "heading_2",
                           "heading_2": {"rich_text": [{"type": "text", "text": {"content": line[3:][:1900]}}]}})
        elif line.startswith("# "):
            blocks.append({"object": "block", "type": "heading_1",
                           "heading_1": {"rich_text": [{"type": "text", "text": {"content": line[2:][:1900]}}]}})
        elif line.strip():
            blocks.append({"object": "block", "type": "paragraph",
                           "paragraph": {"rich_text": [{"type": "text", "text": {"content": line[:1900]}}]}})
    return blocks


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- public API ----------

def log_review(*, project_id: str | None, iteration: int, agent: str,
               verdict: str, summary: str, body_md: str,
               diff_sha: str = "",
               usage: dict | None = None,
               started_at: str | None = None,
               completed_at: str | None = None) -> dict | None:
    db = _db("reviews")
    if not db:
        return None
    title = f"iter {iteration} · {agent} · {verdict}"
    props = {
        "Title": _title(title),
        "Iteration": _number(iteration),
        "Agent": _select(agent),
        "Verdict": _select(verdict),
        "Summary": _rich(summary),
        "Diff SHA": _rich(diff_sha),
        "Created": _date(now_iso()),
    }
    if project_id:
        props["Project"] = _relation([project_id])
    if usage:
        if usage.get("input_tokens") is not None:
            props["Input tokens"] = _number(int(usage["input_tokens"]))
        if usage.get("output_tokens") is not None:
            props["Output tokens"] = _number(int(usage["output_tokens"]))
        if usage.get("cache_read_input_tokens") is not None:
            props["Cache read tokens"] = _number(int(usage["cache_read_input_tokens"]))
        if usage.get("cache_creation_input_tokens") is not None:
            props["Cache creation tokens"] = _number(int(usage["cache_creation_input_tokens"]))
        if usage.get("cost_usd") is not None:
            props["Cost USD"] = _number(float(usage["cost_usd"]))
    if started_at:
        props["Started"] = _date(started_at)
    if completed_at:
        props["Completed"] = _date(completed_at)
    return _request("POST", "/pages", {
        "parent": {"database_id": db},
        "properties": props,
        "children": _markdown_blocks(body_md),
    })


def log_standup(*, date_str: str, yesterday: str, today: str,
                blockers: str, project_ids: list[str]) -> dict | None:
    db = _db("standups")
    if not db:
        return None
    return _request("POST", "/pages", {
        "parent": {"database_id": db},
        "properties": {
            "Date": _title(date_str),
            "Yesterday": _rich(yesterday),
            "Today": _rich(today),
            "Blockers": _rich(blockers),
            "Active projects": _relation(project_ids),
        },
    })


def log_health(*, target: str, status: str, disk_pct: float,
               cpu_load: float, details: str) -> dict | None:
    db = _db("health")
    if not db:
        return None
    return _request("POST", "/pages", {
        "parent": {"database_id": db},
        "properties": {
            "Timestamp": _title(now_iso()),
            "Target": _select(target),
            "Status": _select(status),
            "Disk %": _number(disk_pct),
            "CPU load": _number(cpu_load),
            "Details": _rich(details),
        },
    })


def log_gsd_start(*, project_id: str | None, project_name: str,
                  task: str, duration_min: int) -> dict | None:
    """Create a GSD session row in the GSDSessions DB. Returns the page so
    invisible-gsd can grab the page_id and update outcome later."""
    db = _db("gsd")
    if not db:
        return None
    props = {
        "Title": _title(f"{project_name} · {task[:60]} · {duration_min}m"),
        "Task": _rich(task),
        "Started": _date(now_iso()),
        "Duration": _number(duration_min),
        "Outcome": _select("In progress"),
    }
    if project_id:
        props["Project"] = _relation([project_id])
    return _request("POST", "/pages", {
        "parent": {"database_id": db},
        "properties": props,
    })


def update_gsd_outcome(*, page_id: str, outcome: str, notes: str) -> dict | None:
    if not page_id:
        return None
    return _request("PATCH", f"/pages/{page_id}", {
        "properties": {
            "Outcome": _select(outcome),
            "Notes": _rich(notes),
        }
    })


def find_or_create_client(name: str) -> str | None:
    """Look up a Client row by Name; create it if missing. Returns page id."""
    db = _db("clients")
    if not db:
        return None
    r = _request("POST", f"/databases/{db}/query", {
        "filter": {"property": "Name", "title": {"equals": name}},
        "page_size": 1,
    })
    hits = (r or {}).get("results", [])
    if hits:
        return hits[0]["id"]
    created = _request("POST", "/pages", {
        "parent": {"database_id": db},
        "properties": {
            "Name":   _title(name),
            "Status": _select("Active"),
        },
    })
    return (created or {}).get("id")


def find_or_create_project(name: str, *, repo_path: str = "",
                           client_name: str = "") -> str | None:
    """Look up a Project row by Name; create it if missing. Returns page id.
    If client_name is given, the row is linked to (and creates if needed) the
    Clients row of that name."""
    db = _db("projects")
    if not db:
        return None
    r = _request("POST", f"/databases/{db}/query", {
        "filter": {"property": "Name", "title": {"equals": name}},
        "page_size": 1,
    })
    hits = (r or {}).get("results", [])
    if hits:
        return hits[0]["id"]
    props = {
        "Name":      _title(name),
        "Status":    _select("Active"),
        "Repo path": _rich(repo_path),
        "Created":   _date(now_iso()),
    }
    if client_name:
        client_id = find_or_create_client(client_name)
        if client_id:
            props["Client"] = _relation([client_id])
    created = _request("POST", "/pages", {
        "parent": {"database_id": db},
        "properties": props,
    })
    return (created or {}).get("id")


def query_active_projects() -> list[dict]:
    db = _db("projects")
    if not db:
        return []
    r = _request("POST", f"/databases/{db}/query", {
        "filter": {"property": "Status", "select": {"equals": "Active"}}
    })
    return r.get("results", []) if r else []


def query_recent_gsd(hours: int = 36) -> list[dict]:
    """Recent GSDSessions rows, newest first. Default 36h so a morning
    standup catches yesterday's afternoon sessions even after a long sleep."""
    db = _db("gsd")
    if not db:
        return []
    r = _request("POST", f"/databases/{db}/query", {
        "sorts": [{"property": "Started", "direction": "descending"}],
        "page_size": 30,
    })
    return r.get("results", []) if r else []


def query_recent_reviews(hours: int = 24, *, project_id: str | None = None,
                         page_size: int = 50) -> list[dict]:
    """Recent Reviews rows, newest first. If project_id is given, filter to
    that project's relation."""
    db = _db("reviews")
    if not db:
        return []
    body: dict = {
        "sorts": [{"property": "Created", "direction": "descending"}],
        "page_size": min(max(page_size, 1), 100),
    }
    if project_id:
        body["filter"] = {
            "property": "Project",
            "relation": {"contains": project_id},
        }
    r = _request("POST", f"/databases/{db}/query", body)
    return r.get("results", []) if r else []


def query_calendar_db(database_id: str, date_from: str, date_to: str) -> list[dict]:
    """Query a Notion calendar database for events in [date_from, date_to].

    Used by lib/api/calendar.py to feed the Notion-source loader for the
    /api/v1/calendar endpoint. Returns the raw Notion `results[]` list (each
    element is a page object whose `properties` dict the caller flattens into
    the canonical event shape). The caller — not this helper — is responsible
    for mapping Notion property values into {id, title, start, end, color,
    source, project_id?}.

    Parameters
    ----------
    database_id : str
        The 32-char Notion database id. Treated as opaque; never logged.
        Empty string is the "no DB configured" signal — returns [] without
        calling the API.
    date_from : str
        Inclusive lower bound, ISO-8601 date (YYYY-MM-DD).
    date_to : str
        Inclusive upper bound, ISO-8601 date (YYYY-MM-DD).

    Returns
    -------
    list[dict]
        Notion page objects, or [] on any failure path (token unset, HTTP
        error, network timeout, JSON parse error). Never raises — mirrors
        `query_active_projects` / `query_recent_reviews` shape.

    Notes
    -----
    The filter hard-codes the property name "Date" because that is Notion's
    default for date-typed properties and matches the convention used by the
    rest of this module. Users whose calendar DB uses a different property
    name (e.g. "When", "Start") can fork this helper or override via a future
    `property_name` kwarg — not in scope for v1.

    Security
    --------
    Never prints the token (delegated to `_request`). Never prints the
    `database_id` in error paths — Notion DB ids leak collaboration scope and
    are mildly sensitive even though they are not credentials.
    """
    if not database_id:
        return []
    body = {
        "filter": {
            "property": "Date",
            "date": {"on_or_after": date_from, "on_or_before": date_to},
        },
        "page_size": 100,
    }
    r = _request("POST", f"/databases/{database_id}/query", body)
    return (r or {}).get("results", [])


def query_reviews_since(since_iso: str, *, project_id: str | None = None,
                        page_size: int = 100) -> list[dict]:
    """All Reviews rows created on or after since_iso, newest first.
    Paginates via start_cursor until has_more is False. If project_id is
    given, filters to that project's relation. Additive helper for the
    analytics aggregator (REQ-05)."""
    db = _db("reviews")
    if not db:
        return []
    page_size = min(max(page_size, 1), 100)
    date_filter = {"property": "Created", "date": {"on_or_after": since_iso}}
    if project_id:
        filter_clause = {
            "and": [
                date_filter,
                {"property": "Project", "relation": {"contains": project_id}},
            ]
        }
    else:
        filter_clause = date_filter
    body: dict = {
        "sorts": [{"property": "Created", "direction": "descending"}],
        "page_size": page_size,
        "filter": filter_clause,
    }
    results: list[dict] = []
    while True:
        r = _request("POST", f"/databases/{db}/query", body)
        if not r:
            break
        results.extend(r.get("results", []))
        if not r.get("has_more"):
            break
        next_cursor = r.get("next_cursor")
        if not next_cursor:
            break
        body["start_cursor"] = next_cursor
    return results
