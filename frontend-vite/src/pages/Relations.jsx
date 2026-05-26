// Relationships — Obsidian-style force-directed graph showing how projects,
// notes, tools, and repos connect. Drag nodes around; edges animate.

import { useState, useRef, useEffect } from 'react';
import { I } from '../Icons.jsx';

// Node graph data — projects in the center, surrounding nodes are notes/tools/repos
const GRAPH = {
  nodes: [
    // Projects (center)
    { id: "echo",    label: "Echo",    kind: "project", x: 380, y: 320, color: "#f5b343" },
    { id: "lumen",   label: "Lumen",   kind: "project", x: 720, y: 280, color: "#5cc8ff" },
    { id: "drift",   label: "Drift",   kind: "project", x: 540, y: 480, color: "#b794ff" },
    { id: "rune",    label: "Rune",    kind: "project", x: 880, y: 480, color: "#f56fb1" },
    { id: "atlas",   label: "Atlas",   kind: "project", x: 240, y: 540, color: "#4ade80" },
    // Notes (Obsidian)
    { id: "n-arch",     label: "Architecture",  kind: "note", x: 200, y: 200, color: "#8aa9ff" },
    { id: "n-jitter",   label: "wave-jitter",   kind: "note", x: 480, y: 180, color: "#8aa9ff" },
    { id: "n-rls",      label: "RLS walker",    kind: "note", x: 860, y: 160, color: "#8aa9ff" },
    { id: "n-pairings", label: "Type pairings", kind: "note", x: 1020, y: 360, color: "#8aa9ff" },
    { id: "n-daily",    label: "Daily 05/24",   kind: "note", x: 340, y: 660, color: "#8aa9ff" },
    { id: "n-cost",     label: "Hetzner cost",  kind: "note", x: 120, y: 380, color: "#8aa9ff" },
    // Tools / services
    { id: "t-claude",  label: "Claude",   kind: "tool", x: 660, y: 80,  color: "#f5b343" },
    { id: "t-whisper", label: "Whisper",  kind: "tool", x: 280, y: 80,  color: "#f5b343" },
    { id: "t-stripe",  label: "Stripe",   kind: "tool", x: 80,  y: 280, color: "#f5b343" },
    { id: "t-resend",  label: "Resend",   kind: "tool", x: 700, y: 620, color: "#f5b343" },
    // Repos
    { id: "r-echo",   label: "@you/echo",   kind: "repo", x: 460, y: 380, color: "#5ee0c8" },
    { id: "r-lumen",  label: "@you/lumen",  kind: "repo", x: 800, y: 360, color: "#5ee0c8" },
    { id: "r-drift",  label: "@you/drift",  kind: "repo", x: 580, y: 580, color: "#5ee0c8" },
    { id: "r-ferry",  label: "@you/ferry",  kind: "repo", x: 60,  y: 600, color: "#5ee0c8" },
  ],
  edges: [
    ["echo","n-arch"], ["echo","n-jitter"], ["echo","r-echo"],
    ["echo","t-whisper"], ["echo","t-claude"], ["echo","t-stripe"],
    ["lumen","n-rls"], ["lumen","r-lumen"], ["lumen","t-claude"],
    ["drift","echo"], ["drift","t-resend"], ["drift","r-drift"],
    ["rune","t-claude"], ["rune","n-pairings"],
    ["atlas","n-cost"], ["atlas","r-ferry"],
    ["echo","n-daily"], ["lumen","n-daily"], ["drift","n-daily"],
    ["n-arch","n-jitter"],
  ],
};

function RelationsGraph() {
  const [nodes, setNodes] = useState(GRAPH.nodes);
  const [drag, setDrag] = useState(null);
  const [hover, setHover] = useState(null);
  const [filter, setFilter] = useState({ project: true, note: true, tool: true, repo: true });
  const wrapRef = useRef(null);

  const visible = nodes.filter(n => filter[n.kind]);
  const visibleIds = new Set(visible.map(n => n.id));
  const visibleEdges = GRAPH.edges.filter(([a,b]) => visibleIds.has(a) && visibleIds.has(b));

  useEffect(() => {
    if (!drag) return;
    const move = (e) => {
      const rect = wrapRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left - drag.dx;
      const y = e.clientY - rect.top - drag.dy;
      setNodes(ns => ns.map(n => n.id === drag.id ? { ...n, x, y } : n));
    };
    const up = () => setDrag(null);
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    return () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
  }, [drag]);

  const startDrag = (e, n) => {
    const rect = wrapRef.current.getBoundingClientRect();
    setDrag({ id: n.id, dx: (e.clientX - rect.left) - n.x, dy: (e.clientY - rect.top) - n.y });
  };

  const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]));

  // Highlight edges and connected nodes when hovering
  const isEdgeActive = ([a,b]) => hover && (a === hover || b === hover);
  const isNodeActive = (id) => {
    if (!hover) return true;
    if (id === hover) return true;
    return visibleEdges.some(([a,b]) => (a === hover && b === id) || (b === hover && a === id));
  };

  return (
    <div className="graph-wrap" ref={wrapRef}>
      <svg className="graph-svg">
        <defs>
          <linearGradient id="edge" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="rgba(255,255,255,0.25)"/>
            <stop offset="100%" stopColor="rgba(255,255,255,0.05)"/>
          </linearGradient>
        </defs>
        {visibleEdges.map(([a,b], i) => {
          const na = nodeMap[a], nb = nodeMap[b];
          if (!na || !nb) return null;
          const active = isEdgeActive([a,b]);
          return (
            <line
              key={i}
              x1={na.x} y1={na.y} x2={nb.x} y2={nb.y}
              stroke={active ? "rgba(180, 210, 255, 0.7)" : "rgba(255,255,255,0.10)"}
              strokeWidth={active ? 1.5 : 1}
              style={{ transition: "stroke 200ms, stroke-width 200ms" }}
            />
          );
        })}
      </svg>

      {visible.map(n => (
        <div
          key={n.id}
          className={"graph-node kind-" + n.kind + (drag?.id === n.id ? " dragging" : "")}
          style={{
            left: n.x, top: n.y,
            "--n-c": n.color,
            opacity: isNodeActive(n.id) ? 1 : 0.32,
            transition: drag?.id === n.id ? "none" : "opacity 200ms",
          }}
          onMouseDown={(e) => startDrag(e, n)}
          onMouseEnter={() => setHover(n.id)}
          onMouseLeave={() => setHover(null)}
        >
          <span className="n-dot"/>
          {n.label}
        </div>
      ))}

      <div className="graph-legend">
        <div style={{ color: "var(--text-2)", marginBottom: 4 }}>FILTER</div>
        {[
          ["project", "Projects",  "#f5b343"],
          ["note",    "Notes",     "#8aa9ff"],
          ["tool",    "Tools",     "#f5b343"],
          ["repo",    "Repos",     "#5ee0c8"],
        ].map(([k, label, c]) => (
          <div key={k} className="legend-row" style={{ cursor: "pointer", opacity: filter[k] ? 1 : 0.4 }}
               onClick={() => setFilter(f => ({ ...f, [k]: !f[k] }))}>
            <span className="legend-dot" style={{ color: c }}/>
            <span>{label}</span>
          </div>
        ))}
      </div>

      <div className="graph-controls">
        <button className="icon-btn" title="Reset"><I.Sparkles size={14}/></button>
        <button className="icon-btn" title="Zoom in"><I.Plus size={14}/></button>
      </div>
    </div>
  );
}

function Relations() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--pad-3)", height: "100%" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span className="chip accent"><span className="chip-dot"/>Obsidian vault · linked</span>
        <span className="chip"><span className="chip-dot" style={{ color: "var(--c-cal)" }}/>18 nodes · 22 links</span>
        <span className="muted mono" style={{ fontSize: 11, marginLeft: 8 }}>Drag nodes · hover to focus subgraph</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          <button className="btn">Force layout</button>
          <button className="btn">Tag view</button>
        </div>
      </div>
      <div style={{ flex: 1, minHeight: 0 }}>
        <RelationsGraph/>
      </div>
    </div>
  );
}

export default Relations;
