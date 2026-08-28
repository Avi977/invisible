import { useEffect, useMemo, useRef, useState } from 'react';
import { I } from '../Icons.jsx';
import { apiJson, postJson } from '../lib/api.js';

const COLORS = {
  project: "#f5b343",
  doc: "#8aa9ff",
  module: "#5ee0c8",
  endpoint: "#5cc8ff",
  tool: "#f5b343",
  repo: "#5ee0c8",
};

function kindFor(type) {
  if (type === "doc") return "doc";
  if (type === "endpoint") return "endpoint";
  if (type === "project") return "project";
  if (type === "repo") return "repo";
  if (type === "tool") return "tool";
  return "module";
}

const MAX_RENDER_NODES = 450;
const MAX_RENDER_EDGES = 1200;

function graphCounts(graph) {
  return {
    nodes: Array.isArray(graph?.nodes) ? graph.nodes.length : 0,
    edges: Array.isArray(graph?.edges) ? graph.edges.length : 0,
  };
}

function displayGraphFor(graph) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  const edges = Array.isArray(graph?.edges) ? graph.edges : [];
  if (nodes.length <= MAX_RENDER_NODES && edges.length <= MAX_RENDER_EDGES) {
    return { nodes, edges, limited: false };
  }

  const degree = new Map();
  edges.forEach((edge) => {
    if (!edge?.from || !edge?.to) return;
    degree.set(edge.from, (degree.get(edge.from) || 0) + 1);
    degree.set(edge.to, (degree.get(edge.to) || 0) + 1);
  });
  const typePriority = { project: 6, repo: 5, endpoint: 4, module: 3, tool: 2, doc: 1 };
  const selected = nodes
    .map((node, index) => ({ node, index }))
    .sort((a, b) => {
      const ap = typePriority[kindFor(a.node.type || a.node.kind)] || 0;
      const bp = typePriority[kindFor(b.node.type || b.node.kind)] || 0;
      if (bp !== ap) return bp - ap;
      return (degree.get(b.node.id) || 0) - (degree.get(a.node.id) || 0) || a.index - b.index;
    })
    .slice(0, MAX_RENDER_NODES)
    .map(({ node }) => node);
  const selectedIds = new Set(selected.map((node) => node.id));
  const selectedEdges = edges
    .filter((edge) => selectedIds.has(edge?.from) && selectedIds.has(edge?.to))
    .slice(0, MAX_RENDER_EDGES);
  return { nodes: selected, edges: selectedEdges, limited: true };
}

function layoutNodes(rawNodes) {
  const count = Math.max(rawNodes.length, 1);
  const cx = 560, cy = 330, rx = 430, ry = 250;
  return rawNodes.map((n, i) => {
    const kind = kindFor(n.type || n.kind);
    const angle = (Math.PI * 2 * i) / count;
    const jitter = 0.78 + ((i % 7) * 0.045);
    return {
      id: String(n.id),
      label: n.label || n.id,
      kind,
      x: n.x ?? cx + Math.cos(angle) * rx * jitter,
      y: n.y ?? cy + Math.sin(angle) * ry * jitter,
      color: COLORS[kind] || "#b794ff",
    };
  });
}

function RelationsGraph({ graph }) {
  const [nodes, setNodes] = useState(() => layoutNodes(graph.nodes || []));
  const [drag, setDrag] = useState(null);
  const [hover, setHover] = useState(null);
  const [filter, setFilter] = useState({
    project: true,
    doc: true,
    module: true,
    endpoint: true,
    tool: true,
    repo: true,
  });
  const wrapRef = useRef(null);
  const edges = useMemo(() => (graph.edges || []).map(e => [e.from, e.to]), [graph]);

  useEffect(() => {
    setNodes(layoutNodes(graph.nodes || []));
  }, [graph]);

  const visible = nodes.filter(n => filter[n.kind]);
  const visibleIds = new Set(visible.map(n => n.id));
  const visibleEdges = edges.filter(([a, b]) => visibleIds.has(a) && visibleIds.has(b));

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
    return () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
  }, [drag]);

  const startDrag = (e, n) => {
    const rect = wrapRef.current.getBoundingClientRect();
    setDrag({ id: n.id, dx: (e.clientX - rect.left) - n.x, dy: (e.clientY - rect.top) - n.y });
  };

  const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]));
  const isEdgeActive = ([a, b]) => hover && (a === hover || b === hover);
  const isNodeActive = (id) => {
    if (!hover) return true;
    if (id === hover) return true;
    return visibleEdges.some(([a, b]) => (a === hover && b === id) || (b === hover && a === id));
  };

  return (
    <div className="graph-wrap" ref={wrapRef}>
      <svg className="graph-svg">
        {visibleEdges.map(([a, b], i) => {
          const na = nodeMap[a], nb = nodeMap[b];
          if (!na || !nb) return null;
          const active = isEdgeActive([a, b]);
          return (
            <line
              key={`${a}-${b}-${i}`}
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
            left: n.x,
            top: n.y,
            "--n-c": n.color,
            opacity: isNodeActive(n.id) ? 1 : 0.32,
            transition: drag?.id === n.id ? "none" : "opacity 200ms",
          }}
          onMouseDown={(e) => startDrag(e, n)}
          onMouseEnter={() => setHover(n.id)}
          onMouseLeave={() => setHover(null)}
          title={n.id}
        >
          <span className="n-dot"/>
          {n.label}
        </div>
      ))}

      <div className="graph-legend">
        <div style={{ color: "var(--text-2)", marginBottom: 4 }}>FILTER</div>
        {[
          ["project", "Projects", "#f5b343"],
          ["doc", "Docs", "#8aa9ff"],
          ["module", "Modules", "#5ee0c8"],
          ["endpoint", "Endpoints", "#5cc8ff"],
          ["tool", "Tools", "#f5b343"],
          ["repo", "Repos", "#5ee0c8"],
        ].map(([k, label, c]) => (
          <div
            key={k}
            className="legend-row"
            style={{ cursor: "pointer", opacity: filter[k] ? 1 : 0.4 }}
            onClick={() => setFilter(f => ({ ...f, [k]: !f[k] }))}
          >
            <span className="legend-dot" style={{ color: c }}/>
            <span>{label}</span>
          </div>
        ))}
      </div>

      <div className="graph-controls">
        <button className="icon-btn" title="Reload layout" onClick={() => setNodes(layoutNodes(graph.nodes || []))}>
          <I.RefreshCw size={14}/>
        </button>
      </div>
    </div>
  );
}

function Relations() {
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [status, setStatus] = useState("loading");
  const [source, setSource] = useState("built-in");
  const counts = graphCounts(graph);
  const displayGraph = useMemo(() => displayGraphFor(graph), [graph]);

  const load = async () => {
    setStatus("loading");
    try {
      const data = await apiJson("/api/v1/relations?project=invisible");
      setGraph(data);
      setSource(data.source || "built-in");
      setStatus("ready");
    } catch (e) {
      setStatus(e.message || "failed");
    }
  };

  const runGraphify = async () => {
    setStatus("running graphify");
    try {
      await postJson("/api/v1/graphify/run", { project: "invisible" });
      await load();
    } catch (e) {
      setStatus(e.message || "graphify failed");
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--pad-3)", height: "100%" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span className="chip accent"><span className="chip-dot"/>{source} graph</span>
        <span className="chip"><span className="chip-dot" style={{ color: "var(--c-cal)" }}/>{counts.nodes} nodes - {counts.edges} links</span>
        {displayGraph.limited && (
          <span className="chip"><span className="chip-dot" style={{ color: "var(--c-graph)" }}/>showing {displayGraph.nodes.length} nodes</span>
        )}
        <span className="muted mono" style={{ fontSize: 11, marginLeft: 8 }}>{status} - drag nodes - hover to focus subgraph</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          <button className="btn" onClick={load}>Refresh</button>
          <button className="btn" onClick={runGraphify}>Run Graphify</button>
        </div>
      </div>
      <div style={{ flex: 1, minHeight: 0 }}>
        <RelationsGraph graph={displayGraph}/>
      </div>
    </div>
  );
}

export default Relations;
