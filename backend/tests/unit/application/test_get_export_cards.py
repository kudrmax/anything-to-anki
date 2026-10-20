from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_export_cards import GetExportCardsUseCase
from backend.application.utils.export_queue import ExportCard
from backend.application.utils.source_scope_resolver import SourceScopeResolver
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.entities.collection import Collection
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.services.cloze_builder import ClozeBuilder
from backend.domain.value_objects.card_choice import CardChoice
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.domain.value_objects.source_scope import SourceScope
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.word_status import WordStatus

from tests.export_support import ExportCards, export_card, in_anki, with_phrase
from tests.phrase_support import phrase
from tests.unit.application.collection_fakes import InMemoryCollectionRepository
from tests.unit.application.scope_fakes import sources_scope_resolver
from tests.unit.application.source_fakes import InMemorySourceRepository


def _make_candidate(
    lemma: str,
    status: WordStatus,
    fragment: str = "test fragment",
    target: str | None = None,
    meaning: str | None = None,
    ipa: str | None = None,
    translation: str | None = None,
    synonyms: str | None = None,
    examples: str | None = None,
    screenshot_path: str | None = None,
    audio_path: str | None = None,
    source_id: int = 1,
    candidate_id: int = 1,
) -> ExportCard:
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
    return export_card(
        StoredCandidate(
            id=candidate_id,
            source_id=source_id,
            lemma=lemma,
            pos="NOUN",
            cefr_level="B2",
            zipf_frequency=3.5,
            occurrences=1,
            status=status,
        ),
        phrase(fragment, target or lemma),
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
        self.cards = ExportCards()
        self.source_repo = MagicMock()
        self.source_repo.get_by_id.return_value = _make_source_mock(1, "Test Source")
        self.use_case = GetExportCardsUseCase(
            export_queue=self.cards.queue(),
            source_repo=self.source_repo,
            cloze_builder=ClozeBuilder(),
            scope_resolver=sources_scope_resolver(1, 2, 99),
        )

    def test_returns_only_learn_candidates(self) -> None:
        self.cards.put([
            _make_candidate(
                "burnout",
                WordStatus.LEARN,
                "leads to burnout quickly",
                meaning="physical collapse",
            ),
            _make_candidate("pursuit", WordStatus.NEW, candidate_id=2),
            _make_candidate("relentless", WordStatus.NEW, candidate_id=3),
        ])

        result = self.use_case.execute(SourceScope.source(1))

        assert len(result.incomplete) == 1
        assert len(result.incomplete[0].cards) == 1
        assert result.incomplete[0].cards[0].lemma == "burnout"

    def test_excludes_already_exported_candidates(self) -> None:
        self.cards.put([
            in_anki(_make_candidate("burnout", WordStatus.LEARN, candidate_id=1)),
            _make_candidate("relentless", WordStatus.LEARN, candidate_id=2),
            in_anki(_make_candidate("pursuit", WordStatus.LEARN, candidate_id=3)),
        ])

        result = self.use_case.execute(SourceScope.source(1))

        assert [card.lemma for card in result.incomplete[0].cards] == ["relentless"]
        assert result.exported_count == 2

    def test_no_sections_when_everything_exported(self) -> None:
        self.cards.put([
            in_anki(_make_candidate("burnout", WordStatus.LEARN, candidate_id=1)),
        ])

        result = self.use_case.execute(SourceScope.source(1))

        assert result.ready == []
        assert result.incomplete == []
        assert result.exported_count == 1

    def test_section_has_source_title(self) -> None:
        self.cards.put([
            _make_candidate("burnout", WordStatus.LEARN),
        ])

        result = self.use_case.execute(SourceScope.source(1))

        assert result.incomplete[0].source_title == "Test Source"
        assert result.incomplete[0].source_id == 1

    def test_sentence_highlights_lemma(self) -> None:
        self.cards.put([
            _make_candidate("burnout", WordStatus.LEARN, "leads to burnout quickly"),
        ])

        result = self.use_case.execute(SourceScope.source(1))
        assert "<b>burnout</b>" in result.incomplete[0].cards[0].sentence

    def test_meaning_from_candidate(self) -> None:
        self.cards.put([
            _make_candidate("burnout", WordStatus.LEARN, meaning="physical collapse"),
        ])

        result = self.use_case.execute(SourceScope.source(1))
        assert result.incomplete[0].cards[0].meaning == "physical collapse"

    def test_no_meaning_becomes_none(self) -> None:
        self.cards.put([
            _make_candidate("burnout", WordStatus.LEARN),
        ])

        result = self.use_case.execute(SourceScope.source(1))
        assert result.incomplete[0].cards[0].meaning is None

    def test_ipa_from_candidate(self) -> None:
        self.cards.put([
            _make_candidate("burnout", WordStatus.LEARN, ipa="/ˈbɜːrnaʊt/"),
        ])

        result = self.use_case.execute(SourceScope.source(1))
        assert result.incomplete[0].cards[0].ipa == "/ˈbɜːrnaʊt/"

    def test_empty_when_no_learn_candidates(self) -> None:
        self.cards.put([
            _make_candidate("burnout", WordStatus.NEW),
        ])
        result = self.use_case.execute(SourceScope.source(1))
        assert result.ready == []
        assert result.incomplete == []

    def test_sentence_highlights_inflected_form(self) -> None:
        self.cards.put([
            _make_candidate("run", WordStatus.LEARN, "she is running fast", target="running"),
        ])
        result = self.use_case.execute(SourceScope.source(1))
        assert "<b>running</b>" in result.incomplete[0].cards[0].sentence

    def test_sentence_bolds_only_the_target_occurrence(self) -> None:
        candidate = _make_candidate("burnout", WordStatus.LEARN, "burnout after burnout")
        candidate = with_phrase(
            candidate, source_phrase=phrase("burnout after burnout", "after burnout"),
        )
        self.cards.put([candidate])
        result = self.use_case.execute(SourceScope.source(1))
        assert result.incomplete[0].cards[0].sentence == "burnout <b>after burnout</b>"

    def test_meaning_strips_markdown_and_highlights(self) -> None:
        self.cards.put([
            _make_candidate(
                "burnout",
                WordStatus.LEARN,
                meaning="**burnout** means exhaustion",
            ),
        ])
        result = self.use_case.execute(SourceScope.source(1))
        card = result.incomplete[0].cards[0]
        assert card.meaning is not None
        assert "**" not in card.meaning
        assert "<b>burnout</b>" in card.meaning

    def test_screenshot_url_generated_from_path(self) -> None:
        self.cards.put([
            _make_candidate(
                "burnout",
                WordStatus.LEARN,
                screenshot_path="/tmp/media/burnout_123.jpg",
            ),
        ])
        result = self.use_case.execute(SourceScope.source(1))
        assert result.incomplete[0].cards[0].screenshot_url == "/media/1/burnout_123.jpg"

    def test_audio_url_generated_from_path(self) -> None:
        self.cards.put([
            _make_candidate(
                "burnout",
                WordStatus.LEARN,
                audio_path="/tmp/media/burnout_456.mp3",
            ),
        ])
        result = self.use_case.execute(SourceScope.source(1))
        assert result.incomplete[0].cards[0].audio_url == "/media/1/burnout_456.mp3"

    def test_both_media_urls_generated(self) -> None:
        self.cards.put([
            _make_candidate(
                "burnout",
                WordStatus.LEARN,
                screenshot_path="/tmp/media/burnout_123.jpg",
                audio_path="/tmp/media/burnout_456.mp3",
            ),
        ])
        result = self.use_case.execute(SourceScope.source(1))
        card = result.incomplete[0].cards[0]
        assert card.screenshot_url == "/media/1/burnout_123.jpg"
        assert card.audio_url == "/media/1/burnout_456.mp3"

    def test_no_media_urls_when_paths_missing(self) -> None:
        self.cards.put([
            _make_candidate("burnout", WordStatus.LEARN),
        ])
        result = self.use_case.execute(SourceScope.source(1))
        card = result.incomplete[0].cards[0]
        assert card.screenshot_url is None
        assert card.audio_url is None

    def test_custom_media_base_url(self) -> None:
        use_case = GetExportCardsUseCase(
            export_queue=self.cards.queue(),
            source_repo=self.source_repo,
            cloze_builder=ClozeBuilder(),
            scope_resolver=sources_scope_resolver(1, 2, 99),
            media_base_url="/custom/media",
        )
        self.cards.put([
            _make_candidate(
                "burnout",
                WordStatus.LEARN,
                screenshot_path="/tmp/burnout_123.jpg",
            ),
        ])
        result = use_case.execute(SourceScope.source(1))
        assert result.incomplete[0].cards[0].screenshot_url == "/custom/media/1/burnout_123.jpg"

    def test_translation_synonyms_examples_from_candidate(self) -> None:
        self.cards.put([
            _make_candidate(
                "burnout",
                WordStatus.LEARN,
                meaning="physical collapse",
                translation="выгорание",
                synonyms="exhaustion, fatigue",
                examples="She suffered from burnout after working 80-hour weeks.",
            ),
        ])
        result = self.use_case.execute(SourceScope.source(1))
        card = result.incomplete[0].cards[0]
        assert card.translation == "выгорание"
        assert card.synonyms == "exhaustion, fatigue"
        assert card.examples == "She suffered from burnout after working 80-hour weeks."

    def test_translation_synonyms_examples_none_when_no_meaning(self) -> None:
        self.cards.put([
            _make_candidate("burnout", WordStatus.LEARN),
        ])
        result = self.use_case.execute(SourceScope.source(1))
        card = result.incomplete[0].cards[0]
        assert card.translation is None
        assert card.synonyms is None
        assert card.examples is None

    def test_splits_ready_and_incomplete_cards(self) -> None:
        ready = _make_candidate(
            "burnout", WordStatus.LEARN, meaning="collapse", candidate_id=1,
        )
        ready = with_phrase(
            ready, tts=CandidateTTS(candidate_id=1, audio_path="/tmp/tts.mp3", generated_at=None),
        )
        self.cards.put([
            ready,
            _make_candidate("pursuit", WordStatus.LEARN, meaning="chase", candidate_id=2),
            _make_candidate("relentless", WordStatus.LEARN, candidate_id=3),
        ])

        result = self.use_case.execute(SourceScope.source(1))

        assert [card.lemma for card in result.ready[0].cards] == ["burnout"]
        assert result.ready[0].cards[0].missing == []
        incomplete = {card.lemma: card.missing for card in result.incomplete[0].cards}
        assert incomplete == {"pursuit": ["audio"], "relentless": ["meaning", "audio"]}

    def test_source_title_fallback_when_source_not_found(self) -> None:
        self.source_repo.get_by_id.return_value = None
        self.cards.put([
            _make_candidate("burnout", WordStatus.LEARN, source_id=99),
        ])
        result = self.use_case.execute(SourceScope.source(99))
        assert result.incomplete[0].source_title == "Source #99"


    def test_cloze_card_shows_hidden_words_in_bold(self) -> None:
        text = "She finally gave up smoking last year."
        candidate = with_phrase(
            _make_candidate("give up", WordStatus.LEARN, text, target="gave up"),
            choice=CardChoice.CLOZE,
            cloze=CandidateCloze(
                candidate_id=1,
                hidden_word_indices=(3,),
                hint_kind=ClozeHintKind.NONE,
                custom_hint=None,
                phrase=text,
            ),
        )
        self.cards.put([candidate])

        card = self.use_case.execute(SourceScope.source(1)).incomplete[0].cards[0]

        assert card.is_cloze is True
        assert card.sentence == "She finally gave <b>up</b> smoking last year."

    def test_recognition_card_is_not_cloze(self) -> None:
        self.cards.put([
            _make_candidate("burnout", WordStatus.LEARN, "leads to burnout quickly"),
        ])

        card = self.use_case.execute(SourceScope.source(1)).incomplete[0].cards[0]

        assert card.is_cloze is False
        assert card.sentence == "leads to <b>burnout</b> quickly"


@pytest.mark.unit
class TestGetExportCardsAllScope:
    def setup_method(self) -> None:
        self.cards = ExportCards()
        self.source_repo = MagicMock()
        self.use_case = GetExportCardsUseCase(
            export_queue=self.cards.queue(),
            source_repo=self.source_repo,
            cloze_builder=ClozeBuilder(),
            scope_resolver=sources_scope_resolver(1, 2, 99),
        )

    def test_groups_by_source(self) -> None:
        self.cards.put([
            _make_candidate("burnout", WordStatus.LEARN, source_id=1),
            _make_candidate("pursuit", WordStatus.LEARN, source_id=1),
            _make_candidate("relentless", WordStatus.LEARN, source_id=2),
        ])
        self.source_repo.get_by_id.side_effect = lambda sid: _make_source_mock(
            sid, f"Source {sid} Title"
        )

        result = self.use_case.execute(SourceScope.all())

        assert len(result.incomplete) == 2
        assert result.incomplete[0].source_id == 1
        assert result.incomplete[0].source_title == "Source 1 Title"
        assert len(result.incomplete[0].cards) == 2
        assert result.incomplete[1].source_id == 2
        assert result.incomplete[1].source_title == "Source 2 Title"
        assert len(result.incomplete[1].cards) == 1

    def test_omits_sources_with_everything_exported(self) -> None:
        self.cards.put([
            in_anki(_make_candidate("burnout", WordStatus.LEARN, source_id=1, candidate_id=1)),
            _make_candidate("relentless", WordStatus.LEARN, source_id=2, candidate_id=2),
        ])
        self.source_repo.get_by_id.side_effect = lambda sid: _make_source_mock(sid, f"S{sid}")

        result = self.use_case.execute(SourceScope.all())

        assert [section.source_id for section in result.incomplete] == [2]
        assert result.exported_count == 1

    def test_empty_when_no_learn_candidates(self) -> None:
        self.cards.put([])

        result = self.use_case.execute(SourceScope.all())

        assert result.ready == []
        assert result.incomplete == []

    def test_source_title_fallback_when_source_not_found(self) -> None:
        self.cards.put([
            _make_candidate("burnout", WordStatus.LEARN, source_id=99),
        ])
        self.source_repo.get_by_id.return_value = None

        result = self.use_case.execute(SourceScope.all())

        assert len(result.incomplete) == 1
        assert result.incomplete[0].source_title == "Source #99"


@pytest.mark.unit
class TestGetExportCardsCollectionScope:
    def setup_method(self) -> None:
        self.cards = ExportCards()
        self.cards.put([
            _make_candidate("burnout", WordStatus.LEARN, source_id=1, candidate_id=1),
            _make_candidate("pursuit", WordStatus.LEARN, source_id=2, candidate_id=2),
        ])
        sources = [
            Source(id=1, status=SourceStatus.DONE, title="Cam 18", collection_id=5),
            Source(id=2, status=SourceStatus.DONE, title="Loose"),
        ]
        self.use_case = GetExportCardsUseCase(
            export_queue=self.cards.queue(),
            source_repo=InMemorySourceRepository(sources),
            cloze_builder=ClozeBuilder(),
            scope_resolver=SourceScopeResolver(
                InMemorySourceRepository(sources),
                InMemoryCollectionRepository([Collection(id=5, name="IELTS")]),
            ),
        )

    def test_scope_limits_cards_and_names_the_scope(self) -> None:
        result = self.use_case.execute(SourceScope.collection(5))

        assert result.title == "IELTS"
        assert [section.source_id for section in result.ready + result.incomplete] == [1]

    def test_all_scope_keeps_everything(self) -> None:
        result = self.use_case.execute(SourceScope.all())

        assert result.title == "All sources"
        assert {s.source_id for s in result.ready + result.incomplete} == {1, 2}

    def test_unsorted_scope_keeps_only_sources_without_collection(self) -> None:
        result = self.use_case.execute(SourceScope.unsorted())

        assert [section.source_id for section in result.ready + result.incomplete] == [2]


@pytest.mark.unit
def test_sections_follow_the_order_of_the_set() -> None:
    """The set orders its sources (newest first here), not their ids."""
    cards = ExportCards()
    cards.put([
        _make_candidate("burnout", WordStatus.LEARN, source_id=1, candidate_id=1),
        _make_candidate("pursuit", WordStatus.LEARN, source_id=2, candidate_id=2),
        _make_candidate("relentless", WordStatus.LEARN, source_id=2, candidate_id=3),
    ])
    sources = [
        Source(
            id=1, status=SourceStatus.DONE, title="Older", collection_id=5,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        Source(
            id=2, status=SourceStatus.DONE, title="Newer", collection_id=5,
            created_at=datetime(2026, 2, 1, tzinfo=UTC),
        ),
    ]
    resolver = SourceScopeResolver(
        InMemorySourceRepository(sources),
        InMemoryCollectionRepository([Collection(id=5, name="IELTS")]),
    )
    use_case = GetExportCardsUseCase(
        export_queue=cards.queue(),
        source_repo=InMemorySourceRepository(sources),
        cloze_builder=ClozeBuilder(),
        scope_resolver=resolver,
    )

    for scope in (SourceScope.collection(5), SourceScope.all()):
        result = use_case.execute(scope)
        sections = result.ready + result.incomplete
        assert [s.source_id for s in sections] == [2, 1]
        assert [c.lemma for c in sections[0].cards] == ["pursuit", "relentless"]
