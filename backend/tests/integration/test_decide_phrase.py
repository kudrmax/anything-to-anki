"""Presses on cards through the decision tables, in a real database: the choice, the word's
status, the Anki binding and the known words they leave."""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.occurrence import Occurrence
from backend.domain.entities.word_decision import WordDecision
from backend.domain.exceptions import (
    ActionRefusedError,
    PhraseNotFoundError,
    SourceOperationBusyError,
)
from backend.domain.value_objects.card_choice import CardChoice, Press, Refusal
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.domain.value_objects.learning_timer import LEARNING_KNOWN_AFTER
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.sqla_candidate_cloze_repository import (
    SqlaCandidateClozeRepository,
)
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from sqlalchemy import text

from tests.decision_support import NOW, Decisions
from tests.integration.conftest import insert_source
from tests.phrase_support import phrase
from tests.word_support import bind, insert_word, phrase_id_of

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

WORD = 1
FIRST = phrase_id_of(WORD)
LEMMA = "glare"
OTHER_SOURCE = 2
OTHER_WORD = 50
LEARN, KNOWN, SKIP = Press.LEARN, Press.KNOWN, Press.SKIP
FRESH = (NOW - LEARNING_KNOWN_AFTER + timedelta(days=1)).replace(tzinfo=None).isoformat(sep=" ")
DUE = (NOW - LEARNING_KNOWN_AFTER).replace(tzinfo=None).isoformat(sep=" ")


class Bench:
    """One word of source 1 with two shown phrases: FIRST and `second`."""

    def __init__(self, session: Session) -> None:
        self.session = session
        insert_word(session, WORD, lemma=LEMMA, pos="VERB", phrase_text="He glared at me.")
        self.occurrences = SqlaOccurrenceRepository(session)
        self.clozes = SqlaCandidateClozeRepository(session)
        self.second = self._add_phrase("She glared back.")
        self.decisions = Decisions(session)

    def _add_phrase(self, text_: str) -> int:
        added = self.occurrences.add(Occurrence(
            candidate_id=WORD, origin=OccurrenceOrigin.MANUAL,
            source_phrase=phrase(text_, "glared"), phrase_position=None, key=None,
            fragment_score=None, shown_by=ShownBy.USER,
        ))
        assert added.id is not None
        return added.id

    def press(self, phrase_id: int, button: Press) -> None:
        self.decisions.decide_phrase().press(phrase_id, button)

    def later(self, days: int = 0) -> None:
        """The next request, `days` later."""
        self.decisions = self.decisions.request(NOW + timedelta(days=days))

    def status(self, word_id: int = WORD) -> str:
        return str(self.session.execute(
            text("SELECT status FROM candidates WHERE id = :id"), {"id": word_id},
        ).scalar_one())

    def choice(self, phrase_id: int) -> CardChoice:
        return CardChoice(self.session.execute(
            text("SELECT choice FROM phrases WHERE id = :id"), {"id": phrase_id},
        ).scalar_one())

    def active(self, phrase_id: int) -> bool:
        return self.session.execute(
            text(
                "SELECT count(*) FROM anki_synced_cards"
                " WHERE phrase_id = :id AND released_at IS NULL"
            ),
            {"id": phrase_id},
        ).scalar_one() == 1

    def released(self, phrase_id: int) -> int:
        return int(self.session.execute(
            text(
                "SELECT count(*) FROM anki_synced_cards"
                " WHERE phrase_id = :id AND released_at IS NOT NULL"
            ),
            {"id": phrase_id},
        ).scalar_one())

    def known(self) -> set[tuple[str, str | None]]:
        return {
            (str(lemma), pos) for lemma, pos in self.session.execute(
                text("SELECT lemma, pos FROM known_words"),
            )
        }

    def list_known(self, *pos: str | None) -> None:
        for one in pos:
            self.session.execute(
                text(
                    "INSERT INTO known_words (lemma, pos, created_at)"
                    " VALUES (:l, :p, '2026-01-01')"
                ),
                {"l": LEMMA, "p": one},
            )

    def in_anki(self, phrase_id: int, choice: CardChoice, *, since: str = FRESH) -> None:
        """The card, decided `choice`, as an export left it."""
        self.session.execute(
            text("UPDATE phrases SET choice = :c WHERE id = :id"),
            {"c": choice.value, "id": phrase_id},
        )
        self.session.execute(
            text("UPDATE candidates SET status = :s WHERE id = :id"),
            {"s": "known" if choice is CardChoice.KNOWN else "learn", "id": WORD},
        )
        bind(self.session, WORD, phrase_id, lemma=LEMMA, since=since)

    def give_cloze(self, phrase_id: int) -> None:
        self.clozes.upsert_for_phrase(phrase_id, CandidateCloze(
            candidate_id=WORD, hidden_word_indices=(1,), hint_kind=ClozeHintKind.NONE,
            custom_hint=None, phrase="He glared at me.",
        ))

    def known_in_other_source(self, *, bound: bool = False) -> int:
        """The lemma decided Known in source 2; its card in Anki when `bound`."""
        insert_source(self.session, OTHER_SOURCE)
        insert_word(self.session, OTHER_WORD, source_id=OTHER_SOURCE, lemma=LEMMA,
                    status="known")
        if bound:
            bind(self.session, OTHER_WORD, phrase_id_of(OTHER_WORD), lemma=LEMMA)
        return phrase_id_of(OTHER_WORD)


@pytest.fixture
def bench(db_session: Session, source_id: int) -> Bench:
    del source_id
    return Bench(db_session)


# ── the press table on a card not in Anki ──────────────────────────────


def test_learn_decides_the_word_on_that_phrase(bench: Bench) -> None:
    bench.press(bench.second, LEARN)

    assert bench.status() == "learn"
    assert (bench.choice(bench.second), bench.choice(FIRST)) == (
        CardChoice.LEARN, CardChoice.NONE,
    )
    bench.decisions.decision_repo.record.assert_called_once_with(
        WordDecision(lemma=LEMMA, zipf_frequency=3.0, is_known=False),
    )


def test_p9_pressing_learn_again_makes_the_word_new(bench: Bench) -> None:
    bench.press(FIRST, LEARN)

    bench.press(FIRST, LEARN)

    assert (bench.status(), bench.choice(FIRST)) == ("pending", CardChoice.NONE)
    bench.decisions.decision_repo.forget.assert_called_once_with(LEMMA)


def test_p12_skip_on_the_learn_card_skips_it_and_the_word_is_new(bench: Bench) -> None:
    bench.press(FIRST, LEARN)

    bench.press(FIRST, SKIP)

    assert (bench.status(), bench.choice(FIRST)) == ("pending", CardChoice.SKIP)


def test_known_marks_the_word_known(bench: Bench) -> None:
    bench.press(FIRST, KNOWN)

    assert (bench.status(), bench.choice(FIRST)) == ("known", CardChoice.KNOWN)
    assert bench.known() == {(LEMMA, "VERB")}


def test_p14_learn_on_a_known_card_removes_known_of_every_pos(bench: Bench) -> None:
    bench.press(FIRST, KNOWN)
    bench.list_known("NOUN")

    bench.press(FIRST, LEARN)

    assert (bench.status(), bench.choice(FIRST)) == ("learn", CardChoice.LEARN)
    assert bench.known() == set()
    bench.decisions.decision_repo.record.assert_called_with(
        WordDecision(lemma=LEMMA, zipf_frequency=3.0, is_known=False),
    )


def test_the_sibling_card_of_a_decided_word_is_refused(bench: Bench) -> None:
    bench.press(FIRST, KNOWN)

    with pytest.raises(ActionRefusedError) as refused:
        bench.press(bench.second, LEARN)

    assert refused.value.refusal is Refusal.NOT_DECISION_CARD
    assert bench.choice(bench.second) is CardChoice.NONE


def test_learn_on_a_word_known_elsewhere_is_refused(bench: Bench) -> None:
    bench.list_known("VERB")

    with pytest.raises(ActionRefusedError) as refused:
        bench.press(FIRST, LEARN)

    assert refused.value.refusal is Refusal.DECIDED_ELSEWHERE
    assert bench.status() == "pending"


def test_learn_on_a_word_marked_unknown_but_learning_elsewhere_is_allowed(
    bench: Bench, db_session: Session,
) -> None:
    """Unknown > Known > learning: the user's "I don't know it" wins here too."""
    insert_source(db_session, OTHER_SOURCE)
    insert_word(db_session, OTHER_WORD, source_id=OTHER_SOURCE, lemma=LEMMA, status="learn")
    db_session.execute(text(
        "INSERT INTO unknown_words (lemma, created_at) VALUES ('glare', '2026-01-01')"
    ))

    bench.press(FIRST, LEARN)

    assert bench.status() == "learn"


def test_cloze_markup_survives_every_decision_change(bench: Bench) -> None:
    bench.press(FIRST, Press.CLOZE)
    bench.give_cloze(FIRST)

    for button in (LEARN, KNOWN, SKIP, SKIP):
        bench.press(FIRST, button)

    assert bench.clozes.get_by_phrase_id(FIRST) is not None


def test_an_unknown_phrase_is_not_found(bench: Bench) -> None:
    with pytest.raises(PhraseNotFoundError):
        bench.press(999, LEARN)


def test_a_phrasal_verb_decision_is_not_remembered(bench: Bench, db_session: Session) -> None:
    insert_word(db_session, 60, lemma="give up")

    bench.press(phrase_id_of(60), LEARN)

    bench.decisions.decision_repo.record.assert_not_called()


# ── a card in Anki ─────────────────────────────────────────────────────


def test_p16_known_on_a_card_in_anki_keeps_the_binding(bench: Bench) -> None:
    bench.in_anki(FIRST, CardChoice.LEARN)

    bench.press(FIRST, KNOWN)

    assert (bench.status(), bench.choice(FIRST)) == ("known", CardChoice.KNOWN)
    assert bench.active(FIRST)
    assert bench.known() == {(LEMMA, "VERB")}


def test_p17_unpressing_learn_in_anki_releases_and_the_word_is_new(bench: Bench) -> None:
    bench.in_anki(FIRST, CardChoice.LEARN)

    bench.press(FIRST, LEARN)

    assert (bench.status(), bench.choice(FIRST)) == ("pending", CardChoice.NONE)
    assert not bench.active(FIRST)
    assert bench.released(FIRST) == 1


def test_p18_cloze_on_a_learn_card_in_anki_releases_and_requeues(bench: Bench) -> None:
    bench.in_anki(FIRST, CardChoice.LEARN)

    bench.press(FIRST, Press.CLOZE)

    assert (bench.status(), bench.choice(FIRST)) == ("learn", CardChoice.CLOZE)
    assert not bench.active(FIRST)


def test_p20_undo_of_known_in_anki_releases_and_the_word_is_new(bench: Bench) -> None:
    bench.in_anki(FIRST, CardChoice.KNOWN)
    bench.list_known("VERB", "NOUN")

    bench.press(FIRST, KNOWN)

    assert (bench.status(), bench.choice(FIRST)) == ("pending", CardChoice.NONE)
    assert not bench.active(FIRST)
    assert bench.known() == set()


def test_p21_skip_on_a_known_card_in_anki_releases(bench: Bench) -> None:
    bench.in_anki(FIRST, CardChoice.KNOWN)
    bench.list_known("VERB")

    bench.press(FIRST, SKIP)

    assert (bench.status(), bench.choice(FIRST)) == ("pending", CardChoice.SKIP)
    assert not bench.active(FIRST)
    assert bench.known() == set()


def test_p23_undo_of_a_card_known_by_its_timer(bench: Bench) -> None:
    bench.in_anki(FIRST, CardChoice.LEARN, since=DUE)
    assert bench.decisions.decide_phrase().view(FIRST).shown.status is WordStatus.KNOWN

    bench.press(FIRST, KNOWN)

    assert (bench.status(), bench.choice(FIRST)) == ("pending", CardChoice.NONE)
    assert not bench.active(FIRST)


def test_p23_undo_of_a_card_known_by_the_list(bench: Bench) -> None:
    bench.in_anki(FIRST, CardChoice.LEARN)
    bench.list_known("VERB")

    bench.press(FIRST, KNOWN)

    assert (bench.status(), bench.choice(FIRST)) == ("pending", CardChoice.NONE)
    assert not bench.active(FIRST)
    assert bench.known() == set()


def test_the_timer_turns_a_card_in_anki_known_at_day_30(bench: Bench) -> None:
    bench.in_anki(FIRST, CardChoice.LEARN, since=FRESH)
    assert bench.decisions.decide_phrase().view(FIRST).shown.status is WordStatus.LEARNING

    bench.later(days=1)

    assert bench.decisions.decide_phrase().view(FIRST).shown.status is WordStatus.KNOWN
    assert bench.status() == "learning", "the timer writes nothing"


# ── Q15: a Learn not exported, then the lemma put in Known ─────────────


def test_a_learn_reads_known_once_its_lemma_is_listed(bench: Bench) -> None:
    bench.press(FIRST, LEARN)
    bench.list_known("VERB")
    bench.later()

    view = bench.decisions.decide_phrase().view(FIRST)

    assert view.shown.status is WordStatus.KNOWN
    assert {b.button for b in view.buttons if b.pressed} == {KNOWN}

    bench.press(FIRST, KNOWN)

    assert (bench.status(), bench.choice(FIRST)) == ("pending", CardChoice.NONE)
    assert bench.known() == set()


# ── the Known removal reaches every source (§2.7) ──────────────────────


def test_undo_of_known_here_makes_known_cards_in_other_sources_new(bench: Bench) -> None:
    """A Known in Anki in source 2 goes new and is released."""
    bench.press(FIRST, KNOWN)
    other = bench.known_in_other_source(bound=True)

    bench.press(FIRST, KNOWN)

    assert (bench.status(OTHER_WORD), bench.choice(other)) == ("pending", CardChoice.NONE)
    assert not bench.active(other)
    assert bench.known() == set()


def test_a_learning_card_elsewhere_that_does_not_read_known_stays(
    bench: Bench, db_session: Session,
) -> None:
    """The card here reads Known by its own timer; the other one's timer runs."""
    bench.in_anki(FIRST, CardChoice.LEARN, since=DUE)
    insert_source(db_session, OTHER_SOURCE)
    insert_word(db_session, OTHER_WORD, source_id=OTHER_SOURCE, lemma=LEMMA, status="learn")
    bind(db_session, OTHER_WORD, phrase_id_of(OTHER_WORD), lemma=LEMMA, since=FRESH)

    bench.press(FIRST, KNOWN)

    assert not bench.active(FIRST)

    assert bench.status(OTHER_WORD) == "learning"
    assert bench.active(phrase_id_of(OTHER_WORD))


def test_a_due_orphaned_binding_of_the_lemma_is_released(
    bench: Bench, db_session: Session,
) -> None:
    bench.press(FIRST, KNOWN)
    db_session.execute(text(
        "INSERT INTO anki_synced_cards (candidate_id, phrase_id, anki_note_id, lemma, pos,"
        " note_kind, learning_since) VALUES (NULL, NULL, 77, 'glare', 'VERB', 'learn', :due)"
    ), {"due": DUE})

    bench.press(FIRST, KNOWN)

    released = db_session.execute(text(
        "SELECT released_at IS NOT NULL FROM anki_synced_cards WHERE anki_note_id = 77"
    )).scalar_one()
    assert released


def test_the_removal_waits_for_a_busy_source(bench: Bench) -> None:
    bench.press(FIRST, KNOWN)
    bench.known_in_other_source()
    bench.decisions.lock.held.side_effect = lambda source_id: (
        SourceOperationKind.REBUILD if source_id == OTHER_SOURCE else None
    )

    with pytest.raises(SourceOperationBusyError):
        bench.press(FIRST, KNOWN)
