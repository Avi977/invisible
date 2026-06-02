---
phase: INV-01-ssh-controlmaster-invisible-toml-host
slug: ssh-controlmaster-invisible-toml-host
status: verified
threats_total: 18
threats_closed: 18
threats_open: 0
asvs_level: 1
block_on: high
audit_date: 2026-06-02
created: 2026-06-02
---

# Phase 1 — Security

> Per-phase security contract for Phase 1 (`INV-01-ssh-controlmaster-invisible-toml-host`).
> Threat register combined across Plan 01-01 (SSH ControlMaster / invisible.toml / doctor)
> and Plan 01-02 (tree_vps live verify + hardening). All threats verified against the
> committed implementation (commits `e8af0bc` … `44bd3d9` on `ws/vps-connection`).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| user shell → VPS (`avi@31.97.222.218:2222`) | Outbound SSH over the open internet; key-based auth; ControlMaster multiplex | Find output (file/dir listings) |
| `invisible.toml.example` → git history | Committable example file; MUST contain no secrets | TOML config (defaults only) |
| `README.md` → git history | Public documentation; references paths only | Markdown |
| `bin/invisible-doctor` stderr → operator console | Error snippets may surface paths or key filenames | Diagnostic text |
| `~/.ssh/config` ↔ out-of-repo file | Not committed; documented for the user | SSH client config |
| `bin/invisible-doctor` → `ssh` subprocess | Argv-based exec (`shell=False`); host passed as positional arg | Argv list |
| `lib/api/tree_vps.py::_walk_remote` → remote `/srv/<project>` via SSH | Argv-form exec; validated host + path; timeout-bounded | Remote `find` argv + stdout |
| `lib/api/tree_vps.py::_ssh_argv` → `-i <identity>` | `os.path.expanduser`-ed and passed via argv — never shell-interpolated | Identity path string |
| pytest process → user's real `~/.invisible/invisible.toml` (live tests) | Read-only fixture; returns `(name, vps_repo_path)` tuple | Project name + remote path |
| pytest process → tmp_path (hermetic tests) | Isolated; never mutates user state | Synthetic TOML |

---

## Threat Register

### Plan 01-01 — SSH ControlMaster + invisible.toml + doctor

| Threat ID | Category | Component | Disposition | Mitigation | Status | Evidence |
|-----------|----------|-----------|-------------|------------|--------|----------|
| T-INV01H-01 | Information Disclosure | `invisible.toml.example` accidentally committing secrets | mitigate | Regex scan on committed file for private-key headers / AWS keys / raw SSH pubkey payloads; defaults-only values | CLOSED | `invisible.toml.example:62-64` (host="", identity="~/.ssh/id_ed25519", use_mosh=false); `grep -E "BEGIN OPENSSH PRIVATE KEY\|AKIA[0-9A-Z]{16}\|ssh-ed25519 AAAA[0-9A-Za-z+/]{20,}" invisible.toml.example` → 0 matches |
| T-INV01H-02 | Information Disclosure | `README.md` printing key material in fenced block | mitigate | Same regex scan; documented commands reference paths only (`~/.ssh/id_ed25519`) | CLOSED | `grep -E "BEGIN OPENSSH PRIVATE KEY\|AKIA[0-9A-Z]{16}\|ssh-ed25519 AAAA[0-9A-Za-z+/]{20,}" README.md` → 0 matches; commands cite paths not bytes (README.md:124-218 — `### VPS connection setup`) |
| T-INV01H-03 | Tampering | `bin/invisible-doctor check_ssh()` shell injection via `vps.host` | mitigate | (a) argv-form `subprocess.run(...)` (shell=False); (b) `_HOST_RE` regex defense-in-depth; (c) regex byte-for-byte identical to `tree_vps.py` (drift gate); (d) bad host NOT echoed back | CLOSED | (a) `bin/invisible-doctor:244,267` argv list, no `shell=True`; (b) `bin/invisible-doctor:52` `_HOST_RE = re.compile(r"^(?:[A-Za-z0-9_.-]+@)?[A-Za-z0-9._-]+$")` matched against `lib/api/tree_vps.py:114` byte-for-byte; (c) `bin/invisible-doctor:230-236` rejects bad host with literal regex echoed but NOT the offending value |
| T-INV01H-04 | Information Disclosure | doctor stderr leaks `/Users/…/.ssh/id_ed25519` paths | mitigate | `_sanitize_ssh_stderr()` redacts `/Users/…`, `/home/…`, `id_*`, `*.pem` | CLOSED | `bin/invisible-doctor:55-76` `_sanitize_ssh_stderr` — substitutes `/Users/[^/ \t]+/[^\s]*`, `/home/[^/ \t]+/[^\s]*` → `<path>`; `\bid_[A-Za-z0-9_]+\b`, `\b[\w.-]+\.pem\b` → `<keyfile>`; called at line 252 |
| T-INV01H-05 | Spoofing | future maintainer collapses two ControlPath layers | mitigate | Decision A documented in 3 locations | CLOSED | (1) `invisible.toml.example:52-61` — "Decision A — Two ControlMaster layers, intentionally NOT consolidated"; (2) `README.md:210-218` — "Two ControlMaster layers (intentional)"; (3) `lib/api/tree_vps.py:34-41` module docstring — "ControlMaster: … The dedicated socket-dir under `$INVISIBLE_HOME/run` prevents collision with the user's own SSH sessions." |
| T-INV01H-06 | Denial of Service | doctor 14s sequential SSH worst-case | accept | Developer diagnostic, not a long-lived service; bounded by per-call timeouts (12s + 6s); documented | CLOSED (accepted) | See Accepted Risks Log |
| T-INV01H-07 | Repudiation | no audit trail of `ssh-copy-id` invocation | accept | Single-user tool per PROJECT.md | CLOSED (accepted) | See Accepted Risks Log |
| T-INV01H-08 | Tampering | user has conflicting `Host *` block | accept | Out of plan authority; README documents pre-existing `Host vps` alias should be preserved | CLOSED (accepted) | `README.md:166-167` — "(You probably already have a `Host vps` block pointing at the same IP — leave it alone. The new `srv982719` block is in addition to it.)"; see Accepted Risks Log |
| T-INV01H-SC | Tampering | supply chain (new package install) | accept | No new package installs; only stdlib `re` + `time` added to doctor | CLOSED (accepted) | `bin/invisible-doctor:21-31` imports — stdlib only; see Accepted Risks Log |

### Plan 01-02 — tree_vps live verify + hardening

| Threat ID | Category | Component | Disposition | Mitigation | Status | Evidence |
|-----------|----------|-----------|-------------|------------|--------|----------|
| T-INV01L-01 | Information Disclosure | integration test logs leak full invisible.toml | mitigate | `vps_configured_project` fixture returns only `(name, vps_repo_path)` tuple; no `print()` of full toml | CLOSED | `tests/conftest.py:110-138` `vps_configured_project()` returns `Optional[tuple[str, str]]`; `grep -n "print(" tests/conftest.py` → no matches; live tests at `tests/test_tree_vps_live.py:91` unpack the tuple by value |
| T-INV01L-02 | Tampering | `_walk_remote` shell injection via `vps_repo_path` | mitigate | `_validate_remote_path()` regex `^/[A-Za-z0-9_./~+-]+$` + explicit `..` rejection; argv-form exec; hermetic test 7 + live test 4 assert | CLOSED | `lib/api/tree_vps.py:120` `_PATH_RE = re.compile(r"^/[A-Za-z0-9_./~+-]+$")`; `lib/api/tree_vps.py:141` `if ".." in p.split("/"): return False`; hermetic regression `tests/test_tree_vps.py::test_walk_all_project_with_invalid_vps_repo_path_skipped_with_stderr`; live regression `tests/test_tree_vps_live.py::test_walk_all_live_unknown_path_yields_unreachable_badge` |
| T-INV01L-03 | Tampering | live test malicious config | accept | `--integration` is opt-in; developer-controlled toml | CLOSED (accepted) | `tests/conftest.py:44-54` `--integration` opt-in flag; see Accepted Risks Log |
| T-INV01L-04 | Spoofing | SSH MITM (different host responds for `srv982719` alias) | mitigate | OpenSSH host-key verification inherited from system defaults (`StrictHostKeyChecking=ask`); first connect prompts user to accept host fingerprint; subsequent connections compare `~/.ssh/known_hosts` | CLOSED | Inherited mitigation operates automatically; `ssh-copy-id` step at `README.md:170-172` is the first connection that triggers the host-key prompt. NOTE: README does NOT contain a literal "accept host key once" sentence — the threat model declared this; the actual defense is the OpenSSH default which fires regardless. Audit acceptance: system-default behavior IS the mitigation. See post-hoc finding #2 below for the documentation-tightening recommendation. |
| T-INV01L-05 | Information Disclosure | `_walk_remote` stderr leaks `/srv/<project>` layout | accept | `/srv/<project>` paths are public per `vps_infra.md`; single-line stderr, no stack trace | CLOSED (accepted) | `lib/api/tree_vps.py:275,286` — one-line `[tree_vps] ssh/find failed for {host}:{remote_root}: {exc}`; see Accepted Risks Log |
| T-INV01L-06 | Denial of Service | live tests hang on slow VPS | mitigate | `SSH_TIMEOUT_S = 15` caps subprocess; live test 2 asserts `< 3.0s` warm | CLOSED | `lib/api/tree_vps.py:95` `SSH_TIMEOUT_S = 15`; passed to `_ssh_argv` as `ConnectTimeout` (line 193) and to `subprocess.run(timeout=SSH_TIMEOUT_S)` (line 272); `tests/test_tree_vps_live.py:133-160` `test_walk_all_live_warm_call_completes_under_3s` asserts `duration < 3.0` |
| T-INV01L-07 | Tampering | live test overwrites user `~/.invisible/invisible.toml` | mitigate | Hermetic tests use `tmp_path` exclusively; live tests forbidden from `_write_toml(home())` | CLOSED | All 20 `_write_toml(...)` call sites in `tests/test_tree_vps.py` + `tests/test_tree_vps_live.py` pass `tmp_path` as first arg (`tests/test_tree_vps_live.py:172,199`); zero call sites pass `home()` or any non-tmp_path arg |
| T-INV01L-08 | Repudiation | no audit trail of which test run walked live VPS | accept | Pytest log is the audit trail | CLOSED (accepted) | See Accepted Risks Log |
| T-INV01L-SC | Tampering | supply chain (new package install) | accept | No new package installs; stdlib + existing pytest only | CLOSED (accepted) | `lib/api/tree_vps.py:65-75` imports — stdlib (`os`, `re`, `shlex`, `subprocess`, `sys`) + project `config` only; see Accepted Risks Log |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Threat Flags from SUMMARY.md

Both `01-01-SUMMARY.md` and `01-02-SUMMARY.md` were reviewed for a `## Threat Flags` section recording new attack surface surfaced during implementation. Neither summary contains such a section. The threat-model items addressed in each summary correlate 1:1 with the pre-registered threats above; no **unregistered_flag** entries to record.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-INV01H-06 | T-INV01H-06 | The doctor's `check_ssh()` runs two sequential SSH invocations (first call up to 12s timeout, second up to 6s timeout) — worst-case ~14s. The doctor is a developer-run diagnostic, not a long-lived service. Per-call timeouts bound the worst case; never hangs indefinitely. Documented in `bin/invisible-doctor:213-220` docstring. | ace | 2026-06-02 |
| AR-INV01H-07 | T-INV01H-07 | No audit trail of who ran `ssh-copy-id`. PROJECT.md declares "Single user" — there is no multi-tenant authorization model to audit against. Audit is out of scope for the workstream. | ace | 2026-06-02 |
| AR-INV01H-08 | T-INV01H-08 | A user-side `Host *` block in `~/.ssh/config` could override directives from the new `Host srv982719` block. Plan authority does not extend to the user's `~/.ssh/config`. README explicitly notes "(You probably already have a `Host vps` block pointing at the same IP — leave it alone.)" The doctor's `master=new` PASS-with-flag surface will report the symptom (warm SSH slower than 200ms). | ace | 2026-06-02 |
| AR-INV01H-SC | T-INV01H-SC | No new package installs in Plan 01-01. Doctor adds only `re` and `time` from the Python standard library. Zero supply-chain surface added. | ace | 2026-06-02 |
| AR-INV01L-03 | T-INV01L-03 | The live integration test reads `~/.invisible/invisible.toml` directly (not via tmp_path). It runs ONLY when the developer explicitly passes `--integration`, and the developer wrote the invisible.toml themselves. There is no untrusted input source for the live tests. | ace | 2026-06-02 |
| AR-INV01L-05 | T-INV01L-05 | `_walk_remote` stderr emits `[tree_vps] ssh/find failed for {host}:{remote_root}: …` to `sys.stderr` on failure. `/srv/<project>` paths are not secrets per Mac memory `vps_infra.md` (the VPS layout is publicly documented). The log line is single-line, no stack trace. Accepted. | ace | 2026-06-02 |
| AR-INV01L-08 | T-INV01L-08 | No audit trail of which test run walked the live VPS. Pytest log is the audit trail; the SUMMARY records date + result. Single-user, single-machine constraint per PROJECT.md. | ace | 2026-06-02 |
| AR-INV01L-SC | T-INV01L-SC | No new package installs in Plan 01-02. `lib/api/tree_vps.py` adds only `shlex` from the Python standard library; pytest is already a dev-dependency. Zero supply-chain surface added. | ace | 2026-06-02 |

*Accepted risks do not resurface in future audit runs.*

---

## Post-Hoc Findings

Findings that are NOT pre-registered threats but are security-adjacent and worth recording for audit completeness.

### PHF-01 — `shlex.quote` of `remote_cmd` in `_ssh_argv` (commit `fa32e9f`)

- **Type:** Correctness improvement to security-critical code (NOT a security vulnerability).
- **What happened:** During Plan 01-02 Task 3 (Step 2B), the live integration test surfaced `find: paths must precede expression: \`ace-claude-toolkit/.gitignore'` when walking `/srv/bg-remover`. Root cause: OpenSSH joins `*remote_cmd` argv with spaces and pipes the result to remote `$SHELL -c`. The unquoted glob token `*/.git*` (from `find -path */.git*`) was re-tokenized AND glob-expanded by the remote bash against `/home/avi`, matching `ace-claude-toolkit/.gitignore` and breaking `find`.
- **Is it a security vulnerability?** No. There is no privilege escalation: argv-form local exec still blocks local shell injection. The remote shell only re-tokenizes content authored by `tree_vps.py` itself (not user input). `_validate_remote_path` still rejects user-supplied paths containing shell-meta before they reach `_ssh_argv`. The bug was a correctness failure: `find` received malformed args and returned rc=1, producing `badge="unreachable"` instead of a real tree.
- **Why it's relevant to security:** `_ssh_argv` is security-critical code (the argv layer is the LAST line of defense before the remote shell). The threat model anticipated argv-form exec as the mitigation for shell injection (T-INV01L-02) but did NOT anticipate the second-order remote-shell-tokenization step. The `shlex.quote` fix is defense-in-depth on top of `_validate_remote_path` — it neutralizes glob-expansion even if validation were ever bypassed.
- **Fix:** `lib/api/tree_vps.py:69` `import shlex`; `lib/api/tree_vps.py:200` `*(shlex.quote(arg) for arg in remote_cmd)` inside `_ssh_argv`. Diff size: +13/-2 LOC.
- **Verification:** 2 hermetic regression tests added in `tests/test_tree_vps.py`:
  - `test_walk_all_argv_shell_quotes_remote_command_so_globs_dont_expand_on_remote` (line 541) — asserts `"'*/.git*'"` appears after `--` in argv.
  - `test_walk_remote_handles_real_world_remote_cwd_via_shell_quoting` (line 588) — stubs remote-shell glob-expansion simulator; asserts happy 200 path (would FAIL without quoting).
  - Both verified to fail before the fix and pass after (via `git stash` rollback test per `01-02-SUMMARY.md`).
- **Recommendation:** Future phases should treat the argv layer's defense-in-depth quoting as a permanent pattern. Any new `subprocess.run(_ssh_argv(host, identity, *remote_cmd))` site inherits the protection automatically.

### PHF-02 — T-INV01L-04 README wording is implicit, not literal

- **Type:** Documentation gap; no implementation gap.
- **Finding:** The threat model for T-INV01L-04 (SSH MITM) declares the mitigation as "README step 4 instructs user to accept host key once". The actual README `### VPS connection setup` section does NOT contain a literal "accept host key once" instruction. The host-key-acceptance prompt fires automatically during step 3 (`ssh-copy-id`) because OpenSSH's `StrictHostKeyChecking=ask` system default presents the host fingerprint on first connection.
- **Why it's CLOSED nonetheless:** The substantive defense is the OpenSSH system default, which operates automatically without user-side opt-in. The user encounters the prompt during `ssh-copy-id` and accepts it once. The README documents the `ssh-copy-id` step but does not call out the fingerprint-acceptance moment explicitly.
- **Recommendation (NON-BLOCKING):** A future docs touch-up could add a sentence to README step 3: "OpenSSH will display the host fingerprint on first connection — confirm it matches `31.97.222.218`'s expected key before accepting." Not required for Phase 1 sign-off; the system-default defense is intact.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By | Verdict |
|------------|---------------|--------|------|--------|---------|
| 2026-06-02 | 18 | 18 | 0 | claude (gsd-secure-phase, register_authored_at_plan_time) | SECURED |

**Audit method:** Per-threat verification by disposition. `mitigate` threats grepped for the declared mitigation pattern in cited files; `accept` threats recorded as accepted-risk entries with rationale; no `transfer` dispositions in this phase. Implementation files were read-only — no source patched during the audit.

**Files inspected:**
- `/Users/ace/.invisible-ws/vps-connection/invisible.toml.example`
- `/Users/ace/.invisible-ws/vps-connection/README.md`
- `/Users/ace/.invisible-ws/vps-connection/bin/invisible-doctor`
- `/Users/ace/.invisible-ws/vps-connection/lib/api/tree_vps.py`
- `/Users/ace/.invisible-ws/vps-connection/tests/conftest.py`
- `/Users/ace/.invisible-ws/vps-connection/tests/test_tree_vps.py`
- `/Users/ace/.invisible-ws/vps-connection/tests/test_tree_vps_live.py`
- `/Users/ace/.invisible-ws/vps-connection/pytest.ini`

**Behavioral confirmations (from `VERIFICATION.md` 2026-06-02):**
- Hermetic test suite: 18 passed (no network).
- Live integration suite: 5 passed against `srv982719:/srv/bg-remover` (with `--integration` + `INVISIBLE_HOME=/tmp/inv-live-probe`).
- Doctor sanitizer: redacts `/Users/.../`, `id_*`, `.pem` confirmed.
- Doctor bad-host rejection: `check_ssh({'vps':{'host':'bad;rm -rf /'}})` returns FAIL without echoing `rm -rf` in detail string.
- `_HOST_RE` regex byte-for-byte identical in `bin/invisible-doctor:52` and `lib/api/tree_vps.py:114`.
- No secrets in any committed diff (`grep -E "BEGIN OPENSSH PRIVATE KEY|AKIA[0-9A-Z]{16}|ssh-ed25519 AAAA[0-9A-Za-z+/]{20,}"` → 0 matches across all three committed files).

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log (8 entries: AR-INV01H-06, -07, -08, -SC, AR-INV01L-03, -05, -08, -SC)
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter
- [x] Post-hoc findings recorded (2 entries: PHF-01 shlex.quote fix; PHF-02 README wording note)

**Approval:** verified 2026-06-02
