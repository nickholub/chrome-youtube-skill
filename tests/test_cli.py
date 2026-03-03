#!/usr/bin/env python3
"""Unit tests for yt_transcript.cli."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch

import yt_transcript.cli as cli


class TestCliJsonOut(unittest.TestCase):
    def test_json_out_writes_file_and_stdout_json(self):
        fake_result = {
            "success": True,
            "video_id": "abc123XYZ_-",
            "title": "Video Title",
            "channel": "Channel Name",
            "url": "https://www.youtube.com/watch?v=abc123XYZ_-",
            "transcript": "hello world",
            "language": "en",
            "method": "dom",
            "error": "",
        }

        with tempfile.TemporaryDirectory() as tmp:
            json_path = os.path.join(tmp, "nested", "result.json")
            stdout = StringIO()

            with (
                patch("yt_transcript.cli.YouTubeTranscriptExtractor") as mock_extractor,
                redirect_stdout(stdout),
                patch.object(
                    sys,
                    "argv",
                    [
                        "yt-transcript",
                        fake_result["url"],
                        "--json",
                        "--json-out",
                        json_path,
                    ],
                ),
            ):
                mock_extractor.return_value.extract_transcript.return_value = fake_result
                cli.main()

            self.assertTrue(os.path.isfile(json_path))
            with open(json_path, "r", encoding="utf-8") as f:
                written = json.load(f)
            self.assertEqual(written["video_id"], fake_result["video_id"])

            printed = json.loads(stdout.getvalue())
            self.assertEqual(printed["video_id"], fake_result["video_id"])

    def test_json_out_writes_file_on_error_before_exit(self):
        fake_result = {
            "success": False,
            "video_id": "",
            "title": "",
            "channel": "",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "transcript": "",
            "language": "",
            "method": "",
            "error": "boom",
        }

        with tempfile.TemporaryDirectory() as tmp:
            json_path = os.path.join(tmp, "nested", "result.json")
            stderr = StringIO()

            with (
                patch("yt_transcript.cli.YouTubeTranscriptExtractor") as mock_extractor,
                redirect_stderr(stderr),
                patch.object(
                    sys,
                    "argv",
                    [
                        "yt-transcript",
                        fake_result["url"],
                        "--json-out",
                        json_path,
                    ],
                ),
            ):
                mock_extractor.return_value.extract_transcript.return_value = fake_result
                with self.assertRaises(SystemExit) as cm:
                    cli.main()

            self.assertEqual(cm.exception.code, 1)
            self.assertTrue(os.path.isfile(json_path))
            with open(json_path, "r", encoding="utf-8") as f:
                written = json.load(f)
            self.assertFalse(written["success"])
            self.assertEqual(written["error"], "boom")


if __name__ == "__main__":
    unittest.main()
