from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.exceptions import InvalidSourceInputError, UnsupportedUrlError
from backend.domain.ports.format_reader import FormatReader
from backend.domain.value_objects.content import SubtitlesContent, YouTubeVideo
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.source_input import Url
from backend.infrastructure.adapters.regex_srt_parser import RegexSrtParser
from backend.infrastructure.readers.subtitles import subtitles_document

if TYPE_CHECKING:
    from backend.domain.ports.url_source_fetcher import UrlSourceFetcher
    from backend.domain.value_objects.content import Content
    from backend.domain.value_objects.question import Answers, Question
    from backend.domain.value_objects.source_input import SourceInput


class YouTubeReader(FormatReader):
    """A YouTube video's subtitles; the video itself is downloaded later, on request."""

    def __init__(self, fetcher: UrlSourceFetcher) -> None:
        self._fetcher = fetcher
        self._parser = RegexSrtParser()

    @property
    def format(self) -> Format:
        return Format.YOUTUBE

    def questions(self, source_input: SourceInput) -> tuple[Question, ...]:
        return ()

    def read(self, source_input: SourceInput, answers: Answers) -> Content:
        if not isinstance(source_input, Url):
            msg = "A YouTube video is read from a link"
            raise InvalidSourceInputError(msg)
        if not self._fetcher.can_handle(source_input.url):
            raise UnsupportedUrlError(f"No fetcher for URL: {source_input.url}")
        fetched = self._fetcher.fetch_subtitles(source_input.url)
        return SubtitlesContent(
            title=fetched.title,
            document=subtitles_document(fetched.srt_text, self._parser),
            video=YouTubeVideo(url=source_input.url),
        )
