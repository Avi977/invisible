# Phase 1: GitHub Actions CI - Pattern Map

**Mapped:** 2026-06-01
**Files analyzed:** 5 (4 new, 1 light-edit)
**Analogs found:** 3 with strong in-repo analogs / 5 total (2 are greenfield CI infra — no in-repo analog by design)

> **Phase nature:** This is CI *infrastructure*, mostly greenfield. The repo has
> **zero** files under `.github/workflows/` (verified), so `ci.yml` and the lint
> config have no in-repo template — for those, follow standard GitHub Actions
> conventions captured below, not a forced weak analog. The parts that DO have
> strong in-repo analogs are the **runtime mechanics** the jobs must reproduce:
> the `sys.path`/`PYTHONPATH=lib` import scheme, the pytest wiring, and the
> reason `ruff` must see the extension-less `bin/invisible-*` scripts.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `.github/workflows/ci.yml` | config (CI workflow) | event-driven (push / PR) | — (none; first workflow) | no-analog (greenfield) |
| `ruff.toml` | config (lint) | batch (static analysis) | — (none) + targets `bin/invisible-*` | no-analog (greenfield) |
| `pyproject.toml` *(or `pytest.ini`)* — `[tool.pytest.ini_options]` | config (test runner) | batch (test collection) | `tests/test_api_projects.py` + `lib/api/test_chat.py` (consumers it must support) | role-match (config inferred from the tests it wires) |
| import-smoke command *(inline in `ci.yml`)* | utility (smoke check) | request-response (import probe) | `bin/invisible-dashboard` L55-64 | exact |
| `README.md` | docs | — (static) | own header (L1-5) | self / light-edit |

> `pyproject.toml` is listed as a *new* file: no `pyproject.toml`, `pytest.ini`,
> `setup.cfg`, `tox.ini`, or any `requirements*.txt` exists in the repo (verified).
> Per D-03 the planner may choose `pyproject.toml` **or** `pytest.ini` — both acceptable.

---

## Pattern Assignments

### `.github/workflows/ci.yml` (config, event-driven) — GREENFIELD

**Analog:** None. There is no `.github/workflows/` directory in the repo at all
(verified: `NO .github/workflows DIR`). PR #3's `security-review.yml` is the only
other workflow and it is **not** on this branch (merged separately, different
filename + job names — zero conflict per D-06). Do **not** model `ci.yml` on it.

**External conventions to follow (standard GitHub Actions shape):**

```yaml
name: ci
on:
  push:                      # D-01: any branch
  pull_request:
    branches: [main]         # D-01: PRs targeting main

jobs:
  lint:                      # D-01: three SEPARATE jobs (independent signal),
  test:                      #       NOT three steps in one job
  import-smoke:
```

Per-job skeleton (each of the three jobs repeats the checkout + setup-python
preamble; pin to **major** versions per D-01, Python **3.11** per D-01):

```yaml
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4          # D-01: pin major
      - uses: actions/setup-python@v5      # D-01: pin major
        with:
          python-version: "3.11"           # D-01: matches dev env 3.11.4
      - run: pip install ruff              # D-05: only ruff + pytest, pinned
      - run: ruff check lib/ bin/          # D-02: lint lib/ and bin/
```

**Job-specific run commands** (sourced from verified mechanics below):
- `lint`: `pip install ruff==<pin>` then `ruff check lib/ bin/` (D-02).
- `test`: `pip install pytest==<pin>` then `PYTHONPATH=lib pytest` (config supplies `testpaths`; D-03).
- `import-smoke`: the two probes in the import-smoke entry below (D-04). No third-party install — pure stdlib (D-05, verified).

**Discretion (D / "Claude's Discretion"):** single 3.11 vs matrix (single fine),
`actions/setup-python` pip cache (nice-to-have), exact version pins.

---

### `ruff.toml` (config, batch) — GREENFIELD, but target shape is in-repo-driven

**Analog:** None for the file itself. The *requirement* that drives its contents
is fully in-repo. Two verified facts force two specific settings:

**1. Lint must see extension-less Python scripts → `extend-include` (D-02).**
21 of 23 `bin/invisible-*` files are Python with **no `.py` extension** (verified;
the 2 exceptions `invisible-review` and `invisible-update` are bash). Ruff will
skip them unless told to include them. Header of a representative script
(`bin/invisible-pty` L1):

```python
#!/usr/bin/env python3
"""invisible-pty — local WebSocket PTY daemon for the Terminals page.
```

→ `ruff.toml` MUST set (or equivalent):
```toml
extend-include = ["bin/invisible-*"]
```
and must not choke on the 2 non-Python `bin/` files (a glob that hits bash files
is fine — ruff only parses what looks like Python; the bash scripts have a
`#!/usr/bin/env bash` shebang and `.toml`-level `extend-include` will not force-parse them as Python errors in practice, but keep the ruleset lenient regardless).

**2. Ruleset must pass existing code on a fresh clone → curated `select`, tolerate E402 (D-02).**
Every Python entrypoint and test does `sys.path.insert(...)` **before** its imports,
then silences the resulting late-import warning with `# noqa: E402`. Canonical
proof from `bin/invisible-doctor` L31-34:

```python
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))

from config import home, load_env, load_toml  # noqa: E402
```

→ A full default ruleset would flag E402 across the whole codebase. Per D-02:
start from a **curated `select`** (pyflakes `F` + a safe subset), NOT ruff's full
default; if E402 is enabled it must be tolerated (it is already `# noqa`'d at every
site, but do not rely on that — keep it out of `select` or add to `ignore`).
Tightening is **explicitly deferred** (D-02, Deferred Ideas).

```toml
# Skeleton — exact rule choice is Claude's Discretion within "lenient, passes existing code"
target-version = "py311"
extend-include = ["bin/invisible-*"]
[lint]
select = ["F"]          # pyflakes only as a safe floor; widen carefully
# E402 must NOT break the build (post-sys.path imports everywhere)
```

---

### `pyproject.toml` `[tool.pytest.ini_options]` (config, batch) — wires existing tests

**Analog (consumers the config must satisfy):** `tests/test_api_projects.py` +
`lib/api/test_chat.py`. No pytest config exists today, so a bare `pytest` run
would (a) not put `lib/` on the path and (b) miss the colocated test.

**Two verified facts force two specific settings:**

**1. `api` is a top-level package reachable ONLY via `lib/` on `sys.path` → `PYTHONPATH=lib` (D-03).**
There is **no `lib/__init__.py`** (verified: `NO lib/__init__.py`). So `api` is not
`lib.api`; it is the top-level package `api`, importable only when `lib/` is on the
path. The tests encode this themselves. From `tests/test_api_projects.py` L22-27:

```python
# Put the repo's lib/ on the import path so `import api` and `from api import ...`
# resolve. This mirrors how bin/invisible-dashboard sets up its own sys.path.
HERE = Path(__file__).resolve().parent
LIB = HERE.parent / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))
```

`test_chat.py` does the dual-path variant (so it runs both as `api.chat` and
`lib.api.chat`). From `lib/api/test_chat.py` L18-25:

```python
HERE = Path(__file__).resolve().parent
# Inside the lib/ tree the import path is `api.chat`; from the repo root it's
# `lib.api.chat`. We support both.
sys.path.insert(0, str(HERE.parent))        # so `api.chat` resolves
sys.path.insert(0, str(HERE.parent.parent)) # so `lib.api.chat` resolves
from api.chat import chat_handler, MAX_MESSAGE_CHARS, CLAUDE_CMD, CLAUDE_TIMEOUT_S  # noqa: E402
```

→ Both files self-insert their path, so they *can* run unaided, but the CI `test`
job standardizes on `PYTHONPATH=lib pytest` (D-03) to match `bin/invisible-dashboard`
and guarantee `from api import ...` resolves regardless of cwd.

**2. `test_chat.py` is colocated under `lib/api/` → `testpaths` must include BOTH dirs (D-03).**
A bare `pytest tests/` would silently skip `lib/api/test_chat.py` (verified it
lives at `lib/api/test_chat.py`, not under `tests/`). Note also `test_chat.py`
uses `unittest.TestCase` style (`import unittest`, L14) — pytest collects these
natively, no extra config.

```toml
[tool.pytest.ini_options]
testpaths = ["tests", "lib/api"]   # D-03: collect test_api_projects.py AND test_chat.py
# pythonpath = ["lib"]  # optional alternative to PYTHONPATH=lib in the workflow
```

> `tests/__init__.py` exists and is **empty** (0 bytes, verified) — it makes
> `tests/` a package; leave it as-is. There is no `lib/api/__init__.py`-as-package
> concern beyond the existing `lib/api/__init__.py` (see import-smoke note).

---

### import-smoke (utility, request-response) — INLINE in `ci.yml` — EXACT analog

**Analog:** `bin/invisible-dashboard` L55-64 — the canonical `sys.path` + `from api import`
sequence the smoke job mirrors with `PYTHONPATH=lib`:

```python
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))

from config import home, load_env  # noqa: E402
from dashboard_render import (  # noqa: E402
    humanize_age, render_index, render_project, render_not_found,
)
from api import ROUTES as API_V1_ROUTES  # noqa: E402
from api import tree_local, tree_vps, tree_repo  # noqa: E402
from api.chat import chat_handler  # noqa: E402
```

**Probe 1 — import present `api.*` submodules, soft-skip `api.analytics` (D-04).**
`lib/api/analytics.py` does **not** exist on this branch (verified:
`NO lib/api/analytics.py` — stranded in PR #8). A hard import of all six modules
would `ModuleNotFoundError` on a fresh clone and break "all jobs green." The 5
present submodules import on pure stdlib — **live-verified just now**:

```
PYTHONPATH=lib python3 -c "import api.projects, api.chat, api.tree_local, api.tree_vps, api.tree_repo"
# → OK: 5 present api.* submodules import
PYTHONPATH=lib python3 -c "import api.analytics"
# → ModuleNotFoundError: No module named 'api.analytics'   (expected; soft)
```

→ Smoke the 5 present submodules **hard**; import `api.analytics` **soft** (try/except
`ModuleNotFoundError` → warn, do not fail) so it auto-covers the moment PR #8 lands.
Shape (planner picks exact form — single `python -c` or a tiny inline script):

```yaml
      - name: import-smoke (api.*)
        run: |
          PYTHONPATH=lib python3 - <<'PY'
          import importlib, sys
          hard = ["api.projects", "api.chat", "api.tree_local", "api.tree_vps", "api.tree_repo"]
          for m in hard:
              importlib.import_module(m)
          try:
              importlib.import_module("api.analytics")  # D-04: optional until PR #8
          except ModuleNotFoundError:
              print("WARN: api.analytics absent (PR #8 not merged) — soft-skip")
          print("import-smoke OK")
          PY
```

> NOTE on `lib/api/__init__.py`: it has **two concatenated module docstrings**
> (L1-16 then L28-35) from prior 4-way merges — the second is an unassigned
> string literal (dead no-op), harmless. It eagerly imports `projects, chat,
> tree_local, tree_vps, tree_repo` (L20, L36-39) but **not** `analytics`, which is
> why `import api` itself succeeds today. Do not "fix" the double docstring in this phase.

**Probe 2 — `py_compile` every `bin/invisible-*` Python script (D-04).**
NOT a full import — many bin scripts need heavy runtime deps (e.g. `invisible-pty`
imports `websockets` + `ptyprocess`; `invisible-pty` L23-24 documents
"Clean import-time error … if `websockets` or `ptyprocess` are missing"). So the
bin smoke is a **syntax + executable-bit** check via `py_compile`. Must skip the
**2 bash** scripts (`invisible-review`, `invisible-update`). Live-verified: all 21
Python bin scripts `py_compile` clean. Shape:

```yaml
      - name: bin syntax smoke (py_compile)
        run: |
          for f in bin/invisible-*; do
            head -1 "$f" | grep -q python || continue   # skip bash scripts
            python3 -m py_compile "$f"
          done
          echo "bin py_compile OK"
```

---

### `README.md` (docs, light-edit) — self

**Analog:** own header. README currently has **no CI badge** (verified — no
`![`/`badge`/`actions` markers found). Header is plain (L1-5):

```markdown
# invisible

A personal multi-agent cockpit. Orchestrates Codex and Claude in turn-taking
loops against your projects, with checkpoints, context budgeting, VPS handoff,
```

→ Add a standard Actions status badge near the top (exact markdown + placement is
Claude's Discretion). Canonical form:
`![ci](https://github.com/Avi977/invisible/actions/workflows/ci.yml/badge.svg)`
(repo verified: `origin https://github.com/Avi977/invisible.git`).

---

## Shared Patterns

### `sys.path` / `PYTHONPATH=lib` import contract
**Source:** `bin/invisible-dashboard` L55-64 (and identically `bin/invisible-doctor` L31-34).
**Apply to:** the `test` job, the `import-smoke` job, and the pytest config.
The whole repo treats `api` as a **top-level** package reachable only with `lib/`
on `sys.path` (there is no `lib/__init__.py`). Every entrypoint does
`sys.path.insert(0, str(HERE.parent / "lib"))`; CI's equivalent is `PYTHONPATH=lib`.

### E402 tolerance (post-`sys.path` imports)
**Source:** every `bin/invisible-*` Python script + both test files — imports sit
**after** `sys.path.insert`, each marked `# noqa: E402` (e.g. dashboard L58-64,
doctor L34, test_chat.py L25).
**Apply to:** `ruff.toml` ruleset — E402 must not break the build (D-02).

### "lenient ruleset, passes existing code"
**Source:** D-02 + the pervasive `# noqa` markers across `lib/` and `bin/`.
**Apply to:** `ruff.toml` `select` — start from pyflakes `F` + a safe subset; do
NOT enable ruff's full default. Tightening deferred.

### Pure-stdlib dependency floor
**Source:** D-05 + live verification (the 5 `api.*` submodules + their transitive
local imports `config.py`, `checkpoint.py`, `dashboard_render.py` import on bare
`python3` with no pip installs).
**Apply to:** CI install steps — install only `ruff` + `pytest` (pinned). Do NOT
add a project-wide requirements file this phase (D-05).

---

## No Analog Found

| File / Artifact | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `.github/workflows/ci.yml` | CI workflow config | event-driven | No `.github/workflows/` dir exists; this is the repo's first workflow. PR #3's `security-review.yml` is not on this branch and is intentionally separate (D-06). Use standard GH Actions conventions captured above. |
| `ruff.toml` | lint config | batch | No prior lint config in repo. Contents are nonetheless fully determined by in-repo facts (extension-less bin scripts + E402-everywhere) — see entry above. |

> The planner has **no RESEARCH.md** for this phase (research disabled,
> `workflow.research=false`). The external conventions to fall back on for the two
> greenfield files are embedded in their entries above (standard `lint`/`test`
> job shape, `actions/checkout@v4`, `actions/setup-python@v5`, py311).

---

## Cross-workstream fences (from CONTEXT.md — planner MUST respect)

- **MUST NOT TOUCH:** `.github/workflows/release.yml` (owned by `tauri-windows`).
- **MERGE, do not rewrite:** PR #3 `security-review.yml` + `.github/SECURITY-REVIEW.md`
  (D-06). `gh pr merge 3` goes behind an explicit confirm step (mutates public
  `main`); then document its 2 post-merge manual steps (set `CLAUDE_API_KEY` secret;
  register `Claude security review` required check). Do NOT author a competing
  `security-review.yml`.
- **Branch protection** for `ci.yml` (required check on `main`) is a **documented
  manual step**, not executed by the plan (D-07) — record the exact
  `gh api .../branches/main/protection` invocation + job/check names.

---

## Metadata

**Analog search scope:** `.github/` (empty of workflows), `lib/`, `lib/api/`,
`tests/`, `bin/invisible-*`, repo-root config slots.
**Files scanned:** ~30 (5 read in full/part for excerpts: `bin/invisible-dashboard`,
`bin/invisible-doctor`, `bin/invisible-pty`, `tests/test_api_projects.py`,
`lib/api/test_chat.py`, `lib/api/__init__.py`).
**Live verifications run:** import-smoke (5 hard + 1 soft), `py_compile` over 21
Python bin scripts, bin shebang classification, absence of
`.github/workflows/` + `lib/__init__.py` + `lib/api/analytics.py` + any
`pyproject/pytest/requirements` config.
**Pattern extraction date:** 2026-06-01
