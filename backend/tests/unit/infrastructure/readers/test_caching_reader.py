from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.ports.format_reader import FormatReader
from backend.domain.value_objects.content import TextContent
from backend.domain.value_objects.document import Document
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.question import Answers, Question, QuestionOption
from backend.domain.value_objects.source_input import LocalFile, Url
from backend.infrastructure.readers.caching_reader import CachingFormatReader

if TYPE_CHECKING:
    from pathlib import Path

    from backend.domain.value_objects.content import Content
    from backend.domain.value_objects.source_input import SourceInput

pytestmark = pytest.mark.unit

KIND = Question(
    id="text.kind", prompt="Text or song?", default="text",
    options=(QuestionOption(id="text", label="Text"), QuestionOption(id="song", label="Song")),
)


class _CountingReader(FormatReader):
    def __init__(self) -> None:
        self.reads = 0
        self.asked = 0

    @property
    def format(self) -> Format:
        return Format.PLAIN

    def questions(self, source_input: SourceInput) -> tuple[Question, ...]:
        self.asked += 1
        return (KIND,)

    def read(self, source_input: SourceInput, answers: Answers) -> Content:
        self.reads += 1
        return TextContent(title=str(self.reads), document=Document(blocks=()))


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _setup(tmp_path: Path) -> tuple[CachingFormatReader, _CountingReader, _Clock, LocalFile]:
    inner = _CountingReader()
    clock = _Clock()
    path = tmp_path / "a.txt"
    path.write_text("one")
    return CachingFormatReader(inner, clock=clock), inner, clock, LocalFile(str(path))


TEXT = Answers({"text.kind": "text"})


class TestCachingFormatReader:
    def test_reading_again_reuses_the_content(self, tmp_path: Path) -> None:
        reader, inner, _, file = _setup(tmp_path)

        first = reader.read(file, TEXT)
        again = reader.read(file, Answers({"text.kind": "text", "book.split": "split"}))

        assert again is first
        assert inner.reads == 1

    def test_questions_are_asked_once(self, tmp_path: Path) -> None:
        reader, inner, _, file = _setup(tmp_path)

        assert reader.questions(file) == reader.questions(file) == (KIND,)
        assert inner.asked == 1

    def test_another_answer_reads_again(self, tmp_path: Path) -> None:
        reader, inner, _, file = _setup(tmp_path)

        reader.read(file, TEXT)
        reader.read(file, Answers({"text.kind": "song"}))

        assert inner.reads == 2

    def test_a_changed_file_is_read_again(self, tmp_path: Path) -> None:
        reader, inner, _, file = _setup(tmp_path)

        reader.read(file, TEXT)
        (tmp_path / "a.txt").write_text("changed and longer")
        reader.read(file, TEXT)

        assert inner.reads == 2

    def test_an_old_read_expires(self, tmp_path: Path) -> None:
        reader, inner, clock, _ = _setup(tmp_path)
        link = Url("https://youtu.be/abc")

        reader.read(link, TEXT)
        clock.now += 11 * 60
        reader.read(link, TEXT)

        assert inner.reads == 2
