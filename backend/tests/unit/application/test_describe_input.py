"""Как экран Add описывает ввод без разбора spaCy.

Ссылки, файлы, пустой, многострочный, длинный и не английский ввод.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.application.use_cases.describe_input import MAX_PHRASE_CHARS, DescribeInputUseCase
from backend.domain.ports.file_reader import FileReader
from backend.domain.ports.text_analyzer import TextAnalyzer
from backend.domain.services.input_kind_classifier import InputKindClassifier
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.input_kind import InputKind
from backend.domain.value_objects.input_problem import InputProblem
from backend.infrastructure.adapters.regex_format_detector import RegexFormatDetector

from tests.unit.infrastructure.readers.fakes import YOUTUBE_URL, FakeYouTube

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData

EXISTING_FILES = frozenset({
    "/Users/max/Books/Twig.epub",
    "/Users/max/Movies/Friends s01e01.mkv",
    "/Users/max/notes.md",
    "/Users/max/lyrics.txt",
    "/Users/max/show.srt",
})


class FakeFiles(FileReader):
    def exists(self, path: str) -> bool:
        return path in EXISTING_FILES

    def read_text(self, path: str) -> str:
        raise AssertionError("describing input never reads a file")


class NoParsing(TextAnalyzer):
    """Эти вводы описываются без spaCy: разбор на каждое нажатие клавиши слишком дорог."""

    def analyze(self, text: str) -> list[TokenData]:
        raise AssertionError(f"spaCy must not be called for {text!r}")


def describe(text: str):  # noqa: ANN201 — DTO из application, тип выводится
    return DescribeInputUseCase(
        detector=RegexFormatDetector(FakeYouTube()),
        file_reader=FakeFiles(),
        text_analyzer=NoParsing(),
        classifier=InputKindClassifier(),
    ).execute(text)


@pytest.mark.parametrize("text", ["", " ", "   ", "\n", "\n\n  \t\n"])
def test_empty_input_has_no_description(text: str) -> None:
    described = describe(text)
    assert described.model_dump() == dict.fromkeys(described.model_dump())


@pytest.mark.parametrize(
    "text",
    [YOUTUBE_URL, f"  {YOUTUBE_URL}  ", f"{YOUTUBE_URL}\n"],
)
def test_youtube_link_is_a_video_source(text: str) -> None:
    described = describe(text)
    assert (described.kind, described.format, described.label, described.problem) == (
        InputKind.SOURCE, Format.YOUTUBE, "Video · YouTube", None,
    )


@pytest.mark.parametrize(
    "text",
    [
        "https://example.com/some-article",
        "http://news.site/2024/story.html",
        "https://vimeo.com/123",
        "HTTPS://EXAMPLE.COM",
    ],
)
def test_link_nobody_reads_is_a_problem(text: str) -> None:
    described = describe(text)
    assert (described.kind, described.label) == (None, None)
    assert described.problem == InputProblem.UNSUPPORTED_LINK
    assert described.problem_message
    assert described.problem_hint


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("/Users/max/Books/Twig.epub", "Book · epub"),
        ("'/Users/max/Books/Twig.epub'", "Book · epub"),
        ('"/Users/max/Books/Twig.epub"', "Book · epub"),
        ("/Users/max/Movies/Friends\\ s01e01.mkv", "Video · mkv"),
        ("/Users/max/notes.md", "Text · markdown"),
        ("/Users/max/lyrics.txt", "Text · txt"),
        ("/Users/max/show.srt", "Subtitles · srt"),
    ],
)
def test_existing_file_is_a_source(text: str, label: str) -> None:
    described = describe(text)
    assert (described.kind, described.label, described.problem) == (InputKind.SOURCE, label, None)


@pytest.mark.parametrize(
    "text",
    [
        "/Users/max/Books/Twig2.epub",
        "/Users/max/Books",
        "/Users/max/Movies/missing.mkv",
        "'/no/such/file.txt'",
        "/",
    ],
)
def test_path_without_a_file_is_a_problem(text: str) -> None:
    described = describe(text)
    assert (described.kind, described.label) == (None, None)
    assert described.problem == InputProblem.FILE_NOT_FOUND
    assert described.problem_message
    assert described.problem_hint


@pytest.mark.parametrize(
    "text",
    [
        "First line\nSecond line",
        "She shrugged off the comment\nand kept walking.",
        "Is this the real life?\nIs this just fantasy?\nCaught in a landslide",
        "# Chapter 1\n\nIt was a bright cold day in April.",
        "1\n00:00:01,000 --> 00:00:02,000\nHello there.\n",
        "медицина\nкак пожаловаться",
        "make a decision\ndeal with a boss",
        "<p>Hello</p>\n<p>World</p>",
    ],
)
def test_more_than_one_line_is_a_text_source(text: str) -> None:
    assert describe(text).kind == InputKind.SOURCE


def test_long_single_line_is_a_text_source() -> None:
    line = "word " * (MAX_PHRASE_CHARS // 5 + 1)
    assert describe(line).kind == InputKind.SOURCE


@pytest.mark.parametrize(
    "text",
    [
        "медицина",
        "как пожаловаться начальнику",
        "Как вернуть товар в магазин?",
        "Она отмахнулась от замечания и пошла дальше.",
        "тема: phrasal verbs",
        "фразовые глаголы с get",
        "give up — сдаться",
        "日本語",
        "123",
        "!!!",
    ],
)
def test_line_not_in_english_is_a_topic(text: str) -> None:
    described = describe(text)
    assert (described.kind, described.problem, described.label) == (InputKind.TOPIC, None, None)


def test_several_existing_files_are_a_batch() -> None:
    described = describe("/Users/max/notes.md\n/Users/max/lyrics.txt")
    assert (described.kind, described.format, described.label, described.problem) == (
        InputKind.SOURCE, None, "2 files", None,
    )


def test_a_missing_file_in_a_batch_is_named() -> None:
    described = describe("/Users/max/notes.md\n/Users/max/missing chapter.txt")
    assert described.problem == InputProblem.FILE_NOT_FOUND
    assert described.problem_message == "No file at this path: missing chapter.txt"
    assert described.kind is None
