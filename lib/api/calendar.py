"""Aggregate calendar events for GET /api/v1/calendar.

Pulls from up to three sources (priority order on dedupe collision):
  1. Notion calendar DB        — via lib/notion.query_calendar_db
  2. iCal URLs (https only)    — via stdlib urllib + a hand-rolled VEVENT parser
  3. ~/.invisible/events.json  — a tiny user-editable file

Wire shape (consumed by frontend/pages/calendar.jsx in Plan 01-02):

    GET /api/v1/calendar?from=YYYY-MM-DD&to=YYYY-MM-DD
    → HTTP 200, [{
        "id":         "<str — stable per (source, source_uid)>",
        "title":      "<str>",
        "start":      "<RFC3339 timestamp>",
        "end":        "<RFC3339 timestamp>",
        "color":      "<hex string, e.g. #5cc8ff>",
        "project_id": "<str, optional — frontend looks up DATA_SETS color>",
        "source":     "notion" | "ics" | "local"
      }, ...]

Bad/missing `from` or `to`:
    400 {"error": "bad_request", "hint": "from and to are required YYYY-MM-DD"}

No source configured:
    200 []

Unrecoverable internal error:
    500 {"error": "internal error"}    (no paths, no traceback in body or log)

Security notes
--------------

- **SSRF (T-01-01, T-01-02)**: `_safe_ics_url` enforces an https-only scheme
  allowlist, refuses empty hostnames, and resolves EVERY A/AAAA address via
  `socket.getaddrinfo(..., AF_UNSPEC)` — an attacker-controlled public DNS
  name that resolves to 127.0.0.1 / 10.0.0.0/8 / fe80::/10 / etc. is rejected
  before the request leaves the box. A custom `HTTPRedirectHandler` subclass
  turns any 3xx into an HTTPError so a public URL cannot redirect to a
  private one (the URL is checked once and never re-resolved).

- **Resource exhaustion (T-01-03)**: 10-second socket timeout plus a 1 MiB
  cap on body size (checked against `Content-Length` and also enforced
  mid-read for servers that lie about / omit `Content-Length`).

- **Path traversal (T-01-04)**: the local-events loader resolves the path
  and confirms `is_relative_to(config.home().resolve())` — symlinks pointing
  outside `~/.invisible/` are rejected and return [].

- **Information disclosure (T-01-05, T-01-07)**: every error-log uses only
  `type(exc).__name__`. Never the exception message, never the URL, never
  the filesystem path, never the Notion DB id. The HTTP error body is a
  generic `{"error": "internal error"}`. The Notion token never reaches
  this module — `lib/notion._request` owns the token.

- **Injection (T-01-08)**: SUMMARY values from iCal are kept as Python str
  and JSON-encoded; the React frontend renders them as text nodes (auto-
  escaped), so HTML / control-char content in an upstream calendar cannot
  reach the DOM verbatim. We do NOT use `dangerouslySetInnerHTML` anywhere.

- **Query-string injection (T-01-09)**: `from` / `to` are strict-parsed by
  `datetime.strptime(value, "%Y-%m-%d")`; on parse failure the response is
  a generic 400 that does not echo the malicious input.

- **Cache stampede (T-01-06)**: a module-level `threading.Lock` is held for
  the duration of any cache miss (single-flight). Concurrent requests for
  the same window block on the lock and then read the freshly-populated
  entry instead of all triggering parallel Notion/iCal fetches. Acceptable
  tradeoff for a personal-cockpit daemon (low qps); the alternative
  (per-key locks) is overkill at this scale.
"""

from __future__ import annotations

import datetime as _dt
import ipaddress
import json
import os
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import config
import notion


# ──────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────

CACHE_TTL_S: int = 60
ICS_FETCH_TIMEOUT_S: int = 10
ICS_MAX_BYTES: int = 1_048_576  # 1 MiB

# https only. http would let an attacker MITM the calendar feed; file:// /
# ftp:// / data:// / javascript:// would let them read local files or pop
# JS into a page that downloads the response. Keep this list tiny.
ALLOWED_ICS_SCHEMES: tuple[str, ...] = ("https",)

# RFC1918 + loopback + link-local (v4) + loopback + ULA + link-local (v6).
# Used by `_safe_ics_url` to reject any URL whose hostname resolves into a
# private address space — SSRF guard against `https://evil.example/` whose
# DNS A record returns 10.x or 127.0.0.1.
_PRIVATE_IP_NETS: tuple[ipaddress._BaseNetwork, ...] = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)

# Frontend default when an event has no project-anchored color. Matches the
# "neutral event" pill in the Calendar page mock.
_DEFAULT_COLOR: str = "#8aa9ff"
# Strict 6-digit hex pattern. Used to validate local events.json color
# fields before they reach the wire (and ultimately a React style attr).
_HEX_COLOR_RE: re.Pattern[str] = re.compile(r"^#[0-9a-fA-F]{6}$")


# ──────────────────────────────────────────────────────────────────────────
# Cache (single-flight under one global lock)
# ──────────────────────────────────────────────────────────────────────────
# Module-level — survives across requests, dies on daemon restart. The lock
# is held for the full duration of a cache miss (including all network
# I/O); concurrent requests for the same window block on the lock and then
# read the freshly-populated entry without re-fetching. Acceptable tradeoff
# at personal-cockpit concurrency (1-2 qps). At higher load this would
# become a bottleneck — switch to per-key locks (a dict of locks keyed on
# (date_from, date_to)) if/when the daemon needs to fan out.

_CACHE: dict[tuple[str, str], tuple[float, list[dict]]] = {}
_CACHE_LOCK = threading.Lock()


# ──────────────────────────────────────────────────────────────────────────
# SSRF guard
# ──────────────────────────────────────────────────────────────────────────


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """OpenerDirector handler that refuses to follow redirects.

    SSRF mitigation T-01-02: a public URL passing `_safe_ics_url` could
    nonetheless 302 to `http://10.0.0.1/secret`. urllib's default behavior
    is to chase the redirect, and the second request is NOT re-checked by
    `_safe_ics_url`. By raising HTTPError on every 3xx we keep all requests
    on the single, already-validated URL.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        # Raise rather than return None — None would silently abort and the
        # caller would see a 200 with an empty body. We want a hard fail so
        # the iCal loader returns [] for this URL and continues with others.
        raise urllib.error.HTTPError(
            req.full_url, code,
            "redirect refused (SSRF guard)",
            headers, fp,
        )


def _safe_ics_url(url: str) -> str | None:
    """Return `url` if it is safe to fetch as an iCal feed, else None.

    Reject conditions:
      - Scheme not in ALLOWED_ICS_SCHEMES (i.e. anything that isn't https)
      - Empty / missing hostname
      - Hostname resolves (any A or AAAA) to RFC1918, loopback, link-local,
        or IPv6 ULA / link-local address
      - Any resolution failure (socket.gaierror, OSError, etc.)

    Note: this validates the URL ONCE. The actual fetch must use a redirect-
    refusing opener (see `_NoRedirectHandler`) so a 3xx cannot escape the
    validation by pointing the second request at a private address.
    """
    if not isinstance(url, str) or not url:
        return None
    try:
        parsed = urllib.parse.urlparse(url)
    except (ValueError, TypeError):
        return None
    if parsed.scheme not in ALLOWED_ICS_SCHEMES:
        return None
    host = parsed.hostname
    if not host:
        return None

    # Resolve EVERY address; reject if ANY is in a private net. AF_UNSPEC
    # asks for both v4 and v6 records. We deliberately use getaddrinfo (not
    # gethostbyname) to cover both families and let the OS resolver pick.
    try:
        addrs = socket.getaddrinfo(host, None, socket.AF_UNSPEC)
    except (socket.gaierror, OSError):
        return None
    if not addrs:
        return None
    for family, _socktype, _proto, _canon, sockaddr in addrs:
        try:
            if family == socket.AF_INET:
                ip = ipaddress.ip_address(sockaddr[0])
            elif family == socket.AF_INET6:
                # sockaddr is (addr, port, flowinfo, scopeid); ip first.
                # Strip any %scope suffix that AF_INET6 sometimes carries.
                addr0 = sockaddr[0].split("%", 1)[0]
                ip = ipaddress.ip_address(addr0)
            else:
                # Unknown family — be conservative; reject.
                return None
        except (ValueError, IndexError):
            return None
        for net in _PRIVATE_IP_NETS:
            try:
                if ip in net:
                    return None
            except TypeError:
                # ip in net raises TypeError if families don't match; the
                # _PRIVATE_IP_NETS tuple has both v4 and v6 entries so this
                # is benign — try the next net.
                continue
        # Belt-and-braces: ipaddress's own classifiers catch anything our
        # net list missed (e.g. multicast, reserved, unspec).
        if ip.is_private or ip.is_loopback or ip.is_link_local \
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            return None
    return url


# ──────────────────────────────────────────────────────────────────────────
# iCal source
# ──────────────────────────────────────────────────────────────────────────


def _parse_ical_dt(raw: str) -> str | None:
    """Convert an iCal DTSTART / DTEND value (RHS only) to an RFC3339 string.

    Handles two common shapes:
      - "20260601T140000Z"               → UTC, append :00 separators
      - "20260601T100000"                → naive (TZID may be on the LHS;
                                           v1 limitation: we treat as naive
                                           and emit without an offset)
      - "20260601"                       → all-day; emit T00:00:00 (no TZ)

    Returns None on parse failure (caller drops the event).
    """
    if not raw:
        return None
    raw = raw.strip()
    # Date-only (VALUE=DATE) — 8 digits.
    if len(raw) == 8 and raw.isdigit():
        try:
            d = _dt.datetime.strptime(raw, "%Y%m%d")
        except ValueError:
            return None
        return d.replace(tzinfo=_dt.timezone.utc).isoformat()
    # Datetime with optional trailing Z.
    is_utc = raw.endswith("Z")
    body = raw[:-1] if is_utc else raw
    try:
        dt = _dt.datetime.strptime(body, "%Y%m%dT%H%M%S")
    except ValueError:
        return None
    if is_utc:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    # If not UTC and TZID was on LHS, we'd ideally honour it via zoneinfo —
    # but that requires inspecting the parameter list at the line level.
    # For v1, emit without offset rather than skip the event (documented
    # in module docstring). The frontend will render at local time.
    return dt.isoformat()


def _unfold_lines(raw: str) -> list[str]:
    """RFC 5545 line unfolding.

    A line that starts with SPACE or TAB is a continuation of the previous
    logical line; the leading whitespace is stripped and the rest is
    concatenated onto the previous line.
    """
    out: list[str] = []
    for line in raw.splitlines():
        if line.startswith((" ", "\t")) and out:
            out[-1] = out[-1] + line[1:]
        else:
            out.append(line)
    return out


def _parse_ical(text: str) -> list[dict]:
    """Tiny stdlib-only iCal parser.

    Extracts DTSTART, DTEND, SUMMARY, UID from each VEVENT block. Returns
    events in the canonical wire shape (source = "ics"; color defaults to
    `_DEFAULT_COLOR`). Never raises — malformed events are skipped, the
    rest are returned.

    TODO(recurrence): RRULE expansion is out of scope for v1. We emit a
    single occurrence per VEVENT — recurring events from upstream calendars
    will appear only on their DTSTART date until a future iteration adds
    RRULE handling.
    """
    events: list[dict] = []
    in_event = False
    cur: dict[str, str] = {}
    for raw_line in _unfold_lines(text):
        # iCal can end lines with CRLF; strip any leftover \r.
        line = raw_line.rstrip("\r")
        if line == "BEGIN:VEVENT":
            in_event = True
            cur = {}
            continue
        if line == "END:VEVENT":
            if in_event:
                _maybe_emit_ical_event(cur, events)
            in_event = False
            cur = {}
            continue
        if not in_event:
            continue
        # Property line is NAME[;params]:VALUE. We only need to split on the
        # FIRST colon — values containing colons (rare in DTSTART/SUMMARY)
        # must be preserved.
        if ":" not in line:
            continue
        lhs, value = line.split(":", 1)
        # Strip parameters from lhs (e.g. "DTSTART;TZID=America/New_York")
        name = lhs.split(";", 1)[0].upper()
        if name in ("DTSTART", "DTEND", "SUMMARY", "UID"):
            cur[name] = value
    return events


def _maybe_emit_ical_event(props: dict[str, str], out: list[dict]) -> None:
    """Validate a parsed VEVENT dict and append it to `out` if usable."""
    title = props.get("SUMMARY", "").strip()
    start = _parse_ical_dt(props.get("DTSTART", ""))
    end = _parse_ical_dt(props.get("DTEND", ""))
    uid = props.get("UID", "").strip()
    if not title or not start:
        return
    if not end:
        # No DTEND → fall back to DTSTART so the event still renders as a
        # zero-length marker. Calendars in the wild sometimes omit DTEND
        # for all-day events; we'd rather show the title than drop it.
        end = start
    # Stable id keyed on source + UID. If UID is missing we fall back to
    # title+start so the dedupe pass still gets a stable key, even if it
    # is not globally unique across re-syncs.
    src_id = uid or f"{title}|{start}"
    out.append({
        "id":     f"ics:{src_id}",
        "title":  title,
        "start":  start,
        "end":    end,
        "color":  _DEFAULT_COLOR,
        "source": "ics",
    })


def _fetch_one_ics(url: str) -> list[dict]:
    """Fetch a single iCal feed with all SSRF + size guards, return parsed events.

    Returns [] on any failure (network, timeout, redirect, size cap, parse).
    """
    safe = _safe_ics_url(url)
    if not safe:
        # Don't log the URL — even just logging the host can leak vendor
        # info (which calendar provider the user has connected). Log only
        # that an iCal source was rejected.
        sys.stderr.write("[api/calendar] ics url rejected by safety guard\n")
        return []
    opener = urllib.request.build_opener(_NoRedirectHandler)
    req = urllib.request.Request(safe, method="GET", headers={
        "User-Agent": "invisible-dashboard/1 (calendar fetcher)",
        "Accept": "text/calendar, */*;q=0.5",
    })
    try:
        with opener.open(req, timeout=ICS_FETCH_TIMEOUT_S) as resp:
            # Respect Content-Length up-front if the server provided one.
            cl = resp.headers.get("Content-Length")
            if cl is not None:
                try:
                    if int(cl) > ICS_MAX_BYTES:
                        sys.stderr.write(
                            "[api/calendar] ics body too large (content-length)\n"
                        )
                        return []
                except (TypeError, ValueError):
                    pass
            # Read up to ICS_MAX_BYTES + 1 — if we got more, the server lied
            # about / omitted Content-Length and we treat it as untrusted.
            data = resp.read(ICS_MAX_BYTES + 1)
            if len(data) > ICS_MAX_BYTES:
                sys.stderr.write(
                    "[api/calendar] ics body too large (streamed cap)\n"
                )
                return []
    except (urllib.error.URLError, urllib.error.HTTPError,
            socket.timeout, ConnectionError, OSError) as exc:
        sys.stderr.write(
            f"[api/calendar] ics fetch failed: {type(exc).__name__}\n"
        )
        return []
    try:
        text = data.decode("utf-8", errors="replace")
    except (UnicodeDecodeError, AttributeError):
        return []
    try:
        return _parse_ical(text)
    except Exception as exc:  # noqa: BLE001 — parser is best-effort
        sys.stderr.write(
            f"[api/calendar] ics parse failed: {type(exc).__name__}\n"
        )
        return []


def _fetch_ics_events(urls: list[str], date_from: str, date_to: str) -> list[dict]:
    """Fetch every iCal URL, parse, filter to [date_from, date_to]."""
    if not urls:
        return []
    out: list[dict] = []
    for url in urls:
        try:
            evs = _fetch_one_ics(url)
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(
                f"[api/calendar] ics loader failed: {type(exc).__name__}\n"
            )
            evs = []
        for e in evs:
            if _within_window(e.get("start", ""), date_from, date_to):
                out.append(e)
    return out


# ──────────────────────────────────────────────────────────────────────────
# Notion source
# ──────────────────────────────────────────────────────────────────────────


def _flatten_notion_title(prop: dict) -> str:
    """Notion title properties are arrays of rich-text segments."""
    parts = prop.get("title") or []
    return "".join(seg.get("plain_text", "") for seg in parts).strip()


def _notion_date_to_iso(value: str | None) -> str | None:
    """Convert a Notion date string (YYYY-MM-DD or full ISO) to RFC3339."""
    if not value:
        return None
    # Notion date values come as either "YYYY-MM-DD" (date-only) or full
    # ISO-8601 with timezone. fromisoformat handles both in py3.11+.
    try:
        dt = _dt.datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt.isoformat()


def _fetch_notion_events(db_id: str, date_from: str, date_to: str) -> list[dict]:
    """Query the configured Notion calendar DB and flatten into wire shape."""
    if not db_id:
        return []
    try:
        rows = notion.query_calendar_db(db_id, date_from, date_to)
    except Exception as exc:  # noqa: BLE001 — never crash the daemon
        sys.stderr.write(
            f"[api/calendar] notion query failed: {type(exc).__name__}\n"
        )
        return []
    out: list[dict] = []
    for page in rows or []:
        if not isinstance(page, dict):
            continue
        props = page.get("properties") or {}
        # Find the title (Notion lets you rename it but the type is "title").
        title = ""
        for key, val in props.items():
            if isinstance(val, dict) and val.get("type") == "title":
                title = _flatten_notion_title(val)
                break
        if not title:
            continue
        date_prop = props.get("Date") or {}
        date_obj = date_prop.get("date") if isinstance(date_prop, dict) else None
        if not isinstance(date_obj, dict):
            continue
        start = _notion_date_to_iso(date_obj.get("start"))
        end = _notion_date_to_iso(date_obj.get("end")) or start
        if not start:
            continue
        # Optional "Color" select property → hex code by convention. Fall
        # back to the safe default if missing or shaped oddly.
        color = _DEFAULT_COLOR
        color_prop = props.get("Color")
        if isinstance(color_prop, dict) and color_prop.get("type") == "select":
            sel = color_prop.get("select") or {}
            name = (sel.get("name") or "").strip()
            if _HEX_COLOR_RE.match(name):
                color = name
        # Optional "Project" relation → first related page id. Frontend uses
        # this to look up project-anchored colors in DATA_SETS.
        project_id = None
        proj_prop = props.get("Project")
        if isinstance(proj_prop, dict) and proj_prop.get("type") == "relation":
            rel = proj_prop.get("relation") or []
            if rel and isinstance(rel[0], dict):
                pid = rel[0].get("id")
                if isinstance(pid, str):
                    project_id = pid
        ev = {
            "id":     f"notion:{page.get('id', f'{title}|{start}')}",
            "title":  title,
            "start":  start,
            "end":    end,
            "color":  color,
            "source": "notion",
        }
        if project_id:
            ev["project_id"] = project_id
        if _within_window(start, date_from, date_to):
            out.append(ev)
    return out


# ──────────────────────────────────────────────────────────────────────────
# Local events.json source
# ──────────────────────────────────────────────────────────────────────────


def _safe_events_path() -> Path | None:
    """Resolve ~/.invisible/events.json and confirm it stays inside the home.

    Symlink trickery (events.json → /etc/passwd) is rejected via
    `Path.resolve()` + `is_relative_to(config.home().resolve())`. Returns
    None on resolution failure or escape.
    """
    try:
        invisible_root = config.home().resolve()
    except (OSError, RuntimeError):
        return None
    try:
        candidate = (invisible_root / "events.json").resolve()
    except (OSError, RuntimeError):
        return None
    try:
        if not candidate.is_relative_to(invisible_root):
            return None
    except (AttributeError, ValueError):
        return None
    return candidate


def _fetch_local_events(date_from: str, date_to: str) -> list[dict]:
    """Read ~/.invisible/events.json and emit wire-shaped, in-window events."""
    p = _safe_events_path()
    if p is None or not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        # Do NOT log the path. Operator can grep for the prefix.
        sys.stderr.write(
            f"[api/calendar] local events.json unreadable: {type(exc).__name__}\n"
        )
        return []
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for raw in data:
        if not isinstance(raw, dict):
            continue
        title = (raw.get("title") or "").strip()
        if not isinstance(title, str) or not title:
            continue
        start = raw.get("start")
        end = raw.get("end") or start
        if not isinstance(start, str) or not isinstance(end, str):
            continue
        # Normalise via fromisoformat so we accept "2026-06-01T14:00:00Z"
        # and "2026-06-01T14:00:00+00:00". Drop entries we can't parse.
        norm_start = _notion_date_to_iso(start)
        norm_end = _notion_date_to_iso(end) or norm_start
        if not norm_start:
            continue
        color = _DEFAULT_COLOR
        raw_color = raw.get("color")
        if isinstance(raw_color, str) and _HEX_COLOR_RE.match(raw_color):
            color = raw_color
        ev = {
            "id":     f"local:{title}|{norm_start}",
            "title":  title,
            "start":  norm_start,
            "end":    norm_end,
            "color":  color,
            "source": "local",
        }
        pid = raw.get("project_id")
        if isinstance(pid, str) and pid:
            ev["project_id"] = pid
        if _within_window(norm_start, date_from, date_to):
            out.append(ev)
    return out


# ──────────────────────────────────────────────────────────────────────────
# Merge + window filter
# ──────────────────────────────────────────────────────────────────────────


def _within_window(start_iso: str, date_from: str, date_to: str) -> bool:
    """Return True if `start_iso` falls in [date_from 00:00, date_to 23:59:59] UTC.

    Always returns True when either bound is unparseable — we'd rather show
    a possibly-out-of-range event than silently drop it.
    """
    try:
        df = _dt.datetime.strptime(date_from, "%Y-%m-%d").replace(
            tzinfo=_dt.timezone.utc)
        dt_to = _dt.datetime.strptime(date_to, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, tzinfo=_dt.timezone.utc)
    except (ValueError, TypeError):
        return True
    try:
        ev = _dt.datetime.fromisoformat(start_iso)
    except (ValueError, TypeError):
        return True
    if ev.tzinfo is None:
        ev = ev.replace(tzinfo=_dt.timezone.utc)
    return df <= ev <= dt_to


def _dedupe_key(ev: dict) -> tuple[str, str]:
    """Stable key for cross-source dedupe."""
    title = (ev.get("title") or "").strip().lower()
    start = ev.get("start") or ""
    return (title, start)


def merge_events(notion_evs: list[dict],
                 ics_evs: list[dict],
                 local_evs: list[dict]) -> list[dict]:
    """Merge events from all three sources, dedupe by (title, start), sort by start.

    Priority on collision: notion > ics > local. The first occurrence wins;
    later sources are dropped if their key matches an already-seen event.
    """
    seen: dict[tuple[str, str], dict] = {}
    # Order matters — first to write into `seen` wins.
    for src in (notion_evs, ics_evs, local_evs):
        for ev in src:
            key = _dedupe_key(ev)
            if key in seen:
                continue
            seen[key] = ev
    merged = list(seen.values())
    merged.sort(key=lambda e: e.get("start") or "")
    return merged


# ──────────────────────────────────────────────────────────────────────────
# Cached aggregator
# ──────────────────────────────────────────────────────────────────────────


def _load_calendar_config() -> dict:
    """Read [calendar] from invisible.toml. Returns {} on any failure."""
    try:
        cfg = config.load_toml() or {}
    except Exception:  # noqa: BLE001
        return {}
    cal = cfg.get("calendar")
    return cal if isinstance(cal, dict) else {}


def _compute_calendar(date_from: str, date_to: str) -> list[dict]:
    """Fetch all sources, merge, and return the wire-shaped list."""
    cal_cfg = _load_calendar_config()
    db_id = ""
    db_raw = cal_cfg.get("notion_database_id")
    if isinstance(db_raw, str):
        db_id = db_raw.strip()
    if not db_id:
        # Optional env fallback for symmetry with other notion.py helpers.
        db_id = os.environ.get("NOTION_DB_CALENDAR", "").strip()

    ics_urls_raw = cal_cfg.get("ics_urls") or []
    ics_urls: list[str] = [u for u in ics_urls_raw if isinstance(u, str) and u]

    notion_evs = _fetch_notion_events(db_id, date_from, date_to)
    ics_evs = _fetch_ics_events(ics_urls, date_from, date_to)
    local_evs = _fetch_local_events(date_from, date_to)
    return merge_events(notion_evs, ics_evs, local_evs)


def get_calendar(date_from: str, date_to: str) -> list[dict]:
    """Cached entry point: 60-second TTL, single-flight under one global lock.

    Concurrent requests for the same window block on `_CACHE_LOCK` and then
    read the freshly-populated cache entry instead of re-fetching.
    """
    key = (date_from, date_to)
    now = time.time()
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if entry and (now - entry[0]) < CACHE_TTL_S:
            return entry[1]
        result = _compute_calendar(date_from, date_to)
        _CACHE[key] = (time.time(), result)
        return result


# ──────────────────────────────────────────────────────────────────────────
# HTTP handler
# ──────────────────────────────────────────────────────────────────────────


def _parse_date_param(value: str | None) -> str | None:
    """Strict YYYY-MM-DD parser. Returns the normalized string or None."""
    if not value or not isinstance(value, str):
        return None
    try:
        _dt.datetime.strptime(value, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    return value


def handle_calendar(handler: Any) -> None:
    """HTTP handler for GET /api/v1/calendar.

    Wraps every external call in try/except. On any failure, logs the
    exception TYPE (never the message, URL, or path) to stderr and sends
    `{"error": "internal error"}` with status 500.
    """
    try:
        parsed = urllib.parse.urlparse(getattr(handler, "path", ""))
        q = urllib.parse.parse_qs(parsed.query)
        date_from = _parse_date_param((q.get("from") or [""])[0])
        date_to = _parse_date_param((q.get("to") or [""])[0])
    except Exception:  # noqa: BLE001
        handler._send_json(
            {"error": "bad_request",
             "hint": "from and to are required YYYY-MM-DD"},
            status=400,
        )
        return
    if not date_from or not date_to:
        handler._send_json(
            {"error": "bad_request",
             "hint": "from and to are required YYYY-MM-DD"},
            status=400,
        )
        return

    try:
        events = get_calendar(date_from, date_to)
        handler._send_json(events, status=200)
    except Exception as exc:  # noqa: BLE001 — generic 500 path
        try:
            sys.stderr.write(
                f"[api/calendar] internal error: {type(exc).__name__}\n"
            )
        except Exception:  # noqa: BLE001
            pass
        try:
            handler._send_json({"error": "internal error"}, status=500)
        except Exception:  # noqa: BLE001
            pass
