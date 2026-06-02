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

// ── Deterministic layout ──────────────────────────────────────────
// Distribute nodes into concentric rings by kind. Pure function: same
// input → same output, so reloads produce the same layout. The four
// rings are project (innermost) → module → doc → endpoint (outermost).
function layoutNodes(rawNodes, width, height) {
  const W = width || 800;
  const H = height || 600;
  const cx = W / 2;
  const cy = H / 2;
  const RING_RADIUS = { project: 90, module: 180, doc: 260, endpoint: 340 };
  const FALLBACK_RADIUS = 380;
  const FALLBACK_COLOR = "#cccccc";

  // Group nodes by kind, preserving incoming order within each ring so
  // the layout is stable across reloads.
  const buckets = { project: [], module: [], doc: [], endpoint: [], _other: [] };
  for (const n of (rawNodes || [])) {
    if (buckets[n.type]) buckets[n.type].push(n);
    else buckets._other.push(n);
  }

  const out = [];
  const placeRing = (members, radius) => {
    const count = members.length;
    if (!count) return;
    for (let i = 0; i < count; i++) {
      const n = members[i];
      const angle = 2 * Math.PI * (i / count);
      out.push({
        ...n,
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle),
        color: KIND_COLOR[n.type] || FALLBACK_COLOR,
      });
    }
  };

  placeRing(buckets.project,  RING_RADIUS.project);
  placeRing(buckets.module,   RING_RADIUS.module);
  placeRing(buckets.doc,      RING_RADIUS.doc);
  placeRing(buckets.endpoint, RING_RADIUS.endpoint);
  placeRing(buckets._other,   FALLBACK_RADIUS);

  return out;
}

// ── Inner graph renderer (data already loaded) ────────────────────
function RelationsGraph({ nodes: rawNodes, edges: rawEdges }) {
  const [nodes, setNodes] = useStateG(() => layoutNodes(rawNodes, 800, 600));
  const [drag, setDrag] = useStateG(null);
  const [hover, setHover] = useStateG(null);
  const [filter, setFilter] = useStateG({ module: true, doc: true, project: true, endpoint: true });
  const wrapRef = useRefG(null);

  // Re-lay out when the data prop identity changes. The fetch is mount-once
  // today, but this is defensive against a future refresh button.
  useEffectG(() => { setNodes(layoutNodes(rawNodes, 800, 600)); }, [rawNodes]);

  // Reset handler: snap nodes back to the deterministic layout.
  const resetLayout = useCallbackG(() => {
    setNodes(layoutNodes(rawNodes, 800, 600));
  }, [rawNodes]);

  const visible = nodes.filter(n => filter[n.type]);
  const visibleIds = new Set(visible.map(n => n.id));
  const visibleEdges = (rawEdges || []).filter(e => visibleIds.has(e.from) && visibleIds.has(e.to));

  useEffectG(() => {
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

  // Highlight edges and connected nodes when hovering. Edge shape is the
  // new backend `{from, to, kind}` object — NOT the legacy `[a,b]` tuple.
  const isEdgeActive = (e) => hover && (e.from === hover || e.to === hover);
  const isNodeActive = (id) => {
    if (!hover) return true;
    if (id === hover) return true;
    return visibleEdges.some(e => (e.from === hover && e.to === id) || (e.to === hover && e.from === id));
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
        {visibleEdges.map((e, i) => {
          const na = nodeMap[e.from], nb = nodeMap[e.to];
          if (!na || !nb) return null;
          const active = isEdgeActive(e);
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
          className={"graph-node kind-" + (KIND_TO_CSS[n.type] || "repo") + (drag?.id === n.id ? " dragging" : "")}
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
        {KIND_LABELS.map(([k, label, c]) => (
          <div key={k} className="legend-row" style={{ cursor: "pointer", opacity: filter[k] ? 1 : 0.4 }}
               onClick={() => setFilter(f => ({ ...f, [k]: !f[k] }))}>
            <span className="legend-dot" style={{ color: c }}/>
            <span>{label}</span>
          </div>
        ))}
      </div>

      <div className="graph-controls">
        <button className="icon-btn" title="Reset" onClick={resetLayout}><I.Sparkles size={14}/></button>
        {/* TODO: zoom support — currently a no-op so the visual control stays parked here for a follow-up plan */}
        <button className="icon-btn" title="Zoom in"><I.Plus size={14}/></button>
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
