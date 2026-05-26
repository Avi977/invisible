// Focus mode — single project, single task. Tasklist + done log + small terminal
// on the left; a browser-tab preview of the dev's localhost on the right.

const { useState: useStateFC, useEffect: useEffectFC, useRef: useRefFC } = React;

// Per-project focus context (what the developer is heads-down on right now).
const FOCUS_CTX = {
  echo: {
    task: "Fix waveform jitter on audio session interrupt",
    progress: 60,
    subtasks: [
      { t: "Reproduce freeze on iPhone 15 sim",       done: true },
      { t: "Inspect AVAudioEngine restart sequence",  done: true },
      { t: "Resume engine before reconnecting tap",   done: false },
      { t: "Add unit test for interruption recovery", done: false },
      { t: "Verify with TestFlight build",            done: false },
    ],
    done: [
      { t: "12:42", c: "swift build · 4.21s, no errors" },
      { t: "12:30", c: "Pulled main · 3 commits behind" },
      { t: "12:18", c: "Recorder.swift refactor merged" },
      { t: "11:52", c: "Spec'd interruption recovery flow" },
    ],
    preview: "echo",
    previewUrl: "localhost:8081",
    previewTab: "Expo · Echo",
  },
  lumen: {
    task: "Generate RLS-aware widgets from partitioned tables",
    progress: 35,
    subtasks: [
      { t: "Walk pg_partitioned_table recursively",  done: true  },
      { t: "Identify partition key + ranges",         done: false },
      { t: "Emit per-partition widget candidates",    done: false },
      { t: "Cache widget tree to Redis (5m TTL)",     done: false },
    ],
    done: [
      { t: "12:40", c: "✓ Compiled /dashboard in 380ms" },
      { t: "12:25", c: "Fixed RLS parser for SECURITY DEFINER" },
      { t: "11:48", c: "Wrote 6 unit tests for schema walker" },
    ],
    preview: "lumen",
    previewUrl: "localhost:3000",
    previewTab: "Lumen · /dashboard",
  },
  drift: {
    task: "Set up verified sending domain and DKIM for Resend",
    progress: 25,
    subtasks: [
      { t: "Buy `drift.so` mail subdomain",            done: true },
      { t: "Add DKIM TXT record",                      done: false },
      { t: "Verify in Resend dashboard",               done: false },
      { t: "Switch test mode → live",                  done: false },
      { t: "Send 5 internal test emails",              done: false },
    ],
    done: [
      { t: "12:42", c: "astro build · 1.84s, 3 routes" },
      { t: "12:20", c: "OG images generated" },
      { t: "12:05", c: "Lighthouse mobile: 96 perf" },
    ],
    preview: "drift",
    previewUrl: "localhost:4321",
    previewTab: "Drift · waitlist",
  },
  atlas: {
    task: "Diagnose metrics-server CrashLoopBackOff",
    progress: 15,
    subtasks: [
      { t: "Pull metrics-server logs",        done: true },
      { t: "Inspect kubelet TLS bootstrapping", done: false },
      { t: "Patch --kubelet-insecure-tls flag", done: false },
      { t: "Restart pod and watch for 5 min",  done: false },
    ],
    done: [
      { t: "12:00", c: "Cilium installed · BGP peering up" },
      { t: "11:42", c: "3-node Hetzner cluster joined" },
    ],
    preview: "atlas",
    previewUrl: "localhost:9090",
    previewTab: "Atlas · k3s · metrics",
  },
  rune: {
    task: "Bias pairing model to weight optical-size axis",
    progress: 45,
    subtasks: [
      { t: "Survey 12 variable fonts for optical axis",  done: true },
      { t: "Add prompt nudge to consider optical size",   done: true },
      { t: "Re-run vision call on 6 specimens",           done: false },
      { t: "Compare scores against baseline",             done: false },
    ],
    done: [
      { t: "12:35", c: "Saved pairings.json (12 pairs)" },
      { t: "11:55", c: "Inter.ttf · 18 axes detected" },
    ],
    preview: "rune",
    previewUrl: "localhost:5173",
    previewTab: "Rune · specimen",
  },
  ferry: {
    task: "Polish v1.0.1 docs site and publish",
    progress: 70,
    subtasks: [
      { t: "Audit getting-started page",   done: true },
      { t: "Add 3 real-world examples",    done: true },
      { t: "Add structured-logging guide", done: false },
      { t: "Tag v1.0.1 and publish",       done: false },
    ],
    done: [
      { t: "12:42", c: "POST /hook/discord → 200" },
      { t: "11:30", c: "Docs site preview built clean" },
    ],
    preview: "ferry",
    previewUrl: "localhost:4000",
    previewTab: "Ferry · docs",
  },
};

// ── Previews — fake but tasteful localhost renders per project ─────────────
function EchoPreview() {
  return (
    <div className="prev-echo">
      <div className="prev-echo-phone">
        <div className="prev-echo-status">9:41</div>
        <div className="prev-echo-title">
          <div className="prev-echo-h">Today</div>
          <div className="prev-echo-sub">Tap to record · 3 entries</div>
        </div>
        <div className="prev-echo-entries">
          {[
            ["08:14", "Morning intent",  "00:42"],
            ["12:03", "Standup recap",   "01:28"],
            ["13:51", "Bug walk-through","02:15"],
          ].map(([t, n, d], i) => (
            <div key={i} className="prev-echo-entry">
              <div>
                <div style={{ fontSize: 11, color: "#a08960", fontFamily: "var(--font-mono)" }}>{t}</div>
                <div style={{ fontSize: 13, color: "#2a2516", marginTop: 2 }}>{n}</div>
              </div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "#a08960" }}>{d}</div>
            </div>
          ))}
        </div>
        <div className="prev-echo-wave">
          {Array.from({length: 48}).map((_, i) => (
            <div key={i} style={{
              height: 4 + Math.abs(Math.sin(i * 0.4) * 28),
              background: "#d97757",
              opacity: 0.6 + Math.sin(i * 0.3) * 0.3,
              animation: `echo-pulse 1.4s ${i * 30}ms ease-in-out infinite alternate`,
            }}/>
          ))}
        </div>
        <div className="prev-echo-record"/>
      </div>
    </div>
  );
}

function LumenPreview() {
  const stats = [["Total users", "12,418"], ["Active /day", "3,201"], ["Errors /hr", "12"], ["p95 latency", "184ms"]];
  return (
    <div className="prev-lumen">
      <div className="prev-lumen-side">
        <div style={{ fontFamily: "var(--font-mono)", color: "#7c818f", fontSize: 11, marginBottom: 10 }}>LUMEN</div>
        {["Overview","Users","Sessions","Errors","SQL","Settings"].map((x, i) => (
          <div key={x} style={{ padding: "6px 10px", borderRadius: 6, fontSize: 12, color: i === 0 ? "#0a0b10" : "#51555f", background: i === 0 ? "#5cc8ff" : "transparent", marginBottom: 2 }}>
            {x}
          </div>
        ))}
      </div>
      <div className="prev-lumen-main">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: "#e6e9f0" }}>Overview</div>
          <span style={{ fontFamily: "var(--font-mono)", color: "#7c818f", fontSize: 11 }}>last 24h · auto</span>
        </div>
        <div className="prev-lumen-stats">
          {stats.map(([l, v]) => (
            <div key={l} className="prev-lumen-stat">
              <div style={{ fontSize: 10, color: "#7c818f", fontFamily: "var(--font-mono)", letterSpacing: "0.1em", textTransform: "uppercase" }}>{l}</div>
              <div style={{ fontSize: 22, fontWeight: 600, color: "#e6e9f0", marginTop: 4 }}>{v}</div>
            </div>
          ))}
        </div>
        <div className="prev-lumen-chart">
          <svg viewBox="0 0 400 100" preserveAspectRatio="none" style={{ width: "100%", height: "100%" }}>
            <defs>
              <linearGradient id="lumen-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"  stopColor="#5cc8ff" stopOpacity="0.4"/>
                <stop offset="100%" stopColor="#5cc8ff" stopOpacity="0"/>
              </linearGradient>
            </defs>
            <path d="M0 70 L 30 60 L 60 65 L 90 50 L 120 55 L 150 35 L 180 40 L 210 30 L 240 45 L 270 25 L 300 35 L 330 20 L 360 28 L 400 18 L 400 100 L 0 100 Z"
                  fill="url(#lumen-fill)"/>
            <path d="M0 70 L 30 60 L 60 65 L 90 50 L 120 55 L 150 35 L 180 40 L 210 30 L 240 45 L 270 25 L 300 35 L 330 20 L 360 28 L 400 18"
                  stroke="#5cc8ff" strokeWidth="1.5" fill="none"/>
          </svg>
        </div>
        <div className="prev-lumen-table">
          <div className="prev-lumen-row prev-lumen-head">
            <span>endpoint</span><span>req</span><span>p95</span><span>err</span>
          </div>
          {[
            ["GET /users",      "8,142", "84ms",  "0.1%"],
            ["POST /auth",      "2,890", "184ms", "0.4%"],
            ["GET /dashboard",  "5,712", "210ms", "0.0%"],
            ["POST /sync",        "412", "1.2s",  "2.1%"],
          ].map((r, i) => (
            <div key={i} className="prev-lumen-row">
              {r.map((c, j) => <span key={j}>{c}</span>)}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function DriftPreview() {
  return (
    <div className="prev-drift">
      <div className="prev-drift-nav">
        <div style={{ fontFamily: "var(--font-mono)", fontWeight: 600, fontSize: 13 }}>drift</div>
        <div style={{ display: "flex", gap: 18, fontSize: 12, color: "#9ba0aa" }}>
          <span>Product</span><span>Pricing</span><span>About</span>
        </div>
        <div style={{ fontSize: 11, padding: "5px 11px", borderRadius: 999, background: "#b794ff", color: "#1a1424" }}>Join waitlist</div>
      </div>
      <div className="prev-drift-hero">
        <div className="prev-drift-eyebrow">VOICE-FIRST · IOS Q3 2026</div>
        <h1 className="prev-drift-h1">A journal that listens<br/>more than it asks.</h1>
        <p className="prev-drift-p">Capture thoughts the moment they arrive. Echo synthesizes your daily themes — without you ever opening a writing app.</p>
        <div style={{ display: "flex", gap: 8, marginTop: 18 }}>
          <input className="prev-drift-input" placeholder="your@email.com"/>
          <button className="prev-drift-btn">Get early access</button>
        </div>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "#7c818f", marginTop: 14 }}>1,284 already on the list</div>
      </div>
    </div>
  );
}

function MetricsPreview() {
  // Atlas — grafana-ish
  const series = Array.from({length: 60}, (_, i) => 40 + Math.sin(i / 5) * 12 + Math.random() * 6);
  const max = Math.max(...series);
  return (
    <div className="prev-metrics">
      <div className="prev-metrics-head">
        <span style={{ color: "#4ade80", fontFamily: "var(--font-mono)", fontSize: 11 }}>● k3s.fsn1.local</span>
        <span style={{ fontFamily: "var(--font-mono)", color: "#7c818f", fontSize: 11 }}>refreshing · 5s</span>
      </div>
      <div className="prev-metrics-row">
        {["CPU","MEM","NET"].map((l, k) => (
          <div key={l} className="prev-metrics-card">
            <div style={{ fontFamily: "var(--font-mono)", color: "#7c818f", fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase" }}>{l}</div>
            <div style={{ fontSize: 24, fontWeight: 600, color: "#e6e9f0", marginTop: 4 }}>{[18,42,7][k]}%</div>
            <svg viewBox="0 0 60 30" style={{ width: "100%", height: 32, marginTop: 6 }}>
              <polyline
                points={series.slice(k*20, k*20+20).map((v, i) => `${i * 3},${30 - (v/max)*28}`).join(" ")}
                fill="none" stroke="#4ade80" strokeWidth="1.2"/>
            </svg>
          </div>
        ))}
      </div>
      <div className="prev-metrics-logs">
        {[
          ["ERR", "metrics-server CrashLoopBackOff (restart 4)"],
          ["OK",  "argocd-server-7f8 healthy"],
          ["OK",  "ferry-69d97cbb56-2bx healthy"],
          ["OK",  "lumen-stage-7d6f9-x healthy"],
        ].map(([k, m], i) => (
          <div key={i} className={"prev-metrics-log " + (k === "ERR" ? "err" : "ok")}>
            <span style={{ width: 28 }}>{k}</span>
            <span>{m}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function FontPreview() {
  return (
    <div className="prev-font">
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "#7c818f", letterSpacing: "0.16em", textTransform: "uppercase" }}>Specimen · Inter — 12 / 24 / 64</div>
      <div style={{ fontSize: 80, fontWeight: 700, lineHeight: 1, letterSpacing: "-0.04em", color: "#e6e9f0", marginTop: 14 }}>Aa</div>
      <div style={{ fontSize: 28, color: "#b6bac4", marginTop: 12, lineHeight: 1.2 }}>Type is the voice of intent — small choices, large impact.</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 14, marginTop: 22 }}>
        {[100,300,400,500,700,900].map(w => (
          <div key={w} style={{ fontWeight: w, fontSize: 18, color: "#e6e9f0" }}>Hg</div>
        ))}
      </div>
    </div>
  );
}

function LogsPreview() {
  // Ferry — webhook event stream
  return (
    <div className="prev-logs">
      {[
        ["12:42:38", "200", "POST /hook/discord", "12ms"],
        ["12:42:33", "RTRY", "discord timeout, retry #2", "—"],
        ["12:42:14", "200", "POST /hook/stripe",  "8ms"],
        ["12:42:01", "200", "POST /hook/github",  "12ms"],
        ["12:41:58", "200", "POST /hook/linear",  "9ms"],
        ["12:41:30", "200", "POST /hook/github",  "14ms"],
        ["12:41:01", "404", "POST /hook/_bad",    "3ms"],
        ["12:40:50", "200", "POST /hook/stripe",  "8ms"],
      ].map(([t, s, m, d], i) => (
        <div key={i} className="prev-logs-row">
          <span style={{ fontFamily: "var(--font-mono)", color: "#7c818f", width: 90 }}>{t}</span>
          <span className={"prev-logs-st " + (s === "200" ? "ok" : s === "RTRY" ? "warn" : "err")}>{s}</span>
          <span style={{ flex: 1, color: "#e6e9f0" }}>{m}</span>
          <span style={{ fontFamily: "var(--font-mono)", color: "#7c818f" }}>{d}</span>
        </div>
      ))}
    </div>
  );
}

function previewFor(kind) {
  switch (kind) {
    case "echo":  return <EchoPreview/>;
    case "lumen": return <LumenPreview/>;
    case "drift": return <DriftPreview/>;
    case "atlas": return <MetricsPreview/>;
    case "rune":  return <FontPreview/>;
    case "ferry": return <LogsPreview/>;
    default:      return <LumenPreview/>;
  }
}

// ── Mini terminal ──────────────────────────────────────────────────────────
function MiniTerm({ project, color }) {
  const [lines, setLines] = useStateFC([
    { t: "prompt", c: "git status", path: `~/code/${project}` },
    { t: "ok",     c: "On branch main · clean" },
    { t: "prompt", c: `pnpm dev`, path: `~/code/${project}` },
    { t: "ok",     c: "▲ ready · :3000" },
  ]);
  const [input, setInput] = useStateFC("");
  const bodyRef = useRefFC(null);
  const inputRef = useRefFC(null);

  useEffectFC(() => { if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight; }, [lines]);

  const run = (cmd) => {
    if (!cmd.trim()) return;
    const lower = cmd.trim().toLowerCase();
    if (lower === "clear") { setLines([]); setInput(""); return; }
    const cmdLine = { t: "prompt", c: cmd, path: `~/code/${project}` };
    let out;
    if (lower.startsWith("ls"))   out = [{ t: "dim", c: "src/  package.json  README.md  .env.local" }];
    else if (lower.startsWith("pwd")) out = [{ t: "dim", c: `~/code/${project}` }];
    else if (lower.startsWith("git")) out = [{ t: "ok", c: "On branch main · clean" }];
    else if (lower.startsWith("echo ")) out = [{ t: "dim", c: cmd.slice(5) }];
    else out = [{ t: "err", c: `command not found: ${cmd.split(" ")[0]}` }];
    setLines(l => [...l, cmdLine, ...out]);
    setInput("");
  };

  return (
    <div className="focus-term" onClick={() => inputRef.current?.focus()} style={{ "--p-c": color }}>
      <div className="focus-term-head">
        <div className="term-dots"><div className="term-dot r"/><div className="term-dot y"/><div className="term-dot g"/></div>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-2)" }}>{project} · zsh</span>
        <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--p-c)" }}>● live</span>
      </div>
      <div className="focus-term-body" ref={bodyRef}>
        {lines.map((ln, i) => (
          <div key={i}>
            {ln.t === "prompt"
              ? <><span style={{ color: "var(--c-fold)" }}>{ln.path}</span>{" "}<span style={{ color: "var(--p-c)" }}>$</span> {ln.c}</>
              : <span className={ln.t}>{ln.c}</span>}
          </div>
        ))}
        <div>
          <span style={{ color: "var(--c-fold)" }}>~/code/{project}</span>{" "}
          <span style={{ color: "var(--p-c)" }}>$</span>{" "}
          <input
            ref={inputRef}
            className="term-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); run(input); } }}
            spellCheck={false}
            autoComplete="off"
          />
          <span className="term-caret" style={{ background: color }}/>
        </div>
      </div>
    </div>
  );
}

// ── Pomodoro / focus timer ─────────────────────────────────────────────────
function FocusTimer({ color }) {
  const TOTAL = 25 * 60;
  const [remaining, setRemaining] = useStateFC(TOTAL);
  const [running, setRunning] = useStateFC(true);

  useEffectFC(() => {
    if (!running) return;
    const id = setInterval(() => {
      setRemaining(r => Math.max(0, r - 1));
    }, 1000);
    return () => clearInterval(id);
  }, [running]);

  const mm = String(Math.floor(remaining / 60)).padStart(2, "0");
  const ss = String(remaining % 60).padStart(2, "0");
  const pct = (TOTAL - remaining) / TOTAL;
  const r = 18;
  const C = 2 * Math.PI * r;
  return (
    <div className="focus-timer" onClick={() => setRunning(x => !x)} title={running ? "Pause" : "Resume"}>
      <svg width="44" height="44" viewBox="0 0 44 44">
        <circle cx="22" cy="22" r={r} stroke="rgba(255,255,255,0.08)" strokeWidth="2.5" fill="none"/>
        <circle cx="22" cy="22" r={r} stroke={color} strokeWidth="2.5" fill="none"
                strokeDasharray={C} strokeDashoffset={C * (1 - pct)} strokeLinecap="round"
                transform="rotate(-90 22 22)" style={{ transition: "stroke-dashoffset 800ms linear" }}/>
      </svg>
      <div className="focus-timer-time">
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-1)", lineHeight: 1 }}>{mm}:{ss}</div>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 8, color: "var(--text-4)", marginTop: 1, letterSpacing: "0.12em" }}>{running ? "FOCUS" : "PAUSED"}</div>
      </div>
    </div>
  );
}

// ── Browser preview chrome ─────────────────────────────────────────────────
function BrowserPreview({ ctx, color }) {
  const [tick, setTick] = useStateFC(0);
  return (
    <div className="focus-browser">
      <div className="focus-browser-chrome">
        <div className="term-dots"><div className="term-dot r"/><div className="term-dot y"/><div className="term-dot g"/></div>
        <button className="icon-btn" style={{ width: 22, height: 22 }} title="Back"><I.ChevronL size={12}/></button>
        <button className="icon-btn" style={{ width: 22, height: 22 }} title="Forward"><I.ChevronR size={12}/></button>
        <button className="icon-btn" style={{ width: 22, height: 22 }} title="Reload" onClick={() => setTick(t => t + 1)}><I.RefreshCw size={11}/></button>
        <div className="focus-url">
          <I.Lock size={10} stroke="var(--text-3)"/>
          <span style={{ color: "var(--text-3)" }}>http://</span>
          <span style={{ color: "var(--text-1)" }}>{ctx.previewUrl}</span>
          <span style={{ color: "var(--text-3)" }}>/</span>
        </div>
        <button className="icon-btn" style={{ width: 22, height: 22 }}><I.Dots size={14}/></button>
      </div>
      <div className="focus-browser-tabs">
        <div className="focus-browser-tab active" style={{ "--p-c": color }}>
          <span className="focus-browser-tab-dot"/>
          {ctx.previewTab}
          <I.X size={10} className="focus-browser-tab-close"/>
        </div>
        <div className="focus-browser-tab">+ new tab</div>
      </div>
      <div className="focus-browser-content" key={tick}>
        {previewFor(ctx.preview)}
      </div>
    </div>
  );
}

// ── Project picker (when none selected) ────────────────────────────────────
function FocusProjectPicker({ projects, onPick }) {
  const withCtx = projects.filter(p => FOCUS_CTX[p.id]);
  return (
    <div className="proj-picker">
      <div className="proj-picker-head">
        <div className="mono" style={{ fontSize: 10.5, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--text-3)" }}>
          Enter focus mode
        </div>
        <h2 style={{ margin: "6px 0 0", fontWeight: 600, fontSize: "calc(22px * var(--d))", letterSpacing: "-0.02em" }}>
          What's the one thing for the next 25 minutes?
        </h2>
        <p className="muted" style={{ fontSize: 12.5, maxWidth: 480, lineHeight: 1.55, marginTop: 8 }}>
          Focus mode hides everything but the task list, terminal, and live preview of the project you're shipping.
        </p>
      </div>
      <div className="proj-picker-grid">
        {withCtx.map(p => {
          const ctx = FOCUS_CTX[p.id];
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
                <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 3, lineHeight: 1.4, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {ctx.task}
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

// ── Main page ──────────────────────────────────────────────────────────────
function Focus({ projects, selectedProject, setSelectedProject }) {
  const projId = selectedProject && FOCUS_CTX[selectedProject] ? selectedProject : null;
  const ctx = projId ? FOCUS_CTX[projId] : null;
  const [subtasks, setSubtasks] = useStateFC(ctx?.subtasks || []);

  useEffectFC(() => {
    if (projId) setSubtasks(FOCUS_CTX[projId].subtasks);
  }, [projId]);

  if (!projId) {
    return <FocusProjectPicker projects={projects} onPick={(id) => setSelectedProject(id)}/>;
  }

  const project = projects.find(p => p.id === projId);

  const toggleSub = (i) => setSubtasks(s => s.map((x, j) => j === i ? { ...x, done: !x.done } : x));
  const done = subtasks.filter(s => s.done).length;
  const pct = subtasks.length ? Math.round((done / subtasks.length) * 100) : 0;

  const c = project.color;

  return (
    <div className="focus-page" style={{ "--p-c": c }}>
      {/* Top strip */}
      <div className="focus-bar">
        <button className="btn" onClick={() => setSelectedProject(null)}>
          <I.ChevronL size={12}/> Exit focus
        </button>
        <div className="focus-bar-proj">
          <div className="proj-icon" style={{ width: 28, height: 28, fontSize: 11, "--p-c": c }}>{project.code}</div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{project.name}</div>
            <div className="mono" style={{ fontSize: 10, color: "var(--text-3)" }}>{ctx.previewUrl}</div>
          </div>
        </div>
        <div className="focus-bar-task">
          <div className="mono" style={{ fontSize: 9.5, color: "var(--text-4)", letterSpacing: "0.16em", textTransform: "uppercase" }}>Current task</div>
          <div style={{ fontSize: 14, color: "var(--text-1)", fontWeight: 500, marginTop: 2 }}>{ctx.task}</div>
        </div>
        <FocusTimer color={c}/>
      </div>

      {/* Two-column layout */}
      <div className="focus-grid">
        {/* LEFT */}
        <div className="focus-left">
          {/* Task progress */}
          <div className="focus-card">
            <div className="focus-card-head">
              <div>
                <div className="focus-card-eyebrow">Subtasks</div>
                <div style={{ fontSize: 12.5, color: "var(--text-2)", marginTop: 2 }}>{done} of {subtasks.length} complete · {pct}%</div>
              </div>
              <div style={{ width: 80, height: 4, background: "rgba(255,255,255,0.06)", borderRadius: 999, overflow: "hidden" }}>
                <div style={{ width: pct + "%", height: "100%", background: c, boxShadow: `0 0 8px ${c}` }}/>
              </div>
            </div>
            <div className="focus-subs">
              {subtasks.map((s, i) => (
                <div key={i} className={"focus-sub " + (s.done ? "done" : "")} onClick={() => toggleSub(i)}>
                  <div className="focus-sub-check">{s.done && <I.CheckCircle size={11} stroke="#0a0b10"/>}</div>
                  <span>{s.t}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Done log */}
          <div className="focus-card">
            <div className="focus-card-eyebrow">Done so far</div>
            <ul className="focus-done">
              {ctx.done.map((d, i) => (
                <li key={i}>
                  <span className="mono" style={{ color: "var(--text-4)", fontSize: 10, width: 44, flex: "0 0 44px" }}>{d.t}</span>
                  <span style={{ color: "var(--text-2)", fontSize: 12 }}>{d.c}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Terminal */}
          <MiniTerm project={projId} color={c}/>
        </div>

        {/* RIGHT */}
        <BrowserPreview ctx={ctx} color={c}/>
      </div>
    </div>
  );
}

window.Focus = Focus;
