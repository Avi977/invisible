"""HTML/CSS for the invisible dashboard.

Used by both bin/invisible-dashboard (local-only view of this machine's
checkpoints) and bin/invisible-server (VPS daemon serving aggregated state
from SQLite). Both call render_index() and render_project() with shaped
dicts; the renderer doesn't care where the data came from.

Shape contracts (kept in sync with bin/invisible-dashboard + the daemon):

  project (in the list view):
    project, state, iter, max_iters, verdict, age, cost_usd, sha, host,
    task_first

  project (detail view):
    project, state, host, iter, max_iters, last_sha, last_verdict,
    last_summary, task, started_age, updated_age, usage_total,
    usage_per_iter, feedback_history

  review:
    title, iter, agent, verdict, summary, diff_sha, age
"""

from __future__ import annotations

import datetime as dt
import html
import socket
import urllib.parse


CSS = """
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  background: #0d0f12; color: #e5e7eb;
  font-size: 15px; line-height: 1.5;
  -webkit-text-size-adjust: 100%;
}
header {
  padding: 14px 16px;
  border-bottom: 1px solid #1f2329;
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px;
}
header h1 { font-size: 16px; margin: 0; font-weight: 600; letter-spacing: 0.2px; }
header h1 a { color: #e5e7eb; text-decoration: none; }
header .stamp { font-size: 12px; color: #6b7280; }
main { max-width: 980px; margin: 0 auto; padding: 12px 16px 80px; }
h2 { font-size: 14px; color: #9ca3af; margin: 20px 0 8px; font-weight: 600;
     letter-spacing: 0.4px; text-transform: uppercase; }
.card {
  background: #15181d; border: 1px solid #1f2329; border-radius: 8px;
  padding: 14px 16px; margin-bottom: 10px;
}
.card a.title {
  color: #e5e7eb; text-decoration: none; font-weight: 600; font-size: 16px;
  display: block; margin-bottom: 4px;
}
.card a.title:hover { color: #93c5fd; }
.row { display: flex; flex-wrap: wrap; gap: 8px 14px; font-size: 13px; color: #9ca3af; }
.row span.k { color: #6b7280; }
.pill {
  display: inline-block; padding: 2px 8px; border-radius: 999px;
  font-size: 11px; font-weight: 600; letter-spacing: 0.3px;
  text-transform: uppercase;
}
.pill.RUN    { background: #064e3b; color: #6ee7b7; }
.pill.idle   { background: #1f2937; color: #9ca3af; }
.pill.stale  { background: #422006; color: #fbbf24; }
.pill.approve, .pill.Approved { background: #064e3b; color: #6ee7b7; }
.pill.changes, .pill.Changes  { background: #422006; color: #fbbf24; }
.pill.block,   .pill.Blocked  { background: #450a0a; color: #fca5a5; }
.pill.Comment  { background: #1e3a8a; color: #93c5fd; }
.pill.codex, .pill.Codex      { background: #1e3a8a; color: #93c5fd; }
.pill.claude, .pill.Claude    { background: #4c1d95; color: #c4b5fd; }
.pill.human, .pill.Human      { background: #1f2937; color: #9ca3af; }
.task { color: #d1d5db; font-size: 13px; margin-top: 6px;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.empty { color: #6b7280; padding: 24px; text-align: center; }
.kvline { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 13px; color: #d1d5db; }
.kvline .k { color: #6b7280; display: inline-block; min-width: 80px; }
.iter-block {
  background: #15181d; border-left: 3px solid #1e3a8a;
  padding: 10px 14px; margin: 8px 0; border-radius: 0 6px 6px 0;
}
.iter-block.approve { border-left-color: #10b981; }
.iter-block.changes { border-left-color: #f59e0b; }
.iter-block.block   { border-left-color: #ef4444; }
.iter-block .iter-head { font-weight: 600; font-size: 14px; }
.iter-block .iter-meta { color: #9ca3af; font-size: 12px; margin-top: 2px; }
.iter-block pre { white-space: pre-wrap; color: #d1d5db; font-size: 12px;
                  background: #0d0f12; padding: 8px 10px; border-radius: 4px;
                  margin: 8px 0 0; overflow-x: auto; }
nav.back { font-size: 13px; }
nav.back a { color: #9ca3af; text-decoration: none; }
nav.back a:hover { color: #93c5fd; }
.live-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
            background: #6b7280; margin-right: 6px; vertical-align: middle; }
.live-dot.on { background: #10b981; box-shadow: 0 0 6px #10b981; }
@media (max-width: 600px) {
  header { padding: 10px 12px; }
  header h1 { font-size: 14px; }
  main { padding: 10px 12px 64px; }
  .card { padding: 12px; }
}
"""


# Optional auto-reconnecting SSE client that flips a "live" indicator and
# triggers a soft refresh when a new event arrives. Pages embed it iff
# sse_path is passed to render_*().
def _sse_script(sse_path: str, token: str | None) -> str:
    if not sse_path:
        return ""
    qs = f"?token={urllib.parse.quote(token)}" if token else ""
    return f"""<script>
(function() {{
  let lastRefresh = Date.now();
  function connect() {{
    const es = new EventSource("{sse_path}{qs}");
    const dot = document.getElementById("live-dot");
    es.onopen = () => dot && dot.classList.add("on");
    es.onmessage = (ev) => {{
      // Throttle: refresh at most every 2s to avoid flickering on bursty runs.
      if (Date.now() - lastRefresh > 2000) {{
        lastRefresh = Date.now();
        location.reload();
      }}
    }};
    es.onerror = () => {{
      dot && dot.classList.remove("on");
      es.close();
      setTimeout(connect, 3000);  // reconnect
    }};
  }}
  connect();
}})();
</script>"""


def humanize_age(iso: str) -> str:
    try:
        when = dt.datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return "?"
    delta = dt.datetime.now(dt.timezone.utc) - when
    s = int(delta.total_seconds())
    # Clock skew between machines is real (Mac pushes a checkpoint, VPS
    # clock is a few seconds ahead). Display future timestamps as "now".
    if s < 0:     return "now"
    if s < 60:    return f"{s}s"
    if s < 3600:  return f"{s//60}m"
    if s < 86400: return f"{s//3600}h"
    return f"{s//86400}d"


def _layout(title: str, body: str, token: str | None,
            sse_path: str = "", subtitle: str = "") -> str:
    qs = f"?token={urllib.parse.quote(token)}" if token else ""
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    if not subtitle:
        subtitle = socket.gethostname()
    live_dot = '<span id="live-dot" class="live-dot"></span>' if sse_path else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="dark">
<title>{html.escape(title)} — invisible</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>{live_dot}<a href="/{qs}">invisible</a> <span style="color:#6b7280;font-weight:400">· {html.escape(subtitle)}</span></h1>
  <div class="stamp">{html.escape(now)}</div>
</header>
<main>
{body}
</main>
{_sse_script(sse_path, token)}
</body>
</html>"""


def render_index(projects: list[dict], reviews: list[dict],
                 token: str | None, *, sse_path: str = "",
                 subtitle: str = "") -> str:
    qs = f"?token={urllib.parse.quote(token)}" if token else ""
    if not projects:
        proj_html = '<div class="empty">No project checkpoints.</div>'
    else:
        cards = []
        for p in projects:
            pill_state = f'<span class="pill {p["state"]}">{p["state"]}</span>'
            verdict_pill = ""
            if p.get("verdict"):
                verdict_pill = (f'<span class="pill {p["verdict"]}">'
                                f'{html.escape(p["verdict"])}</span>')
            cap = p.get("max_iters") or "∞"
            cards.append(f"""
<div class="card">
  <a class="title" href="/p/{urllib.parse.quote(p["project"])}{qs}">{html.escape(p["project"])}</a>
  <div class="row">
    {pill_state}
    {verdict_pill}
    <span><span class="k">iter</span> {p.get("iter", 0)}/{cap}</span>
    <span><span class="k">age</span> {p.get("age", "?")}</span>
    <span><span class="k">cost</span> ${p.get("cost_usd", 0):.4f}</span>
    <span><span class="k">sha</span> {html.escape(p.get("sha") or "—")}</span>
    <span><span class="k">host</span> {html.escape(p.get("host") or "?")}</span>
  </div>
  <div class="task">{html.escape(p.get("task_first") or "")}</div>
</div>""")
        proj_html = "\n".join(cards)

    if reviews:
        review_rows = []
        for r in reviews:
            agent_pill = f'<span class="pill {r.get("agent","")}">{html.escape(r.get("agent") or "?")}</span>'
            verdict_pill = f'<span class="pill {r.get("verdict","")}">{html.escape(r.get("verdict") or "?")}</span>'
            review_rows.append(f"""
<div class="card">
  <div class="row">
    {agent_pill}
    {verdict_pill}
    <span><span class="k">iter</span> {html.escape(str(r.get("iter") or ""))}</span>
    <span><span class="k">age</span> {r.get("age","?")}</span>
    <span><span class="k">sha</span> {html.escape(r.get("diff_sha") or "—")}</span>
  </div>
  <div class="task">{html.escape(r.get("title") or "")}</div>
  <div class="task" style="color:#9ca3af">{html.escape(r.get("summary") or "")}</div>
</div>""")
        review_html = "\n".join(review_rows)
    else:
        review_html = ('<div class="empty">No Notion reviews '
                       '(NOTION_TOKEN/DB unset or unreachable).</div>')

    body = f"""
<h2>Projects</h2>
{proj_html}
<h2>Recent reviews (Notion, all machines)</h2>
{review_html}
"""
    return _layout("dashboard", body, token, sse_path=sse_path, subtitle=subtitle)


def render_project(p: dict, token: str | None, *,
                   sse_path: str = "", subtitle: str = "") -> str:
    qs = f"?token={urllib.parse.quote(token)}" if token else ""
    cap = p.get("max_iters") or "∞"
    u = p.get("usage_total") or {}
    cost_block = ""
    if u:
        cost_block = (f'<div class="kvline"><span class="k">claude</span>'
                      f'{u.get("input_tokens", 0):,} in / '
                      f'{u.get("output_tokens", 0):,} out / '
                      f'{u.get("cache_read_input_tokens", 0):,} cache · '
                      f'${u.get("cost_usd", 0):.4f} cumulative</div>')

    iter_blocks: list[str] = []
    fb = p.get("feedback_history") or []
    per_iter = {it["iter"]: it for it in (p.get("usage_per_iter") or [])}
    total_iters = p.get("iter", 0)
    last_verdict = p.get("last_verdict") or ""
    for n in range(1, total_iters + 1):
        if n <= len(fb):
            klass = "changes"; head_v = "changes"
        elif n == total_iters and last_verdict == "approve":
            klass = "approve"; head_v = "approve"
        else:
            klass = ""; head_v = last_verdict
        u_n = per_iter.get(n) or {}
        cost_str = ""
        if u_n:
            cost_str = (f' · ${u_n.get("cost_usd", 0):.4f} '
                        f'({u_n.get("input_tokens", 0):,} in / '
                        f'{u_n.get("output_tokens", 0):,} out)')
        feedback_pre = ""
        if n <= len(fb):
            feedback_pre = f'<pre>{html.escape(fb[n-1])}</pre>'
        iter_blocks.append(f"""
<div class="iter-block {klass}">
  <div class="iter-head">iter {n} <span class="pill {klass}">{html.escape(head_v)}</span></div>
  <div class="iter-meta">{html.escape(cost_str)}</div>
  {feedback_pre}
</div>""")

    iters_html = ("\n".join(iter_blocks) if iter_blocks
                  else '<div class="empty">No iterations yet.</div>')

    task = p.get("task") or ""
    state = p.get("state", "")
    body = f"""
<nav class="back"><a href="/{qs}">← all projects</a></nav>
<h2>{html.escape(p.get("project") or "?")}</h2>
<div class="card">
  <div class="row">
    <span class="pill {state}">{state}</span>
    <span class="pill {last_verdict}">{html.escape(last_verdict or "—")}</span>
    <span><span class="k">iter</span> {p.get("iter", 0)}/{cap}</span>
    <span><span class="k">started</span> {p.get("started_age","?")} ago</span>
    <span><span class="k">updated</span> {p.get("updated_age","?")} ago</span>
    <span><span class="k">host</span> {html.escape(p.get("host") or "?")}</span>
    <span><span class="k">sha</span> {html.escape(p.get("last_sha") or "—")}</span>
  </div>
  <div class="task" style="margin-top:8px;color:#9ca3af">{html.escape(p.get("last_summary") or "")}</div>
  {cost_block}
</div>
<h2>Task</h2>
<div class="card"><pre style="margin:0;white-space:pre-wrap;color:#d1d5db">{html.escape(task)}</pre></div>
<h2>Iterations</h2>
{iters_html}
"""
    return _layout(p.get("project") or "?", body, token,
                   sse_path=sse_path, subtitle=subtitle)


def render_not_found(label: str, token: str | None,
                     subtitle: str = "") -> str:
    body = f'<div class="empty">No checkpoint for {html.escape(label)}.</div>'
    return _layout(label, body, token, subtitle=subtitle)
