// Calendar — week view + mini month picker, wired to GET /api/v1/calendar.
//
// Replaces the hardcoded EVENTS mock with a live fetch against the dashboard
// daemon. Resolves event colors via window.DATA_SETS lookups (project_id →
// project.color) with a per-event hex fallback and a brand default of #8aa9ff.
//
// State machine:
//   "loading" → "ok"     (events.length > 0)
//             → "empty"  (events.length == 0; no source configured)
//             → "error"  (HTTP non-2xx, network error, malformed response)
//
// XSS posture (T-01-FE-01..05 in 02-PLAN.md): all event titles, project
// names, and source badges render as React text children only — never via
// the unsafe innerHTML escape hatch. Backend hint fields are deliberately
// NOT surfaced in errorMsg; we only show the HTTP status.

const {
  useState:    useStateC,
  useMemo:     useMemoC,
  useEffect:   useEffectC,
  useCallback: useCallbackC,
} = React;

// CAL_API_BASE picks up window.INVISIBLE_API_BASE if set (the Playwright smoke
// uses addInitScript to point at an alt port). Default matches
// frontend/data.jsx:464 so a normal user run is identical to the rest of the
// frontend's network surface.
const CAL_API_BASE = (typeof window !== "undefined" && window.INVISIBLE_API_BASE)
  ? window.INVISIBLE_API_BASE
  : "http://127.0.0.1:8765";

const DEFAULT_EVENT_COLOR = "#8aa9ff";
const HEX_COLOR_RE = /^#[0-9a-fA-F]{6}$/;

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOURS = Array.from({ length: 12 }, (_, i) => 8 + i); // 8am to 7pm

// ── Helpers ──────────────────────────────────────────────────────────────

// Monday 00:00 LOCAL of the ISO week containing `date`. Sunday wraps to the
// PRIOR Monday (not the next), matching the visual "this week" interpretation
// the WeekView already uses for its day columns.
function mondayOf(date) {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const dow = (d.getDay() + 6) % 7; // Mon=0..Sun=6
  d.setDate(d.getDate() - dow);
  return d;
}

// Sunday 23:59:59.999 LOCAL of the same week (inclusive end of range).
function sundayOf(date) {
  const m = mondayOf(date);
  const s = new Date(m.getFullYear(), m.getMonth(), m.getDate() + 6,
                     23, 59, 59, 999);
  return s;
}

// LOCAL-time YYYY-MM-DD string. Avoid toISOString() — it shifts to UTC and
// can flip the date around midnight, which would request the wrong week
// from the backend.
function fmtDate(date) {
  const y  = date.getFullYear();
  const mo = String(date.getMonth() + 1).padStart(2, "0");
  const da = String(date.getDate()).padStart(2, "0");
  return `${y}-${mo}-${da}`;
}

// Wrap `new Date(s)` so a future tweak (e.g. honouring a TZID upstream sends
// us) is a one-line change. RFC3339 is a subset of the formats Date accepts.
function parseRfc3339(s) {
  return new Date(s);
}

// LOCAL decimal hours (0..24). Used by WeekView to position events on the
// 8am-7pm strip and by the "now" line.
function decimalHours(d) {
  return d.getHours() + d.getMinutes() / 60 + d.getSeconds() / 3600;
}

// 0..6 (Mon=0, Sun=6). Clamped so events at week-boundary edges still land
// in a visible column instead of overflowing.
function dayIndex(d, monday) {
  const ms = d - monday;
  const idx = Math.floor(ms / 86_400_000);
  if (idx < 0) return 0;
  if (idx > 6) return 6;
  return idx;
}

// Flatten DATA_SETS.{default,client,...}.projects into a single id→project
// list. First occurrence per id wins (default beats client) so the project
// color the user sees on the dashboard is the same one they see on the
// calendar.
function flattenProjects(dataSets) {
  const out = [];
  const seen = new Set();
  if (!dataSets || typeof dataSets !== "object") return out;
  for (const key of Object.keys(dataSets)) {
    const set = dataSets[key];
    const projects = (set && Array.isArray(set.projects)) ? set.projects : [];
    for (const p of projects) {
      if (!p || typeof p !== "object" || typeof p.id !== "string") continue;
      if (seen.has(p.id)) continue;
      seen.add(p.id);
      out.push({ id: p.id, name: p.name || p.id, color: p.color || DEFAULT_EVENT_COLOR });
    }
  }
  return out;
}

// Resolve the visual color for an event: project lookup wins, else event's
// own hex, else the brand default. Keeps an event tinted with project color
// even if the upstream calendar (e.g. iCal feed) provided a different one.
function colorForEvent(event, projects) {
  if (event && typeof event.project_id === "string" && event.project_id) {
    const match = projects.find((p) => p.id === event.project_id);
    if (match && typeof match.color === "string" && HEX_COLOR_RE.test(match.color)) {
      return match.color;
    }
  }
  if (event && typeof event.color === "string" && HEX_COLOR_RE.test(event.color)) {
    return event.color;
  }
  return DEFAULT_EVENT_COLOR;
}

// API event → WeekView shape, plus extras the popover needs. Returns null
// if start/end is invalid (caller drops it) — see T-01-FE-03 in the plan.
function transformEvent(apiEvent, monday, projects) {
  if (!apiEvent || typeof apiEvent !== "object") return null;
  const start = parseRfc3339(apiEvent.start);
  const end   = parseRfc3339(apiEvent.end);
  if (!start || isNaN(start.getTime())) return null;
  if (!end   || isNaN(end.getTime()))   return null;
  const day   = dayIndex(start, monday);
  const startH = decimalHours(start);
  // End-decimal: clamp at start so a degenerate event still renders as a
  // zero-height marker rather than negative-height.
  const endH   = Math.max(startH, decimalHours(end));
  const projectsList = Array.isArray(projects) ? projects : [];
  const matchedProject = (typeof apiEvent.project_id === "string" && apiEvent.project_id)
    ? projectsList.find((p) => p.id === apiEvent.project_id)
    : null;
  return {
    day,
    start:      startH,
    end:        endH,
    title:      (typeof apiEvent.title === "string" && apiEvent.title) ? apiEvent.title : "(untitled)",
    c:          colorForEvent(apiEvent, projectsList),
    project:    matchedProject ? (matchedProject.name || matchedProject.id) : (apiEvent.project_id || "—"),
    project_id: apiEvent.project_id || null,
    id:         apiEvent.id || `${apiEvent.title}|${apiEvent.start}`,
    source:     apiEvent.source || "local",
    raw:        apiEvent,
    // Keep the raw RFC3339 strings so the popover can format them at the
    // user's locale without re-deriving from decimal hours.
    startIso:   apiEvent.start,
    endIso:     apiEvent.end,
  };
}

function fmtH(h) {
  const hr = Math.floor(h);
  const mn = Math.round((h - hr) * 60);
  return `${hr}:${mn.toString().padStart(2, "0")}`;
}

// ── MiniCal ──────────────────────────────────────────────────────────────

function MiniCal({ today, selected, setSelected, events }) {
  const now = today;
  const y = now.getFullYear(), m = now.getMonth();
  const first = new Date(y, m, 1);
  const dow = (first.getDay() + 6) % 7; // Monday=0
  const days = new Date(y, m + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < dow; i++) cells.push({ d: new Date(y, m, -dow + i + 1).getDate(), other: true });
  for (let i = 1; i <= days; i++) cells.push({ d: i, other: false });
  while (cells.length % 7 !== 0) cells.push({ d: cells.length - days - dow + 1, other: true });

  const month = now.toLocaleString("en-US", { month: "long" });

  // TODO(v2): broaden the API window from the current ISO week to the full
  // visible month so days outside the current week also light up correctly.
  // For v1 we only mark days that overlap with the [Mon, Sun] window the
  // useEffect fetched — anything in the same calendar month but a different
  // week will show no dot.
  const eventDaysSet = useMemoC(() => {
    const s = new Set();
    for (const e of (Array.isArray(events) ? events : [])) {
      // `e.raw.start` is the RFC3339 string from the API. Falls back to a
      // transformed event's startIso, then to the bare start.
      const iso = (e && e.raw && e.raw.start) || (e && e.startIso) || null;
      if (!iso) continue;
      const d = parseRfc3339(iso);
      if (!d || isNaN(d.getTime())) continue;
      // Compare against the rendered month — drop events from neighbouring
      // months that happen to share a day-of-month number.
      if (d.getFullYear() === y && d.getMonth() === m) {
        s.add(d.getDate());
      }
    }
    return s;
  }, [events, y, m]);

  // The "Up next" list filters events on TODAY's column (day index 0..6 in
  // the WeekView grid). Today maps to (now.getDay() + 6) % 7.
  const todayDow = (now.getDay() + 6) % 7;
  const upNext = (Array.isArray(events) ? events : [])
    .filter((e) => e && e.day === todayDow)
    .slice(0, 3);

  return (
    <div>
      <div className="glass mini-cal">
        <div className="mini-cal-head">
          <div className="mini-cal-title">{month} {y}</div>
          <div className="mini-cal-nav">
            <button className="icon-btn"><I.ChevronL size={14}/></button>
            <button className="icon-btn"><I.ChevronR size={14}/></button>
          </div>
        </div>
        <div className="mini-cal-grid">
          {DAY_NAMES.map(d => <div key={d} className="mini-day-h">{d[0]}</div>)}
          {cells.map((c, i) => {
            const isToday = !c.other && c.d === now.getDate();
            const isSelected = !c.other && c.d === selected;
            const hasEvent = !c.other && eventDaysSet.has(c.d);
            return (
              <div
                key={i}
                className={"mini-day " + (c.other ? "other " : "") + (isToday ? "today " : "") + (isSelected ? "selected " : "") + (hasEvent ? "has-event" : "")}
                onClick={() => !c.other && setSelected(c.d)}
              >{c.d}</div>
            );
          })}
        </div>
      </div>

      <div className="glass" style={{ padding: "var(--pad-3)", marginTop: "var(--pad-3)" }}>
        <div className="mono" style={{ fontSize: 10, color: "var(--text-4)", letterSpacing: "0.16em", textTransform: "uppercase", marginBottom: 8 }}>Up next</div>
        {upNext.length === 0 ? (
          <div style={{ fontSize: 12, color: "var(--text-3)", fontStyle: "italic", padding: "4px 0" }}>
            nothing scheduled
          </div>
        ) : upNext.map((e, i) => (
          <div key={e.id || i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 0", borderTop: i ? "1px solid var(--border-1)" : "none" }}>
            <div style={{ width: 3, height: 28, background: e.c, borderRadius: 2, boxShadow: `0 0 8px ${e.c}` }}/>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12.5, fontWeight: 500 }}>{e.title}</div>
              <div className="mono" style={{ fontSize: 10, color: "var(--text-3)" }}>{fmtH(e.start)} – {fmtH(e.end)} · {e.project}</div>
            </div>
          </div>
        ))}
      </div>

      {/* TODO: derive legend from active events (current legend is hardcoded
          to the personal-projects palette — derives-from-events would surface
          single-source calendars only, which is worse for v1). */}
      <div className="glass" style={{ padding: "var(--pad-3)", marginTop: "var(--pad-3)" }}>
        <div className="mono" style={{ fontSize: 10, color: "var(--text-4)", letterSpacing: "0.16em", textTransform: "uppercase", marginBottom: 8 }}>Calendars</div>
        {[
          ["Echo",    "#f5b343"],
          ["Lumen",   "#5cc8ff"],
          ["Drift",   "#b794ff"],
          ["Atlas",   "#4ade80"],
          ["Rune",    "#f56fb1"],
          ["Personal","#8aa9ff"],
        ].map(([n, c]) => (
          <div key={n} style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0", fontSize: 12, color: "var(--text-2)" }}>
            <div style={{ width: 10, height: 10, borderRadius: 3, background: c, boxShadow: `0 0 6px ${c}` }}/>
            {n}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── WeekView ─────────────────────────────────────────────────────────────

function WeekView({ events, onEventClick }) {
  const now = new Date();
  const todayDow = (now.getDay() + 6) % 7;
  // Days of this week starting Monday
  const weekDays = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(now);
    d.setDate(now.getDate() - todayDow + i);
    return d;
  });
  const nowH = now.getHours() + now.getMinutes() / 60;
  const slotPct = (h) => ((h - HOURS[0]) / HOURS.length) * 100;

  return (
    <div className="week-view">
      <div className="week-head">
        <div></div>
        {weekDays.map((d, i) => (
          <div key={i} className={i === todayDow ? "today" : ""}>
            {DAY_NAMES[i]} {i === todayDow ? <b>{d.getDate()}</b> : <span style={{ color: "var(--text-4)", marginLeft: 4 }}>{d.getDate()}</span>}
          </div>
        ))}
      </div>
      <div className="week-body">
        <div className="week-times">
          {HOURS.map(h => <div key={h} className="week-time-slot">{h}:00</div>)}
        </div>
        {weekDays.map((_d, day) => (
          <div key={day} className="week-col">
            {HOURS.map(h => <div key={h} className="slot"/>)}
            {(Array.isArray(events) ? events : []).filter(e => e && e.day === day).map((e, i) => {
              const top = ((e.start - HOURS[0]) / HOURS.length) * 100;
              const h = ((e.end - e.start) / HOURS.length) * 100;
              return (
                <div
                  key={e.id || i}
                  className="week-event"
                  style={{ top: `${top}%`, height: `${h}%`, "--e-c": e.c, cursor: "pointer" }}
                  onClick={() => onEventClick && onEventClick(e)}
                  role="button"
                  tabIndex={0}
                  aria-label={`${e.title} at ${fmtH(e.start)}`}
                >
                  <div className="e-time">{fmtH(e.start)}</div>
                  {e.title}
                </div>
              );
            })}
          </div>
        ))}

        {/* Live "now" line — spans across all day columns, anchored to today's column.
            Preserved verbatim from the pre-rewrite layout (lines 160-164 in the original). */}
        <div className="week-now" style={{
          left: 56 + `calc((100% - 56px) / 7 * ${todayDow})`,
          width: `calc((100% - 56px) / 7)`,
          top: `${slotPct(nowH)}%`
        }}/>
      </div>
    </div>
  );
}

// ── Skeleton + empty + error placeholders ────────────────────────────────

function WeekSkeleton() {
  // Render the WeekView shell shape (head + body grid) without events, with a
  // single low-opacity "Loading…" pill per column. Matches the live grid's
  // dimensions so the layout doesn't shift on transition to "ok".
  const now = new Date();
  const todayDow = (now.getDay() + 6) % 7;
  const weekDays = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(now);
    d.setDate(now.getDate() - todayDow + i);
    return d;
  });
  return (
    <div className="week-view" aria-busy="true">
      <div className="week-head">
        <div></div>
        {weekDays.map((d, i) => (
          <div key={i} className={i === todayDow ? "today" : ""}>
            {DAY_NAMES[i]} <span style={{ color: "var(--text-4)", marginLeft: 4 }}>{d.getDate()}</span>
          </div>
        ))}
      </div>
      <div className="week-body">
        <div className="week-times">
          {HOURS.map(h => <div key={h} className="week-time-slot">{h}:00</div>)}
        </div>
        {weekDays.map((_d, day) => (
          <div key={day} className="week-col">
            {HOURS.map(h => <div key={h} className="slot"/>)}
            <div
              className="week-event"
              style={{ top: "0%", height: "100%", "--e-c": "#8aa9ff", opacity: 0.18 }}
            >
              <div className="e-time">…</div>
              Loading…
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function EmptyPlaceholder() {
  return (
    <div className="glass" style={{
      padding: "var(--pad-4)",
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      gap: 8, height: "100%", minHeight: 240, textAlign: "center",
    }}>
      <div style={{ fontSize: 15, fontWeight: 500, color: "var(--text-1)" }}>No events configured</div>
      <div style={{ fontSize: 12, color: "var(--text-3)" }}>
        Configure <span className="mono">[calendar]</span> in <span className="mono">invisible.toml</span> or add <span className="mono">~/.invisible/events.json</span>
      </div>
    </div>
  );
}

function ErrorPlaceholder({ message, onRetry }) {
  return (
    <div className="glass" style={{
      padding: "var(--pad-4)",
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      gap: 12, height: "100%", minHeight: 240, textAlign: "center",
    }}>
      <div style={{ fontSize: 15, fontWeight: 500, color: "var(--text-1)" }}>Couldn't load events</div>
      {message ? (
        <div className="mono" style={{ fontSize: 11, color: "var(--text-3)" }}>{message}</div>
      ) : null}
      <button className="btn" onClick={onRetry}>Retry</button>
    </div>
  );
}

// ── Event popover ────────────────────────────────────────────────────────

function EventPopover({ event, projects, onClose }) {
  // ESC closes the popover. Keyed on `event` so the handler is rebound when
  // the selection changes (and is removed entirely when the popover unmounts
  // — see Calendar's useEffect cleanup).
  useEffectC(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [event, onClose]);

  if (!event) return null;
  const projectName = (() => {
    if (event.project_id) {
      const match = (projects || []).find((p) => p.id === event.project_id);
      if (match) return match.name || match.id;
    }
    return event.project && event.project !== "—" ? event.project : "—";
  })();

  const backdrop = {
    position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
    background: "rgba(0,0,0,0.4)", zIndex: 999,
  };
  const popover = {
    position: "fixed", top: "50%", left: "50%",
    transform: "translate(-50%, -50%)",
    zIndex: 1000, padding: "var(--pad-3)",
    minWidth: 280, maxWidth: 420,
    borderLeft: `3px solid ${event.c || DEFAULT_EVENT_COLOR}`,
  };

  return (
    <>
      <div style={backdrop} onClick={onClose} aria-hidden="true"/>
      <div
        className="glass"
        style={popover}
        role="dialog"
        aria-modal="true"
        aria-label={event.title}
      >
        <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 10 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-1)" }}>{event.title}</div>
            <div className="mono" style={{ fontSize: 11, color: "var(--text-3)", marginTop: 4 }}>
              {fmtH(event.start)} – {fmtH(event.end)}
            </div>
          </div>
          <button
            className="icon-btn"
            onClick={onClose}
            aria-label="Close"
            style={{ flex: "none" }}
          >×</button>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12, color: "var(--text-2)", marginBottom: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: event.c || DEFAULT_EVENT_COLOR, boxShadow: `0 0 6px ${event.c || DEFAULT_EVENT_COLOR}` }}/>
          <span>{projectName}</span>
        </div>
        <div className="mono" style={{ fontSize: 10, color: "var(--text-4)", textTransform: "uppercase", letterSpacing: "0.12em" }}>
          source: {event.source || "local"}
        </div>
      </div>
    </>
  );
}

// ── Calendar root ────────────────────────────────────────────────────────

function Calendar() {
  const today = new Date();
  const [selected,       setSelected]       = useStateC(today.getDate());
  const [events,         setEvents]         = useStateC([]);
  const [status,         setStatus]         = useStateC("loading"); // initial paint shows the skeleton, not stale mock data
  const [errorMsg,       setErrorMsg]       = useStateC("");
  const [selectedEvent,  setSelectedEvent]  = useStateC(null);
  const [retryNonce,     setRetryNonce]     = useStateC(0);

  // Defensive fallback so a missing/late-loaded data.jsx doesn't crash. In
  // production both scripts are loaded by index.html in order — data.jsx
  // before calendar.jsx — but the fallback is cheap insurance.
  const projects = useMemoC(() => {
    const dataSets = (typeof window !== "undefined" && window.DATA_SETS)
      ? window.DATA_SETS
      : { default: { projects: [] }, client: { projects: [] } };
    return flattenProjects(dataSets);
  }, []);

  useEffectC(() => {
    let cancelled = false;
    const monday = mondayOf(new Date());
    const sunday = sundayOf(new Date());

    setStatus("loading");
    setErrorMsg("");

    fetch(`${CAL_API_BASE}/api/v1/calendar?from=${fmtDate(monday)}&to=${fmtDate(sunday)}`, { credentials: "omit" })
      .then(async (response) => {
        if (!response.ok) {
          // Try to read the body for a console warn, but DO NOT surface the
          // body in the visible errorMsg (T-01-FE-05). If body read fails,
          // swallow — the HTTP status is enough.
          try { await response.text(); } catch (e) { /* ignore */ }
          throw new Error(`HTTP ${response.status}`);
        }
        const json = await response.json();
        if (!Array.isArray(json)) {
          throw new Error("malformed response");
        }
        return json;
      })
      .then((apiEvents) => {
        if (cancelled) return;
        if (apiEvents.length === 0) {
          setEvents([]);
          setStatus("empty");
          return;
        }
        const transformed = apiEvents
          .map((e) => transformEvent(e, monday, projects))
          .filter((e) => e !== null);
        setEvents(transformed);
        setStatus(transformed.length === 0 ? "empty" : "ok");
      })
      .catch((err) => {
        if (cancelled) return;
        // Single defensive console.warn — explicitly allowed by the plan for
        // dev-time debuggability. No PII surface (no path, no URL params).
        console.warn("[calendar] fetch failed:", err && err.message);
        setEvents([]);
        setErrorMsg(err && err.message ? err.message : "network error");
        setStatus("error");
      });

    return () => { cancelled = true; };
  }, [retryNonce, projects]);

  const handleRetry = useCallbackC(() => {
    setRetryNonce((n) => n + 1);
  }, []);

  const handleEventClick = useCallbackC((event) => {
    setSelectedEvent(event);
  }, []);

  const handlePopoverClose = useCallbackC(() => {
    setSelectedEvent(null);
  }, []);

  const totalHoursBooked = useMemoC(() => {
    return events.reduce((acc, e) => acc + Math.max(0, (e.end || 0) - (e.start || 0)), 0);
  }, [events]);

  // Render the main pane content based on status. "ok" → WeekView; otherwise
  // a placeholder. MiniCal renders on the left in every state.
  const mainPane = (() => {
    if (status === "loading") return <WeekSkeleton/>;
    if (status === "empty")   return <EmptyPlaceholder/>;
    if (status === "error")   return <ErrorPlaceholder message={errorMsg} onRetry={handleRetry}/>;
    return <WeekView events={events} onEventClick={handleEventClick}/>;
  })();

  return (
    <div className="cal-layout">
      <MiniCal today={today} selected={selected} setSelected={setSelected} events={events}/>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--pad-2)", minHeight: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="chip accent"><span className="chip-dot"/>This week</span>
          <span className="chip mono">{events.length} events · {totalHoursBooked.toFixed(1)}h booked</span>
          <div style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
            <button className="btn">Day</button>
            <button className="btn accent">Week</button>
            <button className="btn">Month</button>
          </div>
        </div>
        <div style={{ flex: 1, minHeight: 0 }}>
          {mainPane}
        </div>
      </div>
      {selectedEvent ? (
        <EventPopover
          event={selectedEvent}
          projects={projects}
          onClose={handlePopoverClose}
        />
      ) : null}
    </div>
  );
}

window.Calendar = Calendar;
