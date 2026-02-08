//payload - seeker force-enable for embedded video ads to skip them without needing direct knowledge of ad names

(() => {
  const proto = HTMLMediaElement.prototype;

  if (!Object.getOwnPropertyDescriptor(proto, 'seekable')) return;

  const native = Object.getOwnPropertyDescriptor(proto, 'seekable').get;

  Object.defineProperty(proto, 'seekable', {
    configurable: true,
    get() {
      const ranges = native.call(this);

      // Leave live streams alone
      if (!isFinite(this.duration)) return ranges;

      // If seekable already works, don’t interfere
      if (ranges && ranges.length > 0) return ranges;

      // Fake a full seekable range
      return {
        length: 1,
        start: () => 0,
        end: () => this.duration || 1
      };
    }
  });
})();

//Passive logger for seeing how the ads and youtube backend responds, and if it works
new PassiveLogger(() => {
  const v = document.querySelector('video');
  if (v && v.seekable.length === 0) {
    console.debug('[ad?] non-seekable video detected');
  }
}).observe(document.documentElement, { subtree: true, childList: true });

//TODO: figure out how to deploy this into pages just before url load... integration in engine_bridge maybe? 