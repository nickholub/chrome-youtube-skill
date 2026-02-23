# YouTube Transcript Extractor

## Project Structure

```
extract_transcript.py   # Main Python script - CDP connection + transcript extraction
extract                 # Bash wrapper for CLI invocation
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

- Python 3 stdlib (`json`, `sys`, `time`, `urllib.parse`)
- `requests` — HTTP calls to CDP endpoints (open/close tab)
- `websocket-client` — WebSocket to tab for `Runtime.evaluate`

## Chrome Management

The script automatically launches and shuts down its own Chrome instance with `--remote-debugging-port`. Any existing debug Chrome using the same profile (`~/.chrome-debug-profile`) is killed first to avoid conflicts. No manual Chrome launch is needed.

## Testing

```bash
# Extract transcript (plain text)
python3 extract_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"

# JSON output
python3 extract_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID" --json

# Via wrapper
./extract "https://www.youtube.com/watch?v=VIDEO_ID"
```

## Ported From

DOM extraction logic from `ChromeAIHighlights/src/contentScript.js`:
- `extractTranscriptFromDOM()` (lines 245-313) → `_extract_from_dom()`
- `waitForElement()` (lines 223-243) → inline `waitForEl()` in JS
- `fetchTranscriptFromTrack()` (lines 448-473) → `_extract_from_api()` fallback
