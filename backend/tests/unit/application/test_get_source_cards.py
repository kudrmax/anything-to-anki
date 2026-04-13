from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_source_cards import GetSourceCardsUseCase
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.enrichment_status import EnrichmentStatus


def _make_candidate(
    lemma: str,
    status: CandidateStatus,
    fragment: str = "test fragment",
    meaning: str | None = None,
    ipa: str | None = None,
    translation: str | None = None,
    synonyms: str | None = None,
    examples: str | None = None,
    screenshot_path: str | None = None,
    audio_path: str | None = None,
) -> StoredCandidate:
    meaning_obj = None
    if any(v is not None for v in (meaning, ipa, translation, synonyms, examples)):
        meaning_obj = CandidateMeaning(
            candidate_id=1,
            meaning=meaning,
            translation=translation,
            synonyms=synonyms,
            examples=examples,
            ipa=ipa,
            status=EnrichmentStatus.DONE,
            error=None,
            generated_at=datetime(2026, 4, 7, tzinfo=UTC),
        )
    media_obj = None
    if screenshot_path is not None or audio_path is not None:
        media_obj = CandidateMedia(
            candidate_id=1,
            screenshot_path=screenshot_path,
            audio_path=audio_path,
            start_ms=None,
            end_ms=None,
            status=EnrichmentStatus.DONE,
            error=None,
            generated_at=datetime(2026, 4, 7, tzinfo=UTC),
        )
    return StoredCandidate(
        id=1,
        source_id=1,
        lemma=lemma,
        pos="NOUN",
        cefr_level="B2",
        zipf_frequency=3.5,
        is_sweet_spot=True,
        context_fragment=fragment,
        fragment_purity="clean",
        occurrences=1,
        status=status,
        meaning=meaning_obj,
        media=media_obj,
    )


@pytest.mark.unit
class TestGetSourceCardsUseCase:
    def setup_method(self) -> None:
        self.candidate_repo = MagicMock()
        self.use_case = GetSourceCardsUseCase(
            candidate_repo=self.candidate_repo,
        )

    def test_returns_only_learn_candidates(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(
                "burnout",
                CandidateStatus.LEARN,
                "leads to burnout quickly",
                meaning="physical collapse",
            ),
            _make_candidate("pursuit", CandidateStatus.SKIP),
            _make_candidate("relentless", CandidateStatus.PENDING),
        ]

        result = self.use_case.execute(source_id=1)

        assert len(result) == 1
        assert result[0].lemma == "burnout"

    def test_sentence_highlights_lemma(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, "leads to burnout quickly"),
        ]

        result = self.use_case.execute(source_id=1)
        assert "<b>burnout</b>" in result[0].sentence

    def test_meaning_from_candidate(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, meaning="physical collapse"),
        ]

        result = self.use_case.execute(source_id=1)
        assert result[0].meaning == "physical collapse"

    def test_no_meaning_becomes_none(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN),
        ]

        result = self.use_case.execute(source_id=1)
        assert result[0].meaning is None

    def test_ipa_from_candidate(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, ipa="/ˈbɜːrnaʊt/"),
        ]

        result = self.use_case.execute(source_id=1)
        assert result[0].ipa == "/ˈbɜːrnaʊt/"

    def test_empty_when_no_learn_candidates(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.SKIP),
        ]
        result = self.use_case.execute(source_id=1)
        assert result == []

    def test_sentence_highlights_inflected_form(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("run", CandidateStatus.LEARN, "she is running fast"),
        ]
        result = self.use_case.execute(source_id=1)
        assert "<b>running</b>" in result[0].sentence

    def test_sentence_strips_markdown(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, "leads to **burnout** quickly"),
        ]
        result = self.use_case.execute(source_id=1)
        assert "**" not in result[0].sentence
        assert "<b>burnout</b>" in result[0].sentence

    def test_meaning_strips_markdown_and_highlights(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(
                "burnout",
                CandidateStatus.LEARN,
                meaning="**burnout** means exhaustion",
            ),
        ]
        result = self.use_case.execute(source_id=1)
        assert result[0].meaning is not None
        assert "**" not in result[0].meaning
        assert "<b>burnout</b>" in result[0].meaning

    def test_screenshot_url_generated_from_path(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(
                "burnout",
                CandidateStatus.LEARN,
                screenshot_path="/tmp/media/burnout_123.jpg",
            ),
        ]
        result = self.use_case.execute(source_id=1)
        assert result[0].screenshot_url == "/media/1/burnout_123.jpg"

    def test_audio_url_generated_from_path(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(
                "burnout",
                CandidateStatus.LEARN,
                audio_path="/tmp/media/burnout_456.mp3",
            ),
        ]
        result = self.use_case.execute(source_id=1)
        assert result[0].audio_url == "/media/1/burnout_456.mp3"

    def test_both_media_urls_generated(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(
                "burnout",
                CandidateStatus.LEARN,
                screenshot_path="/tmp/media/burnout_123.jpg",
                audio_path="/tmp/media/burnout_456.mp3",
            ),
        ]
        result = self.use_case.execute(source_id=1)
        assert result[0].screenshot_url == "/media/1/burnout_123.jpg"
        assert result[0].audio_url == "/media/1/burnout_456.mp3"

    def test_no_media_urls_when_paths_missing(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN),
        ]
        result = self.use_case.execute(source_id=1)
        assert result[0].screenshot_url is None
        assert result[0].audio_url is None

    def test_custom_media_base_url(self) -> None:
        use_case = GetSourceCardsUseCase(
            candidate_repo=self.candidate_repo,
            media_base_url="/custom/media",
        )
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(
                "burnout",
                CandidateStatus.LEARN,
                screenshot_path="/tmp/burnout_123.jpg",
            ),
        ]
        result = use_case.execute(source_id=1)
        assert result[0].screenshot_url == "/custom/media/1/burnout_123.jpg"

    def test_translation_synonyms_examples_from_candidate(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(
                "burnout",
                CandidateStatus.LEARN,
                meaning="physical collapse",
                translation="выгорание",
                synonyms="exhaustion, fatigue",
                examples="She suffered from burnout after working 80-hour weeks.",
            ),
        ]
        result = self.use_case.execute(source_id=1)
        assert result[0].translation == "выгорание"
        assert result[0].synonyms == "exhaustion, fatigue"
        assert result[0].examples == "She suffered from burnout after working 80-hour weeks."

    def test_translation_synonyms_examples_none_when_no_meaning(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN),
        ]
        result = self.use_case.execute(source_id=1)
        assert result[0].translation is None
        assert result[0].synonyms is None
        assert result[0].examples is None
