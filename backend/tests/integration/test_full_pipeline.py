import pytest
from backend.application.dto.analysis_dtos import AnalyzeTextRequest, OccurrenceDTO, WordDTO
from backend.application.use_cases.analyze_text import AnalyzeTextUseCase
from backend.domain.entities.source import Source
from backend.domain.services.document_layout import DocumentLayout
from backend.domain.services.phrasal_verb_detector import PhrasalVerbDetector
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.document import (
    Document,
    Heading,
    Line,
    Paragraph,
    ParagraphMode,
)
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.source_status import SourceStatus
from backend.infrastructure.api.dependencies import get_session_factory
from backend.infrastructure.container import Container
from backend.infrastructure.persistence.database import run_alembic_migrations
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository

B1 = AnalyzeTextRequest(user_level="B1")
PROSE = "The relentless pursuit of perfection often leads to burnout."


def _only(words: list[WordDTO], lemma: str) -> OccurrenceDTO:
    """The one occurrence of a word."""
    (occurrence,) = next(w for w in words if w.lemma == lemma).occurrences
    return occurrence


def _prose(*paragraphs: str) -> Document:
    return Document(tuple(
        Paragraph(lines=(Line(text),), mode=ParagraphMode.FLOW) for text in paragraphs
    ))


@pytest.fixture(scope="module", autouse=True)
def _migrated_database() -> None:
    """The container's analysis keeps parses in the tests' database."""
    run_alembic_migrations(str(get_session_factory().kw["bind"].url))


@pytest.mark.integration
class TestFullPipeline:
    def setup_method(self) -> None:
        self.container = Container()
        self.use_case = self.container.analyze_text_use_case()

    def test_basic_text(self) -> None:
        response = self.use_case.execute(_prose(PROSE), B1)

        assert response.total_tokens > 0
        assert len(response.words) > 0

        lemmas = {c.lemma for c in response.words}
        # These words should be above B1
        assert "relentless" in lemmas or "pursuit" in lemmas or "burnout" in lemmas

    def test_all_simple_words(self) -> None:
        response = self.use_case.execute(_prose("I have a big red cat."), B1)
        # All A1/A2 words — should have few or no candidates
        assert len(response.words) <= 1

    def test_candidates_have_fragments(self) -> None:
        response = self.use_case.execute(_prose(PROSE), B1)

        for word in response.words:
            for occurrence in word.occurrences:
                assert occurrence.phrase.text != ""
                assert occurrence.phrase.target

    def test_words_have_frequency(self) -> None:
        response = self.use_case.execute(_prose(PROSE), B1)

        for word in response.words:
            assert word.zipf_frequency >= 0

    def test_phrase_is_the_piece_of_the_document_at_its_position(self) -> None:
        document = _prose("Nothing here.", PROSE)
        response = self.use_case.execute(document, B1)

        layout = DocumentLayout(document)
        for word in response.words:
            for occurrence in word.occurrences:
                position = occurrence.phrase_position.to_position()
                assert layout.fragment(position) == occurrence.phrase.text
                assert position.block == 1

    def test_an_occurrence_is_keyed_where_the_target_of_its_phrase_starts(self) -> None:
        """One rule for every key — the analysis, a hand-added phrase, a migrated card —
        even where a phrase word is not one token ("self-esteem")."""
        document = _prose("Her fragile self-esteem collapsed under relentless scrutiny.")
        response = self.use_case.execute(document, B1)

        layout = DocumentLayout(document)
        keyed = {
            word.lemma: (
                occurrence.key.to_key(),
                layout.target_key(occurrence.phrase_position.to_position(), occurrence.phrase),
            )
            for word in response.words
            for occurrence in word.occurrences
        }
        assert "esteem" in keyed
        assert {lemma: own for lemma, (own, _) in keyed.items()} == {
            lemma: rule for lemma, (_, rule) in keyed.items()
        }

    def test_target_is_the_candidate_word_in_its_phrase(self) -> None:
        response = self.use_case.execute(_prose(PROSE), B1)

        for word in response.words:
            for occurrence in word.occurrences:
                target = [occurrence.phrase.words[i] for i in occurrence.phrase.target]
                assert target[0].lemma == word.lemma.split()[0]

    def test_heading_is_a_phrase_of_its_own(self) -> None:
        document = Document((
            Heading(1, "A relentless ambition"),
            Paragraph(
                lines=(Line("Perfection often leads to burnout."),), mode=ParagraphMode.FLOW,
            ),
        ))
        response = self.use_case.execute(document, B1)

        relentless = _only(response.words, "relentless")
        assert relentless.phrase.text == "A relentless ambition"
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

        relentless = _only(response.words, "relentless")
        assert "\n" not in relentless.phrase.text
        assert "call" not in relentless.phrase.text

    def test_cached_parse_gives_the_same_analysis(self) -> None:
        document = Document((
            Heading(1, "A relentless ambition"),
            Paragraph(
                lines=(Line("I keep chasing the relentless dream"), Line("You never call")),
                mode=ParagraphMode.LINES,
            ),
            Paragraph(lines=(Line(PROSE), Line("It never ends.")), mode=ParagraphMode.FLOW),
        ))
        uncached = AnalyzeTextUseCase(
            document_analyzer=self.container._document_analyzer,
            cefr_classifier=self.container._cefr_classifier,
            frequency_provider=self.container._frequency_provider,
            phrasal_verb_detector=PhrasalVerbDetector(self.container._phrasal_verb_dictionary),
            fragment_selection_config=self.container._fragment_selection_config,
            usage_lookup=self.container._usage_source,
        )

        expected = uncached.execute(document, B1)
        self.use_case.execute(document, B1)
        cached = self.use_case.execute(document, B1)

        assert cached == expected


@pytest.mark.integration
class TestRebuildWithTheRealAnalysis:
    def test_a_rebuild_after_processing_has_nothing_to_update(self) -> None:
        container = Container()
        session = get_session_factory()()
        try:
            source = SqlaSourceRepository(session).create(Source(
                status=SourceStatus.NEW, format=Format.PLAIN, kind=Kind.TEXT, title="rebuild",
            ))
            assert source.id is not None
            SqlaDocumentRepository(session).save(source.id, Document((
                Heading(1, "A relentless ambition"),
                Paragraph(
                    lines=(Line(PROSE), Line("The relentless rain never stopped.")),
                    mode=ParagraphMode.FLOW,
                ),
            )))
            session.commit()
            process = container.process_source_use_case(session)
            process.start(source.id)
            session.commit()
            process.execute(source.id)

            preview = container.rebuild_source_use_case(session).preview(source.id)

            assert preview.without_open.nothing_to_update
            assert preview.with_open.nothing_to_update
        finally:
            session.rollback()
            if source.id is not None:
                container.delete_source_use_case(session).execute(source.id)
                session.commit()
            session.close()
