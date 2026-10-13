from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.value_objects.content import SongContent, TextContent
from backend.domain.value_objects.document import (
    Document,
    Heading,
    Line,
    ListItem,
    Paragraph,
    ParagraphMode,
)
from backend.domain.value_objects.question import Answers
from backend.domain.value_objects.source_input import LocalFile, PastedText
from backend.infrastructure.adapters.local_file_reader import LocalFileReader
from backend.infrastructure.readers.html_reader import HtmlReader
from backend.infrastructure.readers.markdown_reader import MarkdownReader
from backend.infrastructure.readers.plain_reader import PlainReader
from backend.infrastructure.readers.text_input import TEXT_KIND_QUESTION_ID

if TYPE_CHECKING:
    from pathlib import Path

FILES = LocalFileReader()
TEXT = Answers({TEXT_KIND_QUESTION_ID: "text"})
SONG = Answers({TEXT_KIND_QUESTION_ID: "song"})


def flow(*lines: str) -> Paragraph:
    return Paragraph(lines=tuple(Line(line) for line in lines), mode=ParagraphMode.FLOW)


def verse(*lines: str) -> Paragraph:
    return Paragraph(lines=tuple(Line(line) for line in lines), mode=ParagraphMode.LINES)


@pytest.mark.unit
class TestPlainReader:
    def test_asks_text_or_song_with_text_by_default(self) -> None:
        (question,) = PlainReader(FILES).questions(PastedText("Hi"))
        assert question.id == TEXT_KIND_QUESTION_ID
        assert question.option_ids == ("text", "song")
        assert question.default == "text"

    def test_text_is_paragraphs_apart_by_blank_lines(self) -> None:
        content = PlainReader(FILES).read(PastedText("One\ntwo.\n\n\nThree.\n"), TEXT)
        document = Document((flow("One", "two."), flow("Three.")))
        assert content == TextContent(title=None, document=document)

    def test_song_is_stanzas_of_lines(self) -> None:
        content = PlainReader(FILES).read(PastedText("- La la\n# Oh\n\nNa na\n"), SONG)
        assert content == SongContent(
            title=None, document=Document((verse("- La la", "# Oh"), verse("Na na")))
        )

    def test_file_is_named_after_itself(self, tmp_path: Path) -> None:
        path = tmp_path / "Lyrics of a song.txt"
        path.write_text("Hello")
        content = PlainReader(FILES).read(LocalFile(str(path)), SONG)
        assert content.title == "Lyrics of a song"


@pytest.mark.unit
class TestMarkdownReader:
    def test_keeps_headings_lists_and_paragraphs_without_markup(self) -> None:
        text = (
            "# Part *one*\n\nSome **bold** text\ngoes on.\n\nSub\n---\n\n"
            "1. First\n   - Inner [link](http://x)\n2. Second\n"
        )
        content = MarkdownReader(FILES).read(PastedText(text), TEXT)
        assert content.document == Document((
            Heading(1, "Part one"),
            flow("Some bold text goes on."),
            Heading(2, "Sub"),
            ListItem(lines=(Line("First"),), ordered=True, depth=0),
            ListItem(lines=(Line("Inner link"),), ordered=False, depth=1),
            ListItem(lines=(Line("Second"),), ordered=True, depth=0),
        ))

    def test_song_keeps_every_line_as_it_is(self) -> None:
        content = MarkdownReader(FILES).read(PastedText("# Chorus **loud**\n- yeah\n1. one"), SONG)
        assert content.document == Document((verse("# Chorus loud", "- yeah", "1. one"),))


@pytest.mark.unit
class TestHtmlReader:
    def test_reads_structure(self) -> None:
        markup = "<h2>Title</h2><p>Line one<br>line two</p><ul><li>Item</li></ul>"
        content = HtmlReader(FILES).read(PastedText(markup), TEXT)
        assert content.document == Document((
            Heading(2, "Title"),
            flow("Line one", "line two"),
            ListItem(lines=(Line("Item"),), ordered=False, depth=0),
        ))

    def test_song_is_lines_by_breaks(self) -> None:
        content = HtmlReader(FILES).read(PastedText("<p>Hello<br>darkness</p><p>Again</p>"), SONG)
        assert content.document == Document((verse("Hello", "darkness"), verse("Again")))
