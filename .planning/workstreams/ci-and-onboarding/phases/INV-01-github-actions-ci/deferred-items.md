# Deferred Items — INV-01-github-actions-ci

Out-of-scope discoveries logged during execution. NOT fixed in this phase.

## From plan 01-02 (Task 1 — CI green verification)

- **Node.js 20 action runtime deprecation.** `actions/checkout@v4` and
  `actions/setup-python@v5` run on Node.js 20, which GitHub deprecates: forced to
  Node 24 by default starting **2026-06-16**, removed from runners **2026-09-16**.
  Surfaced as a non-blocking annotation on every `ci.yml` run (jobs still pass).
  - **Why deferred:** these are warnings, not failures; all three jobs concluded
    `success`. Major-tag action pinning is this phase's agreed security bar (D-01),
    and resolving the warning means editing the action pins / adding
    `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` — an action-hardening task outside
    plan 01-02's documented scope.
  - **Suggested fix (future):** bump `actions/checkout` and `actions/setup-python`
    to Node-24-compatible major versions before 2026-06-16, or set
    `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` on the runner / in the workflow.
  - Ref: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/
