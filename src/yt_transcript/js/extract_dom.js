(async function() {
    function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
    function text(el) {
        return ((el && el.textContent) || '')
            .replace(/\s+/g, ' ')
            .trim();
    }

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

    function waitForAny(selectors, timeout) {
        return new Promise((resolve, reject) => {
            function findNow() {
                for (var i = 0; i < selectors.length; i++) {
                    var el = document.querySelector(selectors[i]);
                    if (el) return el;
                }
                return null;
            }

            var found = findNow();
            if (found) return resolve(found);

            var obs = new MutationObserver(() => {
                var found = findNow();
                if (found) {
                    obs.disconnect();
                    resolve(found);
                }
            });
            obs.observe(document.body, {childList: true, subtree: true});
            setTimeout(() => {
                obs.disconnect();
                reject(new Error('timeout'));
            }, timeout);
        });
    }

    function findTranscriptButton() {
        var oldButton = document.querySelector('ytd-video-description-transcript-section-renderer button');
        if (oldButton) return oldButton;

        var buttons = Array.from(document.querySelectorAll('button, yt-button-shape button'));
        return buttons.find(function(btn) {
            return /transcript/i.test(text(btn));
        }) || null;
    }

    function extractOldLayout(root) {
        var container = (root || document).querySelector('#segments-container');
        if (!container) return '';

        var segs = container.querySelectorAll('yt-formatted-string.segment-text');
        if (!segs.length) segs = container.querySelectorAll('yt-formatted-string');

        return Array.from(segs)
            .map(function(el) { return text(el); })
            .filter(Boolean)
            .join(' ')
            .replace(/\s+/g, ' ')
            .trim();
    }

    function extractModernLayout(root) {
        var segs = (root || document).querySelectorAll('transcript-segment-view-model');
        if (!segs.length) return '';

        var lines = Array.from(segs)
            .map(function(seg) {
                var t = seg.querySelector('span[role="text"], .yt-core-attributed-string, yt-formatted-string');
                return text(t);
            })
            .filter(Boolean);

        return lines.join(' ').replace(/\s+/g, ' ').trim();
    }

    try {
        var button = findTranscriptButton();
        var textValue = extractOldLayout(document) || extractModernLayout(document);
        var wasOpen = !!textValue;

        if (!wasOpen) {
            if (!button) return JSON.stringify({error: 'no_button'});
            button.click();
            try {
                await waitForAny(
                    ['#segments-container', 'transcript-segment-view-model'],
                    8000
                );
            } catch(e) {
                return JSON.stringify({error: 'no_container'});
            }
        }

        // Wait for transcript segments to populate.
        await sleep({{SETTLE_MS}});

        textValue = extractOldLayout(document) || extractModernLayout(document);
        if (!textValue) return JSON.stringify({error: 'no_segments'});

        // Close panel if we opened it.
        if (!wasOpen && button) button.click();

        return JSON.stringify({text: textValue || ''});
    } catch(e) {
        return JSON.stringify({error: e.message});
    }
})()
