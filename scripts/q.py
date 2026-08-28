"""Terminal entry for the local-first router. Wrapped by the `q` PowerShell function.

Usage: py -3 scripts/q.py [--force local|claude|session] [--project SLUG] words...
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))


def main() -> int:
    parser = argparse.ArgumentParser(prog="q")
    parser.add_argument("--force", choices=["local", "claude", "session"])
    parser.add_argument("--project")
    parser.add_argument("words", nargs="+")
    args = parser.parse_args()

    from api import router

    body = {"message": " ".join(args.words)}
    if args.force:
        body["force"] = args.force
    if args.project:
        body["project_id"] = args.project

    status, resp = router.ask_handler(body)
    if status != 200:
        print(f"error {status}: {resp.get('error')} — {resp.get('hint', '')}",
              file=sys.stderr)
        return 1

    route = resp.get("route", "?")
    model = resp.get("model") or resp.get("provider") or ""
    print(f"[{route}{' · ' + model if model else ''}]")
    print(resp.get("text", ""))
    if route == "session":
        print(f"\npacket: {resp.get('packet_path')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
