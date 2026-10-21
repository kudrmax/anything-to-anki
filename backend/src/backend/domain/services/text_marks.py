"""Which targets of the shown phrases are marked in a document's text."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True)
class PlacedMark:
    """The target of a shown phrase, between two offsets of the document's text."""

    phrase_id: int
    start: int
    end: int


def marks_shown(marks: Iterable[PlacedMark]) -> list[PlacedMark]:
    """The marks that do not overlap, in reading order. Where marks would overlap, the one
    that starts first stays; of two starting together, the longer one (a phrasal verb
    rather than its verb); of two the same, the one of the older phrase."""
    shown: list[PlacedMark] = []
    taken_until = -1
    for mark in sorted(marks, key=lambda m: (m.start, -m.end, m.phrase_id)):
        if mark.start < taken_until:
            continue
        shown.append(mark)
        taken_until = mark.end
    return shown
