"""Unit tests for lib.api.chat.chat_handler.

All subprocess invocations are mocked — these tests must NOT shell out to a
real `claude` binary. The aim is to exercise the validation + error-mapping
branches deterministically and to assert the anti-injection contract (the
user-supplied `message` and `page_context` MUST be passed via STDIN, never
appended to argv).
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

HERE = Path(__file__).resolve().parent
# Make `from api.chat import chat_handler` resolvable when running the file
# directly. Inside the lib/ tree the import path is `api.chat`; from the repo
# root it's `lib.api.chat`. We support both.
sys.path.insert(0, str(HERE.parent))  # so `api.chat` resolves
sys.path.insert(0, str(HERE.parent.parent))  # so `lib.api.chat` resolves

from api.chat import chat_handler, MAX_MESSAGE_CHARS, CLAUDE_CMD, CLAUDE_TIMEOUT_S  # noqa: E402


def _fake_envelope(text: str = "pong",
                   input_tokens: int = 5,
                   output_tokens: int = 3,
                   cost_usd: float = 0.0001,
                   duration_ms: int = 42) -> str:
    """Mimic claude --output-format json output shape."""
    return json.dumps({
        "result": text,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
        "total_cost_usd": cost_usd,
        "duration_ms": duration_ms,
    })


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    cp = MagicMock()
    cp.stdout = stdout
    cp.stderr = stderr
    cp.returncode = returncode
    return cp


class TestChatHandlerHappyPath(unittest.TestCase):
    def test_1_valid_input_returns_200_with_text_usage_cost(self):
        with patch("api.chat.subprocess.run",
                   return_value=_completed(stdout=_fake_envelope("pong"))) as m:
            status, body = chat_handler(
                {"message": "say pong", "page_context": "dashboard"}
            )
        self.assertEqual(status, 200, msg=body)
        self.assertIn("text", body)
        self.assertIn("usage", body)
        self.assertIn("cost", body)
        self.assertEqual(body["text"], "pong")
        self.assertIsInstance(body["usage"], dict)
        self.assertEqual(body["usage"]["input_tokens"], 5)
        self.assertEqual(body["usage"]["output_tokens"], 3)
        self.assertEqual(body["cost"], body["usage"]["cost_usd"])
        # subprocess.run was called exactly once.
        self.assertEqual(m.call_count, 1)
        # No shell=True; argv passed as a list.
        call_args, call_kwargs = m.call_args
        self.assertNotIn("shell", call_kwargs)  # implicit shell=False
        self.assertIsInstance(call_args[0], list)


class TestChatHandlerValidation(unittest.TestCase):
    def test_2_missing_message_returns_400(self):
        with patch("api.chat.subprocess.run") as m:
            status, body = chat_handler({"page_context": "dashboard"})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "bad_request")
        self.assertIn("message", body["hint"].lower())
        m.assert_not_called()

    def test_3_missing_page_context_returns_400(self):
        with patch("api.chat.subprocess.run") as m:
            status, body = chat_handler({"message": "hi"})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "bad_request")
        self.assertIn("page_context", body["hint"].lower())
        m.assert_not_called()

    def test_4_non_string_message_returns_400(self):
        with patch("api.chat.subprocess.run") as m:
            status, body = chat_handler({"message": 123, "page_context": "d"})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "bad_request")
        m.assert_not_called()

        with patch("api.chat.subprocess.run") as m:
            status, body = chat_handler({"message": {"x": 1}, "page_context": "d"})
        self.assertEqual(status, 400)
        m.assert_not_called()

    def test_4b_non_dict_body_returns_400(self):
        with patch("api.chat.subprocess.run") as m:
            status, body = chat_handler("not a dict")  # type: ignore[arg-type]
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "bad_request")
        m.assert_not_called()

    def test_4c_empty_message_returns_400(self):
        with patch("api.chat.subprocess.run") as m:
            status, body = chat_handler({"message": "", "page_context": "d"})
        self.assertEqual(status, 400)
        m.assert_not_called()

    def test_5_message_too_large_returns_413(self):
        with patch("api.chat.subprocess.run") as m:
            status, body = chat_handler(
                {"message": "x" * (MAX_MESSAGE_CHARS + 1), "page_context": "d"}
            )
        self.assertEqual(status, 413)
        self.assertEqual(body["error"], "message_too_large")
        m.assert_not_called()


class TestChatHandlerFailureModes(unittest.TestCase):
    def test_6_timeout_returns_504(self):
        with patch("api.chat.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd=CLAUDE_CMD,
                                                         timeout=CLAUDE_TIMEOUT_S)):
            status, body = chat_handler(
                {"message": "hi", "page_context": "d"}
            )
        self.assertEqual(status, 504)
        self.assertEqual(body["error"], "timeout")
        self.assertIn("60", body["hint"])

    def test_7_file_not_found_returns_502_and_redacts_paths(self):
        with patch("api.chat.subprocess.run",
                   side_effect=FileNotFoundError("/usr/local/bin/claude not found")):
            status, body = chat_handler(
                {"message": "hi", "page_context": "d"}
            )
        self.assertEqual(status, 502)
        self.assertEqual(body["error"], "claude_cli_failed")
        # No absolute paths leaked into the hint.
        self.assertNotIn("/usr/local", body["hint"])
        self.assertNotIn("/Users", body["hint"])

    def test_8_unauth_stderr_returns_401(self):
        with patch("api.chat.subprocess.run",
                   return_value=_completed(
                       stdout="",
                       stderr="Error: not logged in to claude.ai. Run `claude login` first.",
                       returncode=1)):
            status, body = chat_handler(
                {"message": "hi", "page_context": "d"}
            )
        self.assertEqual(status, 401)
        self.assertEqual(body["error"], "claude_unauthenticated")
        self.assertIn("claude login", body["hint"])

    def test_8b_unauth_authentication_word_returns_401(self):
        with patch("api.chat.subprocess.run",
                   return_value=_completed(
                       stdout="",
                       stderr="authentication failure: token missing",
                       returncode=1)):
            status, body = chat_handler(
                {"message": "hi", "page_context": "d"}
            )
        self.assertEqual(status, 401)
        self.assertEqual(body["error"], "claude_unauthenticated")

    def test_9_rate_limit_stderr_returns_429(self):
        with patch("api.chat.subprocess.run",
                   return_value=_completed(
                       stdout="",
                       stderr="HTTP 429: rate limit exceeded, try again in 30s",
                       returncode=1)):
            status, body = chat_handler(
                {"message": "hi", "page_context": "d"}
            )
        self.assertEqual(status, 429)
        self.assertEqual(body["error"], "rate_limited")

    def test_10_invalid_json_envelope_returns_502(self):
        with patch("api.chat.subprocess.run",
                   return_value=_completed(stdout="this is not json",
                                           returncode=0)):
            status, body = chat_handler(
                {"message": "hi", "page_context": "d"}
            )
        self.assertEqual(status, 502)
        self.assertEqual(body["error"], "claude_cli_failed")
        self.assertIn("parse", body["hint"].lower())


class TestChatHandlerInjectionPrevention(unittest.TestCase):
    def test_11_command_is_constant_argv_user_input_via_stdin(self):
        # Booby-trap the message with shell metacharacters. They must end up
        # in the STDIN argument to subprocess.run, never in argv.
        hostile = "hi; rm -rf $HOME && echo PWNED"
        with patch("api.chat.subprocess.run",
                   return_value=_completed(stdout=_fake_envelope())) as m:
            chat_handler({"message": hostile, "page_context": "dashboard"})
        call_args, call_kwargs = m.call_args
        argv = call_args[0]
        # Exact argv shape from spec.
        self.assertEqual(argv, ["claude", "-p", "--output-format", "json"])
        # User input is in stdin, NOT argv.
        self.assertIn("input", call_kwargs)
        self.assertIn(hostile, call_kwargs["input"])
        # No argv element contains the hostile string.
        for tok in argv:
            self.assertNotIn(hostile, tok)
        # shell=True is forbidden.
        self.assertNotEqual(call_kwargs.get("shell", False), True)

    def test_12_page_context_in_prompt_string_not_argv(self):
        weird_page = "dashboard; cat /etc/passwd"
        with patch("api.chat.subprocess.run",
                   return_value=_completed(stdout=_fake_envelope())) as m:
            chat_handler({"message": "hi", "page_context": weird_page})
        call_args, call_kwargs = m.call_args
        argv = call_args[0]
        self.assertEqual(argv, ["claude", "-p", "--output-format", "json"])
        self.assertIn(weird_page, call_kwargs["input"])
        for tok in argv:
            self.assertNotIn(weird_page, tok)


if __name__ == "__main__":
    unittest.main()
