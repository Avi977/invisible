---
phase: 01-api-v1-relations-relations-page-wired
reviewed: 2026-06-02T10:30:00Z
depth: deep
reviewer: gsd-code-reviewer (Claude Opus 4.7)
files_reviewed: 4
files_reviewed_list:
  - lib/api/relations.py
  - lib/api/__init__.py
  - bin/invisible-dashboard
  - frontend/pages/relations.jsx
findings:
  critical: 0
  blocker: 0
  warning: 3
  medium: 4
  low: 6
  info: 5
  total: 18
status: issues
---

# Phase 1 Code Review — `relations-page` workstream

**Verdict:** `status: issues` (no blockers; ship-ready with caveats logged).

The implementation is competent. The backend mirrors the sibling patterns in `lib/api/projects.py` and `lib/api/tree_local.py` accurately, the slug-validation gate is honored before any FS/Notion call, and the threat-model mitigations T-01-01-01 through T-01-01-07 are observable in code. The frontend self-fetching shell is clean and the four-branch render is correct.

That said, the deep review surfaced **3 WARNING** items worth tightening before the next plan in this workstream lands and **4 MEDIUM** items that are latent / depend-on-config-shape but not currently exploitable. No CRITICAL/BLOCKER findings.

## Summary table

| ID | Severity | File | Line(s) | Summary |
|----|----------|------|---------|---------|
| WR-01 | WARNING | `frontend/pages/relations.jsx` | 213-217, 303 | Fetch race: stale `error` state can mask a successful subsequent fetch (rapid Retry click) |
| WR-02 | WARNING | `lib/api/relations.py` | 236-240 | `_project_root("invisible")` returns `config.home()` *unresolved*; if the path crosses any symlink, JSX import edges are silently dropped |
| WR-03 | WARNING | `lib/api/relations.py` | 686-712 | Endpoint deriver emits ID with a `/` separator (`bin/invisible-dashboard`) while every other module ID uses `.` — breaks grep cross-ref matching for any doc that mentions the dashboard |
| ME-01 | MEDIUM | `lib/api/relations.py` | 91, 861, 873 | Cache-key collision: a slug literally `"__all__"` validates against `PROJECT_SLUG_RE` and collides with the aggregate key |
| ME-02 | MEDIUM | `lib/api/relations.py` | 91 | `PROJECT_SLUG_RE` accepts leading `-`/`--` (e.g. `-rf`, `--`); sibling `tree_repo.py:_NAME_RE` requires first-char alphanumeric. Hardening regression. Not exploitable today (slug never enters argv) but invites future bug. |
| ME-03 | MEDIUM | `lib/api/relations.py` | 622-650 | Grep deriver is O(docs × patterns) with ~60 docs × hundreds of patterns; every doc is re-scanned for every basename. Functional but the loop ordering invites a DoS once `.planning/` grows. Out of strict v1 scope (perf) but borderline correctness because it directly feeds the 50–500 sanity bound. |
| ME-04 | MEDIUM | `frontend/pages/relations.jsx` | 223-233 | `Header` component is defined *inside* `Relations()` — re-created on every render, causing React to unmount/remount it. Harmless today (no internal state) but lays a trap for any future state added to Header. |
| LO-01 | LOW | `lib/api/relations.py` | 829-947 | `build_graph` returns the *same* cached dict to every caller (no copy). Safe iff no caller mutates; not enforced by code. |
| LO-02 | LOW | `frontend/pages/relations.jsx` | 153-161 | `<line key={i}>` uses array index as React key; when filter toggles reorder `visibleEdges`, React reconciles unnecessarily. |
| LO-03 | LOW | `frontend/pages/relations.jsx` | 109-121 | `useEffectG` drag handler reads `wrapRef.current.getBoundingClientRect()` without a null-check — race if component unmounts mid-drag. |
| LO-04 | LOW | `lib/api/__init__.py` | 30-37 | Orphan triple-quoted string literal between `__all__` and the deferred `from . import` lines — dead code, not a docstring (the module docstring is already at the top). |
| LO-05 | LOW | `lib/api/__init__.py` | 29, 38-41 | `__all__` lists only `["ROUTES", "projects", "relations"]` but the file also imports `chat`, `tree_local`, `tree_vps`, `tree_repo` as side-effect re-exports. Inconsistent. |
| LO-06 | LOW | `frontend/pages/relations.jsx` | 90, 98 | `layoutNodes()` runs twice on mount — once via `useStateG` lazy init, then immediately again via `useEffectG` with same input. Wasted compute. |
| IN-01 | INFO | `lib/api/relations.py` | 390-398 | AST walker ignores `from . import X` (relative) imports — `node.module` is `None`. Acceptable limitation; not documented. |
| IN-02 | INFO | `lib/api/relations.py` | 538-543 | Binary sniff loads entire file via `read_bytes()[:512]` instead of opening + reading 512 bytes. Up to 2× I/O per `.md` file. |
| IN-03 | INFO | `frontend/pages/relations.jsx` | 229-230 | "Force layout" + "Tag view" buttons render but have no `onClick` handler — non-functional UI. |
| IN-04 | INFO | `lib/api/relations.py` | 763-808 | Notion edge construction does not dedupe per-page — a Notion page that lists the same relation twice would emit duplicate edges. Very unlikely. |
| IN-05 | INFO | `frontend/pages/relations.jsx` | 31-40 | `fetch()` has no `AbortController` / client-side timeout — already acknowledged in plan threat model T-01-02-04 (`accept`). Not a finding so much as a documented deferred. |

---

## Warnings

### WR-01 — Stale-error race condition in Relations fetch shell

**File:** `frontend/pages/relations.jsx:213-217, 303`

**Issue.** The loader is:

```jsx
const loadGraph = useCallbackG(() => {
  setError(null);
  setData(null);
  fetchRelations("invisible").then(setData).catch(setError);
}, []);
```

Consider the sequence (a real user can produce this in <500ms):
1. Page mounts → `loadGraph()` fires; fetch #1 starts.
2. Fetch #1 fails after 1.5s (backend down) → `setError(err1)`.
3. User clicks **Retry** → `loadGraph()` fires: `setError(null); setData(null);` then fetch #2 starts.
4. Fetch #2 *succeeds* and calls `setData(result)`.

Order of state updates from React's perspective:
- `setError(null)` from step 3.
- `setData(null)` from step 3.
- `setData(result)` from step 4.
- State settles: `data = result, error = null`. UI shows graph. **OK in this ordering.**

But the failure mode is when fetch #1's `.catch(setError)` resolves **after** the user already clicked Retry:
1. Fetch #1 still pending.
2. User clicks Retry → `setError(null); setData(null);` fetch #2 starts.
3. Fetch #2 *succeeds* → `setData(result)`.
4. Fetch #1 (slow) finally rejects → `setError(err1)`.
5. Final state: `data = result, error = err1`. **The render check `if (error)` runs before `if (!data.nodes)`, so the error UI is shown despite a successful data load.**

This is a real concurrency bug — the "Show empty" button (line 303) is also affected because it sets `data` while leaving `error` cleared in only one of two ordering branches.

**Fix.** Either (a) sequence-number the loads and ignore stale resolutions, or (b) chain the success path so `setError(null)` always runs alongside `setData`:

```jsx
const loadGraph = useCallbackG(() => {
  const seq = ++loadSeqRef.current;
  setError(null); setData(null);
  fetchRelations("invisible").then(
    (d) => { if (seq === loadSeqRef.current) { setData(d); setError(null); } },
    (e) => { if (seq === loadSeqRef.current) { setError(e); } },
  );
}, []);
```

Add `const loadSeqRef = useRefG(0);` at the top of `Relations()`.

---

### WR-02 — `_project_root("invisible")` returns unresolved path; JSX edges silently dropped on symlinks

**File:** `lib/api/relations.py:236-240`

**Issue.** The SPECIAL CASE branch is:

```python
if slug == "invisible":
    try:
        return config.home()
    except Exception:
        return None
```

`config.home()` returns `Path(os.path.expanduser(os.environ.get("INVISIBLE_HOME", "~/.invisible")))` — **no `.resolve()` call**. If `INVISIBLE_HOME` ever points through a symlink, the returned `project_root` is the symlink path, but later in `_derive_import_edges` line 410 the JSX path resolution does:

```python
candidate = (importer_dir / spec).resolve()   # canonicalizes through symlinks
if not candidate.is_relative_to(project_root):  # project_root is NOT canonicalized
    continue                                    # silently dropped!
```

I reproduced this in a sandbox: with `INVISIBLE_HOME=/tmp/symlink → /tmp/real`, every JSX edge gets dropped because `candidate` resolves to `/private/tmp/real/...` while `project_root` is `/tmp/symlink`. Symptom: the graph has fewer edges than expected, but no error / no warning.

The plan's `must_haves.truths` (line 23 of 01-01-PLAN.md) calls out the symlink boundary explicitly: *"The Python AST walker scans only files under the resolved project root (bounded); symbolic links pointing outside that root are NOT followed."* The current code is correct on the *security* side (symlinks outside are blocked) but wrong on the *containment* side (legitimate symlinked roots break).

**Why it didn't surface in verify:** The Plan 01-01 Task 3 verify ran with `INVISIBLE_HOME=/Users/ace/.invisible-ws/relations-page` — which is *not* a symlink — so the bug was masked. Anyone who runs the workstream with `INVISIBLE_HOME=$(realpath ...)` or in a CI that uses `/tmp/*` paths (which on macOS reach through `/private/tmp` symlink) will hit it.

**Fix.** Resolve once at the boundary:

```python
if slug == "invisible":
    try:
        return config.home().resolve()
    except (OSError, RuntimeError):
        return None
```

The general-case branch already does this (via `_safe_resolve`), so this just unifies the two paths.

---

### WR-03 — Endpoint deriver uses inconsistent ID format

**File:** `lib/api/relations.py:686-712`

**Issue.** Every other module node ID is dot-separated (`lib.api.projects`, `frontend.pages.dashboard`). The endpoint deriver introduces:

```python
dash_id = "bin/invisible-dashboard"
```

This string is then:
1. Used as a node `id` (line 690).
2. Stamped into edges (line 707).
3. Fed into the grep deriver's basename map (line 600: `mid.rsplit(".", 1)[-1]`).

Step 3 is where it bites: `"bin/invisible-dashboard".rsplit(".", 1)[-1]` returns the whole string `"bin/invisible-dashboard"` (no dot present), and `_is_meaningful_basename("bin/invisible-dashboard")` returns `False` (no underscore, doesn't start with uppercase). So **any `.planning/*.md` doc that mentions the literal string `invisible-dashboard` produces zero grep edges to this node** — silent miss.

Two further side-effects:
- The frontend's `KIND_TO_CSS[n.type]` lookup uses `n.type` (`"module"`) which is fine — the slash in the ID doesn't break CSS. But edge `from`/`to` matching to draw lines depends on exact string equality; if any future code computes the dashboard ID independently (e.g. via `_module_id_for("bin/invisible-dashboard")` → `"bin.invisible-dashboard"`) you'd get a *second* node with a similar-looking ID and dangling edges.

**Fix.** Either (a) use the dotted form `"bin.invisible-dashboard"` to match the convention, or (b) add a special case in `_derive_grep_edges` to use the *label* (`"invisible-dashboard"`) for basename matching when the ID contains a slash. Option (a) is cleaner:

```python
dash_id = "bin.invisible-dashboard"
nodes.append({
    "id": dash_id,
    "label": "invisible-dashboard",
    "type": "module",
    "project": slug,
    "file_path": "bin/invisible-dashboard",
})
```

This change *also* makes `_is_meaningful_basename("invisible-dashboard")` return `True` via the `-` (no wait — it requires underscore or uppercase; `invisible-dashboard` would still fail). So you actually need to *additionally* loosen `_is_meaningful_basename` to accept hyphen-separated names, or hardcode an exception for known basenames. Practical fix: add hyphenated basename support to `_is_meaningful_basename`:

```python
def _is_meaningful_basename(b: str) -> bool:
    if len(b) < 5:
        return False
    return b[0].isupper() or "_" in b or "-" in b
```

---

## Medium

### ME-01 — Cache-key collision: `"__all__"` is a valid slug

**File:** `lib/api/relations.py:91, 861, 873`

**Issue.** `PROJECT_SLUG_RE = ^[a-z0-9_-]{1,64}$` accepts `"__all__"`. The aggregate cache is keyed under `"__all__"` (line 861). If a user creates an `invisible.toml` entry with `name = "__all__"`, three things happen:

1. `build_graph("__all__")` writes to `_CACHE["__all__"]` — the same slot used for the aggregate.
2. A subsequent `build_graph(None)` (aggregate) hits the per-project cache and returns *only the `__all__` project's graph*, not the union.
3. Worst case: cross-request answer poisoning. A request for `?project=__all__` gets served the aggregate cache (if it was written first) or vice versa.

Likelihood is low (who names a project `__all__`?) but the mitigation is trivial.

**Fix.** Pick a key the slug regex can never produce. The regex disallows uppercase, so `"__ALL__"` or `"__aggregate__"` are guaranteed safe:

```python
_AGGREGATE_KEY = "__ALL__"   # uppercase guaranteed unreachable by PROJECT_SLUG_RE
...
key = project or _AGGREGATE_KEY
```

Alternative: store the cache under a 2-tuple key like `("project", slug)` vs `("aggregate",)` so the namespaces can't collide.

---

### ME-02 — Slug regex is more permissive than sibling pattern

**File:** `lib/api/relations.py:91`

**Issue.** Compare with `lib/api/tree_repo.py:86`:

```python
# tree_repo.py:
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")   # first char MUST be alphanumeric

# relations.py:
PROJECT_SLUG_RE = re.compile(r"^[a-z0-9_-]{1,64}$")     # first char can be '-' or '_'
```

The relations regex accepts `"--"`, `"-rf"`, `"-"`, `"_"` as valid slugs. None of these are exploitable in the current code path — the slug is used for (a) dict lookup against `invisible.toml [[projects]].name` and (b) cache key. Neither flows into `subprocess`, `os.execvp`, shell, or Notion query string interpolation. **Not currently exploitable.**

But:
1. It's a regression from the sibling's hardening.
2. It invites a future bug if anyone extends the code to `git -C <slug>` or similar.
3. The threat model T-01-01-01 calls out "never used in any subprocess argv" — that's currently true, but the regex doesn't *enforce* it.

**Fix.** Mirror the sibling pattern:

```python
PROJECT_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
```

This still accepts every real workstream slug (`invisible`, `relations-page`, `lumen-staging`) and the verified Plan 01-01 test inputs.

---

### ME-03 — Grep deriver O(docs × patterns) loop ordering

**File:** `lib/api/relations.py:622-650`

**Issue.** The second pass is:

```python
for doc_id, text in doc_texts.items():           # ~60 docs
    for basename, pat in module_basename_patterns.items():   # ~25 module basenames
        if pat.search(text):
            ...
    for basename, pat in doc_basename_patterns.items():     # ~50 doc basenames
        ...
```

So roughly 60 × 75 = 4,500 regex searches per build, each scanning the full doc text. For the current 60-file `.planning/` tree that's manageable (~250ms cold per the verify log). But:
- The threat model T-01-01-04 mitigates per-file size (`_GREP_MAX_FILE_BYTES = 1 MiB`), so per-search work is bounded.
- Combined upper bound: 60 × 1 MiB × 75 = 4.5 GiB of text-scanning per build. Realistic worst case.

**Why this matters in v1.** Strictly out of the v1 review scope (perf), but it's a borderline case because the grep deriver's edge output drives the sanity-bound check (50–500 edges). Plan 01-01's own summary notes a tight-fit fix from 703→216 edges; if `.planning/` doubles, the deriver could re-cross the bound *or* lock up the response window.

**Fix.** Build a single combined alternation regex per group:

```python
import re
combined_module_re = re.compile(
    r"\b(" + "|".join(re.escape(b) for b in module_basename_to_id) + r")\b"
) if module_basename_to_id else None
# then per doc:
for m in combined_module_re.finditer(text):
    basename = m.group(1)
    target_id = module_basename_to_id[basename]
    ...
```

One pass instead of N. Same correctness, ~25× faster on this workload.

---

### ME-04 — `Header` defined inside `Relations()`

**File:** `frontend/pages/relations.jsx:223-233`

**Issue.**

```jsx
function Relations() {
  ...
  const Header = ({ chipText, chipColor, dataLabel }) => (...);
  ...
  if (data === null && !error) {
    return <Header ... />;   // a NEW function reference every render
  }
}
```

Because `Header` is a different function reference on every render of `Relations`, React's reconciler treats every `<Header/>` as a different component type — **unmount + mount each time**. Today Header is stateless and effect-less so the only cost is wasted reconciliation work. The bug latent here is: any future state added to `Header` will mysteriously reset on every parent state change.

**Fix.** Move `Header` to module scope (above `function Relations()`), passing branch state via props as it already does. No behavior change, zero re-mounting.

---

## Low

### LO-01 — `build_graph` returns cached dict by reference

**File:** `lib/api/relations.py:863-865, 946`

**Issue.** On cache hit:

```python
cached = _CACHE.get(key)
if cached is not None and cached[0] > time.time():
    return cached[1]                  # NOT a copy
```

Currently safe because the only caller (`handle_relations`) immediately passes the dict to `handler._send_json` which calls `json.dumps` — read-only. But this is an implicit contract; a future caller that mutates the response (e.g. to inject an extra field) will corrupt the cache for all subsequent readers.

**Fix.** Return a shallow copy on cache hit, OR document the contract loudly in the docstring (currently only mentioned obliquely: *"NOT a copy — the graph is read-only on the wire"*).

### LO-02 — `<line key={i}>` uses array index as React key

**File:** `frontend/pages/relations.jsx:154`

**Issue.** When filter chips toggle and `visibleEdges` is re-filtered, edge index 5 (say) refers to a different edge `{from, to, kind}` triple before vs after. React re-renders the SVG line element but with new x1/y1/x2/y2. Functionally OK for stateless SVG lines, but it's a code smell and would bite if anyone adds a keyed CSS transition.

**Fix.**

```jsx
{visibleEdges.map((e) => (
  <line key={`${e.from}|${e.to}|${e.kind}`} ... />
))}
```

### LO-03 — Drag handler null-deref risk on unmount

**File:** `frontend/pages/relations.jsx:111-114`

**Issue.** Window-level mousemove handler:

```jsx
const move = (e) => {
  const rect = wrapRef.current.getBoundingClientRect();   // wrapRef.current can be null
  ...
};
```

If `RelationsGraph` unmounts mid-drag (e.g. user navigates away while holding mouse), the cleanup runs on the *next* effect cycle but the existing mousemove handler may fire one more time on a null ref. Crash → React error boundary needed.

**Fix.** Null-guard:

```jsx
const move = (e) => {
  if (!wrapRef.current) return;
  const rect = wrapRef.current.getBoundingClientRect();
  ...
};
```

### LO-04 — Orphan string literal in `lib/api/__init__.py`

**File:** `lib/api/__init__.py:30-37`

**Issue.** Between `__all__ = [...]` (line 29) and the `from . import chat` block (lines 38-41), there is a triple-quoted string expression:

```python
__all__ = ["ROUTES", "projects", "relations"]
"""API submodules consumed by bin/invisible-dashboard.

Each submodule is responsible for a single data source / capability. ...
"""
from . import chat        # noqa: F401  (ai-bubble: POST /api/v1/chat)
```

This is **not** a docstring — `__doc__` is already set from the file-top docstring (lines 1-16). It's a no-op expression statement: Python evaluates the string, discards it. Looks intentional but is dead.

**Fix.** Either delete it or turn it into a `#`-prefix comment block.

### LO-05 — `__all__` doesn't list `chat`, `tree_local`, `tree_vps`, `tree_repo`

**File:** `lib/api/__init__.py:29, 38-41`

**Issue.** `__all__ = ["ROUTES", "projects", "relations"]` but the file then imports four more submodules. `bin/invisible-dashboard:63-64` does `from api import tree_local, tree_vps, tree_repo` which works because the `from . import` lines made them attributes of the `api` package. But `__all__` lying about what's exported is misleading.

**Fix.** Either add them: `__all__ = ["ROUTES", "projects", "relations", "chat", "tree_local", "tree_vps", "tree_repo"]`, or remove `__all__` entirely (it's not protecting anything here).

### LO-06 — `layoutNodes()` runs twice on mount

**File:** `frontend/pages/relations.jsx:90, 98`

**Issue.**

```jsx
const [nodes, setNodes] = useStateG(() => layoutNodes(rawNodes, 800, 600));  // call #1 (lazy init)
...
useEffectG(() => { setNodes(layoutNodes(rawNodes, 800, 600)); }, [rawNodes]);  // call #2 (mount + every rawNodes change)
```

On the initial mount, both call sites fire. The effect overwrites the lazy init's result with an identical (same-input) layout. Wasted compute.

**Fix.** Skip the redundant first-run by using a ref-guard, or drop the lazy initializer in favor of the effect-only path:

```jsx
const [nodes, setNodes] = useStateG([]);
useEffectG(() => { setNodes(layoutNodes(rawNodes, 800, 600)); }, [rawNodes]);
```

Tradeoff: first render shows empty graph for one tick. Acceptable since the outer `Relations` shell already gates on `data` being loaded.

---

## Info

### IN-01 — AST walker silently ignores relative imports

**File:** `lib/api/relations.py:390-398`

`from . import x` / `from .foo import bar` set `node.module = None` (or `"foo"` without the leading dot). The current code only emits an edge when `node.module` is truthy *and* matches a known module ID. So `lib/api/__init__.py`'s `from . import projects` produces zero edges. Documented limitation, not a bug; flag for future awareness.

### IN-02 — Binary sniff reads full file for first 512 bytes

**File:** `lib/api/relations.py:539`

```python
head = abs_path.read_bytes()[:512]
```

`read_bytes()` reads the *entire* file (up to 1 MiB by the size cap) into memory just to grab the first 512 bytes for the NUL test. Should use:

```python
with abs_path.open("rb") as f:
    head = f.read(512)
```

Strictly perf, but trivial fix.

### IN-03 — Header buttons "Force layout" / "Tag view" are inert

**File:** `frontend/pages/relations.jsx:229-230`

```jsx
<button className="btn">Force layout</button>
<button className="btn">Tag view</button>
```

No `onClick`. Click → silent no-op. Either wire them or comment-mark as TODO (the file already does this for the Zoom-in button — same pattern would help here).

### IN-04 — Notion deriver doesn't dedupe per-page relations

**File:** `lib/api/relations.py:792-808`

Inner relation-property loop appends to `edges_pending` without checking for duplicates. A Notion page that lists the same relation property twice (or where two distinct relation properties on the same page point to the same target) would emit duplicate edges. The final filter (line 811) only drops dangling edges, not duplicates. Very unlikely in practice; flag for completeness.

### IN-05 — No client-side fetch timeout

**File:** `frontend/pages/relations.jsx:31-40`

Already acknowledged in `01-02-PLAN.md` threat model T-01-02-04 as `accept`. Restated here so it appears in the review surface and isn't quietly forgotten by future work.

---

## Notes on scope adherence

- **Out-of-scope (skipped per instructions):**
  - Static `"18 NODES · 22 LINKS"` chip in `frontend/app.jsx:91` — confirmed already documented as follow-up in `01-02-SUMMARY.md`.
  - `lib/notion.py` left untouched — per workstream additive-only rule.
- **Performance findings** (ME-03, IN-02, LO-06): v1 review charter excludes pure performance, but ME-03 in particular sits on the boundary of correctness because it directly feeds the 50–500 edge sanity bound the plan's threat model relies on. Recorded as MEDIUM rather than INFO for that reason.
- **Verified correct (no finding):** the slug→FS path containment, the Notion silent-degrade path, the 60 s TTL cache TTL math, the `_safe_resolve` rejection of `/` and `~`, the dangling-edge filter at `build_graph:935`, the `_send_json` ACAO single-header invariant per the Wave 2 fix (`c18ca74`), and the React text-node escaping of Notion-supplied labels.

---

_Reviewed: 2026-06-02T10:30:00Z_
_Reviewer: Claude (gsd-code-reviewer · Opus 4.7 1M context)_
_Depth: deep (cross-file: relations.py ↔ projects.py / tree_local.py / tree_repo.py; relations.jsx ↔ icons.jsx / styles.css / index.html)_
