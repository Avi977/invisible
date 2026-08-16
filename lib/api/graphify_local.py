"""Local Graphify wrapper.

Graphify is optional at runtime. If the `graphify` CLI or Python module is
installed, Envy can run it against a configured project and import graph.json
from Graphify's graphify-out/ directory into $INVISIBLE_HOME/graphify/<project>/.
No paid model provider is configured here.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from importlib.util import find_spec
from pathlib import Path
from typing import Any

import config

REPO_URL = "https://github.com/safishamsi/graphify"
PACKAGE = "graphifyy"
LICENSE = "MIT"
DEFAULT_BACKEND = "ollama"
DEFAULT_MODEL = "qwen3:4b"
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _valid_slug(project: str | None) -> bool:
    return isinstance(project, str) and bool(_SLUG_RE.fullmatch(project))


def _graph_dir(project: str) -> Path:
    return config.home() / "graphify" / project


def _graph_path(project: str) -> Path:
    return _graph_dir(project) / "graph.json"


def _graphify_command() -> list[str] | None:
    graphify_bin = shutil.which("graphify")
    if graphify_bin:
        return [graphify_bin]
    if find_spec("graphify") is not None:
        return [sys.executable, "-m", "graphify"]
    return None


def project_root(project: str) -> Path | None:
    try:
        cfg = config.load_toml()
    except Exception:  # noqa: BLE001
        cfg = {}
    for p in cfg.get("projects", []) or []:
        if p.get("name") != project:
            continue
        raw = p.get("repo_path")
        if not isinstance(raw, str) or not raw:
            break
        try:
            path = Path(os.path.expanduser(raw)).resolve()
        except (OSError, RuntimeError):
            break
        if path.exists() and path.is_dir():
            return path
        break
    if project == "invisible":
        try:
            return config.home().resolve()
        except Exception:  # noqa: BLE001
            return None
    return None


def status(project: str | None = None) -> dict:
    cmd = _graphify_command()
    body = {
        "tool": "graphify",
        "repo": REPO_URL,
        "package": PACKAGE,
        "license": LICENSE,
        "local_only": True,
        "cost": 0,
        "installed": bool(cmd),
        "path": cmd[0] if cmd else None,
        "command": cmd,
        "backend": DEFAULT_BACKEND,
        "model": DEFAULT_MODEL,
        "install_hint": "uv tool install graphifyy or py -m pip install graphifyy",
    }
    if project and _valid_slug(project):
        body["project"] = project
        body["graph_json"] = str(_graph_path(project))
        body["graph_present"] = _graph_path(project).exists()
    return body


def load_graph(project: str) -> dict | None:
    path = _graph_path(project)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        return data
    return None


def _candidate_graph_paths(root: Path, out_dir: Path) -> list[Path]:
    return [
        out_dir / "graphify-out" / "graph.json",
        out_dir / "graph.json",
        root / "graphify-out" / "graph.json",
    ]


def _import_graph_output(project: str, root: Path, out_dir: Path) -> Path | None:
    for candidate in _candidate_graph_paths(root, out_dir):
        if not candidate.exists():
            continue
        target = _graph_path(project)
        target.parent.mkdir(parents=True, exist_ok=True)
        if candidate.resolve() != target.resolve():
            shutil.copy2(candidate, target)
        try:
            from api import relations

            relations.clear_cache()
        except Exception:  # noqa: BLE001
            pass
        return target
    return None


def normalize_graph(data: dict, project: str) -> dict:
    raw_nodes = data.get("nodes", [])
    raw_edges = data.get("edges") or data.get("links") or []
    nodes: list[dict] = []
    edges: list[dict] = []
    seen: set[str] = set()
    if isinstance(raw_nodes, dict):
        raw_nodes = [{"id": k, **(v if isinstance(v, dict) else {})} for k, v in raw_nodes.items()]
    for n in raw_nodes if isinstance(raw_nodes, list) else []:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or n.get("key") or n.get("name") or "")
        if not nid or nid in seen:
            continue
        raw_type = str(n.get("type") or n.get("kind") or n.get("file_type") or "module")
        node_type = {
            "code": "module",
            "markdown": "doc",
            "md": "doc",
            "pdf": "doc",
        }.get(raw_type.lower(), raw_type)
        seen.add(nid)
        nodes.append({
            "id": nid,
            "label": str(n.get("label") or n.get("name") or nid),
            "type": node_type,
            "project": project,
            "file_path": n.get("file_path") or n.get("path") or n.get("source_file"),
            "graphify": True,
        })
    for e in raw_edges if isinstance(raw_edges, list) else []:
        if not isinstance(e, dict):
            continue
        frm = e.get("from") or e.get("source")
        to = e.get("to") or e.get("target")
        if frm in seen and to in seen:
            edges.append({
                "from": frm,
                "to": to,
                "kind": str(e.get("kind") or e.get("type") or e.get("relation") or "graphify"),
            })
    return {"nodes": nodes, "edges": edges, "source": "graphify"}


def _clear_project_graphify_cache(project: str) -> None:
    root = _graph_dir(project)
    try:
        shutil.rmtree(root / "graphify-out", ignore_errors=True)
        (_graph_path(project)).unlink(missing_ok=True)
    except OSError:
        pass


def run_handler(body: Any) -> tuple[int, dict]:
    if not isinstance(body, dict):
        return 400, {"error": "bad_request", "hint": "body must be a JSON object"}
    project = body.get("project")
    if not _valid_slug(project):
        return 400, {"error": "bad_request", "hint": "valid project is required"}
    cmd_prefix = _graphify_command()
    if not cmd_prefix:
        return 503, {"error": "graphify_missing", **status(project)}
    root = project_root(project)
    if root is None:
        return 404, {"error": "project_not_found", "project": project}
    out_dir = _graph_dir(project)
    out_dir.mkdir(parents=True, exist_ok=True)
    if body.get("force", True):
        _clear_project_graphify_cache(project)
    backend = body.get("backend") if isinstance(body.get("backend"), str) else DEFAULT_BACKEND
    model = body.get("model") if isinstance(body.get("model"), str) else DEFAULT_MODEL
    semantic = bool(body.get("semantic", False))
    repo_graph_dir = root / "graphify-out"
    repo_graph_existed = repo_graph_dir.exists()
    if semantic:
        cmd = [
            *cmd_prefix,
            "extract",
            str(root),
            "--backend",
            backend,
            "--model",
            model,
            "--max-concurrency",
            "1",
            "--out",
            str(out_dir),
        ]
        if body.get("no_cluster", True):
            cmd.append("--no-cluster")
    else:
        cmd = [*cmd_prefix, "update", str(root), "--force", "--no-cluster"]
    env = {
        **os.environ,
        "OLLAMA_BASE_URL": os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1"),
        "OLLAMA_API_KEY": os.environ.get("OLLAMA_API_KEY", "ollama"),
    }
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            timeout=int(body.get("timeout_s") or 600),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return 504, {"error": "graphify_timeout", "project": project}
    except OSError as exc:
        return 502, {"error": "graphify_failed", "hint": type(exc).__name__}
    imported = _import_graph_output(project, root, out_dir) if proc.returncode == 0 else None
    if not semantic and not repo_graph_existed:
        shutil.rmtree(repo_graph_dir, ignore_errors=True)
    graph = load_graph(project) if imported else None
    normalized = normalize_graph(graph, project) if graph else {"nodes": [], "edges": []}
    node_count = len(normalized.get("nodes", []))
    ok = proc.returncode == 0 and imported is not None and node_count > 0
    error = None
    if proc.returncode != 0:
        error = "graphify_failed"
    elif imported is None:
        error = "graphify_output_missing"
    elif node_count == 0:
        error = "graphify_empty"
    return 200 if ok else 502, {
        **({"error": error} if error else {}),
        "project": project,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
        "graph_dir": str(out_dir),
        "graph_json": str(_graph_path(project)),
        "imported_graph_json": str(imported) if imported else None,
        "graph_present": _graph_path(project).exists(),
        "node_count": node_count,
        "command": cmd,
        "backend": backend,
        "model": model,
        "semantic": semantic,
        "local_only": True,
        "cost": 0,
    }


def handle_status(handler: Any) -> None:
    q = urllib.parse.parse_qs(urllib.parse.urlparse(handler.path).query)
    project = q.get("project", [None])[0]
    if project is not None and not _valid_slug(project):
        handler._send_json({"error": "bad_request"}, 400)
        return
    handler._send_json(status(project))
