# YouTube Transcript Extractor

Extract YouTube video transcripts by connecting to a running Chrome instance via the Chrome DevTools Protocol (CDP). Injects JavaScript to read YouTube's internal player data (`ytInitialPlayerResponse`), fetches caption tracks, and returns clean plain text.

## How It Works

```
┌──────────┐    CDP HTTP     ┌─────────────┐   WebSocket    ┌──────────────┐
│  Script   │ ──────────────→│ Chrome :9222 │ ←────────────→ │ YouTube Tab  │
│ (Python)  │  open/close    │              │  Runtime.eval  │              │
└──────────┘    tab          └─────────────┘                └──────────────┘
      │                                                            │
      │  1. Open new tab with video URL                            │
      │  2. Wait for page load                                     │
      │  3. Inject JS → read ytInitialPlayerResponse               │
      │  4. Get caption track URLs back              ◄─────────────┘
      │  5. Fetch caption track (&fmt=json3) directly via HTTP
      │  6. Parse events[].segs[].utf8 → join into text
      │  7. Close tab
      ▼
   Transcript text
```

The key insight is that YouTube embeds all caption metadata in `window.ytInitialPlayerResponse` when a page loads. Instead of scraping the DOM or using unofficial APIs, we read this object directly from the page context, then fetch the actual caption data server-side in Python.

## Setup

**1. Install Python dependencies:**

```bash
pip3 install requests websocket-client
```

**2. Start Chrome with remote debugging enabled:**

```bash
# macOS
open -a "Google Chrome" --args --remote-debugging-port=9222

# Linux
google-chrome --remote-debugging-port=9222

# Or if Chrome is already running, restart it with the flag
```

## Usage

```bash
# Plain text output
./extract "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# JSON output
./extract "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --json

# From stdin
echo "https://youtu.be/dQw4w9WgXcQ" | ./extract --stdin

# Custom CDP port
./extract "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --port 9333
```

### Output

**Plain text (default):**
```
Title: Video Title
Channel: Channel Name
==================================================
This is the full transcript text extracted from the video captions...
```

**JSON (`--json`):**
```json
{
  "success": true,
  "video_id": "dQw4w9WgXcQ",
  "title": "Video Title",
  "channel": "Channel Name",
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "transcript": "This is the full transcript text...",
  "language": "en",
  "method": "api",
  "error": ""
}
```

## Supported URL Formats

- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/shorts/VIDEO_ID`
- `https://www.youtube.com/embed/VIDEO_ID`
- `https://m.youtube.com/watch?v=VIDEO_ID`

## Files

| File | Purpose |
|------|---------|
| `extract_transcript.py` | Main script — CDP connection, JS injection, caption parsing |
| `extract` | Bash wrapper for easy CLI invocation |
| `SKILL.md` | OpenClaw skill manifest |
| `CLAUDE.md` | Developer/architecture notes |

## Limitations

- Requires Chrome running with `--remote-debugging-port`
- Only works with videos that have captions (auto-generated or manual)
- Prefers English captions; falls back to first available language
