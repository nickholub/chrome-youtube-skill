# YouTube Transcript Extractor

Extract YouTube video transcripts by connecting to a visible Chrome instance via CDP. Clicks "Show transcript" and reads the DOM — the same approach used by real users and the [ChromeAIHighlights](https://github.com/nicholasgasior/ChromeAIHighlights) extension.

## How It Works

```
┌──────────┐    CDP HTTP     ┌─────────────┐   WebSocket    ┌──────────────┐
│  Script   │ ──────────────→│ Chrome :9222 │ ←────────────→ │ YouTube Tab  │
│ (Python)  │  open/close    │  (visible)   │  Runtime.eval  │  (visible)   │
└──────────┘    tab          └─────────────┘                └──────────────┘
      │
      │  1. Open new tab with video URL
      │  2. Wait for page to fully load
      │  3. Click "Show transcript" button via JS
      │  4. Read transcript text from DOM
      │  5. Close tab
      ▼
   Transcript text
```

Everything happens in a real, visible Chrome window. The script clicks buttons and reads the page just like a user would — no headless mode, no API calls that get rate-limited.

## Setup

**1. Install Python dependencies:**

```bash
pip3 install requests websocket-client
```

**2. Launch Chrome with remote debugging:**

```bash
# macOS — must use a non-default user-data-dir
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  '--remote-allow-origins=*' \
  --user-data-dir="$HOME/.chrome-debug-profile"
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
  "method": "dom",
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
| `extract_transcript.py` | Main script — CDP connection, DOM transcript extraction |
| `extract` | Bash wrapper for easy CLI invocation |
| `SKILL.md` | OpenClaw skill manifest |
| `CLAUDE.md` | Developer/architecture notes |

## Limitations

- Requires Chrome running with `--remote-debugging-port` and `--remote-allow-origins=*`
- Only works with videos that have captions (auto-generated or manual)
- Prefers English captions; falls back to first available language
