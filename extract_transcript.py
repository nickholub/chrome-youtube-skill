#!/usr/bin/env python3
"""
YouTube Transcript Extractor
Extracts video transcripts via Chrome DevTools Protocol (CDP).
Opens the YouTube video in a visible Chrome tab, clicks "Show transcript",
and extracts the text from the DOM — mimicking normal user behavior.

Ported from ChromeAIHighlights/src/contentScript.js.
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

    def open_tab(self, url):
        """Open a new tab and return target info."""
        endpoint = f"{self.base_url}/json/new?{url}"
        resp = requests.put(endpoint, timeout=10)
        if resp.status_code == 405:
            resp = requests.get(endpoint, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def close_tab(self, target_id):
        """Close a tab by target ID."""
        try:
            requests.get(f"{self.base_url}/json/close/{target_id}", timeout=5)
        except Exception:
            pass

    def send_js(self, ws, script, msg_id=1):
        """Send JS for evaluation and wait for the matching response."""
        ws.send(json.dumps({
            "id": msg_id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": script,
                "returnByValue": True,
                "awaitPromise": True,
            }
        }))
        while True:
            data = json.loads(ws.recv())
            if data.get("id") == msg_id:
                return data

    def extract_transcript(self, url):
        """
        Open YouTube URL in visible Chrome, extract transcript via DOM, close tab.
        """
        video_id = self._parse_video_id(url)
        if not video_id:
            return self._result(error="Could not parse video ID from URL")

        canonical_url = f"https://www.youtube.com/watch?v={video_id}"
        target = None
        ws = None

        try:
            target = self.open_tab(canonical_url)

            # Wait for page to load before connecting WebSocket
            # (navigating resets the WS connection)
            time.sleep(5)

            ws = websocket.create_connection(
                target["webSocketDebuggerUrl"], timeout=30
            )

            # Poll until YouTube's JS has initialized
            self._wait_for_player_response(ws)

            # Get video metadata from ytInitialPlayerResponse
            meta = self._get_metadata(ws, msg_id=2)

            # Try DOM extraction: click "Show transcript" and scrape
            transcript = self._extract_from_dom(ws, msg_id=10)

            # Fallback: try API-based extraction via in-page fetch
            method = "dom"
            if not transcript:
                transcript = self._extract_from_api(ws, msg_id=20)
                method = "api"

            if not transcript:
                return self._result(
                    video_id=video_id, url=canonical_url,
                    title=meta.get("title", ""),
                    channel=meta.get("channel", ""),
                    error="No transcript found. Video may not have captions.",
                )

            return self._result(
                success=True, video_id=video_id, url=canonical_url,
                title=meta.get("title", ""),
                channel=meta.get("channel", ""),
                language=meta.get("language", ""),
                transcript=transcript, method=method,
            )

        except requests.ConnectionError:
            return self._result(
                video_id=video_id, url=canonical_url,
                error=(
                    f"Cannot connect to Chrome on port {self.port}. "
                    "Launch Chrome with: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome "
                    "--remote-debugging-port=9222 '--remote-allow-origins=*' "
                    '--user-data-dir="$HOME/.chrome-debug-profile"'
                ),
            )
        except Exception as e:
            return self._result(
                video_id=video_id, url=canonical_url, error=str(e)
            )
        finally:
            if ws:
                try:
                    ws.close()
                except Exception:
                    pass
            if target:
                self.close_tab(target["id"])

    # ── Page helpers ──────────────────────────────────────────────

    def _wait_for_player_response(self, ws, max_wait=15):
        """Poll until ytInitialPlayerResponse is available."""
        deadline = time.time() + max_wait
        while time.time() < deadline:
            js = "(!!window.ytInitialPlayerResponse).toString()"
            resp = self.send_js(ws, js, msg_id=999)
            val = resp.get("result", {}).get("result", {}).get("value")
            if val == "true":
                return
            time.sleep(1)

    def _get_metadata(self, ws, msg_id=2):
        """Extract title, channel, language from ytInitialPlayerResponse."""
        js = """
        (function() {
            var pr = window.ytInitialPlayerResponse;
            if (!pr) return JSON.stringify({});
            var title = '', channel = '', lang = '';
            try { title = pr.videoDetails.title || ''; } catch(e) {}
            try { channel = pr.videoDetails.author || ''; } catch(e) {}
            try {
                var tracks = pr.captions.playerCaptionsTracklistRenderer.captionTracks;
                var t = tracks.find(function(t) { return t.languageCode && t.languageCode.startsWith('en'); }) || tracks[0];
                lang = t ? t.languageCode : '';
            } catch(e) {}
            return JSON.stringify({title: title, channel: channel, language: lang});
        })()
        """
        resp = self.send_js(ws, js, msg_id)
        value = resp.get("result", {}).get("result", {}).get("value", "{}")
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}

    # ── DOM extraction (primary) ──────────────────────────────────

    def _extract_from_dom(self, ws, msg_id=10):
        """
        Click "Show transcript" button and extract text from the transcript panel.
        Exactly mirrors ChromeAIHighlights extractTranscriptFromDOM().
        """
        js = """
        (async function() {
            function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

            function waitForEl(sel, timeout) {
                return new Promise((resolve, reject) => {
                    var el = document.querySelector(sel);
                    if (el) return resolve(el);
                    var obs = new MutationObserver(() => {
                        var el = document.querySelector(sel);
                        if (el) { obs.disconnect(); resolve(el); }
                    });
                    obs.observe(document.body, {childList: true, subtree: true});
                    setTimeout(() => { obs.disconnect(); reject(new Error('timeout')); }, timeout);
                });
            }

            try {
                // Find the "Show transcript" button
                var button;
                try {
                    button = await waitForEl(
                        'ytd-video-description-transcript-section-renderer button', 8000
                    );
                } catch(e) {
                    return JSON.stringify({error: 'no_button'});
                }

                // Check if panel is already open
                var container = document.querySelector('#segments-container');
                var wasOpen = !!container;

                if (!wasOpen) {
                    button.click();
                    try {
                        container = await waitForEl('#segments-container', 5000);
                    } catch(e) {
                        return JSON.stringify({error: 'no_container'});
                    }
                }

                // Wait for segments to populate
                await sleep(500);

                // Extract text from segments
                var segs = container.querySelectorAll('yt-formatted-string.segment-text');
                if (!segs.length) segs = container.querySelectorAll('yt-formatted-string');

                var text = Array.from(segs)
                    .map(function(el) { return (el.textContent || '').trim(); })
                    .filter(Boolean)
                    .join(' ')
                    .replace(/\\s+/g, ' ')
                    .trim();

                // Close panel if we opened it
                if (!wasOpen && button) button.click();

                return JSON.stringify({text: text || ''});
            } catch(e) {
                return JSON.stringify({error: e.message});
            }
        })()
        """
        resp = self.send_js(ws, js, msg_id)
        value = resp.get("result", {}).get("result", {}).get("value")
        if not value:
            return None
        try:
            data = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
        text = data.get("text", "")
        return text if text else None

    # ── API extraction (fallback) ─────────────────────────────────

    def _extract_from_api(self, ws, msg_id=20):
        """
        Fallback: fetch caption track URL from ytInitialPlayerResponse,
        then fetch + parse it in-browser with credentials.
        """
        js = """
        (async function() {
            try {
                var pr = window.ytInitialPlayerResponse;
                if (!pr) return JSON.stringify({error: 'no player response'});

                var tracks = [];
                try {
                    tracks = pr.captions.playerCaptionsTracklistRenderer.captionTracks || [];
                } catch(e) {}
                if (!tracks.length) return JSON.stringify({error: 'no tracks'});

                var track = tracks.find(function(t) {
                    return t.languageCode && t.languageCode.startsWith('en');
                }) || tracks[0];

                var url = track.baseUrl;
                if (url.indexOf('fmt=') === -1) url += '&fmt=json3';

                var res = await fetch(url, {credentials: 'include'});
                if (!res.ok) {
                    // Try XML fallback
                    var xmlUrl = track.baseUrl.replace(/&fmt=[^&]*/, '');
                    var xmlRes = await fetch(xmlUrl, {credentials: 'include'});
                    if (!xmlRes.ok) return JSON.stringify({error: 'fetch failed: ' + res.status});
                    var xmlText = await xmlRes.text();
                    var parser = new DOMParser();
                    var doc = parser.parseFromString(xmlText, 'text/xml');
                    var nodes = Array.from(doc.getElementsByTagName('text'));
                    var lines = nodes.map(function(n) { return n.textContent || ''; }).filter(Boolean);
                    return JSON.stringify({text: lines.join(' ').replace(/\\s+/g, ' ').trim()});
                }

                var data = await res.json();
                var events = data.events || [];
                var lines = [];
                for (var i = 0; i < events.length; i++) {
                    var segs = events[i].segs;
                    if (!segs) continue;
                    var line = segs.map(function(s) { return s.utf8 || ''; }).join('').trim();
                    if (line) lines.push(line);
                }
                return JSON.stringify({text: lines.join(' ').replace(/\\s+/g, ' ').trim()});
            } catch(e) {
                return JSON.stringify({error: e.message});
            }
        })()
        """
        resp = self.send_js(ws, js, msg_id)
        value = resp.get("result", {}).get("result", {}).get("value")
        if not value:
            return None
        try:
            data = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
        text = data.get("text", "")
        return text if text else None

    # ── Utilities ─────────────────────────────────────────────────

    def _parse_video_id(self, url):
        """Extract video ID from various YouTube URL formats."""
        parsed = urlparse(url)
        if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
            if parsed.path == "/watch":
                return parse_qs(parsed.query).get("v", [None])[0]
            if parsed.path.startswith("/shorts/"):
                return parsed.path.split("/shorts/")[1].split("/")[0]
            if parsed.path.startswith("/embed/"):
                return parsed.path.split("/embed/")[1].split("/")[0]
        if parsed.hostname == "youtu.be":
            return parsed.path.lstrip("/").split("/")[0]
        return None

    def _result(self, success=False, video_id="", url="", title="",
                channel="", transcript="", language="", method="", error=""):
        return {
            "success": success,
            "video_id": video_id,
            "title": title,
            "channel": channel,
            "url": url,
            "transcript": transcript,
            "language": language,
            "method": method,
            "error": error,
        }


def main():
    if len(sys.argv) < 2:
        print("Usage: extract_transcript.py <youtube-url> [--json] [--port 9222]", file=sys.stderr)
        print("       echo '<url>' | extract_transcript.py --stdin [--json]", file=sys.stderr)
        sys.exit(1)

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
