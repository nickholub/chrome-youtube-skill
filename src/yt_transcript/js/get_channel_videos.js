(async function() {
    function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

    var limit = {{LIMIT}};

    function collectUrls() {
        var links = Array.from(document.querySelectorAll(
            'a#video-title-link, a#video-title, ytd-rich-item-renderer a[href*="/watch?v="]'
        ));
        var seen = {};
        var urls = [];
        for (var i = 0; i < links.length; i++) {
            var href = links[i].href;
            if (href && href.includes('/watch?v=') && !seen[href]) {
                seen[href] = true;
                urls.push(href);
            }
        }
        return urls;
    }

    // Wait for at least one video card to appear
    var waited = 0;
    while (waited < 10000) {
        if (collectUrls().length > 0) break;
        await sleep(500);
        waited += 500;
    }

    // Scroll until no new videos load (stagnation) or we have enough
    var prevCount = 0;
    var stagnantRounds = 0;
    var MAX_STAGNANT = 3;  // stop after 3 scrolls with no new videos

    while (true) {
        var urls = collectUrls();
        if (urls.length >= limit) break;

        if (urls.length === prevCount) {
            stagnantRounds++;
            if (stagnantRounds >= MAX_STAGNANT) break;
        } else {
            stagnantRounds = 0;
        }
        prevCount = urls.length;

        window.scrollBy(0, window.innerHeight * 3);
        await sleep(1500);
    }

    var urls = collectUrls();
    return JSON.stringify(urls.slice(0, limit));
})()
