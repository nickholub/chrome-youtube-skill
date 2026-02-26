#!/usr/bin/env python3
"""Unit tests for yt_transcript.extractor"""

import json
import os
import subprocess
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch, MagicMock, call

import requests

from yt_transcript.extractor import YouTubeTranscriptExtractor


class TestParseVideoId(unittest.TestCase):
    def setUp(self):
        self.ext = YouTubeTranscriptExtractor()

    def test_standard_watch_url(self):
        self.assertEqual(
            self.ext._parse_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_watch_url_with_extra_params(self):
        self.assertEqual(
            self.ext._parse_video_id("https://www.youtube.com/watch?v=abc123XYZ_-&t=120"),
            "abc123XYZ_-",
        )

    def test_short_url(self):
        self.assertEqual(
            self.ext._parse_video_id("https://youtu.be/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_short_url_with_params(self):
        self.assertEqual(
            self.ext._parse_video_id("https://youtu.be/dQw4w9WgXcQ?t=30"),
            "dQw4w9WgXcQ",
        )

    def test_shorts_url(self):
        self.assertEqual(
            self.ext._parse_video_id("https://www.youtube.com/shorts/abcdefghijk"),
            "abcdefghijk",
        )

    def test_embed_url(self):
        self.assertEqual(
            self.ext._parse_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_mobile_url(self):
        self.assertEqual(
            self.ext._parse_video_id("https://m.youtube.com/watch?v=dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_plain_youtube_domain(self):
        self.assertEqual(
            self.ext._parse_video_id("https://youtube.com/watch?v=dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_invalid_url(self):
        self.assertIsNone(self.ext._parse_video_id("https://example.com/page"))

    def test_no_video_id_in_query(self):
        self.assertIsNone(
            self.ext._parse_video_id("https://www.youtube.com/watch?list=PLxyz")
        )

    def test_empty_string(self):
        self.assertIsNone(self.ext._parse_video_id(""))

    def test_random_string(self):
        self.assertIsNone(self.ext._parse_video_id("not a url at all"))


class TestResult(unittest.TestCase):
    def setUp(self):
        self.ext = YouTubeTranscriptExtractor()

    def test_default_result(self):
        r = self.ext._result()
        self.assertFalse(r["success"])
        self.assertEqual(r["video_id"], "")
        self.assertEqual(r["transcript"], "")
        self.assertEqual(r["error"], "")

    def test_success_result(self):
        r = self.ext._result(
            success=True, video_id="abc", title="Title",
            channel="Ch", transcript="hello world",
            language="en", method="dom",
        )
        self.assertTrue(r["success"])
        self.assertEqual(r["video_id"], "abc")
        self.assertEqual(r["title"], "Title")
        self.assertEqual(r["channel"], "Ch")
        self.assertEqual(r["transcript"], "hello world")
        self.assertEqual(r["language"], "en")
        self.assertEqual(r["method"], "dom")
        self.assertEqual(r["error"], "")

    def test_error_result(self):
        r = self.ext._result(error="something broke")
        self.assertFalse(r["success"])
        self.assertEqual(r["error"], "something broke")

    def test_result_has_all_keys(self):
        r = self.ext._result()
        expected_keys = {
            "success", "video_id", "title", "channel",
            "url", "transcript", "language", "method", "error",
        }
        self.assertEqual(set(r.keys()), expected_keys)


class TestOpenTab(unittest.TestCase):
    def setUp(self):
        self.ext = YouTubeTranscriptExtractor(port=9222)

    @patch("yt_transcript.extractor.requests")
    def test_put_success(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "TAB1", "webSocketDebuggerUrl": "ws://x"}
        mock_requests.put.return_value = mock_resp

        result = self.ext.open_tab("https://www.youtube.com/watch?v=abc")
        self.assertEqual(result["id"], "TAB1")
        mock_requests.put.assert_called_once()
        mock_requests.get.assert_not_called()

    @patch("yt_transcript.extractor.requests")
    def test_fallback_to_get_on_405(self, mock_requests):
        mock_put_resp = MagicMock()
        mock_put_resp.status_code = 405
        mock_requests.put.return_value = mock_put_resp

        mock_get_resp = MagicMock()
        mock_get_resp.json.return_value = {"id": "TAB2", "webSocketDebuggerUrl": "ws://y"}
        mock_requests.get.return_value = mock_get_resp

        result = self.ext.open_tab("https://www.youtube.com/watch?v=abc")
        self.assertEqual(result["id"], "TAB2")
        mock_requests.put.assert_called_once()
        mock_requests.get.assert_called_once()


class TestCloseTab(unittest.TestCase):
    def setUp(self):
        self.ext = YouTubeTranscriptExtractor(port=9222)

    @patch("yt_transcript.extractor.requests")
    def test_close_tab(self, mock_requests):
        self.ext.close_tab("TAB1")
        mock_requests.get.assert_called_once_with(
            "http://127.0.0.1:9222/json/close/TAB1", timeout=5
        )

    @patch("yt_transcript.extractor.requests")
    def test_close_tab_swallows_errors(self, mock_requests):
        mock_requests.get.side_effect = Exception("connection refused")
        # Should not raise
        self.ext.close_tab("TAB1")


class TestSendJs(unittest.TestCase):
    def setUp(self):
        self.ext = YouTubeTranscriptExtractor()

    def test_sends_and_receives(self):
        ws = MagicMock()
        ws.recv.return_value = json.dumps({
            "id": 1,
            "result": {"result": {"type": "string", "value": "hello"}}
        })

        result = self.ext.send_js(ws, "1+1", msg_id=1)
        self.assertEqual(result["id"], 1)

        # Verify the message sent
        sent = json.loads(ws.send.call_args[0][0])
        self.assertEqual(sent["id"], 1)
        self.assertEqual(sent["method"], "Runtime.evaluate")
        self.assertEqual(sent["params"]["expression"], "1+1")
        self.assertTrue(sent["params"]["returnByValue"])
        self.assertTrue(sent["params"]["awaitPromise"])

    def test_skips_non_matching_ids(self):
        ws = MagicMock()
        # First recv returns event (no id match), second returns our response
        ws.recv.side_effect = [
            json.dumps({"method": "Page.loadEventFired"}),
            json.dumps({"id": 5, "result": {"result": {"value": "ok"}}}),
        ]

        result = self.ext.send_js(ws, "code", msg_id=5)
        self.assertEqual(result["id"], 5)
        self.assertEqual(ws.recv.call_count, 2)


class TestGetMetadata(unittest.TestCase):
    def setUp(self):
        self.ext = YouTubeTranscriptExtractor()

    def test_parses_metadata(self):
        ws = MagicMock()
        ws.recv.return_value = json.dumps({
            "id": 2,
            "result": {"result": {"value": json.dumps({
                "title": "My Video",
                "channel": "My Channel",
                "language": "en",
            })}}
        })

        meta = self.ext._get_metadata(ws, msg_id=2)
        self.assertEqual(meta["title"], "My Video")
        self.assertEqual(meta["channel"], "My Channel")
        self.assertEqual(meta["language"], "en")

    def test_returns_empty_dict_on_bad_json(self):
        ws = MagicMock()
        ws.recv.return_value = json.dumps({
            "id": 2,
            "result": {"result": {"value": "not json{"}}
        })

        meta = self.ext._get_metadata(ws, msg_id=2)
        self.assertEqual(meta, {})

    def test_returns_empty_dict_when_no_value(self):
        ws = MagicMock()
        ws.recv.return_value = json.dumps({
            "id": 2,
            "result": {"result": {"type": "undefined"}}
        })

        meta = self.ext._get_metadata(ws, msg_id=2)
        self.assertEqual(meta, {})


class TestExtractFromDom(unittest.TestCase):
    def setUp(self):
        self.ext = YouTubeTranscriptExtractor()

    def test_returns_text(self):
        ws = MagicMock()
        ws.recv.return_value = json.dumps({
            "id": 10,
            "result": {"result": {"value": json.dumps({
                "text": "Hello this is the transcript"
            })}}
        })

        result = self.ext._extract_from_dom(ws, msg_id=10)
        self.assertEqual(result, "Hello this is the transcript")

    def test_returns_none_on_error(self):
        ws = MagicMock()
        ws.recv.return_value = json.dumps({
            "id": 10,
            "result": {"result": {"value": json.dumps({"error": "no_button"})}}
        })

        result = self.ext._extract_from_dom(ws, msg_id=10)
        self.assertIsNone(result)

    def test_returns_none_on_empty_text(self):
        ws = MagicMock()
        ws.recv.return_value = json.dumps({
            "id": 10,
            "result": {"result": {"value": json.dumps({"text": ""})}}
        })

        result = self.ext._extract_from_dom(ws, msg_id=10)
        self.assertIsNone(result)

    def test_returns_none_when_no_value(self):
        ws = MagicMock()
        ws.recv.return_value = json.dumps({
            "id": 10,
            "result": {"result": {"type": "undefined"}}
        })

        result = self.ext._extract_from_dom(ws, msg_id=10)
        self.assertIsNone(result)


class TestExtractFromApi(unittest.TestCase):
    def setUp(self):
        self.ext = YouTubeTranscriptExtractor()

    def test_returns_text(self):
        ws = MagicMock()
        ws.recv.return_value = json.dumps({
            "id": 20,
            "result": {"result": {"value": json.dumps({
                "text": "API transcript text here"
            })}}
        })

        result = self.ext._extract_from_api(ws, msg_id=20)
        self.assertEqual(result, "API transcript text here")

    def test_returns_none_on_error(self):
        ws = MagicMock()
        ws.recv.return_value = json.dumps({
            "id": 20,
            "result": {"result": {"value": json.dumps({"error": "fetch failed: 429"})}}
        })

        result = self.ext._extract_from_api(ws, msg_id=20)
        self.assertIsNone(result)

    def test_returns_none_on_empty_text(self):
        ws = MagicMock()
        ws.recv.return_value = json.dumps({
            "id": 20,
            "result": {"result": {"value": json.dumps({"text": ""})}}
        })

        result = self.ext._extract_from_api(ws, msg_id=20)
        self.assertIsNone(result)


class TestExtractTranscript(unittest.TestCase):
    """Integration tests for the full extract_transcript flow.

    All tests patch out Chrome lifecycle methods to avoid launching real
    Chrome processes and to keep tests fast and isolated.
    """

    def setUp(self):
        self.ext = YouTubeTranscriptExtractor(port=9222)
        # Common patches for Chrome lifecycle — no real Chrome during tests
        self._patches = [
            patch.object(self.ext, "_kill_existing_chrome"),
            patch.object(self.ext, "_launch_chrome"),
            patch.object(self.ext, "_wait_for_chrome"),
            patch.object(self.ext, "_shutdown_chrome"),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def test_invalid_url_returns_error(self):
        result = self.ext.extract_transcript("https://example.com/notyt")
        self.assertFalse(result["success"])
        self.assertIn("Could not parse video ID", result["error"])

    @patch("yt_transcript.extractor.time.sleep")
    @patch("yt_transcript.extractor.websocket.create_connection")
    @patch.object(YouTubeTranscriptExtractor, "close_tab")
    @patch.object(YouTubeTranscriptExtractor, "open_tab")
    def test_successful_dom_extraction(self, mock_open, mock_close, mock_ws_create, mock_sleep):
        mock_open.return_value = {
            "id": "TAB1",
            "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/TAB1",
        }

        mock_ws = MagicMock()
        mock_ws_create.return_value = mock_ws

        # Responses for: _wait_for_player_response, _get_metadata, _extract_from_dom
        mock_ws.recv.side_effect = [
            # _wait_for_player_response (msg_id=999)
            json.dumps({"id": 999, "result": {"result": {"value": "true"}}}),
            # _get_metadata (msg_id=2)
            json.dumps({"id": 2, "result": {"result": {"value": json.dumps({
                "title": "Test Video", "channel": "Test Channel", "language": "en"
            })}}}),
            # _extract_from_dom (msg_id=10)
            json.dumps({"id": 10, "result": {"result": {"value": json.dumps({
                "text": "This is the transcript text"
            })}}}),
        ]

        result = self.ext.extract_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        self.assertTrue(result["success"])
        self.assertEqual(result["video_id"], "dQw4w9WgXcQ")
        self.assertEqual(result["title"], "Test Video")
        self.assertEqual(result["channel"], "Test Channel")
        self.assertEqual(result["transcript"], "This is the transcript text")
        self.assertEqual(result["method"], "dom")
        self.assertEqual(result["language"], "en")
        mock_close.assert_called_once_with("TAB1")

    @patch("yt_transcript.extractor.time.sleep")
    @patch("yt_transcript.extractor.websocket.create_connection")
    @patch.object(YouTubeTranscriptExtractor, "close_tab")
    @patch.object(YouTubeTranscriptExtractor, "open_tab")
    def test_dom_fails_falls_back_to_api(self, mock_open, mock_close, mock_ws_create, mock_sleep):
        mock_open.return_value = {
            "id": "TAB1",
            "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/TAB1",
        }

        mock_ws = MagicMock()
        mock_ws_create.return_value = mock_ws

        mock_ws.recv.side_effect = [
            # _wait_for_player_response
            json.dumps({"id": 999, "result": {"result": {"value": "true"}}}),
            # _get_metadata
            json.dumps({"id": 2, "result": {"result": {"value": json.dumps({
                "title": "Test", "channel": "Ch", "language": "en"
            })}}}),
            # _extract_from_dom fails (no button)
            json.dumps({"id": 10, "result": {"result": {"value": json.dumps({
                "error": "no_button"
            })}}}),
            # _extract_from_api succeeds
            json.dumps({"id": 20, "result": {"result": {"value": json.dumps({
                "text": "API fallback transcript"
            })}}}),
        ]

        result = self.ext.extract_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "api")
        self.assertEqual(result["transcript"], "API fallback transcript")

    @patch("yt_transcript.extractor.time.sleep")
    @patch("yt_transcript.extractor.websocket.create_connection")
    @patch.object(YouTubeTranscriptExtractor, "close_tab")
    @patch.object(YouTubeTranscriptExtractor, "open_tab")
    def test_both_methods_fail(self, mock_open, mock_close, mock_ws_create, mock_sleep):
        mock_open.return_value = {
            "id": "TAB1",
            "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/TAB1",
        }

        mock_ws = MagicMock()
        mock_ws_create.return_value = mock_ws

        mock_ws.recv.side_effect = [
            # _wait_for_player_response
            json.dumps({"id": 999, "result": {"result": {"value": "true"}}}),
            # _get_metadata
            json.dumps({"id": 2, "result": {"result": {"value": json.dumps({
                "title": "No Captions", "channel": "Ch", "language": ""
            })}}}),
            # _extract_from_dom fails
            json.dumps({"id": 10, "result": {"result": {"value": json.dumps({
                "error": "no_button"
            })}}}),
            # _extract_from_api fails
            json.dumps({"id": 20, "result": {"result": {"value": json.dumps({
                "error": "no tracks"
            })}}}),
        ]

        result = self.ext.extract_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        self.assertFalse(result["success"])
        self.assertIn("No transcript found", result["error"])
        self.assertEqual(result["title"], "No Captions")

    def test_chrome_launch_failure(self):
        """When _wait_for_chrome raises, extract_transcript returns an error."""
        self.ext._wait_for_chrome.side_effect = RuntimeError(
            "Chrome did not start within 15s on port 9222"
        )

        result = self.ext.extract_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        self.assertFalse(result["success"])
        self.assertIn("Chrome did not start", result["error"])

    @patch("yt_transcript.extractor.time.sleep")
    @patch("yt_transcript.extractor.websocket.create_connection")
    @patch.object(YouTubeTranscriptExtractor, "close_tab")
    @patch.object(YouTubeTranscriptExtractor, "open_tab")
    def test_cleanup_on_exception(self, mock_open, mock_close, mock_ws_create, mock_sleep):
        mock_open.return_value = {
            "id": "TAB1",
            "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/TAB1",
        }

        mock_ws = MagicMock()
        mock_ws_create.return_value = mock_ws
        mock_ws.recv.side_effect = Exception("unexpected error")

        result = self.ext.extract_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        self.assertFalse(result["success"])
        mock_ws.close.assert_called_once()
        mock_close.assert_called_once_with("TAB1")
        self.ext._shutdown_chrome.assert_called()

    @patch("yt_transcript.extractor.time.sleep")
    @patch("yt_transcript.extractor.websocket.create_connection")
    @patch.object(YouTubeTranscriptExtractor, "close_tab")
    @patch.object(YouTubeTranscriptExtractor, "open_tab")
    def test_uses_canonical_url(self, mock_open, mock_close, mock_ws_create, mock_sleep):
        mock_open.return_value = {
            "id": "TAB1",
            "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/TAB1",
        }
        mock_ws = MagicMock()
        mock_ws_create.return_value = mock_ws
        mock_ws.recv.side_effect = [
            json.dumps({"id": 999, "result": {"result": {"value": "true"}}}),
            json.dumps({"id": 2, "result": {"result": {"value": "{}"}}}),
            json.dumps({"id": 10, "result": {"result": {"value": json.dumps({"text": "t"})}}}),
        ]

        self.ext.extract_transcript("https://youtu.be/dQw4w9WgXcQ")

        mock_open.assert_called_once_with("https://www.youtube.com/watch?v=dQw4w9WgXcQ")


class TestWaitForPlayerResponse(unittest.TestCase):
    def setUp(self):
        self.ext = YouTubeTranscriptExtractor()

    @patch("yt_transcript.extractor.time.sleep")
    @patch("yt_transcript.extractor.time.time")
    def test_returns_immediately_when_ready(self, mock_time, mock_sleep):
        mock_time.side_effect = [0] * 10  # _wait loop + send_js deadline/remaining
        ws = MagicMock()
        ws.recv.return_value = json.dumps({
            "id": 999, "result": {"result": {"value": "true"}}
        })

        self.ext._wait_for_player_response(ws, max_wait=15)
        # Should have sent exactly one JS evaluation
        ws.send.assert_called_once()

    @patch("yt_transcript.extractor.time.sleep")
    @patch("yt_transcript.extractor.time.time")
    def test_polls_until_ready(self, mock_time, mock_sleep):
        # Provide enough time() values for multiple send_js calls
        # (each call uses time() for deadline, remaining check, and loop check)
        mock_time.side_effect = [0] * 5 + [1] * 5 + [2] * 5 + [3] * 5
        ws = MagicMock()
        ws.recv.side_effect = [
            json.dumps({"id": 999, "result": {"result": {"value": "false"}}}),
            json.dumps({"id": 999, "result": {"result": {"value": "false"}}}),
            json.dumps({"id": 999, "result": {"result": {"value": "true"}}}),
        ]

        self.ext._wait_for_player_response(ws, max_wait=15)
        self.assertEqual(ws.send.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("yt_transcript.extractor.time.sleep")
    @patch("yt_transcript.extractor.time.time")
    def test_raises_on_timeout(self, mock_time, mock_sleep):
        # Provide enough time() values for the _wait loop + send_js inner loops.
        # After one poll iteration, jump past the deadline.
        mock_time.side_effect = [0] * 10 + [20] * 10
        ws = MagicMock()
        ws.recv.return_value = json.dumps({
            "id": 999, "result": {"result": {"value": "false"}}
        })

        with self.assertRaises(TimeoutError) as ctx:
            self.ext._wait_for_player_response(ws, max_wait=15)
        self.assertIn("ytInitialPlayerResponse", str(ctx.exception))


class TestMainCli(unittest.TestCase):
    @patch("yt_transcript.cli.YouTubeTranscriptExtractor")
    @patch("sys.argv", ["prog", "https://www.youtube.com/watch?v=abc", "--json"])
    def test_json_output(self, MockExtractor):
        instance = MockExtractor.return_value
        instance.extract_transcript.return_value = {
            "success": True, "video_id": "abc", "title": "T",
            "channel": "C", "url": "u", "transcript": "text",
            "language": "en", "method": "dom", "error": "",
        }

        from yt_transcript.cli import main

        captured = StringIO()
        with redirect_stdout(captured):
            main()

        output = json.loads(captured.getvalue())
        self.assertTrue(output["success"])
        self.assertEqual(output["transcript"], "text")

    @patch("yt_transcript.cli.YouTubeTranscriptExtractor")
    @patch("sys.argv", ["prog", "https://www.youtube.com/watch?v=abc"])
    def test_text_output(self, MockExtractor):
        instance = MockExtractor.return_value
        instance.extract_transcript.return_value = {
            "success": True, "video_id": "abc", "title": "My Title",
            "channel": "My Channel", "url": "u", "transcript": "hello world",
            "language": "en", "method": "dom", "error": "",
        }

        from yt_transcript.cli import main

        captured = StringIO()
        with redirect_stdout(captured):
            main()

        output = captured.getvalue()
        self.assertIn("Title: My Title", output)
        self.assertIn("Channel: My Channel", output)
        self.assertIn("hello world", output)

    @patch("sys.argv", ["prog"])
    def test_no_args_exits(self):
        from yt_transcript.cli import main
        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertIn(ctx.exception.code, (1, 2))

    @patch("yt_transcript.cli.YouTubeTranscriptExtractor")
    @patch("sys.argv", ["prog", "https://www.youtube.com/watch?v=abc", "--port", "9333"])
    def test_custom_port(self, MockExtractor):
        instance = MockExtractor.return_value
        instance.extract_transcript.return_value = {
            "success": True, "video_id": "abc", "title": "",
            "channel": "", "url": "u", "transcript": "t",
            "language": "", "method": "dom", "error": "",
        }

        from yt_transcript.cli import main

        captured = StringIO()
        with redirect_stdout(captured):
            main()

        MockExtractor.assert_called_with(port=9333)


class TestFindChrome(unittest.TestCase):
    def setUp(self):
        self.ext = YouTubeTranscriptExtractor()

    @patch("shutil.which", return_value=None)
    @patch("os.path.isfile", return_value=False)
    def test_returns_none_when_not_found(self, mock_isfile, mock_which):
        self.assertIsNone(self.ext._find_chrome())

    @patch("os.path.isfile")
    def test_returns_absolute_path_when_exists(self, mock_isfile):
        mock_isfile.side_effect = lambda p: p == self.ext.CHROME_PATHS[0]
        result = self.ext._find_chrome()
        self.assertEqual(result, self.ext.CHROME_PATHS[0])

    @patch("shutil.which")
    @patch("os.path.isfile", return_value=False)
    def test_uses_which_fallback(self, mock_isfile, mock_which):
        mock_which.side_effect = lambda p: "/usr/bin/chromium" if p == "chromium" else None
        result = self.ext._find_chrome()
        self.assertEqual(result, "/usr/bin/chromium")


class TestKillExistingChrome(unittest.TestCase):
    def setUp(self):
        self.ext = YouTubeTranscriptExtractor()

    @patch("os.remove")
    @patch("yt_transcript.extractor.time.sleep")
    @patch("yt_transcript.extractor.subprocess.run")
    def test_calls_process_kill(self, mock_run, mock_sleep, mock_remove):
        self.ext._kill_existing_chrome()
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        # Should use platform-appropriate command with the user data dir
        cmd_str = " ".join(args)
        self.assertIn(self.ext._user_data_dir, cmd_str)

    @patch("os.remove")
    @patch("yt_transcript.extractor.time.sleep")
    @patch("yt_transcript.extractor.subprocess.run", side_effect=Exception("fail"))
    def test_swallows_pkill_errors(self, mock_run, mock_sleep, mock_remove):
        # Should not raise
        self.ext._kill_existing_chrome()

    @patch("yt_transcript.extractor.time.sleep")
    @patch("yt_transcript.extractor.subprocess.run")
    def test_removes_singleton_files(self, mock_run, mock_sleep):
        removed = []
        original_remove = os.remove
        def fake_remove(path):
            removed.append(os.path.basename(path))
        with patch("os.remove", side_effect=fake_remove):
            self.ext._kill_existing_chrome()
        self.assertIn("SingletonLock", removed)
        self.assertIn("SingletonSocket", removed)
        self.assertIn("SingletonCookie", removed)


class TestLaunchChrome(unittest.TestCase):
    def setUp(self):
        self.ext = YouTubeTranscriptExtractor()

    @patch("yt_transcript.extractor.subprocess.Popen")
    @patch("os.makedirs")
    @patch.object(YouTubeTranscriptExtractor, "_find_chrome", return_value="/usr/bin/chrome")
    def test_launches_with_correct_flags(self, mock_find, mock_makedirs, mock_popen):
        self.ext._launch_chrome()
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        self.assertEqual(cmd[0], "/usr/bin/chrome")
        flags = " ".join(cmd[1:])
        self.assertIn("--remote-debugging-port=9222", flags)
        self.assertIn("--no-first-run", flags)
        self.assertIn("--remote-allow-origins=*", flags)
        self.assertIsNotNone(self.ext._chrome_process)

    @patch.object(YouTubeTranscriptExtractor, "_find_chrome", return_value=None)
    def test_raises_when_chrome_not_found(self, mock_find):
        with self.assertRaises(RuntimeError) as ctx:
            self.ext._launch_chrome()
        self.assertIn("Chrome not found", str(ctx.exception))


class TestWaitForChrome(unittest.TestCase):
    def setUp(self):
        self.ext = YouTubeTranscriptExtractor()

    @patch("yt_transcript.extractor.time.sleep")
    @patch("yt_transcript.extractor.time.time")
    @patch("yt_transcript.extractor.requests.get")
    def test_returns_when_cdp_responds(self, mock_get, mock_time, mock_sleep):
        mock_time.side_effect = [0, 0]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        self.ext._wait_for_chrome(timeout=15)
        mock_get.assert_called_once()

    @patch("yt_transcript.extractor.time.sleep")
    @patch("yt_transcript.extractor.time.time")
    @patch("yt_transcript.extractor.requests.get")
    def test_raises_on_timeout(self, mock_get, mock_time, mock_sleep):
        # time() calls: start, check1 (past deadline)
        mock_time.side_effect = [0, 20]
        mock_get.side_effect = requests.ConnectionError("refused")

        with self.assertRaises(RuntimeError) as ctx:
            self.ext._wait_for_chrome(timeout=15)
        self.assertIn("Chrome did not start", str(ctx.exception))

    @patch("yt_transcript.extractor.time.sleep")
    @patch("yt_transcript.extractor.time.time")
    @patch("yt_transcript.extractor.requests.get")
    def test_retries_on_connection_error(self, mock_get, mock_time, mock_sleep):
        import requests as real_requests
        mock_time.side_effect = [0, 1, 2, 3]
        mock_resp_ok = MagicMock()
        mock_resp_ok.status_code = 200
        mock_get.side_effect = [
            real_requests.ConnectionError("refused"),
            real_requests.ConnectionError("refused"),
            mock_resp_ok,
        ]

        self.ext._wait_for_chrome(timeout=15)
        self.assertEqual(mock_get.call_count, 3)


class TestShutdownChrome(unittest.TestCase):
    def setUp(self):
        self.ext = YouTubeTranscriptExtractor()

    def test_noop_when_no_process(self):
        self.ext._chrome_process = None
        self.ext._shutdown_chrome()  # Should not raise

    def test_terminates_process(self):
        proc = MagicMock()
        self.ext._chrome_process = proc

        self.ext._shutdown_chrome()

        proc.terminate.assert_called_once()
        proc.wait.assert_called()
        self.assertIsNone(self.ext._chrome_process)

    def test_kills_on_timeout(self):
        proc = MagicMock()
        proc.wait.side_effect = [subprocess.TimeoutExpired("chrome", 5), None]
        self.ext._chrome_process = proc

        self.ext._shutdown_chrome()

        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()
        self.assertIsNone(self.ext._chrome_process)


class TestMainCliStdin(unittest.TestCase):
    @patch("yt_transcript.cli.YouTubeTranscriptExtractor")
    @patch("sys.argv", ["prog", "--stdin", "--json"])
    @patch("sys.stdin")
    def test_stdin_mode(self, mock_stdin, MockExtractor):
        mock_stdin.readline.return_value = "https://www.youtube.com/watch?v=abc\n"
        instance = MockExtractor.return_value
        instance.extract_transcript.return_value = {
            "success": True, "video_id": "abc", "title": "",
            "channel": "", "url": "u", "transcript": "stdin text",
            "language": "", "method": "dom", "error": "",
        }

        from yt_transcript.cli import main

        captured = StringIO()
        with redirect_stdout(captured):
            main()

        output = json.loads(captured.getvalue())
        self.assertEqual(output["transcript"], "stdin text")
        instance.extract_transcript.assert_called_once_with(
            "https://www.youtube.com/watch?v=abc"
        )

    @patch("yt_transcript.cli.YouTubeTranscriptExtractor")
    @patch("sys.argv", ["prog", "https://www.youtube.com/watch?v=abc"])
    def test_error_output_exits_1(self, MockExtractor):
        instance = MockExtractor.return_value
        instance.extract_transcript.return_value = {
            "success": False, "video_id": "abc", "title": "",
            "channel": "", "url": "u", "transcript": "",
            "language": "", "method": "", "error": "No captions",
        }

        from yt_transcript.cli import main

        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, 1)


class TestSanitizeFilename(unittest.TestCase):
    def setUp(self):
        from yt_transcript.cli import _sanitize_filename
        self.sanitize = _sanitize_filename

    def test_removes_path_separators(self):
        self.assertNotIn("/", self.sanitize("a/b\\c"))
        self.assertNotIn("\\", self.sanitize("a/b\\c"))

    def test_removes_special_chars(self):
        result = self.sanitize('file:name*"test"<>|')
        for ch in ':*"<>|':
            self.assertNotIn(ch, result)

    def test_collapses_whitespace(self):
        self.assertEqual(self.sanitize("  a   b  "), "a b")

    def test_empty_string_returns_untitled(self):
        self.assertEqual(self.sanitize(""), "untitled")

    def test_all_special_chars_become_underscores(self):
        result = self.sanitize('/:*?"<>|')
        self.assertTrue(all(c == "_" for c in result.replace(" ", "")))

    def test_normal_string_unchanged(self):
        self.assertEqual(self.sanitize("My Video Title"), "My Video Title")

    def test_unicode_preserved(self):
        self.assertEqual(self.sanitize("日本語タイトル"), "日本語タイトル")


class TestSaveTranscript(unittest.TestCase):
    def setUp(self):
        from yt_transcript.cli import _save_transcript
        self.save = _save_transcript

    def test_saves_file_with_correct_content(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            result = {
                "channel": "TestChannel",
                "title": "TestTitle",
                "video_id": "abc123",
                "transcript": "Hello world transcript",
            }
            path = self.save(result, tmpdir)
            self.assertTrue(os.path.isfile(path))
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), "Hello world transcript")

    def test_filename_format(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            result = {
                "channel": "MyChannel",
                "title": "MyTitle",
                "video_id": "xyz789",
                "transcript": "text",
            }
            path = self.save(result, tmpdir)
            filename = os.path.basename(path)
            self.assertEqual(filename, "MyChannel - MyTitle [xyz789].txt")

    def test_missing_fields_use_defaults(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            result = {"transcript": "text"}
            path = self.save(result, tmpdir)
            filename = os.path.basename(path)
            self.assertEqual(filename, "unknown-channel - untitled [video].txt")

    def test_creates_output_dir(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "a", "b", "c")
            result = {
                "channel": "Ch",
                "title": "T",
                "video_id": "id",
                "transcript": "t",
            }
            path = self.save(result, nested)
            self.assertTrue(os.path.isfile(path))


if __name__ == "__main__":
    unittest.main()
