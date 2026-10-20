from __future__ import annotations

from datetime import UTC, datetime

import pytest
from backend.domain.entities.source import Source
from backend.domain.services.source_order import SourceFacts, arrange, oldest_added_first
from backend.domain.value_objects.source_order import SourceGrouping, SourceOrder, SourceSort
from backend.domain.value_objects.source_stage import SourceStage
from backend.domain.value_objects.source_status import SourceStatus

pytestmark = pytest.mark.unit

FLAT = SourceGrouping.NONE


def _day(day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(2026, 1, day, hour, minute, tzinfo=UTC)


def facts(
    source_id: int, *, added: datetime, title: str | None = None,
    stage: SourceStage | None = None, studied: datetime | None = None,
) -> SourceFacts:
    source = Source(id=source_id, title=title, status=SourceStatus.DONE, created_at=added)
    return SourceFacts(source, stage, studied)


def ordered(found: list[SourceFacts], order: SourceOrder) -> list[tuple[str | None, list[int]]]:
    return [
        (g.stage.value if g.stage else None, [s.id or 0 for s in g.sources])
        for g in arrange(found, order)
    ]


def test_the_default_is_by_stage_newest_added_first() -> None:
    assert SourceOrder() == SourceOrder(SourceGrouping.STAGE, SourceSort.ADDED)


def test_added_is_newest_first_and_ties_go_by_id() -> None:
    found = [
        facts(3, added=_day(1)), facts(2, added=_day(2)), facts(1, added=_day(2)),
    ]
    assert ordered(found, SourceOrder(FLAT, SourceSort.ADDED)) == [(None, [1, 2, 3])]


def test_name_ignores_case_and_ties_go_by_id() -> None:
    found = [
        facts(1, added=_day(1), title="banana"),
        facts(4, added=_day(2), title="Apple"),
        facts(2, added=_day(3), title="apple"),
        facts(3, added=_day(4), title=None),
    ]
    assert ordered(found, SourceOrder(FLAT, SourceSort.NAME)) == [(None, [3, 2, 4, 1])]


def test_last_studied_is_by_the_exact_time_newest_first() -> None:
    found = [
        facts(1, added=_day(1), studied=_day(10, 9, 0)),
        facts(2, added=_day(2), studied=_day(10, 9, 1)),
        facts(3, added=_day(3), studied=_day(9, 23, 59)),
    ]
    assert ordered(found, SourceOrder(FLAT, SourceSort.LAST_STUDIED)) == [(None, [2, 1, 3])]


def test_never_studied_come_after_the_studied_in_added_order() -> None:
    found = [
        facts(1, added=_day(1)),
        facts(2, added=_day(2), studied=_day(5)),
        facts(3, added=_day(3)),
        facts(4, added=_day(4)),
    ]
    assert ordered(found, SourceOrder(FLAT, SourceSort.LAST_STUDIED)) == [(None, [2, 4, 3, 1])]


def test_studied_at_the_same_moment_keep_the_added_order() -> None:
    found = [
        facts(1, added=_day(1), studied=_day(5)),
        facts(2, added=_day(2), studied=_day(5)),
    ]
    assert ordered(found, SourceOrder(FLAT, SourceSort.LAST_STUDIED)) == [(None, [2, 1])]


def test_grouped_by_stage_in_stage_order_then_sorted_inside_without_empty_groups() -> None:
    found = [
        facts(1, added=_day(1), title="b", stage=SourceStage.READY),
        facts(2, added=_day(2), title="c", stage=SourceStage.REVIEWED),
        facts(3, added=_day(3), title="a", stage=SourceStage.READY),
        facts(4, added=_day(4), title="d", stage=SourceStage.IN_PROGRESS),
    ]
    assert ordered(found, SourceOrder(SourceGrouping.STAGE, SourceSort.NAME)) == [
        ("in_progress", [4]),
        ("ready", [3, 1]),
        ("reviewed", [2]),
    ]


def test_ungrouped_is_one_group_without_a_stage() -> None:
    found = [
        facts(1, added=_day(1), stage=SourceStage.READY),
        facts(2, added=_day(2), stage=SourceStage.PREPARING),
    ]
    assert ordered(found, SourceOrder(FLAT, SourceSort.ADDED)) == [(None, [2, 1])]


def test_nothing_to_arrange_is_no_group() -> None:
    assert arrange([], SourceOrder(FLAT, SourceSort.ADDED)) == []


def test_oldest_added_first_is_the_added_order_reversed() -> None:
    sources = [
        facts(3, added=_day(1)).source, facts(1, added=_day(2)).source,
        facts(2, added=_day(2)).source,
    ]
    assert [s.id for s in oldest_added_first(sources)] == [3, 2, 1]
