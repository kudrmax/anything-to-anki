"""The binding's card choice is a fact written once, before the card or its source goes
(spec §2): NULL while the card lives, the card's choice on the orphan the orphan rules read."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.application.use_cases.delete_source import DeleteSourceUseCase
from backend.domain.value_objects.card_change import BindingChanged
from backend.domain.value_objects.card_choice import CardChoice
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_anki_sync_repository import SqlaAnkiSyncRepository
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_source_operation_lock import (
    SqlaSourceOperationLock,
)
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork
from sqlalchemy import text

from tests.decision_support import Decisions
from tests.integration.conftest import insert_source
from tests.word_support import CREATED_AT, bind, insert_word, phrase_id_of

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

LEMMA = "glare"
HERE, THERE = 1, 2
WORD, OTHER_WORD = 1, 2
LEARN_NOTE, KNOWN_NOTE, OTHER_NOTE, RELEASED_NOTE = 901, 902, 903, 904


class Bench:
    def __init__(self, session: Session, media_root: Path) -> None:
        self.session = session
        self.recorder = SessionChangeRecorder(session)
        self.anki = SqlaAnkiSyncRepository(session, self.recorder)
        self._media_root = media_root
        insert_source(session, THERE)

    def in_anki(self, word_id: int, choice: str, note_id: int, *, source_id: int = HERE) -> int:
        insert_word(self.session, word_id, source_id=source_id, lemma=LEMMA)
        phrase_id = phrase_id_of(word_id)
        self.session.execute(
            text("UPDATE phrases SET choice = :c WHERE id = :p"), {"c": choice, "p": phrase_id},
        )
        bind(self.session, word_id, phrase_id, lemma=LEMMA, note_id=note_id)
        return phrase_id

    def delete_source(self, source_id: int) -> None:
        self.session.commit()
        decisions = Decisions(self.session)
        DeleteSourceUseCase(
            source_repo=SqlaSourceRepository(self.session, self.recorder),
            candidate_repo=SqlaCandidateRepository(self.session, self.recorder),
            anki_sync=self.anki,
            lock=SqlaSourceOperationLock(self.session),
            media_root=str(self._media_root),
            unit_of_work=SqlaUnitOfWork(self.session, decisions.scope),
        ).execute(source_id)

    def choice_of(self, note_id: int) -> str | None:
        value = self.session.execute(
            text("SELECT card_choice FROM anki_synced_cards WHERE anki_note_id = :n"),
            {"n": note_id},
        ).scalar_one()
        return None if value is None else str(value)


@pytest.fixture
def bench(db_session: Session, source_id: int, tmp_path: Path) -> Bench:
    del source_id
    return Bench(db_session, tmp_path)


def test_a_live_card_leaves_its_binding_without_a_choice(bench: Bench) -> None:
    bench.in_anki(WORD, "learn", LEARN_NOTE)

    assert bench.choice_of(LEARN_NOTE) is None


def test_a_deleted_sources_learn_card_leaves_an_orphan_with_its_choice(bench: Bench) -> None:
    """O0/O1 read the Learn choice of the orphan: it keeps the word Learning by its timer."""
    bench.in_anki(WORD, "learn", LEARN_NOTE)

    bench.delete_source(HERE)

    assert bench.choice_of(LEARN_NOTE) == "learn"
    assert [ref.card_choice for ref in bench.anki.orphans(LEMMA)] == [CardChoice.LEARN]


def test_a_deleted_sources_known_card_leaves_an_orphan_known(bench: Bench) -> None:
    """O2 reads the Known choice: Known removed releases the binding."""
    bench.in_anki(WORD, "known", KNOWN_NOTE)

    bench.delete_source(HERE)

    assert [ref.card_choice for ref in bench.anki.orphans(LEMMA)] == [CardChoice.KNOWN]


def test_a_card_with_no_decision_leaves_the_kind_it_was_exported_as(bench: Bench) -> None:
    phrase_id = bench.in_anki(WORD, "none", LEARN_NOTE)
    bench.session.execute(
        text("UPDATE anki_synced_cards SET note_kind = 'cloze' WHERE phrase_id = :p"),
        {"p": phrase_id},
    )

    bench.delete_source(HERE)

    assert bench.choice_of(LEARN_NOTE) == "cloze"


def test_only_the_deleted_sources_active_bindings_are_written(bench: Bench) -> None:
    phrase_id = bench.in_anki(WORD, "learn", LEARN_NOTE)
    bind(bench.session, WORD, phrase_id, lemma=LEMMA, note_id=RELEASED_NOTE,
         released_at=CREATED_AT)
    bench.in_anki(OTHER_WORD, "learn", OTHER_NOTE, source_id=THERE)

    bench.delete_source(HERE)

    assert bench.choice_of(LEARN_NOTE) == "learn"
    assert bench.choice_of(RELEASED_NOTE) is None
    assert bench.choice_of(OTHER_NOTE) is None


def test_orphaning_cards_writes_only_their_active_bindings_and_records_the_lemma(
    bench: Bench,
) -> None:
    first = bench.in_anki(WORD, "known", KNOWN_NOTE)
    bench.in_anki(OTHER_WORD, "learn", OTHER_NOTE, source_id=THERE)
    bench.session.flush()
    bench.recorder.drain()

    bench.anki.orphan([first])

    assert (bench.choice_of(KNOWN_NOTE), bench.choice_of(OTHER_NOTE)) == ("known", None)
    assert set(bench.recorder.drain()) == {BindingChanged(LEMMA)}


def test_an_orphan_that_lost_its_card_without_orphan_is_a_bug(bench: Bench) -> None:
    bench.in_anki(WORD, "learn", LEARN_NOTE)
    bench.session.execute(text("DELETE FROM sources WHERE id = :s"), {"s": HERE})

    with pytest.raises(AssertionError, match="without orphan"):
        bench.anki.orphans(LEMMA)
