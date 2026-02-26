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
