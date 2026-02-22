//payload - seeker force-enable for embedded video ads to skip them without needing direct knowledge of ad names
// embeddedadblocker.js
(() => {
  const proto = HTMLMediaElement.prototype;
  
  // Get the current descriptor
  const descriptor = Object.getOwnPropertyDescriptor(proto, 'seekable');

  // If we can't find it or it's already locked by the browser/site, exit
  if (!descriptor || descriptor.configurable === false) {
    return;
  }

  const native = descriptor.get;

  try {
    Object.defineProperty(proto, 'seekable', {
      configurable: true, // MUST be true so it can be updated if the page reloads
      enumerable: true,
      get() {
        try {
          const ranges = native.call(this);

          // If it's a valid video and ranges are empty (typical of blocked ads), fake it
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
          return native.call(this);
        }
      }
    });
  } catch (e) {
    //Release fail state if another script beat it to the lock
    console.log("AdBlocker: seekable property already locked.");
  }
})();


//Passive logger for seeing how the ads and youtube backend responds, and if it works

/* new PassiveLogger(() => {
  const v = document.querySelector('video');
  if (v && v.seekable.length === 0) {
    console.debug('[ad?] non-seekable video detected');
  }
}).observe(document.documentElement, { subtree: true, childList: true });
 */

//TODO: figure out how to deploy these into pages just before url load... integration in network_contoller maybe? 