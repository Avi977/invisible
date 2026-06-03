// Mock data — multiple sets, switchable from Tweaks
const DATA_SETS = {
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
const FOLDERS = {
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

// Per-terminal project context — surfaced via the collapsible header.
const TERM_CONTEXT = {
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
// ANALYTICS mock removed in INV-01 (REQ-05) — Analytics page now fetches
// GET /api/v1/analytics from the dashboard daemon. See
// lib/api/analytics.py and frontend/pages/analytics.jsx.

Object.assign(window, { DATA_SETS, FOLDERS, TERM_CONTEXT });

// ── Real-data fetchers (M1 wiring) ─────────────────────────────────
const API_BASE = "http://127.0.0.1:8765";

async function fetchProjects() {
  try {
    const response = await fetch(API_BASE + "/api/v1/projects", { credentials: "omit" });
    if (!response.ok) {
      throw new Error("HTTP " + response.status);
    }
    return await response.json();
  } catch (e) {
    throw new Error("fetchProjects: " + (e.message || "network error"));
  }
}

Object.assign(window, { fetchProjects });
