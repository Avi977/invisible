"""Tests for lib/api/tools.py — the /api/v1/tools CRUD data adapter.

Each test name describes the exact behavior it asserts. See
01-01-PLAN.md::<behavior> for the contract these tests enforce (D-01..D-07).

All tests are hermetic: they monkeypatch INVISIBLE_HOME to a pytest tmp_path
so nothing touches the user's real ~/.invisible directory. config.home()
reads $INVISIBLE_HOME at call time, so no module reload is needed for tools.py.

The handlers are transport-agnostic: each takes a `handler` object exposing
.path (the request line, e.g. "/api/v1/tools?project=foo"), ._json_body (the
PUT payload the daemon's do_PUT parses and stashes), and ._send_json(obj, status)
which produces the response. The FakeHandler below records the last (obj, status).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Put the repo's lib/ on the import path so `import api` and `from api import ...`
# resolve. This mirrors how bin/invisible-dashboard sets up its own sys.path.
HERE = Path(__file__).resolve().parent
LIB = HERE.parent / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))


# ────────────────────────────────────────────────────────────────────────
# test double
# ────────────────────────────────────────────────────────────────────────


class FakeHandler:
    """Minimal stand-in for the daemon's DashboardHandler.

    Exposes the three attributes tools.py's handlers read:
      - path:       the raw request path incl. query string
      - _json_body: the parsed PUT body (the daemon's do_PUT stashes it here)
      - _send_json: records the last (obj, status) the handler emitted
    """

    def __init__(self, path: str, json_body=None):
        self.path = path
        self._json_body = json_body if json_body is not None else {}
        self.sent_obj = None
        self.sent_status = None

    def _send_json(self, obj, status=200):
        self.sent_obj = obj
        self.sent_status = status


def _workflows_dir(home: Path) -> Path:
    return home / "workflows"


def _workflow_file(home: Path, project: str) -> Path:
    return _workflows_dir(home) / f"{project}.json"


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Redirect INVISIBLE_HOME to tmp_path. config.home() reads it at call time."""
    monkeypatch.setenv("INVISIBLE_HOME", str(tmp_path))
    # Drop any cached config import so config.home() re-reads the env var.
    for mod in list(sys.modules):
        if mod == "config":
            del sys.modules[mod]
    return tmp_path


# ────────────────────────────────────────────────────────────────────────
# GET
# ────────────────────────────────────────────────────────────────────────


def test_get_missing_project_returns_empty_200(isolated_home):
    """D-05 — GET on a never-saved project → 200 {nodes:[], edges:[], updated_at:null}."""
    from api import tools

    h = FakeHandler("/api/v1/tools?project=neverseen")
    tools.handle_get(h)

    assert h.sent_status == 200
    assert h.sent_obj == {"nodes": [], "edges": [], "updated_at": None}


def test_get_after_put_round_trips(isolated_home):
    """D-05/D-06 — GET after PUT returns the exact nodes/edges + matching updated_at."""
    from api import tools

    nodes = [{"id": "a", "kind": "Claude"}]
    edges = [{"from": "a", "to": "b"}]
    put_h = FakeHandler("/api/v1/tools?project=jobslayer",
                        json_body={"nodes": nodes, "edges": edges})
    tools.handle_put(put_h)
    assert put_h.sent_status == 200
    put_updated_at = put_h.sent_obj["updated_at"]

    get_h = FakeHandler("/api/v1/tools?project=jobslayer")
    tools.handle_get(get_h)

    assert get_h.sent_status == 200
    assert get_h.sent_obj["nodes"] == nodes
    assert get_h.sent_obj["edges"] == edges
    assert get_h.sent_obj["updated_at"] == put_updated_at


# ────────────────────────────────────────────────────────────────────────
# PUT
# ────────────────────────────────────────────────────────────────────────


def test_put_writes_file_and_returns_iso_updated_at(isolated_home):
    """D-06/D-02 — PUT returns a non-null ISO-8601 updated_at and the file now exists."""
    from api import tools

    h = FakeHandler("/api/v1/tools?project=jobslayer",
                    json_body={"nodes": [{"id": "a", "kind": "Claude"}], "edges": []})
    tools.handle_put(h)

    assert h.sent_status == 200
    updated_at = h.sent_obj["updated_at"]
    assert isinstance(updated_at, str) and updated_at
    # Must parse as ISO-8601 (datetime.fromisoformat handles the +00:00 offset).
    from datetime import datetime
    datetime.fromisoformat(updated_at)

    assert _workflow_file(isolated_home, "jobslayer").exists()


def test_put_nodes_not_a_list_is_400_and_no_write(isolated_home):
    """D-06 — PUT with nodes not a list → 400 and NO file written."""
    from api import tools

    h = FakeHandler("/api/v1/tools?project=jobslayer",
                    json_body={"nodes": "x", "edges": []})
    tools.handle_put(h)

    assert h.sent_status == 400
    assert not _workflow_file(isolated_home, "jobslayer").exists()


def test_put_edges_not_a_list_is_400_and_no_write(isolated_home):
    """D-06 — PUT with edges not a list → 400 and NO file written."""
    from api import tools

    h = FakeHandler("/api/v1/tools?project=jobslayer",
                    json_body={"nodes": [], "edges": {"bad": 1}})
    tools.handle_put(h)

    assert h.sent_status == 400
    assert not _workflow_file(isolated_home, "jobslayer").exists()


def test_put_leaves_no_tmp_file(isolated_home):
    """D-02 — after a PUT, no leftover *.tmp file remains in the workflows dir."""
    from api import tools

    h = FakeHandler("/api/v1/tools?project=jobslayer",
                    json_body={"nodes": [], "edges": []})
    tools.handle_put(h)

    wf_dir = _workflows_dir(isolated_home)
    leftovers = list(wf_dir.glob("*.tmp"))
    assert leftovers == [], f"leftover tmp files: {leftovers}"


# ────────────────────────────────────────────────────────────────────────
# DELETE
# ────────────────────────────────────────────────────────────────────────


def test_delete_existing_file_returns_deleted_true(isolated_home):
    """D-07 — DELETE on an existing file → 200 {deleted:true}, file gone."""
    from api import tools

    put_h = FakeHandler("/api/v1/tools?project=jobslayer",
                        json_body={"nodes": [], "edges": []})
    tools.handle_put(put_h)
    assert _workflow_file(isolated_home, "jobslayer").exists()

    del_h = FakeHandler("/api/v1/tools?project=jobslayer")
    tools.handle_delete(del_h)

    assert del_h.sent_status == 200
    assert del_h.sent_obj == {"deleted": True}
    assert not _workflow_file(isolated_home, "jobslayer").exists()


def test_delete_missing_file_returns_404(isolated_home):
    """D-07 — DELETE on a missing file → 404."""
    from api import tools

    h = FakeHandler("/api/v1/tools?project=neverexisted")
    tools.handle_delete(h)

    assert h.sent_status == 404


# ────────────────────────────────────────────────────────────────────────
# slug validation / traversal (D-03)
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "project",
    [
        "",          # empty
        ".",         # current dir
        "..",        # parent dir
        "../etc",    # traversal
        "a/b",       # slash
        "A",         # uppercase out of charset
        "foo%2e",    # encoded char present
        "-leading",  # may not start with hyphen
        "x" * 65,    # too long (max 64)
    ],
)
def test_invalid_slug_get_is_400_and_writes_nothing(isolated_home, project):
    """D-03 — invalid project on GET → 400, and nothing created under workflows/."""
    from api import tools

    wf_dir = _workflows_dir(isolated_home)
    before = sorted(p.name for p in wf_dir.iterdir()) if wf_dir.exists() else None

    # urllib.parse_qs drops empty values, so the empty-string case arrives as
    # a None project — both must be rejected identically. Build the path the
    # way the daemon would: an empty value yields "?project=" with no value.
    qval = "" if project == "" else project
    h = FakeHandler(f"/api/v1/tools?project={qval}")
    tools.handle_get(h)

    assert h.sent_status == 400, f"project={project!r} should be 400"
    after = sorted(p.name for p in wf_dir.iterdir()) if wf_dir.exists() else None
    assert after == before, f"project={project!r} mutated workflows dir"


@pytest.mark.parametrize(
    "project",
    ["", "..", "../etc", "a/b", "A"],
)
def test_invalid_slug_put_is_400_and_writes_nothing(isolated_home, project):
    """D-03 — invalid project on PUT → 400, and no file escapes workflows/."""
    from api import tools

    wf_dir = _workflows_dir(isolated_home)
    before = sorted(p.name for p in wf_dir.iterdir()) if wf_dir.exists() else None

    qval = "" if project == "" else project
    h = FakeHandler(f"/api/v1/tools?project={qval}",
                    json_body={"nodes": [], "edges": []})
    tools.handle_put(h)

    assert h.sent_status == 400, f"project={project!r} should be 400"
    after = sorted(p.name for p in wf_dir.iterdir()) if wf_dir.exists() else None
    assert after == before, f"project={project!r} mutated workflows dir"


def test_valid_slug_forms_are_accepted(isolated_home):
    """D-03 — representative valid slugs round-trip through PUT then GET."""
    from api import tools

    for project in ("a", "jobslayer", "proj_1", "proj-1", "a1b2c3", "x" * 64):
        put_h = FakeHandler(f"/api/v1/tools?project={project}",
                            json_body={"nodes": [], "edges": []})
        tools.handle_put(put_h)
        assert put_h.sent_status == 200, f"valid slug {project!r} rejected"
        assert _workflow_file(isolated_home, project).exists()
