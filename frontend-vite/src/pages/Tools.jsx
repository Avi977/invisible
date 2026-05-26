// Tools — n8n-style node graph, scoped per project.
// Flow: choose project → see that project's workflow → drag/drop new tools onto canvas.

import { useState, useRef, useEffect, useMemo } from 'react';
import { I } from '../Icons.jsx';
import { TOOL_WORKFLOWS } from '../Data.jsx';

const PALETTE = [
  { kind: "ai",       label: "AI",         items: [
    { type: "claude",   name: "Claude Sonnet 4.5", code: "AI", c: "#f5b343", body: "anthropic" },
    { type: "haiku",    name: "Claude Haiku 4.5",  code: "AI", c: "#f5b343", body: "anthropic" },
    { type: "whisper",  name: "Whisper v3",        code: "AI", c: "#f5b343", body: "openai" },
    { type: "embed",    name: "Voyage Embeddings", code: "AI", c: "#f5b343", body: "voyage-3" },
  ]},
  { kind: "data",     label: "Data",       items: [
    { type: "postgres", name: "Postgres",       code: "DB", c: "#5cc8ff", body: "pg-pool" },
    { type: "redis",    name: "Redis",          code: "DB", c: "#5cc8ff", body: "queue" },
    { type: "s3",       name: "S3 Bucket",      code: "S3", c: "#5cc8ff", body: "echo-uploads" },
  ]},
  { kind: "api",      label: "APIs",       items: [
    { type: "stripe",   name: "Stripe",   code: "$",  c: "#b794ff", body: "billing" },
    { type: "github",   name: "GitHub",   code: "GH", c: "#b794ff", body: "webhooks" },
    { type: "resend",   name: "Resend",   code: "@",  c: "#b794ff", body: "transactional" },
    { type: "slack",    name: "Slack",    code: "#",  c: "#b794ff", body: "#alerts" },
  ]},
  { kind: "logic",    label: "Logic",      items: [
    { type: "if",       name: "Condition",  code: "IF", c: "#5ee0c8", body: "branch" },
    { type: "switch",   name: "Switch",     code: "SW", c: "#5ee0c8", body: "route" },
    { type: "code",     name: "Run Code",   code: "JS", c: "#5ee0c8", body: "node 20" },
  ]},
];

const NODE_W = 180;

function ToolsCanvas({ initialNodes, initialEdges, accentC }) {
  const [nodes, setNodes] = useState(initialNodes);
  const [edges, setEdges] = useState(initialEdges);
  const [drag, setDrag] = useState(null);
  const [connecting, setConnecting] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const canvasRef = useRef(null);
  const [selected, setSelected] = useState(null);

  // Reset when project changes
  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
    setSelected(null);
  }, [initialNodes, initialEdges]);

  useEffect(() => {
    const move = (e) => {
      if (!canvasRef.current) return;
      const rect = canvasRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      setMousePos({ x, y });
      if (drag) {
        setNodes(ns => ns.map(n => n.id === drag.id ? { ...n, x: x - drag.dx, y: y - drag.dy } : n));
      }
    };
    const up = () => { setDrag(null); setConnecting(null); };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    return () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
  }, [drag]);

  const startDrag = (e, n) => {
    if (e.target.classList.contains("tool-port")) return;
    e.preventDefault();
    const rect = canvasRef.current.getBoundingClientRect();
    setDrag({ id: n.id, dx: (e.clientX - rect.left) - n.x, dy: (e.clientY - rect.top) - n.y });
    setSelected(n.id);
  };

  const startConnect = (e, n) => { e.stopPropagation(); setConnecting({ from: n.id }); };
  const endConnect = (e, n) => {
    e.stopPropagation();
    if (connecting && connecting.from !== n.id) {
      const exists = edges.some(ed => ed.from === connecting.from && ed.to === n.id);
      if (!exists) setEdges(es => [...es, { from: connecting.from, to: n.id }]);
    }
    setConnecting(null);
  };

  const onDrop = (e) => {
    e.preventDefault();
    const data = e.dataTransfer.getData("application/x-tool");
    if (!data) return;
    const t = JSON.parse(data);
    const rect = canvasRef.current.getBoundingClientRect();
    const newId = "n" + Math.random().toString(36).slice(2, 7);
    setNodes(ns => [...ns, { ...t, id: newId, x: e.clientX - rect.left, y: e.clientY - rect.top }]);
  };
  const onDragOver = (e) => e.preventDefault();

  const removeSelected = () => {
    if (!selected) return;
    setNodes(ns => ns.filter(n => n.id !== selected));
    setEdges(es => es.filter(e => e.from !== selected && e.to !== selected));
    setSelected(null);
  };

  const edgePath = (x1, y1, x2, y2) => {
    const dx = Math.max(40, Math.abs(x2 - x1) * 0.5);
    return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
  };

  const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]));

  return (
    <div
      className="tools-canvas"
      ref={canvasRef}
      onDrop={onDrop}
      onDragOver={onDragOver}
      onClick={(e) => { if (e.target === canvasRef.current) setSelected(null); }}
    >
      <svg className="tools-svg">
        <defs>
          <linearGradient id="wire" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%"  stopColor="rgba(245, 111, 177, 0.85)"/>
            <stop offset="100%" stopColor="rgba(94, 224, 200, 0.85)"/>
          </linearGradient>
          <linearGradient id="wire-dim" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%"  stopColor="rgba(245, 111, 177, 0.35)"/>
            <stop offset="100%" stopColor="rgba(94, 224, 200, 0.35)"/>
          </linearGradient>
        </defs>
        {edges.map((ed, i) => {
          const a = nodeMap[ed.from], b = nodeMap[ed.to];
          if (!a || !b) return null;
          const x1 = a.x + NODE_W / 2, y1 = a.y;
          const x2 = b.x - NODE_W / 2, y2 = b.y;
          const active = selected && (selected === ed.from || selected === ed.to);
          return (
            <g key={i}>
              <path d={edgePath(x1, y1, x2, y2)} stroke={active ? "url(#wire)" : "url(#wire-dim)"} strokeWidth={active ? 2.2 : 1.6} fill="none"/>
              <circle r="2.5" fill="#fff" opacity="0.9">
                <animateMotion dur="2.8s" repeatCount="indefinite" path={edgePath(x1, y1, x2, y2)}/>
              </circle>
            </g>
          );
        })}
        {connecting && nodeMap[connecting.from] && (() => {
          const a = nodeMap[connecting.from];
          const x1 = a.x + NODE_W / 2, y1 = a.y;
          return <path d={edgePath(x1, y1, mousePos.x, mousePos.y)} stroke="rgba(255,255,255,0.5)" strokeWidth="1.5" strokeDasharray="4 4" fill="none"/>;
        })()}
      </svg>

      {nodes.map(n => (
        <div
          key={n.id}
          className={"tool-node " + (drag?.id === n.id ? "dragging" : "")}
          style={{
            left: n.x, top: n.y, width: NODE_W,
            "--n-c": n.c,
            outline: selected === n.id ? "1px solid var(--n-c)" : "none",
            boxShadow: selected === n.id
              ? "0 14px 40px -16px rgba(0,0,0,0.6), 0 0 24px color-mix(in oklab, var(--n-c) 40%, transparent)"
              : undefined,
          }}
          onMouseDown={(e) => startDrag(e, n)}
        >
          <div className="tool-node-head">
            <div className="tool-node-ico">{n.code}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="tool-node-name" style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{n.name}</div>
            </div>
          </div>
          <div className="tool-node-body">{n.body}</div>
          <div className="tool-port in" onMouseUp={(e) => endConnect(e, n)}/>
          <div className="tool-port out" onMouseDown={(e) => startConnect(e, n)}/>
        </div>
      ))}

      <div className="tools-toolbar">
        <button className="btn" style={{ padding: "5px 10px", fontSize: 11 }}><I.Play size={11}/> Run</button>
        <button className="btn" style={{ padding: "5px 10px", fontSize: 11 }} onClick={removeSelected} disabled={!selected}>
          Delete
        </button>
        <span className="chip mono" style={{ fontSize: 10 }}>{nodes.length} nodes · {edges.length} wires</span>
      </div>
    </div>
  );
}

function ProjectPicker({ projects, onPick }) {
  return (
    <div className="proj-picker">
      <div className="proj-picker-head">
        <div className="mono" style={{ fontSize: 10.5, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--text-3)" }}>
          Choose a project
        </div>
        <h2 style={{ margin: "6px 0 0", fontWeight: 600, fontSize: "calc(22px * var(--d))", letterSpacing: "-0.02em" }}>
          Which workflow are you working on?
        </h2>
        <p className="muted" style={{ fontSize: 12.5, maxWidth: 480, lineHeight: 1.55, marginTop: 8 }}>
          Tool connections — APIs, AI models, databases, logic — are scoped to a project so each one has its own graph.
        </p>
      </div>
      <div className="proj-picker-grid">
        {projects.map(p => {
          const wf = TOOL_WORKFLOWS[p.id];
          const has = !!wf;
          return (
            <button
              key={p.id}
              className="proj-picker-card"
              style={{ "--p-c": p.color }}
              onClick={() => onPick(p.id)}
            >
              <div className="proj-icon" style={{ width: 32, height: 32 }}>{p.code}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{p.name}</div>
                <div className="mono" style={{ fontSize: 10.5, color: "var(--text-3)", marginTop: 2 }}>
                  {has ? `${wf.nodes.length} nodes · ${wf.edges.length} wires` : "no workflow yet"}
                </div>
              </div>
              <I.ChevronR size={14} style={{ color: "var(--p-c)" }}/>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Tools({ projects, selectedProject, setSelectedProject }) {
  const projId = selectedProject && projects.some(p => p.id === selectedProject) ? selectedProject : null;

  if (!projId) {
    return <ProjectPicker projects={projects} onPick={setSelectedProject}/>;
  }

  const project = projects.find(p => p.id === projId);
  const wf = TOOL_WORKFLOWS[projId] || { name: `${project.name} · new workflow`, nodes: [], edges: [] };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--pad-3)", height: "100%" }}>
      {/* Project switcher tabs */}
      <div className="proj-tabs">
        <button
          className="proj-tab"
          onClick={() => setSelectedProject(null)}
          title="Back to project picker"
          style={{ flex: "0 0 auto" }}
        >
          <I.ChevronL size={14}/>
        </button>
        {projects.map(p => (
          <button
            key={p.id}
            className={"proj-tab " + (p.id === projId ? "active" : "")}
            onClick={() => setSelectedProject(p.id)}
            style={{ "--p-c": p.color }}
          >
            <span className="proj-tab-dot" style={{ background: p.color }}/>
            {p.name}
          </button>
        ))}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          <span className="chip mono" style={{ fontSize: 10 }}>{wf.name}</span>
        </div>
      </div>

      <div className="tools-layout" style={{ flex: 1, minHeight: 0 }}>
        <div className="tools-palette">
          <div className="muted mono" style={{ fontSize: 10.5, padding: "4px 0 var(--pad-2)" }}>
            Drag onto canvas →
          </div>
          {PALETTE.map(g => (
            <div key={g.kind}>
              <div className="palette-section">{g.label}</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 6 }}>
                {g.items.map(item => (
                  <div
                    key={item.type}
                    className="palette-item"
                    draggable
                    onDragStart={(e) => e.dataTransfer.setData("application/x-tool", JSON.stringify(item))}
                    style={{ "--p-c": item.c }}
                  >
                    <div className="palette-ico">{item.code}</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="palette-name">{item.name}</div>
                      <div className="palette-meta">{item.body}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        <ToolsCanvas
          key={projId /* force fresh canvas per project */}
          initialNodes={wf.nodes}
          initialEdges={wf.edges}
          accentC={project.color}
        />
      </div>
    </div>
  );
}

export default Tools;
