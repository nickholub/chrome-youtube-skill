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
        await sleep({{SETTLE_MS}});

        // Extract text from segments
        var segs = container.querySelectorAll('yt-formatted-string.segment-text');
        if (!segs.length) segs = container.querySelectorAll('yt-formatted-string');

        var text = Array.from(segs)
            .map(function(el) { return (el.textContent || '').trim(); })
            .filter(Boolean)
            .join(' ')
            .replace(/\s+/g, ' ')
            .trim();

        // Close panel if we opened it
        if (!wasOpen && button) button.click();

        return JSON.stringify({text: text || ''});
    } catch(e) {
        return JSON.stringify({error: e.message});
    }
})()
