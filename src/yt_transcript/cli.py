"""Command-line interface for yt-transcript."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from .extractor import YouTubeTranscriptExtractor, __version__


def _sanitize_filename(value: str) -> str:
    """Sanitize filename for cross-platform safety."""
    if not value:
        return "untitled"
    for ch in '/\\:*?"<>|':
        value = value.replace(ch, "_")
    return " ".join(value.split()).strip() or "untitled"


def _save_transcript(result: dict, output_dir: str) -> str:
    """Save successful transcript to disk and return file path."""
    os.makedirs(output_dir, exist_ok=True)
    channel = _sanitize_filename(result.get("channel") or "unknown-channel")
    title = _sanitize_filename(result.get("title") or "untitled")
    video_id = _sanitize_filename(result.get("video_id") or "video")
    filename = f"{channel} - {title} [{video_id}].txt"
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(result.get("transcript", ""))
    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract YouTube video transcripts via Chrome DevTools Protocol.",
    )
    parser.add_argument("url", nargs="?", default=None, help="YouTube video URL")
    parser.add_argument("--json", action="store_true", dest="output_json", help="output as JSON")
    parser.add_argument("--port", type=int, default=9222, help="Chrome CDP port (default: 9222)")
    parser.add_argument("--stdin", action="store_true", help="read URL from stdin")
    parser.add_argument("--output-dir", default=None, help="transcript output directory (enables saving)")
    parser.add_argument("--no-save", action="store_true", help="skip saving transcript to disk")
    parser.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    args = parser.parse_args()

    logging.basicConfig(
        format="%(levelname)s: %(message)s",
        level=logging.DEBUG if args.verbose else logging.WARNING,
    )

    url = args.url
    if args.stdin:
        url = sys.stdin.readline().strip()

    if not url:
        parser.error("No URL provided. Pass a URL or use --stdin.")

    extractor = YouTubeTranscriptExtractor(port=args.port)
    result = extractor.extract_transcript(url)

    if result.get("success") and args.output_dir and not args.no_save:
        result["output_file"] = _save_transcript(result, os.path.expanduser(args.output_dir))

    if args.output_json:
        print(json.dumps(result, indent=2))
    else:
        if result["success"]:
            if result["title"]:
                print(f"Title: {result['title']}")
            if result["channel"]:
                print(f"Channel: {result['channel']}")
            if result["title"] or result["channel"]:
                print("=" * 50)
            print(result["transcript"])
            if result.get("output_file"):
                print("=" * 50)
                print(f"Saved: {result['output_file']}")
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
