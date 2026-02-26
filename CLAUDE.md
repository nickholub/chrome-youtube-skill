# YouTube Transcript Extractor

## Project Structure

```
src/yt_transcript/
    __init__.py         # Package exports: YouTubeTranscriptExtractor, __version__
    extractor.py        # CDP connection + transcript extraction
    cli.py              # CLI entry point, file saving
    __main__.py         # python -m yt_transcript support
    js/                 # JavaScript snippets executed in Chrome via CDP
        get_metadata.js     # Extract title, channel, language from ytInitialPlayerResponse
        extract_dom.js      # Click "Show transcript" and scrape DOM
        extract_api.js      # Fallback: fetch caption track URL via in-page fetch
tests/
    __init__.py
    test_extractor.py   # Unit tests
extract                 # Bash wrapper for CLI invocation
pyproject.toml          # PEP 621 packaging metadata and dependencies
SKILL.md                # OpenClaw skill manifest
CLAUDE.md               # This file
```

## Architecture

Connects to a visible Chrome instance via CDP (Chrome DevTools Protocol) on `--remote-debugging-port` (default 9222). Mimics normal user behavior by clicking "Show transcript" and reading the DOM.

**Extraction flow:**
1. `PUT /json/new?{url}` — opens a new visible Chrome tab
2. Wait for page to load, poll for `ytInitialPlayerResponse`
3. Connect WebSocket to tab, extract video metadata
4. **DOM method (primary):** Click "Show transcript" button → wait for `#segments-container` → extract text from `yt-formatted-string.segment-text` elements
5. **API method (fallback):** Fetch caption track URL via in-browser `fetch()` with credentials
6. `GET /json/close/{targetId}` — closes the tab

**Key design decisions:**
- DOM extraction first (same as ChromeAIHighlights) — most reliable, no API calls
- All network requests happen inside the browser tab with credentials — avoids 429 rate limiting
- WebSocket connects after initial page load (navigation resets WS connections)
- Chrome 145+ requires PUT for `/json/new`, falls back to GET for older versions

## Dependencies

Defined in `pyproject.toml`. Install with `pip install .` or `pip install -e .` for development.

- Python 3.10+ stdlib (`json`, `sys`, `time`, `argparse`, `logging`, `urllib.parse`)
- `requests>=2.20,<3` — HTTP calls to CDP endpoints (open/close tab)
- `websocket-client>=1.0,<2` — WebSocket to tab for `Runtime.evaluate`

## Chrome Management

The script automatically launches and shuts down its own Chrome instance with `--remote-debugging-port`. Any existing debug Chrome using the same profile (`~/.chrome-debug-profile`) is killed first to avoid conflicts. No manual Chrome launch is needed.

## Testing

```bash
# Run tests
PYTHONPATH=src python3 -m pytest tests/ -v

# Extract transcript (plain text)
PYTHONPATH=src python3 -m yt_transcript "https://www.youtube.com/watch?v=VIDEO_ID"

# JSON output
PYTHONPATH=src python3 -m yt_transcript "https://www.youtube.com/watch?v=VIDEO_ID" --json

# Verbose/debug logging
PYTHONPATH=src python3 -m yt_transcript "https://www.youtube.com/watch?v=VIDEO_ID" -v

# Via wrapper
./extract "https://www.youtube.com/watch?v=VIDEO_ID"

# Via installed entry point (after pip install .)
yt-transcript "https://www.youtube.com/watch?v=VIDEO_ID"
```

## Ported From

DOM extraction logic from `ChromeAIHighlights/src/contentScript.js`:
- `extractTranscriptFromDOM()` (lines 245-313) → `_extract_from_dom()`
- `waitForElement()` (lines 223-243) → inline `waitForEl()` in JS
- `fetchTranscriptFromTrack()` (lines 448-473) → `_extract_from_api()` fallback
