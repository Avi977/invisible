---
phase: INV-01-three-tree-endpoints-live-folders-page
plan: 02
subsystem: folders-3source
tags: [ssh, github, gh-cli, cache, graceful-degradation, controlmaster]
requires:
  - lib/config.py::load_toml, home
  - gh CLI (authenticated as Avi977)
  - ssh client (system default; ControlMaster support — OpenSSH ≥ 5.6)
  - find with -printf (GNU find; standard on Linux VPS targets)
provides:
  - lib/api/tree_repo.py::walk_all(project=None) -> list[dict]
  - lib/api/tree_repo.py::clear_cache() -> None
  - lib/api/tree_repo.py::_derive_owner_repo(repo_path) -> tuple[str,str]|None
  - lib/api/tree_vps.py::walk_all(project=None) -> tuple[list[dict], int]
  - lib/api/tree_vps.py::VPS_NOT_CONFIGURED  # canonical empty-host error body
  - lib/api/tree_vps.py::_validate_host(host) -> bool
  - lib/api/tree_vps.py::_validate_remote_path(p) -> bool
affects:
  - bin/invisible-dashboard (Plan 03 will register /api/v1/tree/repo and /api/v1/tree/vps routes)
  - frontend/data.jsx ([[FOLDERS.repo]] and [[FOLDERS.vps]] mocks become live in Plan 03)
tech_stack:
  added: []                                          # no new pip deps (intentional)
  patterns:
    - "subprocess.run with argv list, shell=False, explicit timeout — every call"
    - "60s in-process TTL cache via module-level dict (tree_repo)"
    - "SSH ControlMaster=auto + ControlPersist=60s for multiplexed remote walks"
    - "(payload, status_code) tuple return so HTTP handler skips JSON inspection"
    - "tuple-return + early-short-circuit ordering preserves cross-walker BLOCKER #2"
key_files:
  created:
    - lib/api/tree_repo.py
    - lib/api/tree_vps.py
  modified: []
decisions:
  - "tree_vps: unknown-project filter runs BEFORE the empty-host check so walk_all(project='__nope__') is ([], 200) regardless of vps.host state — cross-walker consistency with tree_local + tree_repo (the BLOCKER #2 contract from Plan 01)"
  - "tree_repo: 60s TTL cache in a module-level dict; ample under gh's 5000/hr authenticated rate limit while letting the user mash refresh without re-paying gh latency"
  - "tree_vps: SSH/find failure returns a placeholder node {badge: unreachable} rather than raising — keeps the rest of the response intact when one project's VPS is down"
  - "Both walkers validate inputs (owner/repo regex; host regex; absolute-path regex w/ explicit '..' rejection) BEFORE shelling out — defense-in-depth on top of argv-based exec"
metrics:
  duration: "4m 31s"
  tasks_completed: 2
  files_created: 2
  files_modified: 0
  lines_added: 727
  commits: 2
  completed: "2026-05-27T02:11:52Z"
---

# Phase INV-01 Plan 02: VPS + GitHub tree walkers — Summary

JSON tree walkers for `/api/v1/tree/repo` (GitHub via `gh api`, 60s cache)
and `/api/v1/tree/vps` (SSH + remote `find` with ControlMaster
multiplexing); graceful 503 when `vps.host=""`, cross-walker consistent
empty-list response for unknown projects.

## What This Plan Delivers

- **`lib/api/tree_repo.py`** — `walk_all(project=None) -> list[dict]`.
  Derives `(owner, repo)` from each project's `git remote get-url
  origin`, validates both names against `^[A-Za-z0-9][A-Za-z0-9._-]*$`
  (T-INV01-08), then shells `gh api repos/<owner>/<repo>/git/trees/HEAD?recursive=1`
  via argv list. Flattens the response into the nested `{name, type,
  children, badge: "main", open: true}` shape that matches
  `frontend/data.jsx:151-167`. Cache keys are `owner/repo`; TTL 60s
  via the module-level `_CACHE` dict. `clear_cache()` exposed for tests
  and a future "force refresh" UI control.

- **`lib/api/tree_vps.py`** — `walk_all(project=None) -> tuple[list[dict], int]`.
  When `vps.host=""` (the dev default), returns
  `([VPS_NOT_CONFIGURED], 503)` so the frontend renders a placeholder
  instead of the daemon crashing. When configured, builds an SSH argv
  with `-o ControlMaster=auto -o ControlPath=$INVISIBLE_HOME/run/ssh-cm-%r@%h:%p
  -o ControlPersist=60s -o BatchMode=yes`, runs `find <vps_repo_path>
  -maxdepth 6 -not -path */.git* … -printf "%y %p\n"` on the remote,
  and assembles the canonical tree shape. Per-project `vps_repo_path`
  is optional — projects without it are silently skipped (VPS handoff
  is opt-in). Failed SSH leaves a `{badge: "unreachable"}` placeholder
  rather than raising.

## Return Signatures (for Plan 03's route wiring)

| Endpoint | Module fn | Signature | Status notes |
| --- | --- | --- | --- |
| `GET /api/v1/tree/repo` | `tree_repo.walk_all(project=None)` | `-> list[dict]` | Always `200` from the route's POV; the JSON list may be empty. Per-project errors are silently swallowed and logged to stderr. |
| `GET /api/v1/tree/vps` | `tree_vps.walk_all(project=None)` | `-> tuple[list[dict], int]` | Route handler should pass `status` straight to `_send_json(payload, status)`. `503` for unconfigured/invalid host; `200` otherwise (including empty list for unknown-project filter). |

## Top-Level Node Shapes (frontend contract)

- `tree_repo`: `{name: "@owner/repo", type: "folder", badge: "main",
   open: true, children: [...]}` — one node per project.
- `tree_vps`: `{name: "<project-name>", type: "folder", open: true,
   children: [{name: "<remote_root>", type: "folder", open: true,
   children: [...]}]}` — project-name wrapper around the walked
   remote root. The wrapper keeps the response shape symmetrical with
   `tree_local` and `tree_repo` (one project = one top-level node).

## Cross-Walker BLOCKER #2 Verification

All three walkers return an empty container — never `[None]` — for an
unknown project. Verified at plan close:

```
walk_local(project='__nope__') == []                           # tree_local
walk_repo (project='__nope__') == []                           # tree_repo (this plan)
walk_vps  (project='__nope__') == ([], 200)                    # tree_vps  (this plan)
```

`tree_vps` evaluates the unknown-project short-circuit BEFORE the
`vps.host` configuration check, so the contract holds even with
`vps.host=""`.

## Build-Machine Notes (for Plan 03)

- `gh auth status` ⇒ `Logged in to github.com account Avi977 (keyring)`.
  Authenticated rate limit (5000/hr) applies; the 60s cache makes
  it effectively impossible to exhaust under normal UI usage.
- `vps.host` in the live `invisible.toml` is currently `""` (dev
  default), so `tree_vps.walk_all()` will return `(payload, 503)` in
  Plan 03's integration test. Plan 03's curl probe should expect 503
  for the VPS endpoint and 200 (possibly empty) for the GitHub
  endpoint until a host is set.
- `lib/api/__init__.py` is intentionally absent — Plan 03 will create
  it (or leave it implicit if Plan 03 uses the same `sys.path.insert`
  pattern as `bin/invisible-dashboard`).

## Tasks Executed

| Task | Name | Commit | Files |
| ---- | --- | --- | --- |
| 1 | Implement `tree_repo.py` (gh-api walker with 60s cache) | `baf1628` | `lib/api/tree_repo.py` |
| 2 | Implement `tree_vps.py` (SSH find walker with 503 graceful degradation) | `3224bed` | `lib/api/tree_vps.py` |

## Verification Run

```
$ python3 -c "import sys; sys.path.insert(0, 'lib'); \
    from api.tree_repo import walk_all, clear_cache, _derive_owner_repo; \
    clear_cache(); \
    assert walk_all(project='__does_not_exist__') == []; \
    print('structural OK')"
structural OK

$ python3 -c "import sys; sys.path.insert(0, 'lib'); \
    from api.tree_vps import walk_all, VPS_NOT_CONFIGURED, _validate_host, _validate_remote_path; \
    payload, status = walk_all(); \
    assert isinstance(payload, list) and isinstance(status, int); \
    up, us = walk_all(project='__does_not_exist__'); \
    assert up == []; \
    assert _validate_host('user@host.example.com') is True; \
    assert _validate_host('host; rm -rf /') is False; \
    assert _validate_remote_path('/srv/app') is True; \
    assert _validate_remote_path('/etc/../etc') is False; \
    print('OK status=', status)"
OK status= 503
```

Extra cross-walker + injection-attempt smoke tests also pass (see
session log for the full battery: `;`, `|`, `$`, backtick, spaces in
hostnames; `..` and non-absolute paths; non-GitHub remote URLs).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] `tree_vps.walk_all` short-circuit ordering**

- **Found during:** Task 2 verify.
- **Issue:** The plan's `<action>` section described the empty-host
  check before the project-filter check, but the plan's verify
  command simultaneously asserted `walk_all() -> status=503` (which
  needs the empty-host branch) AND `walk_all(project='__nope__') ->
  ([], 200)` (which needs the unknown-project branch). Both cannot
  hold with `vps.host=""` unless the unknown-project filter runs
  first.
- **Fix:** Moved the `if project is not None / matched is None
  → ([], 200)` short-circuit to run BEFORE the `host == ""
  → ([VPS_NOT_CONFIGURED], 503)` check. This also matches the
  semantic intent: "no such project" is the same answer regardless
  of whether the VPS layer is configured, and it preserves the
  cross-walker BLOCKER #2 contract (the BLOCKER #2 fix is supposed
  to be invariant across configuration states).
- **Files modified:** `lib/api/tree_vps.py` (one block re-ordered;
  docstring updated to reflect evaluation order).
- **Commit:** `3224bed` (the only `tree_vps` commit — the fix
  landed before the first commit of that file).

No other deviations. No package installs. No `[ASSUMED]` / `[SUS]`
flags from the threat register. All security gates (T-INV01-07
through T-INV01-11) have argv/regex/timeout mitigations in place;
T-INV01-12 is the documented `accept` (rely on user's
`~/.ssh/known_hosts`).

## Known Stubs

None. `_walk_remote` returns a `{badge: "unreachable"}` placeholder
on SSH failure, but that's intentional graceful degradation (and
documented in the module docstring), not a stub.

## Files Created

- `lib/api/tree_repo.py` (317 lines)
- `lib/api/tree_vps.py` (410 lines)

Both modules satisfy the plan's `min_lines` floors (100 and 80
respectively) with comfortable margin — the extra lines are
docstring and inline rationale, kept verbose because both modules
sit on a security-sensitive trust boundary (config → argv) and the
intent of every guard needs to survive future drive-by edits.

## Self-Check: PASSED

- [x] `lib/api/tree_repo.py` exists (317 lines).
- [x] `lib/api/tree_vps.py` exists (410 lines).
- [x] Commit `baf1628` exists on `ws/folders-3source`.
- [x] Commit `3224bed` exists on `ws/folders-3source`.
- [x] Plan structural-verify assertions pass.
- [x] Cross-walker BLOCKER #2 contract holds across all three walkers.
- [x] No files outside `lib/api/{tree_repo,tree_vps}.py` were modified
  in the per-task commits (STATE.md, ROADMAP.md, SUMMARY.md land in
  a separate `docs(INV-01-02)` metadata commit).
