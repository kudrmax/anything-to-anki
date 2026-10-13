from __future__ import annotations

import pytest
from backend.domain.value_objects.content import (
    BookContent,
    Kind,
    SongContent,
    SubtitlesContent,
    TextContent,
)
from backend.domain.value_objects.document import Document, Heading, Line, ListItem
from backend.domain.value_objects.question import Answers, Question, QuestionOption

EMPTY = Document(blocks=())


@pytest.mark.unit
class TestDocument:
    @pytest.mark.parametrize("level", [0, 7])
    def test_heading_level_out_of_range_is_rejected(self, level: int) -> None:
        with pytest.raises(ValueError, match="Heading level"):
            Heading(level=level, text="Title")

    def test_negative_list_depth_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="depth"):
            ListItem(lines=(Line("item"),), ordered=False, depth=-1)

    def test_line_needs_both_times_or_neither(self) -> None:
        with pytest.raises(ValueError, match="both start and end"):
            Line("Hello", start_ms=100)

    def test_line_cannot_end_before_it_starts(self) -> None:
        with pytest.raises(ValueError, match="ends before it starts"):
            Line("Hello", start_ms=200, end_ms=100)

    def test_timed_line(self) -> None:
        assert Line("Hello", start_ms=100, end_ms=100).end_ms == 100


@pytest.mark.unit
class TestContentKind:
    def test_each_content_reports_its_kind(self) -> None:
        assert TextContent(None, EMPTY).kind is Kind.TEXT
        assert BookContent(None, ()).kind is Kind.BOOK
        assert SubtitlesContent(None, EMPTY).kind is Kind.SUBTITLES
        assert SongContent(None, EMPTY).kind is Kind.SONG


@pytest.mark.unit
class TestQuestion:
    def test_default_must_be_an_option(self) -> None:
        with pytest.raises(ValueError, match="not an option"):
            Question(
                id="text.kind",
                prompt="What is it?",
                options=(QuestionOption("text", "Text"),),
                default="song",
            )

    def test_answers_by_question_id(self) -> None:
        answers = Answers({"text.kind": "song"})
        assert answers.get("text.kind") == "song"
        assert answers.has("text.kind")
        assert answers.get("book.split") is None
        assert not answers.has("book.split")
