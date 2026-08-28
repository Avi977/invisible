"""Registered Envy tool metadata, search, approvals, and audit helpers."""

from __future__ import annotations

import json
import re
from typing import Any

import envy_db

RISK_LEVELS = {
    "read",
    "write_local",
    "execute_local",
    "external_read",
    "external_write",
    "spend_money",
    "credential_change",
}

TOOL_METADATA: dict[str, dict] = {
    "sandbox_shell": {
        "category": "local",
        "risk_level": "execute_local",
        "requires_approval": False,
        "runner": "native_sandbox",
    },
    "sandbox_list": {
        "category": "filesystem",
        "risk_level": "read",
        "requires_approval": False,
        "runner": "native_sandbox",
    },
    "sandbox_read_file": {
        "category": "filesystem",
        "risk_level": "read",
        "requires_approval": False,
        "runner": "native_sandbox",
    },
    "sandbox_write_file": {
        "category": "filesystem",
        "risk_level": "write_local",
        "requires_approval": False,
        "runner": "native_sandbox",
    },
    "project_status": {
        "category": "project",
        "risk_level": "read",
        "requires_approval": False,
        "runner": "native",
    },
    "mcp_inventory": {
        "category": "mcp",
        "risk_level": "read",
        "requires_approval": False,
        "runner": "native",
    },
    "plugin_inventory": {
        "category": "plugins",
        "risk_level": "read",
        "requires_approval": False,
        "runner": "native",
    },
    "system_shell": {
        "category": "local",
        "risk_level": "execute_local",
        "requires_approval": True,
        "runner": "native_system",
    },
    "system_list": {
        "category": "filesystem",
        "risk_level": "read",
        "requires_approval": False,
        "runner": "native_system",
    },
    "system_read_file": {
        "category": "filesystem",
        "risk_level": "read",
        "requires_approval": False,
        "runner": "native_system",
    },
    "system_write_file": {
        "category": "filesystem",
        "risk_level": "write_local",
        "requires_approval": True,
        "runner": "native_system",
    },
    "clipboard_get": {
        "category": "desktop",
        "risk_level": "read",
        "requires_approval": False,
        "runner": "native_desktop",
    },
    "clipboard_set": {
        "category": "desktop",
        "risk_level": "write_local",
        "requires_approval": True,
        "runner": "native_desktop",
    },
    "screen_snapshot": {
        "category": "desktop",
        "risk_level": "read",
        "requires_approval": False,
        "runner": "native_desktop",
    },
}

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_./:-]+")


def enrich_specs(specs: list[dict]) -> list[dict]:
    tools: list[dict] = []
    for spec in specs:
        name = spec.get("name")
        if not isinstance(name, str) or not name:
            continue
        meta = TOOL_METADATA.get(name, {})
        risk = meta.get("risk_level", "read")
        if risk not in RISK_LEVELS:
            risk = "read"
        tool = {
            "id": name,
            "name": name,
            "description": spec.get("description") or "",
            "category": meta.get("category", "local"),
            "risk_level": risk,
            "input_schema": spec.get("args") or spec.get("input_schema") or {},
            "requires_approval": bool(meta.get("requires_approval", False)),
            "runner": meta.get("runner", "native"),
            "credential_keys": list(meta.get("credential_keys") or []),
            "enabled": spec.get("enabled", True) is not False,
        }
        tools.append(tool)
    envy_db.upsert_tool_catalog(tools)
    return tools


def public_catalog(specs: list[dict]) -> dict:
    return {
        "schema": "envy.tool_catalog.v1",
        "risk_levels": sorted(RISK_LEVELS),
        "tools": enrich_specs(specs),
    }


def search(specs: list[dict], query: str, category: str | None = None, limit: int = 12) -> list[dict]:
    tools = enrich_specs(specs)
    tokens = {t.lower() for t in _TOKEN_RE.findall(query or "")}
    category_l = category.lower() if isinstance(category, str) and category else None
    ranked = []
    for tool in tools:
        if category_l and tool["category"].lower() != category_l:
            continue
        haystack = " ".join(
            [
                tool["id"],
                tool["name"],
                tool["category"],
                tool["risk_level"],
                tool["description"],
            ]
        ).lower()
        score = sum(3 if token in tool["id"].lower() else 1 for token in tokens if token in haystack)
        if not tokens:
            score = 1
        if score <= 0:
            continue
        ranked.append((score, tool))
    ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
    summaries = []
    for score, tool in ranked[: max(1, min(int(limit), 50))]:
        summaries.append(
            {
                "id": tool["id"],
                "name": tool["name"],
                "category": tool["category"],
                "risk_level": tool["risk_level"],
                "requires_approval": tool["requires_approval"],
                "description": tool["description"],
                "enabled": tool["enabled"],
                "score": score,
                "credential_keys": tool["credential_keys"],
            }
        )
    return summaries


def get_tool(specs: list[dict], tool_id: str) -> dict | None:
    for tool in enrich_specs(specs):
        if tool["id"] == tool_id or tool["name"] == tool_id:
            return tool
    return None


def approval_required(tool: dict, approval_mode: str | None = None) -> bool:
    if approval_mode in {"allow_once", "allow_for_session", "approved", "agent"}:
        return False
    if tool["risk_level"] in {"external_write", "spend_money", "credential_change"}:
        return True
    return bool(tool.get("requires_approval"))


def scrub_for_log(args: Any) -> dict:
    if not isinstance(args, dict):
        return {}
    clean = {}
    for key, value in args.items():
        lower = str(key).lower()
        if any(marker in lower for marker in ("token", "secret", "password", "apikey", "api_key")):
            clean[key] = "<redacted>"
        else:
            clean[key] = value
    return clean


def audit_tool_call(
    *,
    tool_id: str,
    args: dict,
    result: dict,
    tool: dict | None = None,
    approved: bool = False,
    task_id: str | None = None,
    run_id: str | None = None,
) -> str:
    ok = bool(result.get("ok"))
    status = "ok" if ok else "error"
    if result.get("error") == "approval_required":
        status = "blocked"
    return envy_db.log_tool_call(
        tool_id=tool_id,
        args=scrub_for_log(args),
        result=result,
        risk_level=(tool or {}).get("risk_level"),
        approved=approved,
        status=status,
        task_id=task_id,
        run_id=run_id,
        elapsed_ms=result.get("elapsed_ms") if isinstance(result.get("elapsed_ms"), int) else None,
        error=result.get("error") if isinstance(result.get("error"), str) else None,
    )


def describe(tool: dict) -> dict:
    public = dict(tool)
    public["input_schema_json"] = json.dumps(tool.get("input_schema") or {}, ensure_ascii=False)
    return public
