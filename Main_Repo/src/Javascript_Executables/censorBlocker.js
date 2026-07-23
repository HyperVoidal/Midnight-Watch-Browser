// censorBlocker.js

const flavourTexts = [
    "Ad Blocker Active. Enjoy painless (but occasionally darkened) viewing!",
    "Ads blocked here (hopefully) still support the creator!",
    "Consider supporting the creator directly if you really like their content!",
    "Blocked ads, now with 90% less jumpscares",
    "I bet uBlock doesn't have these silly splash texts!",
    "Go do some exercise while you're waiting?"
];

const flavourDisplays = [
    "https://media1.tenor.com/m/zBc1XhcbTSoAAAAd/nyan-cat-rainbow.gif",
    "https://media.tenor.com/0EDznml5BDAAAAAj/cat-spinning.gif"
];

const bufferingTexts = "Midnight Watch is automatically fast-forwarding adverts, please stand by...";



(() => {
    // Escape subframes safely to avoid sandbox frame restrictions
    if (window.self !== window.top || window.location.href === 'about:blank') return;
    if (window.__ev_censor_loaded__) return;
    window.__ev_censor_loaded__ = true;

    // --- TRUSTED TYPES BYPASS POLICY FOR MSIX PACKAGES ---
    // If the browser enforces a TrustedHTML policy layout, we create a pass-through policy 
    // to prevent the script engine from crashing on element injection.
    let trustedHTMLPolicy = { createHTML: (string) => string };
    if (window.trustedTypes && window.trustedTypes.createPolicy) {
        try {
            trustedHTMLPolicy = window.trustedTypes.createPolicy('evAdBlockPolicy', {
                createHTML: (string) => string
            });
        } catch (e) {
            // Policy already exists or cannot be customized, fall back gracefully
            if (window.trustedTypes.defaultPolicy) {
                trustedHTMLPolicy = window.trustedTypes.defaultPolicy;
            }
        }
    }

    let wasAdShowingPreviously = false;
    let overlay = null;
    let layoutWrapper = null;
    let topLeftBadge = null;

    function initializeAdBlockDOM() {
        if (!document.head) return false;

        const styleNode = document.createElement('style');
        // Wrap assignment using our safe Trusted Types bypass layout policy
        styleNode.textContent = trustedHTMLPolicy.createHTML(`
            @keyframes evYtSpin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .ev-yt-spinner {
                width: 22px;
                height: 22px;
                border: 3px solid rgba(255, 255, 255, 0.2);
                border-top: 3px solid #ffffff;
                border-radius: 50%;
                animation: evYtSpin 0.8s linear infinite;
            }
        `);
        document.head.appendChild(styleNode);

        overlay = document.createElement('div');
        overlay.id = 'ev-ad-blackout-screen';
        overlay.style.position = 'absolute';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100%';
        overlay.style.height = '100%';
        overlay.style.backgroundColor = '#000000';
        overlay.style.zIndex = '9999';
        overlay.style.display = 'none'; 
        overlay.style.pointerEvents = 'none';

        topLeftBadge = document.createElement('div');
        topLeftBadge.style.position = 'absolute';
        topLeftBadge.style.top = '24px';
        topLeftBadge.style.left = '24px';
        topLeftBadge.style.display = 'flex';
        topLeftBadge.style.alignItems = 'center';
        topLeftBadge.style.gap = '12px';
        topLeftBadge.style.backgroundColor = 'rgba(0, 0, 0, 0.6)';
        topLeftBadge.style.padding = '8px 14px';
        topLeftBadge.style.borderRadius = '20px';
        topLeftBadge.style.backdropFilter = 'blur(4px)';
        overlay.appendChild(topLeftBadge);

        layoutWrapper = document.createElement('div');
        layoutWrapper.style.display = 'flex';
        layoutWrapper.style.justifyContent = 'center';
        layoutWrapper.style.alignItems = 'center';
        layoutWrapper.style.width = '100%';
        layoutWrapper.style.height = '100%';
        overlay.appendChild(layoutWrapper);

        return true;
    }

    setInterval(() => {
        if (!overlay) {
            const ok = initializeAdBlockDOM();
            if (!ok) return;
        }

        const playerContainer = document.querySelector('.html5-video-player');
        if (playerContainer && !document.getElementById('ev-ad-blackout-screen')) {
            playerContainer.appendChild(overlay);
        }

        const video = document.querySelector('video');
        const isAdShowing = playerContainer && (
            playerContainer.classList.contains('ad-showing') || 
            playerContainer.classList.contains('ad-mode') ||
            document.querySelector('.ytp-ad-player-overlay') !== null
        );

        if (video) {
            if (isAdShowing) {
                console.log("AD PLAYING!!! GETTEM BOYS!")
                if (!wasAdShowingPreviously) {
                    layoutWrapper.replaceChildren(); 
                    topLeftBadge.replaceChildren();

                    const spinnerElement = document.createElement('div');
                    spinnerElement.className = 'ev-yt-spinner';

                    const miniText = document.createElement('span');
                    miniText.innerText = bufferingTexts;
                    miniText.style.color = '#ffffff';
                    miniText.style.fontFamily = 'sans-serif';
                    miniText.style.fontSize = '13px';
                    miniText.style.fontWeight = '500';

                    topLeftBadge.appendChild(spinnerElement);
                    topLeftBadge.appendChild(miniText);

                    if (Math.random() < 0.5) {
                        const splashText = document.createElement('div');
                        splashText.innerText = flavourTexts[Math.floor(Math.random() * flavourTexts.length)];
                        splashText.style.color = '#ffffff';
                        splashText.style.fontFamily = 'sans-serif';
                        splashText.style.fontSize = '20px';
                        splashText.style.textAlign = 'center';
                        splashText.style.padding = '20px';
                        layoutWrapper.appendChild(splashText);
                    } else {
                        const imageDisplay = document.createElement('img');
                        imageDisplay.src = flavourDisplays[Math.floor(Math.random() * flavourDisplays.length)];
                        imageDisplay.style.maxWidth = '250px';
                        imageDisplay.style.maxHeight = '250px';
                        imageDisplay.style.borderRadius = '12px';
                        imageDisplay.style.boxShadow = '0px 8px 24px rgba(0,0,0,0.5)';
                        layoutWrapper.appendChild(imageDisplay);
                    }
                }
               

                overlay.style.display = 'block';
                video.muted = true;

                try {
                    if (video.playbackRate !== 16.0) {
                        video.playbackRate = 16.0;
                    }
                } catch (speedError) {
                    console.debug("AdBlock Tracker: Playback modification intercepted.");
                }
                
                wasAdShowingPreviously = true;

            } else {
                overlay.style.display = 'none';
                if (video.playbackRate === 16.0) {
                    video.playbackRate = 1.0;
                    video.muted = false;
                }
                wasAdShowingPreviously = false;
            }
        }

        const skipSelectors = ['.ytp-ad-skip-button', '.ytp-skip-ad-button', '.ytp-ad-skip-button-modern', '.ytp-ad-skip-button-slot'];
        const skipBtn = document.querySelector(skipSelectors.join(', '));
        if (skipBtn) skipBtn.click();

        const promotionBanners = document.querySelectorAll('.ytp-ad-message-container, .ytp-ad-overlay-container, ytd-banner-promoted-video-renderer, ytd-companion-slot-renderer');
        promotionBanners.forEach(el => el.remove());
    }, 200);
})();
