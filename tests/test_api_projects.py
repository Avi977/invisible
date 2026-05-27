"""Tests for lib/api/projects.py — the /api/v1/projects data adapter.

Each test name describes the exact behavior it asserts. See
01-01-PLAN.md::<behavior> for the contract these tests enforce.

All tests are hermetic: they monkeypatch INVISIBLE_HOME to a pytest tmp_path
and write synthetic invisible.toml + checkpoint files. No test touches the
user's real ~/.invisible directory.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Put the repo's lib/ on the import path so `import api` and `from api import ...`
# resolve. This mirrors how bin/invisible-dashboard sets up its own sys.path.
HERE = Path(__file__).resolve().parent
LIB = HERE.parent / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))


# ────────────────────────────────────────────────────────────────────────
# fixtures
# ────────────────────────────────────────────────────────────────────────


def _write_toml(home: Path, projects: list[dict]) -> None:
    """Render a minimal invisible.toml at home / 'invisible.toml'.
    `projects` is a list of dicts with at minimum {"name", "repo_path"}.
    """
    lines: list[str] = []
    for p in projects:
        lines.append("[[projects]]")
        for k, v in p.items():
            if isinstance(v, list):
                items = ", ".join(f'"{x}"' for x in v)
                lines.append(f"{k} = [{items}]")
            elif isinstance(v, (int, float, bool)):
                lines.append(f"{k} = {v}")
            else:
                lines.append(f'{k} = "{v}"')
        lines.append("")
    (home / "invisible.toml").write_text("\n".join(lines))


def _write_checkpoint(home: Path, project: str, payload: dict) -> Path:
    """Write a checkpoint file at home/worktrees/<project>/feature/.invisible-checkpoint.json.
    Returns the worktree directory path."""
    wt = home / "worktrees" / project / "feature"
    wt.mkdir(parents=True, exist_ok=True)
    (wt / ".invisible-checkpoint.json").write_text(json.dumps(payload))
    return wt


def _init_git_repo(repo: Path) -> None:
    """Create a real git repo with one commit so branch + log queries succeed.
    Uses a local user.name/user.email config so the commit doesn't fail in CI."""
    repo.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    subprocess.run(["git", "-C", str(repo), "init", "-q", "-b", "main"],
                   check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.local"],
                   check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"],
                   check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "config", "commit.gpgsign", "false"],
                   check=True, env=env)
    (repo / "README.md").write_text("test\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-q",
                    "--no-gpg-sign", "-m", "init"],
                   check=True, env=env)


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Redirect INVISIBLE_HOME to tmp_path and force a fresh import of api modules."""
    monkeypatch.setenv("INVISIBLE_HOME", str(tmp_path))
    # Drop any cached imports so config.home() reads the new env var, and
    # so api.projects re-binds load_toml from the right module.
    for mod in list(sys.modules):
        if mod == "config" or mod == "checkpoint" or mod.startswith("api"):
            del sys.modules[mod]
    return tmp_path


# ────────────────────────────────────────────────────────────────────────
# tests
# ────────────────────────────────────────────────────────────────────────


def test_build_projects_shape(isolated_home):
    """Test 1 — exact 13-key shape, no extras, no missing."""
    home = isolated_home
    repo = home / "fake-repo"
    _init_git_repo(repo)
    _write_toml(home, [{"name": "jobslayer", "repo_path": str(repo)}])

    from api.projects import build_projects
    rows = build_projects()

    assert isinstance(rows, list)
    assert len(rows) == 1
    expected = {
        "id", "code", "name", "color", "status", "branch", "lastCommit",
        "summary", "progress", "todos", "note", "stack", "nextEvent",
    }
    got = set(rows[0].keys())
    assert got == expected, f"missing {expected - got}, extra {got - expected}"


def test_build_projects_field_types(isolated_home):
    """Test 2 — every field has the exact type DATA_SETS uses."""
    home = isolated_home
    repo = home / "fake-repo"
    _init_git_repo(repo)
    _write_toml(home, [{
        "name": "jobslayer",
        "repo_path": str(repo),
        "summary": "test project",
        "stack": ["Python", "React"],
    }])

    from api.projects import build_projects
    row = build_projects()[0]

    for k in ("id", "code", "name", "color", "branch",
              "lastCommit", "summary", "note", "nextEvent"):
        assert isinstance(row[k], str), f"{k} is {type(row[k]).__name__}, expected str"

    assert isinstance(row["progress"], int)
    assert 0 <= row["progress"] <= 100

    assert isinstance(row["todos"], list)
    for t in row["todos"]:
        assert isinstance(t, dict)
        assert isinstance(t["t"], str)
        assert isinstance(t["done"], bool)

    assert isinstance(row["stack"], list)
    for s in row["stack"]:
        assert isinstance(s, str)

    assert row["status"] in {"in-progress", "blocked", "planning", "shipped"}


def test_build_projects_no_checkpoint_yields_planning(isolated_home):
    """Test 3 — missing orchestrator worktree → status="planning", empty todos/note/progress."""
    home = isolated_home
    repo = home / "fake-repo"
    _init_git_repo(repo)
    _write_toml(home, [{"name": "jobslayer", "repo_path": str(repo)}])
    # explicitly do NOT write a checkpoint file

    from api.projects import build_projects
    row = build_projects()[0]

    assert row["status"] == "planning"
    assert row["todos"] == []
    assert row["note"] == ""
    assert row["progress"] == 0


def test_build_projects_branch_dash_when_repo_missing(isolated_home):
    """Test 4 — repo_path doesn't exist → branch == "—" and lastCommit == "—"."""
    home = isolated_home
    _write_toml(home, [{
        "name": "ghostproject",
        "repo_path": str(home / "does-not-exist"),
    }])

    from api.projects import build_projects
    row = build_projects()[0]

    assert row["branch"] == "—"
    assert row["lastCommit"] == "—"


def test_build_projects_color_in_palette(isolated_home):
    """Test 5 — color field is one of the six palette hex codes."""
    home = isolated_home
    repo = home / "fake-repo"
    _init_git_repo(repo)
    _write_toml(home, [{"name": "jobslayer", "repo_path": str(repo)}])

    from api.projects import build_projects, PALETTE
    row = build_projects()[0]

    assert row["color"] in PALETTE
    assert PALETTE == [
        "#f5b343", "#5cc8ff", "#b794ff", "#4ade80", "#f56fb1", "#5ee0c8",
    ]


def test_build_projects_does_not_leak_paths(isolated_home):
    """Test 6 — no string field contains the user's home path substring, even on broken worktree."""
    home = isolated_home
    # Use a broken / non-existent repo + checkpoint write so error narratives kick in.
    bad_repo = home / "broken-repo-with-sensitive-path"
    _write_toml(home, [{"name": "leakytest", "repo_path": str(bad_repo)}])

    from api.projects import build_projects
    row = build_projects()[0]

    # Anything string-typed must not contain the user's home path.
    sensitive_substrings = [str(home), "/Users/", "/home/"]
    for k, v in row.items():
        if isinstance(v, str):
            for needle in sensitive_substrings:
                assert needle not in v, (
                    f"field {k!r}={v!r} leaks {needle!r}"
                )


def test_api_routes_registry(isolated_home):
    """Test 7 — `from lib import api` exposes api.ROUTES['/api/v1/projects'] → callable.
    Calling it with a fake handler triggers handler._send_json(<list>)."""
    import api  # noqa: F401
    importlib.reload(api)

    assert hasattr(api, "ROUTES"), "api.ROUTES must exist"
    assert isinstance(api.ROUTES, dict)
    assert "/api/v1/projects" in api.ROUTES, (
        "/api/v1/projects must be registered in api.ROUTES"
    )

    fn = api.ROUTES["/api/v1/projects"]
    assert callable(fn)

    # Drive the handler with a minimal stand-in to confirm it calls _send_json
    # with a list. The minimal handler captures the args for the assertion.
    home = isolated_home
    repo = home / "fake-repo"
    _init_git_repo(repo)
    _write_toml(home, [{"name": "jobslayer", "repo_path": str(repo)}])

    captured: dict = {}

    class FakeHandler:
        def _send_json(self, obj, status=200):
            captured["obj"] = obj
            captured["status"] = status

    fn(FakeHandler())

    assert "obj" in captured, "handler must call _send_json"
    assert isinstance(captured["obj"], list), (
        f"_send_json got {type(captured['obj']).__name__}, expected list"
    )
    assert captured.get("status", 200) == 200
