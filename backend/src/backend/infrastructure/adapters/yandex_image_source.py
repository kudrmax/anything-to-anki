from __future__ import annotations

import html
import re
import urllib.parse
from functools import partial
from typing import TYPE_CHECKING

from backend.domain.exceptions import ImageSearchError
from backend.domain.ports.target_image_source import TargetImageSource
from backend.domain.value_objects.image_option import ImageOption
from backend.domain.value_objects.image_provider import ImageProvider
from backend.infrastructure.adapters.http_fetch import BROWSER_USER_AGENT, http_get

if TYPE_CHECKING:
    from collections.abc import Callable

SEARCH_URL = "https://yandex.com/images/search"
THUMBNAIL_HOST = "avatars.mds.yandex.net"
CAPTCHA_MARKER = "captcha"

_fetch_as_browser = partial(http_get, user_agent=BROWSER_USER_AGENT)

# The results page embeds its state as HTML-escaped JSON; every result has a
# "thumb" object whose protocol-relative URL points at Yandex's own servers.
_THUMBNAIL = re.compile(r'"thumb":\{"url":"(//avatars\.mds\.yandex\.net/i\?id=[^"]+)"')


class YandexImageSource(TargetImageSource):
    """Yandex image search read from its results page.

    Yandex has no free official API for this; the page layout is undocumented
    and may change. Under heavy use Yandex answers with a captcha instead —
    that counts as a failed lookup, so the other sources still show.
    """

    def __init__(self, fetch: Callable[[str], bytes] = _fetch_as_browser) -> None:
        self._fetch = fetch

    def find_images(self, word: str, limit: int) -> list[ImageOption]:
        query = urllib.parse.urlencode({"text": word})
        try:
            page = self._fetch(f"{SEARCH_URL}?{query}").decode("utf-8", errors="replace")
        except OSError as e:
            raise ImageSearchError(f"Yandex image search failed: {e}") from e

        state = html.unescape(page)
        urls = list(dict.fromkeys(f"https:{path}" for path in _THUMBNAIL.findall(state)))
        if not urls and CAPTCHA_MARKER in state.lower():
            raise ImageSearchError("Yandex image search asks for a captcha")
        return [ImageOption(url=url, provider=ImageProvider.YANDEX) for url in urls[:limit]]

    def owns(self, url: str) -> bool:
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme == "https" and parsed.hostname == THUMBNAIL_HOST
