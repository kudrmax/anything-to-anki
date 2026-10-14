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
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.elsewhere import Elsewhere
from backend.domain.value_objects.phrase_origin_kind import DecisionKind
from backend.domain.value_objects.word_status import WordStatus

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.entities.stored_candidate import StoredCandidate

__all__ = [
    "CardState",
    "DecisionAction",
    "DecisionButton",
    "DecisionOutcome",
    "Elsewhere",
    "card_state",
    "decide",
    "word_status_of",
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
    UNSKIP = "unskip"
    UNDO = "undo"


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
class CardState:
    """What a card shows of the decision and which buttons work; the frontend renders it."""

    decided_here: bool
    decided_elsewhere: WordStatus | None
    elsewhere: Elsewhere | None
    buttons_enabled: frozenset[DecisionButton]


def word_status_of(word: StoredCandidate) -> WordStatus:
    """The decision on the word.

    TRANSITIONAL(words-phrases): removed in Task 10 — the card-shaped word reads SKIP when
    its primary phrase is skipped; the word itself is pending then.
    """
    if word.status is CandidateStatus.LEARN:
        return WordStatus.LEARN
    if word.status is CandidateStatus.KNOWN:
        return WordStatus.KNOWN
    return WordStatus.PENDING


def decide(
    occ: Occurrence, word_status: WordStatus, action: DecisionAction, elsewhere: Elsewhere | None,
) -> DecisionOutcome:
    """What `action` on the phrase `occ` does, or the domain error refusing it.

    `elsewhere`: the word is known or learned via another source, for a word still pending.
    """
    assert occ.id is not None
    decided = word_status is not WordStatus.PENDING
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
            word_status=WordStatus.PENDING, is_decision=False, decision_kind=None,
            skipped=skip, drop_cloze=drop_cloze,
        )
    return _phrase_only(occ, word_status, skipped=skip, drop_cloze=drop_cloze)


def card_state(
    occ: Occurrence, word: StoredCandidate, learning_or_known_elsewhere: Elsewhere | None,
) -> CardState:
    """`learning_or_known_elsewhere`: why the word is done via another source, if it is;
    a word decided in this source shows its own decision instead."""
    status = word_status_of(word)
    decided = status is not WordStatus.PENDING
    decided_here = decided and occ.is_decision
    elsewhere = None if decided else learning_or_known_elsewhere
    enabled = {
        button for button, action in ACTION_OF_BUTTON.items()
        if _allowed(occ, status, action, elsewhere)
    }
    if occ.skipped:
        enabled.add(DecisionButton.UNSKIP)
    if decided_here and not occ.exported:
        enabled.add(DecisionButton.UNDO)
    return CardState(
        decided_here=decided_here,
        decided_elsewhere=status if decided and not occ.is_decision else None,
        elsewhere=elsewhere,
        buttons_enabled=frozenset(enabled),
    )


def _allowed(
    occ: Occurrence, status: WordStatus, action: DecisionAction, elsewhere: Elsewhere | None,
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
