// App shell — sidebar nav + page router + Tweaks panel.

import { useState, useEffect } from 'react';
import { I } from './Icons.jsx';
import { DATA_SETS } from './Data.jsx';
import { useTweaks, TweaksPanel, TweakSection, TweakRadio, TweakSelect } from './TweaksPanel.jsx';
import AIBubble from './AiChat.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Focus from './pages/Focus.jsx';
import Folders from './pages/Folders.jsx';
import Relations from './pages/Relations.jsx';
import Terminals from './pages/Terminals.jsx';
import Tools from './pages/Tools.jsx';
import Calendar from './pages/Calendar.jsx';
import Analytics from './pages/Analytics.jsx';

const PAGES = [
  { id: "dashboard",  label: "Dashboard",   icon: "Dashboard", color: "var(--c-dash)",  badge: "3 active", Cmp: () => null },
  { id: "focus",      label: "Focus",       icon: "Target",    color: "var(--c-focus)", badge: null,       Cmp: () => null },
  { id: "folders",    label: "Folders",     icon: "Folder",    color: "var(--c-fold)",  badge: null,       Cmp: () => null },
  { id: "relations",  label: "Relations",   icon: "Graph",     color: "var(--c-graph)", badge: null,       Cmp: () => null },
  { id: "terminals",  label: "Terminals",   icon: "Terminal",  color: "var(--c-term)",  badge: "6",        Cmp: () => null },
  { id: "tools",      label: "Tools",       icon: "Tools",     color: "var(--c-tools)", badge: null,       Cmp: () => null },
  { id: "calendar",   label: "Calendar",    icon: "Calendar",  color: "var(--c-cal)",   badge: "8",        Cmp: () => null },
  { id: "analytics",  label: "Analytics",   icon: "BarChart",  color: "var(--c-anlt)",  badge: null,       Cmp: () => null },
];

const DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "default",
  "density": "comfy",
  "sidebar": "expanded",
  "mainLayout": "bento",
  "dataSet": "default"
}/*EDITMODE-END*/;

const DENSITY_VALUES = { compact: 0.88, comfy: 1.0, spacious: 1.12 };

function Sidebar({ activeId, onChange, collapsed, onToggle }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-dot"/>
        <span className="brand-text">invisible</span>
      </div>

      <div className="nav-section-title">Workspace</div>
      {PAGES.map(p => (
        <div
          key={p.id}
          className={"nav-item " + (activeId === p.id ? "active" : "")}
          style={{ "--nav-c": p.color }}
          onClick={() => onChange(p.id)}
        >
          <span className="nav-icon">
            {p.icon === "Dashboard" && <I.Dashboard size={18}/>}
            {p.icon === "Target"    && <I.Target size={18}/>}
            {p.icon === "Folder"    && <I.Folder size={18}/>}
            {p.icon === "Graph"     && <I.Graph size={18}/>}
            {p.icon === "Terminal"  && <I.Terminal size={18}/>}
            {p.icon === "Tools"     && <I.Tools size={18}/>}
            {p.icon === "Calendar"  && <I.Calendar size={18}/>}
            {p.icon === "BarChart"  && <I.BarChart size={18}/>}
          </span>
          <span className="nav-label">{p.label}</span>
          {p.badge && <span className="nav-badge">{p.badge}</span>}
        </div>
      ))}

      <div className="sidebar-spacer"/>

      <div className="nav-section-title">Recent</div>
      {[
        ["#echo / wave-jitter", "var(--c-dash)"],
        ["#lumen / RLS walker", "var(--c-fold)"],
        ["#atlas / k3s spec",   "var(--c-term)"],
      ].map(([t, c]) => (
        <div key={t} className="nav-item" style={{ "--nav-c": c, fontSize: 12, padding: "7px 12px" }}>
          <span className="nav-icon"><I.Hash size={14}/></span>
          <span className="nav-label" style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{t}</span>
        </div>
      ))}

      <div className="sidebar-footer">
        <div className="avatar">D</div>
        <div className="sidebar-footer-meta">
          <div className="sidebar-footer-name">dev@local</div>
          <div className="sidebar-footer-sub">⌘K · search</div>
        </div>
      </div>

      <button className="collapse-btn" onClick={onToggle} title={collapsed ? "Expand" : "Collapse"}>
        {collapsed ? <I.ChevronR size={14}/> : <I.ChevronL size={14}/>}
      </button>
    </aside>
  );
}

function PageHeader({ page, projects, dataSetName }) {
  const subs = {
    dashboard: `${projects.length} projects · ${projects.filter(p => p.status === "in-progress").length} active`,
    focus:     "Deep work · one task at a time",
    folders:   "3 sources · 1,204 files indexed",
    relations: "18 nodes · 22 links",
    terminals: "6 sessions · zsh",
    tools:     "Workflow editor · echo-deploy",
    calendar:  "Week of " + new Date().toLocaleDateString("en-US", { month: "long", day: "numeric" }),
    analytics: "Tokens, time and tool usage",
  };

  return (
    <header className="page-header">
      <div>
        <h1 className="page-title">
          <span className="accent">{page.label.toLowerCase()}</span>
          {page.id === "dashboard" && <span style={{ color: "var(--text-3)", fontWeight: 400, fontSize: "0.7em" }}> · {dataSetName}</span>}
        </h1>
        <div className="page-sub">{subs[page.id]}</div>
      </div>
      <div className="page-tools">
        <span className="chip"><span className="chip-dot" style={{ color: "var(--c-term)" }}/>online</span>
        <button className="icon-btn"><I.Search size={15}/></button>
        <button className="icon-btn"><I.Bell size={15}/></button>
        <button className="icon-btn"><I.Settings size={15}/></button>
      </div>
    </header>
  );
}

function App() {
  const [pageId, setPageId] = useState("dashboard");
  const [selectedProject, setSelectedProject] = useState(null); // project id, for cross-page focus
  const [t, setTweak] = useTweaks(DEFAULTS);

  const navTo = (id, projectId = null) => {
    setPageId(id);
    if (projectId) setSelectedProject(projectId);
  };

  const page = PAGES.find(p => p.id === pageId);

  // Apply accent based on current page
  const accent = page.color;
  // Apply density
  const density = DENSITY_VALUES[t.density] || 1;
  // Sidebar collapse
  const collapsed = t.sidebar === "collapsed";
  // Data set
  const dataKey = t.dataSet || "default";
  const data = DATA_SETS[dataKey] || DATA_SETS.default;
  const projects = data.projects;

  useEffect(() => {
    document.documentElement.style.setProperty("--accent", accent);
    document.documentElement.style.setProperty("--d", String(density));
  }, [accent, density]);

  return (
    <>
      <div className="bg-layer"/>
      <div className="bg-grain"/>
      <div className={"app " + (collapsed ? "collapsed" : "")} style={{ "--accent": accent }}>
        <Sidebar
          activeId={pageId}
          onChange={setPageId}
          collapsed={collapsed}
          onToggle={() => setTweak("sidebar", collapsed ? "expanded" : "collapsed")}
        />
        <main className="page" key={pageId}>
          <PageHeader page={page} projects={projects} dataSetName={data.name}/>
          <div className="page-body fade-in">
            {pageId === "dashboard"  && <Dashboard projects={projects} layout={t.mainLayout} dataSet={data.name} navTo={navTo}/>}
            {pageId === "focus"      && <Focus projects={projects} selectedProject={selectedProject} setSelectedProject={setSelectedProject}/>}
            {pageId === "folders"    && <Folders/>}
            {pageId === "relations"  && <Relations/>}
            {pageId === "terminals"  && <Terminals projects={projects} selectedProject={selectedProject} setSelectedProject={setSelectedProject}/>}
            {pageId === "tools"      && <Tools projects={projects} selectedProject={selectedProject} setSelectedProject={setSelectedProject}/>}
            {pageId === "calendar"   && <Calendar/>}
            {pageId === "analytics"  && <Analytics projects={projects}/>}
          </div>
        </main>
      </div>

      <AIBubble pageContext={page.label}/>

      <TweaksPanel title="Tweaks">
        <TweakSection label="Theme"/>
        <TweakRadio
          label="Accent"
          value={t.accent}
          onChange={(v) => setTweak("accent", v)}
          options={[
            { label: "Per page", value: "default" },
            { label: "Amber",    value: "var(--c-dash)" },
            { label: "Cyan",     value: "var(--c-fold)" },
          ]}
        />
        <TweakRadio
          label="Density"
          value={t.density}
          onChange={(v) => setTweak("density", v)}
          options={["compact", "comfy", "spacious"]}
        />
        <TweakRadio
          label="Sidebar"
          value={t.sidebar}
          onChange={(v) => setTweak("sidebar", v)}
          options={["expanded", "collapsed"]}
        />

        <TweakSection label="Dashboard"/>
        <TweakSelect
          label="Layout"
          value={t.mainLayout}
          onChange={(v) => setTweak("mainLayout", v)}
          options={[
            { label: "Bento (asymmetric)", value: "bento" },
            { label: "Grid (uniform)",     value: "grid" },
            { label: "Kanban (by status)", value: "kanban" },
            { label: "List (one per row)", value: "list" },
          ]}
        />
        <TweakSelect
          label="Mock data"
          value={t.dataSet}
          onChange={(v) => setTweak("dataSet", v)}
          options={[
            { label: "Personal projects", value: "default" },
            { label: "Client work",       value: "client" },
          ]}
        />
      </TweaksPanel>
    </>
  );
}

export default App;
