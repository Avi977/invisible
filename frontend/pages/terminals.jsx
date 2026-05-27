// Terminals — 1 large + 5 small. Each pane mounts a real xterm.js Terminal
// connected to the local PTY daemon over WebSocket.
//
// Requires bin/invisible-pty running on 127.0.0.1:8091. See START_HERE.md.
//
// Daemon contract (Plans 01 + 02):
//   - WS  ws://127.0.0.1:8091/pty/{pane_id}  — bidirectional text frames.
//                                              client → daemon: keystrokes.
//                                              daemon → client: PTY output.
//                                              On reconnect inside the daemon's
//                                              grace window (default 600s), the
//                                              first frame is the backlog replay.
//   - GET http://127.0.0.1:8091/context/{pane_id}  → {goal, activity, next} or {}
//
// Whether a given pane id resolves to bash or ssh is decided server-side by
// the daemon's `invisible.toml [[terminals]]` blocks (Plan 02). The frontend
// only ever names panes by id; `kind` and `host` are server config.

const { useState: useStateT, useRef: useRefT, useEffect: useEffectT } = React;

// Fixed 6-pane roster. Pane ids match the daemon's PANE_ID_RE (^[a-z0-9_-]{1,32}$).
// `title` is for display only. `project_color` drives the per-pane accent (chip
// dot, focused border, context header tint). `project_id` reserved for future
// linkage with the Projects sidebar — null today; the daemon doesn't bind
// panes to projects in Plan 02.
const PTY_PANES = [
  { id: "local-1", title: "local · zsh",     project_color: "#5cc8ff", project_id: null },
  { id: "local-2", title: "local · build",   project_color: "#b794ff", project_id: null },
  { id: "local-3", title: "local · scratch", project_color: "#f5b343", project_id: null },
  { id: "vps-srv", title: "vps · srv982719", project_color: "#4ade80", project_id: null },
  { id: "vps-log", title: "vps · logs",      project_color: "#5ee0c8", project_id: null },
  { id: "vps-k3s", title: "vps · k3s",       project_color: "#f56fb1", project_id: null },
];

function ContextHeader({ ctx, focused }) {
  const [open, setOpen] = useStateT(focused);

  useEffectT(() => { if (focused) setOpen(true); else setOpen(false); }, [focused]);

  if (!ctx) return null;

  return (
    <div className={"term-ctx " + (open ? "open" : "")} style={{ "--p-c": ctx.color }}>
      <button className="term-ctx-toggle" onClick={(e) => { e.stopPropagation(); setOpen(o => !o); }}>
        <span className="term-ctx-dot"/>
        <span className="term-ctx-name">{ctx.project}</span>
        <span className="term-ctx-goal">{open ? "" : ctx.goal}</span>
        <I.ChevronD size={11} className="term-ctx-chev"/>
      </button>

      {open && (
        <div className="term-ctx-body">
          <div className="term-ctx-section">
            <div className="term-ctx-label">Current goal</div>
            <p className="term-ctx-text">{ctx.goal}</p>
          </div>

          <div className="term-ctx-cols">
            <div className="term-ctx-section">
              <div className="term-ctx-label">Activity · last hour</div>
              <ul className="term-ctx-list">
                {ctx.activity.map((a, i) => (
                  <li key={i}>
                    <span className="mono dim" style={{ marginRight: 8, fontSize: 10 }}>{a.t}</span>
                    <span className={"term-ctx-" + a.k}>{a.c}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="term-ctx-section">
              <div className="term-ctx-label">What's next</div>
              <ul className="term-ctx-list">
                {ctx.next.map((n, i) => (
                  <li key={i} style={{ paddingLeft: 14, position: "relative" }}>
                    <span style={{ position: "absolute", left: 0, color: "var(--p-c)" }}>›</span>
                    {n}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function TerminalPane({ idx, focused, onFocus, pane }) {
  const containerRef = useRefT(null);
  const termRef = useRefT(null);
  const fitRef = useRefT(null);
  const wsRef = useRefT(null);
  const [ctxRaw, setCtxRaw] = useStateT(null);

  // Boot xterm + WS once per mount (per pane.id). pane.id is stable for the
  // life of the page so an empty dep array is intentional — we want exactly
  // one Terminal/WebSocket per slot.
  useEffectT(() => {
    if (!containerRef.current) return;
    if (!window.Terminal || !window.FitAddon) {
      // unpkg hadn't loaded — surface visibly instead of a silent black pane.
      containerRef.current.textContent = "[xterm.js failed to load from unpkg]";
      return;
    }

    const term = new window.Terminal({
      fontSize: 12,
      fontFamily: "Geist Mono, ui-monospace, monospace",
      theme: { background: "rgba(0,0,0,0)", foreground: "#e5e7eb" },
      cursorBlink: true,
      allowTransparency: true,
      scrollback: 5000,
    });
    const fit = new window.FitAddon.FitAddon();
    term.loadAddon(fit);
    term.open(containerRef.current);
    try { fit.fit(); } catch (_e) { /* container not laid out yet — first frame will fit */ }
    termRef.current = term;
    fitRef.current = fit;

    const ws = new WebSocket(`ws://127.0.0.1:8091/pty/${pane.id}`);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    const writeDisconnected = () => {
      try {
        term.write("\r\n\x1b[31m[disconnected — invisible-pty not running on :8091]\x1b[0m\r\n");
      } catch (_e) { /* term may already be disposed */ }
    };

    ws.onopen = () => {
      // Send an initial resize hint as a soft signal; daemon ignores it but
      // browsers vary on first-frame timing — re-fit on next tick is safest.
      setTimeout(() => { try { fit.fit(); } catch (_e) {} }, 0);
    };

    ws.onmessage = (ev) => {
      // Plan 01/02 send text frames. If a binary frame ever arrives, decode it.
      if (typeof ev.data === "string") {
        term.write(ev.data);
      } else if (ev.data instanceof ArrayBuffer) {
        term.write(new TextDecoder().decode(ev.data));
      }
    };

    ws.onclose = () => writeDisconnected();
    ws.onerror = () => writeDisconnected();

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(data);
    });

    const onResize = () => { try { fit.fit(); } catch (_e) {} };
    window.addEventListener("resize", onResize);

    // Re-fit when this pane changes focus (large ↔ small swap).
    const refitAfterLayout = setTimeout(() => { try { fit.fit(); } catch (_e) {} }, 60);

    // Fetch pane context once on mount. Failure → null (collapsed header).
    fetch(`http://127.0.0.1:8091/context/${pane.id}`)
      .then(r => r.ok ? r.json() : null)
      .then(setCtxRaw)
      .catch(() => setCtxRaw(null));

    return () => {
      window.removeEventListener("resize", onResize);
      clearTimeout(refitAfterLayout);
      try { ws.close(); } catch (_e) {}
      try { term.dispose(); } catch (_e) {}
      termRef.current = null;
      fitRef.current = null;
      wsRef.current = null;
    };
  }, [pane.id]);

  // Re-fit when focus toggles between large and small (geometry changed).
  useEffectT(() => {
    const t = setTimeout(() => { try { fitRef.current && fitRef.current.fit(); } catch (_e) {} }, 80);
    return () => clearTimeout(t);
  }, [focused]);

  // Merge daemon's live context with the local visual identity. The daemon
  // owns goal/activity/next; PTY_PANES owns project/color.
  // - ctxRaw null  → fetch failed (daemon down or network error). Show collapsed.
  // - ctxRaw {}    → no checkpoint exists for this pane id. Show collapsed.
  // - ctxRaw {…}   → merge daemon fields + visual identity.
  const ctx = (ctxRaw && Object.keys(ctxRaw).length > 0)
    ? { ...ctxRaw, project: pane.title, color: pane.project_color }
    : { project: pane.title, color: pane.project_color, goal: "", activity: [], next: [] };

  return (
    <div
      className={"term-pane " + (focused ? "focused" : "small")}
      onClick={() => { onFocus(); setTimeout(() => termRef.current?.focus(), 50); }}
    >
      <div className="term-head">
        <div className="term-dots">
          <div className="term-dot r"/><div className="term-dot y"/><div className="term-dot g"/>
        </div>
        <span className="term-title">{pane.title}</span>
        <span className="term-status">● live</span>
      </div>

      <ContextHeader ctx={ctx} focused={focused}/>

      <div className="term-body" style={{ padding: 0, whiteSpace: "normal", wordBreak: "normal" }}>
        <div ref={containerRef} className="term-xterm-host" style={{ width: "100%", height: "100%" }}/>
      </div>
    </div>
  );
}

function Terminals({ projects, selectedProject, setSelectedProject }) {
  // Match selectedProject to the pane whose project_id equals it. With Plan 02
  // bindings still server-side-only, project_id is null for all panes — the
  // lookup returns -1 and we keep the user's last focusIdx. The hook is
  // preserved as the wiring seam for a future plan that maps panes to projects.
  const initial = (() => {
    if (!selectedProject) return 0;
    const i = PTY_PANES.findIndex(p => p.project_id === selectedProject);
    return i >= 0 ? i : 0;
  })();
  const [focusIdx, setFocusIdx] = useStateT(initial);

  useEffectT(() => {
    if (!selectedProject) return;
    const i = PTY_PANES.findIndex(p => p.project_id === selectedProject);
    if (i >= 0) setFocusIdx(i);
  }, [selectedProject]);

  // Order so focused goes first (takes large slot)
  const order = [focusIdx, ...PTY_PANES.map((_, i) => i).filter(i => i !== focusIdx)];
  const focusedPane = PTY_PANES[focusIdx];

  return (
    <>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: "var(--pad-3)", flexWrap: "wrap" }}>
        <span className="chip accent"><span className="chip-dot"/>6 sessions · zsh</span>
        {focusedPane && (
          <span className="chip" style={{ borderColor: `color-mix(in oklab, ${focusedPane.project_color} 35%, transparent)` }}>
            <span className="chip-dot" style={{ color: focusedPane.project_color }}/>
            {focusedPane.title}
          </span>
        )}
        <span className="muted mono" style={{ fontSize: 11, marginLeft: 4 }}>Click small panes to swap focus · headers expand for project context</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          {PTY_PANES.map((p, i) => {
            const c = p.project_color;
            return (
              <button
                key={i}
                className={"btn " + (i === focusIdx ? "accent" : "")}
                style={{
                  padding: "5px 9px",
                  fontSize: 11,
                  fontFamily: "var(--font-mono)",
                  "--accent": c || undefined,
                  "--accent-soft": c ? `color-mix(in oklab, ${c} 22%, transparent)` : undefined,
                  color: i === focusIdx && c ? c : undefined,
                }}
                onClick={() => {
                  setFocusIdx(i);
                  if (p.project_id) setSelectedProject(p.project_id);
                }}
                title={p.title}
              >
                {i + 1}
              </button>
            );
          })}
          <button className="btn"><I.Plus size={12}/></button>
        </div>
      </div>
      <div className="term-layout" style={{ height: "calc(100% - 56px)" }}>
        {order.map((i, slot) => (
          <TerminalPane
            key={PTY_PANES[i].id}
            idx={i}
            pane={PTY_PANES[i]}
            focused={slot === 0}
            onFocus={() => {
              setFocusIdx(i);
              if (PTY_PANES[i].project_id) setSelectedProject(PTY_PANES[i].project_id);
            }}
          />
        ))}
      </div>
    </>
  );
}

window.Terminals = Terminals;
