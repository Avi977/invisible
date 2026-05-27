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

Plan 02 hooks left explicit in the code as `# TODO(plan-02): …` markers.
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


class PTYRegistry:
    """In-memory pane-id ⇒ live PTY bookkeeping.

    Plan 01 scope: register / get / count / unregister. Plan 02 will extend
    this with a reconnect-grace timer + reap loop (see `# TODO(plan-02)`
    markers in handle_pty).
    """

    def __init__(self) -> None:
        self._panes: dict[str, dict[str, Any]] = {}

    def register(self, pane_id: str, proc: PtyProcess) -> None:
        """Add (or replace) a pane.

        Plan 01 behavior: re-registering an existing pane silently replaces
        the old entry — the caller (handle_pty) is responsible for
        terminating the old PtyProcess first. Plan 02 changes this to
        "reattach to existing pane".
        """
        self._panes[pane_id] = {
            "proc": proc,
            "created_at": datetime.now(timezone.utc),
            "ws": None,  # Plan 02 will populate this for reconnect routing.
        }

    def get(self, pane_id: str) -> dict[str, Any] | None:
        return self._panes.get(pane_id)

    def count(self) -> int:
        return len(self._panes)

    def unregister(self, pane_id: str) -> None:
        self._panes.pop(pane_id, None)


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
    ) -> None:
        # Defence in depth — even if the CLI forgot to call validate_host,
        # we refuse to construct a server bound to a non-loopback host.
        validate_host(host)
        self.host = host
        self.port = port
        self.registry = PTYRegistry()
        self.pane_configs: dict[str, dict[str, Any]] = pane_configs or {}

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
        # Plan 02 will swap this for a config-driven lookup.
        # TODO(plan-02): replace with self.pane_configs[pane_id]["worktree"] fallback.
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
        """One WS connection ⇒ one PTY. Spawns the shell, pumps bytes in
        both directions, terminates the shell on disconnect.

        Plan 01 semantics: every disconnect kills the PTY. Plan 02 replaces
        this with a reconnect-grace timer + reattach.
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

        # Cap check — T-01-04.
        if self.registry.count() >= MAX_CONCURRENT_PTYS:
            # 1013 = Try Again Later, the right close code for capacity.
            await websocket.close(code=1013, reason="pty cap reached")
            return

        # If a pane with this id already exists, kill it first (Plan 01:
        # last-writer-wins). Plan 02 changes this to "reattach to existing".
        # TODO(plan-02): replace this teardown with reattach-and-resume.
        existing = self.registry.get(pane_id)
        if existing is not None:
            try:
                existing["proc"].terminate(force=True)
            except Exception:  # noqa: BLE001 — best-effort cleanup
                pass
            self.registry.unregister(pane_id)

        # Per-pane config (Plan 01 default: empty ⇒ plain bash in home dir).
        cfg = self.pane_configs.get(pane_id, {})
        # TODO(plan-02): SSH-variant — when cfg["ssh"] is set, spawn `ssh host`
        # instead of a local bash. Plan 02 owns this branch.
        try:
            proc = spawn_pty(
                pane_id,
                cwd=cfg.get("cwd"),
                env=cfg.get("env"),
                command=cfg.get("command"),
            )
        except (OSError, RuntimeError) as e:
            await websocket.close(code=1011, reason=f"spawn failed: {e}")
            return

        self.registry.register(pane_id, proc)

        loop = asyncio.get_running_loop()

        async def pty_to_ws() -> None:
            """Drain PTY stdout/stderr → forward to WS as text frames.

            `proc.read` is blocking; run it in the default executor so the
            asyncio loop stays responsive. Decode with errors="replace" so
            partial-UTF8 reads don't kill the loop.
            """
            while True:
                try:
                    chunk = await loop.run_in_executor(None, proc.read, 1024)
                except (EOFError, OSError, ptyprocess.PtyProcessError):
                    return
                if not chunk:
                    return
                if isinstance(chunk, bytes):
                    text = chunk.decode("utf-8", errors="replace")
                else:
                    text = chunk
                try:
                    await websocket.send(text)
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
                        return
            except ConnectionClosed:
                return

        # Race the two pumps. When either ends, tear the whole pane down.
        try:
            await asyncio.wait(
                {asyncio.create_task(pty_to_ws()), asyncio.create_task(ws_to_pty())},
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            # Plan 01 teardown: kill PTY, unregister, close WS.
            # TODO(plan-02): swap this for "schedule reap after grace period".
            try:
                proc.terminate(force=True)
            except Exception:  # noqa: BLE001
                pass
            self.registry.unregister(pane_id)
            try:
                await websocket.close()
            except Exception:  # noqa: BLE001
                pass

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
        """
        async with ws_serve(
            self.handle_pty,
            self.host,
            self.port,
            process_request=self._process_request,
            origins=list(ALLOWED_ORIGINS),
        ) as server:
            print(f"[invisible-pty] listening on ws://{self.host}:{self.port}")
            print("[invisible-pty] Ctrl-C to stop")
            await server.serve_forever()

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
# Plan 02 will extend, NOT replace:
#   - handle_pty teardown    : last `# TODO(plan-02)` marker — swap kill-on-
#                              disconnect for reconnect-grace + reap.
#   - spawn branch           : add SSH variant when cfg["ssh"] is set.
#   - PTYServer constructor  : populate pane_configs from invisible.toml.

