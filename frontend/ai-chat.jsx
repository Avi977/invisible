// AI chat — floating bubble bottom-right, expands to panel.
// Posts user messages to POST /api/v1/chat (lib/api/chat.py via invisible-dashboard)
// and renders the assistant reply inline. Maps documented backend failure modes
// (400 / 401 / 413 / 429 / 5xx / 504 / network-down) to distinct UI strings.

const { useState: useStateAI, useRef: useRefAI, useEffect: useEffectAI } = React;

// Frontend is served on :8090 (invisible-frontend); backend dashboard is on :8765.
// Absolute URL is required — these are different origins.
const CHAT_ENDPOINT = "http://127.0.0.1:8765/api/v1/chat";

// Mirrors lib/api/chat.py MAX_MESSAGE_CHARS — client-side defense in depth so
// the user gets immediate feedback instead of waiting for the HTTP 413 round-trip.
const MAX_MESSAGE_CHARS = 8000;

const SUGGESTIONS = [
  "What's blocking me right now?",
  "Summarize my last night's notes",
  "Draft tomorrow's todo list",
];

function errorMessageFor(status, body) {
  const hint = (body && typeof body.hint === "string") ? body.hint : "";
  switch (status) {
    case 400:
      return "Couldn't send (bad request): " + (hint || "check input");
    case 401:
      return "Claude CLI not signed in. " + (hint || "run: claude login");
    case 413:
      return "Message too long (max " + MAX_MESSAGE_CHARS + " characters).";
    case 429:
      return "Claude rate-limited. " + (hint || "wait a moment and try again");
    case 504:
      return "Claude took too long (>60s). Try a shorter question.";
    default:
      if (status >= 500) {
        return "Claude CLI failed. " + (hint || ("HTTP " + status));
      }
      return "Unexpected error (HTTP " + status + ").";
  }
}

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

    // Client-side size cap — short-circuits before fetch, mirrors backend HTTP 413.
    if (text.length > MAX_MESSAGE_CHARS) {
      setMsgs(m => [
        ...m,
        { role: "user", text },
        { role: "ai", text: "Message too long (max " + MAX_MESSAGE_CHARS + " characters).", error: true },
      ]);
      setInput("");
      return;
    }

    setMsgs(m => [...m, { role: "user", text }]);
    setInput("");
    setThinking(true);
    try {
      const res = await fetch(CHAT_ENDPOINT, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ message: text, page_context: pageContext }),
      });
      let body = null;
      try { body = await res.json(); } catch (_) { /* leave body null */ }
      if (res.ok && body && typeof body.text === "string") {
        setMsgs(m => [...m, { role: "ai", text: body.text }]);
      } else {
        setMsgs(m => [...m, { role: "ai", text: errorMessageFor(res.status, body), error: true }]);
      }
    } catch (e) {
      // Fetch rejection — backend daemon not running, DNS fail, CORS preflight blocked, etc.
      setMsgs(m => [...m, { role: "ai", text: "Backend unreachable — is invisible-dashboard running on 127.0.0.1:8765?", error: true }]);
    } finally {
      setThinking(false);
    }
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
