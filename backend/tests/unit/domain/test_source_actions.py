"""What a source in the list lets the user do, and how far its review has got."""
from __future__ import annotations

import pytest
from backend.domain.entities.source import Source
from backend.domain.services.source_actions import (
    can_delete,
    can_export,
    can_review,
    review_fraction,
)
from backend.domain.value_objects.decision_progress import DecisionProgress
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_status import SourceStatus

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(("status", "reviewable"), [
    (SourceStatus.NEW, False),
    (SourceStatus.ERROR, False),
    (SourceStatus.DONE, True),
    (SourceStatus.PARTIALLY_REVIEWED, True),
    (SourceStatus.REVIEWED, True),
])
def test_a_processed_source_can_be_reviewed(status: SourceStatus, reviewable: bool) -> None:
    assert can_review(status) is reviewable


@pytest.mark.parametrize(("status", "exportable"), [
    (SourceStatus.NEW, False),
    (SourceStatus.DONE, False),
    (SourceStatus.PARTIALLY_REVIEWED, True),
    (SourceStatus.REVIEWED, True),
])
def test_a_source_with_decisions_can_be_exported(status: SourceStatus, exportable: bool) -> None:
    assert can_export(status) is exportable


def test_a_free_source_can_be_deleted() -> None:
    assert can_delete(Source(id=1, status=SourceStatus.DONE), None)


def test_a_busy_or_built_in_source_cannot_be_deleted() -> None:
    assert not can_delete(Source(id=1, status=SourceStatus.NEW), SourceOperationKind.PROCESS)
    assert not can_delete(Source(id=1, status=SourceStatus.DONE), SourceOperationKind.REBUILD)
    saved_phrases = Source.saved_phrases()
    saved_phrases.id = 2
    assert not can_delete(saved_phrases, None)


@pytest.mark.parametrize(("status", "progress", "fraction"), [
    (SourceStatus.DONE, DecisionProgress(decided=1, total=4), 0.25),
    (SourceStatus.DONE, DecisionProgress(), 0.0),
    (SourceStatus.REVIEWED, DecisionProgress(decided=1, total=4), 1.0),
    (SourceStatus.REVIEWED, DecisionProgress(), 1.0),
])
def test_review_fraction(
    status: SourceStatus, progress: DecisionProgress, fraction: float,
) -> None:
    assert review_fraction(status, progress) == fraction
