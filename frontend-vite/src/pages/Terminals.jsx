// Terminals - 1 large + 5 small. Each terminal has a collapsible project header
// showing summary + recent activity + current goal/next steps.

import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { I } from '../Icons.jsx';
import { TERM_CONTEXT } from '../Data.jsx';
import { apiJson, postJson } from '../lib/api.js';

const TERM_PRESETS = [
  {
    title: "invisible - dashboard",
    cwd: "C:\\Users\\mahar\\repos\\invisible",
    lines: [
      { t: "prompt", c: "git status --short", path: "C:\\Users\\mahar\\repos\\invisible" },
      { t: "dim", c: " M lib\\api\\relations.py" },
      { t: "dim", c: " M frontend-vite\\src\\pages\\Terminals.jsx" },
      { t: "prompt", c: "py -m pytest tests\\test_local_ai_voice_handoff.py", path: "C:\\Users\\mahar\\repos\\invisible" },
      { t: "ok",  c: "focused tests ready to run" },
    ],
  },
  {
    title: "hot-tyres - web",
    cwd: "C:\\Users\\mahar\\repos\\hot-tyres",
    lines: [
      { t: "prompt", c: "Get-ChildItem", path: "C:\\Users\\mahar\\repos\\hot-tyres" },
      { t: "dim", c: "components  pages  public  package.json" },
      { t: "prompt", c: "corepack pnpm test", path: "C:\\Users\\mahar\\repos\\hot-tyres" },
      { t: "ok",  c: "local repo pane initialized" },
    ],
  },
  {
    title: "roofing-sydney - site",
    cwd: "C:\\Users\\mahar\\repos\\roofing.sydney",
    lines: [
      { t: "prompt", c: "git branch --show-current", path: "C:\\Users\\mahar\\repos\\roofing.sydney" },
      { t: "ok",  c: "main" },
      { t: "prompt", c: "corepack pnpm build", path: "C:\\Users\\mahar\\repos\\roofing.sydney" },
      { t: "dim", c: "waiting for local build command" },
    ],
  },
  {
    title: "moana - workspace",
    cwd: "C:\\Users\\mahar\\repos\\Moana",
    lines: [
      { t: "prompt", c: "Get-Location", path: "C:\\Users\\mahar\\repos\\Moana" },
      { t: "ok",  c: "Path" },
      { t: "dim", c: "----" },
      { t: "dim", c: "C:\\Users\\mahar\\repos\\Moana" },
    ],
  },
  {
    title: "claude-workflow-portable - tools",
    cwd: "C:\\Users\\mahar\\repos\\claude-workflow-portable",
    lines: [
      { t: "prompt", c: "Get-ChildItem .\\skills", path: "C:\\Users\\mahar\\repos\\claude-workflow-portable" },
      { t: "dim", c: "agent workflows available locally" },
      { t: "prompt", c: "git status --short", path: "C:\\Users\\mahar\\repos\\claude-workflow-portable" },
    ],
  },
  {
    title: "system - envy",
    cwd: "C:\\Users\\mahar",
    lines: [
      { t: "prompt", c: "Get-Content $env:INVISIBLE_HOME\\invisible.toml", path: "C:\\Users\\mahar" },
      { t: "dim", c: "[[projects]] includes invisible, hot-tyres, moana, roofing-sydney" },
      { t: "prompt", c: "gstack", path: "C:\\Users\\mahar\\repos\\invisible" },
    ],
  },
];

const PTY_BASE = localStorage.getItem("envy.ptyBase") || "ws://127.0.0.1:8091";
const XTERM_CSS_ID = "envy-xterm-css";
let xtermAssetPromise = null;

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[data-envy-src="${src}"]`);
    if (existing) {
      if (existing.dataset.loaded === "true") resolve();
      else {
        existing.addEventListener("load", resolve, { once: true });
        existing.addEventListener("error", reject, { once: true });
      }
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.dataset.envySrc = src;
    script.onload = () => {
      script.dataset.loaded = "true";
      resolve();
    };
    script.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(script);
  });
}

function loadXtermAssets() {
  if (window.Terminal && (window.FitAddon?.FitAddon || window.FitAddon)) return Promise.resolve();
  if (!xtermAssetPromise) {
    if (!document.getElementById(XTERM_CSS_ID)) {
      const link = document.createElement("link");
      link.id = XTERM_CSS_ID;
      link.rel = "stylesheet";
      link.href = "/vendor/xterm/xterm.css";
      document.head.appendChild(link);
    }
    xtermAssetPromise = loadScript("/vendor/xterm/xterm.js")
      .then(() => loadScript("/vendor/xterm/addon-fit.js"))
      .then(() => {
        if (!window.Terminal) throw new Error("xterm Terminal global missing");
      });
  }
  return xtermAssetPromise;
}

function shouldDropTerminalControlInput(data) {
  return /^\x1b\[\?[0-9;]*c$/.test(data) || data === "\x1b[I" || data === "\x1b[O";
}

const LOCAL_REPO_PATHS = {
  "claude-workflow-portable": "C:\\Users\\mahar\\repos\\claude-workflow-portable",
  "hot-tyres": "C:\\Users\\mahar\\repos\\hot-tyres",
  invisible: "C:\\Users\\mahar\\repos\\invisible",
  moana: "C:\\Users\\mahar\\repos\\Moana",
  "roofing-sydney": "C:\\Users\\mahar\\repos\\roofing.sydney",
};

function fallbackRepoPath(project) {
  const key = project.id || project.name;
  return project.repoPath || project.repo_path || LOCAL_REPO_PATHS[key] || `C:\\Users\\mahar\\repos\\${key}`;
}

function presetsFromProjects(projects) {
  if (!Array.isArray(projects) || !projects.length) return TERM_PRESETS.map((p, i) => ({ ...p, id: `pane-${i}` }));
  return projects.map((p) => {
    const cwd = fallbackRepoPath(p);
    return {
      id: p.id,
      title: p.name,
      cwd,
      projectId: p.id,
      color: p.color,
      lines: [
        { t: "dim", c: `Starting local PowerShell for ${p.name}...` },
      ],
    };
  });
}

function baseProjectId(preset) {
  return preset?.projectId || preset?.baseId || preset?.id;
}

function contextForPreset(preset) {
  const existing = TERM_CONTEXT[preset.title];
  if (existing) return existing;
  return {
    project: preset.title,
    projectId: preset.projectId || preset.id,
    color: preset.color || "var(--c-term)",
    goal: "Work directly in this repo with local PowerShell.",
    activity: [{ t: "now", k: "ok", c: "PowerShell pane connected to local PTY daemon" }],
    next: ["Run git status", "Run tests/builds", "Ask Envy to automate repeated commands"],
  };
}

function stripAnsi(text) {
  return String(text || "").replace(/\x1b\[[0-9;?]*[ -/]*[@-~]/g, "");
}

function appendTerminalText(setLines, rawText) {
  const raw = String(rawText || "");
  if (/\x1b\[(2J|3J)|\x1bc/.test(raw)) {
    setLines([]);
    return;
  }
  const text = stripAnsi(raw)
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n");
  if (!text) return;
  setLines((current) => {
    const next = [...current];
    const parts = text.split("\n");
    parts.forEach((part, index) => {
      if (index > 0) next.push({ t: "raw", c: "" });
      if (!part) return;
      const last = next[next.length - 1];
      if (last?.t === "raw") {
        next[next.length - 1] = { ...last, c: `${last.c}${part}` };
      } else {
        next.push({ t: "raw", c: part });
      }
    });
    return next.slice(-500);
  });
}

function ContextHeader({ ctx, focused }) {
  const [open, setOpen] = useState(focused);

  useEffect(() => { if (focused) setOpen(true); else setOpen(false); }, [focused]);

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
              <div className="term-ctx-label">Activity - last hour</div>
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
                    <span style={{ position: "absolute", left: 0, color: "var(--p-c)" }}>{">"}</span>
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

function Terminal({ idx, focused, onFocus, preset, ptyReady, ptyStatus, reconnectToken, requestPtyStart }) {
  const [lines, setLines] = useState(preset.lines);
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);
  const [xtermReady, setXtermReady] = useState(false);
  const bodyRef = useRef(null);
  const inputRef = useRef(null);
  const wsRef = useRef(null);
  const xtermHostRef = useRef(null);
  const xtermRef = useRef(null);
  const ctx = contextForPreset(preset);

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [lines]);

  useEffect(() => {
    setLines(preset.lines);
    setConnected(false);
    setXtermReady(false);
    xtermRef.current = null;
    if (!ptyReady) {
      setLines([
        ...preset.lines,
        { t: "warn", c: ptyStatus || "Starting local PTY daemon..." },
      ]);
      return;
    }
    let cancelled = false;
    let term = null;
    let fitAddon = null;
    let dataSubscription = null;
    let resizeObserver = null;
    const ws = new WebSocket(`${PTY_BASE}/pty/${preset.id}`);
    wsRef.current = ws;
    const sendResize = () => {
      if (!term || ws.readyState !== WebSocket.OPEN) return;
      ws.send(`\x1b]777;resize;${term.cols};${term.rows}\x07`);
    };

    loadXtermAssets()
      .then(() => {
        if (cancelled || !xtermHostRef.current) return;
        const TerminalCtor = window.Terminal;
        const FitAddonCtor = window.FitAddon?.FitAddon || window.FitAddon;
        term = new TerminalCtor({
          convertEol: true,
          cursorBlink: true,
          cursorStyle: "bar",
          fontFamily: "Consolas, 'Cascadia Mono', 'SFMono-Regular', monospace",
          fontSize: focused ? 12 : 11,
          lineHeight: 1.18,
          scrollback: 5000,
          theme: {
            background: "#06080d",
            foreground: "#d7e2ef",
            cursor: "#8bd3ff",
            selectionBackground: "#2d5f7a88",
            black: "#06080d",
            red: "#ff6b81",
            green: "#62e6ac",
            yellow: "#f7c859",
            blue: "#5cc8ff",
            magenta: "#b794ff",
            cyan: "#5ee0c8",
            white: "#d7e2ef",
            brightBlack: "#65758a",
            brightRed: "#ff8899",
            brightGreen: "#8ff0c4",
            brightYellow: "#ffe08a",
            brightBlue: "#8bd3ff",
            brightMagenta: "#c7a8ff",
            brightCyan: "#8af0dc",
            brightWhite: "#ffffff",
          },
          windowsMode: true,
        });
        fitAddon = FitAddonCtor ? new FitAddonCtor() : null;
        if (fitAddon) term.loadAddon(fitAddon);
        term.open(xtermHostRef.current);
        dataSubscription = term.onData((data) => {
          if (shouldDropTerminalControlInput(data)) return;
          if (ws.readyState === WebSocket.OPEN) ws.send(data);
        });
        requestAnimationFrame(() => {
          if (cancelled) return;
          fitAddon?.fit();
          sendResize();
          if (focused) term.focus();
        });
        resizeObserver = new ResizeObserver(() => {
          fitAddon?.fit();
          sendResize();
        });
        resizeObserver.observe(xtermHostRef.current);
        xtermRef.current = term;
        setXtermReady(true);
      })
      .catch((error) => {
        if (!cancelled) {
          setLines(l => [...l, { t: "warn", c: `${error.message}. Falling back to plain output.` }]);
        }
      });

    ws.onopen = () => {
      if (cancelled) {
        ws.close();
        return;
      }
      setConnected(true);
      setLines(l => [...l, { t: "ok", c: "connected to local PowerShell" }]);
      sendResize();
    };
    ws.onmessage = (event) => {
      if (cancelled) return;
      if (term) term.write(event.data);
      else appendTerminalText(setLines, event.data);
    };
    ws.onerror = () => {
      if (cancelled) return;
      setConnected(false);
      setLines(l => [...l, { t: "warn", c: "Real PTY unavailable. Retrying local daemon..." }]);
      requestPtyStart?.();
    };
    ws.onclose = () => {
      if (!cancelled) setConnected(false);
    };
    return () => {
      cancelled = true;
      if (wsRef.current === ws) wsRef.current = null;
      if (ws.readyState === WebSocket.OPEN) ws.close();
      resizeObserver?.disconnect();
      dataSubscription?.dispose();
      term?.dispose();
      if (xtermRef.current === term) xtermRef.current = null;
    };
  }, [preset.id, preset.lines, ptyReady, ptyStatus, reconnectToken, requestPtyStart]);

  useEffect(() => {
    if (!focused || !xtermRef.current) return;
    requestAnimationFrame(() => xtermRef.current?.focus());
  }, [focused]);

  const run = (cmd) => {
    const clean = cmd.trim();
    if (!clean) return;
    const cmdLine = { t: "prompt", c: clean, path: preset.cwd };
    if (connected && wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(`${clean}\r\n`);
      setInput("");
      return;
    }
    const lower = clean.toLowerCase();
    if (["clear", "cls", "clear-host"].includes(lower)) { setLines([]); setInput(""); return; }
    requestPtyStart?.();
    setLines(l => [
      ...l,
      cmdLine,
      { t: "err", c: "No live PTY is connected yet. Starting local PowerShell daemon; retry the command when the pane is live." },
    ]);
    setInput("");
  };

  const onKey = (e) => { if (e.key === "Enter") { e.preventDefault(); run(input); } };

  return (
    <div
      className={"term-pane " + (focused ? "focused" : "small")}
      onClick={() => {
        onFocus();
        setTimeout(() => {
          if (xtermRef.current) xtermRef.current.focus();
          else inputRef.current?.focus();
        }, 50);
      }}
    >
      <div className="term-head">
        <div className="term-dots">
          <div className="term-dot r"/><div className="term-dot y"/><div className="term-dot g"/>
        </div>
        <span className="term-title">{preset.title}</span>
        <span className="term-status">{connected ? "live" : "offline"}</span>
      </div>

      <ContextHeader ctx={ctx} focused={focused}/>

      <div className={"term-body " + (xtermReady ? "xterm-mode" : "")} ref={bodyRef}>
        <div
          className="term-xterm-host"
          ref={xtermHostRef}
          onClick={() => xtermRef.current?.focus()}
          style={{ display: xtermReady ? "block" : "none" }}
        />
        {!xtermReady && (
        <>
        {lines.map((ln, i) => (
          <div key={i}>
            {ln.t === "prompt" ? (
              <><span className="path">{ln.path}</span>{" "}<span className="prompt">PS&gt;</span> {ln.c}</>
            ) : (
              <span className={ln.t} style={ln.t === "raw" ? { whiteSpace: "pre-wrap" } : undefined}>{ln.c}</span>
            )}
          </div>
        ))}
        <div>
          <span className="path">{preset.cwd}</span>{" "}
          <span className="prompt">PS&gt;</span>{" "}
          <input
            ref={inputRef}
            className="term-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={onKey}
            spellCheck={false}
            autoComplete="off"
          />
          <span className="term-caret"/>
        </div>
        </>
        )}
      </div>
    </div>
  );
}

function Terminals({ projects, selectedProject, setSelectedProject, onSessionCountChange }) {
  const basePresets = useMemo(() => presetsFromProjects(projects), [projects]);
  const [extraSessions, setExtraSessions] = useState([]);
  const [pendingFocusId, setPendingFocusId] = useState(null);
  const presets = useMemo(() => {
    const baseIds = new Set(basePresets.map(p => p.projectId || p.id));
    return [
      ...basePresets,
      ...extraSessions.filter(s => baseIds.has(baseProjectId(s))),
    ];
  }, [basePresets, extraSessions]);
  useEffect(() => {
    onSessionCountChange?.(presets.length);
  }, [onSessionCountChange, presets.length]);
  const [ptyState, setPtyState] = useState({
    ready: false,
    status: "Starting local PTY daemon...",
    reconnectToken: 0,
  });

  const ensurePty = useCallback(async () => {
    setPtyState(s => ({ ...s, status: "Checking local PTY daemon..." }));
    try {
      const status = await apiJson("/api/v1/pty/status");
      if (status.running) {
        setPtyState(s => ({
          ready: true,
          status: `PTY online at ${status.ws_base}`,
          reconnectToken: s.reconnectToken + 1,
        }));
        return;
      }
      const started = await postJson("/api/v1/pty/start", {});
      setPtyState(s => ({
        ready: Boolean(started.running),
        status: started.running ? `PTY online at ${started.ws_base}` : (started.error || "PTY daemon unavailable"),
        reconnectToken: s.reconnectToken + 1,
      }));
    } catch (e) {
      setPtyState(s => ({
        ...s,
        ready: false,
        status: e.message || "PTY daemon unavailable",
      }));
    }
  }, []);

  useEffect(() => {
    ensurePty();
  }, [ensurePty]);
  // Match selectedProject to the terminal whose context.projectId equals it.
  const initial = (() => {
    if (!selectedProject) return 0;
    const i = presets.findIndex(p => baseProjectId(p) === selectedProject);
    return i >= 0 ? i : 0;
  })();
  const [focusIdx, setFocusIdx] = useState(initial);

  useEffect(() => {
    if (!selectedProject) return;
    const i = presets.findIndex(p => baseProjectId(p) === selectedProject);
    if (i >= 0) setFocusIdx(i);
  }, [selectedProject, presets]);

  // Order so focused goes first (takes large slot)
  const safeFocusIdx = Math.min(focusIdx, Math.max(0, presets.length - 1));
  const order = [safeFocusIdx, ...presets.map((_, i) => i).filter(i => i !== safeFocusIdx)];
  const focusedCtx = contextForPreset(presets[safeFocusIdx]);
  const addSession = useCallback(() => {
    const current = presets[safeFocusIdx];
    if (!current) return;
    const projectId = baseProjectId(current);
    const all = [...basePresets, ...extraSessions];
    const siblings = all.filter(s => baseProjectId(s) === projectId);
    const nextNumber = Math.max(1, ...siblings.map(s => Number(s.sessionNumber || 1)).filter(Number.isFinite)) + 1;
    const baseTitle = current.baseTitle || current.title.replace(/\s+#\d+$/, "");
    const session = {
      ...current,
      id: `${projectId}-${nextNumber}`,
      baseId: projectId,
      projectId,
      baseTitle,
      title: `${baseTitle} #${nextNumber}`,
      sessionNumber: nextNumber,
      lines: [{ t: "dim", c: `Starting additional PowerShell session for ${baseTitle}...` }],
    };
    setExtraSessions(existing => [...existing, session]);
    setPendingFocusId(session.id);
    if (projectId) setSelectedProject(projectId);
  }, [basePresets, extraSessions, presets, safeFocusIdx, setSelectedProject]);

  useEffect(() => {
    if (!pendingFocusId) return;
    const i = presets.findIndex(p => p.id === pendingFocusId);
    if (i >= 0) {
      setFocusIdx(i);
      setPendingFocusId(null);
    }
  }, [pendingFocusId, presets]);

  return (
    <>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: "var(--pad-3)", flexWrap: "wrap" }}>
        <span className="chip accent"><span className="chip-dot"/>{presets.length} sessions - PowerShell</span>
        <span className="chip"><span className="chip-dot" style={{ color: ptyState.ready ? "var(--c-term)" : "var(--c-dash)" }}/>{ptyState.status}</span>
        {focusedCtx && (
          <span className="chip" style={{ borderColor: `color-mix(in oklab, ${focusedCtx.color} 35%, transparent)` }}>
            <span className="chip-dot" style={{ color: focusedCtx.color }}/>
            {focusedCtx.project}
          </span>
        )}
        <span className="muted mono" style={{ fontSize: 11, marginLeft: 4 }}>Click small panes to swap focus - headers expand for project context</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          {presets.map((t, i) => {
            const c = contextForPreset(t)?.color;
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
                  const pid = baseProjectId(t);
                  if (pid) setSelectedProject(pid);
                }}
                title={contextForPreset(t)?.project || t.title}
              >
                {i + 1}
              </button>
            );
          })}
          <button className="btn" onClick={addSession} title="Add another session for the focused project">
            <I.Plus size={12}/>
          </button>
        </div>
      </div>
      <div className="term-layout" style={{ height: "calc(100% - 56px)" }}>
        {order.map((i, slot) => (
          <Terminal
            key={presets[i].id}
            idx={i}
            preset={presets[i]}
            focused={slot === 0}
            ptyReady={ptyState.ready}
            ptyStatus={ptyState.status}
            reconnectToken={ptyState.reconnectToken}
            requestPtyStart={ensurePty}
            onFocus={() => {
              setFocusIdx(i);
              const pid = baseProjectId(presets[i]);
              if (pid) setSelectedProject(pid);
            }}
          />
        ))}
      </div>
    </>
  );
}

export default Terminals;
