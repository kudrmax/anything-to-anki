"""The projection kept by `CardStateProjector.apply` and the time tick equals the review's
own computation after every step of random sequences of the app's real use cases (spec
§6.1): three sources sharing lemmas, about fifty cards, presses and their undo, reports,
the Known and Unknown lists, export and release, generated content, polish and its revert,
boundary edits, examples, words added from the text, Update and Re-cut, the level, source
deletion and the clock crossing an Anki timer.

After each step the stored rows equal `LiveCardStates` (statuses, done, wants generation,
sections and new-word counts at every threshold step, word statuses, phrase words), and the
review order of every sort order, computed from the stored rows, is today's order; so is the
order an open review holds for every source and the collection, each card in today's section.

Every write method of the owners of facts is reached by some step, or is named here with
the reason it cannot change card state: a new write method without a scenario fails.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import timedelta
from functools import cache
from types import SimpleNamespace
from typing import TYPE_CHECKING, ClassVar, NoReturn
from unittest.mock import MagicMock, patch

import pytest
from backend.application.dto.candidate_dtos import SelectionDTO
from backend.application.dto.card_report_dtos import ReportCandidateRequest
from backend.application.dto.generation_dtos import GenerationKindStatusDTO, GenerationStatusDTO
from backend.application.dto.review_dtos import OpenReviewRequest
from backend.application.dto.source_dtos import ProgressDTO
from backend.application.utils import candidate_sorter
from backend.application.utils.candidate_sorter import CandidateSorter
from backend.application.utils.card_state_differences import differences
from backend.application.utils.live_generation_status import summed
from backend.application.utils.review_answer import ReviewAnswer
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_meaning_image import CandidateMeaningImage
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.exceptions import DomainError
from backend.domain.ports.card_state_query import CardStateQuery
from backend.domain.services import candidate_sorting
from backend.domain.services.candidate_sorting import CardStanding, sort_cards
from backend.domain.services.source_review_status import (
    derive_review_status,
    stored_status_of_set,
)
from backend.domain.value_objects.ai_unavailable import AI_UNAVAILABLE_MARKER, is_ai_unavailable
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.card_choice import Press
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.domain.value_objects.decision_progress import DecisionProgress
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.export_group import ExportGroup
from backend.domain.value_objects.generation_kind import GenerationKind
from backend.domain.value_objects.generation_scope import GenerationScope
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.learning_timer import LEARNING_KNOWN_AFTER
from backend.domain.value_objects.phrase_ref import PhraseRef
from backend.domain.value_objects.polished_phrase import PolishedPhrase
from backend.domain.value_objects.rebuild_mode import RebuildMode
from backend.domain.value_objects.review_order import CardRow
from backend.domain.value_objects.source_scope import SourceScope
from backend.infrastructure.api.background_rebuild_launcher import (
    BackgroundSourcesRebuildLauncher,
    RebuildPasses,
)
from backend.infrastructure.container import Container
from backend.infrastructure.persistence.database import Base, _enable_sqlite_foreign_keys
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_anki_sync_repository import SqlaAnkiSyncRepository
from backend.infrastructure.persistence.sqla_candidate_cloze_repository import (
    SqlaCandidateClozeRepository,
)
from backend.infrastructure.persistence.sqla_candidate_meaning_image_repository import (
    SqlaCandidateMeaningImageRepository,
)
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_candidate_media_repository import (
    SqlaCandidateMediaRepository,
)
from backend.infrastructure.persistence.sqla_candidate_pronunciation_repository import (
    SqlaCandidatePronunciationRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_candidate_tts_repository import (
    SqlaCandidateTTSRepository,
)
from backend.infrastructure.persistence.sqla_card_query import SqlaCardQuery
from backend.infrastructure.persistence.sqla_card_state_query import SqlaCardStateQuery
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_settings_repository import SqlaSettingsRepository
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from backend.infrastructure.persistence.sqla_word_mark_repository import SqlaWordMarkRepository
from backend.infrastructure.persistence.sqla_word_state_repository import (
    SqlaWordStateRepository,
)
from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    initialize,
    invariant,
    precondition,
    rule,
    run_state_machine_as_test,
)
from sqlalchemy import Engine, StaticPool, create_engine, event, select, text
from sqlalchemy.orm import Session, sessionmaker

from tests.decision_support import NOW, FixedClock
from tests.unit.architecture.test_owner_events import WRITE_CASES

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.entities.source import Source
    from backend.domain.ports.ai_service import AIService
    from backend.domain.value_objects.frequent_word_threshold import FrequentWordThreshold
    from backend.domain.value_objects.review_card import ReviewCard
    from backend.domain.value_objects.user_knowledge import UserKnowledge

pytestmark = pytest.mark.integration

SOURCES: dict[int, tuple[str, ...]] = {
    1: (
        "The lighthouse keeper would brood over the ominous glare of the sea.",
        "Gulls linger near the jagged cliffs while the tide recedes.",
        "He began to fret about the relentless storm and its gloom.",
        "A faint gleam of hope would flicker in the murky harbour.",
        "Sailors dwell on old legends of the treacherous reef.",
    ),
    2: (
        "The detective would brood over the ominous letter for hours.",
        "Shadows linger in the alley where the culprit vanished.",
        "She tried not to fret, yet the relentless rain kept falling.",
        "A gleam of the lighthouse cut through the murky fog.",
        "Witnesses dwell on the eerie silence before the crime.",
    ),
    3: (
        "Old farmers fret when the harvest withers in the drought.",
        "The scarecrow keeps a solemn vigil over the barren field.",
        "Crows linger on the fence and glare at the weary traveller.",
        "Dusk brings a gloom that seems to smother the village.",
    ),
    # A video's subtitles: its cards get clips, not speech nor polish.
    4: (
        "The lighthouse beam would flicker over the murky waves.",
        "Sailors linger by the pier and fret about the storm.",
        "A solemn gleam of dawn crept over the harbour.",
    ),
}
VIDEO_SOURCE = 4
VIDEO_FILE = "/media/video.mp4"
# Its first three cards: a clip made and timed, timed and not made, made but not timed.
CLIP = "/media/clip.jpg"
VIDEO_MEDIA = ((0, 1000, CLIP), (0, 1000, None), (None, None, CLIP))
VIDEO_STATES = ("downloaded", "not downloaded", "downloading")
LEVELS = ("A2", "B1", "B2", "C1")
REBUILD_MODES = (RebuildMode.UPDATE, RebuildMode.RECUT)
CLOCK_STEPS = (timedelta(days=1), LEARNING_KNOWN_AFTER + timedelta(days=1))
CONTENT_KINDS = (
    "meaning", "no meaning", "speech", "no speech", "clip", "no clip picture", "lost file",
    "timecodes", "cloze", "no cloze", "pronunciation", "picture", "no picture",
)
FIRST_NOTE = 5000
TWO_KNOWN_LEMMA = "tide"
# A plain word of source 3 that source 1 holds too, in a phrase of another card.
ORPHAN_LEMMA = "old"
ORPHAN_SOURCE = 3
TWO_KNOWN_POS = ("NOUN", "VERB")
SHARED_FILE = "/media/shared.mp3"
IPA = "/ɡleə/"
# A whole card is picked by its rank among the live cards, any number wrapping around.
PICK = st.integers(min_value=0, max_value=10_000)

# Sources 1, 2 and the video stand in it; source 3 is unsorted.
COLLECTION = 1
GENERATED_KINDS = tuple(GenerationKind)
# The order of the container's generation targets, which the ✨ status lists kinds in.
TARGET_ORDER = (
    GenerationKind.POLISH, GenerationKind.MEANING, GenerationKind.MEDIA,
    GenerationKind.PRONUNCIATION, GenerationKind.TTS,
)
GENERATION_SCOPES = (GenerationScope.MISSING, GenerationScope.READY_ALL, GenerationScope.ALL)

MAX_EXAMPLES = 8
STEPS_PER_EXAMPLE = 15

# Owner write methods no use case reaches here, each with why it cannot change card state.
NOT_REACHED: dict[tuple[str, str], str] = {
    ("SourceRepository", "create"): "the source's own row; records no change",
    ("SourceRepository", "update_status"): "the source's own row; records no change",
    ("SourceRepository", "update_title"): "the source's own row; records no change",
    ("SourceRepository", "update_video_path"): "the source's own row; records no change",
    ("SourceRepository", "set_collections"): "the source's own row; records no change",
}

# The concrete owner each port name stands for here.
OWNERS: dict[str, type] = {
    "WordStateRepository": SqlaWordStateRepository,
    "OccurrenceRepository": SqlaOccurrenceRepository,
    "CandidateRepository": SqlaCandidateRepository,
    "SourceRepository": SqlaSourceRepository,
    "WordMarkRepository": SqlaWordMarkRepository,
    "AnkiSyncRepository": SqlaAnkiSyncRepository,
    "SettingsRepository": SqlaSettingsRepository,
    "CandidateMeaningRepository": SqlaCandidateMeaningRepository,
    "CandidateMediaRepository": SqlaCandidateMediaRepository,
    "CandidateTTSRepository": SqlaCandidateTTSRepository,
    "CandidateClozeRepository": SqlaCandidateClozeRepository,
    "CandidatePronunciationRepository": SqlaCandidatePronunciationRepository,
    "CandidateMeaningImageRepository": SqlaCandidateMeaningImageRepository,
}


class _Polisher:
    """The AI service as polish uses it: answers each phrase with the text it is given."""

    def __init__(self) -> None:
        self.answer = ""

    def polish_phrases_batch(self, system_prompt: str, user_prompt: str) -> list[PolishedPhrase]:
        del system_prompt, user_prompt
        return [PolishedPhrase(phrase_index=1, phrase=self.answer)]


class _Anki:
    """Anki as export uses it: every note is added under a new id."""

    def __init__(self) -> None:
        self.connector = MagicMock()
        self.connector.is_available.return_value = True
        self.connector.get_model_field_names.return_value = _EveryField()
        self.connector.find_notes_by_target.return_value = []
        self._next = FIRST_NOTE
        self.connector.add_notes.side_effect = self._add

    def _add(self, **_kwargs: object) -> list[int]:
        self._next += 1
        return [self._next]


class _EveryField(list[str]):
    def __contains__(self, name: object) -> bool:
        return True


class _ScenarioContainer(Container):
    """The app's container on the scenario's database, with only the adapters outside the
    database faked: Anki and the AI service. A level change rebuilds every source at once,
    not on a thread of its own."""

    def __init__(self, clock: FixedClock, anki: _Anki, polisher: _Polisher) -> None:
        super().__init__(clock=clock)
        self._anki_connector = anki.connector
        self._polisher = polisher

    def use(self, factory: sessionmaker[Session]) -> None:
        self._session_factory = factory

    def _ai_service(self, settings_repo: SqlaSettingsRepository) -> AIService:  # type: ignore[override]
        del settings_repo
        return self._polisher  # type: ignore[return-value]

    def _rebuild_launcher(self) -> BackgroundSourcesRebuildLauncher:
        work = self.session_work()
        return BackgroundSourcesRebuildLauncher(
            scope_operations=lambda: work.open(self.scope_operation_use_case),
            spawn=lambda run: run(),
            passes=RebuildPasses(),
        )


@dataclass
class _Scenario:
    """What every example starts from: the container, its clock and fakes, and the
    processed corpus with its projection, kept in a database of its own."""

    container: _ScenarioContainer
    clock: FixedClock
    anki: _Anki
    polisher: _Polisher
    corpus: sqlite3.Connection

    def fresh(self) -> sessionmaker[Session]:
        """A database of its own holding the corpus, for one example."""
        engine = _memory_engine()
        connection = engine.raw_connection()
        try:
            self.corpus.backup(connection.driver_connection)  # type: ignore[arg-type]
        finally:
            connection.close()
        self.clock.moment = NOW
        factory = sessionmaker(bind=engine)
        self.container.use(factory)
        return factory


def _memory_engine() -> Engine:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


@pytest.fixture(scope="module")
def scenario() -> Iterator[_Scenario]:
    clock = FixedClock(NOW)
    anki = _Anki()
    polisher = _Polisher()
    container = _ScenarioContainer(clock, anki, polisher)
    engine = _memory_engine()
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    container.use(factory)
    _process_corpus(container, factory)
    corpus = sqlite3.connect(":memory:", check_same_thread=False)
    connection = engine.raw_connection()
    try:
        connection.driver_connection.backup(corpus)
    finally:
        connection.close()
    yield _Scenario(container, clock, anki, polisher, corpus)
    corpus.close()


def _process_corpus(container: _ScenarioContainer, factory: sessionmaker[Session]) -> None:
    """The sources processed as the app does, every card generated, the projection built."""
    with factory() as session:
        for source_id, lines in SOURCES.items():
            session.execute(text(
                "INSERT INTO sources (id, title, status, role, created_at)"
                " VALUES (:id, :title, 'new', 'content', '2026-01-01 00:00:00')"
            ), {"id": source_id, "title": f"Source {source_id}"})
            SqlaDocumentRepository(session).save(source_id, Document((Paragraph(
                lines=tuple(Line(line) for line in lines), mode=ParagraphMode.FLOW,
            ),)))
        session.execute(text(
            "INSERT INTO collections (id, name, position, created_at)"
            " VALUES (:id, 'Shared', 0, '2026-01-01 00:00:00')"
        ), {"id": COLLECTION})
        session.execute(text(
            "UPDATE sources SET collection_id = :collection WHERE id IN (1, 2, :video)"
        ), {"collection": COLLECTION, "video": VIDEO_SOURCE})
        session.commit()
    for source_id in SOURCES:
        with factory() as session:
            processing = container.process_source_use_case(session)
            processing.start(source_id)
            processing.execute(source_id)
    container.session_work().write(_video)
    with factory() as session:
        phrase_ids = list(session.scalars(text("SELECT id FROM phrases ORDER BY id")))
    for phrase_id in phrase_ids:
        container.session_work().write(lambda s, p=phrase_id: _ready(s, p))
    container.session_work().write(_two_known_entries)
    container.rebuild_card_states()


def _video(session: Session) -> None:
    """Source 4 becomes a downloaded video file, its first cards with clips as VIDEO_MEDIA
    says."""
    session.execute(text(
        "UPDATE sources SET format = 'video_file', kind = 'subtitles', video_path = :path"
        " WHERE id = :id"
    ), {"path": VIDEO_FILE, "id": VIDEO_SOURCE})
    phrase_ids = session.scalars(text(
        "SELECT p.id FROM phrases p JOIN candidates c ON c.id = p.candidate_id"
        " WHERE c.source_id = :id AND p.shown_by IS NOT NULL ORDER BY p.id"
    ), {"id": VIDEO_SOURCE}).all()
    media = SqlaCandidateMediaRepository(session, SessionChangeRecorder(session))
    for phrase_id, (start, end, picture) in zip(phrase_ids, VIDEO_MEDIA, strict=False):
        media.upsert_for_phrase(phrase_id, CandidateMedia(
            candidate_id=0, screenshot_path=picture, audio_path=None,
            start_ms=start, end_ms=end, generated_at=NOW,
        ))


def _two_known_entries(session: Session) -> None:
    """One lemma listed Known for two parts of speech, as lists written before one entry
    per lemma were kept: taking one off leaves the other."""
    marks = SqlaWordMarkRepository(session, SessionChangeRecorder(session))
    for pos in TWO_KNOWN_POS:
        marks.mark_known(TWO_KNOWN_LEMMA, pos)


def _ready(session: Session, phrase_id: int) -> None:
    """A meaning and speech: the card can go to Anki."""
    recorder = SessionChangeRecorder(session)
    SqlaCandidateMeaningRepository(session, recorder).upsert_for_phrase(phrase_id, _meaning())
    SqlaCandidateTTSRepository(session, recorder).upsert_for_phrase(
        phrase_id, CandidateTTS(candidate_id=0, audio_path=f"/media/p{phrase_id}.mp3",
                                generated_at=NOW),
    )


def _meaning() -> CandidateMeaning:
    return CandidateMeaning(
        candidate_id=0, meaning="what it means", translation=None, synonyms=None,
        examples=None, ipa=None, generated_at=NOW,
    )


class _Reached:
    """The owner write methods the scenarios called."""

    def __init__(self) -> None:
        self.methods: set[tuple[str, str]] = set()

    def watch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for port, method in WRITE_CASES:
            owner = OWNERS[port]
            original = getattr(owner, method)
            monkeypatch.setattr(owner, method, self._counted(port, method, original))

    def _counted(
        self, port: str, method: str, original: Callable[..., object],
    ) -> Callable[..., object]:
        def counted(*args: object, **kwargs: object) -> object:
            self.methods.add((port, method))
            return original(*args, **kwargs)

        return counted


class _Projection(RuleBasedStateMachine):
    """Random sequences of the app's use cases; after each, the projection is checked."""

    scenario: ClassVar[_Scenario]

    @initialize()
    def start(self) -> None:
        self.factory = self.scenario.fresh()
        self.container = self.scenario.container

    # --- what the steps work on ---------------------------------------------------------

    def _live_cards(self) -> list[Occurrence]:
        with self.factory() as session:
            occurrences = SqlaOccurrenceRepository(session, SessionChangeRecorder(session))
            return [
                occurrence
                for source_id in self._sources()
                for occurrence in occurrences.by_source(source_id)
                if occurrence.shown_by is not None
            ]

    def _card(self, pick: int) -> Occurrence | None:
        cards = sorted(self._live_cards(), key=lambda o: o.id or 0)
        return cards[pick % len(cards)] if cards else None

    def _sources(self) -> list[int]:
        with self.factory() as session:
            return sorted(
                s.id for s in SqlaSourceRepository(session, SessionChangeRecorder(session))
                .list_all() if s.id is not None
            )

    def _lemma_of(self, card: Occurrence) -> str:
        with self.factory() as session:
            word = SqlaCandidateRepository(session, SessionChangeRecorder(session)).get_by_id(
                card.candidate_id,
            )
        assert word is not None
        return word.lemma

    def _text_with_lemma(self, card: Occurrence, pick: int) -> str:
        """Another card's text that holds the card's lemma, else the card's own."""
        lemma = self._lemma_of(card)
        others = [
            o.phrase.text for o in self._live_cards()
            if o.id != card.id and self._lemma_of(o) == lemma
        ]
        return others[pick % len(others)] if others else card.phrase.text

    def _refusable(self, step: Callable[[Session], object]) -> None:
        """A step the rules may refuse; a refused write leaves everything as it was."""
        with self.factory() as session:
            try:
                step(session)
            except DomainError:
                session.rollback()

    # --- the steps ------------------------------------------------------------------------

    @rule(pick=PICK, button=st.sampled_from(Press))
    def press(self, pick: int, button: Press) -> None:
        card = self._card(pick)
        if card is not None and card.id is not None:
            phrase_id = card.id
            self._refusable(
                lambda s: self.container.decide_phrase_use_case(s).decide(phrase_id, button),
            )

    @rule(pick=PICK, button=st.sampled_from(Press))
    def press_and_undo(self, pick: int, button: Press) -> None:
        """The same button twice: the second press takes the first back."""
        self.press(pick, button)
        self.press(pick, button)

    @rule(pick=PICK, word=st.integers(min_value=0, max_value=20))
    def report_unknown_word(self, pick: int, word: int) -> None:
        card = self._card(pick)
        if card is not None and card.id is not None:
            phrase_id, request = card.id, ReportCandidateRequest(unknown_words=[word])
            self._refusable(
                lambda s: self.container.report_candidate_use_case(s).execute(phrase_id, request),
            )

    @rule(pick=PICK, word=st.integers(min_value=0, max_value=20))
    def list_known(self, pick: int, word: int) -> None:
        card = self._card(pick)
        if card is not None:
            words = card.phrase.words
            lemma = words[word % len(words)].lemma
            self._refusable(
                lambda s: self.container.manage_known_words_use_case(s).add_bulk([lemma]),
            )

    @rule(pick=PICK)
    def unlist_known(self, pick: int) -> None:
        with self.factory() as session:
            entries = self.container.manage_known_words_use_case(session).list_all()
        if entries:
            key = entries[pick % len(entries)].removal_key
            self._refusable(lambda s: self.container.manage_known_words_use_case(s).remove(key))

    @rule(pick=PICK, word=st.integers(min_value=0, max_value=20))
    def report_then_unlist_unknown(self, pick: int, word: int) -> None:
        self.report_unknown_word(pick, word)
        self.unlist_unknown(pick)

    @rule(pick=PICK)
    def unlist_unknown(self, pick: int) -> None:
        with self.factory() as session:
            entries = self.container.manage_unknown_words_use_case(session).list_all()
        if entries:
            entry_id = entries[pick % len(entries)].id
            self._refusable(
                lambda s: self.container.manage_unknown_words_use_case(s).delete(entry_id),
            )

    @rule(pick=PICK)
    def press_an_exported_card_again(self, pick: int) -> None:
        """Its button pressed again on a card in Anki: the binding is released."""
        with self.factory() as session:
            bound = list(session.scalars(text(
                "SELECT a.phrase_id FROM anki_synced_cards a JOIN phrases p ON p.id = a.phrase_id"
                " WHERE a.released_at IS NULL ORDER BY a.phrase_id",
            )))
            choices = dict(session.execute(text("SELECT id, choice FROM phrases")).all())
        if bound:
            phrase_id = bound[pick % len(bound)]
            button = Press(choices[phrase_id]) if choices[phrase_id] in set(Press) else Press.LEARN
            self._refusable(
                lambda s: self.container.decide_phrase_use_case(s).decide(phrase_id, button),
            )

    @rule(pick=PICK)
    def known_in_two_parts_of_speech_then_one_off(self, pick: int) -> None:
        """Known on words of one lemma read as two parts of speech, then one entry off."""
        with self.factory() as session:
            pairs = session.execute(text(
                "SELECT min(p1.id), min(p2.id) FROM candidates c1"
                " JOIN candidates c2 ON lower(c2.lemma) = lower(c1.lemma) AND c2.pos > c1.pos"
                " JOIN phrases p1 ON p1.candidate_id = c1.id AND p1.shown_by IS NOT NULL"
                " JOIN phrases p2 ON p2.candidate_id = c2.id AND p2.shown_by IS NOT NULL"
                " GROUP BY c1.id, c2.id ORDER BY 1",
            )).all()
        if not pairs:
            return
        for phrase_id in pairs[pick % len(pairs)]:
            self._refusable(lambda s, p=phrase_id: self.container.decide_phrase_use_case(
                s,
            ).press_unless_done(p, Press.KNOWN))
        self.unlist_known(pick)

    @rule()
    def export(self) -> None:
        self._refusable(lambda s: self.container.sync_to_anki_use_case(s).execute(
            SourceScope.all(), ExportGroup.READY,
        ))

    @rule(pick=PICK, kinds=st.permutations(CONTENT_KINDS))
    def content(self, pick: int, kinds: list[str]) -> None:
        """What generation, media and pictures write for a card, every kind in one write."""
        card = self._card(pick)
        if card is not None and card.id is not None:
            phrase_id, word_id = card.id, card.candidate_id
            self.container.session_work().write(
                lambda s: [_write_content(s, kind, phrase_id, word_id) for kind in kinds],
            )

    @rule(pick=PICK)
    def meaning_with_ipa(self, pick: int) -> None:
        """A meaning that brings the word's IPA: a word without recordings gets a row holding
        only the IPA, which is no pronunciation."""
        card = self._card(pick)
        if card is not None and card.id is not None:
            phrase_id, word_id = card.id, card.candidate_id
            self.container.session_work().write(
                lambda s: SqlaCandidateMeaningRepository(
                    s, SessionChangeRecorder(s),
                ).upsert_for_phrase(phrase_id, replace(_meaning(), candidate_id=word_id,
                                                       ipa=IPA)),
            )

    @rule(pick=PICK, text_pick=PICK)
    def polish(self, pick: int, text_pick: int) -> None:
        card = self._card(pick)
        if card is not None and card.id is not None:
            self.scenario.polisher.answer = self._text_with_lemma(card, text_pick)
            ref = PhraseRef(card.id, card.revision)
            self._refusable(
                lambda s: self.container.phrase_polish_use_case(s).execute_batch([ref]),
            )

    @rule(pick=PICK, reverted=st.booleans())
    def revert_polish(self, pick: int, reverted: bool) -> None:
        card = self._card(pick)
        if card is not None and card.id is not None:
            phrase_id = card.id
            self._refusable(lambda s: self.container.revert_phrase_polish_use_case(s).execute(
                phrase_id, reverted,
            ))

    @rule(pick=PICK)
    def edit_boundary(self, pick: int) -> None:
        """The card's phrase becomes its whole line."""
        card = self._card(pick)
        line = self._line_of(card) if card is not None else None
        if card is not None and card.id is not None and line is not None:
            phrase_id = card.id
            selection = self._line(self._source_of(card), line)
            self._refusable(lambda s: self.container.set_phrase_boundary_use_case(s).execute(
                phrase_id, selection,
            ))

    @rule(pick=PICK, text_pick=PICK)
    def replace_with_example(self, pick: int, text_pick: int) -> None:
        card = self._card(pick)
        if card is not None and card.id is not None:
            phrase_id, example = card.id, self._text_with_lemma(card, text_pick)
            self._refusable(lambda s: self.container.replace_with_example_use_case(s).execute(
                phrase_id, example,
            ))

    @rule(source_pick=PICK, line=st.integers(min_value=0, max_value=4),
          word=st.integers(min_value=0, max_value=12))
    def add_word_from_text(self, source_pick: int, line: int, word: int) -> None:
        sources = self._sources()
        source_id = sources[source_pick % len(sources)]
        selection = self._line(source_id, line % len(SOURCES[source_id]))
        self._refusable(lambda s: self.container.add_manual_candidate_use_case(s).execute(
            source_id, [word], selection,
        ))

    @rule(source_pick=PICK, mode=st.sampled_from(REBUILD_MODES))
    def rebuild(self, source_pick: int, mode: RebuildMode) -> None:
        sources = self._sources()
        source_id = sources[source_pick % len(sources)]
        self._refusable(
            lambda s: self.container.rebuild_source_use_case(s).execute(source_id, mode),
        )

    @rule(level=st.sampled_from(LEVELS))
    def change_level(self, level: str) -> None:
        self._refusable(
            lambda s: self.container.manage_settings_use_case(s).update_cefr_level(level),
        )

    @precondition(lambda self: len(self._sources()) > 1)
    @rule(source_pick=PICK)
    def delete_source(self, source_pick: int) -> None:
        sources = self._sources()
        source_id = sources[source_pick % len(sources)]
        self._refusable(lambda s: self.container.delete_source_use_case(s).execute(source_id))

    @rule(
        kind=st.sampled_from(GENERATED_KINDS), cards=st.sampled_from(GENERATION_SCOPES),
        collection=st.booleans(), source_pick=PICK,
    )
    def queue_generation(
        self, kind: GenerationKind, cards: GenerationScope, collection: bool, source_pick: int,
    ) -> None:
        """✨ on a source or the collection: jobs queued, results of ALL scopes dropped; a
        kind the source has no use for, or a video not downloaded, is refused."""
        sources = self._sources()
        scope = SourceScope.collection(COLLECTION) if collection else SourceScope.source(
            sources[source_pick % len(sources)],
        )
        self._refusable(
            lambda s: self.container.run_generation_use_case(s).execute(scope, kind, cards),
        )

    @rule(pick=PICK, blocked=st.booleans())
    def jobs_run_and_fail(self, pick: int, blocked: bool) -> None:
        """The worker takes some queued jobs and some of them fail, with the AI blocked here
        or another error."""
        error = AI_UNAVAILABLE_MARKER if blocked else "AI proxy error: boom"
        with self.factory() as session:
            session.execute(text(
                "UPDATE jobs SET status = 'running' WHERE status = 'queued' AND id % 3 = :pick"
            ), {"pick": pick % 3})
            session.execute(text(
                "UPDATE jobs SET status = 'failed', error = :error"
                " WHERE status = 'running' AND id % 2 = :pick"
            ), {"error": error, "pick": pick % 2})
            session.commit()

    @rule(pick=PICK)
    def jobs_finish(self, pick: int) -> None:
        """The worker finishes some jobs: their result written, the job gone. A polish job
        finishes without a text: the polish step writes texts."""
        with self.factory() as session:
            done = session.execute(text(
                "SELECT id, job_type, phrase_id, candidate_id FROM jobs"
                " WHERE status IN ('queued', 'running') AND id % 2 = :pick"
            ), {"pick": pick % 2}).all()

        def finish(s: Session) -> None:
            for job_id, job_type, phrase_id, word_id in done:
                if phrase_id is not None or job_type == "pronunciation":
                    _write_result(s, job_type, phrase_id, word_id)
                s.execute(text("DELETE FROM jobs WHERE id = :id"), {"id": job_id})

        if done:
            self.container.session_work().write(finish)

    @rule(pick=PICK)
    def drop_timecodes_of_a_queued_clip(self, pick: int) -> None:
        """A Rebuild loses the timecodes of a phrase whose clip is queued and not made yet:
        its job stays, the card no longer gets a clip."""
        with self.factory() as session:
            queued = session.scalars(text(
                "SELECT j.phrase_id FROM jobs j JOIN candidate_media m"
                " ON m.phrase_id = j.phrase_id WHERE j.job_type = 'media'"
                " AND m.screenshot_path IS NULL AND m.audio_path IS NULL"
                " AND m.start_ms IS NOT NULL ORDER BY j.phrase_id"
            )).all()
        if queued:
            phrase_id = queued[pick % len(queued)]
            self.container.session_work().write(
                lambda s: SqlaCandidateMediaRepository(
                    s, SessionChangeRecorder(s),
                ).set_timecodes({phrase_id: None}),
            )

    @precondition(lambda self: VIDEO_SOURCE in self._sources())
    @rule(state=st.sampled_from(VIDEO_STATES))
    def video(self, state: str) -> None:
        """The video's file is there, not there, or on its way."""
        with self.factory() as session:
            session.execute(text("UPDATE sources SET video_path = :path WHERE id = :id"), {
                "path": VIDEO_FILE if state == "downloaded" else None, "id": VIDEO_SOURCE,
            })
            session.execute(text(
                "DELETE FROM jobs WHERE job_type = 'video_download' AND source_id = :id"
            ), {"id": VIDEO_SOURCE})
            if state == "downloading":
                session.execute(text(
                    "INSERT INTO jobs (job_type, source_id, status, created_at)"
                    " VALUES ('video_download', :id, 'queued', '2026-01-01 00:00:00')"
                ), {"id": VIDEO_SOURCE})
            session.commit()

    @rule(step=st.sampled_from(CLOCK_STEPS))
    def time_passes(self, step: timedelta) -> None:
        self.scenario.clock.moment += step
        self.container.tick_card_states()

    def _line_of(self, card: Occurrence) -> int | None:
        """The line of the card's phrase; for an example, the line of a phrase of its word
        that has one."""
        if card.phrase_position is not None:
            return card.phrase_position.start_line
        with self.factory() as session:
            occurrences = SqlaOccurrenceRepository(session, SessionChangeRecorder(session))
            placed = [o for o in occurrences.of_word(card.candidate_id) if o.phrase_position]
        return placed[0].phrase_position.start_line if placed else None  # type: ignore[union-attr]

    def _source_of(self, card: Occurrence) -> int:
        with self.factory() as session:
            word = SqlaCandidateRepository(session, SessionChangeRecorder(session)).get_by_id(
                card.candidate_id,
            )
        assert word is not None
        return word.source_id

    @staticmethod
    def _line(source_id: int, line: int) -> SelectionDTO:
        return SelectionDTO(
            start_block=0, start_line=line, start_char=0,
            end_block=0, end_line=line, end_char=len(SOURCES[source_id][line]),
        )

    # --- the check -----------------------------------------------------------------------

    @invariant()
    def projection_equals_the_review(self) -> None:
        with self.factory() as session:
            stored = self.container.card_state_projector(session).stored()
        with self.factory() as session, _projection_unread():
            live = self.container.live_card_states(session).compute()
        assert differences(stored, live) == []
        rows = {card.row.phrase_id: card.row for card in stored.cards if not card.removed}
        with self.factory() as session, _live_standing_once():
            container = self.container
            sources = _source_ids(session)
            with _projection_unread():
                cards = container._review_cards(session).of_sources(sources)  # noqa: SLF001
            sorter = _check_sorter(container, session)
            step = container._threshold_resolver(session).resolve().zipf  # noqa: SLF001

            def stored_standing(card: ReviewCard) -> CardStanding:
                row = rows[card.phrase_id]
                return CardStanding(
                    row.is_done, row.sections.at(step), row.new_counts.at(step),
                )

            for order in CandidateSortOrder:
                with _projection_unread():
                    today = sorter.arrange(cards, order, source_order=sources).cards
                projected = sort_cards(
                    cards, order, stored_standing,
                    usage_order=sorter.usage_order(), source_order=sources,
                )
                assert [c.phrase_id for c in projected] == [c.phrase_id for c in today], order
            with _projection_unread():
                sets = {
                    scope: container._live_scope_resolver(session).reviewable_sources(scope)  # noqa: SLF001
                    for scope in (
                        *(SourceScope.source(source_id) for source_id in sources),
                        SourceScope.collection(COLLECTION),
                    )
                }
            self._screens_equal_the_review(session, sources, cards, sets)
            self._open_reviews_hold_todays_order(session, sorter, cards, sets)

    def _open_reviews_hold_todays_order(
        self,
        session: Session,
        sorter: CandidateSorter,
        cards: list[ReviewCard],
        sets: dict[SourceScope, list[Source]],
    ) -> None:
        """An open review of every set, in every order and with every section open, lists the
        set's cards in today's order, each in today's section."""
        for scope, members in sets.items():
            ids = [s.id for s in members if s.id is not None]
            of_set = [c for c in cards if c.word.source_id in ids]
            for order in CandidateSortOrder:
                with _projection_unread():
                    today = sorter.arrange(of_set, order, source_order=ids)
                assert self._opened(session, scope, order) == [
                    (c.phrase_id, today.section(c)) for c in today.cards
                ], (scope, order)

    def _opened(
        self, session: Session, scope: SourceScope, order: CandidateSortOrder,
    ) -> list[tuple[int, CandidateSection]]:
        """The card rows of the set's open review with every section open, each with its held
        section. The answer's windows and cards are left out: the order is what is checked."""
        with patch.object(ReviewAnswer, "of", lambda _answer, review_id, *_a, **_k: review_id):
            review_id = self.container.open_review_use_case(session).execute(OpenReviewRequest(
                scope=scope.token, sort=order, open_sections=list(CandidateSection),
            ))
        with self.container._review_order_store.hold(review_id) as review:  # type: ignore[arg-type]  # noqa: SLF001
            held = {card.phrase_id: card.section for card in review.order.cards}
            return [
                (row.phrase_id, held[row.phrase_id])
                for row in review.layout().rows if isinstance(row, CardRow)
            ]

    def _screens_equal_the_review(
        self,
        session: Session,
        sources: list[int],
        cards: list[ReviewCard],
        sets: dict[SourceScope, list[Source]],
    ) -> None:
        """The header of every review set, each source's progress on the sources screen and
        the ✨ counts, read from the projection, are what the review computes live: the
        progress of a set is its cards' as `CardViews.listed` sums them, its sources'."""
        container = self.container
        of_source = {i: [c for c in cards if c.word.source_id == i] for i in sources}
        with _projection_unread():
            live = container._candidate_sorter(session).progress(of_source)  # noqa: SLF001
            jobs = SqlaJobRepository(session).get_jobs_for_phrases([c.phrase_id for c in cards])
        projected = container._review_progress(session).of_sources(sources)  # noqa: SLF001
        assert {i: p.progress for i, p in projected.items()} == live
        assert {i: p.cards for i, p in projected.items()} == {
            i: len(found) for i, found in of_source.items()
        }
        with _projection_unread():
            generation = {
                i: container.live_generation_status(session).execute(SourceScope.source(i))
                for i in sources
            }
        for scope, members in sets.items():
            ids = [s.id for s in members if s.id is not None]
            expected = _summed_status([generation[i] for i in ids])
            progress = sum((live[i] for i in ids), DecisionProgress())
            header = container.review_header(session).of(scope)
            assert header.progress == ProgressDTO.of(progress), scope
            assert header.status == derive_review_status(
                stored_status_of_set(s.status for s in members), progress,
            ).value, scope
            assert header.learn_count == sum(
                SqlaCardQuery(session).learn_counts(ids).values(),
            ), scope
            # The front's rule over the cards' meaning status, an active job before a failed.
            assert header.ai_unavailable == any(
                (job := jobs.get(card.phrase_id, {}).get(JobType.MEANING.value)) is not None
                and job.status is JobStatus.FAILED and is_ai_unavailable(job.error)
                for i in ids for card in of_source[i]
            ), scope
            assert container.get_generation_status_use_case(session).execute(scope) == (
                expected
            ), scope


def _summed_status(of_sources: list[GenerationStatusDTO]) -> GenerationStatusDTO:
    """The ✨ status of a set from its sources' as `LiveGenerationStatus` sums them, each
    source computed live once per check rather than once per set holding it."""
    per_kind: dict[GenerationKind, list[GenerationKindStatusDTO]] = {
        kind: [] for kind in TARGET_ORDER
    }
    for status in of_sources:
        for kind in status.kinds:
            per_kind[kind.kind].append(kind)
    return GenerationStatusDTO(
        kinds=[summed(kinds) for kinds in per_kind.values() if kinds],
        in_progress=any(status.in_progress for status in of_sources),
    )


def _check_sorter(container: Container, session: Session) -> CandidateSorter:
    """Today's sorter with what the user knows, the threshold and the settings read once for
    a whole check: nothing writes inside it."""
    knowledge = container._user_knowledge(session).current()  # noqa: SLF001
    threshold = container._threshold_resolver(session).resolve()  # noqa: SLF001
    settings = SqlaSettingsRepository(session, SessionChangeRecorder(session))
    return CandidateSorter(
        settings_repo=SimpleNamespace(get=cache(settings.get)),  # type: ignore[arg-type]
        threshold_resolver=SimpleNamespace(resolve=lambda: threshold),  # type: ignore[arg-type]
        knowledge=SimpleNamespace(current=lambda: knowledge),  # type: ignore[arg-type]
    )


@contextmanager
def _live_standing_once() -> Iterator[None]:
    """Today's standing and section of a card computed by today's rules once per check and
    shared by every `CandidateSorter` call in it, which still sorts as today: what the user
    knows does not change inside one check."""
    standing_rule = candidate_sorting.live_standing
    section_rule = candidate_sorter.card_section
    standings: dict[int, CardStanding] = {}
    sections: dict[int, CandidateSection] = {}

    def live_standing(
        knowledge: UserKnowledge | None, threshold: FrequentWordThreshold | None,
    ) -> Callable[[ReviewCard], CardStanding]:
        standing = standing_rule(knowledge, threshold)

        def once(card: ReviewCard) -> CardStanding:
            if card.phrase_id not in standings:
                standings[card.phrase_id] = standing(card)
            return standings[card.phrase_id]

        return once

    def card_section(
        card: ReviewCard,
        knowledge: UserKnowledge | None,
        threshold: FrequentWordThreshold | None,
    ) -> CandidateSection:
        if card.phrase_id not in sections:
            sections[card.phrase_id] = section_rule(card, knowledge, threshold)
        return sections[card.phrase_id]

    with (
        patch.object(candidate_sorting, "live_standing", live_standing),
        patch.object(candidate_sorter, "card_section", card_section),
    ):
        yield


@contextmanager
def _projection_unread() -> Iterator[None]:
    """The live references compute without the stored projection: reading it fails."""
    def refused(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("a live reference read the stored projection")

    with patch.multiple(
        SqlaCardStateQuery, **dict.fromkeys(CardStateQuery.__abstractmethods__, refused),
    ):
        yield


def _source_ids(session: Session) -> list[int]:
    return sorted(session.scalars(select(text("id")).select_from(text("sources"))))


def _write_result(
    session: Session, job_type: str, phrase_id: int | None, word_id: int,
) -> None:
    """What a finished job of the type writes; a clip is cut at the phrase's timecodes."""
    recorder = SessionChangeRecorder(session)
    if job_type == "pronunciation":
        SqlaCandidatePronunciationRepository(session, recorder).upsert(
            CandidatePronunciation(word_id, SHARED_FILE, None, NOW),
        )
        return
    assert phrase_id is not None
    if job_type == "meaning":
        SqlaCandidateMeaningRepository(session, recorder).upsert_for_phrase(phrase_id, _meaning())
    elif job_type == "tts":
        SqlaCandidateTTSRepository(session, recorder).upsert_for_phrase(
            phrase_id, CandidateTTS(candidate_id=0, audio_path=SHARED_FILE, generated_at=NOW),
        )
    elif job_type == "media":
        media = SqlaCandidateMediaRepository(session, recorder)
        timed = media.get_by_phrase_id(phrase_id)
        media.upsert_for_phrase(phrase_id, CandidateMedia(
            candidate_id=0, screenshot_path=CLIP, audio_path=SHARED_FILE,
            start_ms=timed.start_ms if timed else None, end_ms=timed.end_ms if timed else None,
            generated_at=NOW,
        ))


def _write_content(session: Session, kind: str, phrase_id: int, word_id: int) -> None:
    recorder = SessionChangeRecorder(session)
    meanings = SqlaCandidateMeaningRepository(session, recorder)
    speech = SqlaCandidateTTSRepository(session, recorder)
    media = SqlaCandidateMediaRepository(session, recorder)
    clozes = SqlaCandidateClozeRepository(session, recorder)
    images = SqlaCandidateMeaningImageRepository(session, recorder)
    match kind:
        case "meaning":
            meanings.upsert_for_phrase(phrase_id, _meaning())
        case "no meaning":
            meanings.delete_by_phrase_id(phrase_id)
        case "speech":
            speech.upsert_for_phrase(
                phrase_id, CandidateTTS(candidate_id=0, audio_path=SHARED_FILE, generated_at=NOW),
            )
        case "no speech":
            speech.delete_by_phrase_id(phrase_id)
        case "clip":
            media.upsert_for_phrase(phrase_id, CandidateMedia(
                candidate_id=0, screenshot_path=SHARED_FILE, audio_path=SHARED_FILE,
                start_ms=0, end_ms=1000, generated_at=NOW,
            ))
        case "no clip picture":
            media.clear_phrase_paths(phrase_id, clear_screenshot=True, clear_audio=False)
        case "lost file":
            media.clear_missing_file(SHARED_FILE)
        case "timecodes":
            media.set_timecodes({phrase_id: (0, 1000)})
        case "cloze":
            clozes.upsert_for_phrase(
                phrase_id, CandidateCloze(0, (0,), ClozeHintKind.NONE, None, "hidden"),
            )
        case "no cloze":
            clozes.delete_by_phrase_id(phrase_id)
        case "pronunciation":
            SqlaCandidatePronunciationRepository(session, recorder).upsert(
                CandidatePronunciation(word_id, SHARED_FILE, None, NOW),
            )
        case "picture":
            images.upsert(CandidateMeaningImage(word_id, "/media/picture.jpg"))
        case "no picture":
            images.delete_by_candidate_id(word_id)


def test_the_projection_equals_the_review_after_every_step(
    scenario: _Scenario, monkeypatch: pytest.MonkeyPatch,
) -> None:
    reached = _Reached()
    reached.watch(monkeypatch)
    _Projection.scenario = scenario
    _tour(_Projection())
    _timer_tour(_Projection())
    _orphan_tour(_Projection())
    _generation_tour(_Projection())

    run_state_machine_as_test(_Projection, settings=settings(
        derandomize=True,
        deadline=None,
        database=None,
        max_examples=MAX_EXAMPLES,
        stateful_step_count=STEPS_PER_EXAMPLE,
        suppress_health_check=list(HealthCheck),
    ))

    missed = set(WRITE_CASES) - reached.methods - set(NOT_REACHED)
    assert not missed, (
        "Owner write methods no scenario reached: give each a step, or name it in"
        f" NOT_REACHED with why it cannot change card state: {sorted(missed)}"
    )
    assert not set(NOT_REACHED) - set(WRITE_CASES)


def _timer_tour(machine: _Projection) -> None:
    """A Learn in Anki whose timer comes due: its cards carry the moment, the tick writes
    what it changes."""
    for step in (
        machine.start,
        lambda: machine.press(0, Press.LEARN),
        machine.export,
        lambda: machine.time_passes(CLOCK_STEPS[-1]),
    ):
        step()
        machine.projection_equals_the_review()


def _generation_tour(machine: _Projection) -> None:
    """✨ on the collection and on single sources queues jobs, the worker fails some with
    the AI blocked and finishes others, the video comes and goes: the counts see running,
    failed and done cards of every kind, clips only for timed cards, and the header the
    blocked AI."""
    machine.start()
    scope = SourceScope.collection(COLLECTION)
    video = VIDEO_SOURCE - 1
    for step in (
        lambda: machine.press(0, Press.LEARN),
        lambda: machine.queue_generation(GenerationKind.MEANING, GenerationScope.ALL, True, 0),
        lambda: machine.queue_generation(
            GenerationKind.PRONUNCIATION, GenerationScope.MISSING, False, 0,
        ),
        lambda: machine.queue_generation(GenerationKind.POLISH, GenerationScope.ALL, False, 0),
        lambda: machine.queue_generation(GenerationKind.MEDIA, GenerationScope.ALL, False, video),
        lambda: machine.drop_timecodes_of_a_queued_clip(0),
    ):
        step()
        machine.projection_equals_the_review()
    with machine.factory() as session:
        dropped = session.scalars(text(
            "SELECT j.phrase_id FROM jobs j JOIN candidate_media m ON m.phrase_id = j.phrase_id"
            " WHERE j.job_type = 'media' AND m.start_ms IS NULL"
        )).all()
    assert dropped, "a queued clip lost its timecodes"
    machine.container.session_work().write(
        lambda s: SqlaCandidateMediaRepository(s, SessionChangeRecorder(s)).set_timecodes(
            dict.fromkeys(dropped, (0, 1000)),
        ),
    )
    machine.projection_equals_the_review()
    with machine.factory() as session:
        session.execute(text(
            "UPDATE jobs SET status = 'running' WHERE id IN (SELECT min(id) FROM jobs"
            " WHERE job_type = :kind UNION SELECT max(id) FROM jobs WHERE job_type = :kind)"
        ), {"kind": "meaning"})
        session.commit()
    machine.jobs_run_and_fail(0, blocked=True)
    machine.projection_equals_the_review()
    with machine.factory() as session:
        status = machine.container.get_generation_status_use_case(session).execute(scope)
        header = machine.container.review_header(session).of(scope)
    kinds = {k.kind: k for k in status.kinds}
    assert kinds[GenerationKind.MEANING].running > 0
    assert kinds[GenerationKind.MEANING].failed > 0
    assert kinds[GenerationKind.POLISH].running > 0
    assert kinds[GenerationKind.MEDIA].running + kinds[GenerationKind.MEDIA].failed > 0
    assert header.ai_unavailable
    for step in (
        lambda: machine.queue_generation(
            GenerationKind.MEDIA, GenerationScope.FAILED, False, video,
        ),
        lambda: machine.jobs_finish(0),
        lambda: machine.jobs_finish(1),
        lambda: machine.video("not downloaded"),
        lambda: machine.video("downloading"),
        lambda: machine.video("downloaded"),
    ):
        step()
        machine.projection_equals_the_review()
    with machine.factory() as session:
        media = next(
            k for k in machine.container.get_generation_status_use_case(session).execute(
                SourceScope.source(VIDEO_SOURCE),
            ).kinds
            if k.kind is GenerationKind.MEDIA
        )
    assert media.done > 0


def _orphan_tour(machine: _Projection) -> None:
    """A binding no card holds whose timer comes due: "old", added from source 3's text,
    learned and exported, its source deleted, is still an other word in source 1."""
    machine.start()
    machine.add_word_from_text(ORPHAN_SOURCE - 1, 0, 0)
    with machine.factory() as session:
        phrase_id = session.execute(text(
            "SELECT p.id FROM phrases p JOIN candidates c ON c.id = p.candidate_id"
            " WHERE lower(c.lemma) = :lemma AND c.source_id = :source",
        ), {"lemma": ORPHAN_LEMMA, "source": ORPHAN_SOURCE}).scalar_one()
    machine.container.session_work().write(lambda s: _ready(s, phrase_id))
    with machine.factory() as session:
        machine.container.decide_phrase_use_case(session).decide(phrase_id, Press.LEARN)
    for step in (
        machine.export,
        lambda: machine.delete_source(ORPHAN_SOURCE - 1),
        lambda: machine.time_passes(CLOCK_STEPS[-1]),
    ):
        step()
        machine.projection_equals_the_review()
    with machine.factory() as session:
        orphans = session.execute(text(
            "SELECT count(*) FROM anki_synced_cards WHERE lower(lemma) = :lemma"
            " AND phrase_id IS NULL AND released_at IS NULL",
        ), {"lemma": ORPHAN_LEMMA}).scalar_one()
    assert orphans == 1


def _tour(machine: _Projection) -> None:
    """Every step once, in an order where each reaches its writes, checked after each: the
    random sequences start from here and need not happen upon them."""
    steps: list[Callable[[], None]] = [
        machine.start,
        lambda: machine.press(0, Press.LEARN),
        lambda: machine.press(1, Press.CLOZE),
        machine.export,
        lambda: machine.press_an_exported_card_again(0),
        lambda: machine.press_and_undo(2, Press.KNOWN),
        lambda: machine.report_then_unlist_unknown(3, 1),
        lambda: machine.list_known(4, 2),
        lambda: machine.unlist_known(0),
        lambda: machine.unlist_known(0),
        lambda: machine.meaning_with_ipa(7),
        lambda: machine.content(5, list(CONTENT_KINDS)),
        lambda: machine.polish(6, 0),
        lambda: machine.revert_polish(6, True),
        lambda: machine.replace_with_example(3, 0),
        lambda: machine.edit_boundary(len(machine._live_cards()) - 1),  # noqa: SLF001
        lambda: machine.add_word_from_text(0, 1, 3),
        # "lighthouse", a card of source 1 already: the user's pick shows it again.
        lambda: machine.add_word_from_text(0, 0, 1),
        lambda: machine.rebuild(0, RebuildMode.UPDATE),
        lambda: machine.rebuild(1, RebuildMode.RECUT),
        lambda: machine.change_level("C1"),
        lambda: machine.time_passes(CLOCK_STEPS[-1]),
        lambda: machine.delete_source(2),
    ]
    for step in steps:
        step()
        machine.projection_equals_the_review()


def test_the_corpus_holds_shared_lemmas_and_about_fifty_cards(scenario: _Scenario) -> None:
    factory = scenario.fresh()
    with factory() as session:
        lemmas = session.execute(text(
            "SELECT lower(lemma), count(DISTINCT source_id) FROM candidates GROUP BY 1",
        )).all()
        cards = session.execute(
            text("SELECT count(*) FROM phrases WHERE shown_by IS NOT NULL"),
        ).scalar_one()
    shared = [lemma for lemma, sources in lemmas if sources > 1]
    assert len(shared) >= 10, shared
    assert 40 <= cards <= 70, cards
