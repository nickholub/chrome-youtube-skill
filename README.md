# YouTube Transcript Extractor

Extract YouTube video transcripts by connecting to a visible Chrome instance via CDP (Chrome DevTools Protocol). Clicks "Show transcript" and reads the DOM — the same approach used by real users and the [ChromeAIHighlights](https://github.com/nicholasgasior/ChromeAIHighlights) extension.

## How It Works

```
┌──────────┐    CDP HTTP     ┌─────────────┐   WebSocket    ┌──────────────┐
│  Script   │ ──────────────→│ Chrome :9222 │ ←────────────→ │ YouTube Tab  │
│ (Python)  │  open/close    │  (visible)   │  Runtime.eval  │  (visible)   │
└──────────┘    tab          └─────────────┘                └──────────────┘
```

Everything happens in a real, visible Chrome window. The script clicks buttons and reads the page just like a user would — no headless mode, no API calls that get rate-limited.

### Step-by-Step Extraction Flow

1. **Launch Chrome** — The script automatically finds Chrome on your system, kills any existing debug instance using the same profile (`~/.chrome-debug-profile`), and launches a fresh Chrome process with `--remote-debugging-port=9222`. It then polls `http://127.0.0.1:9222/json/version` until the CDP endpoint is ready (up to 15 seconds).

2. **Open a new tab** — Sends `PUT /json/new?{url}` to Chrome's CDP HTTP API to open the YouTube video in a new visible tab. (Falls back to `GET` for Chrome versions older than 145 that return 405 on PUT.) Chrome returns a JSON object with the tab's `id` and `webSocketDebuggerUrl`.

3. **Wait for page load** — Sleeps 5 seconds to let the page navigate and YouTube's JavaScript initialize. This delay is necessary because navigating a tab resets its WebSocket connection — connecting too early would get disconnected.

4. **Connect WebSocket** — Opens a WebSocket to the tab's `webSocketDebuggerUrl`. All subsequent interaction with the page happens through `Runtime.evaluate` messages over this WebSocket, which execute JavaScript in the tab's context and return results.

5. **Wait for YouTube's player** — Polls `window.ytInitialPlayerResponse` (YouTube's internal player state object) up to 15 seconds until it's defined. This object contains video metadata and caption track information.

6. **Extract metadata** — Reads `videoDetails.title`, `videoDetails.author`, and the first English caption track's `languageCode` from `ytInitialPlayerResponse`.

7. **DOM extraction (primary method)** — Injects JavaScript that:
   - Waits up to 8 seconds for the `ytd-video-description-transcript-section-renderer button` element (the "Show transcript" button below the video description)
   - Clicks the button to open the transcript panel
   - Waits up to 5 seconds for `#segments-container` to appear in the DOM
   - Waits 500ms for transcript segments to populate
   - Reads text from all `yt-formatted-string.segment-text` elements inside the container
   - Joins all segment text into a single string with whitespace normalized
   - Closes the transcript panel if it was opened by the script

8. **API extraction (fallback method)** — If DOM extraction fails (e.g., the "Show transcript" button isn't present), the script falls back to fetching captions via YouTube's internal caption API. This runs entirely inside the browser tab using `fetch()` with cookies — avoiding the 429 rate limits that happen when fetching from outside the browser. It:
   - Gets the caption track URL from `ytInitialPlayerResponse.captions.playerCaptionsTracklistRenderer.captionTracks`
   - Prefers English tracks; falls back to the first available language
   - Fetches the `json3` format first, parsing `events[].segs[].utf8` into text
   - Falls back to XML format if JSON fails, parsing `<text>` elements via `DOMParser`

9. **Close tab** — Sends `GET /json/close/{targetId}` to Chrome's CDP API.

10. **Shutdown Chrome** — Terminates the Chrome process that was launched in step 1. Uses `SIGTERM` first, escalating to `SIGKILL` if Chrome doesn't exit within 5 seconds.

### Why This Approach?

- **No API keys or authentication** — Uses the same method a human would: clicking buttons and reading the page
- **Avoids rate limiting** — All network requests happen inside Chrome with the user's cookies, so YouTube sees normal browser traffic
- **Works with auto-generated and manual captions** — The DOM method reads whatever transcript YouTube displays in its UI
- **Visible Chrome** — You can see exactly what's happening; no hidden headless browser

## Setup

**Install Python dependencies:**

```bash
pip3 install requests websocket-client
```

Chrome is found automatically. The script searches these paths in order:
1. `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` (macOS)
2. `google-chrome` (Linux, via PATH)
3. `google-chrome-stable` (Linux package managers)
4. `chromium-browser` / `chromium` (Chromium)

## Usage

```bash
# Plain text output (also saves transcript file)
./extract "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# JSON output
./extract "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --json

# From stdin
echo "https://youtu.be/dQw4w9WgXcQ" | ./extract --stdin

# Custom transcript output directory
./extract "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --output-dir ~/Downloads/yt_transcripts

# Disable file saving
./extract "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --no-save

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

The `method` field indicates which extraction path succeeded: `"dom"` for the primary transcript panel scrape, or `"api"` for the caption track URL fallback.

By default, successful runs are saved to:

`/Users/Shared/yt_transcripts`

The JSON output also includes an `output_file` field when saving is enabled.
Use `--output-dir` to override the directory or `--no-save` to disable file creation.

## Supported URL Formats

- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/shorts/VIDEO_ID`
- `https://www.youtube.com/embed/VIDEO_ID`
- `https://m.youtube.com/watch?v=VIDEO_ID`

All formats are normalized to `https://www.youtube.com/watch?v=VIDEO_ID` before loading.

## Files

| File | Purpose |
|------|---------|
| `extract_transcript.py` | Main script — Chrome lifecycle, CDP communication, DOM/API transcript extraction |
| `extract` | Bash wrapper for CLI invocation |
| `test_extract_transcript.py` | Unit tests (61 tests, runs in <1s) |
| `SKILL.md` | OpenClaw skill manifest |
| `CLAUDE.md` | Developer/architecture notes |

## Testing

```bash
python3 -m pytest test_extract_transcript.py -v
```

All tests are fully mocked — no Chrome instance is needed to run them.

## Sequential Execution Lock

The script uses an exclusive file lock (`fcntl.flock` on `/tmp/yt-extract.lock`) to ensure only one extraction runs at a time. If you invoke the script twice concurrently, the second invocation blocks until the first one finishes.

**How the lock is released:**

| Scenario | Lock released? | Mechanism |
|----------|---------------|-----------|
| Extraction completes successfully | Yes | `with` block exits, file closes, lock released |
| Extraction raises an exception | Yes | `with` block exits on exception, file closes, lock released |
| Process killed (`SIGTERM`, `SIGKILL`, `kill -9`) | Yes | OS releases `flock` locks when the owning process dies |
| Machine reboots / power loss | Yes | `/tmp` is cleared on boot; `flock` doesn't survive process death anyway |

The lock is tied to the process lifetime, not to the file on disk. There is no risk of a stuck lock preventing future runs. Even if the script crashes mid-extraction, the next invocation will acquire the lock immediately.

**Manual release (not normally needed):**

```bash
# If you somehow need to clear it, just remove the file
rm /tmp/yt-extract.lock
```

Removing the file is harmless — the script recreates it on each run. But in practice you should never need to do this, since `flock` locks are always released when the process exits.

## Limitations

- Requires Chrome or Chromium installed on the system
- Only works with videos that have captions (auto-generated or manual)
- Prefers English captions; falls back to first available language
- The script launches and kills its own Chrome instance on each run; it cannot reuse an already-running browser
