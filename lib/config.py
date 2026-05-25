"""Load invisible.toml + .env from $INVISIBLE_HOME (defaults to ~/.invisible)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import tomllib  # py3.11+
except ImportError:
    import tomli as tomllib  # type: ignore


def home() -> Path:
    # expanduser() handles both the env-var case (where a user puts "~/.invisible"
    # in .env and ~ doesn't get expanded by the shell) and the default case.
    return Path(os.path.expanduser(os.environ.get("INVISIBLE_HOME", "~/.invisible")))


def load_env() -> None:
    """Source secrets in two passes:

    1. Tiny .env loader (stdlib, no python-dotenv). `setdefault` semantics
       so anything already set in the shell wins. This is where you put
       *bootstrap* creds: INFISICAL_CLIENT_ID/SECRET/PROJECT_ID, plus
       non-secret config like INVISIBLE_CONTEXT_BUDGET.

    2. If Infisical is configured, fetch all secrets from the vault and
       merge them in — overriding .env values for the same key. The vault
       is the source of truth; .env is just the bootstrap.
    """
    p = home() / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    # Best-effort vault load. Swallows all errors — if Infisical is down
    # we silently fall back to whatever .env supplied.
    try:
        import infisical  # local import to avoid hard dep at import time
        n = infisical.bootstrap_from_infisical()
        if n:
            import sys
            sys.stderr.write(f"[invisible] loaded {n} secrets from Infisical\n")
    except Exception:  # noqa: BLE001 — never let secrets layer crash startup
        pass


def load_toml() -> dict:
    p = home() / "invisible.toml"
    if not p.exists():
        print(f"[config] {p} missing — copy invisible.toml.example", file=sys.stderr)
        return {}
    with open(p, "rb") as f:
        return tomllib.load(f)


def project_meta(project_name: str) -> dict:
    cfg = load_toml()
    for proj in cfg.get("projects", []):
        if proj.get("name") == project_name:
            return proj
    return {}
