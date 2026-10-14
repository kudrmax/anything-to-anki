from __future__ import annotations

import pytest
from backend.domain.services.source_stage import is_pending, stage_of
from backend.domain.value_objects.source_stage import SourceStage
from backend.domain.value_objects.source_status import SourceStatus


@pytest.mark.unit
@pytest.mark.parametrize(("status", "awaiting", "stage"), [
    (SourceStatus.PARTIALLY_REVIEWED, False, SourceStage.IN_PROGRESS),
    (SourceStatus.DONE, False, SourceStage.READY),
    (SourceStatus.REVIEWED, False, SourceStage.REVIEWED),
    (SourceStatus.NEW, False, SourceStage.PREPARING),
    (SourceStatus.PROCESSING, False, SourceStage.PREPARING),
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
    (SourceStatus.PROCESSING, False, False),
    (SourceStatus.DONE, False, False),
])
def test_is_pending(status: SourceStatus, awaiting: bool, pending: bool) -> None:
    assert is_pending(status, awaiting_generation=awaiting) is pending
