// Mock data — multiple sets, switchable from Tweaks
export const DATA_SETS = {
  default: {
    name: "Personal",
    projects: [
      {
        id: "echo", code: "EC", name: "Echo", color: "#f5b343",
        status: "in-progress", branch: "main", lastCommit: "23m ago",
        summary: "Voice-first journaling app — capture thoughts via Whisper, synthesize daily themes with Claude. iOS shipping next sprint.",
        progress: 68,
        todos: [
          { t: "Wire StoreKit subscription flow", done: false },
          { t: "Fix waveform jitter on iPhone 13", done: false },
          { t: "Audit consent copy with legal", done: true },
          { t: "Onboarding A/B variants", done: false },
        ],
        note: "Got the streaming transcription working but the waveform visualizer freezes when audio session interrupts. Suspect it's the AVAudioEngine restart — not the buffer. Try resuming engine before reconnecting tap tomorrow.",
        stack: ["Swift", "Whisper", "Claude"],
        nextEvent: "Standup · 9:30",
      },
      {
        id: "lumen", code: "LM", name: "Lumen", color: "#5cc8ff",
        status: "in-progress", branch: "feat/auth-v2", lastCommit: "2h ago",
        summary: "Open-source dashboard kit for Postgres. Auto-discovers schema, generates dashboards. v0.4 focuses on RLS-aware widgets.",
        progress: 41,
        todos: [
          { t: "RLS-aware SQL generator", done: false },
          { t: "Migrate to PgBouncer pool", done: false },
          { t: "Theme tokens — dark + light", done: true },
        ],
        note: "Schema introspection works but it doesn't pick up partitioned tables. Look at pg_partitioned_table — there's a recursive walk needed. Also: connection pool drops every ~6 min, not sure why.",
        stack: ["Node", "Postgres", "React"],
        nextEvent: "Code review · 14:00",
      },
      {
        id: "drift", code: "DR", name: "Drift", color: "#b794ff",
        status: "blocked", branch: "main", lastCommit: "1d ago",
        summary: "Marketing site + waitlist for Echo. Custom WebGL hero, Framer-based CMS.",
        progress: 88,
        todos: [
          { t: "Waitlist email confirmation", done: false },
          { t: "Lighthouse ≥ 95 mobile", done: true },
          { t: "OG images per route", done: true },
        ],
        note: "Resend keeps bouncing the confirmation emails from @gmail in test mode. Probably need a verified sending domain — set up DKIM tomorrow morning before the launch call.",
        stack: ["Astro", "Three.js", "Resend"],
        nextEvent: "Launch sync · 16:00",
      },
      {
        id: "atlas", code: "AT", name: "Atlas", color: "#4ade80",
        status: "planning", branch: "—", lastCommit: "—",
        summary: "Internal infra: k3s on a fleet of Hetzner boxes, Tailscale mesh, GitOps via Argo. Foundation for everything else.",
        progress: 12,
        todos: [
          { t: "Spec out node topology", done: false },
          { t: "Cost model: Hetzner vs Vultr", done: true },
          { t: "Argo CD bootstrap manifest", done: false },
        ],
        note: "Decided to skip k0s — too opinionated. Going with stock k3s + cilium for networking. Budget is ~120 EUR/mo for 3 worker nodes which is fine.",
        stack: ["k3s", "Argo", "Cilium"],
        nextEvent: "Hetzner intro · Thu",
      },
      {
        id: "rune", code: "RN", name: "Rune", color: "#f56fb1",
        status: "in-progress", branch: "experiment/glyphs", lastCommit: "5h ago",
        summary: "Generative font weight explorer. Drop in any variable font, get back a curated set of weight pairings via vision model.",
        progress: 55,
        todos: [
          { t: "Pair the heavy weights properly", done: false },
          { t: "Export as CSS @font-face", done: false },
          { t: "Wire Claude vision call", done: true },
        ],
        note: "Vision returns surprisingly good pairings but it overweights serif/sans contrast. Tomorrow: add a prompt nudge to consider optical sizes.",
        stack: ["Python", "Claude", "Vite"],
        nextEvent: "—",
      },
      {
        id: "ferry", code: "FR", name: "Ferry", color: "#5ee0c8",
        status: "shipped", branch: "main", lastCommit: "3d ago",
        summary: "Webhook router + replay tool. Self-hosted. Powers all infra alerts.",
        progress: 100,
        todos: [
          { t: "v1.0 tagged + released", done: true },
          { t: "Homebrew tap", done: true },
        ],
        note: "Shipped clean — minor docs polish needed but otherwise solid. Got two stars and a thoughtful issue overnight.",
        stack: ["Go", "Redis", "Caddy"],
        nextEvent: "—",
      },
    ],
  },
  client: {
    name: "Client work",
    projects: [
      { id: "north", code: "NR", name: "Northwind Retail", color: "#f5b343", status: "in-progress", branch: "release/q3", lastCommit: "11m ago", summary: "POS rewrite — Vue 2 → Vue 3, plus a real offline mode using IndexedDB + sync queue.", progress: 72, todos: [{t:"Conflict resolution UI",done:false},{t:"Sync queue back-pressure",done:false},{t:"Legacy printer driver bridge",done:true}], note: "The sync queue keeps deadlocking when the user goes offline mid-transaction. I think it's the optimistic lock on cart items. Try moving the lock to the line item level.", stack: ["Vue", "IndexedDB", "Stripe"], nextEvent: "Demo · 10:00" },
      { id: "veridian", code: "VR", name: "Veridian Labs", color: "#5cc8ff", status: "in-progress", branch: "feat/llm-eval", lastCommit: "1h ago", summary: "LLM eval harness for a biotech. Scores model outputs against curated rubrics from domain experts.", progress: 48, todos: [{t:"Inter-rater reliability metric",done:false},{t:"Rubric versioning",done:false},{t:"Run #14 results",done:true}], note: "Cohen's kappa is the right metric here, not Fleiss — only two raters per item. Switched and the numbers actually look reasonable now.", stack: ["Python", "Claude", "Postgres"], nextEvent: "Sci review · 15:00" },
      { id: "hailey", code: "HC", name: "Hailey Co.", color: "#b794ff", status: "planning", branch: "—", lastCommit: "—", summary: "Brand site + commerce for an independent ceramics studio.", progress: 18, todos: [{t:"Photography brief",done:false},{t:"Type pairing options",done:true}], note: "Client wants Söhne but the license is steep. Going to present 3 alts that capture the same warmth without the cost.", stack: ["Shopify", "Hydrogen"], nextEvent: "Brand call · Fri" },
      { id: "midas", code: "MD", name: "Midas Finance", color: "#4ade80", status: "blocked", branch: "main", lastCommit: "4d ago", summary: "Compliance-grade audit log viewer for a fintech.", progress: 64, todos: [{t:"SOC 2 export format",done:false}], note: "Waiting on legal to clarify retention rules. Parked the export work, picked up Veridian instead.", stack: ["Next", "Postgres"], nextEvent: "Blocked" },
    ],
  },
};

// Folder structure
export const FOLDERS = {
  local: {
    label: "Local",
    meta: "MBP · /Users/dev",
    color: "var(--c-fold)",
    tree: [
      { name: "code", type: "folder", open: true, children: [
        { name: "echo", type: "folder", badge: "git" },
        { name: "lumen", type: "folder", badge: "git", open: true, children: [
          { name: "src", type: "folder" },
          { name: "package.json", type: "file" },
          { name: "README.md", type: "file" },
          { name: ".env.local", type: "file" },
        ]},
        { name: "drift", type: "folder", badge: "git" },
        { name: "scratch", type: "folder", children: [
          { name: "wave-jitter.swift", type: "file" },
          { name: "rls-walker.sql", type: "file" },
        ]},
      ]},
      { name: "notes", type: "folder", children: [
        { name: "Daily", type: "folder" },
        { name: "Architecture", type: "folder" },
      ]},
      { name: "Downloads", type: "folder", badge: "412" },
    ],
  },
  vps: {
    label: "VPS",
    meta: "hetzner-fsn1 · 49.12.x.x",
    color: "var(--c-graph)",
    tree: [
      { name: "/srv", type: "folder", open: true, children: [
        { name: "ferry", type: "folder", badge: "live" },
        { name: "lumen-staging", type: "folder", badge: "live" },
        { name: "atlas", type: "folder", children: [
          { name: "argo", type: "folder" },
          { name: "manifests", type: "folder" },
        ]},
      ]},
      { name: "/var/log", type: "folder", children: [
        { name: "ferry.log", type: "file", badge: "2.1G" },
        { name: "caddy.access", type: "file" },
      ]},
      { name: "/home/dev", type: "folder" },
    ],
  },
  repo: {
    label: "GitHub",
    meta: "26 repos · synced",
    color: "var(--c-tools)",
    tree: [
      { name: "@you/echo", type: "folder", badge: "main", open: true, children: [
        { name: "ios", type: "folder" },
        { name: "backend", type: "folder" },
        { name: ".github", type: "folder" },
      ]},
      { name: "@you/lumen", type: "folder", badge: "main" },
      { name: "@you/drift", type: "folder", badge: "main" },
      { name: "@you/ferry", type: "folder", badge: "v1.0" },
      { name: "@you/rune", type: "folder", badge: "draft" },
      { name: "@you/dotfiles", type: "folder" },
    ],
  },
};

// Per-project tool workflows. Each project has its own n8n-style graph.
export const TOOL_WORKFLOWS = {
  echo: {
    name: "Echo · ingest pipeline",
    nodes: [
      { id: "e1", type: "github",   name: "Voice clip",     code: "MIC", c: "#f5b343", body: "iOS upload",      x: 100, y: 120 },
      { id: "e2", type: "whisper",  name: "Whisper v3",     code: "AI",  c: "#f5b343", body: "transcribe",      x: 320, y: 120 },
      { id: "e3", type: "claude",   name: "Claude Sonnet",  code: "AI",  c: "#f5b343", body: "extract themes",  x: 540, y: 120 },
      { id: "e4", type: "embed",    name: "Voyage Embed",   code: "AI",  c: "#f5b343", body: "vectorize",       x: 540, y: 240 },
      { id: "e5", type: "postgres", name: "Postgres",       code: "DB",  c: "#5cc8ff", body: "entries + vecs",  x: 760, y: 180 },
      { id: "e6", type: "stripe",   name: "Stripe",         code: "$",   c: "#b794ff", body: "premium gate",    x: 320, y: 300 },
    ],
    edges: [
      { from: "e1", to: "e2" }, { from: "e2", to: "e3" }, { from: "e2", to: "e4" },
      { from: "e3", to: "e5" }, { from: "e4", to: "e5" }, { from: "e6", to: "e1" },
    ],
  },
  lumen: {
    name: "Lumen · dashboard gen",
    nodes: [
      { id: "l1", type: "postgres", name: "Postgres",       code: "DB",  c: "#5cc8ff", body: "user schema",    x: 100, y: 140 },
      { id: "l2", type: "code",     name: "Schema walker",  code: "JS",  c: "#5ee0c8", body: "RLS-aware",      x: 320, y: 140 },
      { id: "l3", type: "claude",   name: "Claude Haiku",   code: "AI",  c: "#f5b343", body: "suggest widgets",x: 540, y: 140 },
      { id: "l4", type: "redis",    name: "Redis",          code: "DB",  c: "#5cc8ff", body: "cache layout",   x: 540, y: 260 },
      { id: "l5", type: "github",   name: "GitHub Action",  code: "GH",  c: "#b794ff", body: "publish",        x: 760, y: 200 },
    ],
    edges: [
      { from: "l1", to: "l2" }, { from: "l2", to: "l3" }, { from: "l3", to: "l4" }, { from: "l3", to: "l5" },
    ],
  },
  drift: {
    name: "Drift · launch funnel",
    nodes: [
      { id: "d1", type: "github",   name: "Waitlist form",  code: "WL",  c: "#b794ff", body: "POST /signup",    x: 100, y: 160 },
      { id: "d2", type: "if",       name: "Validate",       code: "IF",  c: "#5ee0c8", body: "email ok",        x: 320, y: 160 },
      { id: "d3", type: "postgres", name: "Postgres",       code: "DB",  c: "#5cc8ff", body: "waitlist",        x: 540, y: 100 },
      { id: "d4", type: "resend",   name: "Resend",         code: "@",   c: "#b794ff", body: "welcome email",   x: 540, y: 240 },
      { id: "d5", type: "slack",    name: "Slack",          code: "#",   c: "#b794ff", body: "#growth",         x: 760, y: 180 },
    ],
    edges: [
      { from: "d1", to: "d2" }, { from: "d2", to: "d3" }, { from: "d2", to: "d4" },
      { from: "d3", to: "d5" }, { from: "d4", to: "d5" },
    ],
  },
  atlas: {
    name: "Atlas · deploy GitOps",
    nodes: [
      { id: "a1", type: "github",   name: "Push to main",   code: "GH",  c: "#b794ff", body: "atlas repo",      x: 100, y: 160 },
      { id: "a2", type: "code",     name: "Argo sync",      code: "CD",  c: "#5ee0c8", body: "k3s manifests",   x: 320, y: 160 },
      { id: "a3", type: "if",       name: "Health check",   code: "IF",  c: "#5ee0c8", body: "rollout ok",      x: 540, y: 160 },
      { id: "a4", type: "slack",    name: "Slack",          code: "#",   c: "#b794ff", body: "#deploys",        x: 760, y: 100 },
      { id: "a5", type: "github",   name: "Rollback",       code: "↶",   c: "#b794ff", body: "auto-revert",     x: 760, y: 240 },
    ],
    edges: [
      { from: "a1", to: "a2" }, { from: "a2", to: "a3" }, { from: "a3", to: "a4" }, { from: "a3", to: "a5" },
    ],
  },
  rune: {
    name: "Rune · pairing engine",
    nodes: [
      { id: "r1", type: "github",   name: "Font upload",    code: "TTF", c: "#b794ff", body: ".ttf / .otf",     x: 100, y: 160 },
      { id: "r2", type: "code",     name: "Sample render",  code: "JS",  c: "#5ee0c8", body: "skia canvas",     x: 320, y: 160 },
      { id: "r3", type: "claude",   name: "Claude Vision",  code: "AI",  c: "#f5b343", body: "rate pairings",   x: 540, y: 160 },
      { id: "r4", type: "s3",       name: "S3",             code: "S3",  c: "#5cc8ff", body: "samples bucket",  x: 320, y: 280 },
    ],
    edges: [
      { from: "r1", to: "r2" }, { from: "r2", to: "r3" }, { from: "r2", to: "r4" }, { from: "r4", to: "r3" },
    ],
  },
  ferry: {
    name: "Ferry · webhook router",
    nodes: [
      { id: "f1", type: "github",   name: "Inbound hook",   code: "IN",  c: "#b794ff", body: "any source",      x: 100, y: 160 },
      { id: "f2", type: "switch",   name: "Route",          code: "SW",  c: "#5ee0c8", body: "by signature",    x: 320, y: 160 },
      { id: "f3", type: "slack",    name: "Slack",          code: "#",   c: "#b794ff", body: "#alerts",         x: 540, y: 80  },
      { id: "f4", type: "resend",   name: "Resend",         code: "@",   c: "#b794ff", body: "ops email",       x: 540, y: 180 },
      { id: "f5", type: "redis",    name: "Redis",          code: "DB",  c: "#5cc8ff", body: "replay queue",    x: 540, y: 280 },
    ],
    edges: [
      { from: "f1", to: "f2" }, { from: "f2", to: "f3" }, { from: "f2", to: "f4" }, { from: "f2", to: "f5" },
    ],
  },
};

// Per-terminal project context — surfaced via the collapsible header.
export const TERM_CONTEXT = {
  "echo · ios": {
    project: "Echo",
    projectId: "echo",
    color: "#f5b343",
    goal: "Ship a stable iOS build with the new waveform fix before EOD.",
    activity: [
      { t: "12:42", k: "ok",   c: "swift build · completed in 4.21s" },
      { t: "12:39", k: "warn", c: "AVAudioSessionInterruption deprecation surfaced" },
      { t: "12:30", k: "ok",   c: "git pull · 3 new commits from main" },
      { t: "12:18", k: "ok",   c: "Recorder.swift refactor merged" },
    ],
    next: [
      "Boot iPhone 15 simulator and reproduce the freeze",
      "Restart AVAudioEngine before reconnecting input tap",
      "Add unit test for interruption recovery",
    ],
  },
  "lumen · dev": {
    project: "Lumen",
    projectId: "lumen",
    color: "#5cc8ff",
    goal: "Get RLS-aware widget generation working end-to-end on staging.",
    activity: [
      { t: "12:40", k: "ok",   c: "✓ Compiled /dashboard in 380ms" },
      { t: "12:38", k: "ok",   c: "Next 14.2.3 ready · :3000" },
      { t: "12:25", k: "warn", c: "schema walker missed partitioned tables" },
      { t: "12:10", k: "ok",   c: "RLS policy parser now handles SECURITY DEFINER" },
    ],
    next: [
      "Recursive walk for pg_partitioned_table",
      "Snapshot widget tree to Redis (5-min TTL)",
      "Wire generated widgets into demo dashboard",
    ],
  },
  "drift · build": {
    project: "Drift",
    projectId: "drift",
    color: "#b794ff",
    goal: "Pass Lighthouse ≥ 95 mobile and ship the new waitlist flow today.",
    activity: [
      { t: "12:42", k: "ok",   c: "astro build · 1.84s · 3 pages" },
      { t: "12:30", k: "warn", c: "Resend bounced @gmail confirmation in test" },
      { t: "12:20", k: "ok",   c: "OG images generated for all routes" },
      { t: "12:05", k: "ok",   c: "Lighthouse mobile: 96 perf · 100 a11y" },
    ],
    next: [
      "Set up verified sending domain + DKIM",
      "Add server-side bot filter to /signup",
      "Coordinate launch window with the Drift channel",
    ],
  },
  "atlas · k3s": {
    project: "Atlas",
    projectId: "atlas",
    color: "#4ade80",
    goal: "Stabilize k3s control plane and ship the Argo bootstrap manifest.",
    activity: [
      { t: "12:41", k: "err",  c: "metrics-server CrashLoopBackOff (8m)" },
      { t: "12:30", k: "ok",   c: "argocd-server running · 3d uptime" },
      { t: "12:00", k: "ok",   c: "Cilium installed · BGP peering up" },
      { t: "11:42", k: "ok",   c: "3-node Hetzner cluster joined" },
    ],
    next: [
      "Inspect metrics-server logs and patch the CrashLoop",
      "Commit the Argo bootstrap manifest",
      "Write runbook for node replacement",
    ],
  },
  "rune · python": {
    project: "Rune",
    projectId: "rune",
    color: "#f56fb1",
    goal: "Curate a believable pairing set for variable fonts using Claude Vision.",
    activity: [
      { t: "12:35", k: "ok",   c: "pair.py · saved pairings.json (12 pairs)" },
      { t: "12:22", k: "ok",   c: "Claude Vision returned 18 ratings" },
      { t: "12:12", k: "warn", c: "skia render fell back to bitmap for italic axis" },
      { t: "11:55", k: "ok",   c: "Inter.ttf · 18 axes detected" },
    ],
    next: [
      "Nudge prompt to weight optical-size axis",
      "Export CSS @font-face block from chosen pairs",
      "Add a “taste” slider that re-scores using user prefs",
    ],
  },
  "ferry · logs": {
    project: "Ferry",
    projectId: "ferry",
    color: "#5ee0c8",
    goal: "Quiet maintenance — ship v1.0.1 docs polish, monitor production.",
    activity: [
      { t: "12:42", k: "ok",   c: "POST /hook/discord → 200 · retry succeeded" },
      { t: "12:42", k: "warn", c: "discord webhook timeout, retry #2" },
      { t: "12:42", k: "ok",   c: "POST /hook/stripe → 200 (8ms)" },
      { t: "12:42", k: "ok",   c: "POST /hook/github → 200 (12ms)" },
    ],
    next: [
      "Polish docs site → publish v1.0.1",
      "Add structured logging to retry layer",
      "Open Homebrew formula PR",
    ],
  },
};

// ── Analytics ────────────────────────────────────────────────────────────
// Each tokensByDay / timeByDay array is 30 entries — last 30 days, oldest first.
// Numbers are in thousands of tokens; hours for time. Hand-tuned to feel real.
export const ANALYTICS = {
  tokensByDay: {
    echo:  [42,38,55,71,49,12,18,84,92,68,55,71,88,102,45,38,29,12,8,95,128,142,156,88,77,134,112,98,142,168],
    lumen: [22,28,35,18,42,8 ,12,38,42,55,68,72,88,95,52,38,42,28,18,68,72,84,92,78,68,55,82,98,112,124],
    drift: [12,8 ,15,22,18,5 ,8 ,32,28,42,55,62,38,28,22,12,8 ,18,42,68,72,85,52,38,28,42,55,38,28,42],
    atlas: [2 ,4 ,8 ,12,5 ,3 ,2 ,18,22,12,8 ,5 ,8 ,12,4 ,2 ,8 ,12,18,22,15,8 ,12,18,28,32,22,18,12,15],
    rune:  [18,22,8 ,12,28,4 ,2 ,32,38,42,28,18,22,38,52,42,12,8 ,42,55,68,72,52,42,38,28,32,28,38,42],
    ferry: [4 ,2 ,3 ,2 ,4 ,1 ,2 ,3 ,4 ,2 ,3 ,4 ,3 ,2 ,1 ,2 ,3 ,4 ,2 ,3 ,2 ,3 ,4 ,2 ,3 ,2 ,4 ,3 ,2 ,3],
  },
  timeByDay: {
    echo:  [1.2,2.4,3.1,4.2,2.8,0.5,0.8,5.2,6.4,4.8,3.6,4.2,5.8,7.1,3.4,2.2,1.8,0.4,0,5.4,7.2,8.1,6.8,4.2,3.8,7.4,5.6,4.8,7.1,7.8],
    lumen: [2.1,2.8,3.4,1.8,4.2,0.6,1.2,3.8,4.2,5.5,6.8,7.2,4.8,5.5,3.2,2.4,2.6,1.8,0.8,4.2,5.4,6.2,5.8,5.1,4.2,3.4,4.8,5.5,6.4,7.1],
    drift: [1.2,0.8,1.5,2.2,1.8,0.5,0.8,3.2,2.8,4.2,3.5,4.2,3.8,2.8,2.2,1.2,0.8,1.8,4.2,3.8,3.2,4.2,3.2,2.8,2.2,3.4,3.8,2.8,2.2,3.4],
    atlas: [0.2,0.4,0.8,1.2,0.5,0.3,0.2,1.8,2.2,1.2,0.8,0.5,0.8,1.2,0.4,0.2,0.8,1.2,1.8,2.2,1.5,0.8,1.2,1.8,2.4,2.8,2.2,1.8,1.2,1.5],
    rune:  [1.8,2.2,0.8,1.2,2.8,0.4,0.2,2.8,3.2,3.8,2.4,1.8,2.2,3.2,4.2,3.6,1.2,0.8,3.5,4.2,3.8,3.2,2.8,2.2,2.4,2.2,2.8,2.4,3.2,3.4],
    ferry: [0.4,0.2,0.3,0.2,0.4,0.1,0.2,0.3,0.4,0.2,0.3,0.4,0.3,0.2,0.1,0.2,0.3,0.4,0.2,0.3,0.2,0.3,0.4,0.2,0.3,0.2,0.4,0.3,0.2,0.3],
  },
  toolBreakdown: {
    echo: [
      { name: "Claude Sonnet 4.5", c: "#f5b343", tokens: 1840000, calls: 412 },
      { name: "Claude Haiku 4.5",  c: "#f5b343", tokens: 280000,  calls: 1842 },
      { name: "Whisper v3",         c: "#f5b343", tokens: 92000,   calls: 1843 },
      { name: "Voyage Embed",       c: "#f5b343", tokens: 168000,  calls: 5240 },
      { name: "Postgres",           c: "#5cc8ff", tokens: 0,       calls: 28412 },
      { name: "Stripe",             c: "#b794ff", tokens: 0,       calls: 412 },
    ],
    lumen: [
      { name: "Claude Haiku 4.5",  c: "#f5b343", tokens: 1240000, calls: 8420 },
      { name: "Claude Sonnet 4.5", c: "#f5b343", tokens: 540000,  calls: 184 },
      { name: "Postgres",           c: "#5cc8ff", tokens: 0,       calls: 142840 },
      { name: "Redis",              c: "#5cc8ff", tokens: 0,       calls: 41840 },
      { name: "GitHub",             c: "#b794ff", tokens: 0,       calls: 1240 },
    ],
    drift: [
      { name: "Claude Sonnet 4.5", c: "#f5b343", tokens: 380000,  calls: 84 },
      { name: "Resend",             c: "#b794ff", tokens: 0,       calls: 2412 },
      { name: "Postgres",           c: "#5cc8ff", tokens: 0,       calls: 8420 },
      { name: "GitHub",             c: "#b794ff", tokens: 0,       calls: 240 },
    ],
    atlas: [
      { name: "Claude Sonnet 4.5", c: "#f5b343", tokens: 124000,  calls: 38 },
      { name: "GitHub",             c: "#b794ff", tokens: 0,       calls: 412 },
      { name: "Slack",              c: "#b794ff", tokens: 0,       calls: 92 },
    ],
    rune: [
      { name: "Claude Vision",      c: "#f5b343", tokens: 820000,  calls: 412 },
      { name: "Claude Sonnet 4.5", c: "#f5b343", tokens: 240000,  calls: 84 },
      { name: "S3",                 c: "#5cc8ff", tokens: 0,       calls: 2412 },
    ],
    ferry: [
      { name: "Claude Haiku 4.5",  c: "#f5b343", tokens: 42000,   calls: 184 },
      { name: "Redis",              c: "#5cc8ff", tokens: 0,       calls: 18420 },
      { name: "Slack",              c: "#b794ff", tokens: 0,       calls: 412 },
      { name: "Resend",             c: "#b794ff", tokens: 0,       calls: 18 },
    ],
  },
  topActions: {
    echo: [
      { name: "Extract daily themes",       tool: "Claude Sonnet",   tokens: 542000, calls: 142 },
      { name: "Summarize voice entry",      tool: "Claude Sonnet",   tokens: 480000, calls: 1842 },
      { name: "Transcribe audio",           tool: "Whisper v3",       tokens: 92000,  calls: 1843 },
      { name: "Embed for semantic search",  tool: "Voyage Embed",     tokens: 168000, calls: 5240 },
      { name: "Title suggestion",            tool: "Claude Haiku",     tokens: 84000,  calls: 1842 },
      { name: "Onboarding copy A/B",        tool: "Claude Sonnet",   tokens: 28000,  calls: 12 },
    ],
    lumen: [
      { name: "Suggest dashboard widgets",  tool: "Claude Haiku",     tokens: 840000, calls: 6240 },
      { name: "SQL → natural language",     tool: "Claude Haiku",     tokens: 280000, calls: 2180 },
      { name: "RLS policy explanation",     tool: "Claude Sonnet",   tokens: 380000, calls: 84 },
      { name: "Schema diff narrative",      tool: "Claude Sonnet",   tokens: 124000, calls: 42 },
      { name: "Chart axis suggestions",      tool: "Claude Haiku",     tokens: 120000, calls: 412 },
    ],
    drift: [
      { name: "Hero copy A/B",              tool: "Claude Sonnet",   tokens: 184000, calls: 32 },
      { name: "OG image alt text",           tool: "Claude Sonnet",   tokens: 84000,  calls: 28 },
      { name: "Waitlist confirmation copy", tool: "Claude Sonnet",   tokens: 64000,  calls: 8 },
      { name: "Privacy page tone pass",      tool: "Claude Sonnet",   tokens: 48000,  calls: 4 },
    ],
    atlas: [
      { name: "Manifest review",             tool: "Claude Sonnet",   tokens: 64000,  calls: 12 },
      { name: "Cost optimization brief",    tool: "Claude Sonnet",   tokens: 38000,  calls: 8 },
      { name: "Runbook generation",          tool: "Claude Sonnet",   tokens: 22000,  calls: 18 },
    ],
    rune: [
      { name: "Rate font pairings",          tool: "Claude Vision",    tokens: 540000, calls: 240 },
      { name: "Describe specimen vibe",     tool: "Claude Vision",    tokens: 280000, calls: 172 },
      { name: "Weight pairing rationale",   tool: "Claude Sonnet",   tokens: 180000, calls: 64 },
      { name: "CSS export polish",          tool: "Claude Sonnet",   tokens: 60000,  calls: 20 },
    ],
    ferry: [
      { name: "Webhook signature explainer",tool: "Claude Haiku",     tokens: 22000,  calls: 84 },
      { name: "Retry policy advice",         tool: "Claude Haiku",     tokens: 14000,  calls: 62 },
      { name: "Error message rewrites",     tool: "Claude Haiku",     tokens: 6000,   calls: 38 },
    ],
  },
};

