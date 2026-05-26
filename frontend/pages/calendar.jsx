// Calendar — week view with project-color-coded events + a mini month picker.

const { useState: useStateC, useMemo: useMemoC } = React;

const EVENTS = [
  { day: 0, start: 9.5,  end: 10,   title: "Standup",          project: "echo",  c: "#f5b343" },
  { day: 0, start: 11,   end: 12.5, title: "Wave jitter dive", project: "echo",  c: "#f5b343" },
  { day: 0, start: 14,   end: 15,   title: "Lumen code review",project: "lumen", c: "#5cc8ff" },
  { day: 0, start: 16,   end: 17,   title: "Drift launch sync",project: "drift", c: "#b794ff" },

  { day: 1, start: 9.5,  end: 10,   title: "Standup",          project: "echo",  c: "#f5b343" },
  { day: 1, start: 10.5, end: 12,   title: "RLS walker spec",  project: "lumen", c: "#5cc8ff" },
  { day: 1, start: 15,   end: 16,   title: "Sci review",       project: "vrd",   c: "#5ee0c8" },

  { day: 2, start: 9,    end: 11,   title: "Hetzner onboarding",project:"atlas", c: "#4ade80" },
  { day: 2, start: 13,   end: 14.5, title: "Rune ↔ Pairings",  project: "rune",  c: "#f56fb1" },
  { day: 2, start: 16,   end: 17.5, title: "Office hours",     project: "—",     c: "#8aa9ff" },

  { day: 3, start: 10,   end: 11.5, title: "Brand call · Hailey",project:"hailey",c:"#b794ff" },
  { day: 3, start: 14,   end: 16,   title: "Deep work · Echo",  project:"echo",  c:"#f5b343" },

  { day: 4, start: 9.5,  end: 10,   title: "Standup",          project: "echo",  c: "#f5b343" },
  { day: 4, start: 11,   end: 12.5, title: "Drift launch",     project: "drift", c: "#b794ff" },
  { day: 4, start: 15,   end: 17,   title: "Weekly review",    project: "—",     c: "#8aa9ff" },

  { day: 5, start: 11,   end: 13,   title: "Personal · gym",   project: "life",  c: "#5ee0c8" },

  { day: 6, start: 14,   end: 16,   title: "Reading · papers", project: "life",  c: "#8aa9ff" },
];

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOURS = Array.from({length: 12}, (_, i) => 8 + i); // 8am to 7pm

function MiniCal({ today, selected, setSelected }) {
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
            const hasEvent = !c.other && (c.d % 3 === 0 || c.d === now.getDate());
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
        {EVENTS.filter(e => e.day === 0).slice(0, 3).map((e, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 0", borderTop: i ? "1px solid var(--border-1)" : "none" }}>
            <div style={{ width: 3, height: 28, background: e.c, borderRadius: 2, boxShadow: `0 0 8px ${e.c}` }}/>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12.5, fontWeight: 500 }}>{e.title}</div>
              <div className="mono" style={{ fontSize: 10, color: "var(--text-3)" }}>{fmtH(e.start)} – {fmtH(e.end)} · {e.project}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="glass" style={{ padding: "var(--pad-3)", marginTop: "var(--pad-3)" }}>
        <div className="mono" style={{ fontSize: 10, color: "var(--text-4)", letterSpacing: "0.16em", textTransform: "uppercase", marginBottom: 8 }}>Calendars</div>
        {[
          ["Echo",   "#f5b343"],
          ["Lumen",  "#5cc8ff"],
          ["Drift",  "#b794ff"],
          ["Atlas",  "#4ade80"],
          ["Rune",   "#f56fb1"],
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

function fmtH(h) {
  const hr = Math.floor(h);
  const mn = Math.round((h - hr) * 60);
  return `${hr}:${mn.toString().padStart(2,"0")}`;
}

function WeekView() {
  const now = new Date();
  const todayDow = (now.getDay() + 6) % 7;
  // Days of this week starting Monday
  const weekDays = Array.from({length: 7}, (_, i) => {
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
        {weekDays.map((d, day) => (
          <div key={day} className="week-col">
            {HOURS.map(h => <div key={h} className="slot"/>)}
            {EVENTS.filter(e => e.day === day).map((e, i) => {
              const top = ((e.start - HOURS[0]) / HOURS.length) * 100;
              const h = ((e.end - e.start) / HOURS.length) * 100;
              return (
                <div
                  key={i}
                  className="week-event"
                  style={{ top: `${top}%`, height: `${h}%`, "--e-c": e.c }}
                >
                  <div className="e-time">{fmtH(e.start)}</div>
                  {e.title}
                </div>
              );
            })}
          </div>
        ))}

        {/* Now line spans across all day columns */}
        <div className="week-now" style={{
          left: 56 + `calc((100% - 56px) / 7 * ${todayDow})`,
          width: `calc((100% - 56px) / 7)`,
          top: `${slotPct(nowH)}%`
        }}/>
      </div>
    </div>
  );
}

function Calendar() {
  const today = new Date();
  const [selected, setSelected] = useStateC(today.getDate());

  return (
    <div className="cal-layout">
      <MiniCal today={today} selected={selected} setSelected={setSelected}/>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--pad-2)", minHeight: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="chip accent"><span className="chip-dot"/>This week</span>
          <span className="chip mono">8 events · 14h booked</span>
          <div style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
            <button className="btn">Day</button>
            <button className="btn accent">Week</button>
            <button className="btn">Month</button>
          </div>
        </div>
        <div style={{ flex: 1, minHeight: 0 }}>
          <WeekView/>
        </div>
      </div>
    </div>
  );
}

window.Calendar = Calendar;
