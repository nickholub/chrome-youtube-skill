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
            return JSON.stringify({text: lines.join(' ').replace(/\s+/g, ' ').trim()});
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
        return JSON.stringify({text: lines.join(' ').replace(/\s+/g, ' ').trim()});
    } catch(e) {
        return JSON.stringify({error: e.message});
    }
})()
