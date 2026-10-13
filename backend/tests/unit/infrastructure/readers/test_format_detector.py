from __future__ import annotations

import pytest
from backend.domain.exceptions import UnsupportedUrlError
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.source_input import LocalFile, PastedText, Url
from backend.infrastructure.adapters.regex_format_detector import RegexFormatDetector

from tests.unit.infrastructure.readers.fakes import YOUTUBE_URL, FakeYouTube

DETECTOR = RegexFormatDetector(FakeYouTube())


@pytest.mark.unit
class TestFormatDetector:
    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("/b/Book.EPUB", Format.EPUB),
            ("/n/notes.md", Format.MARKDOWN),
            ("/n/notes.markdown", Format.MARKDOWN),
            ("/p/page.htm", Format.HTML),
            ("/s/show.srt", Format.SRT),
            ("/v/movie.mkv", Format.VIDEO_FILE),
            ("/t/lyrics.txt", Format.PLAIN),
            ("/t/README", Format.PLAIN),
            ("/t/data.csv", Format.PLAIN),
        ],
    )
    def test_file_by_extension(self, path: str, expected: Format) -> None:
        assert DETECTOR.detect(LocalFile(path)) is expected

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("1\n00:00:01,000 --> 00:00:02,000\nHello", Format.SRT),
            ("<p>Hello <b>there</b></p>", Format.HTML),
            ("# Title\n\nText", Format.MARKDOWN),
            ("See [the docs](https://x.org).", Format.MARKDOWN),
            ("It was **very** good.", Format.MARKDOWN),
            ("- one\n- two", Format.MARKDOWN),
            ("- just one line that starts with a dash", Format.PLAIN),
            ("Plain prose, nothing else.\nAnother line.", Format.PLAIN),
            ("I <3 you and 2 > 1", Format.PLAIN),
        ],
    )
    def test_pasted_text_by_markup(self, text: str, expected: Format) -> None:
        assert DETECTOR.detect(PastedText(text)) is expected

    def test_youtube_link(self) -> None:
        assert DETECTOR.detect(Url(YOUTUBE_URL)) is Format.YOUTUBE

    def test_other_links_are_not_supported(self) -> None:
        with pytest.raises(UnsupportedUrlError):
            DETECTOR.detect(Url("https://genius.com/song"))
