from __future__ import annotations

import html
import re
import urllib.parse
from functools import partial
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

from backend.domain.exceptions import ImageSearchError
from backend.domain.ports.target_image_source import TargetImageSource
from backend.domain.value_objects.image_option import ImageOption
from backend.domain.value_objects.image_provider import ImageProvider
from backend.infrastructure.adapters.http_fetch import BROWSER_USER_AGENT, http_get

if TYPE_CHECKING:
    from collections.abc import Callable

SEARCH_URL = "https://www.bing.com/images/async"
THUMBNAIL_HOST_SUFFIX = ".mm.bing.net"

_fetch_as_browser = partial(http_get, user_agent=BROWSER_USER_AGENT)

# Every result tile carries its metadata as HTML-escaped JSON in an `m` attribute.
_RESULT_METADATA = re.compile(r'\bm="(\{[^"]+\})"')


class _ResultMetadata(BaseModel):
    turl: str | None = None  # thumbnail served by Bing itself


class BingImageSource(TargetImageSource):
    """Bing image search through the endpoint its own results page loads tiles from.

    Bing has no free official API for this; the endpoint is undocumented and may
    change. Thumbnails come from Bing's own servers, so they always load, unlike
    originals scattered over third-party sites.
    """

    def __init__(
        self,
        fetch: Callable[[str], bytes] = _fetch_as_browser,
    ) -> None:
        self._fetch = fetch

    def find_images(self, word: str, limit: int) -> list[ImageOption]:
        query = urllib.parse.urlencode(
            {"q": word, "first": "0", "count": str(limit), "mmasync": "1"},
        )
        try:
            page = self._fetch(f"{SEARCH_URL}?{query}").decode("utf-8", errors="replace")
        except OSError as e:
            raise ImageSearchError(f"Bing image search failed: {e}") from e

        urls: list[str] = []
        for raw in _RESULT_METADATA.findall(page):
            try:
                thumbnail = _ResultMetadata.model_validate_json(html.unescape(raw)).turl
            except ValidationError:
                continue
            if thumbnail and self.owns(thumbnail) and thumbnail not in urls:
                urls.append(thumbnail)
        return [
            ImageOption(url=url, provider=ImageProvider.BING) for url in urls[:limit]
        ]

    def owns(self, url: str) -> bool:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or ""
        return parsed.scheme == "https" and host.endswith(THUMBNAIL_HOST_SUFFIX)
