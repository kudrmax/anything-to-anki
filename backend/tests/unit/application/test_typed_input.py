from __future__ import annotations

import pytest
from backend.application.source_intake.typed_input import typed_input, typed_inputs
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


def test_several_paths_are_several_files() -> None:
    assert typed_inputs("/a/1.txt\n\n'/a/My 2.md'\n") == [
        LocalFile("/a/1.txt"), LocalFile("'/a/My 2.md'"),
    ]


def test_one_line_is_what_typed_input_reads() -> None:
    assert typed_inputs("/a/1.txt") == [LocalFile("/a/1.txt")]


@pytest.mark.parametrize(
    "typed",
    ["First line.\nSecond line.", "/a/1.txt\nand some words", "https://x.org\n/a/1.txt"],
)
def test_lines_that_are_not_all_paths_are_text(typed: str) -> None:
    assert typed_inputs(typed) == [PastedText(typed)]


def test_subtitles_go_with_one_file_only() -> None:
    with pytest.raises(InvalidSourceInputError):
        typed_inputs("/v/a.mkv\n/v/b.mkv", "/v/a.srt")
