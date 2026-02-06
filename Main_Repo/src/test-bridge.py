#For testing gatekeeper/engine-bridge functionality

from engine_bridge import is_url_safe

test_urls = [
    "https://google.com",
    "https://doubleclick.net",
    "https://duckduckgo.com"
]

for url in test_urls:
    safe = is_url_safe(url)
    status = "SAFE" if safe else "BLOCKED"
    print(f"[{status}] {url}")
