"""Unit tests for lib.api.router.ask_handler.

Everything external is mocked — no Ollama, no claude binary, no hermes.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent))

from api import router  # noqa: E402


def _classify_response(route: str, confidence: float = 0.9) -> dict:
    return {"message": {"content": json.dumps(
        {"route": route, "confidence": confidence})}}


_MODELS_OK = (200, {"models": [{"name": "qwen3:14b"}], "default": "qwen3:14b"})


class ValidationTests(unittest.TestCase):
    def test_rejects_non_dict(self):
        status, body = router.ask_handler("nope")
        self.assertEqual(status, 400)

    def test_rejects_missing_message(self):
        status, body = router.ask_handler({})
        self.assertEqual(status, 400)

    def test_rejects_oversize(self):
        status, body = router.ask_handler(
            {"message": "x" * (router.MAX_MESSAGE_CHARS + 1)})
        self.assertEqual(status, 413)


class RoutingTests(unittest.TestCase):
    def test_local_route(self):
        with patch.object(router.ai, "_ollama_json",
                          return_value=_classify_response("local")), \
             patch.object(router, "_memory_block", return_value=""), \
             patch.object(router.ai, "list_models", return_value=_MODELS_OK), \
             patch.object(router.ai, "chat_handler",
                          return_value=(200, {"text": "hi", "model": "qwen3:14b"})) as ans:
            status, body = router.ask_handler({"message": "what is a monad"})
        self.assertEqual(status, 200)
        self.assertEqual(body["route"], "local")
        self.assertEqual(body["text"], "hi")
        self.assertEqual(ans.call_args[0][0]["model"], "qwen3:14b")

    def test_claude_route(self):
        with patch.object(router.ai, "_ollama_json",
                          return_value=_classify_response("claude")), \
             patch.object(router, "_memory_block", return_value="Relevant memory:\n- fact"), \
             patch.object(router, "_project_state", return_value="Checkpoint: {}"), \
             patch.object(router, "_curate", return_value="## Goal\nAnswer well"), \
             patch.object(router.chat, "chat_handler",
                          return_value=(200, {"text": "deep answer"})) as esc:
            status, body = router.ask_handler(
                {"message": "hard question",
                 "history": [{"role": "user", "content": "earlier turn"}]})
        self.assertEqual(status, 200)
        self.assertEqual(body["route"], "claude")
        self.assertEqual(body["provider"], "claude")
        self.assertTrue(body["memory_used"])
        self.assertTrue(body["curated"])
        sent = esc.call_args[0][0]["message"]
        for expected in ("Relevant memory:", "hard question", "## Goal",
                         "earlier turn", "Checkpoint:", "executive summary"):
            self.assertIn(expected, sent)

    def test_claude_route_curate_failure_still_escalates(self):
        with patch.object(router, "_memory_block", return_value=""), \
             patch.object(router, "_project_state", return_value=""), \
             patch.object(router, "_curate", return_value=""), \
             patch.object(router.chat, "chat_handler",
                          return_value=(200, {"text": "answer"})) as esc:
            status, body = router.ask_handler(
                {"message": "hard question", "force": "claude"})
        self.assertEqual(status, 200)
        self.assertFalse(body["curated"])
        self.assertIn("hard question", esc.call_args[0][0]["message"])

    def test_claude_route_curate_opt_out(self):
        with patch.object(router, "_memory_block", return_value=""), \
             patch.object(router, "_project_state", return_value=""), \
             patch.object(router, "_curate") as curate, \
             patch.object(router.chat, "chat_handler",
                          return_value=(200, {"text": "answer"})):
            status, body = router.ask_handler(
                {"message": "q", "force": "claude", "curate": False})
        curate.assert_not_called()
        self.assertFalse(body["curated"])

    def test_classify_failure_falls_back_to_local(self):
        with patch.object(router.ai, "_ollama_json", side_effect=OSError), \
             patch.object(router, "_memory_block", return_value=""), \
             patch.object(router.ai, "list_models", return_value=_MODELS_OK), \
             patch.object(router.ai, "chat_handler",
                          return_value=(200, {"text": "ok"})):
            status, body = router.ask_handler({"message": "anything"})
        self.assertEqual(status, 200)
        self.assertEqual(body["route"], "local")
        self.assertEqual(body["confidence"], 0.0)

    def test_force_skips_classify(self):
        with patch.object(router.ai, "_ollama_json") as classify, \
             patch.object(router, "_memory_block", return_value=""), \
             patch.object(router, "_project_state", return_value=""), \
             patch.object(router, "_curate", return_value=""), \
             patch.object(router.chat, "chat_handler",
                          return_value=(200, {"text": "x"})):
            status, body = router.ask_handler(
                {"message": "q", "force": "claude"})
        classify.assert_not_called()
        self.assertEqual(body["route"], "claude")
        self.assertEqual(body["confidence"], 1.0)


class SessionTests(unittest.TestCase):
    def test_session_writes_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(router.config, "home",
                              return_value=Path(tmp)), \
                 patch.object(router, "_memory_block", return_value=""), \
                 patch.object(router, "_project_state", return_value=""), \
                 patch.object(router, "_curate", return_value="## Goal\nBuild it"):
                status, body = router.ask_handler(
                    {"message": "build the thing", "force": "session",
                     "project_id": "invisible"})
            self.assertEqual(status, 200)
            self.assertEqual(body["route"], "session")
            packet = Path(body["packet_path"])
            self.assertTrue(packet.is_file())
            self.assertIn("handoffs", packet.parts)
            self.assertIn("invisible", packet.parts)
            text = packet.read_text(encoding="utf-8")
            self.assertIn("build the thing", text)
            self.assertIn("## Goal", text)
            self.assertIn("Claude Code", text)  # session-mode instructions

    def test_session_bad_slug_goes_global(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(router.config, "home",
                              return_value=Path(tmp)), \
                 patch.object(router, "_memory_block", return_value=""), \
                 patch.object(router, "_project_state", return_value=""), \
                 patch.object(router, "_curate", return_value=""):
                status, body = router.ask_handler(
                    {"message": "do it", "force": "session",
                     "project_id": "../evil"})
            self.assertEqual(status, 200)
            self.assertIn("_global", Path(body["packet_path"]).parts)


class ProjectStateTests(unittest.TestCase):
    """_project_state is patched out in every other test -- cover it directly.

    Regression guard: it once read edge keys "source"/"target", which
    build_graph never emits, so the Relations block silently never rendered.
    """

    _GRAPH = {
        "nodes": [{"id": "a", "label": "router.py"},
                  {"id": "b", "label": "chat.py"}],
        "edges": [{"from": "a", "to": "b", "kind": "import"}],
    }

    def _state(self, graph, project="invisible"):
        from api import handoff
        with patch.object(handoff, "_checkpoint", return_value=None), \
             patch.object(handoff, "_repo_path", return_value=None), \
             patch.object(handoff, "_graph_excerpt", return_value=graph):
            return router._project_state(project)

    def test_serializes_edges_from_build_graph_keys(self):
        state = self._state(self._GRAPH)
        self.assertIn("Related entities: router.py, chat.py", state)
        self.assertIn("Relations:", state)
        self.assertIn("router.py -[import]-> chat.py", state)

    def test_raw_graph_json_link_keys_are_not_edges(self):
        # graph.json on disk uses source/target under "links"; build_graph
        # normalises those away. If one leaks through unnormalised we emit
        # entities but no relations, rather than "None -[related]-> None".
        graph = {"nodes": self._GRAPH["nodes"],
                 "edges": [{"source": "a", "target": "b", "relation": "x"}]}
        state = self._state(graph)
        self.assertIn("Related entities:", state)
        self.assertNotIn("Relations:", state)

    def test_unlabelled_edge_falls_back_to_ids_and_kind(self):
        graph = {"nodes": [], "edges": [{"from": "x", "to": "y"}]}
        self.assertIn("x -[related]-> y", self._state(graph))

    def test_long_labels_are_trimmed(self):
        prose = ("Build the /api/v1/relations response: an Obsidian-style "
                 "graph derived from the project tree and its docstrings.")
        graph = {"nodes": [{"id": "a", "label": prose},
                           {"id": "b", "label": "chat.py"}],
                 "edges": [{"from": "a", "to": "b", "kind": "calls"}]}
        state = self._state(graph)
        self.assertIn("Build the /api/v1/relations response: an", state)
        self.assertIn("…", state)
        self.assertNotIn("docstrings", state)
        trimmed = ("Build the /api/v1/relations response: an "
                   "Obsidian-style gra" + chr(8230))
        self.assertLessEqual(len(trimmed), 60)
        self.assertIn(trimmed + " -[calls]-> chat.py", state)

    def test_short_collapses_whitespace(self):
        self.assertEqual(router._short("a\n  b\tc"), "a b c")

    def test_bad_slug_returns_empty(self):
        self.assertEqual(router._project_state("../evil"), "")

    def test_no_project_returns_empty(self):
        self.assertEqual(router._project_state(None), "")

if __name__ == "__main__":
    unittest.main()
