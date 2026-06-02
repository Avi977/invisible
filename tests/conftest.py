"""Shared pytest config for the invisible test-suite.

This file does three things:

1. Registers the `--integration` CLI flag. Tests marked
   `pytest.mark.vps_integration` are SKIPPED by default; pass
   `--integration` to opt in.

2. Provides a session-scoped `vps_reachable` fixture that runs a single
   `ssh -o BatchMode=yes -o ConnectTimeout=4 srv982719 true` probe. If
   it fails for any reason (ssh missing, alias not configured, network
   down, host down), the fixture returns False. Live integration tests
   then SKIP cleanly rather than FAIL.

3. Provides a session-scoped `vps_configured_project` fixture that reads
   the user's REAL `~/.invisible/invisible.toml` and returns the first
   `(name, vps_repo_path)` tuple it finds — or None if no project has a
   `vps_repo_path` set yet.

The composite `live_vps_or_skip` fixture combines both: if either is
missing it calls `pytest.skip(...)` with a useful message; otherwise it
returns the `(name, vps_repo_path)` tuple for the live test to consume.

Hermetic tests in `tests/test_tree_vps.py` do NOT depend on any of these
fixtures — they monkeypatch `INVISIBLE_HOME` to a tmp_path themselves.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import pytest


# ────────────────────────────────────────────────────────────────────────
# CLI option + marker collection hook
# ────────────────────────────────────────────────────────────────────────


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register `--integration`: opt-in flag for live VPS tests."""
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help=(
            "Run live VPS integration tests against srv982719 "
            "(requires `ssh srv982719 echo ok` to succeed)."
        ),
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """If --integration was NOT passed, skip every item marked vps_integration."""
    if config.getoption("--integration"):
        return  # opt-in: leave the marker active; the fixture decides per-test
    skip_marker = pytest.mark.skip(
        reason="--integration not given (pass --integration to run live VPS tests)"
    )
    for item in items:
        if "vps_integration" in item.keywords:
            item.add_marker(skip_marker)


# ────────────────────────────────────────────────────────────────────────
# Reachability probe (session-scoped — runs once per pytest invocation)
# ────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def vps_reachable() -> bool:
    """Return True iff `ssh -o BatchMode=yes srv982719 true` exits 0.

    Returns False on any exception (FileNotFoundError if ssh is missing,
    TimeoutExpired if the network hangs, OSError for everything else).
    This fixture NEVER raises — failure to reach the VPS is a SKIP signal,
    not a test failure.
    """
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=4",
                "srv982719",
                "true",
            ],
            capture_output=True,
            timeout=8,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


# ────────────────────────────────────────────────────────────────────────
# Real-config discovery (session-scoped)
# ────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def vps_configured_project() -> Optional[tuple[str, str]]:
    """Return (name, vps_repo_path) for the first project that has both,
    reading the user's REAL ~/.invisible/invisible.toml.

    Returns None if:
    - No invisible.toml exists at ~/.invisible/.
    - No [[projects]] entry has both `name` AND `vps_repo_path`.
    """
    try:
        try:
            import tomllib  # py3.11+
        except ImportError:  # pragma: no cover
            import tomli as tomllib  # type: ignore

        home = Path(os.path.expanduser(os.environ.get("INVISIBLE_HOME", "~/.invisible")))
        toml_path = home / "invisible.toml"
        if not toml_path.exists():
            return None
        with open(toml_path, "rb") as f:
            cfg = tomllib.load(f)
        for p in cfg.get("projects", []) or []:
            name = p.get("name")
            vps_repo_path = (p.get("vps_repo_path", "") or "").strip()
            if name and vps_repo_path:
                return (name, vps_repo_path)
        return None
    except Exception:  # noqa: BLE001 — never let config-discovery raise into tests
        return None


# ────────────────────────────────────────────────────────────────────────
# Composite gate: SKIP cleanly if either prerequisite is missing
# ────────────────────────────────────────────────────────────────────────


@pytest.fixture
def live_vps_or_skip(
    vps_reachable: bool,
    vps_configured_project: Optional[tuple[str, str]],
) -> tuple[str, str]:
    """Return (name, vps_repo_path) for a live VPS test, or SKIP cleanly.

    Skips with a descriptive reason if:
    - srv982719 isn't reachable via BatchMode ssh (Plan 01-01 prerequisite).
    - No project in ~/.invisible/invisible.toml has a vps_repo_path set.
    """
    if not vps_reachable:
        pytest.skip(
            "srv982719 not reachable (BatchMode ssh failed) — "
            "verify Plan 01-01 setup: `ssh srv982719 echo ok` should succeed"
        )
    if vps_configured_project is None:
        pytest.skip(
            "no [[projects]] in ~/.invisible/invisible.toml has vps_repo_path set — "
            "add one (e.g. vps_repo_path = \"/srv/<your-project>\") and re-run"
        )
    return vps_configured_project
