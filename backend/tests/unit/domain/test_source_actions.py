"""What a source in the list lets the user do, and how far its review has got."""
from __future__ import annotations

import pytest
from backend.domain.entities.source import Source
from backend.domain.services.source_actions import (
    can_delete,
    can_export,
    can_review,
    progress_caption,
    review_fraction,
)
from backend.domain.value_objects.decision_progress import DecisionProgress
from backend.domain.value_objects.review_status import ReviewStatus
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_scope import SourceScope
from backend.domain.value_objects.source_status import SourceStatus

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(("status", "reviewable"), [
    (ReviewStatus.NEW, False),
    (ReviewStatus.ERROR, False),
    (ReviewStatus.DONE, True),
    (ReviewStatus.PARTIALLY_REVIEWED, True),
    (ReviewStatus.REVIEWED, True),
])
def test_a_processed_source_can_be_reviewed(status: ReviewStatus, reviewable: bool) -> None:
    assert can_review(SourceScope.source(1), status) is reviewable


@pytest.mark.parametrize(("status", "learn_count", "exportable"), [
    (ReviewStatus.NEW, 0, False),
    (ReviewStatus.ERROR, 1, False),
    (ReviewStatus.DONE, 0, False),
    (ReviewStatus.DONE, 1, True),
    (ReviewStatus.PARTIALLY_REVIEWED, 0, False),
    (ReviewStatus.PARTIALLY_REVIEWED, 2, True),
    (ReviewStatus.REVIEWED, 0, False),
    (ReviewStatus.REVIEWED, 3, True),
])
def test_a_processed_source_with_a_word_to_learn_can_be_exported(
    status: ReviewStatus, learn_count: int, exportable: bool,
) -> None:
    """Decisions alone are not enough: all-Known or all-Skip leaves nothing to export."""
    assert can_export(status, learn_count) is exportable


def test_unsorted_is_never_reviewable() -> None:
    assert can_review(SourceScope.unsorted(), ReviewStatus.DONE) is False
    assert can_review(SourceScope.collection(1), ReviewStatus.DONE) is True
    assert can_review(SourceScope.source(1), ReviewStatus.NEW) is False


def test_a_free_source_can_be_deleted() -> None:
    assert can_delete(Source(id=1, status=SourceStatus.DONE), None)


def test_a_busy_or_built_in_source_cannot_be_deleted() -> None:
    assert not can_delete(Source(id=1, status=SourceStatus.NEW), SourceOperationKind.PROCESS)
    assert not can_delete(Source(id=1, status=SourceStatus.DONE), SourceOperationKind.UPDATE)
    saved_phrases = Source.saved_phrases()
    saved_phrases.id = 2
    assert not can_delete(saved_phrases, None)


@pytest.mark.parametrize(("status", "progress", "fraction"), [
    (ReviewStatus.DONE, DecisionProgress(decided=1, total=4), 0.25),
    (ReviewStatus.DONE, DecisionProgress(), 0.0),
    (ReviewStatus.REVIEWED, DecisionProgress(decided=1, total=4), 1.0),
    (ReviewStatus.REVIEWED, DecisionProgress(), 1.0),
])
def test_review_fraction(
    status: ReviewStatus, progress: DecisionProgress, fraction: float,
) -> None:
    assert review_fraction(status, progress) == fraction


@pytest.mark.parametrize(("status", "cards", "progress", "learn", "busy", "caption"), [
    (ReviewStatus.DONE, 0, DecisionProgress(), 0, None, "Nothing to learn"),
    (ReviewStatus.DONE, 3, DecisionProgress(), 0, None, "Nothing ready"),
    (ReviewStatus.DONE, 1, DecisionProgress(decided=0, total=1), 0, None, "1 phrase"),
    (ReviewStatus.DONE, 4, DecisionProgress(decided=0, total=4), 0, None, "4 phrases"),
    (ReviewStatus.PARTIALLY_REVIEWED, 4, DecisionProgress(decided=1, total=4), 1, None,
     "1 of 4 decided"),
    (ReviewStatus.REVIEWED, 4, DecisionProgress(decided=4, total=4), 2, None, "2 to learn"),
    (ReviewStatus.DONE, 4, DecisionProgress(), 0, SourceOperationKind.UPDATE, "Updating…"),
    (ReviewStatus.DONE, 4, DecisionProgress(), 0, SourceOperationKind.REFRESH, "Refreshing…"),
])
def test_progress_caption(
    status: ReviewStatus, cards: int, progress: DecisionProgress, learn: int,
    busy: SourceOperationKind | None, caption: str,
) -> None:
    assert progress_caption(status, cards, progress, learn, busy) == caption
