---
phase: INV-01-ssh-controlmaster-invisible-toml-host
plan: 02
subsystem: vps-connection
tags: [tree_vps, ssh, controlmaster, pytest, integration, m2]
requirements_addressed:
  - REQ-VPS-01
  - REQ-04
requires:
  - 01-01
provides:
  - tree_vps-hermetic-test-coverage
  - tree_vps-live-integration-suite
  - tree_vps-shell-quoting-fix
affects:
  - lib/api/tree_vps.py
  - tests/test_tree_vps.py (new)
  - tests/test_tree_vps_live.py (new)
  - tests/conftest.py (new)
  - pytest.ini (new)
tech_stack:
  added: []
  patterns:
    - pytest-integration-flag (--integration opt-in)
    - session-scoped-reachability-probe (vps_reachable fixture)
    - composite-skip-gate (live_vps_or_skip)
    - shlex-quote-remote-argv (defend against remote-shell glob expansion)
key_files:
  created:
    - tests/test_tree_vps.py
    - tests/test_tree_vps_live.py
    - tests/conftest.py
    - pytest.ini
    - .planning/workstreams/vps-connection/phases/INV-01-ssh-controlmaster-invisible-toml-host/01-02-SUMMARY.md
  modified:
    - lib/api/tree_vps.py
decisions:
  - "Step 2B applied: integration test surfaced a real bug. Live walk against /srv/bg-remover failed with `find: paths must precede expression` because OpenSSH joins remote argv with spaces and the remote bash glob-expanded `*/.git*` against /home/avi (matched ace-claude-toolkit/.gitignore)."
  - "Fix: shlex.quote each remote_cmd element in _ssh_argv. Surgical: +13/-2 LOC. Single-token args unchanged; only glob/meta-char args wrapped."
  - "Live-tests use the user's REAL ~/.invisible/invisible.toml via the vps_configured_project fixture. When the user has no [[projects]] entry with a vps_repo_path, the tests SKIP cleanly (rather than FAIL) — verified end-to-end."
  - "Evidence for must-have happy-path contract captured via INVISIBLE_HOME=/tmp/inv-live-probe — all 5 live tests PASS against srv982719 when a vps_repo_path IS configured."
metrics:
  duration: ~45m
  task_count: 3
  files_count: 5  # 4 new + 1 modified
  completed_date: 2026-06-02
---

# Phase 1 Plan 02: tree_vps verify-and-harden Summary

**One-liner:** Verified the existing `lib/api/tree_vps.py` end-to-end against `srv982719` — surfaced a real glob-quoting bug (remote bash was expanding `*/.git*` against `/home/avi` before `find` saw it), applied a 13-line surgical `shlex.quote` fix at the `_ssh_argv` boundary, added 18 hermetic + 5 live integration tests with 2 regression-guard tests for the new contract.

## Files Created / Modified

| File | Lines | Purpose |
|------|-------|---------|
| `tests/test_tree_vps.py` (new) | +633 | 18 hermetic tests — every documented branch of `walk_all` + `_walk_remote`; 2 regression tests for the shlex-quote contract. NO live network. |
| `tests/test_tree_vps_live.py` (new) | +272 | 5 live tests gated by `--integration` + `live_vps_or_skip` fixture; module-level `pytestmark = pytest.mark.vps_integration`. |
| `tests/conftest.py` (new) | +167 | `--integration` CLI flag, `vps_reachable` session probe, `vps_configured_project` real-toml discovery, composite `live_vps_or_skip` gate. |
| `pytest.ini` (new) | +12 | `vps_integration` marker registration, `--strict-markers` in addopts, `testpaths = tests`. |
| `lib/api/tree_vps.py` (modified) | +13/-2 | `import shlex`; `shlex.quote` each `remote_cmd` arg in `_ssh_argv` so the remote `$SHELL -c` cannot glob-expand. |

## Commits

| Hash | Type | Message |
|------|------|---------|
| `36fa0ec` | test | hermetic unit tests for `tree_vps.walk_all` + `_walk_remote` |
| `88d3acb` | test | integration scaffolding — `pytest.ini`, `conftest.py`, live tests |
| `fa32e9f` | fix  | `shlex.quote` remote_cmd in `_ssh_argv` so globs survive intact |
| (this)    | docs | complete Plan 01-02 — tree_vps verify-and-harden |

## Step 2A / 2B / 2C — which path applied?

**Step 2B applied.** The live integration test surfaced a CONCRETE, diagnosable failure path in `lib/api/tree_vps.py`. The fix is minimal (+13/-2) and surgical, accompanied by 2 hermetic regression tests that fail before the fix and pass after (verified via `git stash`).

### Failure mode

When invoked against the real srv982719 (with a `vps_repo_path = "/srv/bg-remover"` configured), `walk_all` returned status=200 but the walked-root carried `badge="unreachable"`. The captured remote stderr:

```
find: paths must precede expression: `ace-claude-toolkit/.gitignore'
find: possible unquoted pattern after predicate `-path'?
```

### Diagnosis

`lib/api/tree_vps.py:170-190` (`_ssh_argv`) builds an SSH argv where `*remote_cmd` is appended as-is after `--`. OpenSSH then **joins the remote argv with spaces** and pipes the result to the remote `$SHELL -c`. The remote bash re-tokenizes AND glob-expands. The find argv contains `["-not", "-path", "*/.git*"]` — the `*/.git*` token gets expanded by the remote shell against the remote CWD (`/home/avi` for the `avi` user), which has `ace-claude-toolkit/.gitignore` matching `*/.git*`. The expanded arg list confuses `find`, which exits with rc=1 and the diagnostic above. `_walk_remote` correctly returns `badge="unreachable"` — the contract IS preserved — but the user's expectation of a real tree is not met.

### Fix

```python
# lib/api/tree_vps.py
import shlex  # new
# ... inside _ssh_argv:
    return [
        "ssh", ..., host, "--",
        *(shlex.quote(arg) for arg in remote_cmd),
    ]
```

`shlex.quote` leaves single-token args (`find`, `/srv/proj`, `-maxdepth`) unchanged and only wraps glob/meta-char args. The local `subprocess.run` is unaffected — it never invoked a shell — only the remote shell sees the quoted form.

### Regression tests (in `tests/test_tree_vps.py`)

1. **`test_walk_all_argv_shell_quotes_remote_command_so_globs_dont_expand_on_remote`** — stubs `subprocess.run`, asserts `"'*/.git*'"` (the `shlex.quote`'d form) appears in the argv after `--`.
2. **`test_walk_remote_handles_real_world_remote_cwd_via_shell_quoting`** — stubs `subprocess.run` to SIMULATE the remote-shell glob-expansion failure when given an unquoted glob, asserts `walk_all` returns 200 with no `unreachable` badge (which would only happen if quoting works).

Both tests fail before the fix (verified by `git stash`-ing `lib/api/tree_vps.py` and re-running). Both pass after.

## Test Counts

| Suite | File | Count | Status (default) | Status (--integration with /tmp/inv-live-probe) |
|-------|------|-------|-----------------|------------------------------------------------|
| Hermetic | `tests/test_tree_vps.py` | 18 | 18 PASSED | 18 PASSED |
| Live integration | `tests/test_tree_vps_live.py` | 5 | 5 SKIPPED (no `--integration`) | 5 PASSED |
| Pre-existing | `tests/test_api_projects.py` | 7 | 7 PASSED | 7 PASSED |
| **Total** | | **30** | **25 PASSED + 5 SKIPPED** | **30 PASSED** |

With the user's REAL `~/.invisible/invisible.toml` (no `vps_repo_path` set for any project): live tests SKIP cleanly with reason `no [[projects]] in ~/.invisible/invisible.toml has vps_repo_path set` — the `live_vps_or_skip` gate working as designed.

## Live VPS Evidence

Full output of `INVISIBLE_HOME=/tmp/inv-live-probe pytest tests/test_tree_vps_live.py --integration -v` where `/tmp/inv-live-probe/invisible.toml` has `vps_repo_path = "/srv/bg-remover"`:

```
============================= test session starts ==============================
platform darwin -- Python 3.11.4, pytest-7.4.0, pluggy-1.0.0 -- /Users/ace/anaconda3/bin/python3
cachedir: .pytest_cache
rootdir: /Users/ace/.invisible-ws/vps-connection
configfile: pytest.ini
plugins: anyio-4.12.1, langsmith-0.7.16
collecting ... collected 5 items

tests/test_tree_vps_live.py::test_walk_all_live_returns_tree PASSED      [ 20%]
tests/test_tree_vps_live.py::test_walk_all_live_warm_call_completes_under_3s PASSED [ 40%]
tests/test_tree_vps_live.py::test_walk_all_live_empty_host_still_503 PASSED [ 60%]
tests/test_tree_vps_live.py::test_walk_all_live_unknown_path_yields_unreachable_badge PASSED [ 80%]
tests/test_tree_vps_live.py::test_walk_all_live_argv_actually_uses_controlmaster PASSED [100%]

============================== 5 passed in 2.31s ===============================
```

Sample walked tree (from a one-shot probe — `INVISIBLE_HOME=/tmp/inv-live-probe python3 -c '... walk_all(...)'`):

```
status=200
top_name='bg-remover'
walked_name='/srv/bg-remover'
walked_badge=None
child_count=8
first_10_children: ['.env', 'app.py', 'bulk.py', 'data', 'deploy', 'requirements.txt', 'static', 'webp.py']
```

## Public API Surface Guard

```
$ python3 -c 'import sys; sys.path.insert(0, "lib"); from api import tree_vps; assert tree_vps.VPS_NOT_CONFIGURED == {"error": "vps.host not configured"}; assert tree_vps.MAX_DEPTH == 6; assert tree_vps.SSH_TIMEOUT_S == 15'
OK · public API preserved
```

`walk_all`, `_walk_remote`, `_ssh_argv`, `_validate_host`, `_validate_remote_path` all callable; signatures unchanged; `VPS_NOT_CONFIGURED`, `MAX_DEPTH`, `SSH_TIMEOUT_S` constants identical; 4-branch return contract preserved.

## tree_vps.py Diff Size

```
$ git diff --shortstat HEAD~3 HEAD -- lib/api/tree_vps.py
 1 file changed, 13 insertions(+), 2 deletions(-)
```

Surgical edit, well under the 20-line budget from the plan's authority limit.

## SSH Reachability After Test Run

```
$ ssh -o BatchMode=yes -o ConnectTimeout=4 srv982719 echo ok
ok
```

The ControlMaster master survived the test invocations — `~/.ssh/cm-avi@31.97.222.218:2222` socket still active (Plan 01-01 layer). The dashboard daemon's separate socket dir (`$INVISIBLE_HOME/run/`) is also unaffected.

## Threat Model — must-have correlations

Confirmed Plan 01-02 `<threat_model>` mitigations remain in place after the fix:

- **T-INV01L-01 (info disclosure in test logs):** `vps_configured_project` returns only `(name, vps_repo_path)`; tests never `print()` the full toml.
- **T-INV01L-02 (shell injection via vps_repo_path):** `_validate_remote_path` still rejects `..` segments and shell-meta. Hermetic test 7 (`test_walk_all_project_with_invalid_vps_repo_path_skipped_with_stderr`) explicitly asserts. **NOTE:** the `shlex.quote` fix is defense-in-depth on TOP of validation — it neutralizes glob-expansion even if validation were somehow bypassed.
- **T-INV01L-04 (host spoofing):** OpenSSH `StrictHostKeyChecking=ask` default → user accepts host key on first connect (Plan 01-01 step 4).
- **T-INV01L-06 (DoS via slow VPS):** `SSH_TIMEOUT_S=15` cap unchanged; `test_walk_all_live_warm_call_completes_under_3s` enforces a 3.0s warm budget.

## Deviations from Plan

### Plan said `Step 2A` was 85% likely; reality was `Step 2B`

The plan author's prior was 85% Step 2A (no patch). The actual outcome was Step 2B — a real bug surfaced. The plan handled this correctly: the `<authority_limits>` section in Task 3 explicitly allowed a surgical patch with a regression test, which is exactly what was applied.

The bug had been latent because:
- Plan 01-01's `invisible-doctor` check_ssh only runs `ssh srv982719 echo ok` — it never invokes a `find` with glob args, so the bug couldn't have been caught at the doctor layer.
- No prior test exercised `walk_all` against a real VPS; the M1 `folders-3source` workstream tested `walk_all` only with `vps.host = ""` (the 503 path).
- The user's only project (`jobslayer`) had no `vps_repo_path` set, so the dashboard had never actually walked anything on srv982719.

### Live tests skip cleanly on the user's real ~/.invisible — needed an INVISIBLE_HOME override to demonstrate the live PASS

The user's `~/.invisible/invisible.toml` has `jobslayer` but `vps_repo_path` is commented out:

```toml
[[projects]]
name = "jobslayer"
# vps_repo_path  = "/srv/jobslayer"   # set later if you want VPS handoff
```

`live_vps_or_skip` correctly SKIPs the 4 tests that need a configured project. To capture EVIDENCE that the live path actually works (must_have #1: *"a live `walk_all(project='<configured-project>')` returns `([{...tree...}], 200)`"*), the verification used `INVISIBLE_HOME=/tmp/inv-live-probe` with a synthetic invisible.toml pointing at `/srv/bg-remover` (a real-existing /srv/* dir on the VPS per memory `bg_remover_api.md`). This does NOT mutate the user's real config.

**Recommendation:** To run the live suite against the user's real config, add (as the user sees fit):

```toml
[[projects]]
name = "jobslayer"
client = "personal"
repo_path = "~/Projects/jobslayer"
vps_repo_path = "/srv/jobslayer"   # ← uncomment + ensure /srv/jobslayer exists on srv982719
```

Or any other real `/srv/<dir>`. Out of scope for this plan (we don't touch the user's local config).

## Deferred Items

1. **`/srv/jobslayer` does not exist on srv982719.** The user has `jobslayer` in `[[projects]]` but no corresponding `/srv/jobslayer` on the VPS. When `vps_repo_path = "/srv/jobslayer"` is eventually uncommented, either (a) create the dir on the VPS or (b) the dashboard will render the project with `badge="unreachable"`. Not a code issue; user-action.

2. **Plan 01-01 deferred item — doctor `master=cached` threshold (200ms vs RTT floor).** Still applies; not addressed in 01-02 (out of scope — 01-02 owned tree_vps, not invisible-doctor).

3. **Existing untracked file `.planning/workstreams/vps-connection/config.json`** — `{"workflow": {"_auto_chain_active": false}}`. Not modified by this plan; left untracked. Belongs to the gsd workstream-config layer and is gitignored implicitly (no .gitignore entry yet, but no other workstreams in this milestone have committed it either).

4. **Frontend smoke-test.** Plan 03-02 will exercise the `/api/v1/tree/vps` HTTP endpoint end-to-end through the React frontend. With Plan 01-02's fix, that endpoint should now return real trees instead of 503/unreachable. No work required here; just a forward-looking note for Phase 3.

## Phase 1 Status After This Plan

All four ROADMAP criteria for Phase 1 are now satisfied or characterized:

1. ✅ `~/.ssh/config` `Host srv982719` block with ControlMaster directives (Plan 01-01)
2. ✅ `invisible.toml` `[vps]` configured (Plan 01-01)
3. ✅ Passwordless SSH (Plan 01-01)
4. ⚠️ Warm SSH "under 200ms" — RTT-bound; criterion-spec correction recommended (Plan 01-01)
5. ✅ **`lib/api/tree_vps.py` actually walks the live VPS** (Plan 01-02) — verified against `/srv/bg-remover` end-to-end; bug found + fixed.

Phase 1 is complete from this workstream's perspective. Phase 2 (`invisible-server` systemd unit + nginx vhost) can now rely on the SSH plumbing being solid AND the dashboard walker actually working.

## Self-Check: PASSED

- `tests/test_tree_vps.py` — present, 18 tests collected, all pass ✓
- `tests/test_tree_vps_live.py` — present, 5 tests collected, all skip without `--integration` ✓
- `tests/conftest.py` — present, contains `--integration`, `vps_reachable`, `vps_configured_project`, `live_vps_or_skip` ✓
- `pytest.ini` — present, registers `vps_integration` marker, `--strict-markers` in addopts ✓
- `lib/api/tree_vps.py` — present, parses, `shlex` imported, `_ssh_argv` shell-quotes remote_cmd ✓
- Commits `36fa0ec`, `88d3acb`, `fa32e9f` exist in git log ✓
- Live VPS reachability after test run: `ssh srv982719 echo ok` returns `ok` ✓
- Public API surface unchanged: `walk_all`, `_walk_remote`, `_ssh_argv`, `VPS_NOT_CONFIGURED`, `MAX_DEPTH`, `SSH_TIMEOUT_S` all callable/equal ✓
- Regression tests fail before fix + pass after (verified via `git stash`) ✓
- No secrets in any staged diff (regex scan clean) ✓
