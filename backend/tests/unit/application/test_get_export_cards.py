from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_export_cards import GetExportCardsUseCase
from backend.application.utils.export_queue import ExportQueue
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.services.cloze_builder import ClozeBuilder
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind


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
    source_id: int = 1,
    candidate_id: int = 1,
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
            generated_at=datetime(2026, 4, 7, tzinfo=UTC),
        )
    return StoredCandidate(
        id=candidate_id,
        source_id=source_id,
        lemma=lemma,
        pos="NOUN",
        cefr_level="B2",
        zipf_frequency=3.5,
        context_fragment=fragment,
        fragment_purity="clean",
        occurrences=1,
        status=status,
        meaning=meaning_obj,
        media=media_obj,
    )


def _make_source_mock(source_id: int = 1, title: str = "Test Source") -> MagicMock:
    source = MagicMock()
    source.id = source_id
    source.title = title
    return source


@pytest.mark.unit
class TestGetExportCardsExecute:
    def setup_method(self) -> None:
        self.candidate_repo = MagicMock()
        self.anki_sync_repo = MagicMock()
        self.anki_sync_repo.get_synced_candidate_ids.return_value = set()
        self.source_repo = MagicMock()
        self.source_repo.get_by_id.return_value = _make_source_mock(1, "Test Source")
        self.use_case = GetExportCardsUseCase(
            export_queue=ExportQueue(self.candidate_repo, self.anki_sync_repo),
            source_repo=self.source_repo,
            cloze_builder=ClozeBuilder(),
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

        assert len(result.incomplete) == 1
        assert len(result.incomplete[0].cards) == 1
        assert result.incomplete[0].cards[0].lemma == "burnout"

    def test_excludes_already_exported_candidates(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, candidate_id=1),
            _make_candidate("relentless", CandidateStatus.LEARN, candidate_id=2),
            _make_candidate("pursuit", CandidateStatus.LEARN, candidate_id=3),
        ]
        self.anki_sync_repo.get_synced_candidate_ids.return_value = {1, 3}

        result = self.use_case.execute(source_id=1)

        assert [card.lemma for card in result.incomplete[0].cards] == ["relentless"]
        assert result.exported_count == 2

    def test_no_sections_when_everything_exported(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, candidate_id=1),
        ]
        self.anki_sync_repo.get_synced_candidate_ids.return_value = {1}

        result = self.use_case.execute(source_id=1)

        assert result.ready == []
        assert result.incomplete == []
        assert result.exported_count == 1

    def test_section_has_source_title(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN),
        ]

        result = self.use_case.execute(source_id=1)

        assert result.incomplete[0].source_title == "Test Source"
        assert result.incomplete[0].source_id == 1

    def test_sentence_highlights_lemma(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, "leads to burnout quickly"),
        ]

        result = self.use_case.execute(source_id=1)
        assert "<b>burnout</b>" in result.incomplete[0].cards[0].sentence

    def test_meaning_from_candidate(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, meaning="physical collapse"),
        ]

        result = self.use_case.execute(source_id=1)
        assert result.incomplete[0].cards[0].meaning == "physical collapse"

    def test_no_meaning_becomes_none(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN),
        ]

        result = self.use_case.execute(source_id=1)
        assert result.incomplete[0].cards[0].meaning is None

    def test_ipa_from_candidate(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, ipa="/ˈbɜːrnaʊt/"),
        ]

        result = self.use_case.execute(source_id=1)
        assert result.incomplete[0].cards[0].ipa == "/ˈbɜːrnaʊt/"

    def test_empty_when_no_learn_candidates(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.SKIP),
        ]
        result = self.use_case.execute(source_id=1)
        assert result.ready == []
        assert result.incomplete == []

    def test_sentence_highlights_inflected_form(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("run", CandidateStatus.LEARN, "she is running fast"),
        ]
        result = self.use_case.execute(source_id=1)
        assert "<b>running</b>" in result.incomplete[0].cards[0].sentence

    def test_sentence_strips_markdown(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, "leads to **burnout** quickly"),
        ]
        result = self.use_case.execute(source_id=1)
        card = result.incomplete[0].cards[0]
        assert "**" not in card.sentence
        assert "<b>burnout</b>" in card.sentence

    def test_meaning_strips_markdown_and_highlights(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(
                "burnout",
                CandidateStatus.LEARN,
                meaning="**burnout** means exhaustion",
            ),
        ]
        result = self.use_case.execute(source_id=1)
        card = result.incomplete[0].cards[0]
        assert card.meaning is not None
        assert "**" not in card.meaning
        assert "<b>burnout</b>" in card.meaning

    def test_screenshot_url_generated_from_path(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(
                "burnout",
                CandidateStatus.LEARN,
                screenshot_path="/tmp/media/burnout_123.jpg",
            ),
        ]
        result = self.use_case.execute(source_id=1)
        assert result.incomplete[0].cards[0].screenshot_url == "/media/1/burnout_123.jpg"

    def test_audio_url_generated_from_path(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(
                "burnout",
                CandidateStatus.LEARN,
                audio_path="/tmp/media/burnout_456.mp3",
            ),
        ]
        result = self.use_case.execute(source_id=1)
        assert result.incomplete[0].cards[0].audio_url == "/media/1/burnout_456.mp3"

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
        card = result.incomplete[0].cards[0]
        assert card.screenshot_url == "/media/1/burnout_123.jpg"
        assert card.audio_url == "/media/1/burnout_456.mp3"

    def test_no_media_urls_when_paths_missing(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN),
        ]
        result = self.use_case.execute(source_id=1)
        card = result.incomplete[0].cards[0]
        assert card.screenshot_url is None
        assert card.audio_url is None

    def test_custom_media_base_url(self) -> None:
        use_case = GetExportCardsUseCase(
            export_queue=ExportQueue(self.candidate_repo, self.anki_sync_repo),
            source_repo=self.source_repo,
            cloze_builder=ClozeBuilder(),
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
        assert result.incomplete[0].cards[0].screenshot_url == "/custom/media/1/burnout_123.jpg"

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
        card = result.incomplete[0].cards[0]
        assert card.translation == "выгорание"
        assert card.synonyms == "exhaustion, fatigue"
        assert card.examples == "She suffered from burnout after working 80-hour weeks."

    def test_translation_synonyms_examples_none_when_no_meaning(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN),
        ]
        result = self.use_case.execute(source_id=1)
        card = result.incomplete[0].cards[0]
        assert card.translation is None
        assert card.synonyms is None
        assert card.examples is None

    def test_splits_ready_and_incomplete_cards(self) -> None:
        ready = _make_candidate(
            "burnout", CandidateStatus.LEARN, meaning="collapse", candidate_id=1,
        )
        ready.tts = CandidateTTS(candidate_id=1, audio_path="/tmp/tts.mp3", generated_at=None)
        self.candidate_repo.get_by_source.return_value = [
            ready,
            _make_candidate("pursuit", CandidateStatus.LEARN, meaning="chase", candidate_id=2),
            _make_candidate("relentless", CandidateStatus.LEARN, candidate_id=3),
        ]

        result = self.use_case.execute(source_id=1)

        assert [card.lemma for card in result.ready[0].cards] == ["burnout"]
        assert result.ready[0].cards[0].missing == []
        incomplete = {card.lemma: card.missing for card in result.incomplete[0].cards}
        assert incomplete == {"pursuit": ["audio"], "relentless": ["meaning", "audio"]}

    def test_source_title_fallback_when_source_not_found(self) -> None:
        self.source_repo.get_by_id.return_value = None
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, source_id=99),
        ]
        result = self.use_case.execute(source_id=99)
        assert result.incomplete[0].source_title == "Source #99"


    def test_cloze_card_shows_hidden_words_in_bold(self) -> None:
        phrase = "She finally gave up smoking last year."
        candidate = replace(
            _make_candidate("give up", CandidateStatus.LEARN, phrase),
            surface_form="gave up",
            cloze=CandidateCloze(
                candidate_id=1,
                hidden_word_indices=(3,),
                hint_kind=ClozeHintKind.NONE,
                custom_hint=None,
                phrase=phrase,
            ),
        )
        self.candidate_repo.get_by_source.return_value = [candidate]

        card = self.use_case.execute(source_id=1).incomplete[0].cards[0]

        assert card.is_cloze is True
        assert card.sentence == "She finally gave <b>up</b> smoking last year."

    def test_recognition_card_is_not_cloze(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, "leads to burnout quickly"),
        ]

        card = self.use_case.execute(source_id=1).incomplete[0].cards[0]

        assert card.is_cloze is False
        assert card.sentence == "leads to <b>burnout</b> quickly"


@pytest.mark.unit
class TestGetExportCardsExecuteAll:
    def setup_method(self) -> None:
        self.candidate_repo = MagicMock()
        self.anki_sync_repo = MagicMock()
        self.anki_sync_repo.get_synced_candidate_ids.return_value = set()
        self.source_repo = MagicMock()
        self.use_case = GetExportCardsUseCase(
            export_queue=ExportQueue(self.candidate_repo, self.anki_sync_repo),
            source_repo=self.source_repo,
            cloze_builder=ClozeBuilder(),
        )

    def test_groups_by_source(self) -> None:
        self.candidate_repo.get_all_by_status.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, source_id=1),
            _make_candidate("pursuit", CandidateStatus.LEARN, source_id=1),
            _make_candidate("relentless", CandidateStatus.LEARN, source_id=2),
        ]
        self.source_repo.get_by_id.side_effect = lambda sid: _make_source_mock(
            sid, f"Source {sid} Title"
        )

        result = self.use_case.execute_all()

        assert len(result.incomplete) == 2
        assert result.incomplete[0].source_id == 1
        assert result.incomplete[0].source_title == "Source 1 Title"
        assert len(result.incomplete[0].cards) == 2
        assert result.incomplete[1].source_id == 2
        assert result.incomplete[1].source_title == "Source 2 Title"
        assert len(result.incomplete[1].cards) == 1

    def test_omits_sources_with_everything_exported(self) -> None:
        self.candidate_repo.get_all_by_status.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, source_id=1, candidate_id=1),
            _make_candidate("relentless", CandidateStatus.LEARN, source_id=2, candidate_id=2),
        ]
        self.anki_sync_repo.get_synced_candidate_ids.return_value = {1}
        self.source_repo.get_by_id.side_effect = lambda sid: _make_source_mock(sid, f"S{sid}")

        result = self.use_case.execute_all()

        assert [section.source_id for section in result.incomplete] == [2]
        assert result.exported_count == 1

    def test_empty_when_no_learn_candidates(self) -> None:
        self.candidate_repo.get_all_by_status.return_value = []

        result = self.use_case.execute_all()

        assert result.ready == []
        assert result.incomplete == []

    def test_source_title_fallback_when_source_not_found(self) -> None:
        self.candidate_repo.get_all_by_status.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, source_id=99),
        ]
        self.source_repo.get_by_id.return_value = None

        result = self.use_case.execute_all()

        assert len(result.incomplete) == 1
        assert result.incomplete[0].source_title == "Source #99"
