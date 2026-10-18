"""The card DTO and the decide API in their old values, read from the card view, until the
API goes by button (plan step 11). Nothing here decides: every value comes from the view."""
from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.domain.services.card_view import Command, Where
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.card_choice import Press
from backend.domain.value_objects.word_status import WordStatus

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.domain.services.card_view import ButtonState, CardView


class DecisionAction(StrEnum):
    """What the old API sends for a card. PENDING undoes what is pressed; UNSKIP undoes a
    Skip."""

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


BUTTON_OF_PRESS: Mapping[Press, DecisionButton] = MappingProxyType(
    {press: DecisionButton(press.value) for press in Press},
)
_ACTION_OF_PRESS: Mapping[Press, DecisionAction] = MappingProxyType(
    {press: DecisionAction(press.value) for press in Press},
)
_PRESS_OF_ACTION: Mapping[DecisionAction, Press] = MappingProxyType(
    {DecisionAction(press.value): press for press in Press},
)
_UNPRESS: Mapping[Press, DecisionAction] = MappingProxyType(
    {
        **{press: DecisionAction.PENDING for press in Press},
        Press.SKIP: DecisionAction.UNSKIP,
    },
)
# NEW → pending, LEARN / LEARNING → learn, KNOWN (by the choice, the list or the timer) → known.
OLD_WORD_STATUS: Mapping[WordStatus, WordStatus] = MappingProxyType(
    {
        WordStatus.NEW: WordStatus.NEW,
        WordStatus.LEARN: WordStatus.LEARN,
        WordStatus.LEARNING: WordStatus.LEARN,
        WordStatus.KNOWN: WordStatus.KNOWN,
    },
)


def word_status(view: CardView) -> WordStatus:
    """The word's own status as the old DTO had it: a word open here is pending, even when it
    is decided in another source."""
    if view.shown.where is Where.OTHER_SOURCE:
        return WordStatus.NEW
    return OLD_WORD_STATUS[view.shown.status]


def card_status(view: CardView) -> CandidateStatus:
    """The decision the card shows: the word's beats a Skip."""
    status = word_status(view)
    if status is WordStatus.NEW and view.shown.skipped:
        return CandidateStatus.SKIP
    return CandidateStatus(status.value)


def button_action(button: ButtonState, view: CardView) -> DecisionAction | None:
    """Cloze opens the markup editor where the card can edit its markup or Cloze lands on a
    cloze; pressing the pressed button undoes it; a refused button is off."""
    if button.button is Press.CLOZE:
        opens = view.can_edit_cloze or button.command is Command.EDIT_CLOZE
        return DecisionAction.CLOZE if opens else None
    if button.command is None:
        return None
    if button.pressed:
        return _UNPRESS[button.button]
    return _ACTION_OF_PRESS[button.button]


def press_of(action: DecisionAction, view: CardView) -> Press | None:
    """The press an old action means on this card: "pending" is the pressed button that
    works (a decision before a Skip), "unskip" is Skip on a skipped card. None: nothing to
    undo, so nothing happens."""
    if action is DecisionAction.PENDING:
        undoable = [b.button for b in view.buttons if b.pressed and b.command is not None]
        deciding = [press for press in undoable if press is not Press.SKIP]
        return next(iter(deciding or undoable), None)
    if action is DecisionAction.UNSKIP:
        return Press.SKIP if view.shown.skipped else None
    return _PRESS_OF_ACTION[action]
