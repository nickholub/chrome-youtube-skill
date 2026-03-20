(function() {
    var pr = window.ytInitialPlayerResponse;
    if (!pr) return JSON.stringify({});
    var title = '', channel = '', lang = '', viewCount = '', publishDate = '';
    try { title = pr.videoDetails.title || ''; } catch(e) {}
    try { channel = pr.videoDetails.author || ''; } catch(e) {}
    try { viewCount = pr.videoDetails.viewCount || ''; } catch(e) {}
    try { publishDate = pr.microformat.playerMicroformatRenderer.publishDate || ''; } catch(e) {}
    try {
        var tracks = pr.captions.playerCaptionsTracklistRenderer.captionTracks;
        var t = tracks.find(function(t) { return t.languageCode && t.languageCode.startsWith('en'); }) || tracks[0];
        lang = t ? t.languageCode : '';
    } catch(e) {}
    return JSON.stringify({title: title, channel: channel, language: lang, view_count: viewCount, publish_date: publishDate});
})()
