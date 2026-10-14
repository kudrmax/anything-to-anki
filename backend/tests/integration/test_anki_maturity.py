"""Learn → learning → Known when the Anki note matures, in a real database; Anki is a fake."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.check_anki_progress import CheckAnkiProgressUseCase
from backend.application.use_cases.decide_phrase import DecidePhraseUseCase
from backend.application.use_cases.get_learning_words import GetLearningWordsUseCase
from backend.application.utils.decided_elsewhere import DecidedElsewhere
from backend.application.utils.known_from_anki import RefreshKnownFromAnki
from backend.application.utils.user_vocabulary import UserVocabulary
from backend.domain.exceptions import AnkiNotAvailableError
from backend.domain.ports.anki_connector import AnkiConnector
from backend.domain.services.card_decision import DecisionAction
from backend.domain.value_objects.note_maturity import NoteCards
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.models import AnkiNoteModel
from backend.infrastructure.persistence.sqla_anki_note_repository import SqlaAnkiNoteRepository
from backend.infrastructure.persistence.sqla_anki_sync_repository import SqlaAnkiSyncRepository
from backend.infrastructure.persistence.sqla_candidate_cloze_repository import (
    SqlaCandidateClozeRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_known_word_removal_repository import (
    SqlaKnownWordRemovalRepository,
)
from backend.infrastructure.persistence.sqla_known_word_repository import (
    SqlaKnownWordRepository,
)
from backend.infrastructure.persistence.sqla_learning_query import SqlaLearningQuery
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from backend.infrastructure.persistence.sqla_unknown_word_repository import (
    SqlaUnknownWordRepository,
)
from sqlalchemy import text

from tests.lock_support import free_lock
from tests.word_support import insert_word

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

NOTE = 900
MATURE = NoteCards(intervals=(30,), suspended=0)
YOUNG = NoteCards(intervals=(3,), suspended=0)


class Bench:
    """The user's words over a real database and an Anki that answers what it is told."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.notes = SqlaAnkiNoteRepository(session)
        self.known = SqlaKnownWordRepository(session)
        self.unknown = SqlaUnknownWordRepository(session)
        self.learning = SqlaLearningQuery(session)
        self.vocabulary = UserVocabulary(
            known_word_repo=self.known,
            unknown_word_repo=self.unknown,
            learning_query=self.learning,
            removal_repo=SqlaKnownWordRemovalRepository(session),
        )
        self.anki = MagicMock(spec=AnkiConnector)
        self.anki.is_available.return_value = True
        self.anki.note_cards.return_value = {}
        self.review_status = MagicMock()

    def refresh(self) -> RefreshKnownFromAnki:
        return RefreshKnownFromAnki(
            anki_connector=self.anki,
            anki_note_repo=self.notes,
            vocabulary=self.vocabulary,
            review_status=self.review_status,
        )

    def check(self) -> int:
        return CheckAnkiProgressUseCase(self.anki, self.refresh()).execute().matured

    def decide(self, phrase_id: int, action: DecisionAction) -> None:
        """A decision on a card, as the review screen makes it."""
        DecidePhraseUseCase(
            occurrence_repo=SqlaOccurrenceRepository(self.session),
            candidate_repo=SqlaCandidateRepository(self.session),
            vocabulary=self.vocabulary,
            decision_repo=MagicMock(),
            review_status=self.review_status,
            cloze_repo=SqlaCandidateClozeRepository(self.session),
            decided_elsewhere=DecidedElsewhere(self.vocabulary),
            lock=free_lock(),
        ).execute(phrase_id, action)

    def export(self, word_id: int, lemma: str, note_id: int) -> None:
        """What a successful export of the word's decision phrase writes."""
        SqlaAnkiSyncRepository(self.session).mark_synced(word_id, note_id, word_id)
        self.notes.add(note_id, lemma, "NOUN")

    def remove_in_settings(self, lemma: str) -> None:
        known = self.known.add(lemma, None)
        assert known.id is not None
        self.vocabulary.remove_known(known.id)

    def exported_learn_word(self, word_id: int, lemma: str, note_id: int) -> None:
        insert_word(self.session, word_id, lemma=lemma, status=WordStatus.LEARN.value)
        SqlaAnkiSyncRepository(self.session).mark_synced(word_id, note_id, word_id)
        self.notes.add(note_id, lemma, "NOUN")

    def is_learning(self, lemma: str) -> bool:
        return self.vocabulary.snapshot().is_learning(lemma)

    def is_known(self, lemma: str) -> bool:
        return self.vocabulary.is_known(lemma)

    def note(self, note_id: int) -> AnkiNoteModel:
        self.session.expire_all()
        found = self.session.get(AnkiNoteModel, note_id)
        assert found is not None
        return found


@pytest.fixture
def bench(db_session: Session, source_id: int) -> Bench:
    del source_id
    return Bench(db_session)


# ── learning ──────────────────────────────────────────────────────────


def test_an_exported_learn_word_is_learning_not_known(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)

    assert bench.is_learning("glare")
    assert not bench.is_known("glare")


def test_a_learn_word_waiting_for_export_is_learning(bench: Bench) -> None:
    insert_word(bench.session, 1, lemma="linger", status=WordStatus.LEARN.value)

    assert bench.is_learning("linger")


def test_old_exported_words_stay_known(bench: Bench) -> None:
    """Migration 0049 records old exports as mature: Known stays stronger than learning."""
    bench.exported_learn_word(1, "glare", NOTE)
    bench.notes.mark_matured([NOTE], datetime(2026, 10, 1, tzinfo=UTC))
    bench.known.add("glare", "NOUN")

    assert bench.is_known("glare")
    assert not bench.is_learning("glare")


def test_known_is_stronger_than_a_note_still_learning(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    bench.known.add("glare", None)

    assert bench.is_known("glare")
    assert not bench.is_learning("glare")


def test_deleting_the_source_keeps_learning_and_maturity(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    SqlaSourceRepository(bench.session).delete(1)
    bench.session.flush()

    assert bench.is_learning("glare")

    bench.anki.note_cards.return_value = {NOTE: MATURE}
    assert bench.check() == 1
    assert bench.is_known("glare")


def test_the_learning_list_tells_words_in_anki_from_words_waiting(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    insert_word(bench.session, 2, lemma="linger", status=WordStatus.LEARN.value)
    insert_word(bench.session, 3, lemma="wander", status=WordStatus.LEARN.value)
    bench.known.add("wander", None)

    learning = GetLearningWordsUseCase(bench.vocabulary, bench.learning).execute()

    assert learning.in_anki == ["glare"]
    assert learning.awaiting_export == ["linger"]


# ── maturity ──────────────────────────────────────────────────────────


def test_a_mature_note_makes_its_word_known(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    bench.anki.note_cards.return_value = {NOTE: MATURE}

    assert bench.check() == 1

    assert bench.is_known("glare")
    assert not bench.is_learning("glare")
    assert bench.note(NOTE).matured_at is not None
    bench.anki.note_cards.assert_called_once_with([NOTE])
    bench.review_status.refresh_showing.assert_called_once_with({"glare"})


def test_a_young_note_keeps_its_word_learning(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    bench.anki.note_cards.return_value = {NOTE: YOUNG}

    assert bench.check() == 0

    assert bench.is_learning("glare")
    assert bench.note(NOTE).matured_at is None
    bench.review_status.refresh_showing.assert_not_called()


@pytest.mark.parametrize("cards", [
    NoteCards(intervals=(), suspended=0),
    NoteCards(intervals=(), suspended=2),
])
def test_a_note_without_active_cards_is_not_mature(bench: Bench, cards: NoteCards) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    bench.anki.note_cards.return_value = {NOTE: cards}

    assert bench.check() == 0
    assert bench.is_learning("glare")


def test_a_deleted_note_takes_its_word_out_of_learning(bench: Bench) -> None:
    """The exported Learn word of a note deleted in Anki may become a candidate again."""
    bench.exported_learn_word(1, "glare", NOTE)
    bench.anki.note_cards.return_value = {}

    assert bench.check() == 0

    assert bench.note(NOTE).deleted_at is not None
    assert not bench.is_learning("glare")
    assert not bench.is_known("glare")
    bench.review_status.refresh_showing.assert_called_once_with({"glare"})


def test_a_mature_word_the_user_marked_unknown_stays_unknown(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    bench.vocabulary.mark_unknown("glare")
    bench.anki.note_cards.return_value = {NOTE: MATURE}

    assert bench.check() == 0

    assert bench.vocabulary.snapshot().is_unknown("glare")
    assert not bench.is_known("glare")


def test_a_word_removed_from_known_in_settings_is_not_put_back(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    bench.remove_in_settings("glare")
    bench.anki.note_cards.return_value = {NOTE: MATURE}

    assert bench.check() == 0

    assert not bench.is_known("glare")


def test_marking_a_removed_word_known_again_lets_maturity_through(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    bench.remove_in_settings("glare")
    bench.vocabulary.mark_known("glare", None)
    bench.vocabulary.forget_known("glare", None)
    bench.anki.note_cards.return_value = {NOTE: MATURE}

    assert bench.check() == 1

    assert bench.is_known("glare")


def test_leaving_known_on_the_card_does_not_block_its_own_maturity(bench: Bench) -> None:
    """Known → Learn → export → mature → Known: a card decision is no settings removal."""
    insert_word(bench.session, 1, lemma="glare")
    bench.decide(1, DecisionAction.KNOWN)
    bench.decide(1, DecisionAction.LEARN)
    assert not bench.is_known("glare")
    removals = bench.session.execute(text("SELECT count(*) FROM known_word_removals")).scalar()
    assert removals == 0

    bench.export(1, "glare", NOTE)
    bench.anki.note_cards.return_value = {NOTE: MATURE}

    assert bench.check() == 1
    assert bench.is_known("glare")


def test_a_learn_decision_after_a_settings_removal_lets_maturity_through(bench: Bench) -> None:
    bench.remove_in_settings("glare")
    insert_word(bench.session, 1, lemma="glare")
    bench.decide(1, DecisionAction.LEARN)
    bench.export(1, "glare", NOTE)
    bench.anki.note_cards.return_value = {NOTE: MATURE}

    assert bench.check() == 1
    assert bench.is_known("glare")


def test_a_word_already_known_is_not_counted_again(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    bench.known.add("glare", "VERB")
    bench.anki.note_cards.return_value = {NOTE: MATURE}

    assert bench.check() == 0

    assert bench.note(NOTE).matured_at is not None


def test_each_note_is_promoted_once(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    bench.anki.note_cards.return_value = {NOTE: MATURE}
    assert bench.check() == 1

    assert bench.check() == 0
    bench.anki.note_cards.assert_called_once()


def test_an_exported_learn_word_whose_note_was_deleted_is_not_learning(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    bench.notes.mark_deleted([NOTE], datetime(2026, 10, 1, tzinfo=UTC))

    assert not bench.is_learning("glare")


def test_checking_progress_with_anki_offline_is_an_error(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    bench.anki.is_available.return_value = False

    with pytest.raises(AnkiNotAvailableError):
        bench.check()
    bench.anki.note_cards.assert_not_called()
    assert bench.is_learning("glare")


def test_anki_failing_during_the_check_is_anki_not_available(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    bench.anki.note_cards.side_effect = AnkiNotAvailableError()

    with pytest.raises(AnkiNotAvailableError):
        bench.check()
    assert bench.note(NOTE).matured_at is None
    assert bench.note(NOTE).deleted_at is None


# ── Known on a card of a word the user marked unknown ─────────────────


@pytest.mark.parametrize("leave", [
    DecisionAction.PENDING, DecisionAction.LEARN, DecisionAction.SKIP,
])
def test_leaving_known_restores_a_word_the_user_marked_unknown(
    bench: Bench, leave: DecisionAction,
) -> None:
    bench.vocabulary.mark_unknown("glare")
    insert_word(bench.session, 1, lemma="glare")
    bench.decide(1, DecisionAction.KNOWN)
    assert bench.is_known("glare")
    assert not bench.vocabulary.snapshot().is_unknown("glare")

    bench.decide(1, leave)

    assert bench.vocabulary.snapshot().is_unknown("glare")
    assert not bench.is_known("glare")


def test_leaving_known_does_not_mark_unknown_a_word_that_was_not(bench: Bench) -> None:
    insert_word(bench.session, 1, lemma="glare")
    bench.decide(1, DecisionAction.KNOWN)

    bench.decide(1, DecisionAction.PENDING)

    assert not bench.vocabulary.snapshot().is_unknown("glare")
    assert not bench.is_known("glare")
