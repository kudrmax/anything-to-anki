from unittest.mock import MagicMock

import pytest
from backend.application.dto.analysis_dtos import (
    AnalyzeTextResponse,
    WordCandidateDTO,
)
from backend.application.use_cases.process_source import ProcessSourceUseCase
from backend.domain.entities.source import Source
from backend.domain.exceptions import (
    SourceAlreadyProcessedError,
    SourceHasNoDocumentError,
    SourceNotFoundError,
)
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.phrase_words import PhraseWord, PhraseWords
from backend.domain.value_objects.source_status import SourceStatus

from tests.candidate_sorter_support import threshold_resolver
from tests.vocabulary_support import user_vocabulary


def _words(phrase: str, *rare: str) -> PhraseWords:
    return PhraseWords(phrase=phrase, words=tuple(PhraseWord(word, rare=True) for word in rare))


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
            candidates=[
                WordCandidateDTO(
                    lemma="ubiquitous", pos="ADJ", cefr_level="C1",
                    zipf_frequency=3.2, is_sweet_spot=True,
                    context_fragment="ubiquitous presence",
                    phrase_words=_words("ubiquitous presence"),
                    occurrences=1,
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
            candidates=[
                WordCandidateDTO(
                    lemma="dodgy", pos="ADJ", cefr_level="B2",
                    zipf_frequency=3.3, is_sweet_spot=True,
                    context_fragment="dodgy deal",
                    phrase_words=_words("dodgy deal"),
                    occurrences=1,
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
            text="Hello", candidates=[], total_tokens=1, unique_lemmas=1,
        )
        uc.execute(1)
        document, request = mocks["analyze_text"].execute.call_args[0]
        assert document == DOCUMENT
        assert request.vocabulary.known == frozenset({"pursuit", "divorce"})
        assert request.frequent_word_zipf == 5.0

    def test_execute_saves_phrase_words(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, status=SourceStatus.PROCESSING, format=Format.PLAIN, kind=Kind.TEXT,
            )
        mocks["settings_repo"].get.return_value = "B1"
        mocks["known_word_repo"].get_all_pairs.return_value = set()
        mocks["analyze_text"].execute.return_value = AnalyzeTextResponse(
            text="Hello",
            candidates=[
                WordCandidateDTO(
                    lemma="paleontology", pos="NOUN", cefr_level="C1",
                    zipf_frequency=2.8, is_sweet_spot=False,
                    context_fragment="So on a dare, I picked paleontology.",
                    phrase_words=_words("So on a dare, I picked paleontology.", "dare"),
                    occurrences=1,
                ),
            ],
            total_tokens=8,
            unique_lemmas=7,
        )
        uc.execute(1)
        created = mocks["candidate_repo"].create_batch.call_args[0][0]
        assert created[0].phrase_words == _words("So on a dare, I picked paleontology.", "dare")

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
