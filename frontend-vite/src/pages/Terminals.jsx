// Terminals — 1 large + 5 small. Each terminal has a collapsible project header
// showing summary + recent activity + current goal/next steps.

import { useState, useRef, useEffect } from 'react';
import { I } from '../Icons.jsx';
import { TERM_CONTEXT } from '../Data.jsx';

const TERM_PRESETS = [
  {
    title: "echo · ios",
    cwd: "~/code/echo/ios",
    lines: [
      { t: "prompt", c: "swift build", path: "~/code/echo/ios" },
      { t: "ok",  c: "Building for iOS Simulator…" },
      { t: "dim", c: "[1/12] Compiling Recorder.swift" },
      { t: "dim", c: "[7/12] Compiling Whisper.swift" },
      { t: "warn", c: "warning: deprecated AVAudioSessionInterruptionTypeKey" },
      { t: "ok",  c: "Build complete! (4.21s)" },
      { t: "prompt", c: "xcrun simctl boot iPhone15", path: "~/code/echo/ios" },
    ],
  },
  {
    title: "lumen · dev",
    cwd: "~/code/lumen",
    lines: [
      { t: "prompt", c: "pnpm dev", path: "~/code/lumen" },
      { t: "dim", c: "› next dev --turbo" },
      { t: "ok",  c: "▲ Next.js 14.2.3 ·  Local: http://localhost:3000" },
      { t: "ok",  c: "✓ Ready in 1.2s" },
      { t: "dim", c: "○ Compiling /dashboard …" },
      { t: "ok",  c: "✓ Compiled /dashboard in 380ms" },
    ],
  },
  {
    title: "drift · build",
    cwd: "~/code/drift",
    lines: [
      { t: "prompt", c: "astro build", path: "~/code/drift" },
      { t: "dim", c: "12:42:18 [build] output: \"static\"" },
      { t: "ok",  c: "▶ /index.html        (15ms)" },
      { t: "ok",  c: "▶ /waitlist          (22ms)" },
      { t: "ok",  c: "▶ /privacy           (8ms)" },
      { t: "ok",  c: "✓ Completed in 1.84s" },
    ],
  },
  {
    title: "atlas · k3s",
    cwd: "ssh fsn1",
    lines: [
      { t: "prompt", c: "kubectl get pods -A", path: "fsn1:/srv/atlas" },
      { t: "dim", c: "NAMESPACE     NAME                    READY   STATUS    AGE" },
      { t: "dim", c: "argocd        argocd-server-7f8       1/1     Running   3d" },
      { t: "dim", c: "ferry         ferry-69d97cbb56-2bx    1/1     Running   12h" },
      { t: "dim", c: "lumen-stage   lumen-7d6f9-x          1/1     Running   45m" },
      { t: "err", c: "kube-system   metrics-server-7s      0/1     CrashLoop 8m" },
    ],
  },
  {
    title: "rune · python",
    cwd: "~/code/rune",
    lines: [
      { t: "prompt", c: "python pair.py --font Inter.ttf", path: "~/code/rune" },
      { t: "dim", c: "Loading Inter.ttf … 18 axes detected" },
      { t: "dim", c: "Generating 12 weight pairs" },
      { t: "dim", c: "Querying Claude for ratings…" },
      { t: "ok",  c: "✓ Saved pairings.json" },
    ],
  },
  {
    title: "ferry · logs",
    cwd: "ssh fsn1",
    lines: [
      { t: "prompt", c: "tail -f /var/log/ferry.log", path: "fsn1:/var/log" },
      { t: "ok",  c: "[12:42:01] POST /hook/github → 200 (12ms)" },
      { t: "ok",  c: "[12:42:14] POST /hook/stripe → 200 (8ms)" },
      { t: "warn", c: "[12:42:33] retry #2 → discord (timeout)" },
      { t: "ok",  c: "[12:42:38] POST /hook/discord → 200" },
    ],
  },
];

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

function Terminal({ idx, focused, onFocus, preset }) {
  const [lines, setLines] = useState(preset.lines);
  const [input, setInput] = useState("");
  const bodyRef = useRef(null);
  const inputRef = useRef(null);
  const ctx = TERM_CONTEXT[preset.title];

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [lines]);

  const run = (cmd) => {
    const cmdLine = { t: "prompt", c: cmd, path: preset.cwd };
    let out;
    const lower = cmd.trim().toLowerCase();
    if (!cmd.trim()) out = [];
    else if (lower === "clear" || lower === "cls") { setLines([]); return; }
    else if (lower.startsWith("ls"))   out = [{ t: "dim", c: "README.md  src/  package.json  .env.local  node_modules/" }];
    else if (lower.startsWith("git status")) out = [
      { t: "dim", c: "On branch " + (preset.title.includes("lumen") ? "feat/auth-v2" : "main") },
      { t: "ok",  c: "nothing to commit, working tree clean" },
    ];
    else if (lower.startsWith("pwd"))  out = [{ t: "dim", c: preset.cwd }];
    else if (lower.startsWith("date")) out = [{ t: "dim", c: new Date().toString() }];
    else if (lower.startsWith("echo ")) out = [{ t: "dim", c: cmd.slice(5) }];
    else if (lower.startsWith("help")) out = [{ t: "dim", c: "ls · pwd · date · git status · echo … · clear" }];
    else out = [{ t: "err", c: "command not found: " + cmd.split(" ")[0] }];

    setLines(l => [...l, cmdLine, ...out]);
    setInput("");
  };

  const onKey = (e) => { if (e.key === "Enter") { e.preventDefault(); run(input); } };

  return (
    <div
      className={"term-pane " + (focused ? "focused" : "small")}
      onClick={() => { onFocus(); setTimeout(() => inputRef.current?.focus(), 50); }}
    >
      <div className="term-head">
        <div className="term-dots">
          <div className="term-dot r"/><div className="term-dot y"/><div className="term-dot g"/>
        </div>
        <span className="term-title">{preset.title}</span>
        <span className="term-status">● live</span>
      </div>

      <ContextHeader ctx={ctx} focused={focused}/>

      <div className="term-body" ref={bodyRef}>
        {lines.map((ln, i) => (
          <div key={i}>
            {ln.t === "prompt" ? (
              <><span className="path">{ln.path}</span>{" "}<span className="prompt">$</span> {ln.c}</>
            ) : (
              <span className={ln.t}>{ln.c}</span>
            )}
          </div>
        ))}
        <div>
          <span className="path">{preset.cwd}</span>{" "}
          <span className="prompt">$</span>{" "}
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
      </div>
    </div>
  );
}

function Terminals({ projects, selectedProject, setSelectedProject }) {
  // Match selectedProject to the terminal whose context.projectId equals it.
  const initial = (() => {
    if (!selectedProject) return 0;
    const i = TERM_PRESETS.findIndex(p => TERM_CONTEXT[p.title]?.projectId === selectedProject);
    return i >= 0 ? i : 0;
  })();
  const [focusIdx, setFocusIdx] = useState(initial);

  useEffect(() => {
    if (!selectedProject) return;
    const i = TERM_PRESETS.findIndex(p => TERM_CONTEXT[p.title]?.projectId === selectedProject);
    if (i >= 0) setFocusIdx(i);
  }, [selectedProject]);

  // Order so focused goes first (takes large slot)
  const order = [focusIdx, ...TERM_PRESETS.map((_, i) => i).filter(i => i !== focusIdx)];
  const focusedCtx = TERM_CONTEXT[TERM_PRESETS[focusIdx].title];

  return (
    <>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: "var(--pad-3)", flexWrap: "wrap" }}>
        <span className="chip accent"><span className="chip-dot"/>6 sessions · zsh</span>
        {focusedCtx && (
          <span className="chip" style={{ borderColor: `color-mix(in oklab, ${focusedCtx.color} 35%, transparent)` }}>
            <span className="chip-dot" style={{ color: focusedCtx.color }}/>
            {focusedCtx.project}
          </span>
        )}
        <span className="muted mono" style={{ fontSize: 11, marginLeft: 4 }}>Click small panes to swap focus · headers expand for project context</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          {TERM_PRESETS.map((t, i) => {
            const c = TERM_CONTEXT[t.title]?.color;
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
                  const pid = TERM_CONTEXT[t.title]?.projectId;
                  if (pid) setSelectedProject(pid);
                }}
                title={TERM_CONTEXT[t.title]?.project || t.title}
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
          <Terminal
            key={i}
            idx={i}
            preset={TERM_PRESETS[i]}
            focused={slot === 0}
            onFocus={() => {
              setFocusIdx(i);
              const pid = TERM_CONTEXT[TERM_PRESETS[i].title]?.projectId;
              if (pid) setSelectedProject(pid);
            }}
          />
        ))}
      </div>
    </>
  );
}

export default Terminals;
