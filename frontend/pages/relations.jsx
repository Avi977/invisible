// Relationships — the "app galaxy". Thousands of stars form spiral arms;
// each project is a glowing core whose modules/tools/notes/repos resolve into
// labeled nodes as you zoom in. Drag to orbit, scroll (or pinch) to fly in,
// click a node to dive to it. Rendered on canvas for the star count; labels
// and the detail card are DOM overlays.

const { useState: useStateG, useRef: useRefG, useEffect: useEffectG } = React;

const FOCAL = 700;
const DIST_FAR = 1700;
const DIST_NEAR = 110;            // smaller = fly in closer
const SPIN_RESUME_DELAY = 2800;   // ms of stillness before auto-rotate resumes

function GalaxyGraph() {
  const canvasRef = useRefG(null);
  const wrapRef = useRefG(null);
  const [filter, setFilter] = useStateG({ project: true, note: true, tool: true, repo: true, mod: true });
  const [spin, setSpin] = useStateG(true);
  const [info, setInfo] = useStateG(null);     // hovered/focused node summary (DOM card)
  const [zoomPct, setZoomPct] = useStateG(0);

  // mutable engine state (never triggers React renders)
  const eng = useRefG({
    ry: 0.65, rx: -0.92, dist: 1500,
    spinT: 0, vy: 0, vx: 0,
    pan: { x: 0, y: 0, z: 0 },
    panTarget: { x: 0, y: 0, z: 0 },
    distTarget: 1500,
    focusId: null,
    mouse: { x: -1, y: -1, down: false, moved: false },
    drag: null,
    hoverId: null,
    dpr: 1, w: 0, h: 0,
    labelHits: [],   // [{id, sx, sy}] candidates for hit-testing
  });

  const filterRef = useRefG(filter);
  const spinRef = useRefG(spin);
  useEffectG(() => { filterRef.current = filter; }, [filter]);
  useEffectG(() => { spinRef.current = spin; }, [spin]);

  // ---- sizing / hi-dpi ----
  useEffectG(() => {
    const cv = canvasRef.current, wrap = wrapRef.current;
    const resize = () => {
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const w = wrap.clientWidth, h = wrap.clientHeight;
      eng.current.dpr = dpr; eng.current.w = w; eng.current.h = h;
      cv.width = w * dpr; cv.height = h * dpr;
      cv.style.width = w + "px"; cv.style.height = h + "px";
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(wrap);
    return () => ro.disconnect();
  }, []);

  // ---- helpers to set focus ----
  const focusNode = (id) => {
    const G = window.GALAXY;
    const e = eng.current;
    if (!id) {
      e.focusId = null;
      e.panTarget = { x: 0, y: 0, z: 0 };
      e.distTarget = 900;
      return;
    }
    const n = G.nodes[G.nodeIndex[id]];
    if (!n) return;
    e.focusId = id;
    // pan target is computed each frame (spun frame); just set zoom depth
    e.distTarget = n.kind === "project" ? 230 : 175;
  };

  // ---- the render loop ----
  useEffectG(() => {
    let raf;
    const G = window.GALAXY;
    if (!G) return;

    const draw = () => {
      const e = eng.current;
      const ctx = canvasRef.current.getContext("2d");
      const { w, h, dpr } = e;
      const cx = w / 2, cy = h / 2;

      // spin (intrinsic galaxy rotation) — only after the user has been
      // still for a beat, so interaction never fights the auto-rotate.
      const now = performance.now();
      const idle = now - (e.lastInteract || 0) > SPIN_RESUME_DELAY;
      if (spinRef.current && !e.drag && idle) e.spinT += 0.0011;

      // camera inertia when not dragging
      if (!e.drag) {
        e.ry += e.vy; e.rx += e.vx;
        e.vy *= 0.92; e.vx *= 0.92;
        e.rx = Math.max(-1.45, Math.min(-0.05, e.rx));
      }

      // ease zoom toward target
      e.dist += (e.distTarget - e.dist) * 0.08;

      // focus pan: lock to focused node's *current spun* position
      if (e.focusId) {
        const n = G.nodes[G.nodeIndex[e.focusId]];
        if (n) {
          const cs = Math.cos(e.spinT), sn = Math.sin(e.spinT);
          e.panTarget = { x: n.x * cs - n.y * sn, y: n.x * sn + n.y * cs, z: n.z };
        }
      }
      e.pan.x += (e.panTarget.x - e.pan.x) * 0.08;
      e.pan.y += (e.panTarget.y - e.pan.y) * 0.08;
      e.pan.z += (e.panTarget.z - e.pan.z) * 0.08;

      // When focused on an app, only that app's own subgraph stays lit —
      // every other project's nodes recede to dust so the eye isn't flooded
      // with labels. activeProj is the project id we're locked onto (a focused
      // child resolves to its parent project).
      let activeProj = null;
      if (e.focusId) {
        const fn = G.nodes[G.nodeIndex[e.focusId]];
        if (fn) activeProj = fn.kind === "project" ? fn.id : fn.parent;
      }
      const inFocus = (n) =>
        !activeProj || n.id === activeProj || n.parent === activeProj;

      const cosY = Math.cos(e.ry), sinY = Math.sin(e.ry);
      const cosX = Math.cos(e.rx), sinX = Math.sin(e.rx);
      const cs = Math.cos(e.spinT), sn = Math.sin(e.spinT);

      // project disk-local point -> screen
      const project = (x, y, z) => {
        // intrinsic spin in disk plane
        let sx = x * cs - y * sn;
        let sy = x * sn + y * cs;
        let sz = z;
        // focus pan
        sx -= e.pan.x; sy -= e.pan.y; sz -= e.pan.z;
        // tilt about X
        const y1 = sy * cosX - sz * sinX;
        const z1 = sy * sinX + sz * cosX;
        // orbit about Y
        const x2 = sx * cosY + z1 * sinY;
        const z2 = -sx * sinY + z1 * cosY;
        const denom = FOCAL + z2 + e.dist;
        if (denom <= 1) return null;
        const depth = FOCAL / denom;
        return { sx: cx + x2 * depth, sy: cy + y1 * depth, depth, z: z2 };
      };

      // zoom factor 0 (far) .. 1 (near)
      const zf = Math.max(0, Math.min(1, (DIST_FAR - e.dist) / (DIST_FAR - DIST_NEAR)));

      // ---- clear ----
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      // faint vignette already on the wrapper; draw stars additively
      ctx.globalCompositeOperation = "lighter";

      // ---- stars (dust) ----
      const tw = e.spinT * 6;
      for (let i = 0; i < G.stars.length; i++) {
        const s = G.stars[i];
        const p = project(s.x, s.y, s.z);
        if (!p || p.sx < -20 || p.sx > w + 20 || p.sy < -20 || p.sy > h + 20) continue;
        const twinkle = 0.78 + 0.22 * Math.sin(tw + s.tw);
        const a = s.alpha * twinkle * (0.45 + 0.55 * p.depth);
        if (a < 0.02) continue;
        const sz = Math.max(0.4, s.size * p.depth * (1 + zf * 0.8));
        ctx.fillStyle = `rgba(${s.col[0]},${s.col[1]},${s.col[2]},${a.toFixed(3)})`;
        ctx.fillRect(p.sx - sz / 2, p.sy - sz / 2, sz, sz);
      }

      // project labeled nodes once
      const np = new Array(G.nodes.length);
      for (let i = 0; i < G.nodes.length; i++) {
        np[i] = project(G.nodes[i].x, G.nodes[i].y, G.nodes[i].z);
      }

      // ---- edges (fade in with zoom) ----
      if (zf > 0.08) {
        ctx.lineWidth = 1;
        for (let i = 0; i < G.edges.length; i++) {
          const [a, b] = G.edges[i];
          const pa = np[a], pb = np[b];
          if (!pa || !pb) continue;
          const na = G.nodes[a], nb = G.nodes[b];
          if (!filterRef.current[na.kind] || !filterRef.current[nb.kind]) continue;
          const hov = e.hoverId && (na.id === e.hoverId || nb.id === e.hoverId ||
            na.parent === e.hoverId || nb.parent === e.hoverId);
          // when an app is focused, hide edges that aren't part of its subgraph
          if (activeProj && !hov && !(inFocus(na) && inFocus(nb))) continue;
          // project-project edges show earlier; cluster edges need more zoom
          const cluster = na.kind === "project" || nb.kind === "project";
          const gate = cluster ? 0.12 : 0.45;
          if (zf < gate && !hov) continue;
          const base = Math.min(0.5, (zf - gate) * 1.2);
          const a2 = hov ? 0.8 : Math.max(0.04, base) * (0.4 + 0.6 * Math.min(pa.depth, pb.depth));
          ctx.strokeStyle = hov ? "rgba(190,215,255,0.85)" : `rgba(150,175,225,${a2.toFixed(3)})`;
          ctx.beginPath();
          ctx.moveTo(pa.sx, pa.sy);
          ctx.lineTo(pb.sx, pb.sy);
          ctx.stroke();
        }
      }

      // ---- node cores (glow) ----
      const hits = [];
      for (let i = 0; i < G.nodes.length; i++) {
        const n = G.nodes[i];
        const p = np[i];
        if (!p) continue;
        if (!filterRef.current[n.kind]) continue;
        if (p.sx < -40 || p.sx > w + 40 || p.sy < -40 || p.sy > h + 40) continue;
        const c = n.col;
        const isHover = e.hoverId === n.id;
        const isFocus = e.focusId === n.id;
        const ff = inFocus(n);
        // other apps' nodes recede to faint dust when one app is focused
        const dim = (activeProj && !ff && !isHover) ? 0.16 : 1;

        // glow radius by tier + zoom + depth
        let glow;
        if (n.kind === "project") glow = (10 + zf * 26) * p.depth;
        else if (n.tier === 1)    glow = (5 + zf * 16) * p.depth;
        else                       glow = (2.5 + zf * 11) * p.depth;
        if (isHover || isFocus) glow *= 1.5;

        const coreA = (n.kind === "project" ? 1 : (0.55 + 0.45 * p.depth)) * dim;
        // outer glow
        const g = ctx.createRadialGradient(p.sx, p.sy, 0, p.sx, p.sy, glow * 2.4);
        g.addColorStop(0, `rgba(${c[0]},${c[1]},${c[2]},${(0.55 * coreA).toFixed(3)})`);
        g.addColorStop(1, `rgba(${c[0]},${c[1]},${c[2]},0)`);
        ctx.fillStyle = g;
        ctx.fillRect(p.sx - glow * 2.4, p.sy - glow * 2.4, glow * 4.8, glow * 4.8);
        // bright core
        ctx.fillStyle = `rgba(255,255,255,${(0.9 * coreA).toFixed(3)})`;
        const core = Math.max(0.8, glow * 0.34);
        ctx.beginPath();
        ctx.arc(p.sx, p.sy, core, 0, Math.PI * 2);
        ctx.fill();

        // label LOD gate
        let labelGate;
        if (n.kind === "project") labelGate = 0.04;
        else if (n.tier === 1)    labelGate = 0.40;
        else                       labelGate = 0.66;
        const labelable = zf >= labelGate || isHover || isFocus;
        // suppress labels for other apps while one app is focused
        if (labelable && (!activeProj || ff || isHover)) hits.push({ id: n.id, sx: p.sx, sy: p.sy, depth: p.depth, n });
      }
      e.labelHits = hits;

      // ---- labels (drawn in normal blend over glow) ----
      ctx.globalCompositeOperation = "source-over";
      ctx.textBaseline = "middle";
      for (const hsel of hits) {
        const n = hsel.n;
        const isHover = e.hoverId === n.id;
        const isFocus = e.focusId === n.id;
        let gate, fade;
        if (n.kind === "project") { gate = 0.04; fade = 0.18; }
        else if (n.tier === 1)    { gate = 0.40; fade = 0.12; }
        else                       { gate = 0.66; fade = 0.10; }
        let la = Math.max(0, Math.min(1, (zf - gate) / fade));
        if (isHover || isFocus) la = 1;
        la *= (0.5 + 0.5 * hsel.depth);
        if (la < 0.04) continue;

        const proj = n.kind === "project";
        const fs = proj ? 14 : (n.tier === 1 ? 12 : 11);
        ctx.font = `${proj ? 600 : 400} ${fs}px "Geist Mono", ui-monospace, monospace`;
        const tw2 = ctx.measureText(n.label).width;
        const padX = 7, padY = proj ? 5 : 4;
        const bx = hsel.sx + (proj ? 0 : 9);
        const by = hsel.sy - (proj ? (16 + fs) : 0);
        const boxX = proj ? bx - tw2 / 2 - padX : bx;
        const boxY = by - fs / 2 - padY;
        const boxW = tw2 + padX * 2;
        const boxH = fs + padY * 2;
        const c = n.col;
        // pill bg
        ctx.globalAlpha = la;
        ctx.fillStyle = `rgba(18,20,28,${proj ? 0.82 : 0.68})`;
        roundRect(ctx, boxX, boxY, boxW, boxH, boxH / 2);
        ctx.fill();
        ctx.lineWidth = 1;
        ctx.strokeStyle = `rgba(${c[0]},${c[1]},${c[2]},${(isHover || isFocus) ? 0.95 : 0.45})`;
        ctx.stroke();
        // dot
        ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
        ctx.beginPath();
        ctx.arc(boxX + padX + 2, boxY + boxH / 2, proj ? 3.2 : 2.6, 0, Math.PI * 2);
        ctx.fill();
        // text
        ctx.fillStyle = proj ? "rgba(244,245,248,1)" : "rgba(214,218,227,0.96)";
        ctx.fillText(n.label, boxX + padX + (proj ? 9 : 8), boxY + boxH / 2 + 0.5);
        ctx.globalAlpha = 1;
      }

      // hover hit-test using latest projected label candidates
      if (!e.drag && e.mouse.x >= 0) {
        let best = null, bestD = 22 * 22;
        for (const hsel of e.labelHits) {
          const dx = hsel.sx - e.mouse.x, dy = hsel.sy - e.mouse.y;
          const d = dx * dx + dy * dy;
          if (d < bestD) { bestD = d; best = hsel.id; }
        }
        if (best !== e.hoverId) {
          e.hoverId = best;
          syncInfo();
        }
      }

      // report zoom for the DOM meter (throttled-ish: only on change)
      const pct = Math.round(zf * 100);
      if (pct !== e._lastPct) { e._lastPct = pct; setZoomPct(pct); }

      raf = requestAnimationFrame(draw);
    };

    const syncInfo = () => {
      const e = eng.current;
      const id = e.focusId || e.hoverId;
      if (!id) { setInfo(null); return; }
      const G = window.GALAXY;
      const n = G.nodes[G.nodeIndex[id]];
      if (!n) { setInfo(null); return; }
      // count links
      let links = 0;
      for (const [a, b] of G.edges) {
        if (G.nodes[a].id === id || G.nodes[b].id === id) links++;
        else if (G.nodes[a].parent === id || G.nodes[b].parent === id) links++;
      }
      setInfo({
        label: n.label, kind: n.kind, desc: n.desc, stack: n.stack,
        parent: n.parent, links,
      });
    };
    eng.current._syncInfo = syncInfo;

    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, []);

  // round-rect helper
  function roundRect(ctx, x, y, w, h, r) {
    r = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  // ---- pointer handlers ----
  const onDown = (ev) => {
    const e = eng.current;
    const rect = wrapRef.current.getBoundingClientRect();
    e.drag = { px: ev.clientX, py: ev.clientY, ry: e.ry, rx: e.rx, moved: false };
    e.mouse.down = true;
    e.vy = 0; e.vx = 0;
    e.lastInteract = performance.now();
    document.body.style.cursor = "grabbing";
  };
  const onMove = (ev) => {
    const e = eng.current;
    const rect = wrapRef.current.getBoundingClientRect();
    e.mouse.x = ev.clientX - rect.left;
    e.mouse.y = ev.clientY - rect.top;
    if (e.drag) {
      const dx = ev.clientX - e.drag.px, dy = ev.clientY - e.drag.py;
      if (Math.abs(dx) + Math.abs(dy) > 3) e.drag.moved = true;
      e.lastInteract = performance.now();
      const ry0 = e.ry;
      e.ry = e.drag.ry + dx * 0.006;
      e.rx = Math.max(-1.45, Math.min(-0.05, e.drag.rx + dy * 0.006));
      e.vy = e.ry - ry0;
    }
  };
  const onUp = (ev) => {
    const e = eng.current;
    const wasDrag = e.drag && e.drag.moved;
    e.drag = null;
    e.mouse.down = false;
    e.lastInteract = performance.now();
    document.body.style.cursor = "";
    if (!wasDrag) {
      // click: focus hovered node, or unfocus on empty space
      if (e.hoverId) {
        focusNode(e.hoverId);
        e._syncInfo && setTimeout(() => e._syncInfo(), 0);
      } else if (e.focusId) {
        focusNode(null);
        setInfo(null);
      }
    }
  };
  const onLeave = () => {
    const e = eng.current;
    e.mouse.x = -1; e.mouse.y = -1;
    if (!e.focusId && e.hoverId) { e.hoverId = null; setInfo(null); }
  };
  const onWheel = (ev) => {
    ev.preventDefault();
    const e = eng.current;
    e.focusId = null; // free-fly when manually zooming
    e.lastInteract = performance.now();
    e.distTarget = Math.max(DIST_NEAR, Math.min(DIST_FAR, e.distTarget + ev.deltaY * 0.9));
  };

  useEffectG(() => {
    const wrap = wrapRef.current;
    wrap.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      wrap.removeEventListener("wheel", onWheel);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  const G = window.GALAXY || { counts: { stars: 0, nodes: 0, edges: 0 } };
  const kindLabel = { project: "Project", note: "Note", tool: "Tool", repo: "Repo", mod: "Module" };
  const kindColor = { project: "#f5b343", note: "#8aa9ff", tool: "#f5b343", repo: "#5ee0c8", mod: "#9aa6c4" };

  const flyTo = (id) => { eng.current.lastInteract = performance.now(); focusNode(id); setSpin(true); setTimeout(() => eng.current._syncInfo && eng.current._syncInfo(), 0); };
  const resetView = () => {
    const e = eng.current;
    e.focusId = null;
    e.lastInteract = performance.now();
    e.distTarget = 1500; e.panTarget = { x: 0, y: 0, z: 0 };
    Object.assign(e, { ry: 0.65, rx: -0.92, vy: 0, vx: 0 });
    setInfo(null);
  };

  return (
    <div className="galaxy-wrap" ref={wrapRef} onMouseDown={onDown} onMouseLeave={onLeave}>
      <canvas ref={canvasRef} className="galaxy-canvas"/>

      {/* zoom depth meter */}
      <div className="galaxy-zoom">
        <span className="gz-label">{zoomPct < 25 ? "GALAXY" : zoomPct < 60 ? "CLUSTER" : "SYSTEM"}</span>
        <div className="gz-track"><div className="gz-fill" style={{ width: zoomPct + "%" }}/></div>
        <span className="gz-pct">{zoomPct}%</span>
      </div>

      {/* legend / filters */}
      <div className="graph-legend" onMouseDown={(e) => e.stopPropagation()}>
        <div style={{ color: "var(--text-2)", marginBottom: 4 }}>LAYERS</div>
        {["project", "tool", "note", "repo", "mod"].map((k) => (
          <div key={k} className="legend-row" style={{ cursor: "pointer", opacity: filter[k] ? 1 : 0.4 }}
               onClick={() => setFilter((f) => ({ ...f, [k]: !f[k] }))}>
            <span className="legend-dot" style={{ color: kindColor[k] }}/>
            <span>{kindLabel[k]}</span>
          </div>
        ))}
      </div>

      {/* jump-to-project rail */}
      <div className="galaxy-rail" onMouseDown={(e) => e.stopPropagation()}>
        <div className="gr-head">PROJECTS</div>
        {(window.GALAXY ? window.GALAXY.nodes.filter((n) => n.kind === "project") : []).map((p) => (
          <button key={p.id} className="gr-btn" onClick={() => flyTo(p.id)}>
            <span className="gr-dot" style={{ background: `rgb(${p.col[0]},${p.col[1]},${p.col[2]})` }}/>
            {p.label}
          </button>
        ))}
      </div>

      {/* detail card */}
      {info && (
        <div className="galaxy-card" onMouseDown={(e) => e.stopPropagation()}>
          <div className="gc-kind" style={{ color: kindColor[info.kind] }}>
            <span className="gc-dot" style={{ background: kindColor[info.kind] }}/>
            {kindLabel[info.kind]}{info.parent ? " · " + info.parent : ""}
          </div>
          <div className="gc-title">{info.label}</div>
          {info.desc && <div className="gc-desc">{info.desc}</div>}
          {info.stack && (
            <div className="gc-stack">
              {info.stack.map((s) => <span key={s} className="gc-tag">{s}</span>)}
            </div>
          )}
          <div className="gc-meta">{info.links} link{info.links === 1 ? "" : "s"}</div>
        </div>
      )}

      {/* controls */}
      <div className="graph-controls" onMouseDown={(e) => e.stopPropagation()}>
        <button className={"icon-btn" + (spin ? " on" : "")} title={spin ? "Pause rotation" : "Rotate"}
                onClick={() => setSpin((s) => !s)}><I.Sparkles size={14}/></button>
        <button className="icon-btn" title="Zoom in"
                onClick={() => { const e = eng.current; e.focusId = null; e.lastInteract = performance.now(); e.distTarget = Math.max(DIST_NEAR, e.distTarget - 220); }}>
          <I.Plus size={14}/></button>
        <button className="icon-btn" title="Reset view" onClick={resetView}><I.Search size={14}/></button>
      </div>

      <div className="galaxy-hint">
        {G.counts.stars.toLocaleString()} stars · {G.counts.nodes} nodes · drag to orbit · scroll to dive · click a star
      </div>
    </div>
  );
}

// Same host as the other real-data fetchers (dashboard daemon).
const RELATIONS_API_BASE = "http://127.0.0.1:8765";

function GalaxyStatus({ children }) {
  return (
    <div className="galaxy-wrap" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div className="glass" style={{ padding: "var(--pad-5)", textAlign: "center", maxWidth: 420 }}>
        {children}
      </div>
    </div>
  );
}

function Relations() {
  // Galaxy is built from the LIVE relations graph. The canvas engine reads
  // window.GALAXY synchronously at mount, so GalaxyGraph is only rendered once
  // window.buildGalaxy() has populated it (status === "ready").
  const [state, setState] = useStateG({ status: "loading", counts: null, error: null });
  const [tick, setTick] = useStateG(0);

  useEffectG(() => {
    let cancelled = false;
    setState({ status: "loading", counts: null, error: null });
    fetch(RELATIONS_API_BASE + "/api/v1/relations", { credentials: "omit" })
      .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then((data) => {
        if (cancelled) return;
        if (typeof window.buildGalaxy !== "function") throw new Error("galaxy-data.jsx not loaded");
        const g = window.buildGalaxy(data);   // populates window.GALAXY
        setState({ status: "ready", counts: g.counts, error: null });
      })
      .catch((e) => {
        if (cancelled) return;
        console.error("[relations] load failed", e);
        setState({ status: "error", counts: null, error: e.message || "network error" });
      });
    return () => { cancelled = true; };
  }, [tick]);

  const c = state.counts || { stars: 0, nodes: 0, projects: 0 };
  const live = state.status === "ready";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--pad-3)", height: "100%" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span className="chip accent"><span className="chip-dot"/>App galaxy · {live ? "live" : state.status}</span>
        {live && (
          <span className="chip"><span className="chip-dot" style={{ color: "var(--c-cal)" }}/>
            {c.projects} system{c.projects === 1 ? "" : "s"} · {c.nodes} nodes · {c.stars.toLocaleString()} stars</span>
        )}
        <span className="muted mono" style={{ fontSize: 11, marginLeft: 8 }}>zoom in to resolve modules &amp; tools</span>
      </div>
      <div style={{ flex: 1, minHeight: 0 }}>
        {state.status === "loading" && (
          <GalaxyStatus>
            <div className="mono" style={{ fontSize: 11, color: "var(--text-3)", letterSpacing: "0.14em", textTransform: "uppercase", marginBottom: 8 }}>Charting</div>
            <div style={{ fontSize: 16, color: "var(--text-2)" }}>Mapping the relations graph…</div>
          </GalaxyStatus>
        )}
        {state.status === "error" && (
          <GalaxyStatus>
            <h2 style={{ margin: "0 0 8px", fontSize: 18, fontWeight: 600 }}>Couldn't load relations</h2>
            <div className="mono" style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 16, wordBreak: "break-word" }}>{state.error}</div>
            <button className="btn accent" style={{ justifyContent: "center" }} onClick={() => setTick((t) => t + 1)}>Retry</button>
          </GalaxyStatus>
        )}
        {state.status === "ready" && <GalaxyGraph/>}
      </div>
    </div>
  );
}

window.Relations = Relations;
