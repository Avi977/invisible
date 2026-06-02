"""Live integration tests for lib/api/tree_vps.py against srv982719.

These tests are gated TWO ways:

1. Module-level `pytestmark = pytest.mark.vps_integration` — the
   collection hook in tests/conftest.py skips them unless `--integration`
   is passed on the pytest CLI.

2. The `live_vps_or_skip` fixture — if srv982719 is not reachable via
   `ssh -o BatchMode=yes srv982719 true`, or if no project in the user's
   real ~/.invisible/invisible.toml has a vps_repo_path set, every test
   here SKIPS (it never FAILS) with a clear reason.

So in CI without the flag: every test here is SKIPPED, no network hit.
On the developer's machine with `--integration`: real SSH, real walks.

Plan 01-01 must have been completed first (~/.ssh/config has the
`Host srv982719` block + ControlMaster directives, key-based auth works).
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

# Put the repo's lib/ on the import path. Mirrors test_api_projects.py.
HERE = Path(__file__).resolve().parent
LIB = HERE.parent / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))


# Every test in this module is a vps_integration test.
pytestmark = pytest.mark.vps_integration


# ────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────


def _write_toml(home: Path, vps: dict | None, projects: list[dict]) -> None:
    """Render a synthetic invisible.toml (mirror of test_tree_vps.py helper)."""
    lines: list[str] = []
    if vps is not None:
        lines.append("[vps]")
        for k, v in vps.items():
            if isinstance(v, bool):
                lines.append(f"{k} = {str(v).lower()}")
            else:
                lines.append(f'{k} = "{v}"')
        lines.append("")
    for p in projects:
        lines.append("[[projects]]")
        for k, v in p.items():
            if isinstance(v, bool):
                lines.append(f"{k} = {str(v).lower()}")
            else:
                lines.append(f'{k} = "{v}"')
        lines.append("")
    (home / "invisible.toml").write_text("\n".join(lines))


def _fresh_tree_vps(monkeypatch, tmp_path):
    """Drop cached api.* / config modules so a re-import picks up tmp_path env."""
    monkeypatch.setenv("INVISIBLE_HOME", str(tmp_path))
    for mod in list(sys.modules):
        if mod == "config" or mod.startswith("api"):
            del sys.modules[mod]
    from api import tree_vps  # noqa: WPS433
    return tree_vps


# ────────────────────────────────────────────────────────────────────────
# Live tests
# ────────────────────────────────────────────────────────────────────────


def test_walk_all_live_returns_tree(live_vps_or_skip):
    """Contract: walk_all(project=<configured>) returns a 200 tree from the real VPS.

    The test uses the user's REAL ~/.invisible/invisible.toml (no monkeypatching
    here — we want to exercise the exact production code path).
    """
    name, vps_repo_path = live_vps_or_skip

    # Fresh import — the production sys.modules cache could carry a stale
    # tree_vps from a prior hermetic test that monkeypatched INVISIBLE_HOME.
    for mod in list(sys.modules):
        if mod == "config" or mod.startswith("api"):
            del sys.modules[mod]
    from api import tree_vps

    rows, status = tree_vps.walk_all(project=name)

    assert status == 200, f"expected 200, got {status} (rows: {rows!r})"
    assert isinstance(rows, list)
    assert len(rows) == 1, f"expected exactly one project row, got {len(rows)}"

    top = rows[0]
    assert top["name"] == name
    assert top["type"] == "folder"
    assert top.get("open") is True
    assert len(top["children"]) == 1, "top-level project node must wrap exactly one walked-root"

    walked_root = top["children"][0]
    assert walked_root["name"] == vps_repo_path
    assert walked_root["type"] == "folder"
    # On the happy path, there must be NO badge key (badge appears only on
    # SSH/find failures). If the configured /srv/<project> doesn't exist
    # on the VPS, this would fail — that's a config issue, not a code bug.
    assert "badge" not in walked_root, (
        f"walked root has unexpected badge={walked_root.get('badge')!r} — "
        f"is {vps_repo_path} actually present on srv982719?"
    )

    # There must be SOMETHING under the walked root for a real project
    # (an empty dir is unlikely but possible — flag it loudly if so).
    children = walked_root["children"]
    assert isinstance(children, list)
    assert len(children) > 0, (
        f"{vps_repo_path} on srv982719 contains no walkable entries — "
        "is it an empty directory or a permission issue?"
    )


def test_walk_all_live_warm_call_completes_under_3s(live_vps_or_skip):
    """Contract: with ControlMaster pre-primed, a full walk takes <3.0s warm.

    The first call would include the cold SSH handshake (~2.5s on this network
    per Plan 01-01); we prime the master once before the timer starts.
    """
    name, _vps_repo_path = live_vps_or_skip

    # Prime the master connection (a separate ssh call); this populates the
    # ControlMaster socket under $INVISIBLE_HOME/run/. Subsequent calls reuse it.
    # We deliberately prime via _ssh_argv so the SAME socket path is used.
    for mod in list(sys.modules):
        if mod == "config" or mod.startswith("api"):
            del sys.modules[mod]
    from api import tree_vps

    # First call (cold) — warm the master, ignore timing.
    tree_vps.walk_all(project=name)

    # Now time the warm call.
    start = time.perf_counter()
    rows, status = tree_vps.walk_all(project=name)
    duration = time.perf_counter() - start

    assert status == 200
    assert duration < 3.0, (
        f"warm walk took {duration:.3f}s — expected <3.0s "
        "(ControlMaster master should have been reused). "
        "If this fails consistently, check the socket under $INVISIBLE_HOME/run/."
    )


def test_walk_all_live_empty_host_still_503(monkeypatch, tmp_path):
    """Regression guard on the live system: vps.host="" → ([VPS_NOT_CONFIGURED], 503).

    Hermetic in execution (uses tmp_path) but lives in the live file so that
    `--integration` runs assert every contract together. The graceful-degradation
    path must NEVER regress.
    """
    _write_toml(
        tmp_path,
        vps={"host": "", "identity": "~/.ssh/id_ed25519"},
        projects=[{"name": "p1", "vps_repo_path": "/srv/p1"}],
    )
    tree_vps = _fresh_tree_vps(monkeypatch, tmp_path)

    monkeypatch.setattr(
        tree_vps.subprocess,
        "run",
        lambda *a, **k: pytest.fail("subprocess.run should not be called"),
    )
    rows, status = tree_vps.walk_all()
    assert status == 503
    assert rows == [tree_vps.VPS_NOT_CONFIGURED]


def test_walk_all_live_unknown_path_yields_unreachable_badge(live_vps_or_skip, monkeypatch, tmp_path):
    """Contract: vps_repo_path that doesn't exist on the VPS → badge="unreachable", status=200.

    This test ACTUALLY hits srv982719 (the live host) with a /srv path that
    doesn't exist, then asserts the daemon gracefully degrades instead of
    crashing. Per-walk failure is NOT a config failure (which would be 503).
    """
    _name, _vps_repo_path = live_vps_or_skip

    bogus = "/srv/__definitely_does_not_exist_invisible_test__"
    _write_toml(
        tmp_path,
        vps={"host": "srv982719", "identity": "~/.ssh/vps_avi"},
        projects=[{"name": "bogus-proj", "vps_repo_path": bogus}],
    )
    tree_vps = _fresh_tree_vps(monkeypatch, tmp_path)

    # No subprocess monkeypatching here — we genuinely want the real ssh+find
    # to run against the live VPS and return a non-zero exit code (the path
    # doesn't exist), which _walk_remote translates into badge="unreachable".
    rows, status = tree_vps.walk_all()
    assert status == 200, "non-existent path is a per-walk failure, not a config failure"
    assert len(rows) == 1
    walked_root = rows[0]["children"][0]
    assert walked_root.get("badge") == "unreachable", (
        f"expected badge='unreachable' for bogus path, got: {walked_root!r}"
    )


def test_walk_all_live_argv_actually_uses_controlmaster(live_vps_or_skip, monkeypatch):
    """Contract: when the real ssh is invoked, argv carries the ControlMaster options.

    Spies on subprocess.run with a wrapper that captures argv then delegates
    to the real subprocess.run. The hermetic test exercises the same shape;
    this test confirms the REAL invocation against srv982719 uses the same
    argv (no shell wrapping, ControlPath under $INVISIBLE_HOME/run/).
    """
    name, _ = live_vps_or_skip

    for mod in list(sys.modules):
        if mod == "config" or mod.startswith("api"):
            del sys.modules[mod]
    from api import tree_vps

    captured: list[list[str]] = []
    real_run = subprocess.run

    def spy_run(argv, *args, **kwargs):
        captured.append(list(argv))
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(tree_vps.subprocess, "run", spy_run)
    rows, status = tree_vps.walk_all(project=name)
    assert status == 200, f"walk_all returned status {status}: {rows!r}"

    assert len(captured) >= 1, "expected at least one ssh call"
    argv = captured[0]
    assert argv[0] == "ssh"

    # Extract -o KEY=VAL pairs into a flat list of values for assertions.
    options: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "-o" and i + 1 < len(argv):
            options.append(argv[i + 1])
            i += 2
        else:
            i += 1
    assert "BatchMode=yes" in options
    assert "ControlMaster=auto" in options
    assert "ControlPersist=60s" in options
    cp_opt = next((o for o in options if o.startswith("ControlPath=")), None)
    assert cp_opt is not None, f"ControlPath option missing from argv {options}"
    # The socket path must point inside $INVISIBLE_HOME/run/ (NOT ~/.ssh/cm-*)
    # — Decision A: dashboard daemon uses a dedicated socket dir.
    assert "/run/" in cp_opt, (
        f"ControlPath {cp_opt!r} should point inside $INVISIBLE_HOME/run/ "
        "(Decision A — separate socket from user-shell ~/.ssh/cm-*)"
    )

    # The "--" option-terminator must come before the remote find command.
    assert "--" in argv
    dd = argv.index("--")
    assert "find" in argv[dd + 1 :]
