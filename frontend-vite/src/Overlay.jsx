// Alt+Space overlay -- the zero-friction entry to the local-first router.
//
// Runs in its own borderless Tauri window (label "overlay"), hidden until the
// global shortcut shows it. Posts to POST /api/v1/router/ask and renders
// whichever of the three routes came back. Escape or losing focus dismisses.
//
// Also loads in a plain browser at /overlay.html for development: the Tauri
// bits sit behind isTauri() and degrade to no-ops.
import { useCallback, useEffect, useRef, useState } from 'react';
import { postJson } from './lib/api.js';
import { isTauri } from './lib/tauri.js';

const MODES = [
  { id: 'auto', label: 'Auto', hint: 'let qwen3:4b pick the route' },
  { id: 'local', label: 'Local', hint: 'force a local answer' },
  { id: 'claude', label: 'Claude', hint: 'force escalation to headless claude' },
  { id: 'session', label: 'Session', hint: 'force a Claude Code handoff packet' },
];

async function hideOverlay() {
  if (!isTauri()) return;
  const { getCurrentWindow } = await import('@tauri-apps/api/window');
  await getCurrentWindow().hide();
}

function Result({ data }) {
  const route = data.route || 'unknown';
  const meta = [
    data.model || data.provider,
    data.confidence == null ? null : 'confidence ' + Number(data.confidence).toFixed(2),
    data.memory_used ? 'memory' : null,
  ].filter(Boolean).join(' - ');

  return (
    <div className="ov-out">
      <div className="ov-meta">
        <span className={'ov-route ov-route-' + route}>{route}</span>
        {meta ? <span className="ov-model">{meta}</span> : null}
      </div>
      {data.text ? <div className="ov-text">{data.text}</div> : null}
      {data.packet_path ? (
        <div className="ov-packet">
          <code>{data.packet_path}</code>
          <button
            className="ov-copy"
            onClick={() => navigator.clipboard && navigator.clipboard.writeText(data.packet_path)}
          >
            Copy path
          </button>
        </div>
      ) : null}
    </div>
  );
}

export default function Overlay() {
  const [question, setQuestion] = useState('');
  const [mode, setMode] = useState('auto');
  const [project, setProject] = useState(
    () => localStorage.getItem('envy.overlayProject') || '');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const inputRef = useRef(null);

  const focusInput = useCallback(() => {
    requestAnimationFrame(() => {
      if (inputRef.current) inputRef.current.focus();
    });
  }, []);

  useEffect(() => { focusInput(); }, [focusInput]);

  // The window is reused, not recreated, so each Alt+Space has to reset it --
  // otherwise the previous answer is still sitting there when it reappears.
  useEffect(() => {
    if (!isTauri()) return undefined;
    let unlisten = () => {};
    let cancelled = false;
    (async () => {
      const { listen } = await import('@tauri-apps/api/event');
      const off = await listen('overlay:opened', () => {
        setQuestion('');
        setResult(null);
        setError('');
        focusInput();
      });
      if (cancelled) off(); else unlisten = off;
    })();
    return () => { cancelled = true; unlisten(); };
  }, [focusInput]);

  useEffect(() => {
    const onKey = event => {
      if (event.key === 'Escape') {
        event.preventDefault();
        hideOverlay();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    if (project.trim()) localStorage.setItem('envy.overlayProject', project.trim());
    else localStorage.removeItem('envy.overlayProject');
  }, [project]);

  const ask = async () => {
    const message = question.trim();
    if (!message || busy) return;
    setBusy(true);
    setError('');
    setResult(null);
    try {
      const body = { message };
      if (mode !== 'auto') body.force = mode;
      if (project.trim()) body.project_id = project.trim();
      setResult(await postJson('/api/v1/router/ask', body));
    } catch (err) {
      setError(err.message || 'router unreachable');
    } finally {
      setBusy(false);
      focusInput();
    }
  };

  return (
    <div className="ov">
      <div className="ov-bar">
        <input
          ref={inputRef}
          className="ov-input"
          value={question}
          placeholder="Ask anything - Enter to send, Esc to dismiss"
          spellCheck="false"
          onChange={event => setQuestion(event.target.value)}
          onKeyDown={event => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              ask();
            }
          }}
        />
        <button className="ov-go" onClick={ask} disabled={busy || !question.trim()}>
          {busy ? 'Thinking' : 'Ask'}
        </button>
      </div>

      <div className="ov-controls">
        {MODES.map(m => (
          <button
            key={m.id}
            type="button"
            title={m.hint}
            className={'ov-mode' + (mode === m.id ? ' on' : '')}
            onClick={() => setMode(m.id)}
          >
            {m.label}
          </button>
        ))}
        <input
          className="ov-project"
          value={project}
          placeholder="project (optional)"
          spellCheck="false"
          onChange={event => setProject(event.target.value)}
        />
      </div>

      {error ? <div className="ov-out ov-error">{error}</div> : null}
      {result ? <Result data={result}/> : null}
    </div>
  );
}
