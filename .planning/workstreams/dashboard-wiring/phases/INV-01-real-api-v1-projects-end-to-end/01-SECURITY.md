---
phase: INV-01-real-api-v1-projects-end-to-end
slug: real-api-v1-projects-end-to-end
status: verified
threats_total: 16
threats_closed: 16
threats_open: 0
asvs_level: 1
block_on: high
audit_date: 2026-06-01
created: 2026-06-01
---

# Phase INV-01 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Verifies every declared mitigation in the implementation source. Plans 01-01
> (backend) + 01-02 (frontend) — 16 STRIDE threats (9 mitigate / 7 accept).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| user browser (origin `http://127.0.0.1:8090`) → dashboard daemon (`http://127.0.0.1:8765`) | Cross-origin fetch over loopback; CORS-controlled | Project metadata (names, repo paths, summaries, checkpoint state) |
| dashboard daemon → `invisible.toml` | File read; user-controlled paths inside `$INVISIBLE_HOME` | Project list + repo_path strings |
| dashboard daemon → user's project repos (`repo_path`) | Subprocess `git -C <path>`; potential path-injection target | git stdout (branch name, ISO timestamp) |
| dashboard daemon → orchestrator worktree | File read of `.invisible-checkpoint.json` | Orchestrator state (iteration, verdict, feedback history) |
| dashboard daemon → Notion API | Outbound HTTPS with bearer token from env | Review titles (read-only) |
| frontend daemon → user filesystem | Static file server; serves `frontend/*.jsx` to the browser | JSX source files |
| DOM render → response body | Renders strings from `/api/v1/projects` directly into the DOM via React text nodes | Project field strings (name, summary, note, error messages) |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-INV-01-01 | Tampering | `git -C <repo_path>` subprocess via `_run_git` / `_branch_and_last_commit` | mitigate | List-form `subprocess.run([...], shell=False, capture_output=True, text=True, timeout=2)` — `lib/api/projects.py:121-127`. Try/except catches `TimeoutExpired`, `FileNotFoundError`, `OSError` — `lib/api/projects.py:128-129`. Never propagates. | closed |
| T-INV-01-02 | Information Disclosure | Error responses leak absolute filesystem paths | mitigate | `handle_projects()` wraps `build_projects()` in `try/except Exception` and emits generic `{"error":"internal error"}` 500 — `lib/api/projects.py:301-319`. Stderr log uses `type(exc).__name__` only (no traceback, no path). `build_projects()` itself wraps `config.load_toml()` and `checkpoint.load()` in try/except — `lib/api/projects.py:244-263`. Test 6 (`test_build_projects_does_not_leak_paths`) asserts no `str(home)`, `/Users/`, or `/home/` substring in any string field even on broken worktree — `tests/test_api_projects.py:203-220`. | closed |
| T-INV-01-03 | Information Disclosure | Path traversal via `invisible.toml` `repo_path` (e.g. `"../../../etc"`) | mitigate | `_safe_path()` calls `Path(os.path.expanduser(p)).resolve()` then validates via `resolved.is_relative_to(home_dir)` OR `resolved.is_relative_to(invisible_root)` — `lib/api/projects.py:80-104`. Out-of-bounds returns `None`; treated by caller (`build_projects`, `lib/api/projects.py:256`) as "repo missing" (branch="—", lastCommit="—"). git subprocess is read-only (`rev-parse`, `log -1`). | closed |
| T-INV-01-04 | Spoofing | Cross-origin fetch from a malicious local web page reads user's project list | mitigate | `_send_json` echoes `Access-Control-Allow-Origin` ONLY when `origin.startswith("http://127.0.0.1:")` or `origin.startswith("http://localhost:")` — `bin/invisible-dashboard:258-262`. Never `*`. `Vary: Origin` set alongside (`:262`) to prevent intermediate cache poisoning. Daemon binds 127.0.0.1 by default — `bin/invisible-dashboard:381-382`. `--no-auth` requires `--host 127.0.0.1` — `bin/invisible-dashboard:390-392`. | closed |
| T-INV-01-05 | Denial of Service | Slow / hung git on a corrupt or NFS-mounted repo blocks the HTTP response | mitigate | `subprocess.run(..., timeout=2)` per git call — `lib/api/projects.py:126`. `TimeoutExpired` caught at `:128`, returns `None` → caller falls back to `("—", "—")` at `lib/api/projects.py:144-152`. Worst-case latency: N projects × 2s per repo. | closed |
| T-INV-01-06 | Tampering | Malicious `.invisible-checkpoint.json` crashes JSON decoder | accept | Python stdlib `json.loads` handles deeply-nested JSON safely; checkpoint files are written by our own orchestrator (single-user). Risk accepted — see Accepted Risks Log. | closed |
| T-INV-01-07 | Information Disclosure | Notion review titles surface internal project names to cross-origin attacker | accept | Gated by loopback CORS rule (same boundary as T-INV-01-04). Notion data flows browser ↔ loopback only; not exposed to non-loopback origins. Risk accepted — see Accepted Risks Log. Note: in current implementation `nextEvent` is the literal `"—"` for every project (Notion wire-up deferred), so no Notion data is actually surfaced yet. | closed |
| T-INV-01-08 | Repudiation | No audit trail of who fetched the projects endpoint | accept | Single-user tool per `PROJECT.md` "Single user" constraint; loopback-only binding; `log_message` no-op suppresses access logs. Risk accepted — see Accepted Risks Log. | closed |
| T-INV-01-09 | Tampering (XSS) | Script injection via project string fields (`summary`, `note`, etc.) | mitigate | All dynamic strings rendered as React text nodes (auto-escaped): `{p.name}`, `{p.status}`, `{p.summary}`, `{p.note}`, `{p.lastCommit}`, `{p.code}`, `{t.t}`, `{p.nextEvent}` — `frontend/pages/dashboard.jsx:21,24,47,55,63,69`. `grep -c dangerouslySetInnerHTML frontend/pages/dashboard.jsx` = **0**. `grep -c dangerouslySetInnerHTML frontend/data.jsx` = **0**. Error message also rendered as text node `{error.message}` — `frontend/pages/dashboard.jsx:237`. | closed |
| T-INV-01-10 | Information Disclosure | Error UI surfaces raw `error.message` with internals (URL, stack, host path) | mitigate | `fetchProjects()` sanitizes rejection: throws `new Error("HTTP " + response.status)` on non-2xx — `frontend/data.jsx:470`; outer catch re-throws `new Error("fetchProjects: " + (e.message || "network error"))` — `frontend/data.jsx:473-475`. URL `API_BASE + "/api/v1/projects"` never echoed into the thrown message. | closed |
| T-INV-01-11 | Spoofing (CSRF) | Browser silently sends credentials to cross-origin (loopback daemon) | mitigate | `fetch(API_BASE + "/api/v1/projects", { credentials: "omit" })` — explicit — `frontend/data.jsx:468`. Belt-and-suspenders with backend loopback-only CORS (T-INV-01-04). | closed |
| T-INV-01-12 | Denial of Service | Slow `/api/v1/projects` response blocks the Dashboard render | accept | Backend's 2s git timeout per project (T-INV-01-05) bounds latency; Dashboard renders a loading state ("Loading projects…" — `frontend/pages/dashboard.jsx:201`) while waiting; no browser-side timeout added in M1. Risk accepted — see Accepted Risks Log. | closed |
| T-INV-01-13 | Repudiation | Frontend has no fetch logging | accept | Single-user tool; backend daemon's stderr suffices. Risk accepted — see Accepted Risks Log. | closed |
| T-INV-01-14 | Information Disclosure | Dashboard frame-embedded on malicious site reads response | mitigate | Same loopback CORS rule as T-INV-01-04 — `bin/invisible-dashboard:258-262` (for `_send_json`) and `:340-351` (for `do_OPTIONS` preflight). Non-loopback `Origin` headers receive a 204 with NO `Access-Control-Allow-Origin` header — browser then blocks the response from being read. Frontend daemon also binds 127.0.0.1 by default. No `frame-ancestors` CSP added — explicitly out of scope for M1. | closed |
| T-INV-01-SC (01-01) | Tampering | Supply chain — new package installs (backend) | accept | No new package installs in plan 01-01; pure stdlib (`subprocess`, `hashlib`, `json`, `pathlib`, `urllib`). `pytest` is a pre-existing dev dependency. Confirmed in `01-01-SUMMARY.md` § Tech tracking → `added: []`. Risk accepted — see Accepted Risks Log. | closed |
| T-INV-01-SC (01-02) | Tampering | Supply chain — new package installs (frontend) | accept | No new package installs in plan 01-02; pure browser `fetch` + React hooks (`useEffect`, `useCallback`). React 18 + Babel-standalone loaded from unpkg via existing `<script>` tags in `frontend/index.html` (untouched by this phase). Confirmed in `01-02-SUMMARY.md` § Tech tracking → `added: []`. Risk accepted — see Accepted Risks Log. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

### Severity Ratings (OWASP ASVS L1)

| Threat ID | OWASP ASVS L1 Severity | Notes |
|-----------|-------------------------|-------|
| T-INV-01-01 | High | Command injection on a developer machine that can read arbitrary file paths from `invisible.toml`. Mitigated by list-form subprocess. |
| T-INV-01-02 | Medium | Path disclosure has reconnaissance value; full mitigation via generic error + Test 6. |
| T-INV-01-03 | High | Path traversal could let a hostile `invisible.toml` make git run in `/etc/<...>`. Mitigated at the resolver, not at git. |
| T-INV-01-04 | High | Cross-origin read of project data from any browser tab on the user's machine if `*` were used. Mitigated by exact-match origin echo. |
| T-INV-01-05 | Medium | Single-user UX; reduces UX, not a security boundary. Mitigated. |
| T-INV-01-06 | Low | Risk accepted; orchestrator-controlled writes. |
| T-INV-01-07 | Low | Risk accepted; bounded by loopback CORS. |
| T-INV-01-08 | Info | Risk accepted; single-user tool. |
| T-INV-01-09 | High | XSS would let a hostile `invisible.toml` inject scripts into the dashboard origin. Mitigated by React text-node escape policy. |
| T-INV-01-10 | Medium | URL/host info leak via Error.message. Mitigated by `fetchProjects` sanitization. |
| T-INV-01-11 | Medium | CSRF prevention; mitigated by explicit `credentials: "omit"`. |
| T-INV-01-12 | Low | Bounded by T-INV-01-05's 2s git timeout; risk accepted. |
| T-INV-01-13 | Info | Risk accepted; single-user tool. |
| T-INV-01-14 | Medium | Same boundary as T-INV-01-04; mitigated. |
| T-INV-01-SC (01-01) | Info | Risk accepted; no new package installs. |
| T-INV-01-SC (01-02) | Info | Risk accepted; no new package installs. |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-INV-01-06 | T-INV-01-06 | Python stdlib `json.loads` handles deeply-nested input safely within Python's recursion budget; `.invisible-checkpoint.json` files are written by our own orchestrator on the same machine — never user-editable in the M1 surface. Revisit if checkpoint becomes externally writable. | gsd-planner (per 01-01-PLAN.md threat_model) | 2026-05-26 |
| AR-INV-01-07 | T-INV-01-07 | Notion review titles are bounded by the same loopback CORS rule as T-INV-01-04. Data flows browser ↔ loopback dashboard only; the daemon does not relay Notion data to any outbound non-loopback caller. (Note: `nextEvent` currently returns the literal `"—"` for every project — Notion wire-up is deferred — so no Notion data is yet surfaced through `/api/v1/projects`.) | gsd-planner (per 01-01-PLAN.md threat_model) | 2026-05-26 |
| AR-INV-01-08 | T-INV-01-08 | Single-user tool per `PROJECT.md` "Single user" constraint; loopback-only binding; existing `log_message` no-op already suppresses access logs (consistent with the rest of the dashboard daemon). Audit trail is out of scope for the M1 milestone. | gsd-planner (per 01-01-PLAN.md threat_model) | 2026-05-26 |
| AR-INV-01-12 | T-INV-01-12 | Backend's 2s git timeout per project (T-INV-01-05) bounds total latency at ~N×2s where N is the project count (currently 1, expected < 10). Dashboard shows a "Loading projects…" state during the wait — no UX worse than a sluggish page. KISS for M1; revisit when project counts grow. | gsd-planner (per 01-02-PLAN.md threat_model) | 2026-05-26 |
| AR-INV-01-13 | T-INV-01-13 | Single-user tool; the dashboard daemon's stderr already serves as the operator-side debug surface. Frontend fetch logging is out of scope for the M1 milestone. | gsd-planner (per 01-02-PLAN.md threat_model) | 2026-05-26 |
| AR-INV-01-SC-01 | T-INV-01-SC (01-01) | No new package installs in plan 01-01 — implementation uses only Python stdlib (`subprocess`, `hashlib`, `json`, `pathlib`, `urllib`). `pytest` was already a project dev dependency. Existing supply-chain surface unchanged. | gsd-planner (per 01-01-PLAN.md threat_model) | 2026-05-26 |
| AR-INV-01-SC-02 | T-INV-01-SC (01-02) | No new package installs in plan 01-02 — implementation uses only browser-native `fetch` + React hooks (`useEffect`, `useCallback`) already loaded by `frontend/index.html` via unpkg `<script>` tags. `index.html` was not modified by this plan. Existing supply-chain surface unchanged. | gsd-planner (per 01-02-PLAN.md threat_model) | 2026-05-26 |

*Accepted risks do not resurface in future audit runs.*

---

## Implementation Evidence (Adversarial Grep Trail)

Every mitigation was verified by exact-grep against the implementation files. Citations below:

### Backend — `lib/api/projects.py`

```
:80-104   _safe_path() resolves repo_path; rejects anything not under $HOME or
          $INVISIBLE_HOME via Path.is_relative_to().                         [T-INV-01-03]
:107-132  _run_git(): subprocess.run([...], shell=False, capture_output=True,
          text=True, timeout=2) inside try/except for TimeoutExpired /
          FileNotFoundError / OSError.                                       [T-INV-01-01, T-INV-01-05]
:135-152  _branch_and_last_commit(): returns ("—","—") on any git failure
          (cwd missing, no commits, timeout). Worst case bounded by 2s/call. [T-INV-01-05]
:228-298  build_projects(): wraps config.load_toml() and checkpoint.load() in
          try/except; never raises to caller.                                [T-INV-01-02]
:301-321  handle_projects(): try/except wraps build_projects(); on exception
          emits handler._send_json({"error":"internal error"}, status=500);
          stderr log uses type(exc).__name__ only — no traceback, no path.   [T-INV-01-02]
```

### Backend — `bin/invisible-dashboard`

```
:249-264  _send_json(): origin = self.headers.get("Origin",""). Echoes
          Access-Control-Allow-Origin ONLY if origin.startswith("http://
          127.0.0.1:") or origin.startswith("http://localhost:"). Sets
          Vary: Origin alongside.                                            [T-INV-01-04, T-INV-01-14]
:333-351  do_OPTIONS(): preflight handler with identical loopback origin
          check. Non-loopback origins get a bare 204 with NO ACAO header —
          browser then blocks the actual fetch.                              [T-INV-01-04, T-INV-01-14]
:381-382  --host default = 127.0.0.1 (loopback bind).                        [T-INV-01-04]
:390-392  --no-auth requires --host 127.0.0.1 (refuses LAN binding without
          auth).                                                              [T-INV-01-04]
```

### Backend — `tests/test_api_projects.py`

```
:203-220  test_build_projects_does_not_leak_paths: asserts none of {str(home),
          "/Users/", "/home/"} appears in any string field of the returned
          row, even when repo_path is a broken/non-existent path containing
          the literal substring "sensitive-path".                            [T-INV-01-02]
```

### Frontend — `frontend/data.jsx`

```
:466-475  async function fetchProjects(): try { fetch(API_BASE + "/api/v1/
          projects", { credentials: "omit" }); if (!response.ok) throw new
          Error("HTTP " + response.status); ... } catch (e) { throw new
          Error("fetchProjects: " + (e.message || "network error")); }       [T-INV-01-10, T-INV-01-11]
:468      `credentials: "omit"` — explicit on the fetch call.                [T-INV-01-11]
:470      Sanitized status-code message ("HTTP <status>"); URL not echoed.   [T-INV-01-10]
:474      Outer catch sanitizes to "fetchProjects: <e.message>"; URL never
          included.                                                          [T-INV-01-10]
```

### Frontend — `frontend/pages/dashboard.jsx`

```
:21,24,47,55,63,69  All dynamic strings rendered via JSX text-node
          interpolation (`{p.name}`, `{p.status}`, `{p.summary}`, `{t.t}`,
          `{p.note}`, `{p.nextEvent}`) — React auto-escapes.                 [T-INV-01-09]
:237      Error message rendered as `{error.message}` (text node).          [T-INV-01-09, T-INV-01-10]
(file-wide) grep -c "dangerouslySetInnerHTML" → 0                           [T-INV-01-09]
```

### File-Wide Negative Invariants

```
$ grep -c "dangerouslySetInnerHTML" frontend/pages/dashboard.jsx → 0
$ grep -c "dangerouslySetInnerHTML" frontend/data.jsx          → 0
```

---

## Unregistered Flags

None.

Both `01-01-SUMMARY.md` and `01-02-SUMMARY.md` were scanned for a `## Threat Flags` section. Neither contains one. The 01-01 SUMMARY documents two CORS-hygiene additions beyond the plan (`Vary: Origin` and `Access-Control-Max-Age: 600`) — both reinforce the T-INV-01-04 mitigation surface rather than expanding attack surface, and the verifier explicitly classified them under § Deviations from Plan / Rule 2 (auto-add missing critical correctness functionality).

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-01 | 16 | 16 | 0 | gsd-secure-phase (Claude Opus 4.7, 1M context) |

**Verdict:** SECURED — all 9 `mitigate` threats verified by code grep with file:line citations; all 7 `accept` threats documented in the Accepted Risks Log with rationale.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-01
