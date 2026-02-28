(async function() {
    function normalize(s) {
        return (s || '').replace(/\s+/g, ' ').trim();
    }

    function stripFmt(url) {
        return (url || '').replace(/([?&])fmt=[^&]*/g, '$1').replace(/[?&]$/, '');
    }

    function parseXmlTranscript(xmlText) {
        var parser = new DOMParser();
        var doc = parser.parseFromString(xmlText, 'text/xml');
        var nodes = Array.from(doc.getElementsByTagName('text'));
        var lines = nodes.map(function(n) { return n.textContent || ''; }).filter(Boolean);
        return normalize(lines.join(' '));
    }

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
        var xmlUrl = stripFmt(track.baseUrl);

        var res = await fetch(url, {credentials: 'include'});
        if (!res.ok) {
            // Try XML fallback
            var xmlRes = await fetch(xmlUrl, {credentials: 'include'});
            if (!xmlRes.ok) return JSON.stringify({error: 'fetch failed: ' + res.status});
            var xmlText = await xmlRes.text();
            var xmlTranscript = parseXmlTranscript(xmlText);
            if (!xmlTranscript) return JSON.stringify({error: 'empty xml transcript'});
            return JSON.stringify({text: xmlTranscript});
        }

        var data;
        try {
            data = await res.json();
        } catch (jsonErr) {
            // Some videos return an empty/invalid JSON body for fmt=json3.
            // Retry with XML captions.
            var fallbackRes = await fetch(xmlUrl, {credentials: 'include'});
            if (!fallbackRes.ok) {
                return JSON.stringify({
                    error: 'json parse failed and xml fallback failed: ' + jsonErr.message
                });
            }
            var fallbackXml = await fallbackRes.text();
            var fallbackTranscript = parseXmlTranscript(fallbackXml);
            if (!fallbackTranscript) {
                return JSON.stringify({
                    error: 'json parse failed and xml transcript empty: ' + jsonErr.message
                });
            }
            return JSON.stringify({text: fallbackTranscript});
        }

        var events = data.events || [];
        var lines = [];
        for (var i = 0; i < events.length; i++) {
            var segs = events[i].segs;
            if (!segs) continue;
            var line = segs.map(function(s) { return s.utf8 || ''; }).join('').trim();
            if (line) lines.push(line);
        }
        return JSON.stringify({text: normalize(lines.join(' '))});
    } catch(e) {
        return JSON.stringify({error: e.message});
    }
})()
