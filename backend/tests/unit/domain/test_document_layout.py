from __future__ import annotations

import pytest
from backend.domain.services.document_layout import DocumentLayout
from backend.domain.services.document_time import time_of
from backend.domain.value_objects.document import (
    Document,
    Heading,
    Line,
    ListItem,
    Paragraph,
    ParagraphMode,
)
from backend.domain.value_objects.document_position import DocumentPosition

DOCUMENT = Document((
    Heading(1, "Title"),
    Paragraph((Line("I told him", 0, 900), Line("nothing.", 1000, 1500)), ParagraphMode.FLOW),
    Paragraph((Line("La la"), Line("na na")), ParagraphMode.LINES),
    ListItem(lines=(Line("Item"),), ordered=True, depth=0),
))
LAYOUT = DocumentLayout(DOCUMENT)


@pytest.mark.unit
class TestDocumentLayout:
    def test_text_is_the_document_text(self) -> None:
        assert LAYOUT.text == DOCUMENT.text == (
            "Title\n\nI told him\nnothing.\n\nLa la\nna na\n\nItem"
        )

    def test_offsets_become_a_position_and_back(self) -> None:
        start = LAYOUT.text.index("him")
        end = LAYOUT.text.index("nothing") + len("nothing")
        position = LAYOUT.position(start, end)
        assert position == DocumentPosition(1, 0, 7, 1, 7)
        assert LAYOUT.span(position) == (start, end)
        assert LAYOUT.fragment(position) == "him\nnothing"

    def test_heading_is_line_zero(self) -> None:
        assert LAYOUT.position(0, 5) == DocumentPosition(0, 0, 0, 0, 5)

    def test_lines_of_a_verse_keep_their_breaks(self) -> None:
        start = LAYOUT.text.index("la\nna")
        position = LAYOUT.position(start, start + 5)
        assert position == DocumentPosition(2, 0, 3, 1, 2)
        assert LAYOUT.fragment(position) == "la\nna"

    def test_a_piece_never_runs_across_blocks(self) -> None:
        with pytest.raises(ValueError, match="across blocks"):
            LAYOUT.position(0, LAYOUT.text.index("him"))

    def test_line_offset(self) -> None:
        assert LAYOUT.line_offset(2, 1) == LAYOUT.text.index("na na")


@pytest.mark.unit
class TestTimeOf:
    def test_from_the_first_line_to_the_last(self) -> None:
        assert time_of(DOCUMENT, DocumentPosition(1, 0, 7, 1, 7)) == (0, 1500)

    def test_untimed_lines_and_headings_have_no_time(self) -> None:
        assert time_of(DOCUMENT, DocumentPosition(2, 0, 0, 0, 2)) is None
        assert time_of(DOCUMENT, DocumentPosition(0, 0, 0, 0, 5)) is None
