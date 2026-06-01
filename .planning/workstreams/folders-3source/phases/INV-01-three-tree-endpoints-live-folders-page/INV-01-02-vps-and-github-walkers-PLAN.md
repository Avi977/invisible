---
phase: INV-01-three-tree-endpoints-live-folders-page
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - lib/api/tree_vps.py
  - lib/api/tree_repo.py
autonomous: true
requirements:
  - REQ-03
tags:
  - ssh
  - github
  - gh-cli
  - cache
  - graceful-degradation

must_haves:
  truths:
    - "GET /api/v1/tree/repo returns the GitHub tree for each project (via gh api repos/<owner>/<repo>/git/trees/HEAD?recursive=1)."
    - "GitHub tree responses are cached in-process for 60 seconds to stay under the gh rate limit."
    - "GET /api/v1/tree/vps returns the VPS-side tree via SSH-driven find, multiplexed via ControlMaster."
    - "GET /api/v1/tree/vps returns HTTP 503 with body {\"error\":\"vps.host not configured\"} when vps.host is empty in invisible.toml."
    - "Per-project filtering works via ?project=<name> for both endpoints (returns only that project's subtree)."
    - "walk_all(project='<unknown>') returns [] (empty list) — never [None] — in both tree_repo and tree_vps, consistent with tree_local."
    - "Neither walker shells out with shell=True or interpolates user-controlled config strings into a shell-parsed command line."
  artifacts:
    - path: "lib/api/tree_vps.py"
      provides: "walk_all(project=None) -> tuple[list[dict], int] — returns (tree, status_code). status=200 with tree on success, status=503 with [{'error':'…'}] when vps.host empty."
      min_lines: 80
      exports: ["walk_all", "VPS_NOT_CONFIGURED"]
    - path: "lib/api/tree_repo.py"
      provides: "walk_all(project=None) -> list[dict]. Cached for 60s via _TTLCache."
      min_lines: 100
      exports: ["walk_all", "clear_cache"]
  key_links:
    - from: "lib/api/tree_vps.py::walk_all"
      to: "ssh subprocess"
      via: "argv list (no shell=True), uses -o ControlPath= for multiplex"
      pattern: "subprocess\\.run.*\\[.*ssh"
    - from: "lib/api/tree_repo.py::walk_all"
      to: "gh CLI subprocess"
      via: "argv list invoking gh api repos/<owner>/<repo>/git/trees/HEAD?recursive=1"
      pattern: "gh.*api.*repos"
---

<objective>
Build two backend tree walkers that complete the three-source story:
- `lib/api/tree_repo.py` — GitHub tree per project via `gh api`, with 60-second in-process cache.
- `lib/api/tree_vps.py` — VPS tree via SSH + `find`, with explicit 503 graceful degradation when `vps.host` is empty.

Purpose: Without these, the Folders page can only show local files. The VPS walker must NOT crash the daemon when `vps.host=""` (today's reality); it must return a clear 503 so the frontend can render a placeholder. The GitHub walker must respect `gh` rate limits.

Output: Two Python modules consumed by `bin/invisible-dashboard` in Plan 03. Output shape matches the tree-node contract from `frontend/data.jsx`.

**Cross-walker consistency note (BLOCKER #2 fix):** All three walkers (`tree_local`, `tree_repo`, `tree_vps`) MUST treat unknown or unsafe project names as empty lists, never `[None]`. The single-project branch of `walk_all` must filter out a None result from the underlying per-project lookup. This protects the frontend TreeNode renderer from null-deref crashes when the dashboard's "Dive in" flow hits an unknown project.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/REQUIREMENTS.md
@.planning/workstreams/folders-3source/ROADMAP.md
@.planning/workstreams/folders-3source/STATE.md

@frontend/data.jsx
@bin/invisible-dashboard
@lib/config.py
@invisible.toml.example

<interfaces>
<!-- Tree-node shape (same as Plan 01 — single source of truth):
     { "name": str, "type": "folder"|"file", "children"?: [...], "badge"?: str, "open"?: bool }

     The top-level response shape for each endpoint:
     [ { "name": "<project-name>", "type": "folder", "open": true, "children": [...] }, ... ] -->

invisible.toml relevant sections:
```toml
[vps]
host = ""                              # empty in dev — endpoint must return 503
identity = "~/.ssh/id_ed25519"
use_mosh = false

[[projects]]
name = "jobslayer"
repo_path = "~/Projects/jobslayer"     # used to derive owner/repo for tree_repo via `git remote get-url origin`, OR
# repo_url = "github.com/Avi977/jobslayer"  # NOT in current schema; use git remote
# vps_repo_path = "/srv/jobslayer"     # OPTIONAL: present only if VPS handoff configured. If missing for a project, skip that project in tree_vps output.
```

lib/config.py exports:
- `load_toml() -> dict` returns parsed toml; `cfg.get("vps", {}).get("host", "")` and `cfg.get("projects", [])` are the relevant lookups.

`gh` CLI:
- Authenticated as `Avi977`.
- Tree call: `gh api repos/<owner>/<repo>/git/trees/HEAD?recursive=1` returns JSON `{tree: [{path, type, sha, size?}, ...], truncated: bool}` where `type` is `"blob"` or `"tree"`.
- Rate-limited (5000/hr authenticated, 60/hr unauthenticated) — the 60s cache protects against the user mashing refresh.

SSH multiplexing (from PROJECT.md "VPS connection is non-negotiable"):
- ControlMaster path convention: `~/.ssh/cm-%r@%h:%p`
- For invisible, use a dedicated path under `$INVISIBLE_HOME/run/ssh-cm-%r@%h:%p` so we don't collide with the user's own ssh sessions.
- First call opens the master with `-o ControlMaster=auto -o ControlPersist=60s`; subsequent calls reuse it (fast).
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Implement lib/api/tree_repo.py (gh-api walker with 60s cache)</name>
  <files>lib/api/tree_repo.py</files>
  <read_first>
    - lib/config.py (entire file — uses `load_toml()`, `home()`)
    - invisible.toml.example (the `[[projects]]` shape — fields `name`, `repo_path`; there is NO `repo_url` field, so owner/repo must be derived from `git remote get-url origin` inside the repo_path)
    - frontend/data.jsx:151-167 (the GitHub mock shape — confirms top-level nodes are `{name: "@you/<repo>", type: "folder", badge: "main", children: [{name: "<dir>", type: "folder"}, ...]}` — flatten the gh tree response into this shape)
    - bin/invisible-dashboard:1-60 (header doc — confirms that the daemon shells out for `gh` operations and never uses PyGithub)
  </read_first>
  <action>
    First, ensure the parent directory exists: `mkdir -p lib/api` (idempotent; safe for Wave 1 parallelism with Plan 01 which also creates files under `lib/api/`).

    Create `lib/api/tree_repo.py`.

    Imports: `from __future__ import annotations`, `subprocess`, `json`, `re`, `time`, `os`, `pathlib.Path`, `typing.Any`, `from config import load_toml`.

    **Module-level cache:**
    ```
    _CACHE: dict[str, tuple[float, list[dict]]] = {}   # key -> (expires_at, tree)
    _CACHE_TTL_S = 60
    ```
    Implement `clear_cache() -> None` that empties `_CACHE` (used by tests / forced refresh).

    **`_derive_owner_repo(repo_path: str) -> tuple[str, str] | None`:**
    - `path = Path(os.path.expanduser(repo_path))`; if not a directory, return None.
    - Run `subprocess.run(["git", "-C", str(path), "remote", "get-url", "origin"], capture_output=True, text=True, timeout=5)`.
    - If returncode != 0 or empty stdout, return None.
    - Parse the URL with a regex that handles both SSH (`git@github.com:owner/repo.git`) and HTTPS (`https://github.com/owner/repo.git`) forms: `re.match(r"(?:git@github\.com:|https?://github\.com/)([^/]+)/([^/.]+)", url.strip())`.
    - **Validation gate (T-INV01-08):** `owner` and `repo` MUST each match `^[A-Za-z0-9][A-Za-z0-9._-]*$`. Reject otherwise (return None). This prevents shell-meta or path-meta characters from a maliciously crafted git remote from reaching the `gh api` argv.
    - Return `(owner, repo)` or None.

    **`_fetch_tree(owner: str, repo: str) -> list[dict]`:**
    - Cache key: `f"{owner}/{repo}"`. If `_CACHE` has a non-expired entry, return it.
    - Run `subprocess.run(["gh", "api", f"repos/{owner}/{repo}/git/trees/HEAD?recursive=1"], capture_output=True, text=True, timeout=15)`.
      - Use `shell=False` (default — but document the choice inline).
      - Pass arguments as a list, never as a single string.
    - On non-zero return, return `[]` (do not raise — caller is the HTTP handler and should still respond 200 with a possibly-empty tree). Log to stderr with `sys.stderr.write(...)`.
    - Parse JSON. If the response has `"truncated": true`, log a stderr warning and continue with whatever was returned (gh truncates at 100k files; document the limitation in the module docstring).
    - Convert the flat `[{path, type}]` list into the nested tree shape:
      - Build a root dict; for each entry, split `path.split("/")`, walk/create dicts along the way. `type=="blob"` → `{"name": leaf, "type": "file"}`; `type=="tree"` → `{"name": leaf, "type": "folder", "children": []}`.
      - Implementation hint: use a recursive helper `_insert(node_list, parts, kind)`.
    - Cache as `_CACHE[key] = (time.time() + _CACHE_TTL_S, tree)` and return `tree`.

    **`_walk_one(p: dict) -> dict | None`** (extracted helper so the single- and multi-project branches share logic):
    - `owner_repo = _derive_owner_repo(p["repo_path"])`; return `None` if None.
    - `subtree = _fetch_tree(*owner_repo)`.
    - Return `{"name": f"@{owner_repo[0]}/{owner_repo[1]}", "type": "folder", "badge": "main", "open": True, "children": subtree}`.

    **`walk_all(project: str | None = None) -> list[dict]`:**
    - Load `cfg = load_toml()`.
    - If `project` is given: find the matching `p` in `cfg.get("projects", [])`. If not found, return `[]`. Otherwise compute `node = _walk_one(p)` and return `[node]` if `node is not None` else `[]`. **Never return `[None]`** — this is the cross-walker BLOCKER #2 fix.
    - Otherwise iterate `cfg.get("projects", [])`, call `_walk_one(p)` for each, filter out Nones, return the list.
    - Empty list is a valid response (frontend renders "no repos").
  </action>
  <verify>
    <automated>cd "$INVISIBLE_HOME" && python3 -c "import sys; sys.path.insert(0, 'lib'); from api.tree_repo import walk_all, clear_cache, _derive_owner_repo; assert callable(walk_all) and callable(clear_cache) and callable(_derive_owner_repo), 'all three symbols must be callable'; clear_cache(); t = walk_all(project='__does_not_exist__'); assert t == [], f'unknown project must return [], got {t!r}'; print('structural OK')"</automated>
  </verify>
  <done>
    - `lib/api/tree_repo.py` exists with `walk_all`, `clear_cache`, `_derive_owner_repo`, `_fetch_tree`, `_walk_one`, and the `_CACHE` / `_CACHE_TTL_S` module state.
    - `_derive_owner_repo` validates owner/repo against `^[A-Za-z0-9][A-Za-z0-9._-]*$` (security gate T-INV01-08).
    - All subprocess calls use a list argv with `shell=False`.
    - `walk_all(project="__nope__")` returns `[]`, never `[None]` (BLOCKER #2 fix; cross-walker consistency with `tree_local`).
    - Calling `walk_all()` twice in under 60s makes only one `gh api` call per project (cache hit on the second call). Confirm by stubbing `subprocess.run` in a quick scratch test if needed, or rely on the integration test in Plan 03.
    - Top-level node shape matches `data.jsx:151-167`: `{name: "@owner/repo", type: "folder", badge: "main", open: true, children: [...]}`.
    - Verify is **structural-only / no network round-trip** — `walk_all(project='__nope__')` short-circuits before any `gh api` call, so the gate does not require GitHub connectivity (WARNING #4 fix from checker pass).
  </done>
</task>

<task type="auto">
  <name>Task 2: Implement lib/api/tree_vps.py (SSH find walker with 503 graceful degradation)</name>
  <files>lib/api/tree_vps.py</files>
  <read_first>
    - lib/config.py (uses `load_toml()`, `home()`)
    - invisible.toml.example:3-7 (the `[vps]` block — note `host = ""` is the dev default; the endpoint MUST handle this)
    - frontend/data.jsx:131-150 (the VPS mock shape — top-level nodes are absolute paths like `/srv`, `/var/log`, `/home/dev` with `children`)
    - bin/invisible-dashboard:212-265 (DashboardHandler — Wave 2 will check `status` returned from this module and pass to `_send_json(obj, status)`)
  </read_first>
  <action>
    Ensure the parent directory exists: `mkdir -p lib/api` (idempotent; harmless if Plan 01 / Task 1 already created it).

    Create `lib/api/tree_vps.py`.

    Imports: `from __future__ import annotations`, `subprocess`, `os`, `re`, `sys`, `pathlib.Path`, `typing.Any`, `from config import load_toml, home`.

    **Constants:**
    ```
    VPS_NOT_CONFIGURED = {"error": "vps.host not configured"}
    MAX_DEPTH = 6                          # find -maxdepth
    SSH_TIMEOUT_S = 15
    _IGNORE_DIRS = (".git", "node_modules", ".venv", "venv", "__pycache__")
    ```

    **`_cm_path() -> str`:**
    - Return the ControlMaster socket path: `str(home() / "run" / "ssh-cm-%r@%h:%p")`.
    - Ensure `home() / "run"` exists: `(home() / "run").mkdir(parents=True, exist_ok=True)`.

    **`_ssh_argv(host: str, identity: str, *remote_cmd: str) -> list[str]`:**
    - Returns the argv for an SSH call.
    - `["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={SSH_TIMEOUT_S}", "-o", "ControlMaster=auto", "-o", f"ControlPath={_cm_path()}", "-o", "ControlPersist=60s", "-i", os.path.expanduser(identity), host, "--", *remote_cmd]`
    - Use `--` to terminate option parsing before the remote command list — guards against an exotic remote path starting with `-`.
    - Note: every argument is a separate list element; `shell=False` at the call site.

    **`_validate_host(host: str) -> bool`:**
    - Allow `^(?:[a-zA-Z0-9_.-]+@)?[a-zA-Z0-9.-]+$` (user@hostname or hostname only). Reject any host containing `;`, `|`, `$`, backticks, spaces, or `&`. Return False if regex does not match.
    - This is a defense-in-depth guard; the argv-based subprocess already prevents shell injection, but rejecting bad hosts surfaces config bugs early.

    **`_validate_remote_path(p: str) -> bool`:**
    - Must start with `/`, must not contain `..`, must match `^/[A-Za-z0-9_./~+-]+$`.

    **`_walk_remote(host: str, identity: str, remote_root: str) -> dict`:**
    - Build the find argv: `["find", remote_root, "-maxdepth", str(MAX_DEPTH), "-not", "-path", "*/.git*", "-not", "-path", "*/node_modules*", "-not", "-path", "*/__pycache__*", "-printf", "%y %p\\n"]`.
      - `%y` is `f` (file), `d` (directory), `l` (symlink), etc.; `%p` is the path.
      - `\n` is a newline that the shell on the remote will see literally (find -printf format string).
    - Run `subprocess.run(_ssh_argv(host, identity, *find_argv), capture_output=True, text=True, timeout=SSH_TIMEOUT_S)`.
    - On non-zero return: write to stderr, return `{"name": remote_root, "type": "folder", "children": [], "badge": "unreachable"}` (do not raise).
    - Parse each stdout line: `kind, path = line.split(" ", 1)`. Skip symlinks (kind == "l") to mirror the local walker's symlink policy.
    - Bucket entries by path components into a nested dict tree rooted at `remote_root`. (Same `_insert` helper pattern as `tree_repo.py` — consider sharing via a tiny helper module if time allows, but a copy is acceptable here.)
    - Return the root node with `{"name": remote_root, "type": "folder", "open": True, "children": [...]}`.

    **`walk_all(project: str | None = None) -> tuple[list[dict], int]`:**
    - Returns `(payload, status_code)`. The status code lets the HTTP handler in Plan 03 set 503 cleanly without needing to inspect the payload.
    - Load `cfg = load_toml()`.
    - `vps_cfg = cfg.get("vps", {})`; `host = vps_cfg.get("host", "").strip()`.
    - If `host == ""`: return `([VPS_NOT_CONFIGURED], 503)`. The route handler will translate this to a 503 JSON response.
    - If `_validate_host(host) is False`: return `([{"error": f"invalid vps.host: {host!r}"}], 503)`.
    - `identity = vps_cfg.get("identity", "~/.ssh/id_ed25519")`.
    - Build the project list:
      - If `project` is given: find the matching project in `cfg.get("projects", [])`. If not found, return `([], 200)` — unknown project is empty, not an error.
      - Otherwise iterate `cfg.get("projects", [])`.
      - For each project, look up `vps_repo_path` (optional field per invisible.toml.example:23). If missing, skip the project (do not error — VPS handoff is per-project opt-in).
      - If present, validate with `_validate_remote_path`. Skip if invalid (log to stderr).
    - For each `(project_name, vps_path)`, call `_walk_remote(host, identity, vps_path)`, wrap as `{"name": project_name, "type": "folder", "open": True, "children": [<the walked node>]}` (keeps the top-level node-per-project shape).
    - **Filter Nones** (defense-in-depth): if any wrapped node ends up None for any reason, omit it from the returned list. Never emit `[None]` — cross-walker consistency with BLOCKER #2.
    - Return `(list_of_top_level_nodes, 200)`.

    Add a module docstring documenting: the (payload, status) return contract, that the empty-host case is intentional (not an error), that an unknown project returns `([], 200)`, ControlMaster details, and that this never shells out with `shell=True`.
  </action>
  <verify>
    <automated>cd "$INVISIBLE_HOME" && python3 -c "import sys; sys.path.insert(0, 'lib'); from api.tree_vps import walk_all, VPS_NOT_CONFIGURED, _validate_host, _validate_remote_path; payload, status = walk_all(); assert isinstance(payload, list) and isinstance(status, int), f'walk_all must return (list,int), got ({type(payload)},{type(status)})'; assert status in (200, 503), f'status must be 200 or 503, got {status}'; up, us = walk_all(project='__does_not_exist__'); assert up == [], f'unknown project must return [], got {up!r}'; assert _validate_host('user@host.example.com') is True; assert _validate_host('host; rm -rf /') is False; assert _validate_remote_path('/srv/app') is True; assert _validate_remote_path('/etc/../etc') is False; print('OK status=', status)"</automated>
  </verify>
  <done>
    - `lib/api/tree_vps.py` exists with `walk_all`, `VPS_NOT_CONFIGURED`, `_validate_host`, `_validate_remote_path`, `_walk_remote`, `_ssh_argv`, `_cm_path`.
    - `walk_all()` returns `(payload, status)` with `status=503` and `payload=[{"error":"vps.host not configured"}]` when the dev-default `vps.host=""` is set.
    - `walk_all()` returns `(payload, 200)` when vps.host is set and projects have `vps_repo_path`.
    - `walk_all(project='__nope__')` returns `([], 200)` — unknown project is empty, never `[None]` (cross-walker BLOCKER #2 fix).
    - Host validation rejects shell-meta characters; path validation rejects `..` and non-absolute paths.
    - All subprocess calls use argv lists, never `shell=True`, never f-string interpolation into a single command string.
    - `_cm_path()` creates `$INVISIBLE_HOME/run/` if missing, returns the ControlMaster socket template.
    - End-to-end HTTP/curl verification is in Plan 03.
  </done>
</task>

</tasks>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| invisible.toml `[vps].host` → subprocess argv | Config-controlled; even though argv-based exec prevents shell injection, a malformed host wastes resources on a doomed SSH attempt |
| invisible.toml `[[projects]].repo_path` → `git remote get-url` → owner/repo regex → `gh api` argv | A maliciously-crafted git remote could inject `..` or shell-meta into the gh API path. Owner/repo regex validation closes this |
| invisible.toml `[[projects]].vps_repo_path` → find argv on remote host | Remote path is sent as a separate argv element; validated against `_validate_remote_path` to reject `..` and non-absolute paths |
| gh CLI rate limit | 5000 req/hr authenticated; without the 60s cache, a chatty UI could hit the limit |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-INV01-07 | Tampering / Command Injection | SSH argv construction in `_ssh_argv` | mitigate | Argv list (not string), `shell=False` everywhere, `--` separator before remote command, `BatchMode=yes` so no interactive prompts. `_validate_host` rejects shell-meta in the host string (Task 2) |
| T-INV01-08 | Tampering / Command Injection | `gh api repos/<owner>/<repo>/...` | mitigate | Owner and repo each validated against `^[A-Za-z0-9][A-Za-z0-9._-]*$` after parsing from `git remote get-url`; argv list passed to `subprocess.run`; `shell=False` (Task 1) |
| T-INV01-09 | Information Disclosure | remote find on VPS | mitigate | `vps_repo_path` validated against `_validate_remote_path` (no `..`, absolute path required); `find -maxdepth 6` caps tree size; symlinks excluded from output (Task 2) |
| T-INV01-10 | Denial of Service | unauthenticated gh API rate limit | mitigate | 60s in-process TTL cache per (owner, repo); `truncated:true` from gh logged but not retried (Task 1) |
| T-INV01-11 | Denial of Service | hanging SSH connection | mitigate | `ConnectTimeout=15`, `subprocess.run(..., timeout=15)`, `BatchMode=yes` (never prompts for password) (Task 2) |
| T-INV01-12 | Spoofing | SSH host key check | accept | Relies on the user's `~/.ssh/known_hosts` — we don't disable `StrictHostKeyChecking`. First-run UX: the user must SSH manually once to accept the host key. Documented in the module docstring |
| T-INV{phase}-SC | Tampering | `gh` CLI binary | accept | `gh` is GitHub's official CLI, installed via Homebrew or apt. No `pip install` of an `[ASSUMED]` package in this plan — only invokes existing local binaries (`gh`, `ssh`, `git`, `find`). Package legitimacy gate is not triggered |

No new pip packages added in this plan. No `[ASSUMED]` / `[SUS]` flags. The blocking-human-checkpoint requirement from the planner system prompt does not apply (no installs).

</threat_model>

<verification>
- `lib/api/tree_repo.py` and `lib/api/tree_vps.py` both importable: `python3 -c "from api import tree_repo, tree_vps"` (with `lib/` on path) succeeds.
- `tree_vps.walk_all()` with the current dev-default `vps.host=""` returns `(payload, 503)` with the `VPS_NOT_CONFIGURED` body.
- `tree_repo.walk_all(project='__nope__')` returns `[]` (structural check, no network round-trip).
- `tree_vps.walk_all(project='__nope__')` returns `([], 200)`.
- Both modules validate inputs before shelling out; no `shell=True`; no f-string command interpolation.
- All subprocesses have a `timeout=`.
- End-to-end curl verification deferred to Plan 03.
</verification>

<success_criteria>
- Two files (`lib/api/tree_repo.py`, `lib/api/tree_vps.py`) checked in.
- `walk_all()` functions match the contracts above (list-of-dicts for repo, tuple for vps).
- All three walkers (this plan's two + Plan 01's `tree_local`) return `[]` (or `([], 200)`) for unknown projects — never `[None]`.
- The `vps.host=""` graceful-degradation path is the first thing exercised by Plan 03's wiring tests.
- The 60s GitHub cache is in place.
- No security gate (T-INV01-07 through T-INV01-11) accepted without mitigation.
</success_criteria>

<output>
Create `.planning/workstreams/folders-3source/phases/INV-01-three-tree-endpoints-live-folders-page/INV-01-02-SUMMARY.md` when done. Include:
- The exact return signatures (`walk_all(project=None) -> list[dict]` for repo, `walk_all(project=None) -> tuple[list[dict], int]` for vps) so Plan 03's route registration uses them correctly.
- Whether the build machine has `gh` authenticated as `Avi977` (test: `gh auth status`) — if not, the integration test in Plan 03 will skip rather than fail.
- The exact top-level node shape returned by each (`@owner/repo` for repo; project-name wrapper for vps) so the frontend in Plan 03 can render consistently across all three sources.
- Confirmation that both walkers return `[]` for unknown projects (cross-walker BLOCKER #2 fix verified).
</output>
</output>
