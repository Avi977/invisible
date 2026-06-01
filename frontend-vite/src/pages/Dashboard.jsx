// Dashboard — projects overview. Supports grid / bento / kanban / list layouts.

import { useState } from 'react';
import { I } from '../Icons.jsx';

function ProjectCard({ p, layout, navTo }) {
  const [todos, setTodos] = useState(p.todos);
  const toggle = (i) => setTodos(t => t.map((x, j) => j === i ? { ...x, done: !x.done } : x));
  const done = todos.filter(t => t.done).length;
  const statusColor = {
    "in-progress": "var(--c-term)",
    "blocked":     "#ff7a7a",
    "planning":    "var(--c-graph)",
    "shipped":     "var(--c-cal)",
  }[p.status];

  return (
    <div className="proj-card fade-in" style={{ "--p-c": p.color }}>
      <div className="proj-head">
        <div className="proj-icon">{p.code}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 className="proj-name">{p.name}</h3>
          <div className="proj-meta">
            <span style={{ color: statusColor }}>● </span>
            {p.status} · {p.branch} · {p.lastCommit}
          </div>
        </div>
        <div style={{ display: "flex", gap: 2 }}>
          <button
            className="icon-btn"
            title="View tools / workflow"
            onClick={() => navTo("tools", p.id)}
          >
            <I.Tools size={14}/>
          </button>
          <button
            className="icon-btn"
            title="Enter focus mode"
            onClick={() => navTo("focus", p.id)}
            style={{ color: "var(--p-c)" }}
          >
            <I.Target size={14}/>
          </button>
        </div>
      </div>

      {layout !== "kanban" && (
        <p className="proj-summary">{p.summary}</p>
      )}

      <div>
        <div className="card-sub">Todo · {done}/{todos.length}</div>
        <div className="proj-todo">
          {todos.slice(0, layout === "kanban" ? 2 : 4).map((t, i) => (
            <div key={i} className={"todo-row " + (t.done ? "done" : "")} onClick={() => toggle(i)}>
              <div className="check">{t.done && <I.CheckCircle size={9} stroke="#0a0b10"/>}</div>
              <span>{t.t}</span>
            </div>
          ))}
        </div>
      </div>

      {layout !== "kanban" && (
        <div className="proj-note">{p.note}</div>
      )}

      <div className="proj-foot">
        <div className="proj-progress"><div style={{ width: p.progress + "%" }}/></div>
        <span>{p.progress}%</span>
        {p.nextEvent && p.nextEvent !== "—" && (
          <span style={{ marginLeft: 8 }}>· {p.nextEvent}</span>
        )}
      </div>

      {layout !== "kanban" && (
        <div className="proj-actions">
          <button
            className="btn"
            onClick={() => navTo("tools", p.id)}
            style={{ flex: 1, justifyContent: "center" }}
          >
            <I.Tools size={12}/> Tools
          </button>
          <button
            className="btn"
            onClick={() => navTo("terminals", p.id)}
            style={{ flex: 1, justifyContent: "center" }}
          >
            <I.Terminal size={12}/> Terminal
          </button>
          <button
            className="btn accent"
            onClick={() => navTo("focus", p.id)}
            style={{ flex: 1.2, justifyContent: "center", "--accent": p.color, "--accent-soft": `color-mix(in oklab, ${p.color} 22%, transparent)` }}
          >
            <I.Target size={12}/> Focus <I.ChevronR size={11}/>
          </button>
        </div>
      )}
    </div>
  );
}

function DashHeader({ projects, dataSet }) {
  const total = projects.length;
  const active = projects.filter(p => p.status === "in-progress").length;
  const blocked = projects.filter(p => p.status === "blocked").length;
  const allTodos = projects.flatMap(p => p.todos);
  const todoOpen = allTodos.filter(t => !t.done).length;
  const now = new Date();
  const hour = now.getHours();
  const greeting = hour < 5 ? "Late night" : hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  return (
    <div style={{ marginBottom: "var(--pad-5)", display: "flex", gap: "var(--pad-4)", alignItems: "flex-end" }}>
      <div style={{ flex: 1 }}>
        <div className="mono" style={{ fontSize: 11, color: "var(--text-3)", letterSpacing: "0.12em", textTransform: "uppercase" }}>
          {now.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })} · {dataSet}
        </div>
        <h1 style={{ margin: "4px 0 0", fontSize: "calc(28px * var(--d))", fontWeight: 600, letterSpacing: "-0.025em" }}>
          {greeting}. <span style={{ color: "var(--accent)", fontStyle: "italic", fontFamily: "var(--font-mono)", fontWeight: 400 }}>{active} active</span>, <span className="dim">{blocked} blocked</span>.
        </h1>
      </div>
      <div style={{ display: "flex", gap: "var(--pad-2)" }}>
        <Stat label="Projects" value={total}/>
        <Stat label="Open todos" value={todoOpen} accent/>
        <Stat label="This week" value="14h"/>
      </div>
    </div>
  );
}

function Stat({ label, value, accent }) {
  return (
    <div className="glass" style={{ padding: "10px 16px", minWidth: 90 }}>
      <div className="mono" style={{ fontSize: 9.5, color: "var(--text-4)", letterSpacing: "0.14em", textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 600, color: accent ? "var(--accent)" : "var(--text-1)", lineHeight: 1.1, marginTop: 4 }}>{value}</div>
    </div>
  );
}

function Dashboard({ projects, layout, dataSet, navTo }) {
  if (layout === "kanban") {
    const cols = [
      { id: "planning",    title: "Planning" },
      { id: "in-progress", title: "In progress" },
      { id: "blocked",     title: "Blocked" },
      { id: "shipped",     title: "Shipped" },
    ];
    return (
      <>
        <DashHeader projects={projects} dataSet={dataSet}/>
        <div className="dash-grid layout-kanban">
          {cols.map(c => (
            <div key={c.id} className="kanban-col">
              <div className="kanban-col-title">{c.title} · {projects.filter(p => p.status === c.id).length}</div>
              {projects.filter(p => p.status === c.id).map(p => (
                <ProjectCard key={p.id} p={p} layout="kanban" navTo={navTo}/>
              ))}
            </div>
          ))}
        </div>
      </>
    );
  }

  return (
    <>
      <DashHeader projects={projects} dataSet={dataSet}/>
      <div className={"dash-grid layout-" + layout}>
        {projects.map(p => <ProjectCard key={p.id} p={p} layout={layout} navTo={navTo}/>)}
      </div>
    </>
  );
}

export default Dashboard;
