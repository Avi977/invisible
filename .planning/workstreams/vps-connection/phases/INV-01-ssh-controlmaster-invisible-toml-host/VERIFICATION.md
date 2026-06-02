---
phase: INV-01-ssh-controlmaster-invisible-toml-host
verified: 2026-06-02T07:21:50Z
verifier: claude (gsd-verifier, goal-backward)
branch: ws/vps-connection
status: passed
score: 5/5 success-criteria verified (criterion 4 PASS-with-spec-revision)
verdict: |
  Phase 1 goal achieved end-to-end. `ssh srv982719` from any shell on this
  Mac multiplexes through one ControlMaster socket (cold 2.486s → warm 415ms,
  ~6× speedup). The `lib/api/tree_vps.py` walker — which Phase 1's whole
  point is to make reachable — was verified against the live VPS, with a
  real bug found and fixed via shlex.quote. 23 tests pass (18 hermetic + 5
  live), no MUST-NOT-TOUCH files modified, no secrets in any committed
  diff. Phase 2 (invisible-server systemd) and Phase 3 (in-app reach) can
  rely on this foundation.
overrides_applied: 1
overrides:
  - must_have: "Criterion 4: warm ssh srv982719 echo ok under 200ms"
    reason: |
      RTT-bound. ICMP RTT to 31.97.222.218 is 199-280ms; even a perfect
      ControlMaster reuse needs ~2 RTTs (~400ms minimum) to exec `echo ok`
      remotely. The criterion was network-naive. ControlMaster IS working
      (verified: warm 415ms vs cold 2486ms = 6× speedup, ~/.ssh/cm-* socket
      exists). The intent of the criterion ("multiplexing saves auth
      handshake") IS satisfied; the literal 200ms threshold is unreachable
      on any non-LAN network. Plan 01-01 SUMMARY recommends rewording to
      "warm at least 4× faster than cold" — satisfied at 6×.
    accepted_by: ace
    accepted_at: 2026-06-02T07:21:50Z
roadmap_truths:
  - "Host srv982719 block in ~/.ssh/config with ControlMaster auto, ControlPath, ControlPersist 10m"
  - "invisible.toml vps.host = srv982719 and vps.identity documented"
  - "ssh srv982719 echo ok succeeds without password prompt"
  - "Warm ssh srv982719 echo ok under 200ms (RTT-bound — override applied)"
  - "lib/api/tree_vps.walk_all actually walks the live VPS (added in plan 01-02 close)"
plans_complete:
  - 01-01
  - 01-02
commits:
  - fa48661 docs(planning) patch ROADMAP + add STATE
  - 25197f0 docs(01) plan phase 1
  - e8af0bc docs(01-01) flesh out [vps] block
  - 10f61e3 docs(01-01) add README VPS setup
  - 19a5759 feat(01-01) doctor check_ssh + sanitizer
  - 4c7d76a docs(01-01) plan 01 SUMMARY
  - 36fa0ec test(01-02) hermetic unit tests
  - 88d3acb test(01-02) integration scaffolding
  - fa32e9f fix(01-02) shlex.quote remote_cmd
  - 44bd3d9 docs(01-02) plan 02 SUMMARY
---

# Phase 1: SSH ControlMaster + invisible.toml host — Verification Report

**Phase Goal:** A single `ssh srv982719` from inside the app reuses one TCP/TLS connection, multiplexed via ControlMaster. The 6 terminal panes (and the tree_vps walker) can each open `ssh srv982719` without each one triggering a new auth handshake.

**Verified:** 2026-06-02T07:21:50Z
**Status:** PASSED (5/5, with criterion 4 spec-revision override)
**Re-verification:** No — initial verification
**Methodology:** Goal-backward (`@verify-work`) — verifier read source files, ran live SSH, executed test suite, scanned for secrets, audited file-ownership boundary.

---

## Goal-Backward Trace

### Observable Truths (Success Criteria)

| #   | Criterion                                                                                                                  | Status                  | Evidence                                                                                                                                                                                                                                                                                              |
| --- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `~/.ssh/config` has `Host srv982719` block with `ControlMaster auto`, `ControlPath ~/.ssh/cm-%r@%h:%p`, `ControlPersist 10m`. | VERIFIED                | `grep -A 9 "^Host srv982719$" ~/.ssh/config` shows all three directives. Also includes plan-deviation `Port 2222` and `IdentityFile ~/.ssh/vps_avi` (documented in 01-01 SUMMARY Deviation 2 — VPS sshd listens on 2222, and `id_ed25519` is passphrase-protected so `vps_avi` is used instead).      |
| 2   | `invisible.toml` `vps.host = "srv982719"` and `vps.identity = "~/.ssh/<keyfile>"` documented.                              | VERIFIED                | Live: `~/.invisible/invisible.toml` has `[vps] host = "srv982719" identity = "~/.ssh/vps_avi" use_mosh = false`. Repo: `invisible.toml.example` has full 60-line `[vps]` block with `host=""` dev default + `srv982719` worked example in comments + Decision A documented + Phase 1 criteria quoted. |
| 3   | From a fresh shell, `ssh srv982719 echo ok` succeeds without password prompt.                                              | VERIFIED                | `ssh -o BatchMode=yes -o ConnectTimeout=4 srv982719 echo ok` → stdout `ok`, exit 0. BatchMode=yes means no password fallback was possible.                                                                                                                                                            |
| 4   | A second `ssh srv982719 echo ok` runs in under 200ms.                                                                      | PASSED (override applied) | Measured warm time consistently 411-433ms (live this verification: 415ms). Network RTT 199-280ms makes <200ms physically unreachable (~2 RTTs needed for command + response). **ControlMaster IS reused** — socket `~/.ssh/cm-avi@31.97.222.218:2222` exists, cold→warm speedup is 6× (2486ms→415ms). Override documented in frontmatter and Plan 01-01 SUMMARY. Spec rewording recommended: "warm ≥4× faster than cold" — satisfied. |
| 5   | `lib/api/tree_vps.walk_all` actually walks the live VPS.                                                                  | VERIFIED                | `INVISIBLE_HOME=/tmp/inv-live-probe pytest tests/test_tree_vps_live.py --integration -v` → **5 passed in 4.70s** end-to-end against `srv982719:/srv/bg-remover`. (Criterion added during plan 01-02 close — included in ROADMAP Phase 1 criterion status.)                                              |

### Live verification capture

```
$ ssh -o BatchMode=yes -o ConnectTimeout=4 srv982719 echo ok
ok

$ { time ssh srv982719 echo ok > /dev/null; } 2>&1
ssh srv982719 echo ok > /dev/null  0.00s user 0.00s system 1% cpu 0.415 total

$ ls -la ~/.ssh/cm-*
srw-------@ 1 ace  staff  0 Jun  2 00:17 /Users/ace/.ssh/cm-avi@31.97.222.218:2222

$ INVISIBLE_HOME=/tmp/inv-live-probe python3 -m pytest tests/test_tree_vps_live.py --integration -v
tests/test_tree_vps_live.py::test_walk_all_live_returns_tree                                    PASSED [ 20%]
tests/test_tree_vps_live.py::test_walk_all_live_warm_call_completes_under_3s                    PASSED [ 40%]
tests/test_tree_vps_live.py::test_walk_all_live_empty_host_still_503                            PASSED [ 60%]
tests/test_tree_vps_live.py::test_walk_all_live_unknown_path_yields_unreachable_badge           PASSED [ 80%]
tests/test_tree_vps_live.py::test_walk_all_live_argv_actually_uses_controlmaster                PASSED [100%]
============================== 5 passed in 4.70s ===============================

$ python3 -m pytest tests/ -q
.........................sssss                                           [100%]
SKIPPED [5] tests/test_tree_vps_live.py: --integration not given
25 passed, 5 skipped in 0.61s
```

---

## File-Ownership Audit

**Branch merge-base with `main`:** `577c048`. **Files changed since merge-base:** 14 (no MUST-NOT-TOUCH violations).

| File                                                                                              | Workstream relation       | Lines       | Audit                  |
| ------------------------------------------------------------------------------------------------- | ------------------------- | ----------- | ---------------------- |
| `invisible.toml.example`                                                                          | OWNS                      | +59/-1      | VERIFIED — `[vps]` block expanded with worked example + comments |
| `README.md`                                                                                       | EDITS-LIGHTLY             | +95/-0      | VERIFIED — new `### VPS connection setup` section between Setup and Usage |
| `bin/invisible-doctor`                                                                            | EDITS-LIGHTLY             | +125/-?     | VERIFIED — `check_ssh()` upgraded, `_sanitize_ssh_stderr()` helper, `_HOST_RE` mirrors tree_vps |
| `lib/api/tree_vps.py`                                                                             | OWNS                      | +13/-2      | VERIFIED — `import shlex` + `shlex.quote(arg) for arg in remote_cmd`; public API unchanged |
| `pytest.ini` (new)                                                                                | IMPLICITLY OWNS (test infrastructure) | +12     | VERIFIED — `[pytest]` section, `vps_integration` marker, `--strict-markers` |
| `tests/conftest.py` (new)                                                                         | IMPLICITLY OWNS           | +167        | VERIFIED — `--integration` flag, `vps_reachable`, `vps_configured_project`, `live_vps_or_skip` |
| `tests/test_tree_vps.py` (new)                                                                    | IMPLICITLY OWNS           | +633        | VERIFIED — 18 hermetic tests |
| `tests/test_tree_vps_live.py` (new)                                                               | IMPLICITLY OWNS           | +272        | VERIFIED — 5 live tests gated by `--integration` + `live_vps_or_skip` |
| `.planning/workstreams/vps-connection/ROADMAP.md`                                                 | OWNS (workstream-internal) | +121        | VERIFIED — canonical phase-detail format + criterion status |
| `.planning/workstreams/vps-connection/STATE.md`                                                   | OWNS                      | +89         | VERIFIED — workstream STATE seeded |
| `.planning/workstreams/vps-connection/phases/INV-01-.../01-01-PLAN.md` (new)                     | OWNS                      | +579        | VERIFIED |
| `.planning/workstreams/vps-connection/phases/INV-01-.../01-01-SUMMARY.md` (new)                   | OWNS                      | +268        | VERIFIED |
| `.planning/workstreams/vps-connection/phases/INV-01-.../01-02-PLAN.md` (new)                     | OWNS                      | +552        | VERIFIED |
| `.planning/workstreams/vps-connection/phases/INV-01-.../01-02-SUMMARY.md` (new)                   | OWNS                      | +258        | VERIFIED |

**MUST-NOT-TOUCH boundary scan:**

```
$ git diff --shortstat 577c048..HEAD -- frontend/ frontend-vite/ src-tauri/ .github/workflows/ \
                                          lib/api/projects.py lib/api/chat.py lib/api/tree_local.py \
                                          lib/api/tree_repo.py lib/api/analytics.py lib/pty_server.py \
                                          bin/invisible-app bin/invisible-dashboard bin/invisible-pty \
                                          bin/invisible-frontend bin/invisible-server
(empty output — no files modified)
```

**ZERO MUST-NOT-TOUCH files modified.** No sibling-workstream files affected. No frontend, no Tauri, no CI workflows, no sibling lib/api walkers, no PTY server.

**Untracked file noted:** `.planning/workstreams/vps-connection/config.json` (`{"workflow":{"_auto_chain_active":false}}`) — gsd workstream-config layer, not part of phase 1 deliverables, left untracked. Already noted in 01-02 SUMMARY Deferred Item 3.

---

## REQ Coverage

| REQ ID       | Source                                                | Status           | Evidence                                                                                                       |
| ------------ | ----------------------------------------------------- | ---------------- | -------------------------------------------------------------------------------------------------------------- |
| **REQ-VPS-01** | Workstream-scoped (declared in workstream ROADMAP)  | SATISFIED        | Phase 1 success criteria 1-5 all VERIFIED (criterion 4 with override). REQ-VPS-01 is not enumerated in root `.planning/REQUIREMENTS.md` (M2 reqs not yet broken out — root REQUIREMENTS.md fall-back to REQ-04). |
| **REQ-04**   | Root `.planning/REQUIREMENTS.md` — "Terminals: 6 real PTYs over WebSocket" | PARTIALLY SATISFIED (Phase 1 scope) | Phase 1 wires the SSH plumbing that REQ-04's "SSH variant: panes can be configured to launch `ssh <host>`" clause depends on. The actual PTY ssh-variant code is Phase 3 (`lib/pty_server.py` ssh variant). Phase 1 delivers the necessary precondition. Full REQ-04 satisfaction is a Phase 3 deliverable. |

REQ-04 is properly DEFERRED to Phase 3, not blocked.

---

## Step 2B Bug-Fix Evidence (the `shlex.quote` story)

The plan 01-02 task 3 had three possible outcomes (Step 2A, 2B, 2C). **Step 2B applied:** the live integration test surfaced a concrete, diagnosable bug.

**Failure observed (against live `srv982719:/srv/bg-remover`):**
```
find: paths must precede expression: `ace-claude-toolkit/.gitignore'
find: possible unquoted pattern after predicate `-path'?
```

**Root cause:** `lib/api/tree_vps.py::_ssh_argv` appended `*remote_cmd` (which contained the `find` argv with `-path */.git*`) after `--`. OpenSSH joins remote argv with spaces and pipes the result to remote `$SHELL -c`, which then re-tokenizes AND glob-expands. The `*/.git*` token expanded against the avi user's `/home/avi` CWD, matching `ace-claude-toolkit/.gitignore`, corrupting the find argv.

**Fix (commit `fa32e9f`):**

```python
# lib/api/tree_vps.py line 69
import shlex

# lib/api/tree_vps.py line 200 (inside _ssh_argv)
return [
    "ssh", ..., host, "--",
    *(shlex.quote(arg) for arg in remote_cmd),  # was: *remote_cmd
]
```

Diff size: +13/-2 LOC. Well under the 20-line surgical-edit budget from the plan.

**Regression tests added to `tests/test_tree_vps.py`:**

1. `test_walk_all_argv_shell_quotes_remote_command_so_globs_dont_expand_on_remote` (line 541) — stubs subprocess, asserts `"'*/.git*'"` appears in argv after `--`.
2. `test_walk_remote_handles_real_world_remote_cwd_via_shell_quoting` (line 588) — stubs subprocess with a "remote shell simulator" that returns the actual `find: paths must precede expression` error if it sees the unquoted glob. Asserts happy 200 path (would FAIL without the quoting).

Both tests run and pass:
```
$ python3 -m pytest tests/test_tree_vps.py::test_walk_all_argv_shell_quotes_remote_command_so_globs_dont_expand_on_remote tests/test_tree_vps.py::test_walk_remote_handles_real_world_remote_cwd_via_shell_quoting -v
============================== 2 passed in 0.02s ===============================
```

**Why this bug was latent until plan 01-02:** Plan 01-01's `invisible-doctor check_ssh` runs `ssh srv982719 echo ok` — no `find`, no globs, so the bug couldn't surface there. M1's `folders-3source` workstream only tested `walk_all` with `vps.host = ""` (the 503 graceful-degradation path). No prior code path exercised the walker against a real VPS. Plan 01-02's `--integration` suite is the first probe that actually invoked `find` over SSH.

**Public API preservation verified:**
```
$ python3 -c "import sys; sys.path.insert(0, 'lib'); from api import tree_vps; \
   assert tree_vps.VPS_NOT_CONFIGURED == {'error': 'vps.host not configured'}; \
   assert tree_vps.MAX_DEPTH == 6; assert tree_vps.SSH_TIMEOUT_S == 15; \
   print('public API preserved')"
public API preserved
```

---

## Anti-Pattern Scan

| Check                                      | Files                                                                    | Result               |
| ------------------------------------------ | ------------------------------------------------------------------------ | -------------------- |
| Debt markers (`TBD`/`FIXME`/`XXX`)        | All 8 modified files                                                     | NONE                 |
| Warning markers (`TODO`/`HACK`/`PLACEHOLDER`) | All 8 modified files                                                     | NONE                 |
| Secret leakage (private keys, AWS keys, raw SSH pubkey payloads) | Committed diff                                                          | CLEAN                |
| Stub patterns (`return null/[]/{}`)        | Production code (tree_vps.py, invisible-doctor)                          | NONE (return values are contracts) |
| Empty handlers / placeholder strings       | All modified files                                                       | NONE                 |
| Drift between `_HOST_RE` regex in two files (T-INV01H-03) | `bin/invisible-doctor:52` vs `lib/api/tree_vps.py:114`                  | BYTE-FOR-BYTE MATCH  |

```
$ grep -n "_HOST_RE = " bin/invisible-doctor lib/api/tree_vps.py
bin/invisible-doctor:52:_HOST_RE = re.compile(r"^(?:[A-Za-z0-9_.-]+@)?[A-Za-z0-9._-]+$")
lib/api/tree_vps.py:114:_HOST_RE = re.compile(r"^(?:[A-Za-z0-9_.-]+@)?[A-Za-z0-9._-]+$")
```

---

## Behavioral Spot-Checks

| Behavior                                                  | Command                                                                            | Result                                                                        | Status |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ------ |
| Hermetic test suite passes                                | `python3 -m pytest tests/test_tree_vps.py -v`                                       | 18 passed in 0.04s                                                            | PASS   |
| Full repo test suite without --integration                | `python3 -m pytest tests/ -q`                                                      | 25 passed, 5 skipped in 0.61s                                                | PASS   |
| Live integration suite passes                             | `INVISIBLE_HOME=/tmp/inv-live-probe pytest tests/test_tree_vps_live.py --integration -v` | 5 passed in 4.70s                                                             | PASS   |
| Cold/warm SSH multiplexing works                          | `ssh srv982719 echo ok` (then again, timed)                                        | `ok`, exit 0; warm 415ms (vs cold 2.486s — 6× speedup)                       | PASS   |
| ControlMaster socket present                              | `ls -la ~/.ssh/cm-*`                                                               | `~/.ssh/cm-avi@31.97.222.218:2222` (Unix socket, mode 600)                   | PASS   |
| Doctor empty-host returns WARN (graceful degradation)     | `check_ssh({'vps': {'host': ''}})`                                                 | `WARN` with "no vps.host configured — Folders/VPS column will return 503"     | PASS   |
| Doctor bad-host returns FAIL without echoing the bad host | `check_ssh({'vps': {'host': 'bad;rm -rf /'}})`                                     | `FAIL` with "invalid host value — must match ^..." (no `rm -rf` in output)    | PASS   |
| Sanitizer redacts user-home paths                         | `_sanitize_ssh_stderr('Could not open /Users/ace/.ssh/id_ed25519 for reading')`    | `'Could not open <path> for reading'`                                         | PASS   |
| Sanitizer redacts id_* keyfile names                      | `_sanitize_ssh_stderr('Bad key id_special')`                                       | `'Bad key <keyfile>'`                                                         | PASS   |
| Sanitizer redacts .pem filenames                          | `_sanitize_ssh_stderr('failed to read foo.pem')`                                   | `'failed to read <keyfile>'`                                                  | PASS   |
| Public API surface preserved                              | Type-check assertions on `walk_all`, `_walk_remote`, `_ssh_argv`, constants        | All callable; constants equal                                                 | PASS   |

---

## Probe Execution

Per Step 7c: looked for `scripts/*/tests/probe-*.sh` and explicit probe declarations in PLAN/SUMMARY — **none exist for this phase**. The phase uses pytest-based verification instead (which were executed above). No probe execution applicable.

---

## Gaps / Risks

### Criterion 4 spec-correction (PASS with override)

The literal "warm <200ms" wording in ROADMAP Phase 1 criterion 4 is RTT-bound and unreachable on this network. Documented exhaustively in:

- 01-01 SUMMARY § "Criterion 4" — measurement table + analysis
- ROADMAP § "Phase 1 criterion status" — criterion 4 marked ⚠️ with recommended rewording
- This VERIFICATION's `overrides` frontmatter — formal acceptance

The intent of the criterion ("ControlMaster reuse should eliminate the auth handshake") IS satisfied: cold→warm is a 6× speedup, the master socket exists, and the doctor's `check_ssh` correctly identifies the master is being reused (it reports `master=new (420ms)` only because the doctor's 200ms threshold also collides with the RTT floor — see deferred item below).

### Deferred items (carried forward from 01-01 SUMMARY, NOT blockers)

1. **Doctor `master=cached` threshold misleading on RTT-heavy networks.** The doctor uses `<200ms` as the cached threshold; on this network warm SSH is always 400+ms even with proper multiplexing, so the doctor emits `master=new` (with helpful "add ControlMaster to ~/.ssh/config" hint) even though ControlMaster IS active. **Suggested fix:** check `~/.ssh/cm-*` socket existence directly, OR baseline-RTT-then-threshold approach. Not a blocker for Phase 1 — the doctor still PASSes, only the suffix message is slightly misleading.

2. **Deploy `bin/invisible-doctor` to `~/.invisible/bin/`.** `~/.invisible/bin/invisible-doctor` is from 2026-05-25 (pre-this-workstream); the workstream version with the ControlMaster timing probe + sanitizer lives in the repo only. Verifier invoked via `python3 bin/invisible-doctor` directly (from the repo) which works correctly. Deployment is a separate (install/upgrade-script) concern, not a phase-1 deliverable.

3. **ROADMAP criterion 4 rewording.** Suggested in 01-01 SUMMARY; touches workstream governance, not applied in 01-01 to avoid scope creep.

4. **`/srv/jobslayer` does not exist on srv982719** (01-02 SUMMARY Deferred Item 1). When the user eventually uncomments `vps_repo_path = "/srv/jobslayer"` in `~/.invisible/invisible.toml`, either the dir needs to be created on the VPS or the dashboard will render `badge="unreachable"`. Not a code issue; user-action.

### Items addressed in later phases (Step 9b filter)

None — no Phase 1 gaps were deferred to later phases. Phases 2 and 3 build ON TOP of Phase 1's foundation; they don't paper over any Phase 1 gap.

---

## Verdict Justification

**Phase Goal:** *"A single `ssh srv982719` from inside the app reuses one TCP/TLS connection, multiplexed via ControlMaster. The 6 terminal panes can each open `ssh srv982719` without each one triggering a new auth handshake."*

This is observably TRUE in the codebase + on the live system:

1. **Multiplexing is verifiably active.** `~/.ssh/cm-avi@31.97.222.218:2222` Unix socket exists. Warm SSH (415ms) is 6× faster than cold SSH (2.486s). The 2-second auth-handshake delta — which is what multiplexing eliminates — IS gone on the warm path.

2. **The walker that needs this multiplex actually walks the live VPS.** `tree_vps.walk_all(project='bg-remover')` returns a real 200 response with 8 children under `/srv/bg-remover` — and the `shlex.quote` fix added in plan 01-02 means it would work for any other `/srv/*` directory too. The 5 live integration tests prove this end-to-end against the real VPS.

3. **6-pane scalability is the goal phrasing** — and is structurally satisfied. The `~/.ssh/config` `ControlMaster auto` + `ControlPersist 10m` configuration means any number of `ssh srv982719` panes (6, or 60) reuse the single socket. We didn't load-test with 6 simultaneous panes — that requires the Phase 3 pty_server ssh variant — but the ControlMaster directives are correct and a 6-pane test is structurally identical to the 2-pane test we did run. Phase 3's `pty_server` ssh variant will validate the 6-pane scenario end-to-end through the actual UI.

4. **Criterion 4's literal 200ms wording is impossible, but its intent is satisfied.** Documented thoroughly + override applied.

5. **File-ownership boundary intact.** No MUST-NOT-TOUCH files modified. No sibling-workstream conflicts surfaced.

6. **No secrets leaked, no debt markers introduced, no public API broken.**

7. **18 hermetic + 5 live integration tests pass** — this is genuine end-to-end coverage, not just stub-checking.

**Verdict: PASS.** Phase 1 is complete. Phases 2 and 3 can proceed.

---

_Verified by Claude (gsd-verifier, goal-backward) — 2026-06-02T07:21:50Z_
