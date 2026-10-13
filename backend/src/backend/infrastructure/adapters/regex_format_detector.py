from __future__ import annotations

import re
from pathlib import PurePath
from typing import TYPE_CHECKING

from backend.domain.exceptions import UnsupportedUrlError
from backend.domain.ports.format_detector import FormatDetector
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.source_input import LocalFile, PastedText, Url

if TYPE_CHECKING:
    from backend.domain.ports.url_source_fetcher import UrlSourceFetcher
    from backend.domain.value_objects.source_input import SourceInput

# Any other file is read as plain text.
FORMAT_BY_EXTENSION: dict[str, Format] = {
    ".md": Format.MARKDOWN,
    ".markdown": Format.MARKDOWN,
    ".html": Format.HTML,
    ".htm": Format.HTML,
    ".epub": Format.EPUB,
    ".srt": Format.SRT,
    ".mp4": Format.VIDEO_FILE,
    ".mkv": Format.VIDEO_FILE,
    ".avi": Format.VIDEO_FILE,
    ".mov": Format.VIDEO_FILE,
}

_SRT_TIMECODE_RE = re.compile(r"^\s*\d{1,2}:\d{2}:\d{2}[,.]\d{3}\s*-->", re.MULTILINE)
_HTML_TAG_RE = re.compile(
    r"<(?:p|div|br|h[1-6]|ul|ol|li|span|a|em|strong|b|i|html|body|article|section|"
    r"blockquote|table)\b[^>]*>",
    re.IGNORECASE,
)
_MARKDOWN_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s{0,3}#{1,6}\s+\S", re.MULTILINE),
    re.compile(r"\[[^\]\n]+\]\([^)\s]+\)"),
    re.compile(r"\*\*\S[^\n]*?\*\*|__\S[^\n]*?__"),
    re.compile(r"^\s*(```|~~~)", re.MULTILINE),
)
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d{1,9}[.)])\s+\S", re.MULTILINE)
# One line that looks like a list item is just a line; a list has several.
MIN_LIST_ITEMS = 2


class RegexFormatDetector(FormatDetector):
    """Tells the format of a file by its extension and of pasted text by its markup."""

    def __init__(self, url_fetcher: UrlSourceFetcher) -> None:
        self._url_fetcher = url_fetcher

    def detect(self, source_input: SourceInput) -> Format:
        match source_input:
            case LocalFile():
                return FORMAT_BY_EXTENSION.get(
                    PurePath(source_input.path).suffix.lower(), Format.PLAIN
                )
            case PastedText():
                return self._pasted_format(source_input.text)
            case Url():
                if self._url_fetcher.can_handle(source_input.url):
                    return Format.YOUTUBE
                raise UnsupportedUrlError(f"No fetcher for URL: {source_input.url}")

    def _pasted_format(self, text: str) -> Format:
        if _SRT_TIMECODE_RE.search(text):
            return Format.SRT
        if _HTML_TAG_RE.search(text):
            return Format.HTML
        is_markdown = any(pattern.search(text) for pattern in _MARKDOWN_RES) or (
            len(_LIST_ITEM_RE.findall(text)) >= MIN_LIST_ITEMS
        )
        return Format.MARKDOWN if is_markdown else Format.PLAIN
