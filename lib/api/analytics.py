"""Analytics aggregator for REQ-05.

Reads orchestrator review rows from Notion (via lib/notion.py) and rolls them
up into the JSON shape that frontend/pages/analytics.jsx consumes:

    {
      "totals":      { input_tokens, output_tokens, cache_read_tokens,
                       cost_usd, total_minutes },
      "by_project":  { <slug>: { input_tokens, output_tokens,
                                  cost_usd, minutes } },
      "top_tools":   [ { name, calls, total_tokens, color }, ... ],
      "top_actions": [ { name, tool, calls, tokens }, ... ],   # top 8
      "series":      { tokensByDay: { <slug>: [float, ...] },
                       timeByDay:   { <slug>: [float, ...] } },
    }

All token values are raw counts (the frontend handles unit conversion).
Time values: total_minutes in totals/by_project (minutes), timeByDay arrays
in hours-per-day. Series arrays are length == range_days, oldest first.

Notion review-row properties this module reads (set by lib/notion.py:log_review):
    Title, Iteration, Agent, Verdict, Summary, Diff SHA, Created,
    Project (relation, UUID), and the seven properties added by the
    INV-01 Task 0 human checkpoint: Input tokens, Output tokens,
    Cache read tokens, Cache creation tokens, Cost USD, Started, Completed.

Caching: in-process dict keyed by (range_days, project_slug_or_None).
TTL = CACHE_TTL_SECONDS = 30. The same key also caches the slug map so the
extra Notion call per cache miss is absorbed by the same TTL.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

# lib/ is on sys.path via bin/invisible-dashboard's bootstrap; import notion
# as a top-level module just like the dashboard does.
import notion  # noqa: E402


RANGE_DAYS_ALLOWED = {7, 14, 30}
CACHE_TTL_SECONDS = 30
PROJECT_ORDER = ("echo", "lumen", "drift", "atlas", "rune", "ferry")

# Tool palette colors mirror frontend/data.jsx mock:
#   LLMs (claude, codex)  -> #f5b343 (warm amber)
#   Datastores (Postgres, Redis, etc.) -> #5cc8ff (cyan)
#   APIs (GitHub, Slack, Stripe, etc.) -> #b794ff (violet)
_COLOR_LLM = "#f5b343"
_COLOR_DATASTORE = "#5cc8ff"
_COLOR_API = "#b794ff"

_DATASTORE_MARKERS = ("Postgres", "Redis", "S3", "MySQL", "SQLite")
_API_MARKERS = ("GitHub", "Slack", "Stripe", "Resend", "Linear")


# ---------- cache ----------

_CACHE: dict[tuple[int, str | None], tuple[float, dict]] = {}


def _cache_get(key: tuple[int, str | None]) -> dict | None:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    ts, payload = entry
    if time.monotonic() - ts > CACHE_TTL_SECONDS:
        return None
    return payload


def _cache_put(key: tuple[int, str | None], payload: dict) -> None:
    _CACHE[key] = (time.monotonic(), payload)


# ---------- Notion row extraction ----------

def _rt(props: dict, key: str) -> Any:
    """Pull a typed Notion property value. Mirrors fetch_recent_reviews in
    bin/invisible-dashboard. Returns '' / None / 0 sentinel by type."""
    p = props.get(key, {}) or {}
    t = p.get("type")
    if t == "title":
        return "".join(x.get("plain_text", "") for x in p.get("title", []))
    if t == "rich_text":
        return "".join(x.get("plain_text", "") for x in p.get("rich_text", []))
    if t == "select":
        return (p.get("select") or {}).get("name", "")
    if t == "number":
        return p.get("number")
    if t == "date":
        return (p.get("date") or {}).get("start")
    if t == "relation":
        return p.get("relation", [])
    return ""


def _name_to_slug(name: str) -> str:
    return (name or "").strip().lower().replace(" ", "-")


def _build_slug_map() -> dict[str, str]:
    """Map Notion project page UUID -> human-readable slug.

    Reads Status=Active projects from the Projects DB. Slug is derived from
    the Name title by lowercasing and replacing whitespace with hyphens, so
    a Notion project named "Echo" becomes slug "echo" and matches the
    frontend's PROJECT_ORDER allowlist."""
    pages = notion.query_active_projects()
    slug_map: dict[str, str] = {}
    for page in pages:
        uuid = page.get("id")
        if not uuid:
            continue
        props = page.get("properties", {}) or {}
        name = _rt(props, "Name")
        slug = _name_to_slug(name)
        if slug:
            slug_map[uuid] = slug
    return slug_map


def _extract_review(page: dict, slug_map: dict[str, str]) -> dict | None:
    """Normalize one Notion review-row page into the shape the aggregator
    needs. Returns None if essential fields (agent, created) are missing."""
    props = page.get("properties", {}) or {}
    agent = _rt(props, "Agent") or ""
    created = _rt(props, "Created") or ""
    if not agent or not created:
        return None

    rels = _rt(props, "Project") or []
    project_id: str | None = None
    if rels:
        uuid = (rels[0] or {}).get("id") if isinstance(rels[0], dict) else None
        if uuid:
            project_id = slug_map.get(uuid, uuid)  # fallback to raw UUID; frontend drops it

    def _n(k: str) -> int:
        v = _rt(props, k)
        return int(v) if isinstance(v, (int, float)) else 0

    return {
        "agent": agent,
        "project_id": project_id,
        "iteration": _n("Iteration"),
        "verdict": _rt(props, "Verdict") or "",
        "summary": _rt(props, "Summary") or "",
        "created": created,
        "started": _rt(props, "Started") or None,
        "completed": _rt(props, "Completed") or None,
        "input_tokens": _n("Input tokens"),
        "output_tokens": _n("Output tokens"),
        "cache_read_tokens": _n("Cache read tokens"),
        "cost_usd": float(_rt(props, "Cost USD") or 0.0),
    }


def _minutes_between(started: str | None, completed: str | None) -> float:
    if not started or not completed:
        return 0.0
    try:
        s = datetime.fromisoformat(started.replace("Z", "+00:00"))
        c = datetime.fromisoformat(completed.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    delta = (c - s).total_seconds() / 60.0
    return max(delta, 0.0)


def _classify_tool(agent: str, summary: str) -> tuple[str, str]:
    """Return (tool_name, color). LLMs are agent-named; non-LLM substring
    matches override and re-attribute. Best-effort — claude/codex stays the
    dominant tool for most reviews."""
    s = summary or ""
    for marker in _DATASTORE_MARKERS:
        if marker in s:
            return (marker, _COLOR_DATASTORE)
    for marker in _API_MARKERS:
        if marker in s:
            return (marker, _COLOR_API)
    return (agent or "unknown", _COLOR_LLM)


def _utc_day_index(iso_ts: str, oldest_day: datetime, range_days: int) -> int | None:
    """Convert an ISO timestamp into a 0-based day index from oldest_day.
    Returns None if outside the range."""
    if not iso_ts:
        return None
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta_days = (dt.date() - oldest_day.date()).days
    if 0 <= delta_days < range_days:
        return delta_days
    return None


# ---------- public API ----------

def get_analytics(range_days: int, project_id: str | None = None) -> dict:
    """Aggregate Notion review rows into the analytics payload.

    range_days: 7, 14, or 30.
    project_id: optional project slug (e.g. "echo"). When provided, the
                aggregator reverse-maps to the Notion UUID and filters the
                Notion query. by_project / series still contain only the
                matching project's data.
    """
    if range_days not in RANGE_DAYS_ALLOWED:
        raise ValueError(f"range_days must be one of {sorted(RANGE_DAYS_ALLOWED)}")

    cache_key = (range_days, project_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=range_days)
    oldest_day = now - timedelta(days=range_days - 1)

    slug_map = _build_slug_map()

    project_uuid: str | None = None
    if project_id:
        # Reverse-map slug -> first matching UUID.
        for uuid, slug in slug_map.items():
            if slug == project_id:
                project_uuid = uuid
                break
        # Unknown slug -> project_uuid stays None -> no filter passed -> we'll
        # filter client-side below so we don't bypass the user's intent.

    pages = notion.query_reviews_since(since.isoformat(), project_id=project_uuid)
    reviews: list[dict] = []
    for page in pages:
        review = _extract_review(page, slug_map)
        if review is None:
            continue
        if project_id and review["project_id"] != project_id:
            # Either the requested slug didn't resolve to a UUID, or the row
            # has no project relation. Drop it client-side to honor the filter.
            continue
        reviews.append(review)

    # ----- totals -----
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cost_usd": 0.0,
        "total_minutes": 0.0,
    }
    for r in reviews:
        totals["input_tokens"] += r["input_tokens"]
        totals["output_tokens"] += r["output_tokens"]
        totals["cache_read_tokens"] += r["cache_read_tokens"]
        totals["cost_usd"] += r["cost_usd"]
        totals["total_minutes"] += _minutes_between(r["started"], r["completed"])
    totals["cost_usd"] = round(totals["cost_usd"], 4)
    totals["total_minutes"] = round(totals["total_minutes"], 2)

    # ----- by_project -----
    by_project: dict[str, dict] = {}
    for r in reviews:
        slug = r["project_id"]
        if not slug:
            continue
        bucket = by_project.setdefault(slug, {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "minutes": 0.0,
        })
        bucket["input_tokens"] += r["input_tokens"]
        bucket["output_tokens"] += r["output_tokens"]
        bucket["cost_usd"] += r["cost_usd"]
        bucket["minutes"] += _minutes_between(r["started"], r["completed"])
    for bucket in by_project.values():
        bucket["cost_usd"] = round(bucket["cost_usd"], 4)
        bucket["minutes"] = round(bucket["minutes"], 2)

    # ----- top_tools -----
    tool_agg: dict[str, dict] = {}
    for r in reviews:
        tool, color = _classify_tool(r["agent"], r["summary"])
        bucket = tool_agg.setdefault(tool, {
            "name": tool,
            "calls": 0,
            "total_tokens": 0,
            "color": color,
        })
        bucket["calls"] += 1
        bucket["total_tokens"] += r["input_tokens"] + r["output_tokens"]
    top_tools = sorted(tool_agg.values(), key=lambda t: t["total_tokens"], reverse=True)

    # ----- top_actions -----
    action_agg: dict[tuple[str, str], dict] = {}
    for r in reviews:
        action_name = (r["summary"] or "(no summary)")[:60]
        tool = r["agent"] or "unknown"
        key = (action_name, tool)
        bucket = action_agg.setdefault(key, {
            "name": action_name,
            "tool": tool,
            "calls": 0,
            "tokens": 0,
        })
        bucket["calls"] += 1
        bucket["tokens"] += r["input_tokens"] + r["output_tokens"]
    top_actions = sorted(action_agg.values(), key=lambda a: a["tokens"], reverse=True)[:8]

    # ----- series -----
    tokens_by_day: dict[str, list[float]] = {}
    time_by_day: dict[str, list[float]] = {}
    for r in reviews:
        slug = r["project_id"]
        if not slug:
            continue
        day_idx = _utc_day_index(r["started"] or r["created"], oldest_day, range_days)
        if day_idx is None:
            continue
        toks = tokens_by_day.setdefault(slug, [0.0] * range_days)
        toks[day_idx] += float(r["input_tokens"] + r["output_tokens"])
        mins = _minutes_between(r["started"], r["completed"])
        hours = mins / 60.0
        secs = time_by_day.setdefault(slug, [0.0] * range_days)
        secs[day_idx] += hours
    for arr in tokens_by_day.values():
        for i in range(len(arr)):
            arr[i] = round(arr[i], 2)
    for arr in time_by_day.values():
        for i in range(len(arr)):
            arr[i] = round(arr[i], 3)

    payload = {
        "totals": totals,
        "by_project": by_project,
        "top_tools": top_tools,
        "top_actions": top_actions,
        "series": {
            "tokensByDay": tokens_by_day,
            "timeByDay": time_by_day,
        },
    }
    _cache_put(cache_key, payload)
    return payload


def handle_request(query_params: dict[str, list[str]]) -> tuple[int, dict]:
    """Dashboard route adapter. Parses query string, invokes get_analytics,
    maps exceptions to HTTP status codes."""
    try:
        raw_range = (query_params.get("range") or ["30d"])[0]
        if raw_range.endswith("d"):
            raw_range = raw_range[:-1]
        range_days = int(raw_range)
        project_id = (query_params.get("project") or [None])[0] or None
        if project_id == "all":
            project_id = None
        payload = get_analytics(range_days, project_id)
        return (200, payload)
    except ValueError as e:
        return (400, {"error": "invalid range, must be 7d|14d|30d", "message": str(e)})
    except Exception as e:  # noqa: BLE001 — daemon shouldn't crash on Notion blip
        print(f"[analytics] {type(e).__name__}: {e}", file=sys.stderr)
        return (500, {"error": "internal", "message": str(e)})
