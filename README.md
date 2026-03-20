# YouTube Transcript Extractor and Summarizer

Extract YouTube video transcripts by connecting to a visible Chrome instance via CDP (Chrome DevTools Protocol). Clicks "Show transcript" and reads the DOM — the same approach used by real users.

## OpenClaw usage

OpenClaw skills are loaded from `~/.openclaw/workspace/skills/` and require a `SKILL.md`.

```bash
# Install as a local skill
mkdir -p ~/.openclaw/workspace/skills
ln -s /path/to/chrome-youtube-skill ~/.openclaw/workspace/skills/youtube
```

## Codex usage

Codex skills are loaded from `$CODEX_HOME/skills` (usually `~/.codex/skills`) and require a `SKILL.md`.
This repo includes `SKILL.md` and `agents/openai.yaml`.

```bash
# Install as a local skill
mkdir -p ~/.codex/skills
ln -s /path/to/chrome-youtube-skill ~/.codex/skills/youtube
```

Restart Codex after installing so the new skill is detected.

Invoke it in prompts as `$youtube`, for example:

```text
$youtube https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

## Claude usage

Claude Code skills are loaded from `~/.claude/skills` and require a `SKILL.md`.
This repo includes `SKILL.md` with Claude Code-compatible metadata.

```bash
# Install as a local skill
mkdir -p ~/.claude/skills
ln -s /path/to/chrome-youtube-skill ~/.claude/skills/youtube
```

Invoke it with the `/youtube` slash command, for example:

```text
/youtube https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

## Skill Configuration

When used as a skill (OpenClaw, Codex, or Claude Code), summaries are saved to a configurable output directory.

**To configure the output directory:**

1. Copy the example config:
   ```bash
   cp skill.config.example skill.config
   ```

2. Edit `skill.config` and set your desired path:
   ```bash
   OUTPUT_DIR=/path/to/your/summaries
   ```

3. The config file is local to the project and ignored by git.

**Default behavior:**
- If no `skill.config` exists, summaries are saved to `/Users/Shared/youtube_summary`
- The output directory is created automatically if it doesn't exist

## CLI usage

### Single video

```bash
# Plain text output
./extract "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# JSON output
./extract "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --json

# JSON output (also write to a file)
./extract "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --json --json-out /tmp/yt_transcript.json

# From stdin
echo "https://youtu.be/dQw4w9WgXcQ" | ./extract --stdin

# Save transcript to a directory
./extract "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --output-dir ~/Downloads/yt_transcripts

# Disable file saving
./extract "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --no-save

# Custom CDP port
./extract "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --port 9333
```

### Batch channel export

Export transcripts from the N latest videos on a YouTube channel in a single Chrome session:

```bash
# Export the 10 latest videos
./extract batch https://www.youtube.com/@channelhandle/videos --count 10 --output-dir ~/transcripts

# Export all videos (scrolls until the page is fully loaded)
./extract batch https://www.youtube.com/@channelhandle/videos --count 10000 --output-dir ~/transcripts

# Short flags
./extract batch https://www.youtube.com/@channelhandle/videos -n 25 -o ~/transcripts
```

The batch command:
1. Opens the channel's `/videos` page and scrolls until no new videos load
2. Collects up to `--count` video URLs in chronological order (newest first)
3. Extracts each transcript in the same Chrome session (no restart between videos)
4. Saves one `.txt` file per video; skips videos with no captions and reports them at the end

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
pip install .             # from project root (uses pyproject.toml)
# or manually:
pip3 install requests websocket-client
```

Chrome is found automatically. The script searches these paths in order:
1. `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` (macOS)
2. `google-chrome` (Linux, via PATH)
3. `google-chrome-stable` (Linux package managers)
4. `chromium-browser` / `chromium` (Chromium)

## Output

**Plain text (default):**
```
Title: Video Title
Channel: Channel Name
==================================================
This is the full transcript text extracted from the video captions...
```

**Saved transcript files** (with `--output-dir` or `batch`):

Files are named `YYYY-MM-DD - Channel - Title.txt` and start with a metadata header:

```
Title: Video Title
Channel: Channel Name
URL: https://www.youtube.com/watch?v=dQw4w9WgXcQ
Views: 1,234,567
Published: 2024-06-01
============================================================

This is the full transcript text...
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
  "view_count": "1234567",
  "publish_date": "2024-06-01T10:00:00-07:00",
  "error": ""
}
```

Use `--json-out /path/to/result.json` to write the JSON result to disk.

The `method` field indicates which extraction path succeeded: `"dom"` for the primary transcript panel scrape, or `"api"` for the caption track URL fallback.

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
| `src/yt_transcript/__init__.py` | Package exports, `__version__` |
| `src/yt_transcript/extractor.py` | Core — Chrome lifecycle, CDP communication, transcript extraction |
| `src/yt_transcript/cli.py` | CLI entry point, argument parsing, file saving |
| `src/yt_transcript/__main__.py` | `python -m yt_transcript` support |
| `src/yt_transcript/js/get_metadata.js` | Extract title, channel, view count, publish date from `ytInitialPlayerResponse` |
| `src/yt_transcript/js/extract_dom.js` | Click "Show transcript" and scrape the transcript panel DOM |
| `src/yt_transcript/js/extract_api.js` | Fallback: fetch caption track URL via in-page `fetch()` |
| `src/yt_transcript/js/get_channel_videos.js` | Scroll a channel `/videos` page and collect video URLs |
| `extract` | Bash wrapper for CLI invocation |
| `scripts/run_transcript.py` | Run from repo without installation (sets up `sys.path`) |
| `tests/test_extractor.py` | Unit tests (73 tests, runs in <1s) |
| `pyproject.toml` | PEP 621 packaging metadata and dependencies |
| `SKILL.md` | OpenClaw skill manifest |
| `CLAUDE.md` | Developer/architecture notes |

## Testing

```bash
PYTHONPATH=src python3 -m pytest tests/ -v
```

All tests are fully mocked — no Chrome instance is needed to run them.

## Sequential Execution Lock

The script uses an exclusive file lock on `/tmp/yt-extract.lock` (`fcntl.flock` on Unix, `msvcrt.locking` on Windows) to ensure only one extraction runs at a time. If you invoke the script twice concurrently, the second invocation blocks until the first one finishes.

The lock is explicitly released and the lock file is deleted in a `finally` block after each run. If the process is killed before cleanup, the OS releases the lock when the owning process dies, and the script recreates the file on the next run.

## Limitations

- Requires Chrome or Chromium installed on the system
- Only works with videos that have captions (auto-generated or manual)
- Prefers English captions; falls back to first available language
- Reuses an already-running Chrome instance by default (`--no-reuse` to force a fresh launch)
