---
name: youtube-transcript
description: Extract YouTube video transcripts using Chrome browser automation via CDP. Returns clean transcript text with video metadata (title, channel). Works with any YouTube video that has captions.
---

# YouTube Transcript Extractor

## When to Use

- User shares a YouTube URL and wants a summary or transcript
- Need to extract spoken content from a YouTube video
- Analyzing video content programmatically
- Any task requiring the text of what was said in a video

## How It Works

Connects to a running Chrome instance via Chrome DevTools Protocol (CDP):
1. **Opens tab** with the YouTube video URL
2. **Extracts `ytInitialPlayerResponse`** from the page to find caption tracks
3. **Fetches caption track** in json3 format (prefers English, falls back to first available)
4. **Parses transcript** from caption segments into clean text
5. **Closes tab** automatically

## Usage

### CLI
```bash
# Basic extraction (plain text output)
~/projects/chrome-youtube-summary/extract "https://www.youtube.com/watch?v=VIDEO_ID"

# JSON output
~/projects/chrome-youtube-summary/extract "https://www.youtube.com/watch?v=VIDEO_ID" --json

# From stdin
echo "https://www.youtube.com/watch?v=VIDEO_ID" | ~/projects/chrome-youtube-summary/extract --stdin

# Custom CDP port
~/projects/chrome-youtube-summary/extract "https://www.youtube.com/watch?v=VIDEO_ID" --port 9333
```

### From Python
```python
import subprocess, json

result = subprocess.run([
    "python3", "/Users/nick/projects/chrome-youtube-summary/extract_transcript.py",
    url, "--json"
], capture_output=True, text=True)

if result.returncode == 0:
    data = json.loads(result.stdout)
    if data["success"]:
        transcript = data["transcript"]
        title = data["title"]
```

## Output Format

### Text Mode (default)
```
Title: Video Title
Channel: Channel Name
==================================================
[full transcript text...]
```

### JSON Mode (--json)
```json
{
  "success": true,
  "video_id": "dQw4w9WgXcQ",
  "title": "Video Title",
  "channel": "Channel Name",
  "url": "https://www.youtube.com/watch?v=...",
  "transcript": "full transcript text...",
  "language": "en",
  "method": "api",
  "error": ""
}
```

## Prerequisites

- Chrome running with remote debugging enabled:
  ```bash
  open -a "Google Chrome" --args --remote-debugging-port=9222
  ```
- Python 3 with `requests` and `websocket-client`:
  ```bash
  pip3 install requests websocket-client
  ```

## Error Handling

- **No Chrome connection**: Clear error message with startup instructions
- **No captions available**: Returns error with video metadata still populated
- **Fetch failures**: Retries caption track extraction up to 3 times
- **Invalid URL**: Reports unparseable video ID

## Supported URL Formats

- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/shorts/VIDEO_ID`
- `https://www.youtube.com/embed/VIDEO_ID`
- `https://m.youtube.com/watch?v=VIDEO_ID`
