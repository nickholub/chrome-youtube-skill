#!/usr/bin/env python3
"""
YouTube Transcript Extractor
Extracts video transcripts via Chrome DevTools Protocol (CDP).
Connects to a running Chrome instance, opens the YouTube video,
and extracts captions using ytInitialPlayerResponse.
"""

import sys
import json
import time
import requests
import websocket
from urllib.parse import urlparse, parse_qs


class YouTubeTranscriptExtractor:
    def __init__(self, port=9222):
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"

    def get_cdp_targets(self):
        """List open CDP targets."""
        resp = requests.get(f"{self.base_url}/json", timeout=5)
        resp.raise_for_status()
        return resp.json()

    def open_tab(self, url):
        """Open a new tab and return target info."""
        resp = requests.get(f"{self.base_url}/json/new?{url}", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def close_tab(self, target_id):
        """Close a tab by target ID."""
        try:
            requests.get(f"{self.base_url}/json/close/{target_id}", timeout=5)
        except Exception:
            pass

    def execute_js(self, ws_url, script, timeout=10):
        """Execute JavaScript in a page via CDP WebSocket."""
        ws = websocket.create_connection(ws_url, timeout=timeout)
        try:
            msg = json.dumps({
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": script,
                    "returnByValue": True,
                    "awaitPromise": True,
                }
            })
            ws.send(msg)

            while True:
                raw = ws.recv()
                data = json.loads(raw)
                if data.get("id") == 1:
                    return data
        finally:
            ws.close()

    def extract_transcript(self, url, wait=3, retries=3, retry_delay=1):
        """
        Open YouTube URL in Chrome, extract transcript, close tab.
        Returns dict with success, video_id, title, channel, transcript, etc.
        """
        video_id = self._parse_video_id(url)
        if not video_id:
            return self._error_result(url, "", "Could not parse video ID from URL")

        canonical_url = f"https://www.youtube.com/watch?v={video_id}"
        result = {
            "success": False,
            "video_id": video_id,
            "title": "",
            "channel": "",
            "url": canonical_url,
            "transcript": "",
            "language": "",
            "method": "api",
            "error": "",
        }

        target = None
        try:
            # Open tab
            target = self.open_tab(canonical_url)
            target_id = target["id"]
            ws_url = target["webSocketDebuggerUrl"]

            # Wait for page load
            time.sleep(wait)

            # Extract caption track info with retries
            caption_data = None
            for attempt in range(retries):
                caption_data = self._get_caption_data(ws_url)
                if caption_data and caption_data.get("tracks"):
                    break
                if attempt < retries - 1:
                    time.sleep(retry_delay)

            if not caption_data or not caption_data.get("tracks"):
                result["title"] = (caption_data or {}).get("title", "")
                result["channel"] = (caption_data or {}).get("channel", "")
                result["error"] = "No caption tracks found for this video"
                return result

            result["title"] = caption_data.get("title", "")
            result["channel"] = caption_data.get("channel", "")

            # Pick best track (prefer English)
            tracks = caption_data["tracks"]
            preferred = next(
                (t for t in tracks if t.get("languageCode", "").startswith("en")),
                tracks[0]
            )
            result["language"] = preferred.get("languageCode", "unknown")

            # Fetch transcript from caption track URL
            transcript = self._fetch_transcript(preferred["baseUrl"])
            if not transcript:
                result["error"] = "Failed to fetch transcript from caption track"
                return result

            result["success"] = True
            result["transcript"] = transcript
            return result

        except requests.ConnectionError:
            result["error"] = (
                f"Cannot connect to Chrome on port {self.port}. "
                "Start Chrome with: open -a 'Google Chrome' --args --remote-debugging-port=9222"
            )
            return result
        except Exception as e:
            result["error"] = str(e)
            return result
        finally:
            if target:
                self.close_tab(target["id"])

    def _parse_video_id(self, url):
        """Extract video ID from various YouTube URL formats."""
        parsed = urlparse(url)

        if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
            if parsed.path == "/watch":
                qs = parse_qs(parsed.query)
                return qs.get("v", [None])[0]
            if parsed.path.startswith("/shorts/"):
                return parsed.path.split("/shorts/")[1].split("/")[0]
            if parsed.path.startswith("/embed/"):
                return parsed.path.split("/embed/")[1].split("/")[0]

        if parsed.hostname in ("youtu.be",):
            return parsed.path.lstrip("/").split("/")[0]

        # Bare video ID (11 chars)
        if len(url) == 11 and url.isalnum():
            return url

        return None

    def _get_caption_data(self, ws_url):
        """Inject JS to extract caption tracks and metadata from the page."""
        js = """
        (function() {
            var pr = window.ytInitialPlayerResponse;
            if (!pr) {
                // Try to find it from script tags
                var scripts = document.querySelectorAll('script');
                for (var i = 0; i < scripts.length; i++) {
                    var text = scripts[i].textContent || '';
                    var match = text.match(/ytInitialPlayerResponse\\s*=\\s*(\\{.+?\\});/s);
                    if (match) {
                        try { pr = JSON.parse(match[1]); break; } catch(e) {}
                    }
                }
            }
            if (!pr) return JSON.stringify({tracks: [], title: '', channel: ''});

            var title = '';
            var channel = '';
            try { title = pr.videoDetails.title || ''; } catch(e) {}
            try { channel = pr.videoDetails.author || ''; } catch(e) {}

            var tracks = [];
            try {
                tracks = pr.captions.playerCaptionsTracklistRenderer.captionTracks || [];
            } catch(e) {}

            return JSON.stringify({
                tracks: tracks.map(function(t) {
                    return {baseUrl: t.baseUrl, languageCode: t.languageCode, name: t.name};
                }),
                title: title,
                channel: channel
            });
        })()
        """
        resp = self.execute_js(ws_url, js)
        value = resp.get("result", {}).get("result", {}).get("value")
        if not value:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None

    def _fetch_transcript(self, base_url):
        """Fetch and parse json3 caption track into plain text."""
        url = base_url if "fmt=" in base_url else f"{base_url}&fmt=json3"
        resp = requests.get(url, timeout=15)
        if not resp.ok:
            return None

        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
            return None

        events = data.get("events", [])
        lines = []
        for event in events:
            segs = event.get("segs")
            if not segs:
                continue
            line = "".join(seg.get("utf8", "") for seg in segs).strip()
            if line:
                lines.append(line)

        text = " ".join(lines)
        # Collapse whitespace
        return " ".join(text.split())

    def _error_result(self, url, video_id, error):
        return {
            "success": False,
            "video_id": video_id,
            "title": "",
            "channel": "",
            "url": url,
            "transcript": "",
            "language": "",
            "method": "api",
            "error": error,
        }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 extract_transcript.py <youtube-url> [--json] [--port 9222]", file=sys.stderr)
        print("       echo '<url>' | python3 extract_transcript.py --stdin [--json]", file=sys.stderr)
        sys.exit(1)

    # Parse arguments
    output_json = False
    port = 9222
    url = None
    use_stdin = False

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--json":
            output_json = True
        elif args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 1
        elif args[i] == "--stdin":
            use_stdin = True
        elif not args[i].startswith("--") and url is None:
            url = args[i]
        i += 1

    if use_stdin:
        url = sys.stdin.readline().strip()

    if not url:
        print("Error: No URL provided", file=sys.stderr)
        sys.exit(1)

    extractor = YouTubeTranscriptExtractor(port=port)
    result = extractor.extract_transcript(url)

    if output_json:
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
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
