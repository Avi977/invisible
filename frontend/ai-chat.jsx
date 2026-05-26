// AI chat — floating bubble bottom-right, expands to panel.
// Uses window.claude.complete with a short system prompt about the dev's context.

const { useState: useStateAI, useRef: useRefAI, useEffect: useEffectAI } = React;

const SUGGESTIONS = [
  "What's blocking me right now?",
  "Summarize my last night's notes",
  "Draft tomorrow's todo list",
];

function AIBubble({ pageContext }) {
  const [open, setOpen] = useStateAI(false);
  const [msgs, setMsgs] = useStateAI([
    { role: "ai", text: "Hey. I've got the context for what you're working on — what do you need?" },
  ]);
  const [input, setInput] = useStateAI("");
  const [thinking, setThinking] = useStateAI(false);
  const bodyRef = useRefAI(null);

  useEffectAI(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [msgs, thinking]);

  const send = async (text) => {
    if (!text.trim() || thinking) return;
    setMsgs(m => [...m, { role: "user", text }]);
    setInput("");
    setThinking(true);
    try {
      const sys = "You are an embedded assistant inside a developer's command center. Current page: " + pageContext + ". Be terse — 2-4 short sentences max. No emoji. Speak like a senior engineer pairing with the user.";
      const reply = await window.claude.complete({
        messages: [
          { role: "user", content: sys + "\n\nUser: " + text },
        ],
      });
      setMsgs(m => [...m, { role: "ai", text: reply }]);
    } catch (e) {
      setMsgs(m => [...m, { role: "ai", text: "(couldn't reach the model — try again)" }]);
    }
    setThinking(false);
  };

  return (
    <>
      <div className={"ai-bubble " + (open ? "hidden" : "")} onClick={() => setOpen(true)}>
        <span className="pulse"/>
        <I.Sparkles size={22} stroke="#0a0b10"/>
      </div>

      {open && (
        <div className="ai-panel">
          <div className="ai-head">
            <div className="ai-orb"/>
            <div>
              <div className="ai-name">Compass</div>
              <div className="ai-sub">aware · {pageContext}</div>
            </div>
            <button className="icon-btn ai-close" onClick={() => setOpen(false)}>
              <I.X size={14}/>
            </button>
          </div>

          <div className="ai-msgs" ref={bodyRef}>
            {msgs.map((m, i) => (
              <div key={i} className={"ai-msg " + m.role}>{m.text}</div>
            ))}
            {thinking && <div className="ai-msg ai thinking">thinking…</div>}
          </div>

          {msgs.length <= 1 && (
            <div className="ai-suggest">
              {SUGGESTIONS.map((s, i) => (
                <button key={i} onClick={() => send(s)}>{s}</button>
              ))}
            </div>
          )}

          <div className="ai-input-wrap">
            <input
              className="ai-input"
              placeholder="Ask anything…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") send(input); }}
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

window.AIBubble = AIBubble;
