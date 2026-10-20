"""The one order of sources: the screen's and every set's built from them."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.domain.services.natural_order import natural_key
from backend.domain.value_objects.source_order import (
    SourceGrouping,
    SourceSort,
    SourceSortDirection,
)
from backend.domain.value_objects.source_stage import STAGE_ORDER

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence
    from datetime import datetime

    from backend.domain.entities.source import Source
    from backend.domain.value_objects.source_order import SourceOrder
    from backend.domain.value_objects.source_stage import SourceStage


@dataclass(frozen=True)
class SourceFacts:
    """What the order of a source depends on. `stage` is None when nothing groups by it;
    `last_studied` is None when no card of the source was marked."""

    source: Source
    stage: SourceStage | None = None
    last_studied: datetime | None = None


@dataclass(frozen=True)
class SourceGroup:
    """A run of the ordered sources; `stage` is None when the list is not grouped."""

    stage: SourceStage | None
    sources: tuple[Source, ...]


def arrange(facts: Iterable[SourceFacts], order: SourceOrder) -> list[SourceGroup]:
    """Groups first, when grouped, then the sort inside each group. Empty groups are left
    out."""
    ordered = _SORTS[order.sort](list(facts), order.direction is SourceSortDirection.REVERSE)
    if order.grouping is SourceGrouping.NONE:
        groups = [SourceGroup(None, tuple(f.source for f in ordered))]
    else:
        groups = [
            SourceGroup(stage, tuple(f.source for f in ordered if f.stage is stage))
            for stage in STAGE_ORDER
        ]
    return [group for group in groups if group.sources]


def oldest_added_first(sources: Iterable[Source]) -> list[Source]:
    """The reverse of the date-added order, whatever the user's sort."""
    return [f.source for f in reversed(_by_added([SourceFacts(s) for s in sources]))]


def _by_added(facts: Sequence[SourceFacts], reverse: bool = False) -> list[SourceFacts]:
    """Newest first; sources added at the same moment by id."""
    by_id = sorted(facts, key=_id)
    newest_first = sorted(by_id, key=lambda f: f.source.created_at, reverse=True)
    return newest_first[::-1] if reverse else newest_first


def _by_name(facts: Sequence[SourceFacts], reverse: bool) -> list[SourceFacts]:
    a_to_z = sorted(facts, key=lambda f: (natural_key(f.source.title or ""), _id(f)))
    return a_to_z[::-1] if reverse else a_to_z


def _by_last_studied(facts: Sequence[SourceFacts], reverse: bool) -> list[SourceFacts]:
    """The latest marked first; ties and the never marked keep the date-added order, and the
    never marked come last in both directions."""
    added = _by_added(facts)
    marked = [f for f in added if f.last_studied is not None]
    marked.sort(key=_last_studied, reverse=True)
    return (marked[::-1] if reverse else marked) + [f for f in added if f.last_studied is None]


def _id(facts: SourceFacts) -> int:
    return facts.source.id or 0


def _last_studied(facts: SourceFacts) -> datetime:
    assert facts.last_studied is not None
    return facts.last_studied


_SORTS: Mapping[SourceSort, Callable[[Sequence[SourceFacts], bool], list[SourceFacts]]] = (
    MappingProxyType({
        SourceSort.ADDED: _by_added,
        SourceSort.NAME: _by_name,
        SourceSort.LAST_STUDIED: _by_last_studied,
    })
)
