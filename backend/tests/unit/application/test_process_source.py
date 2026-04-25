from unittest.mock import MagicMock

import pytest
from backend.application.dto.analysis_dtos import (
    AnalyzeTextResponse,
    WordCandidateDTO,
)
from backend.application.use_cases.process_source import ProcessSourceUseCase
from backend.domain.entities.source import Source
from backend.domain.exceptions import SourceAlreadyProcessedError, SourceNotFoundError
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus


def _make_use_case() -> tuple[ProcessSourceUseCase, dict[str, MagicMock]]:
    mocks = {
        "source_repo": MagicMock(),
        "candidate_repo": MagicMock(),
        "known_word_repo": MagicMock(),
        "settings_repo": MagicMock(),
        "analyze_text": MagicMock(),
    }
    uc = ProcessSourceUseCase(
        source_repo=mocks["source_repo"],
        candidate_repo=mocks["candidate_repo"],
        known_word_repo=mocks["known_word_repo"],
        settings_repo=mocks["settings_repo"],
        analyze_text_use_case=mocks["analyze_text"],
    )
    return uc, mocks


@pytest.mark.unit
class TestProcessSourceStart:
    def test_start_sets_processing(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, raw_text="Text", status=SourceStatus.NEW,
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
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
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
        )
        with pytest.raises(SourceAlreadyProcessedError):
            uc.start(1)

    def test_start_allows_error_retry(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, raw_text="Text", status=SourceStatus.ERROR,
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
        )
        uc.start(1)
        mocks["source_repo"].update_status.assert_called_once()


@pytest.mark.unit
class TestProcessSourceExecute:
    def test_execute_saves_candidates(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, raw_text="Hello world", status=SourceStatus.PROCESSING,
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
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
        # 2 stage updates + 1 final DONE update
        assert mocks["source_repo"].update_status.call_count == 3
        final_call = mocks["source_repo"].update_status.call_args_list[-1]
        assert final_call[0][1] == SourceStatus.DONE

    def test_execute_passes_usage_distribution(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, raw_text="dodgy deal", status=SourceStatus.PROCESSING,
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
        )
        mocks["settings_repo"].get.return_value = "B1"
        mocks["known_word_repo"].get_all_pairs.return_value = set()
        mocks["analyze_text"].execute.return_value = AnalyzeTextResponse(
            cleaned_text="dodgy deal",
            candidates=[
                WordCandidateDTO(
                    lemma="dodgy", pos="ADJ", cefr_level="B2",
                    zipf_frequency=3.3, is_sweet_spot=True,
                    context_fragment="dodgy deal",
                    fragment_purity="clean", occurrences=1,
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

    def test_execute_filters_known_words(self) -> None:
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, raw_text="Hello", status=SourceStatus.PROCESSING,
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
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
        "lyrics_parser": lyrics_parser,
        "subtitles_parser": subtitles_parser,
    }
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
        source_parsers={
            InputMethod.LYRICS_PASTED: lyrics_parser,
            InputMethod.SUBTITLES_FILE: subtitles_parser,
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
            input_method=InputMethod.LYRICS_PASTED, content_type=ContentType.LYRICS,
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
            input_method=InputMethod.SUBTITLES_FILE, content_type=ContentType.TEXT,
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
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
        )
        uc.execute(3)
        mocks["lyrics_parser"].parse.assert_not_called()
        mocks["subtitles_parser"].parse.assert_not_called()
        call_args = mocks["analyze_text"].execute.call_args[0][0]
        assert call_args.raw_text == raw


@pytest.mark.unit
class TestProcessSourceKnownWordWildcard:
    def test_wildcard_filters_any_pos(self) -> None:
        """A wildcard known entry (lemma, None) should filter candidates of any POS."""
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, raw_text="Hello", status=SourceStatus.PROCESSING,
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
        )
        mocks["settings_repo"].get.return_value = "B1"
        mocks["known_word_repo"].get_all_pairs.return_value = {("pursuit", None)}
        mocks["analyze_text"].execute.return_value = AnalyzeTextResponse(
            cleaned_text="Hello",
            candidates=[
                WordCandidateDTO(
                    lemma="pursuit", pos="NOUN", cefr_level="B2",
                    zipf_frequency=3.5, is_sweet_spot=True,
                    context_fragment="in pursuit of",
                    fragment_purity="clean", occurrences=1,
                ),
            ],
            total_tokens=2,
            unique_lemmas=1,
        )

        uc.execute(1)

        saved = mocks["candidate_repo"].create_batch.call_args[0][0]
        assert len(saved) == 0

    def test_wildcard_does_not_filter_other_lemmas(self) -> None:
        """A wildcard for 'pursuit' must not filter 'ambition'."""
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, raw_text="Hello", status=SourceStatus.PROCESSING,
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
        )
        mocks["settings_repo"].get.return_value = "B1"
        mocks["known_word_repo"].get_all_pairs.return_value = {("pursuit", None)}
        mocks["analyze_text"].execute.return_value = AnalyzeTextResponse(
            cleaned_text="Hello",
            candidates=[
                WordCandidateDTO(
                    lemma="ambition", pos="NOUN", cefr_level="B2",
                    zipf_frequency=3.5, is_sweet_spot=True,
                    context_fragment="burning ambition",
                    fragment_purity="clean", occurrences=1,
                ),
            ],
            total_tokens=2,
            unique_lemmas=1,
        )

        uc.execute(1)

        saved = mocks["candidate_repo"].create_batch.call_args[0][0]
        assert len(saved) == 1
        assert saved[0].lemma == "ambition"

    def test_exact_and_wildcard_together(self) -> None:
        """Both exact and wildcard entries present — all matching lemmas filtered."""
        uc, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = Source(
            id=1, raw_text="Hello", status=SourceStatus.PROCESSING,
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
        )
        mocks["settings_repo"].get.return_value = "B1"
        mocks["known_word_repo"].get_all_pairs.return_value = {
            ("run", "VERB"),
            ("run", None),
        }
        mocks["analyze_text"].execute.return_value = AnalyzeTextResponse(
            cleaned_text="Hello",
            candidates=[
                WordCandidateDTO(
                    lemma="run", pos="NOUN", cefr_level="B1",
                    zipf_frequency=4.0, is_sweet_spot=True,
                    context_fragment="a run in the park",
                    fragment_purity="clean", occurrences=1,
                ),
            ],
            total_tokens=2,
            unique_lemmas=1,
        )

        uc.execute(1)

        saved = mocks["candidate_repo"].create_batch.call_args[0][0]
        assert len(saved) == 0
