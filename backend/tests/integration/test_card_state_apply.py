"""Every write projects its changes onto the stored card state before it commits: after
each kind of change the stored rows equal the review's own computation, and a card the
change did not move keeps its revision (spec §4, §5)."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.sync_to_anki import SyncToAnkiUseCase
from backend.application.utils.anki_template_renderer import NoteTemplates
from backend.application.utils.card_state_differences import differences
from backend.application.utils.card_state_projector import (
    CardStateProjector,
    ProjectorRecordedChangesError,
)
from backend.application.utils.export_queue import ExportQueue
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_meaning_image import CandidateMeaningImage
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.services.cloze_builder import ClozeBuilder
from backend.domain.value_objects.card_change import (
    BindingChanged,
    CardContentChanged,
    DecisionChanged,
    MarkChanged,
)
from backend.domain.value_objects.card_choice import Press
from backend.domain.value_objects.export_group import ExportGroup
from backend.domain.value_objects.learning_timer import known_on
from backend.domain.value_objects.phrase_origin_kind import ShownBy
from backend.domain.value_objects.source_scope import SourceScope
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_candidate_meaning_image_repository import (
    SqlaCandidateMeaningImageRepository,
)
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_candidate_tts_repository import (
    SqlaCandidateTTSRepository,
)
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_settings_repository import SqlaSettingsRepository
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork
from backend.infrastructure.persistence.sqla_word_mark_repository import SqlaWordMarkRepository
from sqlalchemy import text

from tests.card_state_support import (
    BROOD,
    BROOD_SECOND_PHRASE,
    DWELL,
    GLARE,
    GLEAM,
    HOVER,
    OH,
    ONE,
    SPARK,
    SPARK_EXPORTED,
    SPARK_TWO,
    TWO,
    insert_card_word,
    live_states,
    make_container,
    memory_factory,
    naive,
    seed,
    stored_states,
)
from tests.decision_support import NOW, Decisions
from tests.phrase_support import phrase
from tests.unit.application.scope_fakes import sources_scope_resolver
from tests.word_support import bind, phrase_id_of

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from datetime import datetime

    from backend.domain.value_objects.card_change import CardChange
    from backend.domain.value_objects.card_state_rows import StoredCardStates
    from backend.infrastructure.container import Container
    from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration

GLARE_TWO, CASES, QUILL = 20, 21, 22
SPARK_TWO_EXPORTED = NOW - timedelta(days=5)
NOTE = 777


@pytest.fixture()
def factory() -> Generator[sessionmaker[Session], None, None]:
    yield from memory_factory()


@pytest.fixture()
def world(factory: sessionmaker[Session]) -> World:
    seed(factory)
    return World(make_container(factory), factory)


class World:
    """The seeded world with its projection rebuilt; `write` runs one write of the app and
    `check` compares the projection after it with the live rows and the stored before."""

    def __init__(self, container: Container, factory: sessionmaker[Session]) -> None:
        self.container = container
        self.factory = factory
        self.before: StoredCardStates | None = None

    def rebuild(self) -> None:
        self.container.rebuild_card_states()

    def stored(self) -> StoredCardStates:
        return stored_states(self.container, self.factory)

    def write(self, change: Callable[[Session], object]) -> None:
        self.before = self.stored()
        self.container.session_work().write(change)

    def decide(self, phrase_id: int, button: Press) -> None:
        self.before = self.stored()
        with self.factory() as session:
            self.container.decide_phrase_use_case(session).decide(phrase_id, button)

    def check(self, *, touched: frozenset[int] = frozenset()) -> StoredCardStates:
        """Stored equals live; the cards whose row changed and the `touched` ones moved to
        the new revision, every other card kept its own."""
        after = self.stored()
        assert differences(after, live_states(self.container, self.factory)) == []
        before = self.before
        assert before is not None
        kept = {card.row.phrase_id: card for card in before.cards}
        moved: set[int] = set()
        for card in after.cards:
            old = kept.get(card.row.phrase_id)
            if old is None or (old.row, old.removed) != (card.row, card.removed):
                assert card.revision == after.revision, card
                moved.add(card.row.phrase_id)
            elif card.row.phrase_id in touched:
                assert card.revision == after.revision, card
            else:
                assert card.revision == old.revision, card
        if moved or touched:
            assert after.revision == before.revision + 1
        return after

    def was(self, phrase_id: int) -> tuple[bool, bool, int]:
        """The card as it was before the last write."""
        assert self.before is not None
        return _card(self.before, phrase_id)


def _card(states: StoredCardStates, phrase_id: int) -> tuple[bool, bool, int]:
    """(removed, done, new words at no threshold) of the card."""
    card = next(c for c in states.cards if c.row.phrase_id == phrase_id)
    return card.removed, card.row.is_done, card.row.new_counts.at(None)


def _recorder(session: Session) -> SessionChangeRecorder:
    return SessionChangeRecorder(session)


@pytest.mark.parametrize(("word_id", "button"), [
    (GLARE, Press.KNOWN), (GLARE, Press.LEARN), (GLARE, Press.SKIP), (HOVER, Press.KNOWN),
    (BROOD, Press.LEARN), (OH, Press.SKIP), (SPARK, Press.KNOWN), (DWELL, Press.LEARN),
])
def test_a_press_is_projected_exactly(world: World, word_id: int, button: Press) -> None:
    world.rebuild()
    world.decide(phrase_id_of(word_id), button)
    world.check()


def test_a_known_press_moves_only_the_cards_it_changes(world: World) -> None:
    world.rebuild()
    world.decide(phrase_id_of(GLARE), Press.KNOWN)
    after = world.check()
    moved = {c.row.phrase_id for c in after.cards if c.revision == after.revision}
    assert moved == {phrase_id_of(GLARE)}


def test_a_mark_reaches_every_phrase_holding_its_lemma(world: World) -> None:
    world.rebuild()
    world.write(lambda s: SqlaWordMarkRepository(s, _recorder(s)).mark_known("ominous", None))
    after = world.check()
    for phrase_id in (phrase_id_of(GLARE), phrase_id_of(DWELL), phrase_id_of(HOVER)):
        assert _card(after, phrase_id)[2] < world.was(phrase_id)[2]
    assert _card(after, BROOD_SECOND_PHRASE) != world.was(BROOD_SECOND_PHRASE)
    moved = {c.row.phrase_id for c in after.cards if c.revision == after.revision}
    assert phrase_id_of(OH) not in moved


def test_a_known_mark_taken_off_makes_its_words_new_again(world: World) -> None:
    world.rebuild()
    world.write(lambda s: SqlaWordMarkRepository(s, _recorder(s)).remove_known("lighthouse"))
    after = world.check()
    assert _card(after, phrase_id_of(GLEAM))[2] > world.was(phrase_id_of(GLEAM))[2]


def test_a_released_binding_reopens_the_lemma_in_every_source(world: World) -> None:
    """Learn pressed again on a word in Anki takes it back to new and releases its card."""
    world.rebuild()
    assert _card(world.stored(), phrase_id_of(SPARK_TWO))[1]
    world.decide(phrase_id_of(SPARK), Press.LEARN)
    after = world.check()
    assert not _card(after, phrase_id_of(SPARK_TWO))[1]


def test_a_phrase_no_longer_shown_stays_as_a_tombstone_and_comes_back(world: World) -> None:
    world.rebuild()
    glare = phrase_id_of(GLARE)
    world.write(lambda s: SqlaOccurrenceRepository(s, _recorder(s)).set_shown([glare], None))
    after = world.check()
    assert _card(after, glare)[0]
    assert not any(w.phrase_id == glare for w in after.phrase_words)
    world.write(
        lambda s: SqlaOccurrenceRepository(s, _recorder(s)).set_shown([glare], ShownBy.USER),
    )
    after = world.check()
    assert not _card(after, glare)[0]
    assert any(w.phrase_id == glare for w in after.phrase_words)


def test_a_new_word_gets_its_row(world: World) -> None:
    world.rebuild()
    quill = StoredCandidate(
        id=None, source_id=ONE, lemma="quill", pos="NOUN", cefr_level="C1",
        zipf_frequency=2.9, occurrences=1, status=WordStatus.NEW,
    )
    world.write(lambda s: SqlaCandidateRepository(s, _recorder(s)).add_word(quill))
    after = world.check()
    assert "quill" in {w.lemma for w in after.words}


def test_a_word_fact_written_without_a_state_change_moves_no_card(world: World) -> None:
    world.rebuild()
    world.write(
        lambda s: SqlaCandidateRepository(s, _recorder(s)).set_studied_at(GLARE, NOW),
    )
    after = world.check()
    assert world.before is not None
    assert after.revision == world.before.revision


def test_a_deleted_source_leaves_tombstones_and_releases_its_learn_elsewhere(
    world: World,
) -> None:
    with world.factory() as session:
        insert_card_word(session, GLARE_TWO, TWO, "glare", phrase("I glare back", "glare"))
        session.commit()
    world.rebuild()
    world.decide(phrase_id_of(GLARE), Press.LEARN)
    world.check()
    assert _card(world.stored(), phrase_id_of(GLARE_TWO))[1]

    world.write(lambda s: SqlaSourceRepository(s, _recorder(s)).delete(ONE))
    after = world.check()
    ones = {c.row.phrase_id for c in after.cards if c.row.source_id == ONE}
    assert ones
    assert all(_card(after, phrase_id)[0] for phrase_id in ones)
    assert not any(w.source_id == ONE for w in after.words)
    assert not any(w.phrase_id in ones for w in after.phrase_words)
    assert not _card(after, phrase_id_of(GLARE_TWO))[1]


def test_new_card_content_moves_the_card_without_changing_it(world: World) -> None:
    world.rebuild()
    glare = phrase_id_of(GLARE)
    tts = CandidateTTS(candidate_id=GLARE, audio_path="/media/1/tts.mp3", generated_at=None)
    world.write(
        lambda s: SqlaCandidateTTSRepository(s, _recorder(s)).upsert_for_phrase(glare, tts),
    )
    after = world.check(touched=frozenset({glare}))
    assert {c.row.phrase_id for c in after.cards if c.revision == after.revision} == {glare}


def test_new_word_content_moves_every_card_of_the_word(world: World) -> None:
    world.rebuild()
    image = CandidateMeaningImage(candidate_id=BROOD, image_path="/media/2/brood.jpg")
    world.write(lambda s: SqlaCandidateMeaningImageRepository(s, _recorder(s)).upsert(image))
    broods = frozenset({phrase_id_of(BROOD), BROOD_SECOND_PHRASE})
    after = world.check(touched=broods)
    assert {c.row.phrase_id for c in after.cards if c.revision == after.revision} == broods


def test_a_new_level_rebuilds_the_whole_projection(world: World) -> None:
    world.rebuild()
    world.write(lambda s: SqlaSettingsRepository(s, _recorder(s)).set("cefr_level", "A2"))
    after = world.stored()
    assert differences(after, live_states(world.container, world.factory)) == []
    assert {c.revision for c in after.cards} == {after.revision}
    assert world.before is not None
    assert after.revision == world.before.revision + 1


def test_two_presses_in_one_write_are_projected_once(
    world: World, monkeypatch: pytest.MonkeyPatch,
) -> None:
    world.rebuild()
    applied: list[tuple[CardChange, ...]] = []
    original = CardStateProjector.apply

    def counted(self: CardStateProjector, changes: tuple[CardChange, ...]) -> None:
        applied.append(changes)
        original(self, changes)

    monkeypatch.setattr(CardStateProjector, "apply", counted)

    def press_both(session: Session) -> None:
        use_case = world.container.decide_phrase_use_case(session)
        use_case.press(phrase_id_of(GLARE), Press.KNOWN)
        use_case.press(phrase_id_of(HOVER), Press.LEARN)

    world.write(press_both)
    world.check()
    [changes] = applied
    assert {DecisionChanged("glare"), DecisionChanged("hover")} <= set(changes)


def test_an_export_projects_its_whole_batch_in_one_apply(world: World) -> None:
    """The batch of an export is one write: its bindings reach the projection at its one
    commit."""
    world.rebuild()
    glare = phrase_id_of(GLARE)

    def ready(session: Session) -> None:
        SqlaCandidateMeaningRepository(session, _recorder(session)).upsert_for_phrase(
            glare, CandidateMeaning(
                candidate_id=GLARE, meaning="to look angrily", translation=None,
                synonyms=None, examples=None, ipa=None, generated_at=None,
            ),
        )
        SqlaCandidateTTSRepository(session, _recorder(session)).upsert_for_phrase(
            glare, CandidateTTS(candidate_id=GLARE, audio_path="/m/tts.mp3", generated_at=None),
        )

    world.write(ready)
    world.decide(glare, Press.LEARN)
    world.check()
    world.before = world.stored()

    applied: list[tuple[CardChange, ...]] = []
    with world.factory() as session:
        projector = world.container.card_state_projector(session)

        def counted(changes: tuple[CardChange, ...]) -> None:
            applied.append(changes)
            projector.apply(changes)

        _export(session, SqlaUnitOfWork(session, Decisions(session).scope, counted))
    after = world.check()
    [changes] = applied
    assert BindingChanged("glare") in changes
    assert _card(after, glare)[1]
    assert next(c for c in after.cards if c.row.phrase_id == glare).row.changes_at is not None


def _export(session: Session, unit_of_work: SqlaUnitOfWork) -> None:
    decisions = Decisions(session)
    connector = MagicMock()
    connector.is_available.return_value = True
    connector.get_model_field_names.return_value = _EveryField()
    connector.add_notes.return_value = [NOTE]
    connector.find_notes_by_target.return_value = []
    settings = MagicMock()
    settings.get.return_value = None
    renderer = MagicMock()
    renderer.render_recognition.return_value = NoteTemplates("F", "B", "")
    renderer.render_cloze.return_value = NoteTemplates("CF", "CB", "")
    queue = ExportQueue(
        SqlaCandidateRepository(session, _recorder(session)),
        SqlaOccurrenceRepository(session, _recorder(session)),
        decisions.word_states, decisions.vocabulary,
    )
    SyncToAnkiUseCase(
        export_queue=queue,
        anki_connector=connector,
        settings_repo=settings,
        template_renderer=renderer,
        cloze_builder=ClozeBuilder(),
        scope_resolver=sources_scope_resolver(ONE),
        vocabulary=decisions.vocabulary,
        effects=decisions.effects(),
        word_states=decisions.word_states,
        unit_of_work=unit_of_work,
    ).execute(SourceScope.source(ONE), ExportGroup.READY)


class _EveryField(list[str]):
    def __contains__(self, name: object) -> bool:
        return True


def test_a_phrase_with_two_spellings_of_a_lemma_counts_as_the_review_counts(
    world: World,
) -> None:
    """Stored lemmas are lower-case for lookups; the new words are counted by the lemma as
    the phrase holds it, as the review counts them."""
    shown = phrase("Ominous cases hide ominous clues", "cases", new=["ominous"])
    first = shown.words[0]
    shown = replace(shown, words=(replace(first, lemma="Ominous"), *shown.words[1:]))
    with world.factory() as session:
        insert_card_word(session, CASES, ONE, "case", shown)
        session.commit()
    world.rebuild()
    stored = world.stored()
    assert differences(stored, live_states(world.container, world.factory)) == []
    assert _card(stored, phrase_id_of(CASES))[2] == 2  # noqa: PLR2004 — both spellings
    world.write(lambda s: SqlaWordMarkRepository(s, _recorder(s)).mark_known("ominous", None))
    after = world.check()
    assert _card(after, phrase_id_of(CASES))[2] == 0


def test_two_running_timers_of_a_lemma_change_its_cards_at_the_earlier(world: World) -> None:
    with world.factory() as session:
        session.execute(
            text("UPDATE phrases SET choice = 'learn' WHERE id = :p"),
            {"p": phrase_id_of(SPARK_TWO)},
        )
        bind(session, SPARK_TWO, phrase_id_of(SPARK_TWO), note_id=NOTE,
             since=naive(SPARK_TWO_EXPORTED))
        session.commit()
    world.rebuild()
    stored = world.stored()
    for word_id in (SPARK, SPARK_TWO):
        card = next(c for c in stored.cards if c.row.phrase_id == phrase_id_of(word_id))
        assert card.row.changes_at == known_on(SPARK_TWO_EXPORTED)
    assert known_on(SPARK_TWO_EXPORTED) < known_on(SPARK_EXPORTED)
    assert differences(stored, live_states(world.container, world.factory)) == []

    world.decide(phrase_id_of(SPARK_TWO), Press.LEARN)
    after = world.check()
    card = next(c for c in after.cards if c.row.phrase_id == phrase_id_of(SPARK))
    assert card.row.changes_at == known_on(SPARK_EXPORTED)
    with world.factory() as session:
        stored = session.execute(
            text("SELECT changes_at FROM card_states WHERE phrase_id = :p"),
            {"p": phrase_id_of(SPARK)},
        ).scalar_one()
    assert stored == naive_microseconds(known_on(SPARK_EXPORTED))


def naive_microseconds(moment: datetime) -> str:
    """A moment as SQLAlchemy stores it in SQLite: UTC text with microseconds."""
    return moment.replace(tzinfo=None).isoformat(sep=" ", timespec="microseconds")


def test_a_projector_that_records_a_change_fails_the_write(
    factory: sessionmaker[Session],
) -> None:
    store = MagicMock()
    with factory() as session:
        recorder = SessionChangeRecorder(session)
        store.next_revision.side_effect = lambda: recorder.record(MarkChanged("leak")) or 1
        projector = CardStateProjector(
            source_repo=MagicMock(), card_query=MagicMock(), word_states=MagicMock(),
            knowledge=MagicMock(), vocabulary=MagicMock(), learning=MagicMock(), store=store,
            recorder=recorder,
        )
        with pytest.raises(ProjectorRecordedChangesError):
            projector.apply((CardContentChanged(1),))
        assert recorder.drain() == ()


def test_a_write_whose_projection_fails_is_rolled_back(world: World) -> None:
    world.rebuild()
    with world.factory() as session:
        def failing(changes: tuple[CardChange, ...]) -> None:
            del changes
            raise ProjectorRecordedChangesError((MarkChanged("leak"),))

        unit_of_work = SqlaUnitOfWork(session, Decisions(session).scope, failing)
        with pytest.raises(ProjectorRecordedChangesError), unit_of_work.write():
            SqlaWordMarkRepository(session, _recorder(session)).mark_known("ominous", None)
    with world.factory() as session:
        assert session.execute(
            text("SELECT count(*) FROM word_marks WHERE lemma = 'ominous' AND mark = 'known'"),
        ).scalar_one() == 0


# --- several kinds of change in one write ---------------------------------------------------


def _hide(session: Session, phrase_id: int, by: ShownBy | None = None) -> None:
    SqlaOccurrenceRepository(session, _recorder(session)).set_shown([phrase_id], by)


def _mark_known(session: Session, lemma: str = "ominous") -> None:
    SqlaWordMarkRepository(session, _recorder(session)).mark_known(lemma, None)


def test_a_hidden_phrase_and_a_mark_in_one_write(world: World) -> None:
    world.rebuild()
    glare, dwell = phrase_id_of(GLARE), phrase_id_of(DWELL)
    world.write(lambda s: (_hide(s, glare), _hide(s, dwell), _mark_known(s)))
    world.check()


def test_a_phrase_hidden_then_marked_then_shown_with_the_mark_taken_off(world: World) -> None:
    world.rebuild()
    glare = phrase_id_of(GLARE)
    world.write(lambda s: _hide(s, glare))
    world.check()
    world.write(_mark_known)
    world.check()
    world.write(lambda s: (
        _hide(s, glare, ShownBy.USER),
        SqlaWordMarkRepository(s, _recorder(s)).remove_known("ominous"),
    ))
    world.check()


def test_presses_and_a_mark_in_one_write(world: World) -> None:
    world.rebuild()

    def presses_and_mark(session: Session) -> None:
        use_case = world.container.decide_phrase_use_case(session)
        use_case.press(phrase_id_of(HOVER), Press.KNOWN)
        _mark_known(session)
        use_case.press(phrase_id_of(GLARE), Press.LEARN)

    world.write(presses_and_mark)
    world.check()


def test_a_deleted_source_and_a_mark_in_one_write(world: World) -> None:
    world.rebuild()
    world.write(lambda s: (_mark_known(s), SqlaSourceRepository(s, _recorder(s)).delete(ONE)))
    world.check()


@pytest.mark.parametrize(
    "lemma", ["glare", "hover", "dwell", "spark", "brood", "oh", "lighthouse"],
)
def test_each_lemma_marked_known_then_taken_off_then_unknown(world: World, lemma: str) -> None:
    world.rebuild()
    world.write(lambda s: _mark_known(s, lemma))
    world.check()
    world.write(lambda s: SqlaWordMarkRepository(s, _recorder(s)).remove_known(lemma))
    world.check()
    world.write(lambda s: SqlaWordMarkRepository(s, _recorder(s)).mark_unknown(lemma))
    world.check()
