from __future__ import annotations

import pytest
from backend.domain.services.source_stage import (
    is_pending,
    set_operation,
    shown_status,
    stage_of,
)
from backend.domain.value_objects.review_status import ReviewStatus
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_stage import SourceStage
from backend.domain.value_objects.source_status import SourceStatus


@pytest.mark.unit
@pytest.mark.parametrize(("status", "awaiting", "stage"), [
    (ReviewStatus.PARTIALLY_REVIEWED, False, SourceStage.IN_PROGRESS),
    (ReviewStatus.DONE, False, SourceStage.READY),
    (ReviewStatus.REVIEWED, False, SourceStage.REVIEWED),
    (ReviewStatus.NEW, False, SourceStage.PREPARING),
    (ReviewStatus.ERROR, False, SourceStage.PREPARING),
    (ReviewStatus.DONE, True, SourceStage.PREPARING),
])
def test_stage_of(status: ReviewStatus, awaiting: bool, stage: SourceStage) -> None:
    assert stage_of(status, awaiting_generation=awaiting) is stage


@pytest.mark.unit
@pytest.mark.parametrize(("status", "awaiting", "pending"), [
    (SourceStatus.NEW, False, True),
    (SourceStatus.ERROR, False, True),
    (SourceStatus.NEW, True, False),
    (SourceStatus.DONE, False, False),
])
def test_is_pending(status: SourceStatus, awaiting: bool, pending: bool) -> None:
    assert is_pending(status, awaiting_generation=awaiting) is pending


@pytest.mark.unit
def test_a_source_held_by_an_operation_is_not_pending() -> None:
    assert not is_pending(SourceStatus.NEW, awaiting_generation=False, busy=True)


@pytest.mark.unit
@pytest.mark.parametrize(("busy_with", "shown"), [
    (None, "new"),
    (SourceOperationKind.PROCESS, "processing"),
    (SourceOperationKind.REBUILD, "new"),
])
def test_a_source_shows_processing_only_while_it_is_processed(
    busy_with: SourceOperationKind | None, shown: str,
) -> None:
    assert shown_status(ReviewStatus.NEW, busy_with) == shown


@pytest.mark.unit
@pytest.mark.parametrize(("status", "operations", "busy_with"), [
    (ReviewStatus.NEW, [None, SourceOperationKind.PROCESS], SourceOperationKind.PROCESS),
    (ReviewStatus.ERROR, [SourceOperationKind.PROCESS], SourceOperationKind.PROCESS),
    (ReviewStatus.DONE, [SourceOperationKind.PROCESS], None),
    (ReviewStatus.NEW, [SourceOperationKind.REBUILD], None),
    (ReviewStatus.NEW, [], None),
])
def test_a_set_is_processed_while_a_source_is_and_none_is_ready(
    status: ReviewStatus, operations: list[SourceOperationKind | None],
    busy_with: SourceOperationKind | None,
) -> None:
    assert set_operation(status, operations) is busy_with
