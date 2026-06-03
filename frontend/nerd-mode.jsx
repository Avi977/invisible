// nerd-mode.jsx — IDE overlay for the "invisible" dev cockpit.
// Loads the real source files via the bootstrap VFS, lets you edit them,
// hot-applies CSS changes, persists JSX edits to localStorage, and reloads.

const {
  useState: useStateNM,
  useEffect: useEffectNM,
  useRef: useRefNM,
  useMemo: useMemoNM,
  useCallback: useCallbackNM,
} = React;

/* ───────────────────────── File manifest ─────────────────────────
   Mirrors the bootstrap order. `branch` is just decoration.
   The `index.html` file is read-only — editing it would brick the boot. */
const NM_FILES = [
  { path: "index.html",          type: "html", lang: "html", readonly: true },
  { path: "styles.css",          type: "css",  lang: "css" },
  { path: "app.jsx",             type: "jsx",  lang: "jsx" },
  { path: "data.jsx",            type: "jsx",  lang: "jsx" },
  { path: "icons.jsx",           type: "jsx",  lang: "jsx" },
  { path: "ai-chat.jsx",         type: "jsx",  lang: "jsx" },
  { path: "tweaks-panel.jsx",    type: "jsx",  lang: "jsx" },
  { path: "nerd-mode.jsx",       type: "jsx",  lang: "jsx" },
  { path: "galaxy-data.jsx",     type: "jsx",  lang: "jsx" },
  { path: "pages/dashboard.jsx", type: "jsx",  lang: "jsx" },
  { path: "pages/focus.jsx",     type: "jsx",  lang: "jsx" },
  { path: "pages/folders.jsx",   type: "jsx",  lang: "jsx" },
  { path: "pages/relations.jsx", type: "jsx",  lang: "jsx" },
  { path: "pages/terminals.jsx", type: "jsx",  lang: "jsx" },
  { path: "pages/tools.jsx",     type: "jsx",  lang: "jsx" },
  { path: "pages/calendar.jsx",  type: "jsx",  lang: "jsx" },
  { path: "pages/analytics.jsx", type: "jsx",  lang: "jsx" },
];

/* ───────────────────────── tiny syntax highlighter ─────────────────────────
   Not Prism. Just enough to read code by. */
const escHtml = (s) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const JS_KW = new Set("const let var function return if else for while do switch case break continue new class extends import export from default try catch finally throw typeof instanceof of in delete void async await yield".split(" "));
const JS_BUILTIN = new Set("true false null undefined this super React window document console Math Array Object String Number Boolean Promise Set Map".split(" "));

function highlightJSX(code) {
  // single-pass tokenizer; everything not matched is plain text (escaped).
  const re = /(\/\*[\s\S]*?\*\/)|(\/\/[^\n]*)|(`(?:\\.|\$\{[^}]*\}|[^`\\])*`)|('(?:\\.|[^'\\])*')|("(?:\\.|[^"\\])*")|(\b\d+(?:\.\d+)?\b)|(<\/?[A-Za-z][\w.-]*)|(\b[A-Za-z_$][\w$]*\b)/g;
  let out = "";
  let last = 0;
  let m;
  while ((m = re.exec(code))) {
    out += escHtml(code.slice(last, m.index));
    if (m[1] || m[2]) out += `<span class="tk-c">${escHtml(m[1] || m[2])}</span>`;
    else if (m[3] || m[4] || m[5]) out += `<span class="tk-s">${escHtml(m[3] || m[4] || m[5])}</span>`;
    else if (m[6]) out += `<span class="tk-n">${m[6]}</span>`;
    else if (m[7]) out += `<span class="tk-tag">${escHtml(m[7])}</span>`;
    else if (m[8]) {
      const w = m[8];
      if (JS_KW.has(w)) out += `<span class="tk-k">${w}</span>`;
      else if (JS_BUILTIN.has(w)) out += `<span class="tk-b">${w}</span>`;
      else if (/^[A-Z]/.test(w)) out += `<span class="tk-cls">${w}</span>`;
      else out += w;
    }
    last = re.lastIndex;
  }
  out += escHtml(code.slice(last));
  return out;
}

function highlightCSS(code) {
  // comments, strings, selectors (before {), props (before :), values, numbers, vars
  const re = /(\/\*[\s\S]*?\*\/)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(--[\w-]+)|(#[0-9a-fA-F]{3,8})\b|(\b\d+(?:\.\d+)?(?:px|em|rem|%|vh|vw|vmin|vmax|s|ms|deg|fr)?\b)|(@[\w-]+)|(\.[\w-]+|#[\w-]+|&|::?[\w-]+)|(\b[a-z-]+(?=\s*:))/g;
  let out = "";
  let last = 0;
  let m;
  while ((m = re.exec(code))) {
    out += escHtml(code.slice(last, m.index));
    if (m[1])      out += `<span class="tk-c">${escHtml(m[1])}</span>`;
    else if (m[2]) out += `<span class="tk-s">${escHtml(m[2])}</span>`;
    else if (m[3]) out += `<span class="tk-var">${m[3]}</span>`;
    else if (m[4]) out += `<span class="tk-hex">${m[4]}</span>`;
    else if (m[5]) out += `<span class="tk-n">${m[5]}</span>`;
    else if (m[6]) out += `<span class="tk-k">${m[6]}</span>`;
    else if (m[7]) out += `<span class="tk-sel">${escHtml(m[7])}</span>`;
    else if (m[8]) out += `<span class="tk-prop">${m[8]}</span>`;
    last = re.lastIndex;
  }
  out += escHtml(code.slice(last));
  return out;
}

function highlightHTML(code) {
  // tag + attr + string + comment + doctype
  const re = /(&lt;!--[\s\S]*?--&gt;)|(&lt;!DOCTYPE[^&]*?&gt;)|(&lt;\/?)([\w-]+)|(\s)([\w:-]+)(=)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|(&gt;|\/&gt;)/g;
  let escaped = escHtml(code);
  return escaped.replace(re, (_, c, dt, lt, tn, sp, an, eq, str, gt) => {
    if (c)  return `<span class="tk-c">${c}</span>`;
    if (dt) return `<span class="tk-k">${dt}</span>`;
    if (lt) return `<span class="tk-tag">${lt}${tn}</span>`;
    if (an) return `${sp}<span class="tk-prop">${an}</span><span class="tk-tag">${eq}</span>`;
    if (str) return `<span class="tk-s">${str}</span>`;
    if (gt) return `<span class="tk-tag">${gt}</span>`;
    return _;
  });
}

const HIGHLIGHTERS = { jsx: highlightJSX, js: highlightJSX, css: highlightCSS, html: highlightHTML };
function highlight(code, lang) {
  const fn = HIGHLIGHTERS[lang];
  return fn ? fn(code) : escHtml(code);
}

/* ───────────────────────── tree helpers ───────────────────────── */
function buildTree(files) {
  // { name, path, children?, file? }
  const root = { name: "invisible", path: "", children: [] };
  for (const f of files) {
    const parts = f.path.split("/");
    let node = root;
    for (let i = 0; i < parts.length - 1; i++) {
      let dir = node.children.find((c) => c.name === parts[i] && c.children);
      if (!dir) {
        dir = { name: parts[i], path: parts.slice(0, i + 1).join("/"), children: [] };
        node.children.push(dir);
      }
      node = dir;
    }
    node.children.push({ name: parts[parts.length - 1], path: f.path, file: f });
  }
  // sort: folders first, then files alpha
  const sort = (n) => {
    if (!n.children) return;
    n.children.sort((a, b) => {
      const ad = !!a.children, bd = !!b.children;
      if (ad !== bd) return ad ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    n.children.forEach(sort);
  };
  sort(root);
  return root;
}

const fileIconFor = (path) => {
  if (path.endsWith(".jsx") || path.endsWith(".js")) return { glyph: "JS", color: "var(--c-dash)" };
  if (path.endsWith(".css")) return { glyph: "#",  color: "var(--c-fold)" };
  if (path.endsWith(".html")) return { glyph: "<>", color: "var(--c-term)" };
  return { glyph: "·", color: "var(--text-3)" };
};

/* ───────────────────────── code editor ───────────────────────── */
function NMEditor({ value, lang, onChange, readonly }) {
  const taRef = useRefNM(null);
  const preRef = useRefNM(null);
  const gutRef = useRefNM(null);
  const [pos, setPos] = useStateNM({ line: 1, col: 1 });

  const lineCount = useMemoNM(() => (value.match(/\n/g) || []).length + 1, [value]);
  const html = useMemoNM(() => highlight(value, lang) + "\n", [value, lang]);

  const syncScroll = () => {
    const ta = taRef.current;
    if (!ta) return;
    if (preRef.current) {
      preRef.current.scrollTop = ta.scrollTop;
      preRef.current.scrollLeft = ta.scrollLeft;
    }
    if (gutRef.current) gutRef.current.scrollTop = ta.scrollTop;
  };

  const updateCursor = () => {
    const ta = taRef.current;
    if (!ta) return;
    const before = ta.value.substring(0, ta.selectionStart);
    const line = (before.match(/\n/g) || []).length + 1;
    const col = before.length - before.lastIndexOf("\n");
    setPos({ line, col });
  };

  const onKeyDown = (e) => {
    if (readonly) return;
    if (e.key === "Tab") {
      e.preventDefault();
      const ta = e.target;
      const start = ta.selectionStart, end = ta.selectionEnd;
      const next = value.slice(0, start) + "  " + value.slice(end);
      onChange(next);
      requestAnimationFrame(() => {
        ta.selectionStart = ta.selectionEnd = start + 2;
        updateCursor();
      });
    }
  };

  return (
    <div className="nm-editor">
      <div className="nm-gutter" ref={gutRef}>
        {Array.from({ length: lineCount }, (_, i) => (
          <div key={i} className={"nm-ln " + (i + 1 === pos.line ? "active" : "")}>
            {i + 1}
          </div>
        ))}
      </div>
      <div className="nm-codewrap">
        <pre className="nm-highlight" ref={preRef} aria-hidden="true">
          <code dangerouslySetInnerHTML={{ __html: html }} />
        </pre>
        <textarea
          ref={taRef}
          className="nm-textarea"
          value={value}
          readOnly={readonly}
          onChange={(e) => onChange(e.target.value)}
          onScroll={syncScroll}
          onKeyDown={onKeyDown}
          onKeyUp={updateCursor}
          onClick={updateCursor}
          onSelect={updateCursor}
          spellCheck={false}
          wrap="off"
        />
      </div>
      <div className="nm-statusinfo">
        <span>Ln {pos.line}, Col {pos.col}</span>
        <span>{lineCount} lines</span>
      </div>
    </div>
  );
}

/* ───────────────────────── tree node ───────────────────────── */
function NMTreeNode({ node, depth, openSet, toggleDir, openFile, activePath }) {
  if (node.file) {
    const ico = fileIconFor(node.path);
    const active = activePath === node.path;
    return (
      <div
        className={"nm-tree-row file " + (active ? "active" : "")}
        style={{ paddingLeft: 8 + depth * 14 }}
        onClick={() => openFile(node.file)}
      >
        <span className="nm-tree-ico" style={{ color: ico.color }}>{ico.glyph}</span>
        <span className="nm-tree-name">{node.name}</span>
        {node.file.readonly && <span className="nm-tree-ro">RO</span>}
      </div>
    );
  }
  const open = depth === 0 ? true : openSet.has(node.path);
  return (
    <>
      {depth > 0 && (
        <div
          className="nm-tree-row dir"
          style={{ paddingLeft: 8 + (depth - 1) * 14 }}
          onClick={() => toggleDir(node.path)}
        >
          <span className={"nm-tree-caret " + (open ? "open" : "")}>▸</span>
          <span className="nm-tree-name">{node.name}</span>
        </div>
      )}
      {open &&
        node.children.map((c) => (
          <NMTreeNode
            key={c.path || c.name}
            node={c}
            depth={depth + 1}
            openSet={openSet}
            toggleDir={toggleDir}
            openFile={openFile}
            activePath={activePath}
          />
        ))}
    </>
  );
}

/* ───────────────────────── main IDE shell ───────────────────────── */
function NerdMode({ open, onClose }) {
  // The bootstrap exposes window.__VFS = { originals, current }.
  // current[path] is whatever's running RIGHT NOW (overrides applied at boot).
  const vfsReady = !!(typeof window !== "undefined" && window.__VFS);

  const [openTabs, setOpenTabs]   = useStateNM([]);            // [path]
  const [activeTab, setActiveTab] = useStateNM(null);          // path
  const [buffers, setBuffers]     = useStateNM({});            // path -> draft text
  const [savedTick, setSavedTick] = useStateNM(0);             // bumps after save/reset
  const [toast, setToast]         = useStateNM(null);
  const [openDirs, setOpenDirs]   = useStateNM(() => new Set(["pages"]));
  const [activityTab, setActivityTab] = useStateNM("files");   // files | search | git | settings
  const [query, setQuery]         = useStateNM("");

  const tree = useMemoNM(() => buildTree(NM_FILES), []);
  const fileMeta = useMemoNM(() => {
    const m = {};
    NM_FILES.forEach((f) => (m[f.path] = f));
    return m;
  }, []);

  // close on Escape
  useEffectNM(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
      if ((e.metaKey || e.ctrlKey) && e.key === "s" && activeTab) {
        e.preventDefault();
        saveFile(activeTab);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, activeTab, buffers]);

  const showToast = (msg, kind = "ok") => {
    setToast({ msg, kind });
    setTimeout(() => setToast(null), 2400);
  };

  const currentOf = (path) => {
    if (path in buffers) return buffers[path];
    return window.__VFS?.current?.[path] ?? "";
  };
  const originalOf = (path) => window.__VFS?.originals?.[path] ?? "";

  const isDirtyBuffer = (path) => path in buffers && buffers[path] !== window.__VFS?.current?.[path];
  const hasOverride = (path) => {
    try {
      return localStorage.getItem("nerd:" + path) !== null;
    } catch (e) { return false; }
  };

  const openFile = (file) => {
    if (!file || !file.path) return;
    setOpenTabs((tabs) => (tabs.includes(file.path) ? tabs : [...tabs, file.path]));
    setActiveTab(file.path);
  };

  const closeTab = (path, e) => {
    e?.stopPropagation();
    setOpenTabs((tabs) => {
      const next = tabs.filter((t) => t !== path);
      if (activeTab === path) setActiveTab(next[next.length - 1] || null);
      return next;
    });
    setBuffers((b) => {
      const n = { ...b };
      delete n[path];
      return n;
    });
  };

  const onEdit = (path, val) => {
    setBuffers((b) => ({ ...b, [path]: val }));
  };

  const toggleDir = (path) => {
    setOpenDirs((s) => {
      const n = new Set(s);
      if (n.has(path)) n.delete(path); else n.add(path);
      return n;
    });
  };

  // Apply a CSS file live by rewriting its injected <style>.
  const applyCssLive = (path, text) => {
    const style = document.querySelector(`style[data-nerd-path="${path}"]`);
    if (style) style.textContent = text;
  };

  // Save: persist override to localStorage, mark current.
  const saveFile = (path) => {
    if (!(path in buffers)) return;
    const meta = fileMeta[path];
    if (!meta || meta.readonly) {
      showToast(`${path} is read-only`, "err");
      return;
    }
    const text = buffers[path];
    try {
      if (text === originalOf(path)) {
        localStorage.removeItem("nerd:" + path);
      } else {
        localStorage.setItem("nerd:" + path, text);
      }
    } catch (e) {
      showToast("localStorage write failed", "err");
      return;
    }
    if (window.__VFS) window.__VFS.current[path] = text;
    setBuffers((b) => {
      const n = { ...b };
      delete n[path];
      return n;
    });
    setSavedTick((t) => t + 1);

    if (meta.type === "css") {
      applyCssLive(path, text);
      showToast(`Saved & applied ${path}`, "ok");
    } else {
      showToast(`Saved ${path} — reload to apply`, "warn");
    }
  };

  const revertBuffer = (path) => {
    setBuffers((b) => {
      const n = { ...b };
      delete n[path];
      return n;
    });
    showToast(`Reverted unsaved edits in ${path}`, "ok");
  };

  const resetFile = (path) => {
    try {
      localStorage.removeItem("nerd:" + path);
    } catch (e) {}
    const orig = originalOf(path);
    if (window.__VFS) window.__VFS.current[path] = orig;
    setBuffers((b) => {
      const n = { ...b };
      delete n[path];
      return n;
    });
    setSavedTick((t) => t + 1);
    const meta = fileMeta[path];
    if (meta?.type === "css") {
      applyCssLive(path, orig);
      showToast(`Reset ${path} to disk`, "ok");
    } else {
      showToast(`Reset ${path} — reload to drop overrides`, "warn");
    }
  };

  const resetAll = () => {
    if (!confirm("Drop ALL local overrides and reload?")) return;
    try {
      NM_FILES.forEach((f) => localStorage.removeItem("nerd:" + f.path));
    } catch (e) {}
    location.reload();
  };

  const reload = () => location.reload();

  // search hits across files (cheap substring; this is decoration).
  // Declared BEFORE the early-return so hook order stays stable across open/closed.
  const searchHits = useMemoNM(() => {
    if (!open || !query || query.length < 2) return [];
    const q = query.toLowerCase();
    const hits = [];
    for (const f of NM_FILES) {
      const text = (window.__VFS?.current?.[f.path] || "");
      const lines = text.split("\n");
      lines.forEach((l, i) => {
        if (l.toLowerCase().includes(q) && hits.length < 60) {
          hits.push({ path: f.path, line: i + 1, text: l.trim().slice(0, 120) });
        }
      });
    }
    return hits;
  }, [open, query, savedTick]);

  if (!open) return null;

  const active = activeTab ? fileMeta[activeTab] : null;
  const overridesCount = NM_FILES.filter((f) => hasOverride(f.path)).length;
  const dirtyCount = Object.keys(buffers).filter((p) => isDirtyBuffer(p)).length;

  return (
    <div className="nm-root" onMouseDown={(e) => { if (e.target.classList.contains("nm-backdrop")) onClose(); }}>
      <div className="nm-backdrop" />
      <div className="nm-window">
        {/* Title bar */}
        <div className="nm-titlebar">
          <div className="nm-traffic">
            <span className="nm-light r" onClick={onClose} title="Close (Esc)" />
            <span className="nm-light y" title="Minimise" />
            <span className="nm-light g" title="Maximise" />
          </div>
          <div className="nm-title">
            <span className="nm-title-glyph">{"{ }"}</span>
            <span>nerd mode</span>
            <span className="nm-title-dim">— invisible/</span>
            <span className="nm-title-path">{activeTab || "no file"}</span>
            {dirtyCount > 0 && <span className="nm-title-dirty">● {dirtyCount} unsaved</span>}
          </div>
          <div className="nm-title-actions">
            <button className="nm-tbtn" onClick={reload} title="Reload window">↻ reload</button>
            <button className="nm-tbtn danger" onClick={resetAll} title="Drop all overrides">⌫ reset all</button>
            <button className="nm-tbtn close" onClick={onClose} title="Close">×</button>
          </div>
        </div>

        {/* Body */}
        <div className="nm-body">
          {/* Activity bar */}
          <div className="nm-activity">
            {[
              { id: "files",    glyph: "▤", label: "Explorer" },
              { id: "search",   glyph: "⌕", label: "Search" },
              { id: "git",      glyph: "ϟ", label: "Source control" },
              { id: "settings", glyph: "✱", label: "Settings" },
            ].map((a) => (
              <button
                key={a.id}
                className={"nm-act " + (activityTab === a.id ? "active" : "")}
                title={a.label}
                onClick={() => setActivityTab(a.id)}
              >
                <span>{a.glyph}</span>
                {a.id === "git" && overridesCount > 0 && (
                  <span className="nm-act-badge">{overridesCount}</span>
                )}
              </button>
            ))}
            <div style={{ flex: 1 }} />
            <div className="nm-act-meta">
              <div className="nm-act-meta-row">v0.3</div>
              <div className="nm-act-meta-row">⌘</div>
            </div>
          </div>

          {/* Side panel */}
          <div className="nm-side">
            <div className="nm-side-head">
              {activityTab === "files"    && "EXPLORER"}
              {activityTab === "search"   && "SEARCH"}
              {activityTab === "git"      && "SOURCE CONTROL"}
              {activityTab === "settings" && "SETTINGS"}
            </div>

            {activityTab === "files" && (
              <div className="nm-tree">
                <div className="nm-tree-root">
                  <span className="nm-tree-caret open">▸</span>
                  <span className="nm-tree-name">invisible</span>
                  <span className="nm-tree-meta">{NM_FILES.length} files</span>
                </div>
                <NMTreeNode
                  node={tree}
                  depth={0}
                  openSet={openDirs}
                  toggleDir={toggleDir}
                  openFile={openFile}
                  activePath={activeTab}
                />
              </div>
            )}

            {activityTab === "search" && (
              <div className="nm-search">
                <input
                  className="nm-search-input"
                  placeholder="find in files…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  autoFocus
                />
                <div className="nm-search-meta">
                  {query.length < 2 ? "type 2+ chars" : `${searchHits.length} matches`}
                </div>
                <div className="nm-search-hits">
                  {searchHits.map((h, i) => (
                    <div
                      key={i}
                      className="nm-search-hit"
                      onClick={() => openFile(fileMeta[h.path])}
                    >
                      <div className="nm-search-hit-head">
                        <span className="nm-search-hit-file">{h.path}</span>
                        <span className="nm-search-hit-ln">:{h.line}</span>
                      </div>
                      <div className="nm-search-hit-text">{h.text}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activityTab === "git" && (
              <div className="nm-git">
                <div className="nm-git-section">CHANGES ({overridesCount})</div>
                {NM_FILES.filter((f) => hasOverride(f.path)).map((f) => (
                  <div key={f.path} className="nm-git-row" onClick={() => openFile(f)}>
                    <span className="nm-git-dot" />
                    <span className="nm-git-path">{f.path}</span>
                    <button
                      className="nm-git-btn"
                      onClick={(e) => { e.stopPropagation(); resetFile(f.path); }}
                      title="Discard"
                    >×</button>
                  </div>
                ))}
                {overridesCount === 0 && <div className="nm-git-empty">no local changes</div>}
                <div className="nm-git-section" style={{ marginTop: 16 }}>BRANCH</div>
                <div className="nm-git-row">
                  <span className="nm-git-dot" style={{ background: "var(--c-fold)" }} />
                  <span className="nm-git-path">main · local</span>
                </div>
              </div>
            )}

            {activityTab === "settings" && (
              <div className="nm-settings">
                <div className="nm-set-row">
                  <span>Theme</span><span className="muted">invisible-dark</span>
                </div>
                <div className="nm-set-row">
                  <span>Font</span><span className="muted">Geist Mono</span>
                </div>
                <div className="nm-set-row">
                  <span>Tab size</span><span className="muted">2 spaces</span>
                </div>
                <div className="nm-set-row">
                  <span>Auto-save</span><span className="muted">off (⌘S)</span>
                </div>
                <button className="nm-tbtn danger" style={{ marginTop: 16 }} onClick={resetAll}>
                  ⌫ drop all overrides
                </button>
              </div>
            )}
          </div>

          {/* Editor column */}
          <div className="nm-main">
            {/* Tabs */}
            <div className="nm-tabs">
              {openTabs.length === 0 && (
                <div className="nm-tab-empty">no file open — pick one from the tree</div>
              )}
              {openTabs.map((p) => {
                const ico = fileIconFor(p);
                const dirty = isDirtyBuffer(p);
                return (
                  <div
                    key={p}
                    className={"nm-tab " + (activeTab === p ? "active" : "")}
                    onClick={() => setActiveTab(p)}
                  >
                    <span className="nm-tab-ico" style={{ color: ico.color }}>{ico.glyph}</span>
                    <span className="nm-tab-name">{p}</span>
                    {dirty && <span className="nm-tab-dot" />}
                    <button className="nm-tab-x" onClick={(e) => closeTab(p, e)}>×</button>
                  </div>
                );
              })}
            </div>

            {/* Editor pane */}
            <div className="nm-pane">
              {!active && (
                <div className="nm-empty">
                  <div className="nm-empty-glyph">{"{ }"}</div>
                  <div className="nm-empty-title">nerd mode</div>
                  <div className="nm-empty-sub">
                    edit the live source. CSS hot-applies; JSX persists and reloads.
                  </div>
                  <div className="nm-empty-hint">
                    <kbd>⌘S</kbd> save · <kbd>Esc</kbd> close · <kbd>Tab</kbd> indent
                  </div>
                </div>
              )}

              {active && (
                <>
                  <div className="nm-actionbar">
                    <span className="nm-breadcrumb">
                      invisible <span className="nm-bc-sep">›</span>{" "}
                      {active.path.split("/").map((seg, i, arr) => (
                        <React.Fragment key={i}>
                          {seg}
                          {i < arr.length - 1 && <span className="nm-bc-sep"> › </span>}
                        </React.Fragment>
                      ))}
                    </span>
                    <div style={{ flex: 1 }} />
                    {active.readonly && <span className="nm-chip ro">read-only</span>}
                    {!active.readonly && isDirtyBuffer(active.path) && (
                      <span className="nm-chip dirty">unsaved</span>
                    )}
                    {hasOverride(active.path) && (
                      <span className="nm-chip override">override active</span>
                    )}
                    {!active.readonly && (
                      <>
                        <button
                          className="nm-tbtn"
                          onClick={() => revertBuffer(active.path)}
                          disabled={!isDirtyBuffer(active.path)}
                        >
                          revert
                        </button>
                        <button
                          className="nm-tbtn"
                          onClick={() => resetFile(active.path)}
                          disabled={!hasOverride(active.path) && !isDirtyBuffer(active.path)}
                          title="Drop override and use shipped version"
                        >
                          reset
                        </button>
                        <button
                          className="nm-tbtn accent"
                          onClick={() => saveFile(active.path)}
                          disabled={!isDirtyBuffer(active.path)}
                          title="⌘S"
                        >
                          {active.type === "css" ? "apply" : "save"}
                        </button>
                      </>
                    )}
                  </div>

                  <NMEditor
                    key={active.path + ":" + savedTick}
                    value={currentOf(active.path)}
                    lang={active.lang}
                    onChange={(v) => onEdit(active.path, v)}
                    readonly={active.readonly}
                  />
                </>
              )}
            </div>

            {/* Status bar */}
            <div className="nm-statusbar">
              <span className="nm-sb-seg" style={{ color: "var(--c-fold)" }}>● main</span>
              <span className="nm-sb-seg">{overridesCount} overrides</span>
              <span className="nm-sb-seg">{dirtyCount} unsaved</span>
              <div style={{ flex: 1 }} />
              {active && <>
                <span className="nm-sb-seg">UTF-8</span>
                <span className="nm-sb-seg">LF</span>
                <span className="nm-sb-seg">{active.lang.toUpperCase()}</span>
              </>}
              <span className="nm-sb-seg">⌘S save · Esc close</span>
            </div>
          </div>
        </div>

        {toast && (
          <div className={"nm-toast " + toast.kind}>{toast.msg}</div>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { NerdMode });
