import { useEffect, useRef, useState } from 'react';
import { I } from '../Icons.jsx';
import { apiJson, postJson, putJson } from '../lib/api.js';

const PALETTE = [
  { kind: "ai", label: "AI", items: [
    { type: "ollama", name: "Ollama qwen3:14b", code: "AI", c: "#f5b343", body: "local free" },
    { type: "ollama-small", name: "Ollama qwen3:4b", code: "AI", c: "#f5b343", body: "fast local" },
    { type: "openwhispr", name: "OpenWhispr", code: "MIC", c: "#f5b343", body: "local voice" },
    { type: "handoff", name: "Handoff draft", code: "HF", c: "#f5b343", body: "compact context" },
  ]},
  { kind: "data", label: "Data", items: [
    { type: "graphify", name: "Graphify", code: "GR", c: "#5cc8ff", body: "graph.json" },
    { type: "checkpoint", name: "Checkpoint", code: "CP", c: "#5cc8ff", body: "run state" },
    { type: "repo", name: "Repo files", code: "GH", c: "#5cc8ff", body: "local git" },
  ]},
  { kind: "logic", label: "Logic", items: [
    { type: "if", name: "Condition", code: "IF", c: "#5ee0c8", body: "branch" },
    { type: "code", name: "Run Script", code: "PS", c: "#5ee0c8", body: "local only" },
  ]},
  { kind: "output", label: "Output", items: [
    { type: "markdown", name: "Markdown note", code: "MD", c: "#b794ff", body: "handoff file" },
    { type: "terminal", name: "Terminal", code: "TTY", c: "#b794ff", body: "command" },
  ]},
];

const NODE_W = 180;

function ToolsCanvas({ nodes, edges, onChange }) {
  const [drag, setDrag] = useState(null);
  const [connecting, setConnecting] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [selected, setSelected] = useState(null);
  const canvasRef = useRef(null);

  const setNodes = (updater) => {
    const next = typeof updater === "function" ? updater(nodes) : updater;
    onChange(next, edges);
  };
  const setEdges = (updater) => {
    const next = typeof updater === "function" ? updater(edges) : updater;
    onChange(nodes, next);
  };

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
    return () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
  }, [drag, nodes, edges]);

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
    const newId = "n" + Math.random().toString(36).slice(2, 8);
    setNodes(ns => [...ns, { ...t, id: newId, x: e.clientX - rect.left, y: e.clientY - rect.top }]);
  };

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
      onDragOver={(e) => e.preventDefault()}
      onClick={(e) => { if (e.target === canvasRef.current) setSelected(null); }}
    >
      <svg className="tools-svg">
        <defs>
          <linearGradient id="wire" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="rgba(245, 111, 177, 0.85)"/>
            <stop offset="100%" stopColor="rgba(94, 224, 200, 0.85)"/>
          </linearGradient>
        </defs>
        {edges.map((ed, i) => {
          const a = nodeMap[ed.from], b = nodeMap[ed.to];
          if (!a || !b) return null;
          const x1 = a.x + NODE_W / 2, y1 = a.y;
          const x2 = b.x - NODE_W / 2, y2 = b.y;
          return <path key={i} d={edgePath(x1, y1, x2, y2)} stroke="url(#wire)" strokeWidth="1.8" fill="none"/>;
        })}
        {connecting && nodeMap[connecting.from] && (() => {
          const a = nodeMap[connecting.from];
          return <path d={edgePath(a.x + NODE_W / 2, a.y, mousePos.x, mousePos.y)} stroke="rgba(255,255,255,0.5)" strokeWidth="1.5" strokeDasharray="4 4" fill="none"/>;
        })()}
      </svg>

      {nodes.map(n => (
        <div
          key={n.id}
          className={"tool-node " + (drag?.id === n.id ? "dragging" : "")}
          style={{
            left: n.x,
            top: n.y,
            width: NODE_W,
            "--n-c": n.c,
            outline: selected === n.id ? "1px solid var(--n-c)" : "none",
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
        <button className="btn" style={{ padding: "5px 10px", fontSize: 11 }} onClick={removeSelected} disabled={!selected}>Delete</button>
        <span className="chip mono" style={{ fontSize: 10 }}>{nodes.length} nodes · {edges.length} wires</span>
      </div>
    </div>
  );
}

function ProjectPicker({ projects, workflows, onPick }) {
  return (
    <div className="proj-picker">
      <div className="proj-picker-head">
        <div className="mono" style={{ fontSize: 10.5, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--text-3)" }}>Choose a project</div>
        <h2 style={{ margin: "6px 0 0", fontWeight: 600, fontSize: "calc(22px * var(--d))" }}>Which workflow are you working on?</h2>
        <p className="muted" style={{ fontSize: 12.5, maxWidth: 520, lineHeight: 1.55, marginTop: 8 }}>
          Tool connections are scoped to a project and saved locally under Envy.
        </p>
      </div>
      <div className="proj-picker-grid">
        {projects.map(p => {
          const wf = workflows[p.id] || { nodes: [], edges: [] };
          return (
            <button key={p.id} className="proj-picker-card" style={{ "--p-c": p.color }} onClick={() => onPick(p.id)}>
              <div className="proj-icon" style={{ width: 32, height: 32 }}>{p.code}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{p.name}</div>
                <div className="mono" style={{ fontSize: 10.5, color: "var(--text-3)", marginTop: 2 }}>
                  {wf.nodes.length ? `${wf.nodes.length} nodes · ${wf.edges.length} wires` : "no workflow yet"}
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

function IntegrationsPanel() {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("loading");
  const [secret, setSecret] = useState({ key: "", value: "" });
  const [connection, setConnection] = useState({ name: "", kind: "api", base_url: "", auth: "api_key", secret_keys: "", notes: "" });
  const [mcp, setMcp] = useState({ name: "", command: "npx", args: "", env_keys: "" });

  const load = async () => {
    setStatus("loading");
    try {
      const next = await apiJson("/api/v1/integrations");
      setData(next);
      setStatus("ready");
    } catch (e) {
      setStatus(e.message || "offline");
    }
  };

  useEffect(() => { load(); }, []);

  const splitList = (value) => String(value || "")
    .split(/[\n,]/)
    .map(v => v.trim())
    .filter(Boolean);

  const saveSecret = async () => {
    setStatus("saving secret");
    try {
      await postJson("/api/v1/integrations/secret", secret);
      setSecret({ key: "", value: "" });
      await load();
      setStatus("secret saved to Infisical");
    } catch (e) {
      setStatus(e.message || "secret save failed");
    }
  };

  const saveConnection = async () => {
    setStatus("saving connection");
    try {
      await postJson("/api/v1/integrations/connection", {
        ...connection,
        secret_keys: splitList(connection.secret_keys),
      });
      setConnection({ name: "", kind: "api", base_url: "", auth: "api_key", secret_keys: "", notes: "" });
      await load();
      setStatus("connection saved");
    } catch (e) {
      setStatus(e.message || "connection save failed");
    }
  };

  const saveMcp = async () => {
    setStatus("saving mcp");
    try {
      await postJson("/api/v1/integrations/mcp", {
        ...mcp,
        args: splitList(mcp.args),
        env_keys: splitList(mcp.env_keys),
      });
      setMcp({ name: "", command: "npx", args: "", env_keys: "" });
      await load();
      setStatus("mcp server added");
    } catch (e) {
      setStatus(e.message || "mcp save failed");
    }
  };

  const vault = data?.infisical || {};
  const servers = data?.mcp?.servers || [];
  const connections = data?.connections || [];

  return (
    <div className="integrations-grid">
      <section className="integration-panel">
        <div className="integration-head">
          <div>
            <h3>Infisical Vault</h3>
            <p>{vault.host || "vault"} · {vault.environment || "env"}{vault.secret_path || "/"}</p>
          </div>
          <span className={"chip " + (vault.reachable ? "accent" : "")}>
            <span className="chip-dot"/>{vault.reachable ? "connected" : "not connected"}
          </span>
        </div>
        <div className="integration-kpis">
          <span>{vault.secret_count || 0} keys</span>
          <span>{vault.client_id_set ? "client id set" : "client id missing"}</span>
          <span>{vault.project_id_set ? "project set" : "project missing"}</span>
        </div>
        <div className="integration-form">
          <input className="field" placeholder="SECRET_KEY" value={secret.key} onChange={e => setSecret(s => ({ ...s, key: e.target.value.toUpperCase() }))}/>
          <input className="field" placeholder="secret value" type="password" value={secret.value} onChange={e => setSecret(s => ({ ...s, value: e.target.value }))}/>
          <button className="btn accent" onClick={saveSecret} disabled={!secret.key || !secret.value}>Store Key</button>
        </div>
        <div className="integration-list">
          {(vault.keys || []).slice(0, 12).map(k => (
            <div className="integration-row" key={k.key}>
              <span>{k.key}</span>
              <code>{k.preview || `${k.length} chars`}</code>
            </div>
          ))}
          {!(vault.keys || []).length && <div className="muted">No vault keys visible yet.</div>}
        </div>
      </section>

      <section className="integration-panel">
        <div className="integration-head">
          <div>
            <h3>MCP Servers</h3>
            <p>{data?.mcp?.config || "Codex config"}</p>
          </div>
          <span className="chip"><span className="chip-dot"/>{servers.length} servers</span>
        </div>
        <div className="integration-form stacked">
          <input className="field" placeholder="server-name" value={mcp.name} onChange={e => setMcp(s => ({ ...s, name: e.target.value }))}/>
          <input className="field" placeholder="command" value={mcp.command} onChange={e => setMcp(s => ({ ...s, command: e.target.value }))}/>
          <textarea className="field" rows={2} placeholder="args, comma or newline separated" value={mcp.args} onChange={e => setMcp(s => ({ ...s, args: e.target.value }))}/>
          <input className="field" placeholder="ENV_KEYS used by this server" value={mcp.env_keys} onChange={e => setMcp(s => ({ ...s, env_keys: e.target.value.toUpperCase() }))}/>
          <button className="btn accent" onClick={saveMcp} disabled={!mcp.name || !mcp.command}>Add MCP</button>
        </div>
        <div className="integration-list">
          {servers.map(s => (
            <div className="integration-row" key={s.name}>
              <span>{s.name}</span>
              <code>{s.command} {(s.args || []).join(" ")}</code>
            </div>
          ))}
          {!servers.length && <div className="muted">No MCP servers configured.</div>}
        </div>
      </section>

      <section className="integration-panel wide">
        <div className="integration-head">
          <div>
            <h3>Third-Party Apps & APIs</h3>
            <p>Connection metadata stays local; credentials live as Infisical env keys.</p>
          </div>
          <span className="chip"><span className="chip-dot"/>{connections.length} connections</span>
        </div>
        <div className="integration-form app-form">
          <input className="field" placeholder="github" value={connection.name} onChange={e => setConnection(s => ({ ...s, name: e.target.value }))}/>
          <input className="field" placeholder="kind" value={connection.kind} onChange={e => setConnection(s => ({ ...s, kind: e.target.value }))}/>
          <input className="field" placeholder="https://api.example.com" value={connection.base_url} onChange={e => setConnection(s => ({ ...s, base_url: e.target.value }))}/>
          <input className="field" placeholder="GITHUB_TOKEN, API_KEY" value={connection.secret_keys} onChange={e => setConnection(s => ({ ...s, secret_keys: e.target.value.toUpperCase() }))}/>
          <textarea className="field" rows={2} placeholder="notes" value={connection.notes} onChange={e => setConnection(s => ({ ...s, notes: e.target.value }))}/>
          <button className="btn accent" onClick={saveConnection} disabled={!connection.name}>Save Connection</button>
        </div>
        <div className="connection-table">
          {connections.map(c => (
            <div className="connection-row" key={c.name}>
              <div>
                <strong>{c.name}</strong>
                <span>{c.kind} · {c.base_url || "no base url"}</span>
              </div>
              <code>{(c.secret_keys || []).join(", ") || "no keys"}</code>
            </div>
          ))}
          {!connections.length && <div className="muted">Add GitHub, Notion, Slack, Google, Supabase, or any API you want Envy to use.</div>}
        </div>
      </section>

      <div className="integration-status">{status}</div>
    </div>
  );
}

function ToolCatalogPanel() {
  const [query, setQuery] = useState("project git mcp");
  const [tools, setTools] = useState([]);
  const [status, setStatus] = useState("idle");
  const search = async () => {
    setStatus("searching");
    try {
      const data = await postJson("/api/v1/tools/search", { query, limit: 24 });
      setTools(data.tools || []);
      setStatus(`${(data.tools || []).length} tools`);
    } catch (e) {
      setStatus(e.message || "search failed");
    }
  };
  useEffect(() => { search(); }, []);
  return (
    <div className="integrations-grid">
      <section className="integration-panel wide">
        <div className="integration-head"><div><h3>Tool Catalog</h3><p>Search summaries first; schemas stay hidden until needed.</p></div><span className="chip"><span className="chip-dot"/>{status}</span></div>
        <div className="integration-form app-form">
          <input className="field" value={query} onChange={e => setQuery(e.target.value)} placeholder="search tools"/>
          <button className="btn accent" onClick={search}>Search</button>
        </div>
        <div className="connection-table">
          {tools.map(t => <div className="connection-row" key={t.id}><div><strong>{t.name}</strong><span>{t.category} · {t.description}</span></div><code>{t.risk_level}{t.requires_approval ? " · approval" : ""}</code></div>)}
        </div>
      </section>
    </div>
  );
}

function RunsPanel({ projectId }) {
  const [goal, setGoal] = useState("");
  const [run, setRun] = useState(null);
  const [target, setTarget] = useState("codex");
  const [status, setStatus] = useState("idle");
  const start = async () => {
    setStatus("starting");
    try {
      const data = await postJson("/api/v1/runs", { goal, project_id: projectId, owner: "envy" });
      setRun(data.run);
      setStatus("queued");
    } catch (e) {
      setStatus(e.message || "run failed");
    }
  };
  const handoff = async () => {
    if (!run) return;
    setStatus("handing off");
    try {
      const data = await postJson(`/api/v1/runs/${run.id}/handoff`, { target });
      setRun(data.run);
      setStatus(`owner ${data.run.owner}`);
    } catch (e) {
      setStatus(e.message || "handoff failed");
    }
  };
  return (
    <div className="integrations-grid">
      <section className="integration-panel wide">
        <div className="integration-head"><div><h3>Runs</h3><p>Track long-running tasks before moving them to Codex, Claude, Hermes, or VPS.</p></div><span className="chip"><span className="chip-dot"/>{status}</span></div>
        <div className="integration-form app-form">
          <input className="field" value={goal} onChange={e => setGoal(e.target.value)} placeholder="run goal"/>
          <button className="btn accent" onClick={start} disabled={!goal}>Start Run</button>
          <select className="field" value={target} onChange={e => setTarget(e.target.value)}>
            <option value="codex">Codex</option><option value="claude_code">Claude Code</option><option value="hermes">Hermes</option><option value="vps_worker">VPS Worker</option><option value="human">Human</option>
          </select>
          <button className="btn" onClick={handoff} disabled={!run}>Hand Off</button>
        </div>
        {run && <div className="connection-row"><div><strong>{run.goal}</strong><span>{run.id}</span></div><code>{run.owner} · {run.status}</code></div>}
      </section>
    </div>
  );
}

function MemoryPanel({ projectId }) {
  const [query, setQuery] = useState("");
  const [content, setContent] = useState("");
  const [category, setCategory] = useState("project_fact");
  const [results, setResults] = useState([]);
  const [status, setStatus] = useState("idle");
  const search = async () => {
    setStatus("searching");
    try {
      const data = await apiJson(`/api/v1/memory/search?q=${encodeURIComponent(query)}&project_id=${encodeURIComponent(projectId)}`);
      setResults(data.results || []);
      setStatus(`${(data.results || []).length} memories`);
    } catch (e) {
      setStatus(e.message || "memory search failed");
    }
  };
  const write = async () => {
    setStatus("saving memory");
    try {
      await postJson("/api/v1/memory/write", { category, content, project_id: projectId });
      setContent("");
      await search();
    } catch (e) {
      setStatus(e.message || "memory write failed");
    }
  };
  return (
    <div className="integrations-grid">
      <section className="integration-panel wide">
        <div className="integration-head"><div><h3>Memory</h3><p>Curated Envy/Hermes memories. Secrets are rejected.</p></div><span className="chip"><span className="chip-dot"/>{status}</span></div>
        <div className="integration-form app-form">
          <select className="field" value={category} onChange={e => setCategory(e.target.value)}>
            <option value="user_preference">User preference</option><option value="project_fact">Project fact</option><option value="workflow_pattern">Workflow pattern</option><option value="credential_location">Credential location</option><option value="environment_fact">Environment fact</option><option value="recurring_task">Recurring task</option>
          </select>
          <input className="field" value={content} onChange={e => setContent(e.target.value)} placeholder="memory content"/>
          <button className="btn accent" onClick={write} disabled={!content}>Write</button>
          <input className="field" value={query} onChange={e => setQuery(e.target.value)} placeholder="search memory"/>
          <button className="btn" onClick={search}>Search</button>
        </div>
        <div className="connection-table">{results.map(m => <div className="connection-row" key={m.id}><div><strong>{m.category}</strong><span>{m.content}</span></div><code>{m.status}</code></div>)}</div>
      </section>
    </div>
  );
}

function HandoffsPanel({ projectId }) {
  const [goal, setGoal] = useState("");
  const [target, setTarget] = useState("codex");
  const [handoff, setHandoff] = useState(null);
  const [status, setStatus] = useState("idle");
  const draft = async () => {
    setStatus("drafting");
    try {
      const data = await postJson("/api/v1/handoff/draft", { project: projectId, goal, handoff_target: target });
      setHandoff(data.handoff);
      setStatus("drafted");
    } catch (e) {
      setStatus(e.message || "draft failed");
    }
  };
  const save = async () => {
    if (!handoff) return;
    setStatus("saving");
    try {
      await postJson("/api/v1/handoff/save", { handoff });
      setStatus("saved");
    } catch (e) {
      setStatus(e.message || "save failed");
    }
  };
  return (
    <div className="integrations-grid">
      <section className="integration-panel wide">
        <div className="integration-head"><div><h3>Handoffs</h3><p>Draft compact resume packets with repo, memory, and tool trace context.</p></div><span className="chip"><span className="chip-dot"/>{status}</span></div>
        <div className="integration-form app-form">
          <input className="field" value={goal} onChange={e => setGoal(e.target.value)} placeholder="handoff goal"/>
          <select className="field" value={target} onChange={e => setTarget(e.target.value)}>
            <option value="codex">Codex</option><option value="claude_code">Claude Code</option><option value="hermes">Hermes</option><option value="vps_worker">VPS Worker</option><option value="human">Human</option>
          </select>
          <button className="btn accent" onClick={draft} disabled={!goal}>Draft</button>
          <button className="btn" onClick={save} disabled={!handoff}>Save</button>
        </div>
        {handoff && <pre className="field" style={{ whiteSpace: "pre-wrap", maxHeight: 360, overflow: "auto" }}>{handoff.markdown}</pre>}
      </section>
    </div>
  );
}

function Tools({ projects, selectedProject, setSelectedProject }) {
  const [workflows, setWorkflows] = useState({});
  const [status, setStatus] = useState("idle");
  const [tab, setTab] = useState("workflow");
  const saveTimer = useRef(null);
  const projId = selectedProject && projects.some(p => p.id === selectedProject) ? selectedProject : null;

  const loadWorkflow = async (projectId) => {
    setStatus("loading");
    try {
      const data = await apiJson(`/api/v1/tools?project=${encodeURIComponent(projectId)}`);
      setWorkflows(w => ({ ...w, [projectId]: { nodes: data.nodes || [], edges: data.edges || [], updated_at: data.updated_at } }));
      setStatus("ready");
    } catch (e) {
      setWorkflows(w => ({ ...w, [projectId]: { nodes: [], edges: [] } }));
      setStatus(e.message || "offline");
    }
  };

  useEffect(() => {
    if (projId && !workflows[projId]) loadWorkflow(projId);
  }, [projId]);

  const saveWorkflow = (projectId, nodes, edges) => {
    window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(async () => {
      setStatus("saving");
      try {
        const data = await putJson(`/api/v1/tools?project=${encodeURIComponent(projectId)}`, { nodes, edges });
        setWorkflows(w => ({ ...w, [projectId]: { nodes, edges, updated_at: data.updated_at } }));
        setStatus("saved");
      } catch (e) {
        setStatus(e.message || "save failed");
      }
    }, 450);
  };

  if (!projId) {
    return <ProjectPicker projects={projects} workflows={workflows} onPick={setSelectedProject}/>;
  }

  const project = projects.find(p => p.id === projId);
  const wf = workflows[projId] || { nodes: [], edges: [] };

  const onChange = (nodes, edges) => {
    setWorkflows(w => ({ ...w, [projId]: { ...wf, nodes, edges } }));
    saveWorkflow(projId, nodes, edges);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--pad-3)", height: "100%" }}>
      <div className="proj-tabs">
        <button className="proj-tab" onClick={() => setSelectedProject(null)} title="Back to project picker" style={{ flex: "0 0 auto" }}>
          <I.ChevronL size={14}/>
        </button>
        {projects.map(p => (
          <button key={p.id} className={"proj-tab " + (p.id === projId ? "active" : "")} onClick={() => setSelectedProject(p.id)} style={{ "--p-c": p.color }}>
            <span className="proj-tab-dot" style={{ background: p.color }}/>
            {p.name}
          </button>
        ))}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          <button className={"proj-tab " + (tab === "workflow" ? "active" : "")} onClick={() => setTab("workflow")}>Workflow</button>
          <button className={"proj-tab " + (tab === "connections" ? "active" : "")} onClick={() => setTab("connections")}>Connections</button>
          <button className={"proj-tab " + (tab === "catalog" ? "active" : "")} onClick={() => setTab("catalog")}>Tool Catalog</button>
          <button className={"proj-tab " + (tab === "runs" ? "active" : "")} onClick={() => setTab("runs")}>Runs</button>
          <button className={"proj-tab " + (tab === "memory" ? "active" : "")} onClick={() => setTab("memory")}>Memory</button>
          <button className={"proj-tab " + (tab === "handoffs" ? "active" : "")} onClick={() => setTab("handoffs")}>Handoffs</button>
          <span className="chip mono" style={{ fontSize: 10 }}>{project.name} · {status}</span>
        </div>
      </div>

      {tab === "connections" ? <IntegrationsPanel/> : tab === "catalog" ? <ToolCatalogPanel/> : tab === "runs" ? <RunsPanel projectId={projId}/> : tab === "memory" ? <MemoryPanel projectId={projId}/> : tab === "handoffs" ? <HandoffsPanel projectId={projId}/> : <div className="tools-layout" style={{ flex: 1, minHeight: 0 }}>
        <div className="tools-palette">
          <div className="muted mono" style={{ fontSize: 10.5, padding: "4px 0 var(--pad-2)" }}>Drag onto canvas</div>
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
        <ToolsCanvas nodes={wf.nodes || []} edges={wf.edges || []} onChange={onChange}/>
      </div>}
    </div>
  );
}

export default Tools;
