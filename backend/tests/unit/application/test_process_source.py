from unittest.mock import MagicMock

import pytest
from backend.application.dto.analysis_dtos import (
    AnalyzeTextResponse,
    OccurrenceDTO,
    OccurrenceKeyDTO,
    WordDTO,
)
from backend.application.dto.document_dtos import DocumentPositionDTO
from backend.application.use_cases.process_source import ProcessSourceUseCase
from backend.domain.entities.occurrence import OccurrenceKey
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import (
    SourceAlreadyProcessedError,
    SourceHasNoDocumentError,
    SourceNotFoundError,
)
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.source_status import SourceStatus

from tests.candidate_sorter_support import threshold_resolver
from tests.phrase_support import phrase
from tests.vocabulary_support import user_vocabulary


def _occurrence(
    text: str, target: str | None = None, *, score: float = 0.0, char: int = 0,
) -> OccurrenceDTO:
    return OccurrenceDTO(
        phrase=phrase(text, target),
        phrase_position=DocumentPositionDTO(
            block=0, start_line=0, start_char=char, end_line=0, end_char=char + len(text),
        ),
        key=OccurrenceKeyDTO(block=0, line=0, char=char),
        fragment_score=score,
    )


DOCUMENT = Document((Paragraph(lines=(Line("Hello world"),), mode=ParagraphMode.FLOW),))


def _make_use_case() -> tuple[ProcessSourceUseCase, dict[str, MagicMock]]:
    mocks = {
        "source_repo": MagicMock(),
        "candidate_repo": MagicMock(),
        "known_word_repo": MagicMock(),
        "settings_repo": MagicMock(),
        "analyze_text": MagicMock(),
        "document_repo": MagicMock(),
    }
    mocks["document_repo"].get.return_value = DOCUMENT
    uc = ProcessSourceUseCase(
        source_repo=mocks["source_repo"],
        candidate_repo=mocks["candidate_repo"],
        vocabulary=user_vocabulary(mocks["known_word_repo"]),
        settings_repo=mocks["settings_repo"],
        threshold_resolver=threshold_resolver(mocks["settings_repo"]),
        analyze_text_use_case=mocks["analyze_text"],
        document_repo=mocks["document_repo"],
    )
    return uc, mocks


@pytest.mark.unit
class TestProcessSourceStart:
    def test_start_sets_processing(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, status=SourceStatus.NEW, format=Format.PLAIN, kind=Kind.TEXT,
            )
        uc.start(1)
        mocks["source_repo"].update_status.assert_called_once_with(
            1, SourceStatus.PROCESSING,
        )

    def test_start_not_found(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = None
        with pytest.raises(SourceNotFoundError):
            uc.start(999)

    def test_start_already_done(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, status=SourceStatus.DONE, format=Format.PLAIN, kind=Kind.TEXT,
            )
        with pytest.raises(SourceAlreadyProcessedError):
            uc.start(1)

    def test_start_allows_error_retry(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, status=SourceStatus.ERROR, format=Format.PLAIN, kind=Kind.TEXT,
            )
        uc.start(1)
        mocks["source_repo"].update_status.assert_called_once()


@pytest.mark.unit
class TestProcessSourceExecute:
    def test_execute_saves_candidates(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, status=SourceStatus.PROCESSING, format=Format.PLAIN, kind=Kind.TEXT,
            )
        mocks["settings_repo"].get.return_value = "B1"
        mocks["known_word_repo"].get_all_pairs.return_value = set()
        mocks["analyze_text"].execute.return_value = AnalyzeTextResponse(
            text="Hello world",
            words=[
                WordDTO(
                    lemma="ubiquitous", pos="ADJ", cefr_level="C1",
                    zipf_frequency=3.2,
                    occurrences=[_occurrence("ubiquitous presence")],
                ),
            ],
            total_tokens=5,
            unique_lemmas=3,
        )
        uc.execute(1)
        mocks["candidate_repo"].create_batch.assert_called_once()
        # 1 stage update + 1 final DONE update
        assert mocks["source_repo"].update_status.call_count == 2
        final_call = mocks["source_repo"].update_status.call_args_list[-1]
        assert final_call[0][1] == SourceStatus.DONE

    def test_execute_passes_usage_distribution(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, status=SourceStatus.PROCESSING, format=Format.PLAIN, kind=Kind.TEXT,
            )
        mocks["settings_repo"].get.return_value = "B1"
        mocks["known_word_repo"].get_all_pairs.return_value = set()
        mocks["analyze_text"].execute.return_value = AnalyzeTextResponse(
            text="dodgy deal",
            words=[
                WordDTO(
                    lemma="dodgy", pos="ADJ", cefr_level="B2",
                    zipf_frequency=3.3,
                    occurrences=[_occurrence("dodgy deal")],
                    usage_distribution={"informal": 1.0},
                ),
            ],
            total_tokens=2,
            unique_lemmas=1,
        )
        uc.execute(1)
        created = mocks["candidate_repo"].create_batch.call_args[0][0]
        assert len(created) == 1
        assert created[0].usage_distribution is not None
        assert created[0].usage_distribution.groups == {"informal": 1.0}

    def test_execute_passes_known_words_and_threshold_to_analysis(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, status=SourceStatus.PROCESSING, format=Format.PLAIN, kind=Kind.TEXT,
            )
        settings = {"cefr_level": "B1", "frequent_word_threshold": "5.0"}
        mocks["settings_repo"].get.side_effect = lambda key, default=None: settings.get(
            key, default,
        )
        mocks["known_word_repo"].get_all_pairs.return_value = {
            ("Pursuit", "NOUN"), ("divorce", None),
        }
        mocks["analyze_text"].execute.return_value = AnalyzeTextResponse(
            text="Hello", words=[], total_tokens=1, unique_lemmas=1,
        )
        uc.execute(1)
        document, request = mocks["analyze_text"].execute.call_args[0]
        assert document == DOCUMENT
        assert request.vocabulary.known == frozenset({"pursuit", "divorce"})
        assert request.frequent_word_zipf == 5.0

    def test_execute_saves_the_phrase_as_source_phrase(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, status=SourceStatus.PROCESSING, format=Format.PLAIN, kind=Kind.TEXT,
            )
        mocks["settings_repo"].get.return_value = "B1"
        mocks["known_word_repo"].get_all_pairs.return_value = set()
        mocks["analyze_text"].execute.return_value = AnalyzeTextResponse(
            text="Hello",
            words=[
                WordDTO(
                    lemma="paleontology", pos="NOUN", cefr_level="C1",
                    zipf_frequency=2.8,
                    occurrences=[
                        _occurrence("So on a dare, I picked paleontology.", "paleontology"),
                    ],
                ),
            ],
            total_tokens=8,
            unique_lemmas=7,
        )
        uc.execute(1)
        created = mocks["candidate_repo"].create_batch.call_args[0][0]
        assert created[0].source_phrase == phrase(
            "So on a dare, I picked paleontology.", "paleontology",
        )

    def test_word_gets_the_phrase_of_its_best_occurrence(self) -> None:
        created = self._process(WordDTO(
            lemma="glare", pos="NOUN", cefr_level="C1", zipf_frequency=3.0,
            occurrences=[
                _occurrence("a glare here", "glare", score=5.0, char=0),
                _occurrence("the glare there", "glare", score=2.0, char=20),
                _occurrence("one glare more", "glare", score=2.0, char=40),
            ],
        ))
        assert created[0].source_phrase.text == "the glare there"
        assert created[0].occurrence_key == OccurrenceKey(block=0, line=0, char=20)
        assert created[0].fragment_score == 2.0
        assert created[0].occurrences == 3

    def _process(self, word: WordDTO) -> list[StoredCandidate]:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, status=SourceStatus.PROCESSING, format=Format.PLAIN, kind=Kind.TEXT,
        )
        mocks["settings_repo"].get.return_value = "B1"
        mocks["known_word_repo"].get_all_pairs.return_value = set()
        mocks["analyze_text"].execute.return_value = AnalyzeTextResponse(
            text="text", words=[word], total_tokens=3, unique_lemmas=3,
        )
        uc.execute(1)
        created: list[StoredCandidate] = mocks["candidate_repo"].create_batch.call_args[0][0]
        return created

    def test_execute_not_found(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = None
        with pytest.raises(SourceNotFoundError):
            uc.execute(999)


@pytest.mark.unit
class TestProcessSourceDocument:
    def test_source_without_a_document_is_an_error(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, status=SourceStatus.PROCESSING, format=Format.PLAIN, kind=Kind.TEXT,
            )
        mocks["document_repo"].get.return_value = None
        with pytest.raises(SourceHasNoDocumentError):
            uc.execute(1)
        mocks["analyze_text"].execute.assert_not_called()
