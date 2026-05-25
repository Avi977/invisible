"""Infisical REST client — stdlib only.

Invisible uses Infisical (running at vault.theprofitplatform.com.au by default)
as the source of truth for runtime secrets. The on-disk `.env` shrinks to
*just* the bootstrap creds:

    INFISICAL_CLIENT_ID      = machine identity client id
    INFISICAL_CLIENT_SECRET  = machine identity client secret
    INFISICAL_PROJECT_ID     = workspace id of the "invisible" project

Optional:
    INFISICAL_HOST           = default https://vault.theprofitplatform.com.au
    INFISICAL_ENVIRONMENT    = default "dev"
    INFISICAL_SECRET_PATH    = default "/"
    INFISICAL_TIMEOUT_S      = default 8

Everything else (NOTION_TOKEN, TELEGRAM_*, INVISIBLE_SERVER_TOKEN, etc.) lives
in Infisical and is merged into `os.environ` at startup via
`bootstrap_from_infisical()`, which lib/config.py calls inside `load_env()`.

Failure semantics: every error is swallowed and logged to stderr. A network
blip should never crash an orchestrator run. If Infisical is unreachable,
whatever's already in `os.environ` (from the shell or `.env`) is what the
process sees — same behavior as before this module existed.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_HOST = "https://vault.theprofitplatform.com.au"
DEFAULT_ENV = "dev"
DEFAULT_SECRET_PATH = "/"
DEFAULT_TIMEOUT_S = 8

# Cloudflare's Browser Integrity Check rejects "Python-urllib/X" with error
# 1010 ("Access denied — browser signature"). Sending an explicit UA + an
# Accept header gets us past the lightest WAF checks. If your Cloudflare
# zone has stricter Bot Fight Mode on, you'll also need to add a WAF skip
# rule for User-Agent contains "invisible-cli" — see README "Secrets" section.
DEFAULT_HEADERS = {
    "User-Agent": "invisible-cli/1.0 (+https://github.com/anthropics/claude-code)",
    "Accept": "application/json",
}


def _log(msg: str) -> None:
    sys.stderr.write(f"[infisical] {msg}\n")


def _post_json(url: str, body: dict, headers: dict | None = None,
               timeout: float = DEFAULT_TIMEOUT_S) -> dict | None:
    req = urllib.request.Request(
        url, method="POST",
        headers={**DEFAULT_HEADERS, "Content-Type": "application/json",
                 **(headers or {})},
        data=json.dumps(body).encode(),
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        _log(f"POST {url} → HTTP {e.code}: {e.read()[:200].decode(errors='replace')}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        _log(f"POST {url} failed: {e}")
    return None


def _get_json(url: str, headers: dict | None = None,
              timeout: float = DEFAULT_TIMEOUT_S) -> dict | None:
    req = urllib.request.Request(url, headers={**DEFAULT_HEADERS, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        _log(f"GET {url} → HTTP {e.code}: {e.read()[:200].decode(errors='replace')}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        _log(f"GET {url} failed: {e}")
    return None


# ── Public surface ──────────────────────────────────────────────────────

class InfisicalClient:
    """Stateful client: holds the access token after login(). Tokens last
    ~2h by default in Infisical; we don't bother refreshing because every
    new process re-logins anyway."""

    def __init__(self, host: str, client_id: str, client_secret: str,
                 timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
        self.host = host.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout_s = timeout_s
        self.access_token: str | None = None

    def login(self) -> bool:
        r = _post_json(
            f"{self.host}/api/v1/auth/universal-auth/login",
            {"clientId": self.client_id, "clientSecret": self.client_secret},
            timeout=self.timeout_s,
        )
        if not r or not r.get("accessToken"):
            return False
        self.access_token = r["accessToken"]
        return True

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}

    def list_secrets(self, workspace_id: str, environment: str,
                     secret_path: str = "/") -> dict[str, str]:
        if not self.access_token:
            return {}
        qs = urllib.parse.urlencode({
            "workspaceId": workspace_id,
            "environment": environment,
            "secretPath": secret_path,
        })
        r = _get_json(
            f"{self.host}/api/v3/secrets/raw?{qs}",
            headers=self._auth_headers(),
            timeout=self.timeout_s,
        )
        if not r:
            return {}
        out: dict[str, str] = {}
        for s in r.get("secrets") or []:
            k = s.get("secretKey")
            v = s.get("secretValue")
            if k:
                out[k] = v or ""
        return out

    def upsert_secret(self, workspace_id: str, environment: str,
                      key: str, value: str, secret_path: str = "/") -> bool:
        """Create-or-update a single secret. Infisical's /raw API takes the
        key in the URL path. We try update first; if 404 we POST."""
        url = (f"{self.host}/api/v3/secrets/raw/{urllib.parse.quote(key, safe='')}")
        body = {
            "workspaceId": workspace_id,
            "environment": environment,
            "secretPath": secret_path,
            "secretValue": value,
        }
        # Try PATCH first
        req = urllib.request.Request(
            url, method="PATCH",
            headers={**DEFAULT_HEADERS, "Content-Type": "application/json",
                     **self._auth_headers()},
            data=json.dumps(body).encode(),
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                r.read()
                return True
        except urllib.error.HTTPError as e:
            if e.code != 404:
                _log(f"PATCH {key} → HTTP {e.code}: {e.read()[:200].decode(errors='replace')}")
                return False
            # Fall through to POST (create)
        except (urllib.error.URLError, OSError) as e:
            _log(f"PATCH {key} failed: {e}")
            return False

        body["secretKey"] = key
        req = urllib.request.Request(
            url, method="POST",
            headers={**DEFAULT_HEADERS, "Content-Type": "application/json",
                     **self._auth_headers()},
            data=json.dumps(body).encode(),
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                r.read()
                return True
        except urllib.error.HTTPError as e:
            _log(f"POST {key} → HTTP {e.code}: {e.read()[:200].decode(errors='replace')}")
        except (urllib.error.URLError, OSError) as e:
            _log(f"POST {key} failed: {e}")
        return False


def _env() -> tuple[str, str | None, str | None, str | None, str, str]:
    """Pull config from os.environ. Returns (host, client_id, client_secret,
    project_id, environment, secret_path). Any of the *_id/secret fields can
    be None — caller decides whether to proceed."""
    host = os.environ.get("INFISICAL_HOST", DEFAULT_HOST)
    cid = os.environ.get("INFISICAL_CLIENT_ID") or None
    csecret = os.environ.get("INFISICAL_CLIENT_SECRET") or None
    pid = os.environ.get("INFISICAL_PROJECT_ID") or None
    env = os.environ.get("INFISICAL_ENVIRONMENT", DEFAULT_ENV)
    path = os.environ.get("INFISICAL_SECRET_PATH", DEFAULT_SECRET_PATH)
    return host, cid, csecret, pid, env, path


def configured() -> bool:
    """Cheap predicate — true iff the 3 bootstrap creds are set."""
    _, cid, csecret, pid, _, _ = _env()
    return bool(cid and csecret and pid)


def make_client() -> InfisicalClient | None:
    """Build + login a client from env vars. Returns None on missing creds
    OR login failure. Use this from CLI tools (invisible-secrets); the
    bootstrap path uses bootstrap_from_infisical() instead."""
    host, cid, csecret, _, _, _ = _env()
    if not (cid and csecret):
        _log("INFISICAL_CLIENT_ID / INFISICAL_CLIENT_SECRET unset")
        return None
    c = InfisicalClient(host, cid, csecret)
    if not c.login():
        return None
    return c


def bootstrap_from_infisical() -> int:
    """Called by lib/config.py load_env(). If creds + project id are
    configured, fetch secrets and merge into os.environ (overriding any
    .env values). Returns count of secrets loaded; 0 means "no-op."

    NOTE: this is a hot path on every CLI startup. We swallow all errors
    and never raise."""
    host, cid, csecret, pid, env, path = _env()
    if not (cid and csecret and pid):
        return 0
    c = InfisicalClient(host, cid, csecret)
    if not c.login():
        return 0
    secrets = c.list_secrets(pid, env, path)
    if not secrets:
        return 0
    for k, v in secrets.items():
        os.environ[k] = v
    return len(secrets)
