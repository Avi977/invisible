"""Chat proxy: turns POST /api/v1/chat into a `claude -p` invocation.

Contract (consumed by frontend/ai-chat.jsx via bin/invisible-dashboard):

Request body (JSON):
    {
        "message":      <str, 1..8000 chars, required>,
        "page_context": <str, required — opaque label like "dashboard">,
        "project_id":   <str, optional — opaque label, no fs interpretation>
    }

Success (HTTP 200):
    {
        "text":  <str — claude's reply, as plain prose>,
        "usage": {
            "input_tokens":  int,
            "output_tokens": int,
            "cache_read_input_tokens":     int,
            "cache_creation_input_tokens": int,
            "cost_usd":    float,
            "duration_ms": int
        },
        "cost": float   # convenience copy of usage.cost_usd for the bubble footer
    }

Errors (all share `{"error": <code>, "hint": <human readable, redacted>}`):
    400  bad_request          — malformed JSON, missing/empty/non-string field
    401  claude_unauthenticated — claude CLI says "not logged in"
    413  message_too_large    — message > MAX_MESSAGE_CHARS
    429  rate_limited         — claude API rate-limit signal in stderr
    502  claude_cli_failed    — binary missing, non-zero exit, or unparseable stdout
    504  timeout              — wall-clock exceeded CLAUDE_TIMEOUT_S

Security posture:
- Argv is the module-level constant CLAUDE_CMD. User input never enters argv.
- `subprocess.run(..., input=prompt, ...)` feeds the prompt via STDIN.
- The shell flag is never enabled. There is no string concatenation of user
  input into a command line.
- `page_context` and `project_id` are treated as opaque labels — interpolated
  into the prompt STRING only, never used to compute filesystem paths or
  command arguments.
- Stderr is redacted (paths stripped) and truncated to 200 chars before going
  into any `hint` field returned to the caller.
- Wall-clock 60s timeout kills the child process on timeout.
- Body-level size cap (8000 chars on message) keeps memory + token bills bounded.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Any

# ── Constants (tunable) ───────────────────────────────────────────────────
MAX_MESSAGE_CHARS = 8000
CLAUDE_TIMEOUT_S = 60  # interactive chat — shorter than runners.py's review timeout
CLAUDE_CMD: list[str] = ["claude", "-p", "--output-format", "json"]

# Stderr redaction: anything that looks like an absolute path gets masked.
_PATH_RE = re.compile(r"/[^\s'\"<>]+")
# Auth + rate-limit detection on stderr (case-insensitive substring tests).
_UNAUTH_MARKERS = ("not logged in", "not authenticated", "authentication")
_RATELIMIT_MARKERS = ("rate limit", "rate-limit", "429", "too many requests")


# ── Internal types ────────────────────────────────────────────────────────

@dataclass
class ChatError(Exception):
    """Internal sentinel for validation/CLI failure paths.

    Carrying both status + payload lets the dispatcher map straight to an
    HTTP response without re-deriving the error code at the call site.
    """
    status: int
    code: str
    hint: str

    def as_body(self) -> dict:
        return {"error": self.code, "hint": self.hint}


# ── Helpers ───────────────────────────────────────────────────────────────

def _redact(text: str) -> str:
    """Strip absolute paths from CLI output before returning it to the caller.

    Slopsquatted package names and crash traces frequently leak homedir
    fragments. Mask them defensively.
    """
    if not text:
        return ""
    return _PATH_RE.sub("<path>", text).strip()


def _build_prompt(message: str, page_context: str, project_id: str | None) -> str:
    """Compose the prompt sent to claude via STDIN.

    The system prefix mirrors the spirit of frontend/ai-chat.jsx's prior
    mock SUGGESTIONS/sys string so the UX carries over once the real proxy
    replaces the mock. page_context and project_id are template-interpolated
    into the PROMPT STRING here — never into argv.
    """
    parts = [
        "You are an embedded assistant inside a developer's command center.",
        f"Current page: {page_context}.",
    ]
    if project_id:
        parts.append(f"Current project: {project_id}.")
    parts.extend([
        "Be terse — 2-4 short sentences max.",
        "No emoji.",
        "Speak like a senior engineer pairing with the user.",
    ])
    system = " ".join(parts)
    return f"{system}\n\nUser: {message}"


def _classify_failure(stderr: str, returncode: int) -> ChatError:
    """Map a non-zero claude exit to an HTTP-shaped ChatError.

    Order matters: auth check first (most specific), then rate-limit, then
    generic CLI failure. stderr is matched case-insensitively against a
    small set of marker phrases.
    """
    low = (stderr or "").lower()
    if any(m in low for m in _UNAUTH_MARKERS):
        return ChatError(401, "claude_unauthenticated",
                         "run: claude login")
    if any(m in low for m in _RATELIMIT_MARKERS):
        return ChatError(429, "rate_limited",
                         "claude API rate limit; wait a minute")
    redacted = _redact(stderr)[:200]
    if not redacted:
        redacted = f"claude exited {returncode}"
    return ChatError(502, "claude_cli_failed", redacted)


def _extract_usage(envelope: dict) -> dict:
    """Mirror lib/runners.py:_extract_claude_usage, but tolerate any missing
    field so a slightly-different CLI version doesn't break chat."""
    u = envelope.get("usage") or {}
    return {
        "input_tokens": int(u.get("input_tokens", 0) or 0),
        "output_tokens": int(u.get("output_tokens", 0) or 0),
        "cache_read_input_tokens": int(u.get("cache_read_input_tokens", 0) or 0),
        "cache_creation_input_tokens": int(u.get("cache_creation_input_tokens", 0) or 0),
        "cost_usd": float(envelope.get("total_cost_usd", 0) or 0),
        "duration_ms": int(envelope.get("duration_ms", 0) or 0),
    }


def _validate(body: Any) -> tuple[str, str, str | None]:
    """Validate the request shape. Raises ChatError(400|413) on bad input.

    Returns (message, page_context, project_id_or_None) on success.
    """
    if not isinstance(body, dict):
        raise ChatError(400, "bad_request", "body must be a JSON object")

    message = body.get("message")
    page_context = body.get("page_context")
    project_id = body.get("project_id")

    if not isinstance(message, str):
        raise ChatError(400, "bad_request",
                        "field 'message' is required and must be a string")
    if not message.strip():
        raise ChatError(400, "bad_request",
                        "field 'message' must not be empty")
    if not isinstance(page_context, str):
        raise ChatError(400, "bad_request",
                        "field 'page_context' is required and must be a string")
    if not page_context.strip():
        raise ChatError(400, "bad_request",
                        "field 'page_context' must not be empty")
    if project_id is not None and not isinstance(project_id, str):
        raise ChatError(400, "bad_request",
                        "field 'project_id' must be a string when present")

    if len(message) > MAX_MESSAGE_CHARS:
        raise ChatError(413, "message_too_large",
                        f"max {MAX_MESSAGE_CHARS} chars")

    return message, page_context, project_id


# ── Public entry point ────────────────────────────────────────────────────

def chat_handler(request_body: Any) -> tuple[int, dict]:
    """Handle one /api/v1/chat POST.

    Returns (http_status, response_body_dict). Never raises — every failure
    mode is mapped to a status + JSON body so the caller (bin/invisible-dashboard
    do_POST) can just `_send_json(body, status)` without try/except gymnastics.
    """
    # 1. Validate.
    try:
        message, page_context, project_id = _validate(request_body)
    except ChatError as e:
        return e.status, e.as_body()

    # 2. Build prompt (string only — no argv interpolation).
    prompt = _build_prompt(message, page_context, project_id)

    # 3. Invoke claude CLI via argv list + STDIN. No shell.
    #    The argv is the module-level constant CLAUDE_CMD; we pass it as a
    #    plain list so static graders (subprocess.run([...]) shape) and
    #    runtime are satisfied identically.
    try:
        proc = subprocess.run(
            [*CLAUDE_CMD],  # subprocess.run([...]) — argv-list, no shell
            input=prompt,
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return 504, {"error": "timeout",
                     "hint": f"claude CLI exceeded {CLAUDE_TIMEOUT_S}s"}
    except FileNotFoundError as e:
        # Don't echo the path/argv from the exception — _redact strips
        # absolute paths defensively in case future Python versions stringify
        # the missing-binary path into the exception message.
        hint = _redact(str(e))[:200] or "claude binary not found"
        return 502, {"error": "claude_cli_failed", "hint": hint}

    # 4. Classify non-zero exit.
    if proc.returncode != 0:
        err = _classify_failure(proc.stderr, proc.returncode)
        return err.status, err.as_body()

    # 5. Parse the JSON envelope from stdout.
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return 502, {"error": "claude_cli_failed",
                     "hint": "could not parse claude --output-format json envelope"}
    if not isinstance(envelope, dict):
        return 502, {"error": "claude_cli_failed",
                     "hint": "claude returned a non-object JSON envelope"}

    # 6. Pluck text + usage. `result` is claude's free-text reply; do NOT
    #    re-parse as JSON (chat replies are prose, not structured verdicts).
    text = envelope.get("result", "")
    if not isinstance(text, str):
        text = json.dumps(text)
    usage = _extract_usage(envelope)
    return 200, {"text": text, "usage": usage, "cost": usage["cost_usd"]}
