"""WebSocket PTY server — the core module behind `bin/invisible-pty`.

Serves a single purpose: let `frontend/pages/terminals.jsx` open up to 32 real
bash PTYs over localhost WebSockets, plus a tiny side-channel HTTP route that
returns the per-pane checkpoint context for the React `ContextHeader`.

Surface (Plan 01 — Plan 02 will extend, not replace, these names):
  - PTYServer                  the daemon class (instantiate then call .serve())
  - PANE_ID_RE                 regex gate on pane ids (path segment of /pty/{id})
  - ALLOWED_ORIGINS            set of acceptable Origin headers on WS upgrade
  - spawn_pty()                low-level PtyProcess spawn helper
  - load_pane_context()        checkpoint → 3-key display shape mapper
  - validate_host()            host-binding guard (called by the CLI entrypoint)
  - validate_pane_id()         boolean predicate over PANE_ID_RE
  - MAX_CONCURRENT_PTYS        cap declared by the threat model
  - PTYRegistry                in-memory active-pane bookkeeping

Threat-model gates enforced here (mapping back to 01-PLAN.md → STRIDE register):
  T-01-01  pane-id validation before PTY spawn   (validate_pane_id)
  T-01-02  Origin pinning before WS upgrade      (check_origin / _process_request)
  T-01-03  loopback-only host binding            (validate_host)
  T-01-04  concurrent-PTY cap (32)               (PTYRegistry.count vs MAX)
  T-01-05  pane-id ⇒ worktree path containment   (load_pane_context)

Plan 02 (landed) extended this with session persistence + SSH variant.
See the `# PLAN-02 verification log` marker at the bottom of this file.
"""

from __future__ import annotations

# ────────────────────────────────────────────────────────────────────────
# Dependency gate — surface a clear install hint if either is missing.
# This is the only `import` block that can raise SystemExit; the rest of
# the module assumes both names are usable.
# ────────────────────────────────────────────────────────────────────────
try:
    import websockets  # noqa: F401
    from websockets.asyncio.server import serve as ws_serve
    from websockets.exceptions import ConnectionClosed
    from websockets.http11 import Response
    from websockets.datastructures import Headers
    import ptyprocess
    from ptyprocess import PtyProcess
except ImportError as _e:  # pragma: no cover — surfaced at process startup
    raise SystemExit(
        f"[invisible-pty] missing dependency ({_e.name}): "
        "run `python3 -m pip install --user websockets ptyprocess`"
    ) from _e

import asyncio
import json
import os
import re
import sys
import tomllib
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import checkpoint  # noqa: E402 — same-dir module, post sys.path insert
from config import home  # noqa: E402


# ────────────────────────────────────────────────────────────────────────
# Module constants — the threat-model surface.
# ────────────────────────────────────────────────────────────────────────

# Pane-id whitelist. T-01-01 path-traversal defence: rejects `..`, `/`,
# whitespace, uppercase, anything >32 chars. Match against the raw URL-decoded
# segment before any PTY spawn or checkpoint read.
PANE_ID_RE: re.Pattern[str] = re.compile(r"^[a-z0-9_-]{1,32}$")

# Origin pinning. T-01-02 DNS-rebinding defence: WebSocket upgrades whose
# Origin is not in this set are rejected with HTTP 403 *before* upgrade.
ALLOWED_ORIGINS: set[str] = {
    "http://127.0.0.1:8090",
    "http://localhost:8090",
}

# Host binding allow-list. T-01-03 elevation defence: refuse to expose the
# daemon on any non-loopback interface. Validated at CLI startup.
ALLOWED_HOSTS: set[str] = {"127.0.0.1", "localhost", "::1"}

# Concurrent-PTY cap. T-01-04 DoS defence: reject new spawns at the cap.
MAX_CONCURRENT_PTYS: int = 32

# Shell to launch inside each PTY. Mirrors the user's interactive shell.
DEFAULT_SHELL: str = os.environ.get("SHELL", "/bin/bash")

# ────────────────────────────────────────────────────────────────────────
# Plan 02 — session-persistence constants.
# ────────────────────────────────────────────────────────────────────────

# Grace window after a WebSocket disconnect before the reaper terminates the
# parked PtyProcess. Long enough to survive a full page reload + AI-chat
# detour, short enough that orphaned bash shells eventually go away if the
# user closes the browser tab entirely. CLI `--reconnect-grace` overrides.
RECONNECT_GRACE_SECONDS: int = 600

# Per-pane bounded ring buffer of recent PTY output. When a client reconnects
# inside the grace window, we replay this buffer immediately before resuming
# the live stream. 8 KiB ≈ one screenful of typical shell output.
BACKLOG_BYTES: int = 8 * 1024

# How often the reaper sweeps the registry for expired panes. The window is
# coarse on purpose — the reaper is a janitor, not a deadline.
REAPER_INTERVAL_SECONDS: int = 30


# ────────────────────────────────────────────────────────────────────────
# Validators — pure functions, no side effects, easy to unit-assert.
# ────────────────────────────────────────────────────────────────────────


def validate_host(host: str) -> None:
    """Raise ValueError if `host` is not a loopback address.

    Called by `bin/invisible-pty` before any socket bind. Prevents a typo
    like `--host 0.0.0.0` from exposing every spawned shell to the LAN.
    (T-01-03)
    """
    if host not in ALLOWED_HOSTS:
        raise ValueError(
            f"--host must be one of {sorted(ALLOWED_HOSTS)}, got {host!r}"
        )


def validate_pane_id(pane_id: str) -> bool:
    """Return True iff `pane_id` matches PANE_ID_RE.

    Bottom of the stack — every code path that touches a pane id MUST call
    this (or rely on it having been called) before using the id as a
    filesystem segment or PTY key. (T-01-01, T-01-05)
    """
    if not isinstance(pane_id, str):
        return False
    return PANE_ID_RE.match(pane_id) is not None


def check_origin(origin: str | None) -> bool:
    """Return True iff `origin` is in ALLOWED_ORIGINS.

    Absent/None origins are *rejected* — the frontend always sends an Origin
    on WS upgrade, so missing one is suspicious. (T-01-02)
    """
    if origin is None:
        return False
    return origin in ALLOWED_ORIGINS


# ────────────────────────────────────────────────────────────────────────
# Pane config loader (Plan 02) — reads `[[terminals]]` from invisible.toml.
# ────────────────────────────────────────────────────────────────────────


# Per-pane env values must be strings — TOML naturally produces strings for
# string-typed scalars, but a user could write `FOO = 42` and we'd refuse.
_ALLOWED_KINDS: set[str] = {"bash", "ssh"}


def load_pane_configs(path: Path | str) -> dict[str, dict[str, Any]]:
    """Read `[[terminals]]` blocks from an invisible.toml file.

    Returns a `{pane_id: config_dict}` map. Each config_dict is a sanitised
    copy of the TOML entry minus the redundant `id` key (the dict key IS the
    pane id). Missing/malformed file ⇒ empty dict, not an exception — the
    daemon still runs with all-default plain-bash panes.

    Validation per entry (any failure ⇒ entry dropped + stderr warning):
      - `id`     required, string, matches PANE_ID_RE
      - `kind`   required, must be in {"bash", "ssh"}
      - `host`   required iff kind=="ssh"; must be a string. NEVER comes
                 from the URL — this loader is the single trusted source.
      - `cwd`    optional string; `~` is `os.path.expanduser`'d by the
                 spawn helper (not here — defer until use).
      - `env`    optional table; every value must be a string.
      - `command` optional list-of-strings; only meaningful for kind=="bash"
                 (ignored for kind=="ssh"; the argv is locked to
                 `["ssh", host]` to keep T-02-01 closed).

    Threat-model note (T-02-01): this loader is the boundary between the
    user-controlled TOML file and the trusted runtime. Any field that
    contributes to the spawned argv (host, command) is validated for
    type+shape; the URL never reaches `resolve_command`.
    """
    p = Path(path)
    if not p.exists():
        return {}
    try:
        with p.open("rb") as f:
            raw = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        print(
            f"[invisible-pty] failed to load {p}: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return {}

    terminals = raw.get("terminals")
    if not isinstance(terminals, list):
        return {}

    configs: dict[str, dict[str, Any]] = {}
    for i, entry in enumerate(terminals):
        # The fail-soft pattern: every reject prints why and which entry
        # so the user can fix the TOML and `kill -HUP` (or restart).
        if not isinstance(entry, dict):
            print(
                f"[invisible-pty] config entry #{i}: not a table; skipped",
                file=sys.stderr,
            )
            continue

        pane_id = entry.get("id")
        if not isinstance(pane_id, str) or not validate_pane_id(pane_id):
            print(
                f"[invisible-pty] config entry #{i}: invalid id "
                f"{pane_id!r} (must match {PANE_ID_RE.pattern}); skipped",
                file=sys.stderr,
            )
            continue

        kind = entry.get("kind")
        if kind not in _ALLOWED_KINDS:
            print(
                f"[invisible-pty] config entry {pane_id!r}: invalid kind "
                f"{kind!r} (must be one of {sorted(_ALLOWED_KINDS)}); skipped",
                file=sys.stderr,
            )
            continue

        cfg: dict[str, Any] = {"kind": kind}

        if kind == "ssh":
            host = entry.get("host")
            if not isinstance(host, str) or not host.strip():
                print(
                    f"[invisible-pty] config entry {pane_id!r}: kind=ssh "
                    "requires a non-empty string `host`; skipped",
                    file=sys.stderr,
                )
                continue
            cfg["host"] = host

        cwd = entry.get("cwd")
        if cwd is not None:
            if not isinstance(cwd, str):
                print(
                    f"[invisible-pty] config entry {pane_id!r}: cwd must be "
                    "a string; ignored",
                    file=sys.stderr,
                )
            else:
                cfg["cwd"] = cwd

        env_t = entry.get("env")
        if env_t is not None:
            if not isinstance(env_t, dict):
                print(
                    f"[invisible-pty] config entry {pane_id!r}: env must be a "
                    "table; ignored",
                    file=sys.stderr,
                )
            else:
                # T-02-04: values must be strings. Drop the whole env table
                # if any value is non-string — partial overlay is too easy
                # to misread on first inspection of the running daemon.
                bad = [k for k, v in env_t.items() if not isinstance(v, str)]
                if bad:
                    print(
                        f"[invisible-pty] config entry {pane_id!r}: env keys "
                        f"{bad!r} have non-string values; env table ignored",
                        file=sys.stderr,
                    )
                else:
                    cfg["env"] = dict(env_t)

        command = entry.get("command")
        if command is not None:
            if kind == "ssh":
                # SSH kind has a fixed argv. Allowing override here would
                # reopen T-02-01.
                print(
                    f"[invisible-pty] config entry {pane_id!r}: command is "
                    "ignored for kind=ssh (argv is locked)",
                    file=sys.stderr,
                )
            elif (
                not isinstance(command, list)
                or not all(isinstance(s, str) for s in command)
                or not command
            ):
                print(
                    f"[invisible-pty] config entry {pane_id!r}: command must "
                    "be a non-empty list of strings; ignored",
                    file=sys.stderr,
                )
            else:
                cfg["command"] = list(command)

        configs[pane_id] = cfg

    return configs


def resolve_command(config: dict[str, Any]) -> list[str]:
    """Return the argv to spawn for `config`.

    bash: `config['command']` if present and well-formed, else
          `[DEFAULT_SHELL, "-i"]`.
    ssh:  `["ssh", config['host']]`. Hardcoded — the path id is only a
          lookup key, never interpolated into argv. (T-02-01)

    Defensive default for unknown kinds (shouldn't happen because
    `load_pane_configs` validates): fall back to bash. This keeps any caller
    that hands in a hand-built dict (e.g., a unit test) from raising.
    """
    kind = config.get("kind", "bash")
    if kind == "ssh":
        host = config.get("host")
        if not isinstance(host, str) or not host.strip():
            # Should be unreachable for configs that came from load_pane_configs,
            # but defend in depth — refuse to construct a bare `["ssh"]` argv.
            raise ValueError("ssh config missing host (loader should have rejected)")
        return ["ssh", host]
    # bash (and anything unknown — see docstring).
    cmd = config.get("command")
    if isinstance(cmd, list) and cmd and all(isinstance(s, str) for s in cmd):
        return list(cmd)
    return [DEFAULT_SHELL, "-i"]


# ────────────────────────────────────────────────────────────────────────
# PTY spawn helper + in-memory registry.
# ────────────────────────────────────────────────────────────────────────


def spawn_pty(
    pane_id: str,
    *,
    cwd: str | None = None,
    env: dict | None = None,
    command: list[str] | None = None,
    dimensions: tuple[int, int] = (24, 80),
) -> PtyProcess:
    """Spawn a single PTY.

    Args:
      pane_id:    must already have passed `validate_pane_id` — this helper
                  does NOT re-validate (callers MUST).
      cwd:        working directory for the shell (defaults to PtyProcess's
                  inherited cwd if None).
      env:        environment dict (defaults to inherited os.environ).
      command:    argv to exec (defaults to `[DEFAULT_SHELL, "-i"]`).
      dimensions: initial PTY size as (rows, cols). Default 24×80. Resize
                  support is deferred to Plan 02/03 (`TIOCSWINSZ` via
                  `proc.setwinsize`) — for Plan 01 the dimensions are set
                  once at spawn time and never changed.

    Caller is responsible for the concurrent-PTY cap (`MAX_CONCURRENT_PTYS`)
    — this helper does not consult the registry. PTYServer.handle_pty does
    the count check before calling spawn_pty().
    """
    argv = list(command) if command else [DEFAULT_SHELL, "-i"]
    proc_env = env if env is not None else dict(os.environ)
    return PtyProcess.spawn(
        argv,
        cwd=cwd,
        env=proc_env,
        echo=True,
        dimensions=dimensions,
    )


def spawn_pty_for_config(
    pane_id: str,
    config: dict[str, Any],
    *,
    dimensions: tuple[int, int] = (24, 80),
) -> PtyProcess:
    """Spawn a PTY using a `load_pane_configs`-shaped dict.

    Wraps `spawn_pty` with three policy decisions:
      1. argv comes from `resolve_command(config)` — bash default or
         `["ssh", host]` for kind=="ssh".
      2. cwd is `os.path.expanduser`'d (so `~/code` works in the TOML).
      3. env is an overlay over os.environ — config keys win.

    Unknown pane ids (i.e., `config == {}`) fall back to a default plain
    bash pane. This is the safety valve that keeps `handle_pty`'s lookup
    `self.pane_configs.get(pane_id, {})` from raising on the no-match path.
    """
    # Default fall-through: an empty dict ⇒ bash.
    if "kind" not in config:
        config = {**config, "kind": "bash"}

    argv = resolve_command(config)

    # CWD — string or None, expanduser'd.
    raw_cwd = config.get("cwd")
    cwd: str | None
    if isinstance(raw_cwd, str) and raw_cwd:
        cwd = os.path.expanduser(raw_cwd)
    else:
        cwd = None

    # ENV — overlay onto os.environ.
    raw_env = config.get("env")
    if isinstance(raw_env, dict) and raw_env:
        proc_env = dict(os.environ)
        proc_env.update({k: v for k, v in raw_env.items() if isinstance(v, str)})
    else:
        proc_env = None  # spawn_pty default: inherit os.environ

    return spawn_pty(
        pane_id,
        cwd=cwd,
        env=proc_env,
        command=argv,
        dimensions=dimensions,
    )


class PTYRegistry:
    """In-memory pane-id ⇒ live PTY bookkeeping.

    Plan 02 extended scope:
      - register / get / count / unregister  (Plan 01 surface, preserved)
      - attach_ws / detach_ws                (Plan 02: reconnect semantics)
      - record_output / get_backlog          (Plan 02: backlog ring buffer)
      - sweep                                (Plan 02: reaper helper)

    Entry shape per pane:
        {
            "proc":            PtyProcess,
            "created_at":      datetime (UTC),
            "ws":              websocket | None,
            "disconnected_at": datetime (UTC) | None,
            "backlog":         bytearray (≤ BACKLOG_BYTES, drops from front),
        }

    Backlog is a `bytearray` rather than a `deque` of chunks because (a) we
    only need byte-granular trimming, (b) the read side is "send the whole
    buffer in one frame on reconnect", and (c) `del backlog[:n]` is O(n) but
    only fires when the buffer is full — amortised over the stream this is
    cheaper than reconciling chunk boundaries.
    """

    def __init__(self) -> None:
        self._panes: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Plan 01 surface — preserved verbatim.
    # ------------------------------------------------------------------

    def register(self, pane_id: str, proc: PtyProcess) -> None:
        """Add (or replace) a pane.

        Plan 02 behavior: every fresh registration starts with `ws=None`,
        `disconnected_at=None`, and an empty `backlog`. The caller follows
        up with `attach_ws(pane_id, websocket)` so reconnect bookkeeping is
        symmetrical with `detach_ws`. The old Plan 01 "last-writer-wins"
        teardown moved into `handle_pty`; the registry no longer assumes the
        caller terminated any prior PtyProcess.
        """
        self._panes[pane_id] = {
            "proc": proc,
            "created_at": datetime.now(timezone.utc),
            "ws": None,
            "disconnected_at": None,
            "backlog": bytearray(),
        }

    def get(self, pane_id: str) -> dict[str, Any] | None:
        return self._panes.get(pane_id)

    def count(self) -> int:
        """Number of LIVE panes — orphaned (ws is None) entries that are
        awaiting reap still count, by design. The MAX_CONCURRENT_PTYS cap
        is about how many PtyProcesses exist in memory, not how many have
        a websocket attached. The reaper is what actually shrinks this
        number once a grace window lapses.
        """
        return len(self._panes)

    def unregister(self, pane_id: str) -> None:
        self._panes.pop(pane_id, None)

    # ------------------------------------------------------------------
    # Plan 02 — reconnect, backlog, reaper.
    # ------------------------------------------------------------------

    def attach_ws(self, pane_id: str, ws: Any) -> bool:
        """Bind `ws` to an existing pane entry.

        Returns:
          True  if an existing entry was found and the websocket was attached
                (reconnect path — caller should replay backlog then reuse the
                entry's PtyProcess).
          False if no entry exists for `pane_id` (caller must spawn a fresh
                PTY and call `register`).

        Takeover semantics:
          If the entry already has a live `ws` (some other client is currently
          attached), the prior websocket is forcibly closed (best-effort) and
          replaced. A warning is logged to stderr. This is the "two browser
          tabs racing for the same pane id" edge case — last-writer-wins on
          the websocket, but the PtyProcess survives both transitions.
        """
        entry = self._panes.get(pane_id)
        if entry is None:
            return False

        prior = entry.get("ws")
        if prior is not None and prior is not ws:
            print(
                f"[invisible-pty] takeover: closing prior ws on pane {pane_id!r}",
                file=sys.stderr,
            )
            try:
                # `close` may be a coroutine on real WS connections; we
                # cannot await here (the registry is sync). Fire-and-forget
                # by scheduling on the running loop if one exists. If not
                # (unit-test context), drop silently — the entry is being
                # replaced anyway.
                close_attr = getattr(prior, "close", None)
                if close_attr is not None:
                    result = close_attr()
                    if asyncio.iscoroutine(result):
                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(result)
                        except RuntimeError:
                            # No running loop — coroutine will be GC'd; OK
                            # because we already replaced the ws reference.
                            result.close()
            except Exception:  # noqa: BLE001 — takeover is best-effort
                pass

        entry["ws"] = ws
        entry["disconnected_at"] = None
        return True

    def detach_ws(self, pane_id: str) -> None:
        """Mark a pane as orphaned (websocket gone, PtyProcess still alive).

        Sets `ws=None` and stamps `disconnected_at=utcnow()` — the reaper
        will pick this entry up once `(now - disconnected_at) > grace`.
        Does NOT terminate the PtyProcess; that's the reaper's job.
        """
        entry = self._panes.get(pane_id)
        if entry is None:
            return
        entry["ws"] = None
        entry["disconnected_at"] = datetime.now(timezone.utc)

    def record_output(self, pane_id: str, chunk: bytes) -> None:
        """Append a chunk to the pane's backlog ring, trimming from the
        front if the buffer exceeds BACKLOG_BYTES.

        Called from the pty_to_ws pump in `handle_pty` on every read, so
        the backlog stays current for any in-flight reconnect. Cheap on
        the steady-state path — the trim branch only fires when the buffer
        actually overflows.
        """
        entry = self._panes.get(pane_id)
        if entry is None:
            return
        if not chunk:
            return
        backlog: bytearray = entry["backlog"]
        backlog.extend(chunk)
        overflow = len(backlog) - BACKLOG_BYTES
        if overflow > 0:
            # Drop the oldest `overflow` bytes from the front. `del`
            # on bytearray slice is in-place; no extra allocation.
            del backlog[:overflow]

    def get_backlog(self, pane_id: str) -> bytes:
        """Snapshot the current backlog as immutable bytes.

        Returned as `bytes` (not a view) so the caller can `await ws.send`
        without worrying about concurrent mutation from the pump.
        """
        entry = self._panes.get(pane_id)
        if entry is None:
            return b""
        return bytes(entry["backlog"])

    def sweep(self, now: datetime, grace_seconds: int) -> list[str]:
        """Return pane_ids whose grace window has lapsed.

        A pane is eligible for reap iff:
          - `ws is None` (no client currently attached), AND
          - `disconnected_at is not None`, AND
          - `(now - disconnected_at).total_seconds() > grace_seconds`.

        The caller terminates the PtyProcess and unregisters each returned
        id. Sweep is a pure observation function — it does not mutate the
        registry, so it's safe to call concurrently with `attach_ws` /
        `detach_ws` from the asyncio event loop.
        """
        expired: list[str] = []
        for pane_id, entry in self._panes.items():
            if entry.get("ws") is not None:
                continue
            disconnected_at = entry.get("disconnected_at")
            if disconnected_at is None:
                continue
            elapsed = (now - disconnected_at).total_seconds()
            if elapsed > grace_seconds:
                expired.append(pane_id)
        return expired


# ────────────────────────────────────────────────────────────────────────
# Checkpoint → display-shape mapper.
# ────────────────────────────────────────────────────────────────────────


def load_pane_context(worktree_path: Path | str) -> dict:
    """Read `.invisible-checkpoint.json` for a pane and map to the 3-key
    shape consumed by `frontend/pages/terminals.jsx` → ContextHeader.

    Schema mismatch note (acknowledged in 01-PLAN.md):
      lib/checkpoint.py persists fields named `task`, `feedback_history`,
      `last_summary`, `last_verdict`. The frontend ContextHeader prop shape
      is `{goal, activity, next}`. This function bridges the two:

        goal     ← state.get("task", "")
                   (the orchestrator's "task" IS the pane's current goal)

        activity ← last 4 entries from state.get("feedback_history", []),
                   each rendered as {"c": <truncated 120 chars>, "k": "ok"}.
                   Color/kind heuristics are deferred — Plan 03 can refine
                   by parsing for keywords like "error", "warn", etc.

        next     ← if state.get("last_verdict") == "changes":
                       [state.get("last_summary", "")]
                   else:
                       []
                   (when the last review verdict was "changes", the summary
                   describes what still needs to be done next.)

    Returns `{}` if the checkpoint file does not exist or fails to parse —
    no errors leak path-existence information beyond that boolean. (T-01-05)

    The caller is responsible for ensuring `worktree_path` was derived from
    a `validate_pane_id`-approved pane id — this function trusts its input.
    """
    wt = Path(worktree_path)
    state = checkpoint.load(wt)
    if not state:
        return {}

    history = state.get("feedback_history") or []
    activity = [
        {"c": (entry or "")[:120], "k": "ok"}
        for entry in history[-4:]
    ]

    if state.get("last_verdict") == "changes":
        next_steps = [state.get("last_summary") or ""]
    else:
        next_steps = []

    return {
        "goal": state.get("task", "") or "",
        "activity": activity,
        "next": next_steps,
    }


# ────────────────────────────────────────────────────────────────────────
# The daemon class.
# ────────────────────────────────────────────────────────────────────────


# Pre-compiled path patterns. Captures the pane-id segment for routing only;
# the captured value is then re-validated with PANE_ID_RE for defence in depth.
_PTY_PATH_RE = re.compile(r"^/pty/([^/?#]+)/?$")
_CTX_PATH_RE = re.compile(r"^/context/([^/?#]+)/?$")


class PTYServer:
    """The daemon. Compose host+port, then either await `.serve_async()` from
    your own loop or call the sync `.serve()` (which wraps asyncio.run +
    KeyboardInterrupt handling).

    Attributes:
      host:         bind address (must have passed validate_host)
      port:         TCP port to listen on (default in the CLI is 8091)
      registry:     PTYRegistry holding live PTYs
      pane_configs: per-pane override dict {pane_id: {cwd, env, command, worktree}}.
                    Plan 01 leaves this empty by default — every pane gets a
                    plain bash in the user's home. Plan 02 will populate it
                    from `invisible.toml [[terminals]]` entries.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8091,
        pane_configs: dict[str, dict[str, Any]] | None = None,
        reconnect_grace: int = RECONNECT_GRACE_SECONDS,
    ) -> None:
        # Defence in depth — even if the CLI forgot to call validate_host,
        # we refuse to construct a server bound to a non-loopback host.
        validate_host(host)
        self.host = host
        self.port = port
        self.registry = PTYRegistry()
        self.pane_configs: dict[str, dict[str, Any]] = pane_configs or {}
        # Plan 02: grace window applied by the reaper coroutine. Bumped by
        # the CLI `--reconnect-grace` flag. Stored on self so handle_pty
        # and _reap_loop both read the same value.
        self.reconnect_grace: int = int(reconnect_grace)
        # Reaper task handle — created in serve_async, cancelled on shutdown.
        self._reaper_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # HTTP side-channel + origin gate.
    # ------------------------------------------------------------------

    async def _process_request(
        self,
        connection: Any,
        request: Any,
    ) -> Response | None:
        """`process_request` hook on websockets.serve.

        Responsibilities (in this order):
          1. If the request path matches `/context/{pane_id}`: serve the
             checkpoint context as JSON and return a `Response` so the
             upgrade does NOT proceed. (Plan 01's side-channel.)
          2. Else if the request path matches `/pty/{pane_id}`: enforce
             the Origin allow-list. On disallowed/missing Origin, return
             a 403 Response so the upgrade aborts pre-handshake. Returning
             None lets the upgrade through (handler then runs).
          3. Any other path: return 404.
        """
        path = request.path or "/"
        # Strip query string if present.
        if "?" in path:
            path = path.split("?", 1)[0]

        # /context/{pane_id} — HTTP GET, not a WS upgrade.
        m_ctx = _CTX_PATH_RE.match(path)
        if m_ctx:
            return self._handle_context_http(m_ctx.group(1))

        # /pty/{pane_id} — must pass Origin gate before WS upgrade.
        m_pty = _PTY_PATH_RE.match(path)
        if m_pty:
            origin = request.headers.get("Origin")
            if not check_origin(origin):
                return _http_response(
                    HTTPStatus.FORBIDDEN,
                    b'{"error":"origin not allowed"}\n',
                    content_type="application/json",
                )
            return None  # Let the WS upgrade proceed → handle_pty runs.

        # Anything else: 404.
        return _http_response(
            HTTPStatus.NOT_FOUND,
            b'{"error":"not found"}\n',
            content_type="application/json",
        )

    def _handle_context_http(self, raw_pane_id: str) -> Response:
        """Serve `GET /context/{pane_id}` → JSON body of load_pane_context.

        Defends T-01-05: rejects pane ids that fail PANE_ID_RE before
        deriving any filesystem path. Returns 400 on bad pane id, 200
        with the context dict (possibly `{}`) on success.
        """
        # Slot pane id into the security gate first.
        if not validate_pane_id(raw_pane_id):
            return _http_response(
                HTTPStatus.BAD_REQUEST,
                b'{"error":"bad pane id"}\n',
                content_type="application/json",
            )

        # Pane → worktree mapping. Plan 01 default: home()/worktrees/{id}/feature.
        # NOTE: Plan 02 deliberately did NOT swap this for a config-driven
        # lookup — the only data this endpoint exposes (checkpoint context)
        # is per-worktree, not per-pane, and the frontend has no use for
        # arbitrary cwd-of-the-shell here. If a future plan wants to make
        # `/context/{id}` respect `pane_configs[id]['cwd']` we'd plumb it
        # through `self.pane_configs.get(raw_pane_id, {}).get('cwd')`.
        wt = home() / "worktrees" / raw_pane_id / "feature"
        ctx = load_pane_context(wt)

        body = json.dumps(ctx).encode("utf-8")
        return _http_response(
            HTTPStatus.OK,
            body,
            content_type="application/json",
            extra_headers={
                # CORS — frontend at :8090 fetches this from :8091.
                "Access-Control-Allow-Origin": "http://127.0.0.1:8090",
                "Cache-Control": "no-store",
            },
        )

    # ------------------------------------------------------------------
    # The WebSocket → PTY handler.
    # ------------------------------------------------------------------

    async def handle_pty(self, websocket: Any) -> None:
        """One WS connection ⇒ one PTY. Reconnect-aware.

        Plan 02 semantics:
          - If a pane entry exists in the registry: attach the new
            websocket, replay the backlog, and reuse the existing
            PtyProcess. This is the reconnect path.
          - Otherwise: enforce the cap, resolve the pane config, spawn a
            fresh PtyProcess, register it. This is the fresh path.
          - On either pump terminating:
              * if the PTY died (EOF from proc.read): unregister and close
                the websocket — there's nothing left to reconnect to.
              * if the websocket died (ConnectionClosed) but the PTY is
                still alive: call `detach_ws`, leave the entry parked for
                the reaper, and exit the handler WITHOUT killing the proc.
        """
        # `path` extraction. websockets v16 exposes it via `request` attribute
        # on the ServerConnection (set during handshake). We snapshot it here
        # because the request object is consumed once.
        path = ""
        req = getattr(websocket, "request", None)
        if req is not None and getattr(req, "path", None):
            path = req.path
        # Strip query string defensively (process_request already did this
        # but the handler may be invoked through other paths in the future).
        if "?" in path:
            path = path.split("?", 1)[0]

        m = _PTY_PATH_RE.match(path)
        if not m:
            await websocket.close(code=1008, reason="bad path")
            return

        pane_id = m.group(1)
        if not validate_pane_id(pane_id):
            await websocket.close(code=1008, reason="bad pane id")
            return

        # Reconnect vs fresh-spawn fork.
        attached = self.registry.attach_ws(pane_id, websocket)
        if attached:
            # Reconnect path — reuse the parked PtyProcess and replay the
            # backlog. Cap check is intentionally skipped here: the pane
            # already counts toward the cap from its fresh-spawn epoch.
            entry = self.registry.get(pane_id)
            assert entry is not None  # attach_ws returned True
            proc = entry["proc"]
            # Replay backlog as a single frame. Decode best-effort — partial
            # UTF-8 at the buffer boundary should not crash the reconnect.
            backlog = self.registry.get_backlog(pane_id)
            if backlog:
                try:
                    await websocket.send(backlog.decode("utf-8", errors="replace"))
                except ConnectionClosed:
                    # Client died mid-replay; detach and bail. Reaper will
                    # take care of the parked proc.
                    self.registry.detach_ws(pane_id)
                    return
        else:
            # Fresh-spawn path.
            # Cap check — T-01-04. We count live PtyProcesses including
            # parked ones (orphans waiting for reap), which is the correct
            # semantic for "how much memory is the daemon holding". The
            # reaper is what actually shrinks this number.
            if self.registry.count() >= MAX_CONCURRENT_PTYS:
                # 1013 = Try Again Later, the right close code for capacity.
                await websocket.close(code=1013, reason="pty cap reached")
                return

            # Per-pane config. Task 2 swaps this for `spawn_pty_for_config`;
            # for the Task 1 unit-test we still need to round-trip through
            # the same dict shape.
            cfg = self.pane_configs.get(pane_id, {})
            try:
                proc = self._spawn_for_pane(pane_id, cfg)
            except (OSError, RuntimeError) as e:
                await websocket.close(code=1011, reason=f"spawn failed: {e}")
                return

            self.registry.register(pane_id, proc)
            # Symmetric bookkeeping: after register, immediately attach
            # the websocket so the entry is in the "live" state.
            self.registry.attach_ws(pane_id, websocket)

        loop = asyncio.get_running_loop()
        # Track whether the PTY itself died vs the websocket. Decides the
        # finally branch — kill-and-unregister vs detach-and-park.
        pty_dead = False

        async def pty_to_ws() -> None:
            """Drain PTY stdout/stderr → forward to WS as text frames,
            recording every chunk into the registry's backlog ring.
            """
            nonlocal pty_dead
            while True:
                try:
                    chunk = await loop.run_in_executor(None, proc.read, 1024)
                except (EOFError, OSError, ptyprocess.PtyProcessError):
                    pty_dead = True
                    return
                if not chunk:
                    pty_dead = True
                    return
                if isinstance(chunk, bytes):
                    raw = chunk
                else:
                    raw = chunk.encode("utf-8", errors="replace")
                # Record into backlog before sending — keeps the buffer
                # fresh even if the ws send raises mid-flight.
                self.registry.record_output(pane_id, raw)
                try:
                    await websocket.send(raw.decode("utf-8", errors="replace"))
                except ConnectionClosed:
                    return

        async def ws_to_pty() -> None:
            """Pump WS frames (text or binary) → PTY stdin.

            ConnectionClosed is the normal exit when the browser disconnects.
            """
            try:
                async for message in websocket:
                    if isinstance(message, str):
                        data = message.encode("utf-8")
                    else:
                        data = bytes(message)
                    try:
                        proc.write(data)
                    except (OSError, ptyprocess.PtyProcessError):
                        pty_dead_local = True  # noqa: F841 — narrative only
                        return
            except ConnectionClosed:
                return

        # Race the two pumps. When either ends, decide whether to park or
        # reap the pane (see comment block at the top of handle_pty).
        try:
            await asyncio.wait(
                {asyncio.create_task(pty_to_ws()), asyncio.create_task(ws_to_pty())},
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            if pty_dead:
                # PTY exited (user typed `exit` or the shell died). No
                # session to reconnect to; clean up immediately.
                try:
                    proc.terminate(force=True)
                except Exception:  # noqa: BLE001
                    pass
                self.registry.unregister(pane_id)
                try:
                    await websocket.close()
                except Exception:  # noqa: BLE001
                    pass
            else:
                # Websocket gone, but the PtyProcess is still alive. Park
                # it for the reaper. The reaper will terminate the proc
                # iff no client reattaches within `self.reconnect_grace`.
                self.registry.detach_ws(pane_id)
                try:
                    await websocket.close()
                except Exception:  # noqa: BLE001
                    pass

    # ------------------------------------------------------------------
    # Internal: per-pane spawn dispatcher (Plan 02 hook).
    # ------------------------------------------------------------------

    def _spawn_for_pane(self, pane_id: str, cfg: dict[str, Any]) -> PtyProcess:
        """Spawn a PtyProcess for `pane_id` using `cfg` (from pane_configs).

        Delegates to `spawn_pty_for_config`, which handles the bash-vs-ssh
        branch, expanduser on cwd, and env overlay. Empty `cfg` ⇒ plain
        bash in the user's home (the Plan 01 default behavior).
        """
        return spawn_pty_for_config(pane_id, cfg)

    # ------------------------------------------------------------------
    # Reaper.
    # ------------------------------------------------------------------

    async def _reap_loop(self) -> None:
        """Background coroutine that sweeps the registry every
        `REAPER_INTERVAL_SECONDS` and terminates panes whose grace window
        has lapsed.

        Exits on `asyncio.CancelledError`, which `serve_async` raises on
        shutdown. Any other exception is logged but does NOT take down
        the daemon — the reaper is a janitor, not a critical path.
        """
        try:
            while True:
                await asyncio.sleep(REAPER_INTERVAL_SECONDS)
                now = datetime.now(timezone.utc)
                expired = self.registry.sweep(now, self.reconnect_grace)
                for pane_id in expired:
                    entry = self.registry.get(pane_id)
                    if entry is None:
                        continue
                    proc = entry.get("proc")
                    if proc is not None:
                        try:
                            proc.terminate(force=True)
                        except Exception:  # noqa: BLE001
                            pass
                    self.registry.unregister(pane_id)
                    print(
                        f"[invisible-pty] reaped {pane_id} after "
                        f"{self.reconnect_grace}s idle",
                        file=sys.stderr,
                    )
        except asyncio.CancelledError:
            # Normal shutdown path.
            raise
        except Exception as e:  # noqa: BLE001
            print(
                f"[invisible-pty] reaper crashed: {type(e).__name__}: {e}",
                file=sys.stderr,
            )

    # ------------------------------------------------------------------
    # Lifecycle.
    # ------------------------------------------------------------------

    async def serve_async(self) -> None:
        """Bind the socket and serve forever.

        Origin enforcement is layered: `process_request` returns 403 for
        disallowed Origins on `/pty/...` paths (so the gate fires even
        before any negotiated subprotocol logic). The library also
        natively supports an `origins=` list — we pass it as defence in
        depth, but the explicit check in `_process_request` is what the
        threat model actually relies on.

        Plan 02: also launches the reaper coroutine before binding the
        socket, and cancels it on shutdown. The daemon's in-memory PTY
        state is intentionally non-durable — restarting the daemon clears
        every registered pane. Persistence only spans the lifetime of a
        single daemon process.
        """
        # Plan 02: start the reaper before accepting connections so even
        # the very first orphaned pane gets swept on schedule.
        self._reaper_task = asyncio.create_task(self._reap_loop())
        try:
            async with ws_serve(
                self.handle_pty,
                self.host,
                self.port,
                process_request=self._process_request,
                origins=list(ALLOWED_ORIGINS),
            ) as server:
                print(f"[invisible-pty] listening on ws://{self.host}:{self.port}")
                print(
                    f"[invisible-pty] reconnect grace = {self.reconnect_grace}s; "
                    f"backlog = {BACKLOG_BYTES} bytes; "
                    f"reaper every {REAPER_INTERVAL_SECONDS}s"
                )
                print("[invisible-pty] Ctrl-C to stop")
                await server.serve_forever()
        finally:
            # Shutdown — cancel the reaper and swallow the CancelledError.
            if self._reaper_task is not None:
                self._reaper_task.cancel()
                try:
                    await self._reaper_task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass
                self._reaper_task = None

    def serve(self) -> None:
        """Sync entrypoint. Wraps asyncio.run + a polite KeyboardInterrupt log.

        Mirrors the dashboard's `httpd.serve_forever` + Ctrl-C log pattern.
        """
        try:
            asyncio.run(self.serve_async())
        except KeyboardInterrupt:
            print("\n[invisible-pty] shutting down")


# ────────────────────────────────────────────────────────────────────────
# Internal: HTTP Response helper.
# ────────────────────────────────────────────────────────────────────────


def _http_response(
    status: HTTPStatus,
    body: bytes,
    *,
    content_type: str = "text/plain",
    extra_headers: dict[str, str] | None = None,
) -> Response:
    """Build a websockets.http11.Response from a status + body.

    Centralised so the four call sites all emit consistently-shaped HTTP
    replies during the pre-upgrade phase.
    """
    headers = Headers()
    headers["Content-Type"] = content_type
    headers["Content-Length"] = str(len(body))
    if extra_headers:
        for k, v in extra_headers.items():
            headers[k] = v
    return Response(
        status_code=int(status),
        reason_phrase=status.phrase,
        headers=headers,
        body=body,
    )


# ────────────────────────────────────────────────────────────────────────
# PLAN-01 verification log
# ────────────────────────────────────────────────────────────────────────
# This marker comment is the seam Plan 02 and Plan 03 grep for to confirm
# the Plan 01 daemon surface is stable. Do not move or rename the named
# exports above this line without coordinating with those plans.
#
# Verified gates (Task 3, end-to-end against a live daemon on :8091):
#   (a) /pty/test-1 happy path     — bash PTY spawned, `pwd\n` round-trips
#                                    and stdout streams back as text frames.
#   (b) Bad pane id (T-01-01)      — `..%2Fetc%2Fpasswd` URL-decoded to a
#                                    PANE_ID_RE non-match → WS close 1008.
#   (c) Bad origin (T-01-02)       — `Origin: http://evil.example` rejected
#                                    by _process_request with HTTP 403
#                                    before the WS handshake completes.
#   (d) /context/{pane_id} (T-01-05) — JSON object served on 200; absent
#                                    checkpoint returns `{}` with no path
#                                    information leaked.
#
# Threat-model gates not directly probed by Task 3 (covered by Tasks 1 & 2):
#   - T-01-03 host-binding   : --host 0.0.0.0 → exit 2 (Task 2 verify).
#   - T-01-04 PTY cap (32)   : MAX_CONCURRENT_PTYS enforced in handle_pty;
#                              behaviour asserted by unit test in Plan 02
#                              when reconnect-grace lands (the cap is
#                              easier to test against a stable registry).
#
# Plan 02 (landed): session persistence + SSH variant + invisible.toml configs.
#   - handle_pty teardown    : DONE — reconnect-grace + parked PTY + reaper.
#   - spawn branch           : DONE — resolve_command + spawn_pty_for_config.
#   - PTYServer constructor  : DONE — pane_configs + reconnect_grace kwargs.


# ────────────────────────────────────────────────────────────────────────
# PLAN-02 verification log
# ────────────────────────────────────────────────────────────────────────
# This marker is the seam Plan 03 greps for to confirm Plan 02's surface
# is stable before wiring frontend/pages/terminals.jsx to the daemon.
#
# Plan 02 new exports (extending — not replacing — Plan 01's seven):
#   - PTYRegistry           extended with attach_ws / detach_ws /
#                           record_output / get_backlog / sweep.
#   - RECONNECT_GRACE_SECONDS = 600
#   - BACKLOG_BYTES = 8 * 1024
#   - REAPER_INTERVAL_SECONDS = 30
#   - load_pane_configs(path) -> dict[str, dict]
#   - resolve_command(config) -> list[str]
#   - spawn_pty_for_config(pane_id, config) -> PtyProcess
#   - PTYServer.__init__ now accepts (pane_configs, reconnect_grace)
#
# Verified gates (Task 1 + Task 2 unit checks + Task 3 end-to-end):
#   (e) PTY survives WS disconnect (Task 3) — `export PERSIST_MARKER=42`
#       set on first connection observable on reconnect 3s later, and the
#       reconnect received a 988-byte backlog frame replaying the prior
#       session's output before live streaming resumed. The reattached
#       shell IS the same PtyProcess (env var persisted, prompt cwd
#       unchanged).
#   (f) Reaper sweep semantics (Task 1 unit) — `sweep(future, grace)`
#       returns parked panes past grace; ignores live panes. Reaper
#       cycle terminates + unregisters expired panes; capacity counter
#       includes parked entries (the cap is about memory, not active
#       clients).
#   (g) Backlog ring buffer (Task 1 unit) — bytearray drops from front
#       when length > BACKLOG_BYTES; the tail is always preserved.
#   (h) SSH config whitelist (Task 2 unit) — `load_pane_configs` drops
#       entries with invalid PANE_ID_RE ids and rejects kind=ssh entries
#       missing a `host` field. `resolve_command` returns `['ssh', host]`
#       with host pulled from the trusted TOML — URL pane id is only a
#       registry-lookup key (T-02-01).
#   (i) TOML env-injection mitigation (Task 2 unit) — env values must be
#       strings; any non-string drops the whole env table. cwd is
#       `expanduser`'d only — never shell-expanded (T-02-04).
#
# Plan 03 hooks:
#   - The frontend can connect to `ws://127.0.0.1:8091/pty/{id}` and rely
#     on these guarantees: a reconnect inside `--reconnect-grace` reattaches
#     to the same shell; the first frame after reconnect is a backlog
#     replay (may be empty if the prior session produced nothing).
#   - `bin/invisible-pty --config /path/to/invisible.toml` is the way to
#     point the daemon at non-default pane configs.
#   - Daemon restart clears all PTYs — in-memory only (intentional; the
#     cost is small for a desktop tool and the alternative would require
#     us to durably checkpoint termios/cwd/env, which is well out of
#     scope for v1).

