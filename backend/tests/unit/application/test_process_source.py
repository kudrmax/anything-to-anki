from unittest.mock import MagicMock

import pytest
from backend.application.dto.analysis_dtos import (
    AnalyzeTextResponse,
    WordCandidateDTO,
)
from backend.application.use_cases.process_source import ProcessSourceUseCase
from backend.domain.entities.dictionary_entry import DictionaryEntry
from backend.domain.entities.source import Source
from backend.domain.exceptions import SourceAlreadyProcessedError, SourceNotFoundError
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.source_type import SourceType


def _make_use_case() -> tuple[ProcessSourceUseCase, dict[str, MagicMock]]:
    mocks = {
        "source_repo": MagicMock(),
        "candidate_repo": MagicMock(),
        "known_word_repo": MagicMock(),
        "settings_repo": MagicMock(),
        "analyze_text": MagicMock(),
        "dictionary_provider": MagicMock(),
    }
    mocks["dictionary_provider"].get_entry.return_value = DictionaryEntry(
        lemma="", pos="", definition="a test definition", ipa="/tɛst/",
    )
    uc = ProcessSourceUseCase(
        source_repo=mocks["source_repo"],
        candidate_repo=mocks["candidate_repo"],
        known_word_repo=mocks["known_word_repo"],
        settings_repo=mocks["settings_repo"],
        analyze_text_use_case=mocks["analyze_text"],
        dictionary_provider=mocks["dictionary_provider"],
    )
    return uc, mocks


@pytest.mark.unit
class TestProcessSourceStart:
    def test_start_sets_processing(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, raw_text="Text", status=SourceStatus.NEW,
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
            id=1, raw_text="Text", status=SourceStatus.DONE,
        )
        with pytest.raises(SourceAlreadyProcessedError):
            uc.start(1)

    def test_start_allows_error_retry(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, raw_text="Text", status=SourceStatus.ERROR,
        )
        uc.start(1)
        mocks["source_repo"].update_status.assert_called_once()


@pytest.mark.unit
class TestProcessSourceExecute:
    def test_execute_saves_candidates(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, raw_text="Hello world", status=SourceStatus.PROCESSING,
        )
        mocks["settings_repo"].get.return_value = "B1"
        mocks["known_word_repo"].get_all_pairs.return_value = set()
        mocks["analyze_text"].execute.return_value = AnalyzeTextResponse(
            cleaned_text="Hello world",
            candidates=[
                WordCandidateDTO(
                    lemma="ubiquitous", pos="ADJ", cefr_level="C1",
                    zipf_frequency=3.2, is_sweet_spot=True,
                    context_fragment="ubiquitous presence",
                    fragment_purity="clean", occurrences=1,
                ),
            ],
            total_tokens=5,
            unique_lemmas=3,
        )
        uc.execute(1)
        mocks["candidate_repo"].create_batch.assert_called_once()
        mocks["source_repo"].update_status.assert_called_once()
        call_args = mocks["source_repo"].update_status.call_args
        assert call_args[0][1] == SourceStatus.DONE

    def test_execute_filters_known_words(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, raw_text="Hello", status=SourceStatus.PROCESSING,
        )
        mocks["settings_repo"].get.return_value = "B1"
        mocks["known_word_repo"].get_all_pairs.return_value = {("pursuit", "NOUN")}
        mocks["analyze_text"].execute.return_value = AnalyzeTextResponse(
            cleaned_text="Hello",
            candidates=[
                WordCandidateDTO(
                    lemma="pursuit", pos="NOUN", cefr_level="B2",
                    zipf_frequency=3.5, is_sweet_spot=True,
                    context_fragment="the pursuit of",
                    fragment_purity="clean", occurrences=1,
                ),
            ],
            total_tokens=3,
            unique_lemmas=2,
        )
        uc.execute(1)
        created = mocks["candidate_repo"].create_batch.call_args[0][0]
        assert len(created) == 0

    def test_execute_not_found(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = None
        with pytest.raises(SourceNotFoundError):
            uc.execute(999)


def _make_use_case_with_parsers() -> tuple[ProcessSourceUseCase, dict[str, MagicMock]]:
    """Create use case with mock source parsers."""
    lyrics_parser = MagicMock()
    subtitles_parser = MagicMock()
    mocks = {
        "source_repo": MagicMock(),
        "candidate_repo": MagicMock(),
        "known_word_repo": MagicMock(),
        "settings_repo": MagicMock(),
        "analyze_text": MagicMock(),
        "dictionary_provider": MagicMock(),
        "lyrics_parser": lyrics_parser,
        "subtitles_parser": subtitles_parser,
    }
    mocks["dictionary_provider"].get_entry.return_value = DictionaryEntry(
        lemma="", pos="", definition="a test definition", ipa="/tɛst/",
    )
    mocks["settings_repo"].get.return_value = "B1"
    mocks["known_word_repo"].get_all_pairs.return_value = set()
    mocks["analyze_text"].execute.return_value = AnalyzeTextResponse(
        cleaned_text="parsed text",
        candidates=[],
        total_tokens=2,
        unique_lemmas=1,
    )
    uc = ProcessSourceUseCase(
        source_repo=mocks["source_repo"],
        candidate_repo=mocks["candidate_repo"],
        known_word_repo=mocks["known_word_repo"],
        settings_repo=mocks["settings_repo"],
        analyze_text_use_case=mocks["analyze_text"],
        dictionary_provider=mocks["dictionary_provider"],
        source_parsers={
            SourceType.LYRICS: lyrics_parser,
            SourceType.SUBTITLES: subtitles_parser,
        },
    )
    return uc, mocks


@pytest.mark.unit
class TestProcessSourceParsers:
    def test_execute_calls_parser_for_lyrics(self) -> None:
        uc, mocks = _make_use_case_with_parsers()
        raw = "I was born to run\nShe was made to fly"
        parsed = "I was born to run. She was made to fly."
        mocks["lyrics_parser"].parse.return_value = parsed
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, raw_text=raw, status=SourceStatus.PROCESSING,
            source_type=SourceType.LYRICS,
        )
        uc.execute(1)
        mocks["lyrics_parser"].parse.assert_called_once_with(raw)
        call_args = mocks["analyze_text"].execute.call_args[0][0]
        assert call_args.raw_text == parsed

    def test_execute_calls_parser_for_subtitles(self) -> None:
        uc, mocks = _make_use_case_with_parsers()
        raw = "1\n00:00:01,000 --> 00:00:03,000\nHello world"
        parsed = "Hello world"
        mocks["subtitles_parser"].parse.return_value = parsed
        mocks["source_repo"].get_by_id.return_value = Source(
            id=2, raw_text=raw, status=SourceStatus.PROCESSING,
            source_type=SourceType.SUBTITLES,
        )
        uc.execute(2)
        mocks["subtitles_parser"].parse.assert_called_once_with(raw)
        call_args = mocks["analyze_text"].execute.call_args[0][0]
        assert call_args.raw_text == parsed

    def test_execute_no_parser_for_text(self) -> None:
        uc, mocks = _make_use_case_with_parsers()
        raw = "Plain text content here."
        mocks["source_repo"].get_by_id.return_value = Source(
            id=3, raw_text=raw, status=SourceStatus.PROCESSING,
            source_type=SourceType.TEXT,
        )
        uc.execute(3)
        mocks["lyrics_parser"].parse.assert_not_called()
        mocks["subtitles_parser"].parse.assert_not_called()
        call_args = mocks["analyze_text"].execute.call_args[0][0]
        assert call_args.raw_text == raw
