# Milestone M3 — draft (post-v1.0)

_Draft 2026-06-02. Subject to change based on real M1+M2 usage signals._

## Frame

At the end of M2, `invisible` is a **single-operator desktop app**: signed
Windows + macOS installer, 8 pages reading real local + GitHub + VPS data,
Codex+Claude orchestrator wired end-to-end, AI bubble in every page, first-
run wizard. Shippable to a small alpha audience (you + a handful of trusted
devs).

M3 is the **moat-builder + scale phase**. Three plausible directions, pick
1-2 to commit to. They are explicitly *plausible*, not locked.

---

## Direction A — Distribution & community (8-12 weeks)

Optimised for: turning the alpha into something other people genuinely use,
without yet investing in multi-user backend.

| WS | Owns | Why |
|---|---|---|
| **website** | `theprofitplatform.com.au/invisible` landing page, demo video, docs site (mdBook or Astro) | Without docs, users can't onboard |
| **plugin-api** | `lib/plugins/` directory + manifest schema; `bin/invisible-plugin` CLI; first 3 example plugins (Anthropic web search tool, GitHub issue helper, Notion sync) | Lets the community extend without forking |
| **telemetry-and-feedback** | Optional anonymous usage telemetry (Plausible-style, no PII); in-app feedback widget that opens a GitHub issue; crash reporting via Sentry (self-hosted on srv982719) | Without these you're flying blind |
| **release-cadence** | Automated weekly nightlies, monthly stable; auto-update with rollback; the changelog auto-generator already in place feeds this | Without cadence, alpha → abandoned |
| **observability** | Dashboards on `srv982719` for: token spend per user/day, orchestrator success rate, page load p95, daemon uptime | Without these you can't reason about whether to invest more |
| **community** | Discord (or just GitHub Discussions), public issue triage rotation, contributor guide | Without community, plugins won't happen |

**Exit:** v1.1-v1.4 cadence; 50+ active users; 10+ community plugins; a real
docs site at a real URL; a feedback loop that surfaces the next big bet.

---

## Direction B — Team mode (12-16 weeks)

Optimised for: turning the personal cockpit into something a 3-10 person dev
team actually uses together. Requires backend investment.

| WS | Owns | Why |
|---|---|---|
| **multi-user-auth** | Replace the single bearer-token model with per-user OAuth (GitHub OAuth, or a hosted Auth0/Clerk); add user IDs to every Notion review row | Foundation for everything else in this direction |
| **shared-projects** | Project rows in Notion become team-scoped; orchestrator runs are attributed to the user who started them; cross-team `invisible-status` view | The headline team feature |
| **conflict-aware-orchestrator** | Two devs running orchestrator on the same project — branch handoff, rebase coordination, "Bob is in iter 3/5 on this; want to take over?" | Without this, two devs trip each other immediately |
| **shared-secrets** | Infisical already has per-user roles; expose those in `bin/invisible-doctor` and the first-run wizard; document the team Infisical project setup | Without this, the secret-zero problem reappears |
| **shared-chat** | The AI bubble's session history syncs across team members for the same project; @mentions trigger Telegram pings | Replaces the team Slack channel for ops-y questions |
| **billing** | Token spend dashboards per user + per team; soft caps + alerts | Without this, the bill is a surprise once a quarter |

**Exit:** v2.0 with team-mode flag in the first-run wizard; 3+ teams (5-10
devs each) running it; orchestrator coordination works across team members
without manual handoff.

---

## Direction C — Orchestrator-as-platform (10-14 weeks)

Optimised for: making the codex↔claude loop the most capable agentic IDE on
the market. Less about reach, more about depth.

| WS | Owns | Why |
|---|---|---|
| **llm-provider-abstraction** | Generic `LLMClient` trait/interface; Codex + Claude become two implementations; add Gemini + Grok + local-Llama variants behind it | Hedge against any single provider; let users pick per-task |
| **task-decomposition-agent** | A new agent in the loop: instead of "one task → one loop run", a Decomposer breaks vague tasks into sub-tasks each handled by the orchestrator. Tree-of-tasks UI on the Focus page | The biggest UX win for "I have a fuzzy goal, just figure it out" |
| **eval-harness** | Track per-agent, per-task-type success rates over time. Auto-pick the best agent for a task class based on historical data | "Use Claude for code review, Codex for new code, GPT-5 for refactors" emerges from data |
| **plan-then-execute** | Before any run, a Planner produces a written PLAN.md (we already have this for GSD); the orchestrator follows + adapts. Currently the orchestrator just "does"; this adds the gate. | Higher quality output, less revert pressure |
| **streaming-codex-output** | Currently each codex turn is atomic stdout-only. Stream the output, render it live in the page, let user interject mid-turn | Removes the "stare at logs" friction |
| **memory-across-runs** | Persistent project memory: insights from past runs (decisions, gotchas, dead-ends) auto-feed into future run context. Lives next to the existing checkpoint store. | Compound learning across runs |

**Exit:** v2.0 where users describe what they want in 2 sentences and the
orchestrator handles the rest, ~80% of the time. The 20% that needs human
intervention happens with full context.

---

## Decision criteria

Pick A if: you want this to become a thing other people use, and you're OK
with being the docs-and-community-and-feedback owner for 2-3 months.

Pick B if: you have a specific team in mind that would adopt this (yours,
maybe another small studio), and you're willing to invest in the auth/billing
infra that team-mode demands.

Pick C if: you want the most technically interesting v2.0 possible, and you
don't mind that adoption stays small until the platform itself is strong
enough to demand attention.

**Plausible hybrid:** A + a stripped-down C. Build the plugin API (A) AND
the LLM provider abstraction (C) — they share infrastructure (both need a
generic-interface-and-registry pattern) and together make `invisible`
extensible from both directions. Skip the website + community stuff in A
for now; skip the deeper eval-harness work in C. ~10 weeks combined.

---

## What's NOT in M3

- **Mobile app.** Already excluded in PROJECT.md. Stays excluded.
- **SaaS hosting.** Even in Direction B, `invisible` stays self-hosted. Hosting it for users adds support burden you don't want.
- **Replacing the orchestrator core.** The Codex+Claude loop is the moat. Don't rewrite it in M3.
- **Enterprise.** No SSO, no SOC2, no on-prem licensing until Direction B exits and you have signal that enterprises actually want it.

---

## How to commit

This is a draft. To commit to it:

1. Pick a direction (or the A+C hybrid) after at least 4 weeks of M2 in real use.
2. Split the chosen direction's 6 workstreams into the same parallel-session pattern M1+M2 used.
3. Same conflict-minimisation rules (modular `lib/` boundaries, additive-only edits to shared files).
4. Same docs discipline (`.planning/workstreams/<name>/ROADMAP.md` + per-phase CONTEXT/PLAN/SUMMARY/VERIFICATION).
5. Same human-merge gate.

If after 4 weeks you find a direction not listed here, that's fine. Update this draft, don't force a fit.
