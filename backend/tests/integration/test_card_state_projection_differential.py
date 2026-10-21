"""The projection kept by `CardStateProjector.apply` and the time tick equals the review's
own computation after every step of random sequences of the app's real use cases (spec
§6.1): three sources sharing lemmas, about fifty cards, presses and their undo, reports,
the Known and Unknown lists, export and release, generated content, polish and its revert,
boundary edits, examples, words added from the text, Update and Re-cut, the level, source
deletion and the clock crossing an Anki timer.

After each step the stored rows equal `LiveCardStates` (statuses, done, wants generation,
sections and new-word counts at every threshold step, word statuses, phrase words), and the
review order of every sort order, computed from the stored rows, is today's order.

Every write method of the owners of facts is reached by some step, or is named here with
the reason it cannot change card state: a new write method without a scenario fails.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import MagicMock

import pytest
from backend.application.dto.candidate_dtos import SelectionDTO
from backend.application.dto.card_report_dtos import ReportCandidateRequest
from backend.application.utils.card_state_differences import differences
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_meaning_image import CandidateMeaningImage
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.exceptions import DomainError
from backend.domain.services.candidate_sorting import CardStanding, sort_cards
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.card_choice import Press
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.export_group import ExportGroup
from backend.domain.value_objects.learning_timer import LEARNING_KNOWN_AFTER
from backend.domain.value_objects.phrase_ref import PhraseRef
from backend.domain.value_objects.polished_phrase import PolishedPhrase
from backend.domain.value_objects.rebuild_mode import RebuildMode
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
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
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
    from backend.domain.ports.ai_service import AIService
    from backend.domain.value_objects.review_card import ReviewCard

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
}
LEVELS = ("A2", "B1", "B2", "C1")
REBUILD_MODES = (RebuildMode.UPDATE, RebuildMode.RECUT)
CLOCK_STEPS = (timedelta(days=1), LEARNING_KNOWN_AFTER + timedelta(days=1))
CONTENT_KINDS = (
    "meaning", "no meaning", "speech", "no speech", "clip", "no clip picture", "lost file",
    "timecodes", "cloze", "no cloze", "pronunciation", "picture", "no picture",
)
FIRST_NOTE = 5000
TWO_KNOWN_LEMMA = "tide"
TWO_KNOWN_POS = ("NOUN", "VERB")
SHARED_FILE = "/media/shared.mp3"
# A whole card is picked by its rank among the live cards, any number wrapping around.
PICK = st.integers(min_value=0, max_value=10_000)

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
        session.commit()
    for source_id in SOURCES:
        with factory() as session:
            processing = container.process_source_use_case(session)
            processing.start(source_id)
            processing.execute(source_id)
    with factory() as session:
        phrase_ids = list(session.scalars(text("SELECT id FROM phrases ORDER BY id")))
    for phrase_id in phrase_ids:
        container.session_work().write(lambda s, p=phrase_id: _ready(s, p))
    container.session_work().write(_two_known_entries)
    container.rebuild_card_states()


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
        with self.factory() as session:
            live = self.container.live_card_states(session).compute()
        assert differences(stored, live) == []
        rows = {card.row.phrase_id: card.row for card in stored.cards if not card.removed}
        with self.factory() as session:
            container = self.container
            sources = _source_ids(session)
            cards = container._review_cards(session).of_sources(sources)  # noqa: SLF001
            sorter = container._candidate_sorter(session)  # noqa: SLF001
            step = container._threshold_resolver(session).resolve().zipf  # noqa: SLF001

            def stored_standing(card: ReviewCard) -> CardStanding:
                row = rows[card.phrase_id]
                return CardStanding(
                    row.is_done, row.sections.at(step), row.new_counts.at(step),
                )

            for order in CandidateSortOrder:
                today = sorter.arrange(cards, order, source_order=sources).cards
                projected = sort_cards(
                    cards, order, stored_standing,
                    usage_order=sorter.usage_order(), source_order=sources,
                )
                assert [c.phrase_id for c in projected] == [c.phrase_id for c in today], order


def _source_ids(session: Session) -> list[int]:
    return sorted(session.scalars(select(text("id")).select_from(text("sources"))))


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
