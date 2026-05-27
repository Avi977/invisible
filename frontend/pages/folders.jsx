// Folders — three-source layout: Local / VPS / GitHub side-by-side.
// Each source is its own column with its own tree + accent color.
//
// REQ-03 wiring: the three trees are fetched live from the dashboard daemon
// on :8765 (the frontend itself is served from :8090 — cross-origin, hence
// the dashboard's CORS preflight + Access-Control-Allow-Origin: * posture).
// The local source ALSO subscribes to /api/v1/tree/local?watch=1 (SSE) so
// that filesystem changes propagate within ~5s without a page reload.

const { useState: useStateF, useEffect: useEffectF, useRef: useRefF } = React;

// The dashboard daemon. Hardcoded for now; a future plan (REQ-06 Vite shell)
// will move this into a shared config or env injection.
const API_BASE = "http://127.0.0.1:8765";

// EventSource auto-reconnects forever with backoff. After this many consecutive
// `error` events with no intervening `snapshot`/`diff`, surface a column-level
// placeholder so a flapping/dead daemon is visible instead of silent retries.
const SSE_ERROR_CEILING = 3;

// Token discovery: URL ?token= first (lets you bookmark from phone),
// then window.INVISIBLE_TOKEN (future bootstrap injection).
function getToken() {
  const u = new URLSearchParams(window.location.search).get("token");
  if (u) return u;
  if (window.INVISIBLE_TOKEN) return window.INVISIBLE_TOKEN;
  return "";
}

// Source metadata — keeps the column-header / chip rendering visually
// identical to the pre-wiring mock version. (The `tree` field is injected
// by the Folders component below; the rest is static visual chrome.)
const SOURCE_META = {
  local: { label: "Local",  meta: "MBP",                color: "var(--c-fold)"  },
  vps:   { label: "VPS",    meta: "via SSH",            color: "var(--c-graph)" },
  repo:  { label: "GitHub", meta: "gh api · 60s cache", color: "var(--c-tools)" },
};

function TreeNode({ node, depth = 0, source }) {
  const [open, setOpen] = useStateF(node.open || false);
  const [sel, setSel] = useStateF(false);
  const hasChildren = node.children && node.children.length > 0;
  const isFolder = node.type === "folder";

  return (
    <>
      <div
        className={"tree-row " + (isFolder ? "folder " : "") + (open ? "open " : "") + (sel ? "selected" : "")}
        style={{ paddingLeft: 10 + depth * 14 }}
        onClick={() => { if (hasChildren) setOpen(o => !o); else setSel(s => !s); }}
      >
        <span className="caret">{hasChildren ? "▶" : ""}</span>
        <span className="ico">
          {isFolder ? <I.Folder size={13}/> : <I.File size={13}/>}
        </span>
        <span>{node.name}</span>
        {node.badge && <span className="badge">{node.badge}</span>}
      </div>
      {open && hasChildren && node.children.map((c, i) => (
        <TreeNode key={node.name + i} node={c} depth={depth + 1} source={source}/>
      ))}
    </>
  );
}

function FolderColumn({ sourceKey, source, active, onClick }) {
  const ICONS = {
    local: <I.HardDrive size={16}/>,
    vps:   <I.Server size={16}/>,
    repo:  <I.GitHub size={16}/>,
  };
  return (
    <div
      className={"folder-tree " + (active ? "active" : "")}
      style={{
        "--s-c": source.color,
        flex: 1,
        minWidth: 0,
        opacity: active ? 1 : 0.92,
        borderColor: active ? `color-mix(in oklab, ${source.color} 30%, transparent)` : undefined,
      }}
    >
      <div className="folder-tree-head">
        <span style={{ color: source.color, display: "inline-flex" }}>{ICONS[sourceKey]}</span>
        <span style={{ color: "var(--text-1)", fontWeight: 600, fontFamily: "var(--font-sans)", fontSize: 12 }}>{source.label}</span>
        <span style={{ marginLeft: "auto" }}>{source.meta}</span>
      </div>
      <div className="folder-tree-body">
        {source.tree.map((n, i) => <TreeNode key={i} node={n} source={sourceKey}/>)}
      </div>
    </div>
  );
}

function Folders({ project } = {}) {
  // `project` (optional prop) — if set, only that project's subtree is fetched
  // from every endpoint. Mirrored to the URL `?project=<name>` so the
  // dashboard's "Dive in → Folders" link works without prop drilling.
  const [q, setQ] = useStateF("");
  const [trees,  setTrees]   = useStateF({ local: null, vps: null, repo: null });
  const [errors, setErrors]  = useStateF({ local: null, vps: null, repo: null });
  const [loading, setLoading] = useStateF(true);
  const sseRef = useRefF(null);
  // Bounded SSE error counter (WARNING #6 from checker pass): EventSource
  // auto-reconnects on error forever — without a ceiling a dead daemon is
  // invisible to the user. We increment here on `error`, reset on any
  // successful event, and surface a placeholder at SSE_ERROR_CEILING.
  const consecutiveErrorCount = useRefF(0);

  const effectiveProject = project
    || new URLSearchParams(window.location.search).get("project")
    || null;

  useEffectF(() => {
    const token = getToken();
    const headers = token ? { Authorization: "Bearer " + token } : {};
    const qs = effectiveProject ? "?project=" + encodeURIComponent(effectiveProject) : "";

    let cancelled = false;

    // One fetch per source. Errors land in errors[key]; data lands in trees[key].
    // Returns the promise so the outer Promise.all can flip `loading` off.
    const fetchOne = (key) =>
      fetch(API_BASE + "/api/v1/tree/" + key + qs, { headers })
        .then((r) => r.json().then((body) => ({ ok: r.ok, status: r.status, body })))
        .then(({ ok, status, body }) => {
          if (cancelled) return;
          if (!ok) {
            // VPS 503 lands here with body = {error: "vps.host not configured"}.
            // The dashboard unwraps the [VPS_NOT_CONFIGURED] wrapper into a
            // bare object so this branch can read `.error` directly.
            setErrors((e) => ({ ...e, [key]: (body && body.error) || ("HTTP " + status) }));
            setTrees((t) => ({ ...t, [key]: [] }));
            return;
          }
          setTrees((t) => ({ ...t, [key]: body }));
          setErrors((e) => e[key] ? ({ ...e, [key]: null }) : e); // clear stale error
        })
        .catch((err) => {
          if (cancelled) return;
          setErrors((e) => ({ ...e, [key]: String(err) }));
          setTrees((t) => ({ ...t, [key]: [] }));
        });

    Promise.all([fetchOne("local"), fetchOne("repo"), fetchOne("vps")])
      .finally(() => { if (!cancelled) setLoading(false); });

    // SSE subscription for the local source. EventSource cannot set the
    // Authorization header, so the token rides as ?token= (the dashboard's
    // _token_from_request helper accepts both forms).
    const sseUrl = API_BASE + "/api/v1/tree/local?watch=1"
      + (token ? "&token=" + encodeURIComponent(token) : "")
      + (effectiveProject ? "&project=" + encodeURIComponent(effectiveProject) : "");
    const es = new EventSource(sseUrl);
    sseRef.current = es;

    es.addEventListener("snapshot", (ev) => {
      consecutiveErrorCount.current = 0;
      try {
        const payload = JSON.parse(ev.data);
        if (!cancelled && payload && Array.isArray(payload.tree)) {
          setTrees((t) => ({ ...t, local: payload.tree }));
          setErrors((e) => e.local ? ({ ...e, local: null }) : e);
        }
      } catch (_) {
        /* malformed snapshot — ignore; the JSON fetch path is still authoritative */
      }
    });

    es.addEventListener("diff", () => {
      consecutiveErrorCount.current = 0;
      // Cheap MVP strategy: any diff event triggers a re-fetch of the local
      // tree. Future optimization: apply the diff payload in-place to the
      // existing tree to avoid the round-trip.
      // TODO(REQ-03, future): debounce — successive diffs during `npm install`
      // cause re-fetch storms; the server caps event volume but the client
      // should coalesce within ~250ms.
      if (cancelled) return;
      fetchOne("local");
    });

    es.addEventListener("error", () => {
      consecutiveErrorCount.current += 1;
      if (consecutiveErrorCount.current >= SSE_ERROR_CEILING) {
        if (!cancelled) {
          setErrors((e) => ({ ...e, local: "Local stream disconnected — check daemon" }));
        }
      }
    });

    return () => {
      cancelled = true;
      consecutiveErrorCount.current = 0;
      if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }
    };
  }, [effectiveProject]);

  // Build the {label, meta, color, tree} shape that FolderColumn consumes.
  // Each column's body is one of: loading-placeholder, error-placeholder,
  // empty-placeholder, or the real tree. The placeholders are wrapped as
  // valid tree nodes so TreeNode renders them without special casing.
  const sources = ["local", "vps", "repo"].map((k) => {
    const meta = SOURCE_META[k];
    const tree = trees[k];
    const err  = errors[k];
    let body;
    if (tree === null) {
      body = [{ name: loading ? "Loading…" : "—", type: "file" }];
    } else if (err) {
      body = [{ name: err, type: "file", badge: "error" }];
    } else if (tree.length === 0) {
      body = [{ name: "(empty)", type: "file" }];
    } else {
      body = tree;
    }
    return [k, { label: meta.label, meta: meta.meta, color: meta.color, tree: body }];
  });

  return (
    <>
      <div style={{ display: "flex", gap: "var(--pad-3)", marginBottom: "var(--pad-4)", alignItems: "center" }}>
        <div style={{ position: "relative", flex: 1, maxWidth: 360 }}>
          <span style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-4)" }}>
            <I.Search size={14}/>
          </span>
          {/* TODO(REQ-03, future): wire q to filter tree nodes — visual-only stub for now. */}
          <input
            className="field"
            placeholder="Search across all sources…"
            value={q}
            onChange={e => setQ(e.target.value)}
            style={{ paddingLeft: 32, width: "100%" }}
          />
        </div>
        {effectiveProject && (
          <span className="chip"><span className="chip-dot" style={{ color: "var(--c-fold)" }}/>filter: {effectiveProject}</span>
        )}
        <button className="btn accent" style={{ marginLeft: "auto" }}>
          <I.Plus size={13}/> New source
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--pad-3)", height: "calc(100% - 60px)" }}>
        {sources.map(([k, s]) => (
          <FolderColumn key={k} sourceKey={k} source={s} active={true}/>
        ))}
      </div>
    </>
  );
}

window.Folders = Folders;
