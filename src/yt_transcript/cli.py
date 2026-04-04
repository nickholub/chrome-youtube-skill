"""Command-line interface for yt-transcript."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from . import __version__
from .extractor import YouTubeTranscriptExtractor


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
    date_prefix = (result.get("publish_date") or "")[:10]  # take yyyy-mm-dd from ISO string
    filename = f"{date_prefix} - {channel} - {title}.txt" if date_prefix else f"{channel} - {title}.txt"
    path = os.path.join(output_dir, filename)

    header_lines = []
    if result.get("title"):
        header_lines.append(f"Title: {result['title']}")
    if result.get("channel"):
        header_lines.append(f"Channel: {result['channel']}")
    if result.get("url"):
        header_lines.append(f"URL: {result['url']}")
    if result.get("view_count"):
        try:
            header_lines.append(f"Views: {int(result['view_count']):,}")
        except (ValueError, TypeError):
            header_lines.append(f"Views: {result['view_count']}")
    if result.get("publish_date"):
        header_lines.append(f"Published: {result['publish_date']}")
    if result.get("duration_seconds"):
        try:
            total = int(result["duration_seconds"])
            h, rem = divmod(total, 3600)
            m, s = divmod(rem, 60)
            dur = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
            header_lines.append(f"Duration: {dur}")
        except (ValueError, TypeError):
            header_lines.append(f"Duration: {result['duration_seconds']}s")

    with open(path, "w", encoding="utf-8") as f:
        if header_lines:
            f.write("\n".join(header_lines))
            f.write("\n" + "=" * 60 + "\n\n")
        f.write(result.get("transcript", ""))
    return path


def _run_single(args: argparse.Namespace) -> None:
    url = args.url
    if args.stdin:
        url = sys.stdin.readline().strip()

    if not url:
        print("error: No URL provided. Pass a URL or use --stdin.", file=sys.stderr)
        sys.exit(2)

    extractor = YouTubeTranscriptExtractor(port=args.port, reuse=not args.no_reuse)
    result = extractor.extract_transcript(url)

    if result.get("success") and args.output_dir and not args.no_save:
        result["output_file"] = _save_transcript(result, os.path.expanduser(args.output_dir))

    if args.json_out:
        json_path = os.path.expanduser(args.json_out)
        json_dir = os.path.dirname(json_path)
        if json_dir:
            os.makedirs(json_dir, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
            f.write("\n")

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


def _run_batch(args: argparse.Namespace) -> None:
    output_dir = os.path.expanduser(args.output_dir)
    extractor = YouTubeTranscriptExtractor(port=args.port, reuse=not args.no_reuse)

    print(f"Fetching up to {args.count} video(s) from: {args.channel_url}")
    results = extractor.batch_extract(args.channel_url, args.count)

    if not results:
        print("No videos were processed.", file=sys.stderr)
        sys.exit(1)

    saved = 0
    failed = 0
    for result in results:
        if result.get("success"):
            path = _save_transcript(result, output_dir)
            print(f"  Saved: {path}")
            saved += 1
        else:
            title = result.get("title") or result.get("url") or "unknown"
            print(f"  Failed ({title}): {result.get('error', 'unknown error')}", file=sys.stderr)
            failed += 1

    print(f"\nDone: {saved} saved, {failed} failed.")
    if failed and saved == 0:
        sys.exit(1)


def main() -> None:
    # Inject 'extract' subcommand when the caller uses the legacy flat interface
    # (i.e. no explicit subcommand like 'extract' or 'batch' is present).
    _subcommands = {"extract", "batch"}
    _first_positional = next(
        (a for a in sys.argv[1:] if not a.startswith("-")), None
    )
    if _first_positional not in _subcommands:
        sys.argv.insert(1, "extract")

    parser = argparse.ArgumentParser(
        description="Extract YouTube video transcripts via Chrome DevTools Protocol.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    # ── single video ─────────────────────────────────────────────
    single = subparsers.add_parser("extract", help="Extract transcript from a single video URL.")
    single.add_argument("url", nargs="?", default=None, help="YouTube video URL")
    single.add_argument("--json", action="store_true", dest="output_json", help="output as JSON")
    single.add_argument(
        "--json-out",
        default=None,
        help="write JSON result to path (directories created as needed)",
    )
    single.add_argument("--port", type=int, default=9222, help="Chrome CDP port (default: 9222)")
    single.add_argument("--stdin", action="store_true", help="read URL from stdin")
    single.add_argument("--output-dir", default=None, help="transcript output directory (enables saving)")
    single.add_argument("--no-save", action="store_true", help="skip saving transcript to disk")
    single.add_argument("--no-reuse", action="store_true", help="always launch a fresh Chrome instance")
    single.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")

    # ── batch channel export ─────────────────────────────────────
    batch = subparsers.add_parser(
        "batch",
        help="Extract transcripts from the N latest videos on a YouTube channel.",
    )
    batch.add_argument(
        "channel_url",
        help="YouTube channel URL (e.g. https://www.youtube.com/@handle/videos)",
    )
    batch.add_argument(
        "--count", "-n",
        type=int, default=10,
        help="number of latest videos to export (default: 10)",
    )
    batch.add_argument(
        "--output-dir", "-o",
        required=True,
        help="directory to write transcript files into",
    )
    batch.add_argument("--port", type=int, default=9222, help="Chrome CDP port (default: 9222)")
    batch.add_argument("--no-reuse", action="store_true", help="always launch a fresh Chrome instance")
    batch.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")

    args = parser.parse_args()

    logging.basicConfig(
        format="%(levelname)s: %(message)s",
        level=logging.DEBUG if args.verbose else logging.WARNING,
    )

    if args.command == "batch":
        _run_batch(args)
    else:
        _run_single(args)
