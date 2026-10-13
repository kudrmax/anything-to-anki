from __future__ import annotations

import pytest
from backend.application.source_intake.typed_input import typed_input
from backend.domain.exceptions import InvalidSourceInputError
from backend.domain.value_objects.source_input import LocalFile, PastedText, Url

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("https://youtu.be/abc", Url("https://youtu.be/abc")),
        ("  HTTP://example.com/a  ", Url("HTTP://example.com/a")),
        ("/Users/me/book.epub", LocalFile("/Users/me/book.epub")),
        ("'/Users/me/My Book.epub'", LocalFile("'/Users/me/My Book.epub'")),
        ("~/notes.md", LocalFile("~/notes.md")),
        ("/Users/me/missing.txt", LocalFile("/Users/me/missing.txt")),
        ("Just a sentence.", PastedText("Just a sentence.")),
        ("/usr/bin is\na folder", PastedText("/usr/bin is\na folder")),
        ("https://x.org\nis a link in a text", PastedText("https://x.org\nis a link in a text")),
    ],
)
def test_what_was_typed(typed: str, expected: object) -> None:
    assert typed_input(typed) == expected


def test_subtitles_go_with_a_video_file() -> None:
    assert typed_input("/v/movie.mkv", " /v/movie.srt ") == LocalFile(
        "/v/movie.mkv", subtitles_path="/v/movie.srt",
    )


def test_subtitles_without_a_file_are_an_error() -> None:
    with pytest.raises(InvalidSourceInputError):
        typed_input("Some text", "/v/movie.srt")
