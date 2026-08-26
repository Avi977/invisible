"""Unit tests for lib.api.handoff._graph_excerpt.

The graph is mocked -- no relations build, no graphify output on disk.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent))

from api import handoff  # noqa: E402


def _graph() -> dict:
    return {
        "nodes": [
            {"id": "v1", "label": "hermes.py",
             "source_file": "vendor/hermes-agent/hermes.py"},
            {"id": "v2", "label": "index.js",
             "source_file": "node_modules/three/index.js"},
            {"id": "a", "label": "invisible.bash",
             "source_file": "completions/invisible.bash"},
            {"id": "b", "label": "router.py", "source_file": "lib/api/router.py"},
            {"id": "c", "label": "chat.py", "source_file": "lib/api/chat.py"},
            {"id": "d", "label": "README.md", "source_file": "README.md"},
        ],
        "edges": [
            {"from": "b", "to": "c", "kind": "import"},
            {"from": "a", "to": "d", "kind": "mentions"},
        ],
    }


def _excerpt(query=None, limit=40, graph=None):
    with patch("api.relations.build_graph",
               return_value=_graph() if graph is None else graph):
        return handoff._graph_excerpt("invisible", query, limit)


def _ids(excerpt) -> set:
    return {n["id"] for n in excerpt["nodes"]}


class GraphExcerptTests(unittest.TestCase):
    """Regression guard: this used to return nodes[:40] in walk order, so
    every packet described the same first few files whatever was asked."""

    def test_query_seeds_on_matching_nodes(self):
        ids = _ids(_excerpt("wire the router endpoint into the overlay"))
        self.assertIn("b", ids)          # router.py matched the request
        self.assertNotIn("d", ids)       # README did not

    def test_seed_neighbours_are_pulled_in(self):
        excerpt = _excerpt("fix the router")
        self.assertIn("c", _ids(excerpt))  # chat.py, via b -[import]-> c
        self.assertIn({"from": "b", "to": "c", "kind": "import"},
                      excerpt["edges"])

    def test_vendored_nodes_never_appear(self):
        for query in (None, "hermes three index"):
            ids = _ids(_excerpt(query))
            self.assertNotIn("v1", ids, query)   # vendor/
            self.assertNotIn("v2", ids, query)   # node_modules/

    def test_no_query_keeps_walk_order(self):
        self.assertEqual([n["id"] for n in _excerpt(limit=2)["nodes"]],
                         ["a", "b"])

    def test_unmatched_query_falls_back_to_walk_order(self):
        self.assertEqual(
            [n["id"] for n in _excerpt("xyzzy plugh", limit=2)["nodes"]],
            ["a", "b"])

    def test_limit_is_respected(self):
        self.assertLessEqual(len(_excerpt("router", limit=1)["nodes"]), 1)

    def test_edges_need_both_endpoints_present(self):
        excerpt = _excerpt("router", limit=1)
        ids = _ids(excerpt)
        for e in excerpt["edges"]:
            self.assertIn(e["from"], ids)
            self.assertIn(e["to"], ids)

    def test_build_graph_failure_is_not_fatal(self):
        with patch("api.relations.build_graph", side_effect=RuntimeError("boom")):
            self.assertEqual(handoff._graph_excerpt("invisible", "router"),
                             {"nodes": [], "edges": []})


class NodeScoreTests(unittest.TestCase):
    def test_label_outweighs_path(self):
        terms = handoff._terms("router")
        label_hit = handoff._node_score(
            {"label": "router.py", "source_file": "lib/api/other.py"}, terms)
        path_hit = handoff._node_score(
            {"label": "other.py", "source_file": "lib/api/router.py"}, terms)
        self.assertGreater(label_hit, path_hit)

    def test_short_tokens_are_dropped(self):
        self.assertEqual(handoff._terms("go to py of a"), set())

    def test_windows_paths_normalise(self):
        self.assertTrue(handoff._is_vendored(
            {"source_file": r"vendor\hermes-agent\hermes.py"}))


if __name__ == "__main__":
    unittest.main()
