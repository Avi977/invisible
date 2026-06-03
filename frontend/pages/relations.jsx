// Relationships — Obsidian-style graph rendering real nodes/edges
// from GET /api/v1/relations on the dashboard daemon (port 8765).
// Backend kinds {module, doc, project, endpoint} map to existing CSS
// classes {.kind-repo, .kind-note, .kind-project, .kind-tool}.

const { useState: useStateG, useRef: useRefG, useEffect: useEffectG, useCallback: useCallbackG } = React;

// ── Module-level constants ────────────────────────────────────────
const RELATIONS_API_BASE = "http://127.0.0.1:8765";

// Backend kind → existing CSS class suffix. The page DOES NOT edit
// styles.css; it maps the new four-kind taxonomy onto the four mock
// classes already in the stylesheet.
const KIND_TO_CSS = { module: "repo", doc: "note", project: "project", endpoint: "tool" };

// Per-kind color used to drive the `--n-c` CSS variable that the
// color-mix rules on .graph-node read. Hex values mirror the dashboard's
// deterministic palette so visual identity stays consistent.
const KIND_COLOR = { module: "#5ee0c8", doc: "#8aa9ff", project: "#f5b343", endpoint: "#b794ff" };

// Legend chip rows — [backendKind, label, color]. Drives both render
// order and the filter-chip toggles in the legend.
const KIND_LABELS = [
  ["module",   "Modules",   "#5ee0c8"],
  ["doc",      "Docs",      "#8aa9ff"],
  ["project",  "Projects",  "#f5b343"],
  ["endpoint", "Endpoints", "#b794ff"],
];

// ── Inline fetcher (single-use; kept out of data.jsx per Plan 01-02) ─
async function fetchRelations(project) {
  const url = RELATIONS_API_BASE + "/api/v1/relations" + (project ? ("?project=" + encodeURIComponent(project)) : "");
  try {
    const response = await fetch(url, { credentials: "omit" });
    if (!response.ok) throw new Error("HTTP " + response.status);
    return await response.json();
  } catch (e) {
    throw new Error("fetchRelations: " + (e.message || "network error"));
  }
}

// ── 3D graph renderer (data already loaded) ──────────────────────
// Uses the global `ForceGraph3D` constructor from
// https://unpkg.com/3d-force-graph (loaded in frontend/index.html). The
// library bundles three.js + d3-force-3d, so we don't need a separate
// three.js script tag.
//
// Backend shape:  { nodes: [{id, label, type, ...}], edges: [{from, to, kind}] }
// Library shape:  { nodes: [{id, ...}],              links: [{source, target}] }
// The mapping happens here in `toGraphData`.
function toGraphData(rawNodes, rawEdges, visibleTypes) {
  const FALLBACK_COLOR = "#cccccc";
  const nodes = (rawNodes || [])
    .filter(n => visibleTypes[n.type])
    .map(n => ({
      id: n.id,
      label: n.label || n.id,
      type: n.type,
      color: KIND_COLOR[n.type] || FALLBACK_COLOR,
      file_path: n.file_path || null,
    }));
  const visibleIds = new Set(nodes.map(n => n.id));
  const links = (rawEdges || [])
    .filter(e => visibleIds.has(e.from) && visibleIds.has(e.to))
    .map(e => ({ source: e.from, target: e.to, kind: e.kind || "ref" }));
  return { nodes, links };
}

function RelationsGraph({ nodes: rawNodes, edges: rawEdges }) {
  const wrapRef = useRefG(null);
  const graphRef = useRefG(null);  // holds the ForceGraph3D instance
  const [filter, setFilter] = useStateG({ module: true, doc: true, project: true, endpoint: true });
  const [hover, setHover] = useStateG(null);

  // One-time instantiate of the ForceGraph3D instance, bound to wrapRef.
  // Tearing it down on unmount avoids leaking the WebGL renderer + animation
  // loop. The data + interaction handlers are wired in a second useEffect
  // so they pick up React state updates without recreating the canvas.
  useEffectG(() => {
    if (typeof ForceGraph3D !== "function") {
      console.error("[relations] ForceGraph3D not on window — index.html script tag missing or CDN blocked?");
      return;
    }
    if (!wrapRef.current) return;
    const el = wrapRef.current;
    const g = ForceGraph3D()(el)
      .backgroundColor("rgba(0,0,0,0)")        // transparent so the page bg shows through
      .showNavInfo(false)                      // hide the default top-left help text
      .nodeRelSize(5)
      .nodeColor(n => n.color)
      .nodeLabel(n => `${n.label} <span style="opacity:.6">· ${n.type}</span>`)
      .linkColor(() => "rgba(255,255,255,0.18)")
      .linkOpacity(0.5)
      .linkWidth(0.6)
      .linkDirectionalParticles(0)             // bump >0 if we want flowing particles per link
      .onNodeHover(n => setHover(n ? n.id : null))
      .onNodeClick(n => {
        // Snap the camera to the clicked node — gives a "drill in" feel.
        const dist = 80;
        const r = Math.hypot(n.x || 0, n.y || 0, n.z || 0) || 1;
        const k = 1 + dist / r;
        g.cameraPosition({ x: (n.x || 0) * k, y: (n.y || 0) * k, z: (n.z || 0) * k }, n, 1500);
      });

    // ResizeObserver — keep the WebGL canvas matching the wrapper.
    const ro = new ResizeObserver(() => {
      g.width(el.clientWidth).height(el.clientHeight);
    });
    ro.observe(el);
    g.width(el.clientWidth).height(el.clientHeight);

    graphRef.current = g;
    return () => {
      ro.disconnect();
      // 3d-force-graph exposes _destructor (lib-private) for full cleanup;
      // fall back to detaching the canvas if that's not present.
      try { g._destructor && g._destructor(); } catch (_) { /* swallow */ }
      while (el.firstChild) el.removeChild(el.firstChild);
      graphRef.current = null;
    };
  }, []);

  // Push graph data whenever the raw input or the filter set changes.
  // Hover state intentionally NOT in deps — we update hover-driven visuals
  // by setting node/link color callbacks below in a separate effect.
  useEffectG(() => {
    if (!graphRef.current) return;
    graphRef.current.graphData(toGraphData(rawNodes, rawEdges, filter));
  }, [rawNodes, rawEdges, filter]);

  // Wire hover-driven dimming. The library re-reads node/link color
  // closures on every frame, so updating the closures via setters
  // here is enough; no need to re-feed graphData.
  useEffectG(() => {
    const g = graphRef.current;
    if (!g) return;
    // Build a neighbour set once per hover so the per-frame closures stay O(1).
    let nbrs = null;
    if (hover) {
      nbrs = new Set([hover]);
      for (const e of (rawEdges || [])) {
        if (e.from === hover) nbrs.add(e.to);
        if (e.to === hover) nbrs.add(e.from);
      }
    }
    g.nodeColor(n => {
      if (!nbrs) return n.color;
      return nbrs.has(n.id) ? n.color : "rgba(120,120,140,0.25)";
    });
    g.linkColor(l => {
      if (!nbrs) return "rgba(255,255,255,0.18)";
      const src = typeof l.source === "object" ? l.source.id : l.source;
      const tgt = typeof l.target === "object" ? l.target.id : l.target;
      return (src === hover || tgt === hover) ? "rgba(180, 210, 255, 0.85)" : "rgba(255,255,255,0.05)";
    });
    g.linkWidth(l => {
      const src = typeof l.source === "object" ? l.source.id : l.source;
      const tgt = typeof l.target === "object" ? l.target.id : l.target;
      return (hover && (src === hover || tgt === hover)) ? 1.4 : 0.6;
    });
  }, [hover, rawEdges]);

  // Reset = re-zoom-to-fit and shake the simulation a little so nodes
  // settle from whatever drag position they were in.
  const resetLayout = useCallbackG(() => {
    const g = graphRef.current;
    if (!g) return;
    g.zoomToFit(800, 40);
    g.d3ReheatSimulation && g.d3ReheatSimulation();
  }, []);

  // ForceGraph3D wipes its mount target's children when it initializes —
  // so the canvas container has to be a dedicated inner div with no
  // siblings inside it. Legend + controls sit alongside as absolute-
  // positioned overlays in the outer .graph-wrap.
  return (
    <div className="graph-wrap" style={{ position: "relative" }}>
      <div ref={wrapRef} style={{ position: "absolute", inset: 0 }}/>

      <div className="graph-legend">
        <div style={{ color: "var(--text-2)", marginBottom: 4 }}>FILTER</div>
        {KIND_LABELS.map(([k, label, c]) => (
          <div key={k} className="legend-row" style={{ cursor: "pointer", opacity: filter[k] ? 1 : 0.4 }}
               onClick={() => setFilter(f => ({ ...f, [k]: !f[k] }))}>
            <span className="legend-dot" style={{ color: c }}/>
            <span>{label}</span>
          </div>
        ))}
        <div style={{ color: "var(--text-2)", marginTop: 8, fontSize: 11 }}>
          drag = orbit · scroll = zoom · click node = focus
        </div>
      </div>

      <div className="graph-controls">
        <button className="icon-btn" title="Reset view + reheat simulation" onClick={resetLayout}><I.Sparkles size={14}/></button>
        <button className="icon-btn" title="Zoom in" onClick={() => {
          const g = graphRef.current; if (!g) return;
          const cam = g.cameraPosition();
          g.cameraPosition({ x: cam.x * 0.8, y: cam.y * 0.8, z: cam.z * 0.8 }, undefined, 400);
        }}><I.Plus size={14}/></button>
      </div>
    </div>
  );
}

// ── Outer self-fetching shell (loading / error / empty / loaded) ──
function Relations() {
  // data: null while loading; {nodes, edges} on success.
  // error: null on success; Error instance on failure (message already
  // sanitized by fetchRelations — no URL / host path leakage).
  const [data, setData] = useStateG(null);
  const [error, setError] = useStateG(null);

  // Stable loader so useEffect runs exactly once on mount and the Retry /
  // re-fetch handlers can call the same closure.
  const loadGraph = useCallbackG(() => {
    setError(null);
    setData(null);
    fetchRelations("invisible").then(setData).catch(setError);
  }, []);

  useEffectG(() => { loadGraph(); }, [loadGraph]);

  // Compact header strip used by all four branches (loading/error/empty/loaded).
  // chipText / chipColor / dataLabel vary per branch.
  const Header = ({ chipText, chipColor, dataLabel }) => (
    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
      <span className="chip accent"><span className="chip-dot"/>{dataLabel}</span>
      <span className="chip"><span className="chip-dot" style={{ color: chipColor }}/>{chipText}</span>
      <span className="muted mono" style={{ fontSize: 11, marginLeft: 8 }}>Drag nodes · hover to focus subgraph</span>
      <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
        <button className="btn">Force layout</button>
        <button className="btn">Tag view</button>
      </div>
    </div>
  );

  // ── Loading branch ────────────────────────────────────────────
  if (data === null && !error) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--pad-3)", height: "100%" }}>
        <Header chipText="?? nodes · ?? links" chipColor="var(--c-cal)" dataLabel="Loading…"/>
        <div style={{ flex: 1, minHeight: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div className="glass fade-in" style={{
            padding: "var(--pad-5)",
            maxWidth: 420,
            textAlign: "center",
            opacity: 0.85,
            transition: "opacity .4s ease",
          }}>
            <div className="mono" style={{
              fontSize: 11,
              color: "var(--text-3)",
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              marginBottom: 8,
            }}>
              Fetching
            </div>
            <div style={{ fontSize: 16, color: "var(--text-2)" }}>
              Loading graph…
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Error branch ──────────────────────────────────────────────
  if (error) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--pad-3)", height: "100%" }}>
        <Header chipText="error" chipColor="#ff7a7a" dataLabel="Error"/>
        <div style={{ flex: 1, minHeight: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div className="glass fade-in" style={{
            padding: "var(--pad-5)",
            maxWidth: 480,
            textAlign: "center",
          }}>
            <h2 style={{
              margin: "0 0 8px",
              fontSize: 18,
              fontWeight: 600,
              color: "var(--text-1)",
            }}>
              Couldn't load relations
            </h2>
            <div className="mono" style={{
              fontSize: 12,
              color: "var(--text-3)",
              marginBottom: 18,
              wordBreak: "break-word",
            }}>
              {error.message}
            </div>
            <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
              <button
                className="btn accent"
                onClick={() => loadGraph()}
                style={{ justifyContent: "center" }}
              >
                Retry
              </button>
              <button
                className="btn"
                onClick={() => { setError(null); setData({ nodes: [], edges: [] }); }}
                style={{ justifyContent: "center" }}
              >
                Show empty
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Empty-graph branch ────────────────────────────────────────
  if (!data.nodes || data.nodes.length === 0) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--pad-3)", height: "100%" }}>
        <Header chipText="0 nodes · 0 links · empty" chipColor="var(--text-3)" dataLabel="Empty"/>
        <div style={{ flex: 1, minHeight: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div className="glass fade-in" style={{
            padding: "var(--pad-5)",
            maxWidth: 460,
            textAlign: "center",
            opacity: 0.85,
          }}>
            <div className="mono" style={{
              fontSize: 11,
              color: "var(--text-3)",
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              marginBottom: 8,
            }}>
              No data
            </div>
            <div style={{ fontSize: 16, color: "var(--text-2)" }}>
              No relations yet — the API returned an empty graph for project 'invisible'.
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Loaded branch ─────────────────────────────────────────────
  const nodeCount = data.nodes.length;
  const edgeCount = (data.edges || []).length;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--pad-3)", height: "100%" }}>
      <Header
        chipText={nodeCount + " nodes · " + edgeCount + " links"}
        chipColor="var(--c-cal)"
        dataLabel="API · /api/v1/relations"
      />
      <div style={{ flex: 1, minHeight: 0 }}>
        <RelationsGraph nodes={data.nodes} edges={data.edges || []}/>
      </div>
    </div>
  );
}

window.Relations = Relations;

// PLAN-01-02 verification log
// ----------------------------------------------------------------------
// Headless E2E checks (Task 2) — all PASS against live daemons:
//
//   Daemons:
//     bin/invisible-dashboard --no-auth --port 8765   (Plan 01-01 backend)
//     INVISIBLE_HOME="$(pwd)" bin/invisible-frontend  (serves THIS worktree's frontend/)
//
//   Step 3a  GET http://127.0.0.1:8090/                      → 200 OK
//   Step 3b  index.html references pages/relations.jsx       → present (line 33)
//   Step 4a  GET http://127.0.0.1:8090/pages/relations.jsx   → 200 OK
//   Step 4b  Served bytes == on-disk bytes                   → diff -q clean
//            (confirms INVISIBLE_HOME override served the worktree, not ~/.invisible)
//   Step 5a  GET http://127.0.0.1:8765/api/v1/relations?project=invisible
//                                                            → 200 OK · 98 nodes · 216 edges
//   Step 5b  Access-Control-Allow-Origin header              → present (echoed Origin)
//
//   Plan 01-01 contract spot-checks (sanity — not modified here):
//     ?project=../etc        → 400 {"error": "invalid_project"}
//     ?project=nonexistent   → 200 {"nodes": [], "edges": []}   (drives Empty branch)
//
// Daemons torn down after the check; the next step (Task 3) is a human
// browser-driven visual + interactive verify per the plan.
// ----------------------------------------------------------------------
