(() => {
    const proto = HTMLMediaElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(proto, 'seekable');

    if (!descriptor || !descriptor.configurable) return;

    const nativeGet = descriptor.get;

    Object.defineProperty(proto, 'seekable', {
        configurable: true,
        enumerable: true,
        get() {
            try {
                const ranges = nativeGet.call(this);
                // Target zero-length mock ranges typically used to lock media progress
                if (isFinite(this.duration) && (!ranges || ranges.length === 0)) {
                    return {
                        length: 1,
                        start: () => 0,
                        end: () => this.duration,
                        item: () => 0
                    };
                }
                return ranges;
            } catch (e) {
                return nativeGet.call(this);
            }
        }
    });

    // Prevent ad video freeze by accelerating playback rate on unskippable segments
    setInterval(() => {
        const video = document.querySelector('video');
        const hasAdClass = document.querySelector('.ad-showing, .html5-video-player.ad-mode');
        
        if (video && hasAdClass) {
            // Speed past the un-skips instantly and mute audio artifacts
            video.playbackRate = 16.0;
            video.muted = true;
        }
    }, 300);
})();
