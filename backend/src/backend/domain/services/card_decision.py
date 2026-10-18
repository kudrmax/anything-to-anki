"""Decisions on a word through its phrases.

Learn, Cloze and Known decide the word; the phrase they are made on becomes the phrase of
the decision, the one that goes to Anki. Skip applies to one phrase only. The other cards
of a decided word show the decision, but only its decision card changes or undoes it.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from backend.domain.exceptions import (
    AlreadyInAnkiError,
    CardDecisionLockedError,
    DecidedElsewhereError,
    DomainError,
)
from backend.domain.value_objects.elsewhere import ElsewhereStatus
from backend.domain.value_objects.phrase_origin_kind import DecisionKind
from backend.domain.value_objects.word_status import WordStatus

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.entities.stored_candidate import StoredCandidate

__all__ = [
    "ButtonState",
    "CardState",
    "DecisionAction",
    "DecisionButton",
    "DecisionOutcome",
    "ElsewhereStatus",
    "card_state",
    "decide",
    "wants_generation",
]


class DecisionAction(StrEnum):
    """What the user does on a card. PENDING undoes what is on it."""

    LEARN = "learn"
    CLOZE = "cloze"
    KNOWN = "known"
    SKIP = "skip"
    UNSKIP = "unskip"
    PENDING = "pending"


class DecisionButton(StrEnum):
    LEARN = "learn"
    CLOZE = "cloze"
    KNOWN = "known"
    SKIP = "skip"


DECIDING = frozenset({DecisionAction.LEARN, DecisionAction.CLOZE, DecisionAction.KNOWN})
LEARNING = frozenset({DecisionAction.LEARN, DecisionAction.CLOZE})
UNDOING = frozenset({DecisionAction.PENDING, DecisionAction.SKIP})
KEEPING_CLOZE = frozenset({DecisionAction.CLOZE, DecisionAction.UNSKIP})
ACTION_OF_BUTTON = {
    DecisionButton.LEARN: DecisionAction.LEARN,
    DecisionButton.CLOZE: DecisionAction.CLOZE,
    DecisionButton.KNOWN: DecisionAction.KNOWN,
    DecisionButton.SKIP: DecisionAction.SKIP,
}


@dataclass(frozen=True)
class DecisionOutcome:
    """The word and the phrase after an action.

    `drop_cloze`: the phrase's cloze markup goes — the user decided on it anew; a phrase in
    Anki keeps it, Anki holds it as a cloze note.
    """

    word_status: WordStatus
    is_decision: bool
    decision_kind: DecisionKind | None
    skipped: bool
    drop_cloze: bool


@dataclass(frozen=True)
class ButtonState:
    """A decision button of a card: the action a press sends (None — the button is off) and
    whether it shows as pressed, holding the card's decision."""

    button: DecisionButton
    action: DecisionAction | None
    pressed: bool


# The buttons of a card, in the order the card shows them.
CARD_BUTTONS = (
    DecisionButton.LEARN, DecisionButton.CLOZE, DecisionButton.KNOWN, DecisionButton.SKIP,
)


@dataclass(frozen=True)
class CardState:
    """What a card shows of the decision and which buttons work; the frontend renders it.

    `buttons`: what each button of the card does, by the rules of `decide`."""

    decided_here: bool
    decided_elsewhere: WordStatus | None
    elsewhere: ElsewhereStatus | None
    buttons: tuple[ButtonState, ...]


def decide(
    occ: Occurrence,
    word_status: WordStatus,
    action: DecisionAction,
    elsewhere: ElsewhereStatus | None,
) -> DecisionOutcome:
    """What `action` on the phrase `occ` does, or the domain error refusing it.

    `elsewhere`: the word is known or learned via another source, for a word still pending.
    """
    assert occ.id is not None
    decided = word_status is not WordStatus.NEW
    if action is DecisionAction.UNSKIP:
        return _phrase_only(occ, word_status, skipped=False)
    if decided and not occ.is_decision:
        if action is DecisionAction.PENDING and occ.skipped:
            return _phrase_only(occ, word_status, skipped=False)
        raise CardDecisionLockedError(occ.id, word_status)
    if action in LEARNING and not decided and elsewhere is not None:
        raise DecidedElsewhereError(occ.id, elsewhere)
    if occ.exported and occ.is_decision and (
        action in UNDOING
        or (action is DecisionAction.CLOZE and occ.decision_kind is not DecisionKind.CLOZE)
    ):
        raise AlreadyInAnkiError(occ.id)
    drop_cloze = not occ.exported and action not in KEEPING_CLOZE
    if action in DECIDING:
        return DecisionOutcome(
            word_status=WordStatus.KNOWN if action is DecisionAction.KNOWN else WordStatus.LEARN,
            is_decision=True,
            decision_kind=_kind(occ, action),
            skipped=False,
            drop_cloze=drop_cloze,
        )
    skip = action is DecisionAction.SKIP
    if decided:
        return DecisionOutcome(
            word_status=WordStatus.NEW, is_decision=False, decision_kind=None,
            skipped=skip, drop_cloze=drop_cloze,
        )
    return _phrase_only(occ, word_status, skipped=skip, drop_cloze=drop_cloze)


def card_state(
    occ: Occurrence, word: StoredCandidate, learning_or_known_elsewhere: ElsewhereStatus | None,
) -> CardState:
    """`learning_or_known_elsewhere`: why the word is done via another source, if it is;
    a word decided in this source shows its own decision instead."""
    status = word.status
    decided = status is not WordStatus.NEW
    decided_here = decided and occ.is_decision
    elsewhere = None if decided else learning_or_known_elsewhere
    return CardState(
        decided_here=decided_here,
        decided_elsewhere=status if decided and not occ.is_decision else None,
        elsewhere=elsewhere,
        buttons=tuple(_button(occ, status, button, elsewhere) for button in CARD_BUTTONS),
    )


def _button(
    occ: Occurrence, status: WordStatus, button: DecisionButton, elsewhere: ElsewhereStatus | None,
) -> ButtonState:
    """A press on the button of the card's decision undoes it, on the decision card only;
    Learn on a cloze card makes it a plain card; Skip on a skipped phrase unskips it. A
    refused action turns the button off. Cloze is off once the phrase is in Anki: its markup
    can't change there."""
    shown = _shown_decision(occ, status)
    cloze_card = status is WordStatus.LEARN and occ.is_decision and occ.cloze is not None
    if button is DecisionButton.CLOZE:
        allowed = not occ.exported and _allowed(occ, status, DecisionAction.CLOZE, elsewhere)
        return ButtonState(button, DecisionAction.CLOZE if allowed else None, cloze_card)
    if button is DecisionButton.SKIP:
        action = DecisionAction.UNSKIP if occ.skipped else DecisionAction.SKIP
        pressed = shown is DecisionButton.SKIP
    elif button is DecisionButton.LEARN and cloze_card and not occ.exported:
        action, pressed = DecisionAction.LEARN, False
    else:
        pressed = shown is button
        if pressed and not occ.is_decision:
            # Another card holds the decision: only it undoes it.
            return ButtonState(button, None, pressed)
        action = DecisionAction.PENDING if pressed else ACTION_OF_BUTTON[button]
    return ButtonState(
        button, action if _allowed(occ, status, action, elsewhere) else None, pressed,
    )


def _shown_decision(occ: Occurrence, status: WordStatus) -> DecisionButton | None:
    """The button holding what the card shows: the word's decision beats a Skip."""
    if status is WordStatus.LEARN:
        return DecisionButton.LEARN
    if status is WordStatus.KNOWN:
        return DecisionButton.KNOWN
    return DecisionButton.SKIP if occ.skipped else None


def wants_generation(
    occ: Occurrence, word: StoredCandidate, learning_or_known_elsewhere: ElsewhereStatus | None,
) -> bool:
    """The card is one someone decides on or sends to Anki, so ✨ makes things for it: an
    open card of a pending word not done via another source, or the Learn/Cloze decision
    card. Skipped cards, other cards of a decided word and Known cards need nothing."""
    if occ.skipped:
        return False
    state = card_state(occ, word, learning_or_known_elsewhere)
    if state.decided_here:
        return word.status is WordStatus.LEARN
    return state.decided_elsewhere is None and state.elsewhere is None


def _allowed(
    occ: Occurrence, status: WordStatus, action: DecisionAction, elsewhere: ElsewhereStatus | None,
) -> bool:
    try:
        decide(occ, status, action, elsewhere)
    except DomainError:
        return False
    return True


def _kind(occ: Occurrence, action: DecisionAction) -> DecisionKind | None:
    """A phrase in Anki keeps its note type; otherwise Cloze makes a cloze, Learn a plain card."""
    if occ.exported and occ.is_decision:
        return occ.decision_kind
    if action is DecisionAction.CLOZE:
        return DecisionKind.CLOZE
    if action is DecisionAction.LEARN:
        return DecisionKind.LEARN
    return None


def _phrase_only(
    occ: Occurrence, word_status: WordStatus, *, skipped: bool, drop_cloze: bool = False,
) -> DecisionOutcome:
    return DecisionOutcome(
        word_status=word_status,
        is_decision=occ.is_decision,
        decision_kind=occ.decision_kind,
        skipped=skipped,
        drop_cloze=drop_cloze,
    )
