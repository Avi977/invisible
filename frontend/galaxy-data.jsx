// galaxy-data.jsx — turns the REAL relations graph into an "app galaxy".
//
// Unlike the design prototype (which procedurally invented demo projects), this
// builds window.GALAXY from live /api/v1/relations data: each project becomes a
// glowing cluster core, every module/doc/endpoint becomes a child star orbiting
// it, and real import/grep links become edges. A procedural dust disk + bulge is
// kept purely for the galaxy aesthetic.
//
// Exposes window.buildGalaxy(data) — called by pages/relations.jsx after it
// fetches the graph. Nothing is built at load time (there's no data yet).
//
//   data = { nodes: [{id,label,type,project,file_path}], edges: [{from,to,kind}] }

(function () {
  // ---- seeded RNG (mulberry32) + helpers ----
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // ---- palette ----
  // child kinds (real node `type` maps onto these design kinds)
  const KIND_COLOR = {
    project: null,             // each project carries its own core color
    tool:    [245, 179, 67],   // amber   — endpoints / external tools
    note:    [138, 169, 255],  // blue    — docs / notes
    repo:    [94, 224, 200],   // teal    — repos (unused by current data)
    mod:     [158, 170, 210],  // violet-gray — code modules
  };
  // real relations `type` → galaxy kind
  const TYPE_KIND = { module: "mod", doc: "note", endpoint: "tool", repo: "repo" };
  // deterministic core palette, assigned per project by sorted order
  const PROJECT_PALETTE = [
    [245, 179, 67],   // amber
    [92, 200, 255],   // sky
    [183, 148, 255],  // violet
    [74, 222, 128],   // green
    [245, 111, 177],  // pink
    [94, 224, 200],   // teal
  ];

  // warm core -> cool rim gradient for background dust
  function dustColor(rNorm) {
    const core = [255, 226, 168], mid = [180, 190, 255], rim = [120, 150, 235];
    let c1, c2, t;
    if (rNorm < 0.5) { c1 = core; c2 = mid; t = rNorm / 0.5; }
    else { c1 = mid; c2 = rim; t = (rNorm - 0.5) / 0.5; }
    return [
      Math.round(c1[0] + (c2[0] - c1[0]) * t),
      Math.round(c1[1] + (c2[1] - c1[1]) * t),
      Math.round(c1[2] + (c2[2] - c1[2]) * t),
    ];
  }

  const R = 620;            // galaxy radius
  const ARMS = 3;
  const WIND = 0.0135;      // radians of twist per unit radius
  const GREP_EDGE_CAP = 140; // cap noisy text-cooccurrence links so it never hairballs

  // Build window.GALAXY from a real relations payload. Returns the GALAXY object.
  function buildGalaxy(data) {
    const rng = mulberry32(20260602);
    const rand = (a, b) => a + (b - a) * rng();
    const gauss = () => {
      let u = 0, v = 0;
      while (u === 0) u = rng();
      while (v === 0) v = rng();
      return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
    };

    const realNodes = (data && Array.isArray(data.nodes)) ? data.nodes : [];
    const realEdges = (data && Array.isArray(data.edges)) ? data.edges : [];

    const stars = [];
    const nodes = [];
    const edges = [];
    const nodeIndex = {};           // galaxy node id -> index in `nodes`
    const realToIdx = {};           // real node id   -> index in `nodes`

    function addNode(n) {
      n.col = n.color || KIND_COLOR[n.kind] || [200, 200, 210];
      n.idx = nodes.length;
      nodes.push(n);
      nodeIndex[n.id] = n.idx;
      return n.idx;
    }

    // place a disk star with spiral-arm structure + scatter
    function diskStar(rOuter) {
      const r = R * Math.pow(rng(), 0.62) * rOuter;
      const arm = (rng() * ARMS) | 0;
      const armAngle = arm * ((2 * Math.PI) / ARMS);
      const scatter = gauss() * (0.30 + 0.55 * (1 - r / R));
      const theta = armAngle + r * WIND + scatter;
      return { x: Math.cos(theta) * r, y: Math.sin(theta) * r, z: gauss() * (14 + 46 * Math.exp(-r / 230)), r };
    }
    function clusterChild(cx, cy, cz, spread) {
      return { x: cx + gauss() * spread, y: cy + gauss() * spread, z: cz + gauss() * spread * 0.4 };
    }

    // ---- background dust disk ----
    for (let i = 0; i < 2000; i++) {
      const s = diskStar(1);
      const rNorm = Math.min(1, s.r / R);
      stars.push({ kind: "dust", x: s.x, y: s.y, z: s.z, size: rand(0.5, 1.4),
        col: dustColor(rNorm), alpha: rand(0.25, 0.7) * (1 - rNorm * 0.4), tw: rng() * Math.PI * 2 });
    }
    // ---- central bulge ----
    for (let i = 0; i < 650; i++) {
      const r = Math.pow(rng(), 1.8) * 150;
      const theta = rng() * Math.PI * 2;
      stars.push({ kind: "dust", x: Math.cos(theta) * r, y: Math.sin(theta) * r,
        z: gauss() * (60 * Math.exp(-r / 90)), size: rand(0.6, 1.6),
        col: dustColor(r / R * 0.5), alpha: rand(0.4, 0.9), tw: rng() * Math.PI * 2 });
    }

    // ---- group real nodes by project ----
    const byProject = {};
    for (const n of realNodes) {
      const pid = n.project || "unscoped";
      (byProject[pid] = byProject[pid] || []).push(n);
    }
    const projectNames = Object.keys(byProject).sort();
    const denom = Math.max(1, projectNames.length - 1);

    projectNames.forEach((pname, pi) => {
      const children = byProject[pname];
      const color = PROJECT_PALETTE[pi % PROJECT_PALETTE.length];
      // place the core along a spiral arm; spread projects across the disk
      const rPos = projectNames.length === 1 ? 0.42 : 0.34 + 0.44 * (pi / denom);
      const r = R * rPos;
      const theta = (pi % ARMS) * ((2 * Math.PI) / ARMS) + r * WIND + pi * 0.6;
      const cx = Math.cos(theta) * r, cy = Math.sin(theta) * r, cz = gauss() * 14;

      // type breakdown for the core's detail card
      const typeCounts = {};
      for (const c of children) typeCounts[c.type] = (typeCounts[c.type] || 0) + 1;
      const stack = Object.keys(typeCounts).sort().map((t) => `${t} ×${typeCounts[t]}`);

      const coreIdx = addNode({
        id: pname, label: pname, kind: "project", tier: 0, color,
        x: cx, y: cy, z: cz,
        desc: `${children.length} nodes`, stack,
      });

      // cluster spread scales with child count so big apps don't overlap-blur
      const spread = 26 + 5.2 * Math.sqrt(children.length);
      for (const c of children) {
        const pos = clusterChild(cx, cy, cz, spread);
        const cIdx = addNode({
          id: c.id, label: c.label || c.id, kind: TYPE_KIND[c.type] || "mod",
          tier: 2, x: pos.x, y: pos.y, z: pos.z, parent: pname,
          desc: c.file_path || undefined,
        });
        realToIdx[c.id] = cIdx;
        edges.push([coreIdx, cIdx]);   // the core->child ray (the cluster's shape)
      }

      // halo of anonymous dust hugging the cluster, tinted by the core color
      const halo = Math.min(220, 60 + children.length);
      for (let i = 0; i < halo; i++) {
        const pos = clusterChild(cx, cy, cz, spread * 1.25);
        stars.push({ kind: "dust", x: pos.x, y: pos.y, z: pos.z, size: rand(0.6, 1.7),
          col: color, alpha: rand(0.16, 0.45), tw: rng() * Math.PI * 2 });
      }
    });

    // ---- real edges → galaxy edges (import always; sample noisy grep links) ----
    let grepKept = 0, grepSeen = 0, grepDropped = 0;
    const grepTotal = realEdges.filter((e) => e.kind === "grep").length;
    const grepStride = grepTotal > GREP_EDGE_CAP ? Math.ceil(grepTotal / GREP_EDGE_CAP) : 1;
    for (const e of realEdges) {
      const a = realToIdx[e.from], b = realToIdx[e.to];
      if (a == null || b == null || a === b) continue;
      if (e.kind === "grep") {
        if (grepSeen++ % grepStride !== 0) { grepDropped++; continue; }
        grepKept++;
      }
      edges.push([a, b]);
    }
    if (grepDropped > 0) {
      console.info(`[galaxy] sampled grep links: kept ${grepKept}/${grepTotal} (capped at ~${GREP_EDGE_CAP}); ${grepDropped} dropped`);
    }

    window.GALAXY = {
      R, stars, nodes, edges, nodeIndex,
      counts: { stars: stars.length, nodes: nodes.length, edges: edges.length, projects: projectNames.length },
    };
    return window.GALAXY;
  }

  window.buildGalaxy = buildGalaxy;
})();
