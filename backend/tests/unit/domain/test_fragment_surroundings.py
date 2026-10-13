import pytest
from backend.domain.value_objects.document import (
    Document,
    Heading,
    Line,
    Paragraph,
    ParagraphMode,
)
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.fragment_surroundings import FragmentSurroundings

TEXT = "Wow, you guys sure have a lot of books about being a lesbian."
DOCUMENT = Document((
    Heading(1, "Title"),
    Paragraph(lines=(Line(TEXT), Line("Well, you know.")), mode=ParagraphMode.FLOW),
))


@pytest.mark.unit
class TestFragmentSurroundings:
    def test_text_around_the_phrase_as_the_screen_shows_it(self) -> None:
        start = TEXT.index("of books")
        phrase = DocumentPosition(1, 0, start, 0, len(TEXT))
        found = FragmentSurroundings.around(DOCUMENT, phrase, width=21)
        assert found == FragmentSurroundings(
            before="guys sure have a lot ", after=" Well, you know.",
        )

    def test_reaches_into_the_blocks_around(self) -> None:
        found = FragmentSurroundings.around(DOCUMENT, DocumentPosition(1, 0, 0, 0, 4), width=9)
        assert found == FragmentSurroundings(before="Title\n\n", after=" you guys")

    def test_phrase_without_a_place(self) -> None:
        assert FragmentSurroundings.around(DOCUMENT, None) is None

    def test_source_without_a_document(self) -> None:
        assert FragmentSurroundings.around(None, DocumentPosition(0, 0, 0, 0, 1)) is None
