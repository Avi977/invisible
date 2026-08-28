import { useEffect, useRef, useState } from 'react';
import { I } from './Icons.jsx';
import { apiJson, postJson } from './lib/api.js';

function AIBubble({ pageContext, selectedProject }) {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState([
    { role: "assistant", text: "Envy is ready. Agent tools run locally with system, screen, clipboard, MCP, and sandbox access." },
  ]);
  const [input, setInput] = useState("");
  const [models, setModels] = useState([]);
  const [model, setModel] = useState("qwen3:14b");
  const [project, setProject] = useState(selectedProject || "invisible");
  const [humorLevel, setHumorLevel] = useState(1);
  const [status, setStatus] = useState("local agent - $0");
  const [toolsEnabled, setToolsEnabled] = useState(true);
  const [toolCatalog, setToolCatalog] = useState(null);
  const [sandbox, setSandbox] = useState(null);
  const [thinking, setThinking] = useState(false);
  const [handoff, setHandoff] = useState(null);
  const bodyRef = useRef(null);

  useEffect(() => {
    if (selectedProject) setProject(selectedProject);
  }, [selectedProject]);

  useEffect(() => {
    apiJson("/api/v1/ai/models")
      .then(data => {
        setModels(data.models || []);
        if (data.default) setModel(data.default);
        setStatus(data.models?.length ? "ollama online - agent tools ready - $0" : "ollama has no models");
      })
      .catch(e => setStatus(e.message || "ollama offline"));
    apiJson("/api/v1/agent/tools")
      .then(data => setToolCatalog(data))
      .catch(() => setToolCatalog(null));
  }, []);

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [msgs, thinking, handoff]);

  const history = () => msgs
    .filter(m => m.role === "user" || m.role === "assistant")
    .slice(-8)
    .map(m => ({ role: m.role, content: m.text }));

  const send = async (text) => {
    const clean = text.trim();
    if (!clean || thinking) return;
    setMsgs(m => [...m, { role: "user", text: clean }]);
    setInput("");
    setThinking(true);
    try {
      const data = await postJson(toolsEnabled ? "/api/v1/agent/chat" : "/api/v1/ai/chat", {
        message: clean,
        page_context: pageContext,
        project_id: project,
        model,
        humor_level: humorLevel,
        tools_enabled: toolsEnabled,
        max_steps: 6,
        history: history(),
      });
      setModel(data.model || model);
      setSandbox(data.sandbox || null);
      const toolCount = data.tools?.length || 0;
      setStatus(`${data.model || model} - ${toolCount} tools - ${data.usage?.duration_ms || 0}ms - $0`);
      setMsgs(m => [...m, {
        role: "assistant",
        text: data.text || "(empty response)",
        trace: data.tools || [],
      }]);
    } catch (e) {
      setMsgs(m => [...m, { role: "assistant", text: e.message || "local model unavailable" }]);
      setStatus(e.message || "error");
    } finally {
      setThinking(false);
    }
  };

  const voicePrompt = async () => {
    try {
      const data = await postJson("/api/v1/voice/transcribe", { latest: true });
      setInput(data.text);
      setStatus("OpenWhispr voice command sent - local only - $0");
      await send(data.text);
    } catch (e) {
      const transcript = window.prompt("Paste local OpenWhispr transcript");
      if (!transcript) {
        setStatus(e.message || "voice bridge unavailable");
        return;
      }
      try {
        const data = await postJson("/api/v1/voice/transcribe", { transcript });
        setInput(data.text);
        setStatus("OpenWhispr voice command sent - local only - $0");
        await send(data.text);
      } catch (manualError) {
        setStatus(manualError.message || "voice bridge unavailable");
      }
    }
  };

  const draftHandoff = async () => {
    setThinking(true);
    try {
      const data = await postJson("/api/v1/handoff/draft", {
        project,
        goal: input,
        model,
        humor_level: humorLevel,
      });
      setHandoff(data.handoff);
      setMsgs(m => [...m, { role: "assistant", text: data.handoff.markdown }]);
      setStatus(`handoff drafted - ${data.handoff.model || model} - $0`);
    } catch (e) {
      setStatus(e.message || "handoff failed");
    } finally {
      setThinking(false);
    }
  };

  const saveHandoff = async () => {
    if (!handoff) return;
    try {
      const data = await postJson("/api/v1/handoff/save", { handoff });
      setStatus(`handoff saved - ${data.path}`);
    } catch (e) {
      setStatus(e.message || "save failed");
    }
  };

  return (
    <>
      <div className={"ai-bubble " + (open ? "hidden" : "")} onClick={() => setOpen(true)}>
        <span className="pulse"/>
        <I.Sparkles size={22} stroke="#0a0b10"/>
      </div>

      {open && (
        <div className="ai-panel" style={{ width: 460, maxWidth: "calc(100vw - 32px)" }}>
          <div className="ai-head">
            <div className="ai-orb"/>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="ai-name">Envy Agent</div>
              <div className="ai-sub">{status}</div>
            </div>
            <button className="icon-btn ai-close" onClick={() => setOpen(false)}>
              <I.X size={14}/>
            </button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 96px", gap: 8, padding: "10px 12px 8px", borderBottom: "1px solid var(--border-1)" }}>
            <select className="field" value={model} onChange={e => setModel(e.target.value)} style={{ minWidth: 0 }}>
              {(models.length ? models : [{ name: model }]).map(m => <option key={m.name} value={m.name}>{m.name}</option>)}
            </select>
            <input className="field" value={project} onChange={e => setProject(e.target.value)} placeholder="project" />
            <select className="field" value={humorLevel} onChange={e => setHumorLevel(Number(e.target.value))} title="Humor level">
              <option value={0}>dry</option>
              <option value={1}>light</option>
              <option value={2}>sassy</option>
              <option value={3}>spicy</option>
            </select>
          </div>

          <div className="ai-agent-strip">
            <label className="ai-toggle">
              <input type="checkbox" checked={toolsEnabled} onChange={e => setToolsEnabled(e.target.checked)} />
              <span>Agent tools</span>
            </label>
            <span>{toolCatalog?.tools?.length || 0} tools</span>
            <span>{toolCatalog?.access?.personal_assistant_mode ? "system access on" : "sandbox only"}</span>
          </div>

          <div className="ai-msgs" ref={bodyRef} style={{ minHeight: 260 }}>
            {msgs.map((m, i) => (
              <div key={i} className={"ai-msg " + (m.role === "assistant" ? "ai" : "user")}>
                <div>{m.text}</div>
                {!!m.trace?.length && (
                  <div className="ai-trace">
                    {m.trace.map((t, idx) => (
                      <div key={idx} className="ai-trace-row">
                        <span>{t.tool}</span>
                        <code>{t.result?.ok ? "ok" : (t.result?.error || "failed")}</code>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {thinking && <div className="ai-msg ai thinking">thinking...</div>}
          </div>

          <div className="ai-suggest">
            <button onClick={() => send("Check my sandbox and tell me what you can do there.")}>Sandbox check</button>
            <button onClick={() => send("Inspect configured MCP servers and installed plugins, then summarize what tools I have.")}>MCP/plugins</button>
            <button onClick={() => send("How can I reduce tokens on this project handoff?")}>Token trim</button>
            <button onClick={draftHandoff}>Draft handoff</button>
            <button onClick={saveHandoff} disabled={!handoff}>Save handoff</button>
          </div>

          <div className="ai-input-wrap">
            <button className="icon-btn" title="Voice command" onClick={voicePrompt}><I.Zap size={15}/></button>
            <textarea
              className="ai-input"
              placeholder={toolsEnabled ? "Ask Envy to act on your system..." : "Ask local Ollama..."}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              rows={2}
              style={{ resize: "none", borderRadius: 14 }}
              autoFocus
            />
            <button className="ai-send" onClick={() => send(input)}>
              <I.Send size={14} stroke="#0a0b10"/>
            </button>
          </div>
        </div>
      )}
    </>
  );
}

export default AIBubble;
