"""Which phrase of a word the selection shows."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy

if TYPE_CHECKING:
    from backend.domain.value_objects.occurrence_row import OccurrenceRow

UNSCORED = math.inf
UNPLACED = (math.inf, math.inf, math.inf)


@dataclass(frozen=True)
class SelectionChange:
    """The phrase that gets the selection mark, and the phrases that lose it."""

    set_selection: int | None = None
    clear_selection: tuple[int, ...] = ()

    @property
    def is_empty(self) -> bool:
        return self.set_selection is None and not self.clear_selection


def is_frozen(o: OccurrenceRow, include_open: bool) -> bool:
    """A shown phrase the selection does not take its mark from.

    Results and a running job freeze it unless open cards are rebuilt too; the rest always.
    """
    always = (
        o.is_decision
        or o.exported
        or o.skipped
        or o.edited_by_user
        or o.origin is not OccurrenceOrigin.AUTO
    )
    return always or (not include_open and (o.has_results or o.has_active_job))


def select_phrases(
    word_occurrences: list[OccurrenceRow], word_decided: bool, include_open: bool,
) -> SelectionChange:
    """The selection marks of one word after processing or a rebuild.

    A decided word keeps its cards as they are. A frozen selection mark stays, and no other
    selection mark beside it. A word whose selection card was replaced — by an example or by
    the user's own mark on an auto phrase, so no selection mark is left — gets none.
    Otherwise the best auto phrase that is not skipped is selected: the lowest score, then
    the one read first. Only selection marks are set or cleared.
    """
    if word_decided:
        return SelectionChange()
    selected = [o for o in word_occurrences if o.shown_by is ShownBy.SELECTION]
    frozen = [o for o in selected if is_frozen(o, include_open)]
    if frozen:
        return _keep(selected, {o.id for o in frozen})
    if not selected and any(_replaces_selection(o) for o in word_occurrences):
        return SelectionChange()
    candidates = [
        o for o in word_occurrences
        if o.origin is OccurrenceOrigin.AUTO and not o.skipped and o.shown_by is not ShownBy.USER
    ]
    if not candidates:
        return _keep(selected, set())
    best = min(candidates, key=_rank)
    change = _keep(selected, {best.id})
    if best.shown_by is ShownBy.SELECTION:
        return change
    return SelectionChange(set_selection=best.id, clear_selection=change.clear_selection)


def _keep(selected: list[OccurrenceRow], kept: set[int]) -> SelectionChange:
    return SelectionChange(clear_selection=tuple(o.id for o in selected if o.id not in kept))


def _replaces_selection(o: OccurrenceRow) -> bool:
    if o.shown_by is not ShownBy.USER:
        return False
    return o.origin in (OccurrenceOrigin.EXAMPLE, OccurrenceOrigin.AUTO)


def _rank(o: OccurrenceRow) -> tuple[float, tuple[float, float, float], int]:
    score = UNSCORED if o.fragment_score is None else o.fragment_score
    place = UNPLACED if o.key is None else (o.key.block, o.key.line, o.key.char)
    return score, place, o.id
