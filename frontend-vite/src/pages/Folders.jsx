// Folders — three-source layout: Local / VPS / GitHub side-by-side.
// Each source is its own column with its own tree + accent color.

import { useState } from 'react';
import { I } from '../Icons.jsx';
import { FOLDERS } from '../Data.jsx';

function TreeNode({ node, depth = 0, source }) {
  const [open, setOpen] = useState(node.open || false);
  const [sel, setSel] = useState(false);
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

function Folders() {
  const [q, setQ] = useState("");
  const sources = [
    ["local", FOLDERS.local],
    ["vps",   FOLDERS.vps],
    ["repo",  FOLDERS.repo],
  ];

  return (
    <>
      <div style={{ display: "flex", gap: "var(--pad-3)", marginBottom: "var(--pad-4)", alignItems: "center" }}>
        <div style={{ position: "relative", flex: 1, maxWidth: 360 }}>
          <span style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-4)" }}>
            <I.Search size={14}/>
          </span>
          <input
            className="field"
            placeholder="Search across all sources…"
            value={q}
            onChange={e => setQ(e.target.value)}
            style={{ paddingLeft: 32, width: "100%" }}
          />
        </div>
        <span className="chip"><span className="chip-dot" style={{ color: "var(--c-fold)" }}/>Local · 1,204 files</span>
        <span className="chip"><span className="chip-dot" style={{ color: "var(--c-graph)" }}/>VPS · synced 2m ago</span>
        <span className="chip"><span className="chip-dot" style={{ color: "var(--c-tools)" }}/>GitHub · 26 repos</span>
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

export default Folders;
