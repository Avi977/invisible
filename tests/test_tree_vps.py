"""Hermetic tests for lib/api/tree_vps.py — the VPS SSH walker.

Every test stubs out `subprocess.run` so NO real SSH connection is ever made.
The `vps_reachable` fixture (in conftest.py) does not gate this file — these
tests must run on any machine, in CI, with or without network access.

Test naming follows test_api_projects.py: lowercase snake_case, the contract
the test asserts is in the function name.

Each test exercises exactly one documented branch from
`lib/api/tree_vps.py` docstring lines 326-340 (the `walk_all` return contract)
or `_walk_remote` failure modes.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Put the repo's lib/ on the import path so `from api import tree_vps` resolves.
# Mirrors how bin/invisible-dashboard sets up its own sys.path.
HERE = Path(__file__).resolve().parent
LIB = HERE.parent / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))


# ────────────────────────────────────────────────────────────────────────
# Test helpers
# ────────────────────────────────────────────────────────────────────────


def _write_toml(home: Path, vps: dict | None, projects: list[dict]) -> None:
    """Render a synthetic invisible.toml.

    `vps` is the [vps] table contents (or None to omit the section).
    `projects` is a list of [[projects]] tables.
    """
    lines: list[str] = []
    if vps is not None:
        lines.append("[vps]")
        for k, v in vps.items():
            if isinstance(v, bool):
                lines.append(f"{k} = {str(v).lower()}")
            elif isinstance(v, (int, float)):
                lines.append(f"{k} = {v}")
            else:
                lines.append(f'{k} = "{v}"')
        lines.append("")
    for p in projects:
        lines.append("[[projects]]")
        for k, v in p.items():
            if isinstance(v, list):
                items = ", ".join(f'"{x}"' for x in v)
                lines.append(f"{k} = [{items}]")
            elif isinstance(v, bool):
                lines.append(f"{k} = {str(v).lower()}")
            elif isinstance(v, (int, float)):
                lines.append(f"{k} = {v}")
            else:
                lines.append(f'{k} = "{v}"')
        lines.append("")
    (home / "invisible.toml").write_text("\n".join(lines))


def _fresh_tree_vps(tmp_path, monkeypatch):
    """Force a fresh import of `api.tree_vps` after INVISIBLE_HOME is set.

    Required because `tree_vps` reads INVISIBLE_HOME indirectly through
    `config.home()` — but `_cm_path()` uses `home()` lazily on each call,
    so we only need a clean module-state. Belt-and-braces: drop any cached
    `api.*` and `config` modules so a previous test's import doesn't carry
    a stale view.
    """
    monkeypatch.setenv("INVISIBLE_HOME", str(tmp_path))
    for mod in list(sys.modules):
        if mod == "config" or mod.startswith("api"):
            del sys.modules[mod]
    from api import tree_vps  # noqa: WPS433 — intentional re-import for isolation
    return tree_vps


def _make_completed(stdout: str = "", returncode: int = 0, stderr: str = ""):
    """Construct a subprocess.CompletedProcess result the way `_walk_remote` expects."""
    return subprocess.CompletedProcess(
        args=["ssh", "..."],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


# ────────────────────────────────────────────────────────────────────────
# Branch coverage of walk_all
# ────────────────────────────────────────────────────────────────────────


def test_walk_all_empty_host_returns_503(tmp_path, monkeypatch):
    """Contract: vps.host="" → ([VPS_NOT_CONFIGURED], 503), no ssh call."""
    _write_toml(
        tmp_path,
        vps={"host": "", "identity": "~/.ssh/id_ed25519"},
        projects=[{"name": "p1", "vps_repo_path": "/srv/p1"}],
    )
    tree_vps = _fresh_tree_vps(tmp_path, monkeypatch)

    calls: list[list[str]] = []

    def fake_run(argv, **kw):  # noqa: ARG001
        calls.append(argv)
        return _make_completed()

    monkeypatch.setattr(tree_vps.subprocess, "run", fake_run)
    rows, status = tree_vps.walk_all()
    assert status == 503
    assert rows == [tree_vps.VPS_NOT_CONFIGURED]
    assert calls == [], "subprocess.run must NOT be called when host is empty"


def test_walk_all_missing_vps_section_returns_503(tmp_path, monkeypatch):
    """Contract: no [vps] section at all → same 503 as empty host."""
    _write_toml(
        tmp_path,
        vps=None,
        projects=[{"name": "p1", "vps_repo_path": "/srv/p1"}],
    )
    tree_vps = _fresh_tree_vps(tmp_path, monkeypatch)

    monkeypatch.setattr(
        tree_vps.subprocess,
        "run",
        lambda *a, **k: pytest.fail("subprocess.run should not be called"),
    )
    rows, status = tree_vps.walk_all()
    assert status == 503
    assert rows == [tree_vps.VPS_NOT_CONFIGURED]


def test_walk_all_invalid_host_returns_503_with_error_body(tmp_path, monkeypatch):
    """Contract: vps.host fails _validate_host regex → 503 with error body.

    The bad host content IS echoed inside the error body — acceptable here
    because the route handler strips it before responding to the browser;
    this body is used only by the daemon's own logger and tests.
    """
    bad_host = "bad;rm -rf /"
    _write_toml(
        tmp_path,
        vps={"host": bad_host, "identity": "~/.ssh/id_ed25519"},
        projects=[{"name": "p1", "vps_repo_path": "/srv/p1"}],
    )
    tree_vps = _fresh_tree_vps(tmp_path, monkeypatch)

    monkeypatch.setattr(
        tree_vps.subprocess,
        "run",
        lambda *a, **k: pytest.fail("subprocess.run should not be called"),
    )
    rows, status = tree_vps.walk_all()
    assert status == 503
    assert len(rows) == 1
    assert rows[0] == {"error": f"invalid vps.host: {bad_host!r}"}


def test_walk_all_unknown_project_returns_empty_200_regardless_of_host(tmp_path, monkeypatch):
    """Contract: project="__nope__" with valid host → ([], 200) (BLOCKER #2)."""
    _write_toml(
        tmp_path,
        vps={"host": "srv982719", "identity": "~/.ssh/id_ed25519"},
        projects=[{"name": "real-project", "vps_repo_path": "/srv/real"}],
    )
    tree_vps = _fresh_tree_vps(tmp_path, monkeypatch)

    monkeypatch.setattr(
        tree_vps.subprocess,
        "run",
        lambda *a, **k: pytest.fail("subprocess.run should not be called"),
    )
    rows, status = tree_vps.walk_all(project="__nope__")
    assert (rows, status) == ([], 200)


def test_walk_all_unknown_project_returns_empty_200_when_host_empty(tmp_path, monkeypatch):
    """Contract: project="__nope__" with empty host → ([], 200) STILL.

    The BLOCKER #2 short-circuit must run BEFORE the host check; otherwise a
    user querying a phantom project for a not-yet-configured VPS would see
    a 503 instead of the cross-walker-consistent empty 200.
    """
    _write_toml(
        tmp_path,
        vps={"host": "", "identity": "~/.ssh/id_ed25519"},
        projects=[{"name": "real-project", "vps_repo_path": "/srv/real"}],
    )
    tree_vps = _fresh_tree_vps(tmp_path, monkeypatch)
    rows, status = tree_vps.walk_all(project="__nope__")
    assert (rows, status) == ([], 200)


def test_walk_all_project_without_vps_repo_path_silently_skipped(tmp_path, monkeypatch):
    """Contract: project with no vps_repo_path → silently skipped (per-project opt-in)."""
    _write_toml(
        tmp_path,
        vps={"host": "srv982719", "identity": "~/.ssh/id_ed25519"},
        projects=[{"name": "no-vps"}],  # no vps_repo_path field at all
    )
    tree_vps = _fresh_tree_vps(tmp_path, monkeypatch)

    calls: list[list[str]] = []

    def fake_run(argv, **kw):  # noqa: ARG001
        calls.append(argv)
        return _make_completed()

    monkeypatch.setattr(tree_vps.subprocess, "run", fake_run)
    rows, status = tree_vps.walk_all()
    assert (rows, status) == ([], 200)
    assert calls == [], "ssh must not be invoked for projects without vps_repo_path"


def test_walk_all_project_with_invalid_vps_repo_path_skipped_with_stderr(tmp_path, monkeypatch, capsys):
    """Contract: vps_repo_path containing .. → skipped + stderr warning."""
    _write_toml(
        tmp_path,
        vps={"host": "srv982719", "identity": "~/.ssh/id_ed25519"},
        projects=[{"name": "evil", "vps_repo_path": "../../etc"}],
    )
    tree_vps = _fresh_tree_vps(tmp_path, monkeypatch)
    monkeypatch.setattr(
        tree_vps.subprocess,
        "run",
        lambda *a, **k: pytest.fail("subprocess.run should not be called"),
    )

    rows, status = tree_vps.walk_all()
    assert (rows, status) == ([], 200)
    captured = capsys.readouterr()
    assert "invalid vps_repo_path" in captured.err
    assert "evil" in captured.err


# ────────────────────────────────────────────────────────────────────────
# Branch coverage of _walk_remote
# ────────────────────────────────────────────────────────────────────────


def test_walk_remote_happy_path_builds_nested_tree(tmp_path, monkeypatch):
    """Contract: stdout with mixed files+dirs → nested tree, no badge key."""
    _write_toml(
        tmp_path,
        vps={"host": "srv982719", "identity": "~/.ssh/id_ed25519"},
        projects=[{"name": "proj", "vps_repo_path": "/srv/proj"}],
    )
    tree_vps = _fresh_tree_vps(tmp_path, monkeypatch)

    stdout = (
        "d /srv/proj\n"
        "d /srv/proj/src\n"
        "f /srv/proj/src/main.py\n"
        "d /srv/proj/src/utils\n"
        "f /srv/proj/src/utils/io.py\n"
        "f /srv/proj/README.md\n"
    )
    monkeypatch.setattr(
        tree_vps.subprocess,
        "run",
        lambda *a, **k: _make_completed(stdout=stdout),
    )

    node = tree_vps._walk_remote("srv982719", "~/.ssh/id_ed25519", "/srv/proj")

    assert node["name"] == "/srv/proj"
    assert node["type"] == "folder"
    assert node.get("open") is True
    assert "badge" not in node, "happy path must NOT carry an 'unreachable' badge"

    children = node["children"]
    names = {c["name"]: c for c in children}
    assert set(names.keys()) == {"src", "README.md"}
    assert names["README.md"]["type"] == "file"
    assert names["src"]["type"] == "folder"

    src_children = names["src"]["children"]
    src_names = {c["name"]: c for c in src_children}
    assert set(src_names.keys()) == {"main.py", "utils"}
    assert src_names["main.py"]["type"] == "file"
    assert src_names["utils"]["type"] == "folder"
    utils_children = src_names["utils"]["children"]
    assert len(utils_children) == 1
    assert utils_children[0]["name"] == "io.py"
    assert utils_children[0]["type"] == "file"


def test_walk_remote_ssh_failure_returns_unreachable_badge(tmp_path, monkeypatch, capsys):
    """Contract: returncode=255 (SSH failure) → badge='unreachable', children=[]."""
    _write_toml(
        tmp_path,
        vps={"host": "srv982719", "identity": "~/.ssh/id_ed25519"},
        projects=[{"name": "proj", "vps_repo_path": "/srv/proj"}],
    )
    tree_vps = _fresh_tree_vps(tmp_path, monkeypatch)

    monkeypatch.setattr(
        tree_vps.subprocess,
        "run",
        lambda *a, **k: _make_completed(returncode=255, stderr="ssh: connect refused"),
    )
    node = tree_vps._walk_remote("srv982719", "~/.ssh/id_ed25519", "/srv/proj")

    assert node["name"] == "/srv/proj"
    assert node["type"] == "folder"
    assert node["children"] == []
    assert node["badge"] == "unreachable"
    captured = capsys.readouterr()
    assert "ssh/find" in captured.err
    assert "/srv/proj" in captured.err


def test_walk_remote_timeout_returns_unreachable_badge(tmp_path, monkeypatch, capsys):
    """Contract: subprocess.TimeoutExpired → badge='unreachable', children=[]."""
    _write_toml(
        tmp_path,
        vps={"host": "srv982719", "identity": "~/.ssh/id_ed25519"},
        projects=[{"name": "proj", "vps_repo_path": "/srv/proj"}],
    )
    tree_vps = _fresh_tree_vps(tmp_path, monkeypatch)

    def fake_run(*a, **k):
        raise subprocess.TimeoutExpired(cmd="ssh", timeout=15)

    monkeypatch.setattr(tree_vps.subprocess, "run", fake_run)
    node = tree_vps._walk_remote("srv982719", "~/.ssh/id_ed25519", "/srv/proj")

    assert node["children"] == []
    assert node["badge"] == "unreachable"
    captured = capsys.readouterr()
    assert "ssh/find failed" in captured.err


def test_walk_remote_oserror_returns_unreachable_badge(tmp_path, monkeypatch, capsys):
    """Contract: OSError (ENOENT, etc.) → badge='unreachable'."""
    _write_toml(
        tmp_path,
        vps={"host": "srv982719", "identity": "~/.ssh/id_ed25519"},
        projects=[{"name": "proj", "vps_repo_path": "/srv/proj"}],
    )
    tree_vps = _fresh_tree_vps(tmp_path, monkeypatch)

    def fake_run(*a, **k):
        raise OSError("ENOENT")

    monkeypatch.setattr(tree_vps.subprocess, "run", fake_run)
    node = tree_vps._walk_remote("srv982719", "~/.ssh/id_ed25519", "/srv/proj")

    assert node["children"] == []
    assert node["badge"] == "unreachable"
    captured = capsys.readouterr()
    assert "ssh/find failed" in captured.err


def test_walk_remote_skips_symlinks_and_other_kinds(tmp_path, monkeypatch):
    """Contract: only 'f' and 'd' kinds are honored; 'l', 's', etc. dropped."""
    _write_toml(
        tmp_path,
        vps={"host": "srv982719", "identity": "~/.ssh/id_ed25519"},
        projects=[{"name": "proj", "vps_repo_path": "/srv/proj"}],
    )
    tree_vps = _fresh_tree_vps(tmp_path, monkeypatch)

    stdout = (
        "d /srv/proj\n"
        "f /srv/proj/keep.txt\n"
        "l /srv/proj/link\n"
        "s /srv/proj/sock\n"
        "p /srv/proj/pipe\n"
        "b /srv/proj/blockdev\n"
        "c /srv/proj/chardev\n"
    )
    monkeypatch.setattr(
        tree_vps.subprocess,
        "run",
        lambda *a, **k: _make_completed(stdout=stdout),
    )
    node = tree_vps._walk_remote("srv982719", "~/.ssh/id_ed25519", "/srv/proj")
    names = {c["name"] for c in node["children"]}
    assert names == {"keep.txt"}, f"only keep.txt should remain, got {names}"


def test_walk_remote_skips_root_itself_in_children(tmp_path, monkeypatch):
    """Contract: 'd /srv/proj' (the root) does not appear in its own children."""
    _write_toml(
        tmp_path,
        vps={"host": "srv982719", "identity": "~/.ssh/id_ed25519"},
        projects=[{"name": "proj", "vps_repo_path": "/srv/proj"}],
    )
    tree_vps = _fresh_tree_vps(tmp_path, monkeypatch)

    stdout = "d /srv/proj\nf /srv/proj/a.txt\n"
    monkeypatch.setattr(
        tree_vps.subprocess,
        "run",
        lambda *a, **k: _make_completed(stdout=stdout),
    )
    node = tree_vps._walk_remote("srv982719", "~/.ssh/id_ed25519", "/srv/proj")
    names = [c["name"] for c in node["children"]]
    assert "/srv/proj" not in names
    assert "" not in names
    assert names == ["a.txt"]


def test_walk_remote_skips_paths_outside_root_prefix(tmp_path, monkeypatch):
    """Contract: defense-in-depth — a line whose path is outside the root is dropped silently."""
    _write_toml(
        tmp_path,
        vps={"host": "srv982719", "identity": "~/.ssh/id_ed25519"},
        projects=[{"name": "proj", "vps_repo_path": "/srv/proj"}],
    )
    tree_vps = _fresh_tree_vps(tmp_path, monkeypatch)

    stdout = (
        "d /srv/proj\n"
        "f /srv/proj/inside.txt\n"
        "f /etc/passwd\n"  # paranoid scenario: out-of-tree path
        "f /srv/other/leak.txt\n"
    )
    monkeypatch.setattr(
        tree_vps.subprocess,
        "run",
        lambda *a, **k: _make_completed(stdout=stdout),
    )
    node = tree_vps._walk_remote("srv982719", "~/.ssh/id_ed25519", "/srv/proj")
    names = {c["name"] for c in node["children"]}
    assert names == {"inside.txt"}, (
        f"only inside.txt must be present, got {names} "
        "(out-of-root paths must be silently dropped)"
    )


# ────────────────────────────────────────────────────────────────────────
# Top-level shape contract
# ────────────────────────────────────────────────────────────────────────


def test_walk_all_happy_path_wraps_in_project_node(tmp_path, monkeypatch):
    """Contract: happy path returns ([{name, type=folder, open=True, children=[walked-root]}], 200)."""
    _write_toml(
        tmp_path,
        vps={"host": "srv982719", "identity": "~/.ssh/id_ed25519"},
        projects=[{"name": "proj", "vps_repo_path": "/srv/proj"}],
    )
    tree_vps = _fresh_tree_vps(tmp_path, monkeypatch)

    stdout = "d /srv/proj\nf /srv/proj/main.py\n"
    monkeypatch.setattr(
        tree_vps.subprocess,
        "run",
        lambda *a, **k: _make_completed(stdout=stdout),
    )
    rows, status = tree_vps.walk_all()

    assert status == 200
    assert len(rows) == 1
    top = rows[0]
    assert top["name"] == "proj"
    assert top["type"] == "folder"
    assert top.get("open") is True
    assert len(top["children"]) == 1

    walked_root = top["children"][0]
    assert walked_root["name"] == "/srv/proj"
    assert walked_root["type"] == "folder"
    assert "badge" not in walked_root
    inner_names = {c["name"] for c in walked_root["children"]}
    assert inner_names == {"main.py"}


def test_walk_all_argv_passes_through_ssh_options_and_identity(tmp_path, monkeypatch):
    """Contract: argv contains BatchMode, ControlMaster=auto, ControlPersist=60s, -i <identity>, host, --, then remote cmd."""
    custom_identity = "~/.ssh/custom_key"
    _write_toml(
        tmp_path,
        vps={"host": "srv982719", "identity": custom_identity},
        projects=[{"name": "proj", "vps_repo_path": "/srv/proj"}],
    )
    tree_vps = _fresh_tree_vps(tmp_path, monkeypatch)

    captured: dict[str, list[str]] = {}

    def fake_run(argv, **kw):  # noqa: ARG001
        captured["argv"] = argv
        return _make_completed(stdout="d /srv/proj\n")

    monkeypatch.setattr(tree_vps.subprocess, "run", fake_run)
    tree_vps.walk_all()

    argv = captured["argv"]
    # argv[0] is "ssh" on POSIX; on Windows it may resolve to the native
    # Win32-OpenSSH absolute path (see _ssh_bin) — check the basename.
    assert os.path.basename(argv[0]).lower() in ("ssh", "ssh.exe")

    # Pair-based assertions: each `-o KEY=VAL` is two consecutive elements.
    # Find adjacent pairs.
    options = []
    i = 0
    while i < len(argv):
        if argv[i] == "-o" and i + 1 < len(argv):
            options.append(argv[i + 1])
            i += 2
        else:
            i += 1
    assert "BatchMode=yes" in options
    if os.name == "nt":
        # Win32-OpenSSH has no mux support — _ssh_argv must NOT emit
        # ControlMaster options on Windows (they hard-fail every call).
        assert "ControlMaster=auto" not in options
        assert not any(o.startswith("ControlPath=") for o in options)
    else:
        assert "ControlMaster=auto" in options
        assert "ControlPersist=60s" in options
        # ControlPath is dynamic (depends on tmp_path); just check the prefix.
        cp_found = any(o.startswith("ControlPath=") for o in options)
        assert cp_found, f"ControlPath option missing from argv options: {options}"
    # ConnectTimeout=15 from SSH_TIMEOUT_S
    assert "ConnectTimeout=15" in options

    # Identity flag: -i <expanded-path>
    expected_identity = os.path.expanduser(custom_identity)
    assert "-i" in argv
    i_index = argv.index("-i")
    assert argv[i_index + 1] == expected_identity

    # Host appears as a positional element somewhere after the flags.
    assert "srv982719" in argv

    # The "--" option-terminator must appear between host and remote command.
    assert "--" in argv
    dd_index = argv.index("--")
    host_index = argv.index("srv982719")
    assert host_index < dd_index, "host must come before -- in the argv"
    # The remote command (find ...) must come after --.
    assert "find" in argv[dd_index + 1 :]


def test_walk_all_argv_shell_quotes_remote_command_so_globs_dont_expand_on_remote(tmp_path, monkeypatch):
    """REGRESSION (Plan 01-02 Step 2B): glob args in the remote command must be shell-quoted.

    Found end-to-end against srv982719: OpenSSH joins the remote argv with
    spaces and pipes the result to the remote ``$SHELL -c``, so unquoted
    ``*/.git*`` would be glob-expanded by the remote shell against the
    remote CWD (typically ``$HOME``) — breaking the ``find`` invocation:

        find: paths must precede expression: `ace-claude-toolkit/.gitignore'

    The fix is `shlex.quote` on every element of `*remote_cmd` inside
    `_ssh_argv`. This regression test asserts the contract from the stub
    side so a future maintainer can't accidentally drop the quoting.
    """
    _write_toml(
        tmp_path,
        vps={"host": "srv982719", "identity": "~/.ssh/id_ed25519"},
        projects=[{"name": "proj", "vps_repo_path": "/srv/proj"}],
    )
    tree_vps = _fresh_tree_vps(tmp_path, monkeypatch)

    captured: dict[str, list[str]] = {}

    def fake_run(argv, **kw):  # noqa: ARG001
        captured["argv"] = argv
        return _make_completed(stdout="d /srv/proj\n")

    monkeypatch.setattr(tree_vps.subprocess, "run", fake_run)
    tree_vps.walk_all()

    argv = captured["argv"]
    # The remote command is everything after the "--" terminator.
    dd = argv.index("--")
    remote = argv[dd + 1 :]
    # The glob pattern in the find argv must arrive shell-quoted so the
    # remote shell does NOT glob-expand it. shlex.quote('*/.git*') is
    # "'*/.git*'" (single-quoted).
    assert "'*/.git*'" in remote, (
        f"glob pattern must be shell-quoted in remote argv; got {remote!r}"
    )
    # And the single-token args must NOT be artificially quoted (shlex.quote
    # returns them unchanged) — keeps the argv readable for debugging.
    assert "find" in remote, f"find binary token must appear unquoted in {remote!r}"
    assert "/srv/proj" in remote, f"remote_root must appear unquoted in {remote!r}"
    assert "-maxdepth" in remote, f"-maxdepth flag must appear unquoted in {remote!r}"


def test_walk_remote_handles_real_world_remote_cwd_via_shell_quoting(tmp_path, monkeypatch):
    """REGRESSION (Plan 01-02 Step 2B): _walk_remote tolerates remote CWDs that match the glob.

    Belt-and-braces. Even if a future maintainer reverts the `shlex.quote`
    on `_ssh_argv` and re-introduces the bug, this test would catch it by
    simulating the remote shell's pre-find glob expansion: if globs are
    unquoted, the simulated `subprocess.run` returns the corresponding
    "find: paths must precede expression" stderr + rc=1, leading to a
    `badge="unreachable"` result — and this test asserts the OPPOSITE
    (a happy 200 tree). It would fail loudly if the quoting regressed.
    """
    _write_toml(
        tmp_path,
        vps={"host": "srv982719", "identity": "~/.ssh/id_ed25519"},
        projects=[{"name": "proj", "vps_repo_path": "/srv/proj"}],
    )
    tree_vps = _fresh_tree_vps(tmp_path, monkeypatch)

    def fake_run(argv, **kw):  # noqa: ARG001
        # Find the remote command after "--".
        dd = argv.index("--")
        remote = argv[dd + 1 :]
        # Simulate a remote shell that would glob-expand unquoted "*/.git*"
        # to a list of CWD-relative files — this is exactly the failure
        # mode observed against srv982719 in Plan 01-02.
        for arg in remote:
            if arg == "*/.git*":
                # Bug branch: unquoted glob. Simulate find's error.
                return _make_completed(
                    returncode=1,
                    stderr=(
                        "find: paths must precede expression: "
                        "`ace-claude-toolkit/.gitignore'\n"
                    ),
                )
        # Happy branch: quoted globs survived intact, find runs OK.
        return _make_completed(stdout="d /srv/proj\nf /srv/proj/main.py\n")

    monkeypatch.setattr(tree_vps.subprocess, "run", fake_run)
    rows, status = tree_vps.walk_all()
    assert status == 200
    walked = rows[0]["children"][0]
    assert walked.get("badge") is None, (
        f"the remote shell must NOT receive an unquoted glob — got badge={walked.get('badge')!r}"
    )
    assert {c["name"] for c in walked["children"]} == {"main.py"}
