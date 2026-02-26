#!/usr/bin/env python3
"""Run yt_transcript from this repository without installation."""

from pathlib import Path
import sys

SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from yt_transcript.cli import main  # noqa: E402


if __name__ == "__main__":
    main()
