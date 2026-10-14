from __future__ import annotations

import pytest
from backend.domain.services.source_stage import is_pending, shown_status, stage_of
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_stage import SourceStage
from backend.domain.value_objects.source_status import SourceStatus


@pytest.mark.unit
@pytest.mark.parametrize(("status", "awaiting", "stage"), [
    (SourceStatus.PARTIALLY_REVIEWED, False, SourceStage.IN_PROGRESS),
    (SourceStatus.DONE, False, SourceStage.READY),
    (SourceStatus.REVIEWED, False, SourceStage.REVIEWED),
    (SourceStatus.NEW, False, SourceStage.PREPARING),
    (SourceStatus.ERROR, False, SourceStage.PREPARING),
    (SourceStatus.DONE, True, SourceStage.PREPARING),
])
def test_stage_of(status: SourceStatus, awaiting: bool, stage: SourceStage) -> None:
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
    assert shown_status(SourceStatus.NEW, busy_with) == shown
