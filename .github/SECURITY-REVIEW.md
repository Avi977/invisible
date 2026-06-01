# Security Review — `anthropics/claude-code-security-review`

Future-reference context for this repo's PR security gate. Read this when you encounter:
- A failing `Security Review` check on a PR
- A request to bump the action's pinned SHA
- A question about Claude API spend on PRs
- A new contributor / new session needing to set up auth
- A request to change which directories are scanned, which model is used, or what counts as a "finding"

The actual workflow lives at [`.github/workflows/security-review.yml`](workflows/security-review.yml).

---

## What this is

Anthropic's open-source Action ([anthropics/claude-code-security-review](https://github.com/anthropics/claude-code-security-review), MIT, 4.8k stars at install time). Runs Claude on every PR diff into `main` and posts findings as PR comments. Semantic analysis, not pattern matching.

**Covers (per upstream README):**
Injection (SQL, command, LDAP, NoSQL, XXE) · auth/RBAC flaws (privilege escalation, broken auth, IDOR) · data exposure (hardcoded secrets, PII logging) · crypto issues (weak algorithms, key management) · input validation · business-logic flaws (race conditions, TOCTOU) · code execution (RCE, deserialization) · XSS.

Built-in false-positive filter skips DoS-class noise (rate limiting, memory exhaustion). Override via the `false-positive-filtering-instructions` input.

## Setup sequence (each step is REQUIRED — half-set-up is worse than nothing)

### 1. Workflow file lands on `main`

Done by the PR that introduced this doc — workflow at `.github/workflows/security-review.yml`. Triggers on `pull_request:` into `main` + `workflow_dispatch:` for manual reruns.

### 2. `CLAUDE_API_KEY` repo secret

```bash
gh secret set CLAUDE_API_KEY --body "$ANTHROPIC_API_KEY" --repo Avi977/invisible
```

Or: Settings → Secrets and variables → Actions → New repository secret.

**Without this, every run fails loudly** at the `Run claude-code-security-review` step. That's by design — no silent skips.

### 3. First successful workflow run

GitHub registers the check name `Claude security review` (the job's `name:` field) only after the workflow has *completed* at least once. Without a successful run, step 4 can't add it as a required check (it's not in the dropdown / API yet).

To trigger: either push any commit to an open PR, or:
```bash
gh workflow run security-review.yml --repo Avi977/invisible --ref main
```

### 4. Branch protection — make it a hard gate

```bash
gh api repos/Avi977/invisible/branches/main/protection \
  --method PUT \
  -f required_status_checks[strict]=true \
  -f required_status_checks[contexts][]="Claude security review" \
  -F enforce_admins=false \
  -f required_pull_request_reviews=null \
  -f restrictions=null
```

`strict=true` means PR branches must be up-to-date with `main` before merge. Drop to `false` if you find that annoying for the multi-workstream merge dance.

`enforce_admins=false` lets you (the repo owner) emergency-merge without the check — flip to `true` if you want hard enforcement on yourself too.

## Configuration in this repo

Pinned action SHA, exclude list, timeouts, concurrency — all in [`security-review.yml`](workflows/security-review.yml). Key choices and why:

| Setting | Value | Why |
|---|---|---|
| `uses` | `@0c6a49f1fa56a1d472575da86a94dbc1edb78eda` | Pinned to commit SHA (2026-02-11). Bump intentionally after reviewing upstream diffs — `@main` would let upstream silently change what runs in our pipeline. See [GitHub Actions hardening](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions#using-third-party-actions). |
| `comment-pr` | `true` | Findings show up inline on the PR conversation, not just in logs. |
| `upload-results` | `true` | JSON artifact persists for audit / batch reprocessing. |
| `exclude-directories` | `.planning,frontend-vite/node_modules,src-tauri/target` | Skip planning markdown + vendored deps + Rust build artifacts. Big spend-saver. |
| `claudecode-timeout` | (default, 20 min) | Tune up for very large PRs; tune down to fail fast on stuck runs. |
| Job `timeout-minutes` | 30 | Outer cap above the action's own timeout. |
| `concurrency.cancel-in-progress` | `true` | New commits cancel stale runs. Saves Claude API spend on rapid pushes. |
| Default model | `claude-opus-4-1-20250805` (upstream default) | Drop to `claude-sonnet-4-6` via the `claude-model` input for ~10× cheaper runs at minor accuracy cost. |

## Cost notes

Each PR run consumes Anthropic API credits.

- Default model (Opus 4.1): ~$0.50–$2.00 per typical PR, scales with diff size
- Sonnet 4.6 alternative: ~$0.05–$0.20 per run
- Concurrency-cancel cuts spend on rapid commit pushes
- Excluding `.planning/` saves significantly — planning markdown otherwise gets reviewed as code

If spend matters, switch to Sonnet via:
```yaml
- uses: anthropics/claude-code-security-review@0c6a49f1fa56a1d472575da86a94dbc1edb78eda
  with:
    claude-api-key: ${{ secrets.CLAUDE_API_KEY }}
    claude-model: claude-sonnet-4-6
    comment-pr: true
```

## Known operational concerns

### The action is third-party-trusted

It needs:
- `pull-requests: write` (post comments)
- `contents: read` (read the diff)
- `issues: write` (some configurations post a summary issue)
- The Claude API key (sent to Anthropic's servers — your diff *will* leave the repo)

**Implication for sensitive diffs:** if a PR contains content you don't want to leave the GitHub/Anthropic boundary (e.g., embedded secrets, customer data in fixtures), the action sees and ships it. Use `exclude-directories` to keep those paths out, or skip the action via `[skip ci]` on the commit (defeats the gate — only for genuine emergencies).

### Action is pinned, not auto-updating

The SHA pin means GitHub Dependabot won't auto-bump it. Periodic manual bump: review the diff between the pinned SHA and `main` on upstream, then commit a new SHA in a PR. See [Dependabot's `github-actions` ecosystem](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file#package-ecosystem) for automating this with `dependabot.yml` if desired.

### Branch-protection rule is brittle to job rename

If anyone renames the job (currently `name: Claude security review` in the workflow), the branch protection rule keeps requiring the old name and silently lets PRs through without it. To detect:
```bash
gh api repos/Avi977/invisible/branches/main/protection/required_status_checks --jq '.contexts'
```
should match the current `name:` in the workflow YAML.

### Cross-workstream daemon contention (separate issue)

Documented in `.planning/workstreams/ai-bubble/phases/INV-01-api-v1-chat-end-to-end/FOLLOWUPS.md §5`. Not related to this action but worth knowing about for browser-level UAT.

## Failure modes — what to do when

| Symptom | Likely cause | Fix |
|---|---|---|
| Workflow step `Run claude-code-security-review` errors with auth-related message | `CLAUDE_API_KEY` secret missing or invalid | Set / rotate via `gh secret set CLAUDE_API_KEY ...` |
| Workflow runs but no PR comment | `comment-pr` set to `false`, or workflow permissions missing `pull-requests: write` | Check workflow YAML inputs + `permissions:` block |
| Action takes >20 min and fails on timeout | Very large PR; default `claudecode-timeout: 20` exceeded | Increase `claudecode-timeout: 30` (or higher) in workflow inputs; also bump job `timeout-minutes` above it |
| False positives swamping real findings | Default FP filter not catching your noise | Write `.github/security-review/false-positive-rules.md` and pass via `false-positive-filtering-instructions: .github/security-review/false-positive-rules.md` |
| PRs merge without the check appearing | (a) Workflow file not on `main`, or (b) Branch protection not configured / wrong job name | Check `.github/workflows/security-review.yml` on `main`, then `gh api repos/Avi977/invisible/branches/main/protection` for the contexts list |

## Repo-specific history

- **Introduced:** PR #3 (`chore/add-security-review-action`), 2026-05-27
- **First successful run:** *(record the run id + date here after step 3 above completes)*
- **Branch protection enabled:** *(record date here after step 4)*
- **Workstreams merged without this check:** PRs #1 (ai-bubble), #2 (folders-3source), #4 (tauri-shell), #5 (terminals-pty), #6 (dashboard-wiring) — all of M1's parallel workstreams shipped before the check was on `main`. Retroactive scan can be done by re-running the action against each merge commit via `workflow_dispatch` if desired.

## When to consider replacing or adding to this

`claude-code-security-review` is broad-coverage semantic analysis. It is **not**:
- A SAST tool (use CodeQL — free for public repos, complementary)
- A dependency scanner (use Dependabot / GitHub native)
- A secret scanner (use GitHub secret scanning — free for public repos, already on by default)
- A SBOM generator (use `actions/dependency-review-action`)
- An AI-provenance signer (consider [P-r-e-m-i-u-m/ai-change-passport](https://github.com/P-r-e-m-i-u-m/ai-change-passport) once it matures past v0)

A mature pipeline runs several of these in parallel. Don't expect this one action to cover everything.
