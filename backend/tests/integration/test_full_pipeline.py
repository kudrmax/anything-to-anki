import pytest
from backend.application.dto.analysis_dtos import AnalyzeTextRequest
from backend.domain.services.document_layout import DocumentLayout
from backend.domain.value_objects.document import (
    Document,
    Heading,
    Line,
    Paragraph,
    ParagraphMode,
)
from backend.infrastructure.container import Container

B1 = AnalyzeTextRequest(user_level="B1")
PROSE = "The relentless pursuit of perfection often leads to burnout."


def _prose(*paragraphs: str) -> Document:
    return Document(tuple(
        Paragraph(lines=(Line(text),), mode=ParagraphMode.FLOW) for text in paragraphs
    ))


@pytest.mark.integration
class TestFullPipeline:
    def setup_method(self) -> None:
        self.container = Container()
        self.use_case = self.container.analyze_text_use_case()

    def test_basic_text(self) -> None:
        response = self.use_case.execute(_prose(PROSE), B1)

        assert response.total_tokens > 0
        assert len(response.candidates) > 0

        lemmas = {c.lemma for c in response.candidates}
        # These words should be above B1
        assert "relentless" in lemmas or "pursuit" in lemmas or "burnout" in lemmas

    def test_all_simple_words(self) -> None:
        response = self.use_case.execute(_prose("I have a big red cat."), B1)
        # All A1/A2 words — should have few or no candidates
        assert len(response.candidates) <= 1

    def test_candidates_have_fragments(self) -> None:
        response = self.use_case.execute(_prose(PROSE), B1)

        for candidate in response.candidates:
            assert candidate.context_fragment != ""
            assert candidate.phrase_words.phrase == candidate.context_fragment

    def test_candidates_have_sweet_spot_info(self) -> None:
        response = self.use_case.execute(_prose(PROSE), B1)

        for candidate in response.candidates:
            assert isinstance(candidate.is_sweet_spot, bool)
            assert candidate.zipf_frequency >= 0

    def test_phrase_is_the_piece_of_the_document_at_its_position(self) -> None:
        document = _prose("Nothing here.", PROSE)
        response = self.use_case.execute(document, B1)

        layout = DocumentLayout(document)
        for candidate in response.candidates:
            assert candidate.phrase_position is not None
            assert candidate.target_position is not None
            phrase = candidate.phrase_position.to_position()
            target = candidate.target_position.to_position()
            assert layout.fragment(phrase) == candidate.context_fragment
            assert phrase.block == target.block == 1
            assert layout.span(phrase)[0] <= layout.span(target)[0]
            assert layout.span(target)[1] <= layout.span(phrase)[1]

    def test_heading_is_a_phrase_of_its_own(self) -> None:
        document = Document((
            Heading(1, "A relentless ambition"),
            Paragraph(
                lines=(Line("Perfection often leads to burnout."),), mode=ParagraphMode.FLOW,
            ),
        ))
        response = self.use_case.execute(document, B1)

        relentless = next(c for c in response.candidates if c.lemma == "relentless")
        assert relentless.context_fragment == "A relentless ambition"
        assert relentless.phrase_position is not None
        assert relentless.phrase_position.block == 0

    def test_song_line_that_ends_a_sentence_ends_the_phrase(self) -> None:
        document = Document((
            Paragraph(
                lines=(
                    Line("I keep chasing the relentless dream"),
                    Line("You never call me back"),
                ),
                mode=ParagraphMode.LINES,
            ),
        ))
        response = self.use_case.execute(document, B1)

        relentless = next(c for c in response.candidates if c.lemma == "relentless")
        assert "\n" not in relentless.context_fragment
        assert "call" not in relentless.context_fragment
