from __future__ import annotations

import json
import re
import urllib.parse
from functools import partial
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from backend.domain.exceptions import ImageSearchError
from backend.domain.ports.target_image_source import TargetImageSource
from backend.domain.value_objects.image_option import ImageOption
from backend.domain.value_objects.image_provider import ImageProvider
from backend.infrastructure.adapters.http_fetch import APP_USER_AGENT, http_get

if TYPE_CHECKING:
    from collections.abc import Callable

WIKTIONARY_API = "https://en.wiktionary.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
# Commons serves thumbnails from one host and originals from another.
IMAGE_HOSTS = frozenset({"thumb.wikimedia.org", "upload.wikimedia.org"})
THUMB_WIDTH_PX = 500
PICTURE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".tif", ".tiff")

_ENGLISH_HEADING = re.compile(r"^==\s*English\s*==\s*$", re.MULTILINE)
_LANGUAGE_HEADING = re.compile(r"^==[^=].*==\s*$", re.MULTILINE)
_FILE_LINK = re.compile(r"\[\[\s*(?:File|Image)\s*:\s*([^|\]]+)", re.IGNORECASE)
_GALLERY = re.compile(r"<gallery[^>]*>(.*?)</gallery>", re.IGNORECASE | re.DOTALL)
_GALLERY_LINE = re.compile(
    r"^\s*(?:File:|Image:)?([^|\n]+\.(?:jpe?g|png|gif|svg|webp|tiff?))",
    re.IGNORECASE | re.MULTILINE,
)
_fetch_as_app = partial(http_get, user_agent=APP_USER_AGENT)


class _Slot(BaseModel):
    content: str


class _Slots(BaseModel):
    main: _Slot


class _Revision(BaseModel):
    slots: _Slots


class _ImageInfo(BaseModel):
    thumburl: str | None = None


class _Page(BaseModel):
    title: str
    revisions: list[_Revision] = Field(default_factory=list)
    imageinfo: list[_ImageInfo] = Field(default_factory=list)


class _TitleChange(BaseModel):
    source: str = Field(alias="from")
    target: str = Field(alias="to")


class _Query(BaseModel):
    pages: list[_Page] = Field(default_factory=list)
    normalized: list[_TitleChange] = Field(default_factory=list)


class _ApiResponse(BaseModel):
    """The slice of a MediaWiki API answer (formatversion=2) this source reads."""

    query: _Query = Field(default_factory=_Query)


class WiktionaryImageSource(TargetImageSource):
    """Pictures editors placed in the English entry of a word on Wiktionary.

    Few words have one, but when they do it shows exactly that word. Entries of
    other languages on the same page are ignored.
    """

    def __init__(
        self,
        fetch: Callable[[str], bytes] = _fetch_as_app,
    ) -> None:
        self._fetch = fetch

    def find_images(self, word: str) -> list[ImageOption]:
        file_names = self._entry_picture_names(word)
        if not file_names:
            return []
        return [
            ImageOption(url=url, provider=ImageProvider.WIKTIONARY)
            for url in self._thumbnail_urls(file_names)
        ]

    def owns(self, url: str) -> bool:
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme == "https" and parsed.hostname in IMAGE_HOSTS

    def _entry_picture_names(self, word: str) -> list[str]:
        response = self._query(WIKTIONARY_API, {
            "prop": "revisions", "rvprop": "content", "rvslots": "main",
            "titles": word, "redirects": "1",
        })
        pages = [page for page in response.query.pages if page.revisions]
        if not pages:
            return []
        section = _english_section(pages[0].revisions[0].slots.main.content)
        return _picture_names(section) if section is not None else []

    def _thumbnail_urls(self, file_names: list[str]) -> list[str]:
        titles = [f"File:{name}" for name in file_names]
        response = self._query(COMMONS_API, {
            "prop": "imageinfo", "iiprop": "url", "iiurlwidth": str(THUMB_WIDTH_PX),
            "titles": "|".join(titles),
        })
        renamed = {change.source: change.target for change in response.query.normalized}
        thumbs = {
            page.title: page.imageinfo[0].thumburl
            for page in response.query.pages
            if page.imageinfo
        }
        urls = [thumbs.get(renamed.get(title, title)) for title in titles]
        return [url for url in urls if url]

    def _query(self, api: str, params: dict[str, str]) -> _ApiResponse:
        query = urllib.parse.urlencode(
            {"action": "query", **params, "format": "json", "formatversion": "2"},
        )
        try:
            return _ApiResponse.model_validate(json.loads(self._fetch(f"{api}?{query}")))
        except (OSError, ValueError) as e:
            raise ImageSearchError(f"Wiktionary lookup failed: {e}") from e


def _english_section(wikitext: str) -> str | None:
    start = _ENGLISH_HEADING.search(wikitext)
    if start is None:
        return None
    rest = wikitext[start.end():]
    end = _LANGUAGE_HEADING.search(rest)
    return rest[: end.start()] if end else rest


def _picture_names(section: str) -> list[str]:
    names = [name.strip() for name in _FILE_LINK.findall(section)]
    for gallery in _GALLERY.findall(section):
        names += [name.strip() for name in _GALLERY_LINE.findall(gallery)]
    unique = dict.fromkeys(names)
    return [name for name in unique if name.lower().endswith(PICTURE_EXTENSIONS)]

