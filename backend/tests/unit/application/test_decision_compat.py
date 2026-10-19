"""The old card DTO values, read from the card view (until plan step 11).

Each state has the DTO the old code gave it; where the status model changed a value on
purpose, the row says which decision changed it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pytest
from backend.application.dto.decision_compat import DecisionAction, press_of
from backend.application.dto.source_dtos import card_to_dto
from backend.domain.entities.occurrence import Occurrence
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.services.card_view import card_view
from backend.domain.value_objects.card_choice import (
    Binding,
    CardChoice,
    CardState,
    NoteKind,
    Press,
    WordState,
)
from backend.domain.value_objects.elsewhere import ElsewhereStatus
from backend.domain.value_objects.learning_timer import LEARNING_KNOWN_AFTER
from backend.domain.value_objects.lemma_knowledge import LemmaKnowledge
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.domain.value_objects.review_card import CardContext, ReviewCard
from backend.domain.value_objects.word_status import WordStatus

from tests.decision_support import NOW
from tests.phrase_support import phrase

pytestmark = pytest.mark.unit

CARD = 1
SIBLING = 2
FRESH = NOW - timedelta(days=1)
DUE = NOW - LEARNING_KNOWN_AFTER
N, L, C, K, S = (
    CardChoice.NONE, CardChoice.LEARN, CardChoice.CLOZE, CardChoice.KNOWN, CardChoice.SKIP,
)
P, U = "pending", "unskip"


@dataclass(frozen=True)
class State:
    card: CardState
    sibling: CardState | None = None
    known_marked: bool = False
    elsewhere: ElsewhereStatus | None = None

    def word(self) -> WordState:
        cards = (self.card, *(() if self.sibling is None else (self.sibling,)))
        return WordState(1, "glare", "VERB", 1, cards)

    def knowledge(self) -> LemmaKnowledge:
        since = tuple(c.binding.learning_since for c in self.word().cards if c.binding)
        return LemmaKnowledge.at(
            NOW, known_marked=self.known_marked, unknown=False, learn_anywhere=False,
            active_since=since,
        )

    def review_card(self) -> ReviewCard:
        word = self.word()
        status = WordStatus(card_view(word, CARD, self.knowledge(), None, NOW).shown.status)
        stored = StoredCandidate(
            id=1, source_id=1, lemma="glare", pos="VERB", cefr_level="B2", zipf_frequency=3.0,
            occurrences=1, status=status,
        )
        occurrence = Occurrence(
            id=CARD, candidate_id=1, origin=OccurrenceOrigin.AUTO,
            source_phrase=phrase("He glared at me.", "glared"), phrase_position=None,
            key=None, fragment_score=None, shown_by=ShownBy.SELECTION,
            choice=self.card.choice, binding=self.card.binding,
        )
        return ReviewCard(
            word=stored, occurrence=occurrence, elsewhere=self.elsewhere,
            context=CardContext(word=word, knowledge=self.knowledge(), now=NOW),
        )


@dataclass(frozen=True)
class OldDTO:
    status: str
    word_status: str
    buttons: dict[str, tuple[str | None, bool]]   # button → (action, pressed)
    decided_here: bool = False
    note: str | None = None
    elsewhere: str | None = None
    can_cloze: bool = True
    is_done: bool = True


def _buttons(
    learn: tuple[str | None, bool], cloze: tuple[str | None, bool],
    known: tuple[str | None, bool], skip: tuple[str | None, bool],
) -> dict[str, tuple[str | None, bool]]:
    return {"learn": learn, "cloze": cloze, "known": known, "skip": skip}


OPEN = _buttons(("learn", False), ("cloze", False), ("known", False), ("skip", False))
SNAPSHOTS: dict[str, tuple[State, OldDTO]] = {
    "open": (State(CardState(CARD, N)), OldDTO(P, P, OPEN, is_done=False)),
    "open_skipped": (
        State(CardState(CARD, S)),
        OldDTO("skip", P, {**OPEN, "skip": (U, True)}),
    ),
    # G6 (P6): Known is refused too on a word decided in another source; it was offered.
    "open_known_elsewhere": (
        State(CardState(CARD, N), elsewhere=ElsewhereStatus.KNOWN),
        OldDTO(P, P, _buttons((None, False), (None, False), (None, False), ("skip", False)),
               elsewhere="known", note="known_elsewhere"),
    ),
    "learn": (
        State(CardState(CARD, L)),
        OldDTO("learn", "learn", {**OPEN, "learn": (P, True)}, decided_here=True),
    ),
    # P9 on a cloze card: Learn makes it a plain card; Cloze opens the markup editor.
    "cloze": (
        State(CardState(CARD, C)),
        OldDTO("learn", "learn", {**OPEN, "cloze": ("cloze", True)}, decided_here=True),
    ),
    "known": (
        State(CardState(CARD, K), known_marked=True),
        OldDTO("known", "known", {**OPEN, "known": (P, True)}, decided_here=True),
    ),
    "other_card_of_a_learn_word": (
        State(CardState(CARD, N), CardState(SIBLING, L)),
        OldDTO("learn", "learn",
               _buttons((None, True), (None, False), (None, False), (None, False)),
               note="learned_on_other_card"),
    ),
    # Skip shows pressed beside the word's Known on a skipped sibling (task 4); it did not.
    "skipped_card_of_a_known_word": (
        State(CardState(CARD, S), CardState(SIBLING, K), known_marked=True),
        OldDTO("known", "known",
               _buttons((None, False), (None, False), (None, True), (U, True)),
               note="known_on_other_card"),
    ),
    # Q11: every button works on a card in Anki; Cloze makes a cloze note on the next export.
    "learn_in_anki": (
        State(CardState(CARD, L, Binding(NoteKind.LEARN, FRESH))),
        OldDTO("learn", "learn",
               _buttons((P, True), ("cloze", False), ("known", False), ("skip", False)),
               decided_here=True, note="in_anki"),
    ),
    # Cloze is off on a cloze in Anki: its markup can't change there ("Already in Anki").
    "cloze_in_anki": (
        State(CardState(CARD, C, Binding(NoteKind.CLOZE, FRESH))),
        OldDTO("learn", "learn",
               _buttons(("learn", False), (None, True), ("known", False), ("skip", False)),
               decided_here=True, can_cloze=False, note="in_anki"),
    ),
    "known_by_its_timer": (
        State(CardState(CARD, L, Binding(NoteKind.LEARN, DUE))),
        OldDTO("known", "known",
               _buttons(("learn", False), ("cloze", False), (P, True), ("skip", False)),
               decided_here=True, note="known_by_timer"),
    ),
    # Q15: a Learn not exported reads Known once its lemma is put in Known.
    "learn_then_listed": (
        State(CardState(CARD, L), known_marked=True),
        OldDTO("known", "known",
               _buttons(("learn", False), ("cloze", False), (P, True), ("skip", False)),
               decided_here=True, note="known_by_list"),
    ),
}


@pytest.mark.parametrize("name", list(SNAPSHOTS))
def test_the_dto_has_the_old_values(name: str) -> None:
    state, expected = SNAPSHOTS[name]

    dto = card_to_dto(state.review_card())

    assert (dto.status, dto.word_status) == (expected.status, expected.word_status)
    assert {b.button.value: (b.action.value if b.action else None, b.pressed)
            for b in dto.state.buttons} == expected.buttons
    assert (dto.state.decided_here, dto.state.note, dto.state.elsewhere) == (
        expected.decided_here, expected.note, expected.elsewhere,
    )
    assert (dto.can_cloze, dto.is_done) == (expected.can_cloze, expected.is_done)


@pytest.mark.parametrize(
    ("name", "action", "expected"),
    [
        ("learn", DecisionAction.PENDING, Press.LEARN),
        ("known_by_its_timer", DecisionAction.PENDING, Press.KNOWN),
        ("skipped_card_of_a_known_word", DecisionAction.PENDING, Press.SKIP),
        ("skipped_card_of_a_known_word", DecisionAction.UNSKIP, Press.SKIP),
        ("open_skipped", DecisionAction.UNSKIP, Press.SKIP),
        ("learn", DecisionAction.UNSKIP, None),
        ("open", DecisionAction.PENDING, None),
        ("open", DecisionAction.KNOWN, Press.KNOWN),
    ],
)
def test_an_old_action_is_the_press_it_means(
    name: str, action: DecisionAction, expected: Press | None,
) -> None:
    state, _ = SNAPSHOTS[name]
    view = card_view(state.word(), CARD, state.knowledge(), state.elsewhere, NOW)

    assert press_of(action, view) is expected
