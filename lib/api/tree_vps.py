"""VPS tree walker for the Folders page (SSH + remote ``find``, 503 when unconfigured).

Replaces the ``FOLDERS.vps`` mock in ``frontend/data.jsx`` with a real
tree of every project's VPS-side checkout, read over SSH with
ControlMaster multiplexing so chatty UI refreshes don't re-handshake.

Module exports (consumed by ``bin/invisible-dashboard`` in Plan INV-01-03):

- ``walk_all(project=None) -> tuple[list[dict], int]`` — returns
  ``(payload, status_code)``. The status lets the HTTP handler set 503
  cleanly without parsing the payload:
    - ``([…], 200)`` — happy path; one top-level node per project.
    - ``([VPS_NOT_CONFIGURED], 503)`` — ``vps.host`` is the dev-default
      empty string. This is the graceful-degradation requirement
      (REQ-03 / plan must_haves): the daemon must NOT crash and the
      frontend must be able to render a "VPS not configured" placeholder.
    - ``([{"error": …}], 503)`` — ``vps.host`` failed the validation
      regex (defense-in-depth; argv-based exec already blocks injection).
    - ``([], 200)`` — ``project`` was given but doesn't match any
      configured project (cross-walker BLOCKER #2 contract; mirrors
      ``tree_local.walk_all`` and ``tree_repo.walk_all``).
- ``VPS_NOT_CONFIGURED`` — the canonical error body dict for the empty-host
  case. Re-exported so callers and tests can compare by value.

Tree-node shape (matches ``frontend/data.jsx:131-150``):

    Top-level: {name: "<project-name>", type: "folder", open: true,
                  children: [<walked-vps-root-node>]}
    Walked root: {name: "<remote_root>", type: "folder", open: true,
                    children: [...]}  (or badge="unreachable" on SSH failure)
    Children:  {name: "<basename>", type: "folder" | "file",
                  children?: [<node>, ...]}

ControlMaster:

The first SSH call to a host opens a master connection at
``$INVISIBLE_HOME/run/ssh-cm-<conn>``; subsequent calls reuse it
(``-o ControlMaster=auto -o ControlPersist=60s``). This keeps the
"chatty refresh" cost down to a single TCP/TLS handshake per minute.
The dedicated socket-dir under ``$INVISIBLE_HOME/run`` prevents
collision with the user's own SSH sessions.

Security:

- All subprocess calls use a list ``argv`` with ``shell=False`` (the default).
- ``_validate_host`` rejects hosts containing shell-meta characters
  (``;|&$`` and friends). Even though argv-based exec blocks injection,
  rejecting bad hosts surfaces config bugs early.
- ``_validate_remote_path`` rejects relative paths and any path
  containing ``..`` — required by T-INV01-09 in the threat register.
- ``-o BatchMode=yes`` ensures SSH never prompts for a password (which
  would hang the dashboard request indefinitely). The first manual SSH
  to accept a new host key is part of the documented setup; we don't
  disable ``StrictHostKeyChecking`` (T-INV01-12 disposition: accept).
- ``find -maxdepth 6`` caps remote tree size; symlinks excluded.

Limitations:

- A symlink loop on the remote could still slow ``find`` down — bounded
  by ``MAX_DEPTH`` and the subprocess ``timeout``.
- We do not (yet) cache VPS responses; the SSH ControlMaster makes
  re-fetches cheap enough for v1. Add a TTL cache if the UI gets chatty.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from config import home, load_toml

# ────────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────────

# Canonical error body for the empty-host case. Re-exported so the route
# handler and tests can compare by value rather than by string.
VPS_NOT_CONFIGURED: dict[str, str] = {"error": "vps.host not configured"}

# Cap the remote walk depth. 6 levels is enough for any real repo while
# keeping the response under a few thousand nodes and bounding the cost
# of a pathological symlink layout. Matches the spirit of the local
# walker's MAX_DEPTH=12 (deeper trees are fine locally; over the wire
# we want tighter bounds).
MAX_DEPTH = 6

# SSH connection + subprocess timeout. Mirrors the local-walker's
# generous-enough budget for first-time ControlMaster setup over a
# decent network.
SSH_TIMEOUT_S = 15

# Mirrors tree_local.IGNORE_NAMES — directories that explode tree size
# without adding signal. ``find`` is told to ``-not -path`` these.
_IGNORE_DIRS: tuple[str, ...] = (
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
)

# ────────────────────────────────────────────────────────────────────────
# Validation
# ────────────────────────────────────────────────────────────────────────

# Allow user@hostname or hostname only. Hostnames are alphanumerics with
# dot/hyphen/underscore separators. Refuse anything with ;|$&` or spaces —
# the defense-in-depth gate for T-INV01-07.
_HOST_RE = re.compile(r"^(?:[A-Za-z0-9_.-]+@)?[A-Za-z0-9._-]+$")

# Absolute path made of alphanumerics, dot, slash, underscore, hyphen,
# tilde, and plus. We explicitly reject ``..`` segments in addition to
# the regex (the regex would allow ``/foo/..`` since ``..`` matches the
# character class). T-INV01-09 mitigation.
_PATH_RE = re.compile(r"^/[A-Za-z0-9_./~+-]+$")


def _validate_host(host: str) -> bool:
    """Return True if ``host`` is a syntactically valid SSH target."""
    if not host or not isinstance(host, str):
        return False
    return bool(_HOST_RE.match(host))


def _validate_remote_path(p: str) -> bool:
    """Return True if ``p`` is an acceptable remote path for ``find``.

    Rules:
    - Must be a non-empty string.
    - Must start with ``/`` (no relative paths).
    - Must NOT contain a ``..`` component.
    - Must consist of allowed characters only (no shell-meta).
    """
    if not p or not isinstance(p, str):
        return False
    if ".." in p.split("/"):
        return False
    return bool(_PATH_RE.match(p))


# ────────────────────────────────────────────────────────────────────────
# ControlMaster socket
# ────────────────────────────────────────────────────────────────────────


def _cm_path() -> str:
    """Return the ControlMaster socket-template path.

    ``%r`` (remote user), ``%h`` (hostname), ``%p`` (port) are SSH
    expansion tokens — they're substituted by OpenSSH at runtime so a
    single template can multiplex many destinations.

    Creates ``$INVISIBLE_HOME/run/`` if missing. The directory is mode
    700 by default (SSH ControlMaster refuses world-readable sockets).
    """
    run_dir = home() / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    return str(run_dir / "ssh-cm-%r@%h:%p")


# ────────────────────────────────────────────────────────────────────────
# SSH argv builder
# ────────────────────────────────────────────────────────────────────────


def _ssh_argv(host: str, identity: str, *remote_cmd: str) -> list[str]:
    """Build the argv for an SSH call; never invoke a shell.

    The ``--`` before ``*remote_cmd`` terminates SSH's option parsing so
    a remote path beginning with ``-`` can't be mistaken for an SSH
    flag. ``BatchMode=yes`` prevents any interactive password prompt
    (we rely on key-based auth). ``ControlMaster=auto`` + the dedicated
    socket path under ``$INVISIBLE_HOME/run`` makes repeat calls fast.
    """
    return [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", f"ConnectTimeout={SSH_TIMEOUT_S}",
        "-o", "ControlMaster=auto",
        "-o", f"ControlPath={_cm_path()}",
        "-o", "ControlPersist=60s",
        "-i", os.path.expanduser(identity),
        host,
        "--",
        *remote_cmd,
    ]


# ────────────────────────────────────────────────────────────────────────
# Tree assembly
# ────────────────────────────────────────────────────────────────────────


def _insert(node_list: list[dict[str, Any]], parts: list[str], kind: str) -> None:
    """Insert a single path's components into a nested tree.

    Twin of ``tree_repo._insert``. ``kind`` here is ``"f"`` (file) or
    ``"d"`` (directory) — the ``%y`` token from ``find -printf``.
    Intermediate path components are always created as folders.
    """
    if not parts:
        return
    head, *rest = parts

    existing = next((n for n in node_list if n.get("name") == head), None)
    if existing is None:
        if rest:
            existing = {"name": head, "type": "folder", "children": []}
        else:
            existing = (
                {"name": head, "type": "file"}
                if kind == "f"
                else {"name": head, "type": "folder", "children": []}
            )
        node_list.append(existing)
    else:
        if rest and existing.get("type") == "file":
            existing["type"] = "folder"
            existing["children"] = []

    if rest:
        children = existing.setdefault("children", [])
        _insert(children, rest, kind)


# ────────────────────────────────────────────────────────────────────────
# Remote walker
# ────────────────────────────────────────────────────────────────────────


def _walk_remote(host: str, identity: str, remote_root: str) -> dict[str, Any]:
    """Walk ``remote_root`` on ``host`` and return a single tree node.

    On any SSH or ``find`` failure, returns a placeholder node with
    ``badge="unreachable"`` so the frontend can render the project
    bucket without crashing.
    """
    # The remote find argv. We use -not -path to prune the ignore-list
    # at the source so we don't ship megabytes of node_modules paths
    # across the wire. -printf "%y %p\n" emits one entry per line:
    # the type char (f/d/l/…) and the full path.
    find_argv: list[str] = [
        "find",
        remote_root,
        "-maxdepth",
        str(MAX_DEPTH),
    ]
    for ign in _IGNORE_DIRS:
        find_argv.extend(["-not", "-path", f"*/{ign}*"])
    find_argv.extend(["-printf", "%y %p\n"])

    try:
        result = subprocess.run(
            _ssh_argv(host, identity, *find_argv),
            capture_output=True,
            text=True,
            timeout=SSH_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        sys.stderr.write(f"[tree_vps] ssh/find failed for {host}:{remote_root}: {exc}\n")
        return {
            "name": remote_root,
            "type": "folder",
            "children": [],
            "badge": "unreachable",
        }

    if result.returncode != 0:
        err = (result.stderr or "").strip()
        sys.stderr.write(
            f"[tree_vps] ssh/find {host}:{remote_root} returned {result.returncode}: {err}\n"
        )
        return {
            "name": remote_root,
            "type": "folder",
            "children": [],
            "badge": "unreachable",
        }

    # Strip the remote_root prefix so the relative path becomes the
    # nested-tree key. Treat the remote_root itself as the wrapping
    # node and put its contents in children.
    root_prefix = remote_root.rstrip("/") + "/"
    children: list[dict[str, Any]] = []

    for raw_line in result.stdout.splitlines():
        line = raw_line.rstrip("\r\n")
        if not line or " " not in line:
            continue
        kind, rpath = line.split(" ", 1)
        # Skip symlinks (l) to match the local-walker's symlink policy
        # and avoid leaking out-of-tree data via a bad link.
        if kind not in ("f", "d"):
            continue
        # The root itself is "d <remote_root>" — emit as the wrapping
        # node, not as a child of itself.
        if rpath == remote_root or rpath == remote_root.rstrip("/"):
            continue
        if not rpath.startswith(root_prefix):
            # Defensive: skip anything that didn't land under our root
            # (shouldn't happen — find descends only from remote_root).
            continue
        rel = rpath[len(root_prefix):]
        if not rel:
            continue
        parts = rel.split("/")
        _insert(children, parts, kind)

    return {
        "name": remote_root,
        "type": "folder",
        "open": True,
        "children": children,
    }


# ────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────


def walk_all(project: str | None = None) -> tuple[list[dict[str, Any]], int]:
    """Walk every project's VPS-side tree.

    Return contract (evaluated in this order):
    1. ``([], 200)`` — ``project`` is set but doesn't match any configured
       project. This check runs first so the cross-walker BLOCKER #2
       contract holds regardless of VPS-host config state. Never
       returns ``[None]``.
    2. ``([VPS_NOT_CONFIGURED], 503)`` — ``vps.host`` empty (dev default).
    3. ``([{"error": …}], 503)`` — ``vps.host`` fails the validation regex.
    4. ``([…], 200)`` — normal happy path.

    A project missing ``vps_repo_path`` is silently skipped (VPS handoff
    is per-project opt-in; not configuring it is not an error).
    """
    cfg = load_toml()
    vps_cfg = cfg.get("vps", {}) or {}
    host = (vps_cfg.get("host", "") or "").strip()
    projects = cfg.get("projects", []) or []

    # Cross-walker BLOCKER #2 short-circuit: an unknown ``project`` is
    # always ``([], 200)``, regardless of vps.host state. This must run
    # BEFORE the host-config check so a `walk_all(project='__nope__')`
    # call returns the same shape whether the user has configured VPS
    # or not — matching ``tree_local`` and ``tree_repo`` semantics.
    if project is not None:
        matched = next((p for p in projects if p.get("name") == project), None)
        if matched is None:
            return [], 200
        candidates: list[dict[str, Any]] = [matched]
    else:
        candidates = list(projects)

    # Graceful degradation: empty host is the dev default. Return 503
    # with a clear body so the frontend can render a placeholder. We
    # only reach this point if either no ``project`` filter was given
    # or the named project does exist in the config.
    if host == "":
        return [VPS_NOT_CONFIGURED], 503

    # Defense-in-depth: reject hosts with shell-meta even though the
    # argv-based exec would already neutralize them.
    if not _validate_host(host):
        return [{"error": f"invalid vps.host: {host!r}"}], 503

    identity = vps_cfg.get("identity", "~/.ssh/id_ed25519")

    # Build the (name, vps_repo_path) work list, skipping anything
    # without a vps_repo_path or with an invalid one.
    work: list[tuple[str, str]] = []

    for p in candidates:
        name = p.get("name")
        if not name:
            continue
        vps_path = (p.get("vps_repo_path", "") or "").strip()
        if not vps_path:
            # Per-project opt-in; not an error.
            continue
        if not _validate_remote_path(vps_path):
            sys.stderr.write(
                f"[tree_vps] skipping project {name!r}: invalid vps_repo_path {vps_path!r}\n"
            )
            continue
        work.append((name, vps_path))

    # Walk each remote tree and wrap as a top-level project node.
    out: list[dict[str, Any]] = []
    for name, vps_path in work:
        walked = _walk_remote(host, identity, vps_path)
        if walked is None:  # defense-in-depth — _walk_remote never returns None today
            continue
        out.append(
            {
                "name": name,
                "type": "folder",
                "open": True,
                "children": [walked],
            }
        )

    # Final BLOCKER #2 safety net: filter any None that snuck into the list.
    out = [n for n in out if n is not None]

    return out, 200
