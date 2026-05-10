(() => {
    const cleanAds = obj => {
        if (!obj || typeof obj !== 'object')
            return obj;

        delete obj.adPlacements;
        delete obj.playerAds;
        delete obj.adSlots;

        if (obj.streamingData?.serverAbrStreamingUrl) {
            delete obj.streamingData.serverAbrStreamingUrl;
        }

        return obj;
    };

    const originalFetch = window.fetch;

    window.fetch = async function (...args) {
        const url = args[0]?.toString?.() || "";

        // ===== ALLOWLIST =====
        if (
            url.includes("googlevideo.com") ||
            url.includes("ytimg.com") ||
            url.includes("/youtubei/v1/search") ||
            url.includes("/youtubei/v1/browse") ||
            url.includes("/youtubei/v1/next")
        ) {
            return originalFetch.apply(this, args);
        }

        // ===== FAKE SUCCESS TRACKERS =====
        if (
            url.includes("/pagead/") ||
            url.includes("doubleclick.net") ||
            url.includes("/ptracking") ||
            url.includes("/api/stats/") ||
            url.includes("/log_event")
        ) {
            console.log("Midnight Shield: FAKE OK", url);

            return new Response(
                "{}",
                {
                    status: 200,
                    headers: {
                        "Content-Type": "application/json"
                    }
                }
            );
        }

        // ===== NORMAL REQUEST =====
        const response = await originalFetch.apply(this, args);

        // ===== CLEAN PLAYER JSON =====
        try {
            if (
                url.includes("/player") ||
                url.includes("youtubei/v1/player")
            ) {

                const clone = response.clone();
                const json = await clone.json();

                cleanAds(json);

                return new Response(
                    JSON.stringify(json),
                    {
                        status: response.status,
                        statusText: response.statusText,
                        headers: response.headers
                    }
                );
            }
        } catch (e) {
            console.warn("Midnight Shield parse fail:", e);
        }

        return response;
    };

    // Hook ytInitialPlayerResponse
    Object.defineProperty(window, 'ytInitialPlayerResponse', {
        configurable: true,

        set(value) {
            this._ytInitialPlayerResponse = cleanAds(value);
        },

        get() {
            return this._ytInitialPlayerResponse;
        }
    });

    // Intercept JSON.parse
    const originalParse = JSON.parse;

    JSON.parse = function(...args) {
        const result = originalParse.apply(this, args);

        try {
            cleanAds(result);
        } catch (e) {}

        return result;
    };

    //injection stub to stop google from freaking out when parts of the api are blocked
    window.google = window.google || {};

    if (!window.google.dclc) {
        window.google.dclc = function() {
            return null;
        };
    }

    //repeatedly autoskip ads which are just clickable buttons
    setInterval(() => {
        const btn =
            document.querySelector('.ytp-ad-skip-button') ||
            document.querySelector('.ytp-skip-ad-button');

        if (btn) {
            btn.click();
        }
    }, 500);
})();