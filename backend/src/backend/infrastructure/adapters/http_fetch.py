from __future__ import annotations

import urllib.request

# Wikimedia asks API clients to name themselves instead of posing as a browser.
APP_USER_AGENT = "AnythingToAnki/1.0 (local language-learning tool)"
# Bing serves its image search only to something that looks like a desktop browser.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36"
)
DEFAULT_TIMEOUT_S = 10.0


def http_get(url: str, *, user_agent: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})  # noqa: S310 — callers pass https URLs they build
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 — same
        body: bytes = resp.read()
    return body
