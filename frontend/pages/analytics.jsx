// Analytics — tokens used per project + time spent, plus tool / action breakdowns.
// Range filter: 7d / 30d. Project filter: all / one.

const { useState: useStateA, useMemo: useMemoA } = React;

const PROJECT_ORDER = ["echo", "lumen", "drift", "atlas", "rune", "ferry"];

// Helpers
const fmtK = (n) => {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(n >= 10_000_000 ? 1 : 2) + "M";
  if (n >= 1_000)     return (n / 1_000).toFixed(n >= 10_000 ? 0 : 1) + "k";
  return String(n);
};
const fmtH = (h) => h >= 100 ? `${Math.round(h)}h` : `${h.toFixed(1)}h`;
const sum = (arr) => arr.reduce((a, b) => a + b, 0);

// Slice last N days from a 30-day series
const lastN = (arr, n) => arr.slice(-n);

function StatCard({ label, value, sub, accent, icon }) {
  return (
    <div className="anlt-stat">
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {icon && <span style={{ color: accent || "var(--accent)" }}>{icon}</span>}
        <div className="mono" style={{ fontSize: 10, color: "var(--text-4)", letterSpacing: "0.16em", textTransform: "uppercase" }}>{label}</div>
      </div>
      <div className="anlt-stat-value" style={{ color: accent || "var(--text-1)" }}>{value}</div>
      {sub && <div className="mono" style={{ fontSize: 10.5, color: "var(--text-3)" }}>{sub}</div>}
    </div>
  );
}

function StackedAreaChart({ data, range, projects, projectMap, mode = "tokens" }) {
  // data: { projectId: [..n values..] } already sliced to range
  const days = range;
  const W = 800, H = 200, PAD_L = 36, PAD_R = 10, PAD_T = 14, PAD_B = 24;
  const innerW = W - PAD_L - PAD_R;
  const innerH = H - PAD_T - PAD_B;

  // Compute cumulative stack per day
  const stacks = useMemoA(() => {
    return Array.from({ length: days }, (_, i) => {
      let cum = 0;
      return projects.map(pid => {
        const v = data[pid]?.[i] || 0;
        const seg = { start: cum, end: cum + v, value: v, pid };
        cum += v;
        return seg;
      }).concat([{ totalEnd: cum }]);
    });
  }, [data, days, projects.join(",")]);

  const maxY = Math.max(1, ...stacks.map(s => s[s.length - 1].totalEnd));
  const xAt = (i) => PAD_L + (i / Math.max(1, days - 1)) * innerW;
  const yAt = (v) => PAD_T + innerH - (v / maxY) * innerH;

  const pathFor = (pid, idx) => {
    const top = stacks.map((s, i) => `${xAt(i)},${yAt(s[idx].end)}`).join(" L ");
    const bot = stacks.slice().reverse().map((s, i) => {
      const realIdx = days - 1 - i;
      return `${xAt(realIdx)},${yAt(s[idx].start)}`;
    }).join(" L ");
    return `M ${top} L ${bot} Z`;
  };

  // Y-axis ticks
  const ticks = 4;
  const tickValues = Array.from({ length: ticks + 1 }, (_, i) => (maxY * i) / ticks);

  // X labels — every Nth day
  const xStep = days >= 20 ? Math.ceil(days / 6) : Math.ceil(days / 7);
  const dayLabels = Array.from({ length: days }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - (days - 1 - i));
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  });

  const totalToday = stacks[stacks.length - 1]?.[stacks[0].length - 1]?.totalEnd || 0;

  return (
    <div className="anlt-card" style={{ gridColumn: "1 / -1" }}>
      <div className="anlt-card-head">
        <div>
          <div className="anlt-card-title">{mode === "tokens" ? "Tokens over time" : "Time over time"}</div>
          <div className="muted mono" style={{ fontSize: 10.5, marginTop: 2 }}>
            stacked by project · last {days} days
          </div>
        </div>
        <div className="anlt-legend">
          {projects.map(pid => (
            <div key={pid} className="anlt-legend-item">
              <span style={{ background: projectMap[pid].color }}/>
              {projectMap[pid].name}
            </div>
          ))}
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: "100%", height: 220 }}>
        {tickValues.map((v, i) => (
          <g key={i}>
            <line x1={PAD_L} x2={W - PAD_R} y1={yAt(v)} y2={yAt(v)} stroke="rgba(255,255,255,0.06)" strokeDasharray={i ? "2 4" : ""}/>
            <text x={PAD_L - 6} y={yAt(v) + 3} textAnchor="end" fontFamily="var(--font-mono)" fontSize="9" fill="var(--text-4)">
              {mode === "tokens" ? fmtK(v * 1000) : fmtH(v)}
            </text>
          </g>
        ))}

        {projects.map((pid, idx) => {
          const c = projectMap[pid].color;
          return (
            <g key={pid}>
              <defs>
                <linearGradient id={`grad-${pid}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"  stopColor={c} stopOpacity="0.65"/>
                  <stop offset="100%" stopColor={c} stopOpacity="0.18"/>
                </linearGradient>
              </defs>
              <path d={pathFor(pid, idx)} fill={`url(#grad-${pid})`} stroke={c} strokeWidth="1" strokeOpacity="0.5"/>
            </g>
          );
        })}

        {dayLabels.map((d, i) => i % xStep === 0 && (
          <text key={i} x={xAt(i)} y={H - 6} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="9" fill="var(--text-4)">
            {d}
          </text>
        ))}
      </svg>
    </div>
  );
}

function HorizontalBars({ title, items, max, format, accentByItem }) {
  // items: [{ id, label, value, color }]
  const maxV = max || Math.max(1, ...items.map(i => i.value));
  return (
    <div className="anlt-card">
      <div className="anlt-card-title">{title}</div>
      <div className="anlt-bars">
        {items.map(it => (
          <div key={it.id} className="anlt-bar-row">
            <div className="anlt-bar-label">
              {it.color && <span className="anlt-bar-dot" style={{ background: it.color }}/>}
              {it.label}
            </div>
            <div className="anlt-bar-track">
              <div className="anlt-bar-fill"
                   style={{
                     width: `${(it.value / maxV) * 100}%`,
                     background: it.color || "var(--c-anlt)",
                     boxShadow: it.color ? `0 0 8px ${it.color}` : `0 0 8px var(--c-anlt)`,
                   }}/>
            </div>
            <div className="anlt-bar-value">{format(it.value)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ActionsTable({ rows, projectColor }) {
  const max = Math.max(1, ...rows.map(r => r.tokens));
  return (
    <div className="anlt-card">
      <div className="anlt-card-title">Top actions by tokens</div>
      <div className="muted mono" style={{ fontSize: 10.5, marginBottom: 10 }}>
        what cost the most this period
      </div>
      <div className="anlt-actions">
        <div className="anlt-actions-head">
          <span>Action</span>
          <span>Tool</span>
          <span style={{ textAlign: "right" }}>Calls</span>
          <span style={{ textAlign: "right" }}>Tokens</span>
        </div>
        {rows.map((r, i) => (
          <div key={i} className="anlt-actions-row">
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className="anlt-rank">{String(i + 1).padStart(2, "0")}</span>
              {r.name}
            </span>
            <span className="muted">{r.tool}</span>
            <span className="mono" style={{ textAlign: "right", color: "var(--text-2)" }}>{fmtK(r.calls)}</span>
            <span style={{ textAlign: "right", display: "flex", alignItems: "center", gap: 8, justifyContent: "flex-end" }}>
              <div className="anlt-mini-bar">
                <div style={{ width: `${(r.tokens / max) * 100}%`, background: projectColor || "var(--c-anlt)" }}/>
              </div>
              <span className="mono" style={{ color: "var(--text-1)", fontWeight: 500, minWidth: 50, textAlign: "right" }}>{fmtK(r.tokens)}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Analytics({ projects }) {
  const [range, setRange] = useStateA(30);          // days
  const [projFilter, setProjFilter] = useStateA("all"); // "all" or project id
  const [mode, setMode] = useStateA("tokens");      // "tokens" or "time"

  const projectMap = Object.fromEntries(projects.map(p => [p.id, p]));
  const activeProjects = PROJECT_ORDER.filter(pid => projectMap[pid]);

  // Active project list for charts
  const visibleProjects = projFilter === "all" ? activeProjects : [projFilter];

  // Sliced data
  const tokenData = Object.fromEntries(activeProjects.map(pid => [pid, lastN(ANALYTICS.tokensByDay[pid] || [], range)]));
  const timeData  = Object.fromEntries(activeProjects.map(pid => [pid, lastN(ANALYTICS.timeByDay[pid] || [], range)]));

  // Totals
  const totalTokensK = sum(visibleProjects.flatMap(pid => tokenData[pid] || []));
  const totalHours   = sum(visibleProjects.flatMap(pid => timeData[pid] || []));
  const prevTokensK  = sum(visibleProjects.flatMap(pid => {
    const full = ANALYTICS.tokensByDay[pid] || [];
    return full.slice(-range * 2, -range);
  }));
  const tokenDelta = prevTokensK ? Math.round(((totalTokensK - prevTokensK) / prevTokensK) * 100) : 0;
  const avgPerDay = Math.round((totalTokensK * 1000) / range);

  // Top project by tokens (current window)
  const projTotals = activeProjects.map(pid => ({ pid, tokens: sum(tokenData[pid] || []) * 1000, time: sum(timeData[pid] || []) }));
  const topProj = projTotals.slice().sort((a, b) => b.tokens - a.tokens)[0];

  // Tool breakdown (aggregated across visible projects)
  const toolAgg = (() => {
    const m = new Map();
    visibleProjects.forEach(pid => {
      (ANALYTICS.toolBreakdown[pid] || []).forEach(t => {
        const key = t.name;
        const cur = m.get(key) || { id: key, label: key, value: 0, color: t.c };
        cur.value += t.tokens;
        m.set(key, cur);
      });
    });
    return Array.from(m.values()).sort((a, b) => b.value - a.value).filter(t => t.value > 0).slice(0, 6);
  })();

  // Top actions (aggregated across visible projects)
  const actionRows = (() => {
    const all = visibleProjects.flatMap(pid => ANALYTICS.topActions[pid] || []);
    return all.slice().sort((a, b) => b.tokens - a.tokens).slice(0, 8);
  })();

  return (
    <div className="anlt">
      {/* Filter bar */}
      <div className="anlt-filters">
        <div className="anlt-filter-group">
          {[7, 14, 30].map(d => (
            <button key={d} className={"anlt-pill " + (range === d ? "active" : "")} onClick={() => setRange(d)}>
              {d}d
            </button>
          ))}
        </div>

        <div className="anlt-filter-group">
          <button className={"anlt-pill " + (projFilter === "all" ? "active" : "")} onClick={() => setProjFilter("all")}>
            All projects
          </button>
          {activeProjects.map(pid => (
            <button
              key={pid}
              className={"anlt-pill " + (projFilter === pid ? "active" : "")}
              onClick={() => setProjFilter(pid)}
              style={{ "--p-c": projectMap[pid].color }}
            >
              <span className="anlt-pill-dot" style={{ background: projectMap[pid].color }}/>
              {projectMap[pid].name}
            </button>
          ))}
        </div>

        <div className="anlt-filter-group" style={{ marginLeft: "auto" }}>
          <button className={"anlt-pill " + (mode === "tokens" ? "active" : "")} onClick={() => setMode("tokens")}>
            <I.Coin size={11}/> Tokens
          </button>
          <button className={"anlt-pill " + (mode === "time" ? "active" : "")} onClick={() => setMode("time")}>
            <I.Clock size={11}/> Time
          </button>
        </div>
      </div>

      {/* Stat strip */}
      <div className="anlt-stats">
        <StatCard
          label="Total tokens"
          value={fmtK(totalTokensK * 1000)}
          sub={<>
            <span style={{ color: tokenDelta >= 0 ? "var(--c-term)" : "#ff7a7a" }}>
              {tokenDelta >= 0 ? "↗" : "↘"} {Math.abs(tokenDelta)}%
            </span>
            <span> vs prev {range}d</span>
          </>}
          accent="var(--c-anlt)"
          icon={<I.Coin size={14}/>}
        />
        <StatCard
          label="Time spent"
          value={fmtH(totalHours)}
          sub={`avg ${(totalHours / range).toFixed(1)}h/day`}
          accent="var(--c-graph)"
          icon={<I.Clock size={14}/>}
        />
        <StatCard
          label="Avg tokens / day"
          value={fmtK(avgPerDay)}
          sub={`${Math.round(avgPerDay / 1000)}k typical`}
          accent="var(--c-fold)"
          icon={<I.TrendUp size={14}/>}
        />
        <StatCard
          label="Top project"
          value={topProj ? projectMap[topProj.pid].name : "—"}
          sub={topProj ? `${fmtK(topProj.tokens)} tokens · ${fmtH(topProj.time)}` : ""}
          accent={topProj ? projectMap[topProj.pid].color : undefined}
          icon={<I.Star size={14}/>}
        />
      </div>

      {/* Charts */}
      <div className="anlt-grid">
        <StackedAreaChart
          data={mode === "tokens" ? tokenData : timeData}
          range={range}
          projects={visibleProjects}
          projectMap={projectMap}
          mode={mode}
        />

        <HorizontalBars
          title="Tokens by project"
          items={projTotals
            .slice().sort((a, b) => b.tokens - a.tokens)
            .map(t => ({ id: t.pid, label: projectMap[t.pid].name, value: t.tokens, color: projectMap[t.pid].color }))}
          format={fmtK}
        />

        <HorizontalBars
          title="Time spent by project"
          items={projTotals
            .slice().sort((a, b) => b.time - a.time)
            .map(t => ({ id: t.pid, label: projectMap[t.pid].name, value: t.time, color: projectMap[t.pid].color }))}
          format={fmtH}
        />

        <HorizontalBars
          title="Most-used tools"
          items={toolAgg}
          format={fmtK}
        />

        <ActionsTable
          rows={actionRows}
          projectColor={projFilter !== "all" ? projectMap[projFilter]?.color : undefined}
        />
      </div>
    </div>
  );
}

window.Analytics = Analytics;
