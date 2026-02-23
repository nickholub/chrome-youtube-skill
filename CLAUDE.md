# YouTube Transcript Extractor

## Project Structure

```
extract_transcript.py   # Main Python script - CDP connection + transcript extraction
extract                 # Bash wrapper for CLI invocation
SKILL.md                # OpenClaw skill manifest
CLAUDE.md               # This file
```

## Architecture

Connects to Chrome via CDP (Chrome DevTools Protocol) on `--remote-debugging-port` (default 9222).

**Extraction flow:**
1. `GET /json/new?{url}` — opens a new Chrome tab, returns target info with WebSocket URL
2. WebSocket → `Runtime.evaluate` — injects JS to read `window.ytInitialPlayerResponse`
3. Extracts caption track URLs from `captions.playerCaptionsTracklistRenderer.captionTracks`
4. Fetches caption track with `&fmt=json3` via Python requests
5. Parses `events[].segs[].utf8` → joins into plain text
6. `GET /json/close/{targetId}` — closes the tab

**Key design decisions:**
- Uses `ytInitialPlayerResponse` (YouTube's player data) rather than DOM scraping — more reliable
- Caption fetch happens in Python (not in-browser) to avoid CORS issues
- Retries caption extraction 3 times with delay to handle slow page loads
- Prefers English captions, falls back to first available track

## Dependencies

- Python 3 stdlib (`json`, `sys`, `time`, `urllib.parse`)
- `requests` — HTTP calls to CDP endpoints and caption track URLs
- `websocket-client` — WebSocket connection for `Runtime.evaluate`

## Testing

```bash
# 1. Ensure Chrome is running with debugging port
open -a "Google Chrome" --args --remote-debugging-port=9222

# 2. Test with a known video
python3 extract_transcript.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# 3. Test JSON output
python3 extract_transcript.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --json

# 4. Test error case (no captions)
python3 extract_transcript.py "https://www.youtube.com/watch?v=INVALID_ID"
```

## Ported From

Caption extraction logic adapted from `ChromeAIHighlights/src/contentScript.js` (lines 337-501), specifically:
- `getPlayerResponseFromPage()` → JS injection via `Runtime.evaluate`
- `fetchTranscriptFromTrack()` → `_fetch_transcript()` in Python
- `getCaptionTracksWithRetry()` → retry loop in `extract_transcript()`
